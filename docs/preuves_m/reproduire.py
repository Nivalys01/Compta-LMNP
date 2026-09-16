"""Passe M : uniquement bases blanches temporaires et identités fictives."""
import contextlib, dataclasses, inspect, io, json, os, sqlite3, subprocess, sys, tempfile
from pathlib import Path
from unittest.mock import patch
ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / 'compta_lmnp'
sys.path[:0] = [str(SRC/'modules'), str(SRC)]
import init_db, controles as C, operations as O, fiscal as F, amortissement as A
import gabarits as G, parametres as P, reprise, ecritures as E, audit_cycle as AC
import liasse, liasse_pdf, export_fec, rejeu_fec
ART = Path(__file__).parent
TMP = tempfile.TemporaryDirectory(prefix='audit-m-')
OUT = {}; SEQ = 0; CONNECTIONS = []
def new(y=2026, component=False, dms=None):
    global SEQ
    SEQ += 1
    c = init_db.init_blanc(str(Path(TMP.name)/f'{SEQ}.db'), y)
    c.row_factory=sqlite3.Row
    c.execute("INSERT INTO exploitant VALUES(1,'Exploitant fictif','000000000','Adresse fictive')")
    c.execute("INSERT INTO bien(id,exploitant_id,libelle,prix_total,date_acquisition) VALUES(1,1,'Bien fictif',12000,?)",(dms or f'{y}-01-01',))
    if component:
        c.execute("INSERT INTO composant(bien_id,libelle,valeur_brute,duree_annees,date_mise_service,compte_immo,compte_amort,amortissable) VALUES(1,'Mobilier fictif',12000,10,?,'218400','281840',1)",(dms or f'{y}-01-01',))
    c.commit(); CONNECTIONS.append(c)
    return c
def op(c,t='loyer',m=800,mo=1,y=2026,**kw):
    return O.saisir(c,type=t,montant=m,date_operation=f'{y}-{mo:02d}-05',periode=kw.pop('periode',f'{y}-{mo:02d}'),**kw)
def ent(c,ls,y=2026,j='OD',**kw):
    return E.inserer(c,journal=j,date=kw.pop('date',f'{y}-01-01'),annee=y,piece_ref=kw.pop('piece','FICTIF'),libelle='Écriture fictive',lignes=ls,**kw)
def anos(c,y=2026): return [dataclasses.asdict(a) for a in C.controler(c,y)]
def direct(fn,c,y=2026): return [dataclasses.asdict(a) for a in fn(c,y)]
def previous(c,y=2025):
    c.execute("INSERT INTO exercice(annee,date_debut,date_fin,statut) VALUES(?,?,?,'clos')",(y,f'{y}-01-01',f'{y}-12-31'));c.commit()
def deficit(c,origin=2018,expiry=2028,m=1200):
    c.execute('INSERT INTO deficit_lmnp(annee_origine,montant_initial,solde,annee_expiration) VALUES(?,?,?,?)',(origin,m,m,expiry));c.commit()

# Un témoin indépendant pour chaque fonction, tous passés par controler().
SETUPS = {}
def setup(name):
    def deco(fn): SETUPS[name]=fn;return fn
    return deco
@setup('EQUILIBRE')
def s(c): ent(c,[('628800',100,0),('108000',0,99)],verifier_equilibre=False)
@setup('DATE_HORS_EXERCICE')
def s(c): ent(c,[('628800',10,0),('108000',0,10)],date='2027-01-01',verifier_conformite=False)
@setup('COMPTE_ATTENTE')
def s(c): op(c,'attente_decaissement',0.01)
@setup('MONTANT_INVALIDE')
def s(c): c.execute("INSERT INTO operation(exercice_annee,type,bien_id,date_operation,montant,source) VALUES(2026,'loyer',1,'2026-01-05',0,'import')");c.commit()
@setup('DOUBLON')
def s(c): op(c);op(c)
@setup('REQUALIFIER')
def s(c): op(c,'autres_charges',120)
@setup('IMMOBILISABLE')
def s(c): op(c,'petit_equipement',780)
@setup('LOYER_MANQUANT')
def s(c): op(c)
@setup('SENS')
def s(c): ent(c,[('614100',0,50),('108000',50,0)],j='BQ')
@setup('ANNUEL_MULTIPLE')
def s(c): op(c,'cfe',300);op(c,'cfe',301,mo=2)
@setup('PERIODE_INCOHERENTE')
def s(c): op(c,periode='2025-12')
@setup('INTERETS_MAL_CLASSES')
def s(c): op(c,'frais_bancaires',100,libelle='Intérêts emprunt fictif')
@setup('PLAUSIBILITE_N1')
def s(c):
    previous(c);c.execute("INSERT INTO operation(exercice_annee,type,bien_id,date_operation,montant,source) VALUES(2025,'loyer',1,'2025-01-05',800,'import')");c.commit()
    for mo in (1,2,3): op(c,mo=mo)
@setup('POSTE_HABITUEL_ABSENT')
def s(c):
    for mo in (1,2,3): op(c,mo=mo)
@setup('DEFICIT_MENACE_PAR_39C')
def s(c):
    previous(c);c.execute('INSERT INTO suivi_39c(exercice_annee,stock_cloture) VALUES(2025,1000)');deficit(c);op(c,m=2400)
@setup('RETRAITEMENT_MANUEL_PLAFOND')
def s(c): op(c);F.cloturer(c,2026,autres_retraitements=1000)
@setup('DUREE_ALLONGEE')
def s(c):
    previous(c);c.execute("UPDATE composant SET date_mise_service='2025-01-01'");c.execute("UPDATE exercice SET statut='ouvert' WHERE annee=2025");c.commit()
    ent(c,[('681120',2400,0),('281840',0,2400)],y=2025)
    c.execute("UPDATE exercice SET statut='clos' WHERE annee=2025");c.commit()
@setup('LOYER_ATYPIQUE')
def s(c):
    for mo,m in ((1,800),(2,800),(3,80)):op(c,m=m,mo=mo)
@setup('AN_ABSENTS')
def s(c): previous(c)
@setup('DOTATION_PLAN')
def s(c): ent(c,[('681120',1500,0),('281840',0,1500)])
@setup('AMORT_ANTERIEURS')
def s(c): c.execute("UPDATE composant SET date_mise_service='2025-01-01'");c.commit()
@setup('COMPOSANT_SANS_AMORT')
def s(c): c.execute('UPDATE composant SET compte_amort=NULL');c.commit()
@setup('VENTILATION_INCOMPLETE')
def s(c): c.execute('UPDATE composant SET valeur_brute=6000');c.commit()
@setup('TEOM_ABSENTE')
def s(c): op(c,'taxe_fonciere',900)
@setup('SEUIL_LMP')
def s(c): op(c,m=24000)
@setup('CHARGE_ATTENDUE')
def s(c):
    for mo in range(1,7):op(c,mo=mo)
@setup('ALUR_ABSENT')
def s(c):
    previous(c);c.execute("INSERT INTO operation(exercice_annee,type,bien_id,date_operation,montant,source) VALUES(2025,'fonds_travaux_alur',1,'2025-01-05',100,'import')");c.commit();op(c,'charge_copro',600)
OUT['couverture']={}
for code,fn in SETUPS.items():
    c=new(component=True);fn(c);aa=anos(c)
    found=[a for a in aa if a['code']==code]
    assert found, (code,aa)
    OUT['couverture'][code]=found
assert len(SETUPS)==len(C.CONTROLES)==27
OUT['inventaire']={fn.__name__:inspect.getsourcelines(fn)[1] for fn in C.CONTROLES}
OUT['fonctions_non_enregistrees']=[n for n,v in vars(C).items() if n.startswith('c_') and callable(v) and v not in C.CONTROLES]

# Chaque contrôle sur un exercice vide, après initialisation normale du moteur.
c=new();C.controler(c,2026)
OUT['chaque_controle_vide']={fn.__name__:direct(fn,c) for fn in C.CONTROLES}
# Référence correcte : loyer et capital remboursé ont des effets différents.
c=new();op(c,'loyer',800);op(c,'emprunt_capital_rembourse',800)
OUT['attente_compensee_reference']=F.cloturer(c,2026)
# Extension du catalogue standard : le drapeau est bien pris en compte.
c=new()
with patch.dict(G.GABARITS,{'categorie_fictive':{'compte':'628800','nature':'charge','periodicite':'variable','libelle':'Catégorie fictive','requalifier':True}}):
    op(c,'categorie_fictive',120);OUT['requalifier_drapeau']=direct(C.c_autres_a_requalifier,c)

# Solde d'attente compensé : deux flux non identifiés ne sont pas un apurement.
c=new();op(c,'attente_encaissement',800);op(c,'attente_decaissement',800)
OUT['attente_compensee']={'anomalies':anos(c),'agregats':F.agregats(c,2026),'cloture':F.cloturer(c,2026)}
# Sept chiffres, vrai export/rejeu, sans operation intermédiaire.
c=new();c.execute("INSERT INTO compte VALUES('4720000','Attente fictive','actif',4)");c.commit()
ent(c,[('4720000',800,0),('108000',0,800)])
fec=Path(TMP.name)/'cabinet-fictif.txt';export_fec.exporter(c,2026,str(fec))
c=new();r=rejeu_fec.rejouer(c,str(fec),2026)
OUT['attente_sept_chiffres']={'rejeu':r,'anomalies':anos(c),'solde':liasse._soldes(c,2026).get('4720000'),'cloture':F.cloturer(c,2026)}
# Attente antérieure avec/sans AN.
c=new(2025);op(c,'attente_decaissement',800,y=2025);F.cloturer(c,2025)
reprise.ouvrir_exercice(c,2026,avec_reprise=False)
OUT['attente_anterieure_sans_an']=anos(c)
reprise.construire_an_interne(c,2026);OUT['attente_anterieure_avec_an']=anos(c)
# Seuil LMP : dette et annulation prises pour des recettes.
c=new();op(c,'emprunt_recu',100000)
OUT['seuil_emprunt']={'anomalies':direct(C.c_seuil_lmp,c),'agregats':F.agregats(c,2026)}
c=new();r=op(c,m=24000);O.annuler(c,r['operation_id']);OUT['seuil_annule']={'anomalies':direct(C.c_seuil_lmp,c),'agregats':F.agregats(c,2026)}
# Annulation effective et alertes résiduelles.
c=new();r=op(c,'petit_equipement',780);O.annuler(c,r['operation_id']);r=op(c,'cfe',300);O.annuler(c,r['operation_id']);op(c,'cfe',300)
for mo,m in ((1,800),(2,800),(3,800)):op(c,m=m,mo=mo)
r=op(c,m=80,mo=4);O.annuler(c,r['operation_id']);op(c,m=800,mo=4)
OUT['annulations']={'anomalies':anos(c),'agregats':F.agregats(c,2026)}
# Dossiers légitimes : multi-biens, début novembre, premier exercice, vacance.
c=new();c.execute("INSERT INTO bien(id,exploitant_id,libelle,prix_total,date_acquisition) VALUES(2,1,'Bien fictif B',12000,'2026-01-01')");c.commit()
op(c,tiers='Locataire fictif A');op(c,bien_id=2,tiers='Locataire fictif B')
OUT['deux_locataires']=anos(c)
c=new(dms='2026-11-01');c.execute("UPDATE exercice SET date_debut='2026-11-01'");c.commit();op(c,mo=11);op(c,mo=12)
OUT['acquisition_novembre']=anos(c)
c=new();OUT['vide']=anos(c);OUT['exercice_inexistant']=C.rapport(c,2099)
for mo in (1,2,3):op(c,'assurance',100,mo=mo)
OUT['vacance_maison']=anos(c)
c=new();op(c);OUT['un_loyer_sans_historique']=direct(C.c_loyer_atypique,c)
# Mêmes loyers normaux à deux niveaux de prix.
c=new()
for mo,m in ((1,800),(2,800),(3,800),(4,1600),(5,1600),(6,1600)):op(c,m=m,mo=mo)
OUT['loyers_deux_tarifs']=direct(C.c_loyer_atypique,c)
# API de clôture ne consulte pas les BLOQUANT.
c=new();op(c,'attente_decaissement',800);OUT['api_sans_forcer']={'avant':anos(c),'retour':F.cloturer(c,2026),'statut':c.execute('SELECT statut FROM exercice').fetchone()[0]}
# Bilan perdu sans AN : comparaison de deux cycles.
OUT['an_absents_bilan']={}
for avec in (False,True):
    c=new(2025,component=True);ent(c,[('218400',12000,0),('108000',0,12000)],y=2025);op(c,m=2400,y=2025);F.cloturer(c,2025)
    reprise.ouvrir_exercice(c,2026,avec_reprise=avec);op(c,m=2400)
    aa=anos(c);rr=F.cloturer(c,2026);L=liasse.generer(c,2026)
    OUT['an_absents_bilan'][str(avec)]={'avant':aa,'cloture':rr,'bilan':L['f2033a'],'conforme':L['conforme']}
# PDF réellement rendu : le contrôle existe mais n'est pas dans le document.
c=new();op(c,'attente_decaissement',800);aa=anos(c);L=liasse.generer(c,2026)
p=ART/'attente.pdf';liasse_pdf.generer_pdf(L,str(p));txt=subprocess.check_output(['pdftotext','-layout',str(p),'-'],text=True);(ART/'attente.txt').write_text(txt)
OUT['pdf_attente']={'anomalies':aa,'controles_liasse':L['controles'],'conforme':L['conforme'],'COMPTE_ATTENTE_imprime':'COMPTE_ATTENTE' in txt,'non_solde_imprime':'non soldé' in txt}
# Équilibre par écriture : oppositions, AN, clos et FEC importé.
c=new();ent(c,[('628800',100,0),('108000',0,99)],verifier_equilibre=False);ent(c,[('628800',99,0),('108000',0,100)],verifier_equilibre=False,j='AN')
OUT['equilibre_oppose']={'solde_global':c.execute('SELECT SUM(debit-credit) FROM ligne').fetchone()[0],'anomalies':direct(C.c_equilibre_ecritures,c)}
c.execute("UPDATE exercice SET statut='clos'");c.commit();OUT['equilibre_clos']=direct(C.c_equilibre_ecritures,c)
c=new();rejeu_fec.rejouer(c,str(fec),2026);c.execute("UPDATE ligne SET debit=799 WHERE compte_num='4720000'");c.commit();OUT['equilibre_fec_corrompu']=direct(C.c_equilibre_ecritures,c)
# Tables paresseuses et paramètres absents, trous et valeurs infinies.
c=new();OUT['tables_absentes_avant']=[r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")]
OUT['tables_absentes_controles']=anos(c)
OUT['tables_absentes_apres']=[r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")]
c=new();op(c,'petit_equipement',780);op(c,m=24000);P.assurer(c);c.execute('DELETE FROM regle_fiscale');c.commit();OUT['regles_supprimees']=anos(c)
c.execute("UPDATE regle_fiscale SET date_debut='2027-01-01'");c.commit();OUT['regles_hors_millesime']=anos(c)
P.definir(c,'seuil_immobilisation',float('inf'),'2026-01-01');P.definir(c,'seuil_lmp_recettes',float('inf'),'2026-01-01')
OUT['seuils_infinis']={'immo':direct(C.c_depense_immobilisable,c),'lmp':direct(C.c_seuil_lmp,c)}
# Exception auxiliaire avalée (injection explicite), et vrai composant mal daté.
c=new(component=True,dms='2025-01-01');OUT['amort_avant_panne']=direct(C.c_amortissements_anterieurs,c)
with patch.object(O,'amortissements_anterieurs_manquants',side_effect=sqlite3.OperationalError('lecture fictive indisponible')):
    OUT['amort_panne']=anos(c)
c.execute("UPDATE composant SET date_mise_service='2025-02-30'");c.commit();OUT['date_composant_invalide']=anos(c)
# Déficit menacé : la simulation marche sans cloture_fiscale, mais une panne disparaît.
c=new();SETUPS['DEFICIT_MENACE_PAR_39C'](c);OUT['deficit_avant_panne']=direct(C.c_deficit_menace_par_le_39c,c)
with patch.object(F,'simuler',side_effect=RuntimeError('projection fictive impossible')):OUT['deficit_panne']=direct(C.c_deficit_menace_par_le_39c,c)
# Extension : annuel dynamique oui ; requalification personnalisée sur attente non.
c=new();G.ajouter_personnalise(c,cle='taxe_fictive',libelle='Taxe fictive',compte_num='635130',nature='charge',periodicite='annuel');op(c,'taxe_fictive',100);op(c,'taxe_fictive',101,mo=2)
OUT['annuel_personnalise']=direct(C.c_annuel_multiple,c)
G.ajouter_personnalise(c,cle='inconnu_fictif',libelle='Flux fictif',compte_num='472000',nature='charge');op(c,'inconnu_fictif',800)
OUT['requalifier_personnalise']=direct(C.c_autres_a_requalifier,c)
# SENS reste atteignable ; remboursement natif déclenche aussi.
c=new();op(c,'restitution_charges',100);OUT['sens_restitution']=direct(C.c_sens_comptable,c)
# Exécutions de l'auditeur puis mutations, restaurées à chaque fois.
def run_cycle():
    r=AC.executer();return {'succes':r.succes,'nombre':len(r.checks),'echecs':r.echecs,'checks':r.checks}
OUT['audit_nominal']=run_cycle()
with patch.object(C,'CONTROLES',[f for f in C.CONTROLES if f is not C.c_compte_attente]):OUT['audit_sans_compte_attente']=run_cycle()
orig_gen=A.generer_cloture
with patch.object(A,'generer_cloture',return_value=None):OUT['audit_sans_dotation']=run_cycle()
orig_calc=F.calculer_39c
def bad_plafond(stock,dotation,plafond):return orig_calc(stock,dotation,plafond+1000)
with patch.object(F,'calculer_39c',side_effect=bad_plafond):OUT['audit_plafond_faux']=run_cycle()
orig_def=F.traiter_deficit
hits=[]
def bad_expiry(c,y,resultat_fiscal,commit=True):
    n=c.execute('SELECT COUNT(*) FROM deficit_lmnp WHERE solde>0').fetchone()[0];hits.append(n)
    c.execute('UPDATE deficit_lmnp SET solde=0 WHERE solde>0')
    return orig_def(c,y,resultat_fiscal,commit)
with patch.object(F,'traiter_deficit',side_effect=bad_expiry):OUT['audit_peremption_fausse']=run_cycle()
OUT['audit_peremption_fausse']['stocks_non_vides_rencontres']=sum(hits)
c=new();deficit(c);OUT['temoin_peremption']={'avant':1200,'retour':bad_expiry(c,2026,0),'apres':c.execute('SELECT SUM(solde) FROM deficit_lmnp').fetchone()[0]}
# Mutation contrôle BLOQUANT -> AVERTISSEMENT : audit de cycle voit-il le niveau DATE ?
orig_dates=C.c_dates_hors_exercice
def bad_date_level(c,y):return [C.Anomalie(C.AVERTISSEMENT,a.code,a.message) for a in orig_dates(c,y)]
with patch.object(C,'CONTROLES',[bad_date_level if f is orig_dates else f for f in C.CONTROLES]):OUT['audit_date_degradee']=run_cycle()
# Les seuils acceptent aussi la chaîne web 1e309 : conversion à inf.
OUT['seuil_conversion_1e309'] = str(float('1e309'))
# Le minimum absent est un avertissement malgré un bilan effectivement faux.
c=new(component=True,dms='2025-01-01');ent(c,[('218400',12000,0),('108000',0,12000)]);op(c,m=2400)
OUT['amort_anterieurs_cloture']={'avant':anos(c),'cloture':F.cloturer(c,2026),'bilan':liasse.generer(c,2026)['f2033a']}
# Contrôle incapable de vérifier : vrai message final, pas seulement liste vide.
c=new(component=True,dms='2025-02-30');OUT['rapport_date_composant_invalide']=C.rapport(c,2026)
# Comptage nominal des alertes et statuts, avant clôture du cycle ordinaire.
c=new();c.execute('DELETE FROM bien');c.execute('DELETE FROM exploitant');c.commit()
AC._creer_dossier(c,2026);AC._saisir_annee(c,2026,800,[('charge_copro',600,'03'),('assurance',200,'01'),('cfe',300,'11'),('honoraires',250,'12'),('frais_bancaires',150,'06')])
OUT['dossier_ordinaire']=anos(c)
# Un gabarit de loyer personnalisé disparaît des contrôles nommés en dur.
c=new();G.ajouter_personnalise(c,cle='loyer_fictif',libelle='Loyer fictif personnalisé',compte_num='708810',nature='produit',periodicite='mensuel')
for mo,m in ((1,800),(2,800),(3,80)):op(c,'loyer_fictif',m,mo=mo)
OUT['loyer_personnalise']={'manquants':direct(C.c_completude_loyers,c),'atypique':direct(C.c_loyer_atypique,c),'produits':F.agregats(c,2026)['produits']}
# Détection AMORT_ANTERIEURS avale une panne, DOTATION_PLAN la propage.
c=new(component=True);ent(c,[('681120',1500,0),('281840',0,1500)])
with patch.object(A,'dotations_exercice',side_effect=RuntimeError('plan fictif indisponible')):
    try:C.controler(c,2026);OUT['plan_panne_globale']='silence'
    except RuntimeError as exc:OUT['plan_panne_globale']=str(exc)

# CLI par processus réel, DB explicitement fictive.
OUT['cli']={}
for force in (False,True):
    c=new();op(c,'attente_decaissement',800);db=c.execute('PRAGMA database_list').fetchone()[2];c.close()
    env=dict(os.environ,COMPTA_DB=db)
    r=subprocess.run([sys.executable,str(SRC/'cli.py'),'cloturer','--annee','2026']+(['--forcer'] if force else []),env=env,text=True,capture_output=True)
    cc=sqlite3.connect(db);status=cc.execute('SELECT statut FROM exercice').fetchone()[0];cc.close()
    OUT['cli'][str(force)]={'code_retour':r.returncode,'sortie':r.stdout.replace(TMP.name,'<TEMP>'),'erreur':r.stderr.replace(TMP.name,'<TEMP>'),'statut':status}
# Routes réelles en contextes de requête Flask, seules connexions/résolution isolées.
os.environ['COMPTA_DB']=str(Path(TMP.name)/'web-fictif.db')
import app as web
OUT['web']={}
for force in (False,True):
    c=new();op(c,'attente_decaissement',800);db=c.execute('PRAGMA database_list').fetchone()[2];c.close()
    def connection():
        cc=sqlite3.connect(db);cc.row_factory=sqlite3.Row;return cc
    with patch.object(web,'_conn',side_effect=connection),patch.object(web,'_en_bac_a_sable',return_value=True):
        with web.app.test_request_context('/cloturer',method='POST',data={'annee':'2026','forcer':'1' if force else '0'}):r=web.cloturer()
    cc=sqlite3.connect(db);status=cc.execute('SELECT statut FROM exercice').fetchone()[0];cc.close()
    from urllib.parse import unquote
    OUT['web'][str(force)]={'http':r.status_code,'location':unquote(r.location),'statut':status}
# Chaque BLOQUANT passe par la chaîne web et doit garder l'exercice ouvert.
OUT['web_bloquants']={}
for code in ['EQUILIBRE','DATE_HORS_EXERCICE','COMPTE_ATTENTE','MONTANT_INVALIDE','COMPOSANT_SANS_AMORT']:
    c=new(component=True);SETUPS[code](c);db=c.execute('PRAGMA database_list').fetchone()[2];c.close()
    with patch.object(web,'_conn',side_effect=connection),patch.object(web,'_en_bac_a_sable',return_value=True):
        with web.app.test_request_context('/cloturer',method='POST',data={'annee':'2026'}):r=web.cloturer()
    cc=sqlite3.connect(db);status=cc.execute('SELECT statut FROM exercice').fetchone()[0];cc.close()
    OUT['web_bloquants'][code]={'http':r.status_code,'location':unquote(r.location),'statut':status}
# Même vrai chemin web sans Forcer pour les deux contournements d'attente.
OUT['web_attentes_non_detectees']={}
for kind in ('compensee','sept_chiffres'):
    c=new()
    if kind=='compensee':op(c,'attente_encaissement',800);op(c,'attente_decaissement',800)
    else:rejeu_fec.rejouer(c,str(fec),2026)
    db=c.execute('PRAGMA database_list').fetchone()[2];c.close()
    with patch.object(web,'_conn',side_effect=connection),patch.object(web,'_en_bac_a_sable',return_value=True):
        with web.app.test_request_context('/cloturer',method='POST',data={'annee':'2026'}):r=web.cloturer()
    cc=sqlite3.connect(db);status=cc.execute('SELECT statut FROM exercice').fetchone()[0];cc.close()
    OUT['web_attentes_non_detectees'][kind]={'location':unquote(r.location),'statut':status}

for c in CONNECTIONS:
    try:c.close()
    except sqlite3.Error:pass
TMP.cleanup()
(ART/'resultats.json').write_text(json.dumps(OUT,ensure_ascii=False,indent=2,default=list)+'\n')
print(json.dumps({'couverture':len(OUT['couverture']),'audit_nominal':OUT['audit_nominal']['succes'],'audit_sans_dotation':OUT['audit_sans_dotation']['succes'],'audit_plafond_faux':OUT['audit_plafond_faux']['succes'],'audit_peremption_fausse':OUT['audit_peremption_fausse']['succes'],'audit_date_degradee':OUT['audit_date_degradee']['succes'],'resultats':str(ART/'resultats.json')},ensure_ascii=False,indent=2))
