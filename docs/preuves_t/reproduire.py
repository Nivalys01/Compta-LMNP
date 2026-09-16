"""Audit T : scénarios fictifs, aucun accès aux bases utilisateur."""
import ast
import importlib.metadata as md
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import threading
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'compta_lmnp'), str(ROOT / 'compta_lmnp/modules')]
import app as A
import dossiers as D
import init_db
import perennite

out = {'python': sys.version, 'sqlite': sqlite3.sqlite_version,
       'paquets': {d.metadata['Name']: d.version for d in md.distributions()}}
with tempfile.TemporaryDirectory(prefix='audit-t-') as tmp:
    A.HERE = tmp
    A.DB = str(Path(tmp) / 'compta.db')
    A.BAC_A_SABLE_DB = str(Path(tmp) / 'bac.db')
    c = init_db.init_blanc(A.DB, 2026)
    c.close()
    client = A.app.test_client()
    out['host'] = {
        'get': client.get('/dossiers', base_url='http://audit.invalid:5000').status_code,
        'post': client.post('/dossiers/creer', base_url='http://audit.invalid:5000',
                            headers={'Origin': 'http://audit.invalid:5000'},
                            data={'nom': 'Dossier Fictif'}).status_code,
        'creation_effective': D.chemin_db(tmp, 'dossier-fictif') is not None,
        'origine_distincte': client.post('/dossiers/creer', headers={'Origin': 'http://audit.invalid'},
                                         data={'nom': 'Refuse'}).status_code}
    # La clé personnalisée est admise par l'API publique.
    payload = '</script><script>alert(731)</script>'
    out['html_post'] = client.post('/reglementation/gabarit', data={
        'libelle': payload, 'compte_num': '616110', 'nature': 'charge'}).status_code
    traces = []
    connecter_page = sqlite3.connect
    def connexion_trace(*args, **kwargs):
        conn = connecter_page(*args, **kwargs)
        conn.set_trace_callback(traces.append)
        return conn
    with patch.object(A.sqlite3, 'connect', connexion_trace):
        page = client.get('/saisie').get_data(as_text=True)
    out['requetes_saisie'] = {
        'total_sql': len(traces),
        'lectures_gabarits': sum('FROM gabarit_personnalise' in q for q in traces)}
    out['html_script'] = {'balise_brute_presente': payload in page,
                          'contexte_script': 'const perioMap = ' in page}
    # Migration suspendue : la deuxième requête doit attendre ou refuser.
    A._MIGRES.clear()
    c = sqlite3.connect(A.DB)
    c.execute("UPDATE meta SET valeur='7' WHERE cle='version_schema'")
    c.commit(); c.close()
    entre, finir = threading.Event(), threading.Event()
    def migration_suspendue(_):
        entre.set()
        if not finir.wait(10):
            raise RuntimeError('timeout preuve')
        raise RuntimeError('panne fictive migration')
    def requete():
        with A.app.test_client() as cl:
            out['migration_premiere_requete'] = cl.get('/saisie').status_code
    with patch.object(A.migrations, 'migrer', migration_suspendue):
        th = threading.Thread(target=requete)
        th.start()
        assert entre.wait(10)
        out['migration_requete_pendant'] = client.get('/saisie').status_code
        finir.set(); th.join(10)
        assert not th.is_alive()
    # Deux lectures du registre imposées avant les deux écritures réelles.
    racine = str(Path(tmp) / 'registre')
    Path(racine).mkdir()
    D._enregistrer(racine, [{'slug': 'alpha', 'nom': 'Alpha', 'chemin': 'a.db'},
                           {'slug': 'beta', 'nom': 'Beta', 'chemin': 'b.db'}])
    charger = D._charger
    barriere = threading.Barrier(2)
    premier_fini = threading.Event()
    def lecture(r):
        data = charger(r)
        barriere.wait(10)
        if threading.current_thread().name == 'beta':
            assert premier_fini.wait(10)
        return data
    erreurs = []
    def renommer(slug):
        try:
            D.renommer(racine, slug, slug + '-modifie')
        except Exception as exc:
            erreurs.append(type(exc).__name__)
        finally:
            if slug == 'alpha': premier_fini.set()
    with patch.object(D, '_charger', lecture):
        threads = [threading.Thread(target=renommer, args=(s,), name=s) for s in ('alpha', 'beta')]
        for th in threads: th.start()
        for th in threads: th.join(15)
        assert all(not th.is_alive() for th in threads)
    out['registre'] = {'erreurs': erreurs, 'noms_finaux': [e['nom'] for e in charger(racine)]}

    # Collision du nom de sauvegarde : arrêter après choix, avant création.
    from datetime import datetime
    connecter = sqlite3.connect
    barriere_copie = threading.Barrier(2)
    copies, echecs = [], []
    def connexion(chemin, *args, **kwargs):
        if str(chemin) == A.DB:
            barriere_copie.wait(10)
        return connecter(chemin, *args, **kwargs)
    def copier():
        try:
            copies.append(perennite.sauvegarder(A.DB, 'audit-t'))
        except Exception as exc:
            echecs.append(type(exc).__name__)
    with patch.object(perennite, 'datetime') as horloge, patch.object(perennite.sqlite3, 'connect', connexion):
        horloge.now.return_value = datetime(2026, 9, 16, 12, 0, 0)
        threads = [threading.Thread(target=copier) for _ in range(2)]
        for th in threads: th.start()
        for th in threads: th.join(15)
        assert all(not th.is_alive() for th in threads)
    out['sauvegardes'] = {'retours': len(copies), 'chemins_distincts': len(set(copies)), 'erreurs': echecs}

files = list((ROOT / 'compta_lmnp').glob('*.py')) + list((ROOT / 'compta_lmnp/modules').glob('*.py'))
metrics = []
graph = {}
for p in files:
    tree = ast.parse(p.read_text())
    graph[p.stem] = sorted({(n.module or '').split('.')[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)} |
                           {a.name.split('.')[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names})
    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            branches = sum(isinstance(x, (ast.If, ast.For, ast.While, ast.ExceptHandler, ast.IfExp)) for x in ast.walk(n))
            metrics.append({'fichier': str(p.relative_to(ROOT)), 'fonction': n.name,
                            'ligne': n.lineno, 'lignes': n.end_lineno-n.lineno+1, 'branches_ast': branches})
out['fonctions_longues'] = sorted(metrics, key=lambda x:x['lignes'], reverse=True)[:12]
out['imports_reciproques'] = sorted({tuple(sorted((a,b))) for a, bs in graph.items() for b in bs if a != b and a in graph.get(b, [])})
out['tailles'] = {str(p.relative_to(ROOT)): len(p.read_text().splitlines()) for p in files}
print(json.dumps(out, ensure_ascii=False, indent=2))
