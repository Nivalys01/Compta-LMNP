"""Audit N : uniquement des bases temporaires et des données fictives."""
import contextlib, io, json, sqlite3, sys, tempfile, warnings
from pathlib import Path
from datetime import date
from unittest.mock import patch
ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / 'compta_lmnp_v8.41.0/compta_lmnp'
sys.path[:0] = [str(SRC / 'modules'), str(SRC)]
import init_db, parametres as p, gabarits as g, veille_fiscale as v
import pense_bete as pb, fiscal, operations, liasse, controles, import_bancaire as ib
TMP = tempfile.TemporaryDirectory(prefix='audit-n-')
OUT = {}
def emit(k, value):
    OUT[k] = value
    print(k, json.dumps(value, ensure_ascii=False, default=str))
def new():
    c = init_db.init_blanc(str(Path(TMP.name) / f'{len(list(Path(TMP.name).glob("*.db")))}.db'), 2026)
    c.row_factory = sqlite3.Row
    c.execute("INSERT INTO exploitant VALUES(1,'Exploitant fictif','000000000','Adresse fictive')")
    c.execute("INSERT INTO bien(id,exploitant_id,libelle,prix_total) VALUES(1,1,'Bien fictif',0)")
    p.assurer(c); g.assurer_table(c); v._table_meta(c); c.commit()
    return c
def op(c, t, m, commit=True):
    return operations.saisir(c,type=t,montant=m,date_operation='2026-02-01',commit=commit)
def attempt(fn):
    try: return {'retour': fn()}
    except Exception as e: return {'erreur': type(e).__name__ + ': ' + str(e)}
def rows(c, sql): return [list(r) for r in c.execute(sql)]

c=new();p.definir(c,'seuil_immobilisation',1000,'2026-07-01')
emit('juillet', {y:p.valeur(c,'seuil_immobilisation',y,500) for y in (1999,2025,2026,2029)})
op(c,'petit_equipement',800)
emit('operation_fevrier', {'controle':[a.code for a in controles.c_depense_immobilisable(c,2026)], 'import':ib._seuil_immobilisation(c,2026)})
p.definir(c,'seuil_immobilisation',700,'2025-01-01')
emit('desordre',rows(c,"SELECT valeur,date_debut,date_fin FROM regle_fiscale WHERE cle='seuil_immobilisation' ORDER BY date_debut"))
c.execute("UPDATE regle_fiscale SET date_fin='2026-09-30' WHERE cle='seuil_immobilisation' AND date_debut='2026-07-01'");c.commit()
emit('fin_septembre', {y:p.valeur(c,'seuil_immobilisation',y,-99) for y in (2026,2027)})
c=new();c.execute("DELETE FROM regle_fiscale WHERE cle='seuil_immobilisation'");c.commit()
p.definir(c,'seuil_immobilisation',1000,'2027-01-01')
# Supprimer la version précédente crée un trou annuel explicite.
c.execute("DELETE FROM regle_fiscale WHERE cle='seuil_immobilisation' AND date_debut<'2027-01-01'");c.commit()
emit('trou',p.valeur(c,'seuil_immobilisation',2026,500))
c.execute('DELETE FROM regle_fiscale');c.commit()
buf=io.StringIO()
with warnings.catch_warnings(record=True) as ws, contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
    val=p.valeur(c,'seuil_immobilisation',2026,500)
emit('table_vide',{'valeur':val,'regles_apres':c.execute('SELECT COUNT(*) FROM regle_fiscale').fetchone()[0],'messages':buf.getvalue(),'warnings':len(ws)})
c=new();p.definir(c,'seuil_immobilisation',300,'2026-01-01');op(c,'petit_equipement',400)
old=[a.code for a in controles.c_depense_immobilisable(c,2026)]
c.execute('DELETE FROM regle_fiscale');c.commit()
emit('regles_perdues',{'avant':old,'apres':[a.code for a in controles.c_depense_immobilisable(c,2026)],'valeur_recreee':p.valeur(c,'seuil_immobilisation',2026)})
for val in (-1,0,10000000):
    c=new();p.definir(c,'seuil_immobilisation',val,'2026-01-01');op(c,'petit_equipement',800)
    emit('seuil_'+str(val),{'lu':p.valeur(c,'seuil_immobilisation',2026),'controle':[a.code for a in controles.c_depense_immobilisable(c,2026)]})
c=new();p.definir(c,'duree_report_deficit_lmnp',0,'2026-01-01')
fiscal.traiter_deficit(c,2026,-1200)
emit('duree_zero',{'avant':rows(c,'SELECT annee_origine,solde,annee_expiration FROM deficit_lmnp'),'2027':fiscal.traiter_deficit(c,2027,1200)})
c=new();op(c,'loyer',20000);p.definir(c,'seuil_lmp_recettes',15000,'2026-01-01')
emit('lmp',{'controle':[a.code for a in controles.c_seuil_lmp(c,2026)],'rappel':[r for r in pb.rappels(c,date(2026,9,15)) if 'LMP' in r['titre']]})
c=new();op(c,'loyer',2400);op(c,'fonds_travaux_alur',200);op(c,'petit_equipement',800)
fiscal.cloturer(c,2026,generer_dotation=False);before=liasse.generer(c,2026)
old=[a.code for a in controles.c_depense_immobilisable(c,2026)]
p.definir(c,'seuil_immobilisation',1000,'2026-01-01');p.definir(c,'retraitement_alur_auto',0,'2026-01-01')
after=liasse.generer(c,2026)
emit('clos',{'liasse_identique':before==after,'rf_avant':before['f2033b']['resultat_fiscal_lmnp'],'rf_apres':after['f2033b']['resultat_fiscal_lmnp'],'controle_avant':old,'controle_apres':[a.code for a in controles.c_depense_immobilisable(c,2026)]})
c=new()
emit('veille_absente',v.veille_a_refaire(c,date(2029,9,15)))
for d in ('illisible','2099-01-01','2028-01-01'):
    v.enregistrer_veille(c,d)
    emit('veille_'+d, {'a_refaire':v.veille_a_refaire(c,date(2029,9,15)),'rappels':[r['titre'] for r in pb.rappels(c,date(2029,9,15)) if 'Veille' in r['titre']]})
with patch.object(v,'veille_a_refaire',side_effect=sqlite3.OperationalError('panne fictive')):
    emit('veille_panne',[r['titre'] for r in pb.rappels(c,date(2029,9,15))])
emit('calendrier',pb.actualites())
for name,fn in [('assurer',p.assurer),('valeur',lambda c:p.valeur(c,'seuil_immobilisation',2026)),('historique',p.historique),('assurer_table',g.assurer_table),('_personnalises',g._personnalises),('tous',g.tous),('par_groupe',g.par_groupe),('derniere_veille',v.derniere_veille),('veille_a_refaire',v.veille_a_refaire),('lire_notes',pb.lire_notes),('rappels',lambda c:pb.rappels(c,date(2026,9,15))),('ajouter_personnalise',lambda c:g.ajouter_personnalise(c,cle='fictif',libelle='Fictif',compte_num='606320',nature='charge'))]:
    c=new();op(c,'loyer',800,False);fn(c);active=c.in_transaction;c.rollback()
    emit('transaction_'+name,{'transaction_apres':active,'operations_apres_rollback':c.execute('SELECT COUNT(*) FROM operation').fetchone()[0]})
c=new()
for key,account,nature in [('loyer','606320','charge'),('absent','999999','charge'),('nature','606320','invalide')]:
    emit('refus_'+key,attempt(lambda:g.ajouter_personnalise(c,cle=key,libelle='Fictif',compte_num=account,nature=nature)));c.rollback()
g.ajouter_personnalise(c,cle='inactif',libelle='Fictif',compte_num='606320',nature='charge')
c.execute("UPDATE gabarit_personnalise SET actif=0 WHERE cle='inactif'");c.commit()
emit('collision_inactive',attempt(lambda:g.ajouter_personnalise(c,cle='inactif',libelle='Fictif',compte_num='606320',nature='charge')));c.rollback()
emit('suppression_compte',attempt(lambda:c.execute("DELETE FROM compte WHERE numero='606320'").rowcount));c.rollback()
for account in ('164000','472000'):
    c=new();g.ajouter_personnalise(c,cle='fictif',libelle='Fictif',compte_num=account,nature='charge');op(c,'fictif',800)
    emit('classe_'+account,{'agregats':fiscal.agregats(c,2026),'attente':[a.code for a in controles.c_compte_attente(c,2026)]})
emit('corpus_regles_manquantes',sorted(set(p.LIBELLES)-{x[3] for x in v.CORPUS}))
c=new();p.definir(c,'duree_report_deficit_lmnp',12,'2026-01-01')
fiscal.traiter_deficit(c,2025,-100);fiscal.traiter_deficit(c,2026,-200)
emit('duree_versionnee',rows(c,'SELECT annee_origine,annee_expiration FROM deficit_lmnp'))
c=new();p.definir(c,'seuil_immobilisation',700,'2026-01-01');p.definir(c,'seuil_immobilisation',900,'2026-01-01')
emit('meme_date',{'lu':p.valeur(c,'seuil_immobilisation',2026),'versions':c.execute("SELECT COUNT(*) FROM regle_fiscale WHERE cle='seuil_immobilisation' AND date_debut='2026-01-01'").fetchone()[0]})
c=new();op(c,'loyer',800,False);op(c,'loyer',900,False);c.rollback()
emit('deux_saisies',c.execute('SELECT COUNT(*) FROM operation').fetchone()[0])
c=new()
with patch.object(pb,'date',wraps=date) as clock:
    clock.today.return_value=date(2029,9,15)
    emit('actualites_2029',{'date_simulee':'2029-09-15','echeances':pb.actualites()['echeances']})
emit('prompt_couverture',{'alur':'ALUR' in v.prompt_veille(2029),'prelevements':'prélèvements' in v.prompt_veille(2029),'date_exercice':'2029' in v.prompt_veille(2029)})
c=new();p.definir(c,'seuil_immobilisation',300,'2026-01-01')
normal=ib.categoriser('mobilier fictif',-400,c,2026)
c.set_authorizer(lambda action, table, *rest: sqlite3.SQLITE_DENY if action==sqlite3.SQLITE_READ and table=='regle_fiscale' else sqlite3.SQLITE_OK)
failure=attempt(lambda:p.valeur(c,'seuil_immobilisation',2026))
degraded=ib.categoriser('mobilier fictif',-400,c,2026)
c.set_authorizer(None)
op(c,degraded,400)
emit('import_regle_inaccessible',{'lecture_directe':failure,'normal':normal,'panne':degraded,'resultat_comptable':fiscal.agregats(c,2026)['resultat_comptable'],'controle_apres_retablissement':[a.code for a in controles.c_depense_immobilisable(c,2026)]})
Path(__file__).with_name('sorties.json').write_text(json.dumps(OUT,ensure_ascii=False,indent=2,default=str)+'\n')
