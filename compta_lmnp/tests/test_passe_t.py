# Compta LMNP — Copyright © 2026 Sylvain FAURE et les contributeurs.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Non-régression des constats de la passe T (architecture, sécurité, fiabilité).

Le fil rouge de cette passe est la **composition** : chaque garde prise
isolément faisait ce qu'elle annonçait, et c'est leur assemblage qui laissait
passer. Quatre des cinq défauts prioritaires ne sont visibles que sous
CONCURRENCE, et aucun test séquentiel ne pouvait les voir — la suite passait
au vert pendant que l'audit les reproduisait.

D'où la forme des tests qui suivent : ils utilisent des **barrières** pour
forcer deux fils d'exécution à se croiser à l'endroit exact où l'ancien code
se trompait. Un test séquentiel visant une propriété concurrente ne prouve
rien, et laisse croire qu'un constat est clos (constat T-08).

Les deux autres sont des défauts de frontière HTTP : un nom d'hôte pris pour
une référence de confiance, et du JSON inséré dans un contexte script.

Aucune donnée réelle : bases blanches, identités fictives, fichiers
temporaires.

Lancer :  pytest -q tests/test_passe_t.py
"""
import importlib
import os
import sqlite3
import sys
import threading

import conftest  # noqa: F401  (insère la racine et modules/ dans sys.path)

import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

import dossiers
import gabarits
import init_db
import perennite


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db = str(tmp_path / "compta.db")
    init_db.init(db, "blanc", annee_cible=2026).close()
    monkeypatch.setenv("COMPTA_DB", db)
    monkeypatch.setenv("COMPTA_DB_BAC_A_SABLE", str(tmp_path / "bac.db"))
    import app as app_mod
    importlib.reload(app_mod)
    monkeypatch.setattr(app_mod, "HERE", str(tmp_path))
    yield app_mod, app_mod.app.test_client()
    monkeypatch.delenv("COMPTA_DB")
    importlib.reload(app_mod)


# ═══ T-01 — l'hôte annoncé n'est pas une référence de confiance ════════

def test_t01_un_hote_arbitraire_est_refuse_en_lecture_et_en_ecriture(client):
    """Se lier à 127.0.0.1 restreint l'interface réseau, pas les noms qui
    résolvent vers elle : c'est le principe du DNS rebinding. La garde
    d'origine comparait `Origin` au `Host` fourni par le client — un
    attaquant maîtrisant les deux les faisait coïncider, et obtenait GET
    200, POST 302 et un dossier réellement créé."""
    _app_mod, cl = client
    hostile = "audit.invalid:5000"
    assert cl.get("/dossiers", base_url=f"http://{hostile}").status_code == 403
    r = cl.post("/dossiers/creer", base_url=f"http://{hostile}",
                headers={"Origin": f"http://{hostile}"},
                data={"nom": "Dossier hostile"})
    assert r.status_code == 403
    # et surtout : aucun effet de bord n'a eu lieu
    assert cl.get("/dossiers").status_code == 200
    assert b"Dossier hostile" not in cl.get("/dossiers").data


@pytest.mark.parametrize("hote", ["localhost:5000", "127.0.0.1:5000",
                                  "[::1]:5000", "localhost"])
def test_t01_les_hotes_locaux_restent_acceptes(client, hote):
    """Contre-épreuve indispensable : une garde qui refuse tout le monde
    n'est pas une garde, c'est une panne."""
    _app_mod, cl = client
    assert cl.get("/", base_url=f"http://{hote}").status_code in (200, 302)


def test_t01_la_garde_hote_passe_avant_toute_autre(client):
    """L'ordre est la moitié du correctif : Flask exécute les
    `before_request` dans l'ordre d'enregistrement, et son propre filtrage
    TRUSTED_HOSTS n'intervient qu'au ROUTAGE. Enregistrée après, la garde
    laisserait la migration et la garde de version travailler d'abord."""
    app_mod, _cl = client
    noms = [f.__name__ for f in
            app_mod.app.before_request_funcs[None]]
    assert noms[0] == "_garde_hote", noms
    assert noms.index("_garde_hote") < noms.index("_garde_version_schema")
    assert sorted(app_mod.app.config["TRUSTED_HOSTS"])


# ═══ T-02 — du JSON dans un contexte script ════════════════════════════

def test_t02_le_gabarit_reel_echappe_les_delimiteurs_html():
    """`json.dumps` produit du JSON valide, mais n'échappe pas le
    délimiteur HTML `</script>` ; le filtre `| safe` retirait ensuite la
    dernière protection. Une catégorie personnalisée — saisie par un
    formulaire local — fermait donc le script de la page de saisie.

    Le test rend **la ligne réelle du gabarit**, extraite de `pages.py`,
    avec une valeur hostile. Passer par la route complète ne prouvait rien :
    la normalisation de la clé masquait la charge, et le test restait vert
    avec `| safe` comme avec `| tojson` — un test qui ne distingue pas les
    deux états ne ferme pas le constat (constat T-08).
    """
    from flask import Flask, render_template_string

    import pages
    lignes = [ligne for ligne in pages.PAGE_SAISIE.splitlines()
              if "perioMap" in ligne]
    assert lignes, "la ligne du catalogue a disparu du gabarit"
    hostile = "</script><script>alert(731)</script>"
    with Flask(__name__).app_context():
        rendu = render_template_string("\n".join(lignes),
                                       perio={hostile: "mensuel"})
    assert "</script>" not in rendu, (
        f"le gabarit laisse fermer son propre script : {rendu[:120]}")
    assert "\\u003c" in rendu           # échappement effectif, pas suppression
    assert "alert(731)" in rendu        # la donnée est conservée, pas censurée


def test_t02_aucun_json_brut_ne_reste_dans_un_contexte_script():
    """Anti-régression de méthode : `| safe` sur du JSON dans un `<script>`
    est le motif à bannir, pas seulement ses deux occurrences connues."""
    src = open(conftest.source("pages.py"), encoding="utf-8").read()
    fautifs = [ligne.strip() for ligne in src.splitlines()
               if "| safe }}" in ligne and "json" in ligne.lower()]
    assert not fautifs, f"JSON rendu avec | safe : {fautifs}"


# ═══ T-03 — une migration en cours ne publie pas son succès ════════════

def test_t03_une_requete_concurrente_attend_la_fin_de_la_migration(client,
                                                                  tmp_path):
    """Le marqueur de succès était posé sous verrou, mais la migration avait
    lieu APRÈS sa libération : une seconde requête voyait « déjà migré »
    pendant que la première transformait encore le schéma, et repartait
    servir des pages métier.

    La barrière force exactement ce croisement."""
    app_mod, _cl = client
    chemin = os.environ["COMPTA_DB"]
    app_mod._MIGRES.clear()
    app_mod._MIGRATIONS_EN_ECHEC.clear()
    app_mod._MIGRATIONS_EN_COURS.clear()

    entree = threading.Event()
    liberation = threading.Event()
    etat = {}

    def migration_lente(_chemin):
        entree.set()                       # « je suis dans la migration »
        liberation.wait(timeout=5)

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(app_mod.migrations, "migrer", migration_lente)
        mp.setattr(app_mod.init_db, "version_base", lambda _c: 0)

        premier = threading.Thread(target=app_mod._migrer_si_besoin)
        premier.start()
        assert entree.wait(timeout=5), "la migration n'a pas démarré"

        # Pendant que la migration travaille, le chemin ne doit PAS être
        # publié comme prêt — c'est tout l'objet du constat.
        assert chemin not in app_mod._MIGRES
        assert chemin in app_mod._MIGRATIONS_EN_COURS

        def concurrent():
            try:
                mp.setattr(app_mod, "_ATTENTE_MIGRATION_S", 0.2)
                app_mod._migrer_si_besoin()
                etat["issue"] = "passee"
            except app_mod.MigrationEnCours:
                etat["issue"] = "refusee"

        second = threading.Thread(target=concurrent)
        second.start()
        second.join(timeout=5)
        # La seconde requête n'a PAS traversé : elle a attendu puis renoncé.
        assert etat.get("issue") == "refusee", etat

        liberation.set()
        premier.join(timeout=5)

    # Migration terminée : le chemin est publié, et seulement maintenant.
    assert chemin in app_mod._MIGRES
    assert chemin not in app_mod._MIGRATIONS_EN_COURS


def test_t03_un_echec_de_migration_ne_publie_pas_le_succes(client):
    """Symétrique : une migration qui échoue ne doit pas laisser le dossier
    marqué prêt, ni bloquer indéfiniment les requêtes suivantes."""
    app_mod, _cl = client
    chemin = os.environ["COMPTA_DB"]
    app_mod._MIGRES.clear()
    app_mod._MIGRATIONS_EN_ECHEC.clear()
    app_mod._MIGRATIONS_EN_COURS.clear()

    def migration_cassee(_chemin):
        raise RuntimeError("palier interrompu")

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(app_mod.migrations, "migrer", migration_cassee)
        mp.setattr(app_mod.init_db, "version_base", lambda _c: 0)
        app_mod._migrer_si_besoin()

    assert chemin not in app_mod._MIGRES
    assert chemin not in app_mod._MIGRATIONS_EN_COURS   # pas de blocage
    assert chemin in app_mod._MIGRATIONS_EN_ECHEC


# ═══ T-04 — le nom de sauvegarde est réservé, pas seulement testé ══════

def test_t04_deux_sauvegardes_simultanees_donnent_deux_fichiers(tmp_path):
    """« Vérifier puis agir » : entre `os.path.exists` et la création, le
    second appelant passait. Deux threads obtenaient le MÊME chemin, chacun
    croyant tenir sa copie de sûreté — et la seconde écrasait la première,
    donc l'état que la copie devait permettre de retrouver."""
    db = str(tmp_path / "compta.db")
    init_db.init(db, "blanc", annee_cible=2026).close()

    depart = threading.Barrier(2)
    resultats, erreurs = [], []

    def sauver():
        try:
            depart.wait(timeout=5)
            resultats.append(perennite.sauvegarder(db, motif="concurrent"))
        except Exception as exc:                       # noqa: BLE001
            erreurs.append(repr(exc))

    fils = [threading.Thread(target=sauver) for _ in range(2)]
    for f in fils:
        f.start()
    for f in fils:
        f.join(timeout=10)

    assert not erreurs, erreurs
    assert len(resultats) == 2
    assert len(set(resultats)) == 2, (
        f"deux sauvegardes pour un seul fichier : {resultats}")
    for chemin in resultats:
        assert os.path.exists(chemin)
        # une copie annoncée doit être une base lisible, pas une coquille
        c = sqlite3.connect(chemin)
        try:
            assert c.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        finally:
            c.close()


def test_t04_un_echec_ne_laisse_pas_de_coquille(tmp_path, monkeypatch):
    """Le nom est désormais réservé par un fichier vide avant la copie : si
    la copie échoue, ce fichier ne doit pas rester à figurer dans la liste
    des sauvegardes, où il passerait pour une protection."""
    db = str(tmp_path / "compta.db")
    init_db.init(db, "blanc", annee_cible=2026).close()
    dossier = perennite.dossier_sauvegardes(db)
    os.makedirs(dossier, exist_ok=True)
    avant = set(os.listdir(dossier))

    def connexion_cassee(*_a, **_k):
        raise sqlite3.OperationalError("disque plein")

    monkeypatch.setattr(perennite.sqlite3, "connect", connexion_cassee)
    with pytest.raises(sqlite3.OperationalError):
        perennite.sauvegarder(db, motif="echec")
    apres = set(os.listdir(dossier))
    assert apres == avant, f"coquille laissée : {apres - avant}"


# ═══ T-05 — le registre se modifie d'un seul tenant ════════════════════

def test_t05_deux_renommages_simultanes_sont_tous_deux_conserves(tmp_path):
    """`os.replace` rend la PUBLICATION atomique, pas le cycle
    lecture-modification-écriture qui la précède. Deux renommages lisaient
    la même version du registre, et le second réécrivait par-dessus le
    premier : les deux appels réussissaient, et l'une des modifications
    disparaissait sans un mot — le pire des cas, puisque rien ne permet de
    le remarquer."""
    racine = str(tmp_path)
    dossiers.creer(racine, "Alpha")
    dossiers.creer(racine, "Beta")

    depart = threading.Barrier(2)
    erreurs = []

    def renommer(slug, nom):
        try:
            depart.wait(timeout=5)
            dossiers.renommer(racine, slug, nom)
        except Exception as exc:                       # noqa: BLE001
            erreurs.append(repr(exc))

    fils = [threading.Thread(target=renommer, args=("alpha", "alpha-modifie")),
            threading.Thread(target=renommer, args=("beta", "beta-modifie"))]
    for f in fils:
        f.start()
    for f in fils:
        f.join(timeout=10)

    assert not erreurs, erreurs
    noms = sorted(e["nom"] for e in dossiers._charger(racine))
    assert noms == ["alpha-modifie", "beta-modifie"], (
        f"une modification a été perdue : {noms}")


def test_t05_deux_creations_simultanees_sont_toutes_deux_inscrites(tmp_path):
    """Le même cycle sert à la création : c'est l'inscription au registre
    d'une comptabilité entière qui était exposée."""
    racine = str(tmp_path)
    depart = threading.Barrier(2)
    erreurs = []

    def creer(nom):
        try:
            depart.wait(timeout=5)
            dossiers.creer(racine, nom)
        except Exception as exc:                       # noqa: BLE001
            erreurs.append(repr(exc))

    fils = [threading.Thread(target=creer, args=(n,))
            for n in ("Premier bien", "Second bien")]
    for f in fils:
        f.start()
    for f in fils:
        f.join(timeout=10)

    assert not erreurs, erreurs
    slugs = sorted(e["slug"] for e in dossiers._charger(racine))
    assert slugs == ["premier-bien", "second-bien"], slugs


def test_t05_aucun_temporaire_partage_ne_subsiste(tmp_path):
    """Le nom temporaire `dossiers.json.tmp`, partagé, faisait que deux
    écritures se marchaient dessus dans le fichier même censé rendre
    l'opération sûre."""
    racine = str(tmp_path)
    dossiers.creer(racine, "Unique")
    restes = [f for f in os.listdir(racine) if f.endswith(".tmp")]
    assert not restes, restes
    src = open(conftest.source("dossiers.py"), encoding="utf-8").read()
    assert 'cible + ".tmp"' not in src


# ═══ T-06 — l'environnement livré est celui qui est déclaré ════════════

def test_t06_le_manifeste_runtime_existe_et_borne_les_versions():
    """Les lanceurs écrivaient `pip install flask`, sans version : deux
    utilisateurs d'une même version du logiciel pouvaient exécuter deux
    environnements différents, et une régression rapportée par l'un
    n'était pas reproductible chez l'autre."""
    manifeste = open(os.path.join(HERE, "requirements.txt"),
                     encoding="utf-8").read()
    for paquet in ("flask", "reportlab"):
        assert paquet in manifeste, paquet
    # bornée des deux côtés : un plancher éprouvé, un plafond de majeure
    assert "flask>=" in manifeste and ",<" in manifeste


def test_t06_les_lanceurs_installent_le_manifeste():
    for lanceur, encodage in (("Compta-LMNP-Linux-macOS.sh", "utf-8"),
                              ("Compta-LMNP-Windows.bat", "ascii")):
        src = open(os.path.join(HERE, lanceur), encoding=encodage).read()
        # Le lanceur Unix préfixe par son propre dossier, le .bat s'y place
        # d'abord : on vérifie l'INSTALLATION DU MANIFESTE, pas sa graphie.
        assert "-r " in src and "requirements.txt" in src, lanceur
        # plus aucun nom de paquet installé en clair, sans version
        assert "pip install --quiet flask" not in src, lanceur
        assert "pip install --quiet reportlab" not in src, lanceur


def test_t06_les_versions_eprouvees_sont_coherentes_entre_manifestes():
    """`requirements-dev.txt` épingle ce que la CI éprouve ;
    `requirements.txt` borne ce que l'utilisateur installe. Le plancher du
    second doit être la version épinglée du premier — sinon on éprouve une
    version que personne n'installera."""
    import re
    dev = open(os.path.join(HERE, "requirements-dev.txt"),
               encoding="utf-8").read()
    run = open(os.path.join(HERE, "requirements.txt"), encoding="utf-8").read()
    for paquet in ("flask", "reportlab"):
        epingle = re.search(rf"^{paquet}==([\d.]+)", dev, re.M)
        plancher = re.search(rf"^{paquet}>=([\d.]+)", run, re.M)
        assert epingle and plancher, paquet
        assert epingle.group(1) == plancher.group(1), (
            f"{paquet} : éprouvé en {epingle.group(1)}, "
            f"plancher livré {plancher.group(1)}")


def test_t06_le_paquet_livre_le_manifeste():
    """Un lanceur qui installe `-r requirements.txt` échoue si le fichier
    n'est pas dans le paquet."""
    conftest.exiger_dossier_prive()
    import zipfile
    sys.path.insert(0, HERE)
    import construire_distribution as cd
    ancien = os.getcwd()
    os.chdir(HERE)
    try:
        chemin = cd.construire()
    finally:
        os.chdir(ancien)
    noms = {n.split("compta_lmnp/", 1)[-1]
            for n in zipfile.ZipFile(chemin).namelist()}
    assert "requirements.txt" in noms


# ═══ T-09 — un catalogue chargé une fois par requête ═══════════════════

def test_t09_le_catalogue_nest_lu_quune_fois_par_page(client, monkeypatch):
    """Une page de saisie lisait trois fois `gabarit_personnalise` :
    `_catalogue` appelait `tous` puis `par_groupe`, qui rappelait `tous`, et
    la route rechargeait le tout pour les périodicités."""
    app_mod, cl = client
    lectures = {"n": 0}
    vrai_tous = gabarits.tous

    def compter(conn=None):
        if conn is not None:
            lectures["n"] += 1
        return vrai_tous(conn)

    monkeypatch.setattr(app_mod.gabarits_mod, "tous", compter)
    assert cl.get("/saisie").status_code == 200
    assert lectures["n"] == 1, (
        f"{lectures['n']} lectures du catalogue pour une page")


def test_t09_grouper_est_une_fonction_pure():
    """La lecture et le regroupement sont deux gestes distincts : c'est ce
    qui permet à l'appelant de ne charger qu'une fois."""
    catalogue = gabarits.tous(None)
    groupes = gabarits.grouper(catalogue)
    assert groupes == gabarits.par_groupe(None)
    assert sum(len(v) for _g, v in groupes) == len(catalogue)


def test_t09_larchitecture_ne_cite_plus_de_compteurs_perimes():
    """Le document annonçait 279 tests et des migrations « à venir » alors
    que `migrations.py` existe : un modèle mental périmé coûte au
    mainteneur autant qu'un défaut."""
    src = open(os.path.join(HERE, "ARCHITECTURE.md"), encoding="utf-8").read()
    assert "279 tests" not in src
    assert "1 200 lignes" not in src
