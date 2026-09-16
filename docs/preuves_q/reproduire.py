"""Audit Q : bases fictives uniquement ; aucun accès à reference/ ni au seed privé."""
import ast
import json
import sqlite3
import sys
import tempfile
import threading
import time
import logging
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlparse, parse_qs

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / 'compta_lmnp'
sys.path[:0] = [str(SRC / 'modules'), str(SRC)]
import init_db, operations, ecritures, fiscal, quittances, cession
import parametres, gabarits, veille_fiscale, reprise, migrations, perennite
import rejeu_fec, export_fec

class Trace(sqlite3.Connection):
    commits = 0
    def commit(self):
        self.commits += 1
        return super().commit()

TMP = tempfile.TemporaryDirectory(prefix='audit-q-')
BASE = Path(TMP.name)
SEQ = 0
RESULTS = {}

def emit(key, value):
    RESULTS[key] = value
    print(key, json.dumps(value, ensure_ascii=False), flush=True)

def new():
    global SEQ
    SEQ += 1
    p = BASE / f'cas-{SEQ}.db'
    c = init_db.init_blanc(str(p), 2026)
    c.execute("INSERT INTO exploitant VALUES (1,'Exploitant Fictif','000000000','Adresse fictive')")
    c.execute("INSERT INTO bien(id,exploitant_id,libelle,prix_total) VALUES (1,1,'Bien fictif',120000)")
    c.commit(); c.close()
    return connect(p), p

def connect(p):
    c = sqlite3.connect(p, factory=Trace)
    c.execute('PRAGMA foreign_keys=ON')
    return c

def count(c, table):
    return c.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]

def rent(c, amount=800, **kw):
    return operations.saisir(c, type='loyer', montant=amount,
                            date_operation='2026-01-10', periode='2026-01', **kw)

def component(c):
    c.execute("INSERT INTO composant(bien_id,libelle,valeur_brute,duree_annees,date_mise_service,compte_immo,compte_amort) VALUES (1,'Mobilier fictif',12000,10,'2026-01-01','218400','281840')")
    c.commit()

def readers():
    candidates = {
        'quittances.assurer_schema': quittances.assurer_schema,
        'quittances.locataires': quittances.locataires,
        'quittances.lister': quittances.lister,
        'quittances.prochain_numero': quittances.prochain_numero,
        'cession.assurer_schema': cession.assurer_schema,
        'fiscal._table_39c_bien': fiscal._table_39c_bien,
        'operations.assurer_colonne_annulee': operations.assurer_colonne_annulee,
        'init_db.creer_index': init_db.creer_index,
        'gabarits.assurer_table': gabarits.assurer_table,
        'parametres.assurer': parametres.assurer,
        'veille_fiscale._table_meta': veille_fiscale._table_meta,
        'veille_fiscale.derniere_veille': veille_fiscale.derniere_veille,
        'veille_fiscale.veille_a_refaire': veille_fiscale.veille_a_refaire,
    }
    rows = []
    for name, fn in candidates.items():
        c,p = new()
        c.execute('CREATE TABLE temoin(valeur INTEGER)')
        c.execute('BEGIN'); c.execute('INSERT INTO temoin VALUES (800)')
        c.commits = 0; trace = []; c.set_trace_callback(trace.append)
        fn(c)
        opened = c.in_transaction
        c.rollback()
        rows.append(dict(fonction=name, transaction_apres=opened, commits=c.commits,
                         commit_sql=trace.count('COMMIT'), temoins=count(c,'temoin')))
        c.close()
    emit('lectures', rows)
    c,p=new();rent(c,commit=False);quittances.lister(c);c.rollback()
    emit('lecture_loyer_durable',dict(operations=count(c,'operation'),montant=c.execute('SELECT SUM(montant) FROM operation').fetchone()[0]));c.close()

def grouped():
    c,p = new()
    gabarits.ajouter_personnalise(c,cle='audit_personnalise',libelle='Fictif',compte_num='614100',nature='charge',retraitement='total')
    outcomes = []
    for kind in gabarits.tous(c):
        c.commits = 0
        for _ in range(2):
            operations.saisir(c,type=kind,montant=800,date_operation='2026-01-10',commit=False)
        active = c.in_transaction
        c.rollback()
        outcomes.append([kind,active,c.commits,count(c,'operation'),count(c,'ecriture')])
    emit('gabarits',outcomes); c.close()
    c,p=new();parametres.definir(c,'retraitement_alur_auto',1,'2026-01-01');c.execute('CREATE TABLE temoin(valeur INTEGER)')
    c.execute('BEGIN');c.execute('INSERT INTO temoin VALUES (800)');c.commits=0
    operations.saisir(c,type='fonds_travaux_alur',montant=100,date_operation='2026-01-10',commit=False)
    fiscal.retraitement_automatique(c,2026);c.rollback()
    emit('parametre_versionne',dict(commits=c.commits,temoins=count(c,'temoin'),operations=count(c,'operation')));c.close()
    c,p = new()
    try:
        operations.saisir_appel_charges(c,date_operation='2026-01-10',charges_courantes=600,fonds_alur=100,travaux=float('inf'))
    except Exception as e:
        c.rollback()
        emit('appel_interrompu',dict(erreur=str(e),operations=count(c,'operation'),ecritures=count(c,'ecriture'),montant=c.execute('SELECT SUM(montant) FROM operation').fetchone()[0]))
    c.close()

def closures():
    c,p = new(); rent(c); component(c); c.commits=0
    fiscal.cloturer(c,2026)
    emit('cloture_commits',dict(commits=c.commits,statut=c.execute('SELECT statut FROM exercice').fetchone()[0])); c.close()
    c,p = new(); rent(c); component(c); before=count(c,'ecriture'); c.commits=0
    with patch.object(fiscal,'traiter_deficit',side_effect=RuntimeError('coupure fictive')):
        try: fiscal.cloturer(c,2026)
        except RuntimeError: pass
    c.close(); c=connect(p)
    emit('cloture_interrompue',dict(ecritures_avant=before,ecritures_apres=count(c,'ecriture'),statut=c.execute('SELECT statut FROM exercice').fetchone()[0],suivi=count(c,'suivi_39c'))); c.close()
    c,p = new(); rent(c); component(c); c.close()
    gate=threading.Barrier(2)
    def run(_):
        c=connect(p); gate.wait()
        try: fiscal.cloturer(c,2026); return 'succès'
        except Exception as e: return str(e)
        finally: c.close()
    with ThreadPoolExecutor(2) as pool: out=list(pool.map(run,range(2)))
    c=connect(p); emit('clotures_paralleles',dict(retours=out,dotations=c.execute("SELECT COUNT(*) FROM ecriture WHERE piece_ref='DAA'").fetchone()[0],statut=c.execute('SELECT statut FROM exercice').fetchone()[0]));c.close()

def an_and_cession():
    for name in ('an','cession'):
        c,p=new(); original=ecritures.inserer; calls=0
        if name=='cession': component(c)
        def fail(*a,**kw):
            nonlocal calls
            calls+=1
            if calls==2: raise RuntimeError('coupure fictive deuxième écriture')
            return original(*a,**kw)
        with patch.object(ecritures,'inserer',fail):
            try:
                if name=='an': reprise._construire_an_depuis_balance(c,{'108000':800,'708810':-800},2026)
                else: cession.ceder_bien(c,1,date_cession='2026-06-30',prix_cession=15000)
            except RuntimeError: pass
        pending=count(c,'ecriture'); c.close(); c=connect(p)
        emit(name+'_interruption',dict(avant_fermeture=pending,durable=count(c,'ecriture')));c.close()

def migrations_failure():
    c,p=new()
    c.execute("UPDATE meta SET valeur='2' WHERE cle='version_schema'")
    c.execute("DELETE FROM compte WHERE numero IN ('675000','775000')");c.commit();c.close()
    with patch.dict(migrations.PALIERS,{5:lambda c: (_ for _ in ()).throw(RuntimeError('coupure fictive palier 5'))}):
        try: migrations.migrer(str(p))
        except RuntimeError: pass
    c=connect(p)
    emit('migration_interrompue',dict(version=init_db.version_base(c),comptes_cession=c.execute("SELECT COUNT(*) FROM compte WHERE numero IN ('675000','775000')").fetchone()[0],sauvegardes=len(perennite.lister_sauvegardes(str(p)))));c.close()

def concurrent_cancel():
    c,p=new(); op=rent(c); operations.assurer_colonne_annulee(c); c.commit();c.close()
    gate=threading.Barrier(2); orig=ecritures.inserer
    def meet(*a,**kw): gate.wait(timeout=10); return orig(*a,**kw)
    def run(_):
        c=connect(p)
        try: return operations.annuler(c,op['operation_id'])
        except Exception as e: return str(e)
        finally: c.close()
    with patch.object(ecritures,'inserer',meet),ThreadPoolExecutor(2) as pool:
        out=list(pool.map(run,range(2)))
    c=connect(p)
    emit('annulations_paralleles',dict(retours=out,ecritures=count(c,'ecriture'),loyers=c.execute("SELECT SUM(credit-debit) FROM ligne WHERE compte_num='708810'").fetchone()[0]));c.close()

def receipt_races():
    for same_number in (True,False):
        c,p=new();rent(c)
        for n in ('Locataire fictif A','Locataire fictif B'):
            quittances.ajouter_locataire(c,bien_id=1,nom=n,date_entree='2026-01-01')
        c.close(); gate=threading.Barrier(2); done=threading.Event(); orig=quittances.prochain_numero
        def number(c):
            if same_number:
                n=orig(c);gate.wait(timeout=10);return n
            gate.wait(timeout=10)
            if threading.current_thread().name.endswith('_1'): done.wait(10)
            return orig(c)
        def run(i):
            c=connect(p)
            try: return quittances.emettre(c,locataire_id=i,periode='2026-01')
            except Exception as e: return str(e)
            finally: c.close();done.set()
        with patch.object(quittances,'prochain_numero',number),ThreadPoolExecutor(2) as pool:
            out=list(pool.map(run,(1,2)))
        c=connect(p)
        emit('quittances_collision' if same_number else 'quittances_double',dict(retours=out,nombre=count(c,'quittance'),total=c.execute('SELECT SUM(loyer+charges) FROM quittance').fetchone()[0]));c.close()

def fec_file(year, name):
    c,p=new()
    if year!=2026:
        reprise.ouvrir_exercice(c,year,avec_reprise=False)
    for day in (10,20):
        operations.saisir(c,type='loyer',montant=800,date_operation=f'{year}-01-{day}')
    f=BASE/name;export_fec.exporter(c,year,str(f));c.close();return f

def replay_failure():
    f=fec_file(2026,'rejeu.txt'); c,p=new(); orig=ecritures.inserer; calls=0
    def fail(*a,**kw):
        nonlocal calls
        calls+=1
        if calls==2: raise RuntimeError('coupure fictive deuxième écriture')
        return orig(*a,**kw)
    with patch.object(ecritures,'inserer',fail):
        try: rejeu_fec.rejouer(c,str(f),2026)
        except RuntimeError: pass
    emit('rejeu_interrompu',dict(ecritures=count(c,'ecriture'),transaction=c.in_transaction));c.close()

def retries_and_locks():
    c,p=new();rent(c); calls=0
    def collision(*args):
        nonlocal calls
        calls+=1;return 1
    with patch.object(ecritures,'prochain_num',collision):
        try: rent(c)
        except Exception as e:
            emit('cinquieme_collision',dict(erreur=str(e),tentatives=calls,transaction=c.in_transaction,ecritures=count(c,'ecriture')))
    c.close();c=connect(p);timeout=c.execute('PRAGMA busy_timeout').fetchone()[0];c.execute('BEGIN IMMEDIATE')
    def other():
        d=connect(p);start=time.monotonic()
        try: rent(d);return 'succès'
        except Exception as e: return dict(erreur=str(e),secondes=round(time.monotonic()-start,1))
        finally:d.close()
    with ThreadPoolExecutor(1) as pool: out=pool.submit(other).result(timeout=10)
    emit('verrou',dict(busy_timeout_ms=timeout,resultat=out));c.close()

def web_cases():
    import app as web
    def call(p,fn,data):
        with patch.object(web,'_db_path',return_value=str(p)),web.app.test_request_context('/',method='POST',data=data):
            response=fn()
            return parse_qs(urlparse(response.location).query)
    c,p=new();c.close()
    result=call(p,web.creer_composant,dict(annee='2026',bien_id='1',libelle='Mobilier fictif',compte_immo='218400',valeur_brute='12000',duree_annees='10',date_mise_service='2026-02-30'))
    c=connect(p);emit('composant_web',dict(reponse=result,composants=count(c,'composant'),ecritures=count(c,'ecriture'),valeur=c.execute('SELECT SUM(valeur_brute) FROM composant').fetchone()[0]));c.close()
    c,p=new();c.close()
    result=call(p,web.exercice_ouvrir,dict(annee='2027',date_debut='2027-01-01',date_fin='2027-12-31',reprise='1'))
    c=connect(p);emit('ouverture_web',dict(reponse=result,exercices=count(c,'exercice'),ecritures=count(c,'ecriture')));c.close()
    # Le parseur est remplacé par dix propositions fictives, la boucle web et la base restent réelles.
    props=[dict(type='loyer',montant=800,date_operation='2026-01-10',periode='2026-01',libelle='Loyer fictif') for _ in range(10)]
    for cleanup_error in (False,True):
        c,p=new();c.close();d=BASE/f'imports-{p.stem}';d.mkdir();token='a'*32;f=d/(token+'.csv');f.write_text('fictif')
        current=[dict(x) for x in props]
        if not cleanup_error: current[6]['montant']=float('inf')
        with patch.object(web,'_dossier_imports',return_value=str(d)),patch.object(web.import_bancaire,'proposer',return_value=current):
            if cleanup_error:
                with patch.object(web.os,'remove',side_effect=PermissionError('suppression fictive refusée')):
                    result=call(p,web.import_valider,dict(jeton=token,ligne=[str(i) for i in range(10)]))
            else:
                result=call(p,web.import_valider,dict(jeton=token,ligne=[str(i) for i in range(10)]))
            c=connect(p);n=count(c,'operation');c.close()
            if cleanup_error:
                second=call(p,web.import_valider,dict(jeton=token,ligne=[str(i) for i in range(10)]))
                c=connect(p);emit('import_nettoyage',dict(reponse=result,operations_apres_erreur=n,reponse_relance=second,operations_apres_relance=count(c,'operation'),montant=c.execute('SELECT SUM(montant) FROM operation').fetchone()[0]));c.close()
            else:
                emit('import_interrompu',dict(reponse=result,operations=n,journal_persistant=(p.parent/'logs/erreurs.log').exists()))
    # Reprise multi-exercices réelle : premier FEC correct, deuxième écriture du second déséquilibrée.
    f1=fec_file(2024,'multi2024.txt');f2=fec_file(2025,'multi2025.txt')
    text=f2.read_text(); lines=text.splitlines(); cols=lines[0].split('\t'); vals=lines[-1].split('\t'); vals[cols.index('Credit')]='801,00';lines[-1]='\t'.join(vals);f2.write_text('\n'.join(lines)+'\n')
    c,p=new();c.close();d=BASE/'multi';d.mkdir();token='b'*32;stage=d/token;stage.mkdir()
    (stage/f1.name).write_bytes(f1.read_bytes());(stage/f2.name).write_bytes(f2.read_bytes())
    with patch.object(web,'_dossier_imports',return_value=str(d)):
        result=call(p,web.exercice_reprendre_fec_multi,dict(jeton=token))
    c=connect(p);emit('multi_fec',dict(reponse=result,exercices=[r[0] for r in c.execute('SELECT annee FROM exercice ORDER BY annee')],ecritures=count(c,'ecriture'),source_temporaire=stage.exists()));c.close()
    # Journal : démarrage paresseux, puis exception contenant uniquement une identité fictive.
    c,p=new();c.close()
    with patch.object(web,'_db_path',return_value=str(p)),web.app.test_request_context('/'):
        web._journal_erreurs()
        try: raise ValueError('Locataire Fictif Test : paiement fictif de 800 EUR')
        except ValueError: web.app.logger.exception('Incident fictif')
    log=(p.parent/'logs/erreurs.log').read_text()
    emit('journal_contenu',dict(identite_fictive_presente='Locataire Fictif Test' in log,montant_present='800 EUR' in log))
    for h in list(web.app.logger.handlers):
        if getattr(h,'_journal_compta',False):web.app.logger.removeHandler(h);h.close()

def restoration_race():
    from datetime import datetime
    c,p=new();rent(c);c.close();sv=perennite.sauvegarder(str(p),'manuel')
    c=connect(p);rent(c);c.close()
    gate=threading.Barrier(2);first_done=threading.Event();orig=perennite.sauvegarder
    class Fixed:
        @classmethod
        def now(cls):return datetime(2026,9,15,12,0,0)
    def save(*a,**kw):
        gate.wait(timeout=10)
        if threading.current_thread().name.endswith('_1'):first_done.wait(10)
        return orig(*a,**kw)
    def run(_):
        try:return perennite.restaurer(str(p),sv)
        finally:first_done.set()
    with patch.object(perennite,'datetime',Fixed),patch.object(perennite,'sauvegarder',save),ThreadPoolExecutor(2) as pool:
        out=list(pool.map(run,range(2)))
    c=connect(p);s=connect(out[0])
    emit('restaurations_paralleles',dict(meme_copie_surete=out[0]==out[1],avant=2,apres=count(c,'operation'),copie_surete=count(s,'operation')));c.close();s.close()

def closed_write_race():
    c,p=new();rent(c);c.close();read=threading.Event();closed=threading.Event()
    class Cursor:
        def __init__(self,cur):self.cur=cur
        def fetchone(self):
            row=self.cur.fetchone();read.set()
            if not closed.wait(10):raise RuntimeError('synchronisation expirée')
            return row
    class Pause(sqlite3.Connection):
        def execute(self,sql,*args):
            cur=super().execute(sql,*args)
            return Cursor(cur) if sql=='SELECT statut FROM exercice WHERE annee=?' else cur
    def write():
        c=sqlite3.connect(p,factory=Pause);c.execute('PRAGMA foreign_keys=ON')
        try:return ecritures.inserer(c,journal='BQ',date='2026-01-20',annee=2026,libelle='Loyer fictif tardif',lignes=[('108000',800,0),('708810',0,800)])
        finally:c.close()
    with ThreadPoolExecutor(1) as pool:
        pending=pool.submit(write)
        if not read.wait(10):raise RuntimeError('lecture non atteinte')
        c=connect(p);fiscal.cloturer(c,2026,generer_dotation=False);c.close();closed.set();out=pending.result(timeout=10)
    c=connect(p);emit('ecriture_apres_cloture',dict(retour=out,exercice=list(c.execute('SELECT statut,resultat_comptable FROM exercice').fetchone()),produits=c.execute("SELECT SUM(credit-debit) FROM ligne WHERE compte_num='708810'").fetchone()[0]));c.close()

def migration_guard():
    import app as web
    c,p=new();c.execute("UPDATE meta SET valeur='2' WHERE cle='version_schema'");c.commit();c.close()
    web._MIGRES.discard(str(p))
    with patch.object(web,'_db_path',return_value=str(p)),patch.object(web.migrations,'migrer',side_effect=RuntimeError('migration fictive impossible')),web.app.test_request_context('/'):
        result=web._garde_version_schema()
    c=connect(p);emit('garde_migration_echec',dict(retour=result,version=init_db.version_base(c),memorise=str(p) in web._MIGRES));c.close()

def abrupt_exit():
    c,p=new();rent(c);component(c);c.close()
    code="""import sys,sqlite3,os
sys.path.insert(0,sys.argv[1])
import fiscal
c=sqlite3.connect(sys.argv[2]);c.execute('PRAGMA foreign_keys=ON')
fiscal.traiter_deficit=lambda *a,**k:os._exit(77)
fiscal.cloturer(c,2026)
"""
    child=subprocess.run([sys.executable,'-c',code,str(SRC/'modules'),str(p)],capture_output=True,timeout=15)
    c=connect(p);emit('arret_processus_cloture',dict(code=child.returncode,ecritures=count(c,'ecriture'),suivi=count(c,'suivi_39c'),statut=c.execute('SELECT statut FROM exercice').fetchone()[0],integrite=c.execute('PRAGMA integrity_check').fetchone()[0]));c.close()

def parallel_writes():
    c,p=new();c.close();gate=threading.Barrier(4)
    def write(_):
        c=connect(p);gate.wait(timeout=10)
        try:
            return [rent(c)['ecriture_num'] for _ in range(5)]
        finally:c.close()
    with ThreadPoolExecutor(4) as pool:out=list(pool.map(write,range(4)))
    c=connect(p);emit('saisies_paralleles',dict(numeros=sorted(n for group in out for n in group),ecritures=count(c,'ecriture'),operations=count(c,'operation')));c.close()

def failed_line_savepoint():
    c,p=new();c.execute('CREATE TABLE temoin(valeur INTEGER)');c.execute('BEGIN');c.execute('INSERT INTO temoin VALUES (800)')
    try:
        ecritures.inserer(c,journal='BQ',date='2026-01-10',annee=2026,libelle='Fictif',lignes=[('108000',800,0),('799999',0,800)],commit=False)
    except sqlite3.IntegrityError as e:
        error=str(e)
    c.commit();c.close();c=connect(p)
    emit('savepoint_ligne_invalide',dict(erreur=error,ecritures=count(c,'ecriture'),lignes=count(c,'ligne'),temoins=count(c,'temoin')));c.close()

def inventory():
    rows=[]
    for p in sorted(SRC.rglob('*.py')):
        if 'tests' in p.parts or '.venv' in p.parts: continue
        tree=ast.parse(p.read_text())
        def walk(node,fun='<module>'):
            if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)): fun=node.name
            if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute) and node.func.attr in ('commit','executescript'):
                rows.append(dict(fichier=str(p.relative_to(SRC)),fonction=fun,ligne=node.lineno,appel=ast.unparse(node.func)))
            for child in ast.iter_child_nodes(node): walk(child,fun)
        walk(tree)
    (ROOT/'docs/preuves_q/inventaire.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n')

if __name__=='__main__':
    inventory()
    emit('environnement',dict(python=sys.version.split()[0],sqlite=sqlite3.sqlite_version))
    for fn in (readers,grouped,closures,an_and_cession,migrations_failure,concurrent_cancel,receipt_races,replay_failure,retries_and_locks,web_cases,restoration_race,closed_write_race,migration_guard,abrupt_exit,parallel_writes,failed_line_savepoint):
        try: fn()
        except Exception as e: emit('HARNESS_ERROR_'+fn.__name__,repr(e))
    (ROOT/'docs/preuves_q/resultats.json').write_text(json.dumps(RESULTS,ensure_ascii=False,indent=2)+'\n')
    if any(k.startswith('HARNESS_ERROR_') for k in RESULTS):
        sys.exit(1)
