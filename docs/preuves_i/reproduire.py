"""Passe I : 39 C, fixtures intégralement fictives, aucune donnée privée."""
import hashlib,json,sqlite3,sys,tempfile,subprocess,io
from pathlib import Path
from decimal import Decimal
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[2];SRC=ROOT/'compta_lmnp'
sys.path[:0]=[str(SRC/'modules'),str(SRC)]
import export_fec,init_db,fiscal,amortissement as am,liasse,liasse_pdf,operations,ecritures,reprise,rejeu_fec,cession,migrations,parametres,controles,perennite
TMP=tempfile.TemporaryDirectory(prefix='audit-i-');WORK=Path(TMP.name);SEQ=0;OUT={}
ART=Path(__file__).parent

def emit(k,v):OUT[k]=v;print(k,json.dumps(v,ensure_ascii=False,default=str),flush=True)
def attempt(fn):
    try:return {'retour':fn()}
    except Exception as e:return {'erreur':type(e).__name__+': '+str(e)}
def new(y=2026,n=1):
    global SEQ
    SEQ+=1;p=WORK/f'base-{SEQ}.db';c=init_db.init_blanc(str(p),y);c.row_factory=sqlite3.Row
    c.execute("INSERT INTO exploitant VALUES(1,'Exploitant fictif','000000000','Adresse fictive')")
    for b in range(1,n+1):c.execute('INSERT INTO bien(id,exploitant_id,libelle,prix_total) VALUES(?,1,?,?)',(b,f'Bien fictif {b}',12000))
    c.commit();return c,p

def addcomp(c,b=1,v=12000,d=10,date='2026-01-01',lib=None):
    c.execute("INSERT INTO composant(bien_id,libelle,valeur_brute,duree_annees,date_mise_service,compte_immo,compte_amort,amortissable) VALUES(?,?,?,?,?,'218400','281840',1)",(b,lib or f'Composant fictif {b}',v,d,date));c.commit()
    return ecritures.inserer(c,journal='OD',date=date,annee=int(date[:4]),piece_ref='ACQUIS',libelle='Acquisition fictive',lignes=[('218400',v,0),('108000',0,v)])
def entry(c,y,lines,piece='FICTIF'):
    return ecritures.inserer(c,journal='OD',date=f'{y}-12-31',annee=y,piece_ref=piece,libelle='Écriture fictive',lignes=lines)
def charge(c,amount,y=2026,account='614100'):
    return entry(c,y,[(account,amount,0),('108000',0,amount)])
def income(c,amount,y=2026,account='708810'):
    return entry(c,y,[('108000',amount,0),(account,0,amount)])
def daa(c,amount,y=2026,account='681120'):
    return entry(c,y,[(account,amount,0),('281840',0,amount)],'DAA')
def account(c,num,typ='charge'):
    c.execute('INSERT OR IGNORE INTO compte(numero,libelle,type,classe) VALUES(?,?,?,?)',(num,'Compte fictif',typ,int(num[0])));c.commit()
def open_(c,y):return reprise.ouvrir_exercice(c,y)
def seedstock(c,y,total,parts=None,status='clos'):
    c.execute('INSERT OR IGNORE INTO exercice(annee,date_debut,date_fin,statut) VALUES(?,?,?,?)',(y,f'{y}-01-01',f'{y}-12-31',status))
    c.execute('INSERT INTO suivi_39c(exercice_annee,stock_cloture) VALUES(?,?)',(y,total));fiscal._table_39c_bien(c)
    if parts:
        for b,x in parts.items():c.execute('INSERT INTO suivi_39c_bien(exercice_annee,bien_id,stock_cloture) VALUES(?,?,?)',(y,b,x))
    c.commit()
def snapshot(c,y):
    glob=[dict(x) for x in c.execute('SELECT * FROM suivi_39c WHERE exercice_annee=?',(y,))]
    local=fiscal.suivi_39c_par_bien(c,y)
    fields=['stock_ouverture','dotation_bien','report_bien','utilisation_bien','sortie_bien','stock_cloture']
    return dict(global_=glob,biens=local,sommes={k:round(sum(x[k] for x in local),2) for k in fields},controles=[dict(code=x.code,niveau=x.niveau,message=x.message) for x in controles.controler(c,y)],liasse=liasse.generer(c,y)['controles'])
def pdf(c,y,name):
    path=ART/(name+'.pdf');liasse_pdf.generer_pdf(liasse.generer(c,y),str(path))
    text=subprocess.check_output(['pdftotext','-layout',str(path),'-'],text=True)
    (ART/(name+'.txt')).write_text(text)
    return dict(fichier=path.name,pages=text.count('\f'),texte=text)

def pure():
    data={}
    for stock,dot,plaf in [(0,1200,0),(5000,1200,-300),(5000,0,0),(5000,0,1500),(5000,1200,1500),(5000,1200,1200),(5000,1200,9000),(0,0,-1),(0,-100,0),(0,1200,float('nan'))]:
        data[f'{stock}/{dot}/{plaf}']=attempt(lambda:fiscal.calculer_39c(stock,dot,plaf))
    emit('moteur_limites',data)
    invalid=[];count=0
    for st in (0,.01,.02,1,1234.56,5000):
        for dot in (0,.01,.02,1,1200.01,10000):
            for p in (-1000,0,.01,1,1500.99,20000):
                s=fiscal.calculer_39c(st,dot,p);count+=1
                if abs(s['stock_cloture']-round(st+s['report_annee']-s['utilisation_annee'],2))>.001 or s['stock_cloture']<0 or not(0<=s['report_annee']<=dot):invalid.append([st,dot,p,s])
    emit('moteur_matrice',dict(cas=count,erreurs=invalid))
    emit('repartition_limites',{str((t,w)):fiscal._repartir(t,w) for t,w in [(100,{1:1,2:2,3:3}),(.02,{1:1,2:1,3:1,4:1}),(100,{1:0,2:0}),(100,{})]})

def accounts_cases():
    for variant in ('normal','charges7','dotation7','cession6','cession7','produit_financier'):
        c,p=new();addcomp(c,v=20000,d=10)
        rent=1000;income(c,rent)
        if variant in ('normal','charges7'):
            n='622610' if variant=='normal' else '6226100';account(c,n);charge(c,500,account=n)
        if variant=='dotation7':account(c,'6811200');daa(c,2000,account='6811200')
        else:daa(c,2000)
        if variant.startswith('cession'):
            suf='0' if variant=='cession7' else '';account(c,'675000'+suf);account(c,'775000'+suf,'produit')
            charge(c,10000,account='675000'+suf);income(c,15000,account='775000'+suf)
        if variant=='produit_financier':account(c,'768000','produit');income(c,1000,account='768000')
        f=WORK/(variant+'.txt');export_fec.exporter(c,2026,str(f))
        composants=[tuple(x) for x in c.execute('SELECT bien_id,libelle,valeur_brute,duree_annees,date_mise_service,compte_immo,compte_amort,amortissable FROM composant')]
        c.close();c,p=new();c.executemany('INSERT INTO composant(bien_id,libelle,valeur_brute,duree_annees,date_mise_service,compte_immo,compte_amort,amortissable) VALUES(?,?,?,?,?,?,?,?)',composants);c.commit()
        replay=rejeu_fec.rejouer(c,str(f),2026)
        ag=fiscal.agregats(c,2026);r=fiscal.cloturer(c,2026,generer_dotation=False)
        emit('comptes_'+variant,dict(rejeu=replay,agregats=ag,cloture=r,tableau=liasse.resultat_2033b(c,2026),etat=snapshot(c,2026)));c.close()
    c,p=new();addcomp(c);income(c,1000);charge(c,500,account='622610')
    initial=fiscal.comptes_hors_plafond_39c(c);c.execute('DELETE FROM compte_hors_plafond_39c');c.commit();after=fiscal.comptes_hors_plafond_39c(c)
    account(c,'6226100');charge(c,200,account='6226100');before=fiscal.agregats(c,2026)
    c.execute("INSERT INTO compte_hors_plafond_39c VALUES('6226100')");c.commit();after_add=fiscal.agregats(c,2026)
    emit('liste_exclusions',dict(initiale=initial,apres_vidage=after,avant_ajout=before,apres_ajout=after_add));c.close()
    # Branche réellement vide : ne pas laisser les comptes de défaut dans ce référentiel minimal.
    c,p=new();c.execute("DELETE FROM compte WHERE numero IN ('622610','635110','675000')");c.commit();income(c,1000);charge(c,200)
    emit('liste_reellement_vide',dict(liste=fiscal.comptes_hors_plafond_39c(c),agregats=fiscal.agregats(c,2026)));c.close()

def legal_distribution():
    for sold in (False,True):
        c,p=new(n=2);addcomp(c,1,10000);addcomp(c,2,30000)
        for b,amt in ((1,2000),(2,1000)):operations.saisir(c,type='loyer',montant=amt,date_operation='2026-01-10',bien_id=b)
        if sold:cession.ceder_bien(c,1,'2026-12-31',10000)
        r=fiscal.cloturer(c,2026);emit('ventilation_bien_couvert_'+str(sold),dict(cloture=r,etat=snapshot(c,2026)))
        if sold:emit('pdf_deux_biens',pdf(c,2026,'suivi_deux_biens'));open_(c,2027);fiscal.cloturer(c,2027);emit('annee_apres_cession',snapshot(c,2027))
        c.close()
    # Un bien acquis en cours d'année, sans loyer ; un autre au plafond négatif.
    c,p=new(n=2);addcomp(c,1,12000,date='2026-07-01');addcomp(c,2,12000)
    operations.saisir(c,type='loyer',montant=500,date_operation='2026-01-10',bien_id=2)
    operations.saisir(c,type='maintenance',montant=800,date_operation='2026-01-10',bien_id=2)
    r=fiscal.cloturer(c,2026);emit('acquisition_sans_loyer_plafond_negatif',dict(cloture=r,etat=snapshot(c,2026)));c.close()

def repeated_labels():
    for same in (False,True):
        c,p=new(n=3)
        for b,v in ((1,10000),(2,20000),(3,30000)):addcomp(c,b,v,lib='Mobilier fictif' if same else None)
        a=cession.ceder_bien(c,1,'2026-12-31',10000);b=cession.ceder_bien(c,2,'2026-12-31',20000)
        r=fiscal.cloturer(c,2026)
        emit('cessions_libelles_identiques_'+str(same),dict(dotations_cession=[a['dotation_complementaire'],b['dotation_complementaire']],cloture=r,etat=snapshot(c,2026)));c.close()

def histories():
    for status in ('clos','ouvert'):
        c,p=new();seedstock(c,2024,5000,{1:5000},status)
        before=fiscal._stock_39c_ouverture(c,2026);income(c,1500);r=attempt(lambda:fiscal.cloturer(c,2026,generer_dotation=False))
        emit('historique_'+status,dict(stock_lu=before,cloture=r,etat=snapshot(c,2026)));c.close()
    c,p=new(2040);seedstock(c,2020,5000,{1:5000});c.execute('INSERT INTO deficit_lmnp(annee_origine,montant_initial,solde,annee_expiration) VALUES(2020,5000,5000,2030)');c.commit();income(c,1500,y=2040)
    r=fiscal.cloturer(c,2040,generer_dotation=False);emit('absence_peremption_39c',dict(cloture=r,etat=snapshot(c,2040),deficits=[dict(x) for x in c.execute('SELECT * FROM deficit_lmnp')]));c.close()
    c,p=new();seedstock(c,2025,5000,{1:5000});entry(c,2026,[('218400',10000,0),('108000',0,10000)]);c.commit();bak=perennite.sauvegarder(str(p),'audit-avant');income(c,1500);fiscal.cloturer(c,2026,generer_dotation=False);old=snapshot(c,2026);c.close()
    safety=perennite.restaurer(str(p),bak);c=sqlite3.connect(p);c.row_factory=sqlite3.Row
    emit('restauration_memoire',dict(avant=old,apres_stock_ouverture=fiscal._stock_39c_ouverture(c,2026),stock_lu_2027_apres_restauration=fiscal._stock_39c_ouverture(c,2027),suivi_2026=c.execute('SELECT COUNT(*) FROM suivi_39c WHERE exercice_annee=2026').fetchone()[0],statut=c.execute('SELECT statut FROM exercice WHERE annee=2026').fetchone()[0],sauvegarde_securite=Path(safety).is_file()));c.close()

def legacy():
    c,p=new(n=2);seedstock(c,2025,5000);c.execute('DROP TABLE suivi_39c_bien');c.execute("UPDATE meta SET valeur='1' WHERE cle='version_schema'");c.commit();c.close()
    r=migrations.migrer(str(p));c=sqlite3.connect(p);c.row_factory=sqlite3.Row
    migrated=snapshot(c,2025);amort_before=fiscal._stock_39c_ouverture(c,2026)
    # Cession fictive antérieure signalée dans le référentiel : le bien 2 continue seul.
    c.execute("UPDATE bien SET date_cession='2025-12-31' WHERE id=1");c.commit();addcomp(c,2,10000);daa(c,1000)
    r2=fiscal.cloturer(c,2026,generer_dotation=False)
    emit('migration_stock_historique',dict(migration={k:v for k,v in r.items() if k!='sauvegarde'},apres_migration=migrated,stock_global_lu=amort_before,cloture_suivante=r2,etat=snapshot(c,2026)));c.close()
    c,p=new(n=2);seedstock(c,2024,2000,{1:1000,2:1000});seedstock(c,2025,5000);income(c,1000)
    r=fiscal.cloturer(c,2026,generer_dotation=False)
    emit('historique_partiel_par_bien',dict(cloture=r,etat=snapshot(c,2026)));c.close()

def rounding():
    c,p=new(n=4)
    for b in range(1,5):addcomp(c,b,10,d=10)
    income(c,3.98);r=fiscal.cloturer(c,2026)
    emit('repartition_centimes',dict(cloture=r,etat=snapshot(c,2026)));c.close()

def manual_and_pdf():
    for manuel in (0,1000):
        c,p=new();addcomp(c);income(c,200)
        before=[x.code for x in controles.controler(c,2026)]
        r=fiscal.cloturer(c,2026,autres_retraitements=manuel)
        emit('report_saisi_manuellement_'+str(manuel),dict(controles_avant=before,cloture=r,etat=snapshot(c,2026)))
        if not manuel:emit('pdf_reintegration',pdf(c,2026,'reintegration'));open_(c,2027);income(c,3000,2027);r2=fiscal.cloturer(c,2027);emit('pdf_utilisation',dict(cloture=r2,pdf=pdf(c,2027,'utilisation')))
        c.close()
    c,p=new();addcomp(c);seedstock(c,2025,5000,{1:5000});cession.ceder_bien(c,1,'2026-12-31',12000);r=fiscal.cloturer(c,2026)
    emit('pdf_cession_un_bien',dict(cloture=r,etat=snapshot(c,2026),pdf=pdf(c,2026,'cession_un_bien')));c.close()
    # Automatique = retraitements des opérations, pas le report calculé par le 39 C.
    for active in (1,0):
        c,p=new();parametres.definir(c,'retraitement_alur_auto',active,'2026-01-01');operations.saisir(c,type='fonds_travaux_alur',montant=200,date_operation='2026-01-10')
        emit('automatique_'+str(active),dict(auto=fiscal.retraitement_automatique(c,2026),agregats=fiscal.agregats(c,2026)));c.close()

def complements():
    # Même charge ALUR : neutralisation automatique ou manuelle, sans cumul.
    for active in (1,0):
        c,p=new();addcomp(c);income(c,1200)
        parametres.definir(c,'retraitement_alur_auto',active,'2026-01-01')
        operations.saisir(c,type='fonds_travaux_alur',montant=200,date_operation='2026-01-10')
        r=fiscal.cloturer(c,2026,autres_retraitements=0 if active else 200)
        emit('alur_equivalence_'+str(active),r);c.close()
    # Appel réel du gestionnaire Flask dans un contexte POST ; seule la base
    # et le mode jetable sont substitués. Aucun serveur ni dossier réel ouvert.
    import os
    with patch.dict(os.environ,{'COMPTA_DB':str(WORK/'web-inutilisee.db'),'COMPTA_DB_BAC_A_SABLE':str(WORK/'web-inutilisee-bac.db')}):
        import app as web
    c,p=new();addcomp(c);income(c,200);c.close()
    with patch.object(web,'_db_path',return_value=str(p)),patch.object(web,'_en_bac_a_sable',return_value=True):
        with web.app.test_request_context('/cloturer',method='POST',data={'annee':'2026','retraitements':'1000'}):
            response=web.cloturer()
    c=sqlite3.connect(p);c.row_factory=sqlite3.Row
    from urllib.parse import urlsplit,parse_qs
    emit('web_retraitement_manuel',dict(status=response.status_code,redirection=parse_qs(urlsplit(response.location).query),statut=c.execute('SELECT statut FROM exercice WHERE annee=2026').fetchone()[0],etat=snapshot(c,2026)));c.close()
    # Cession effective en milieu d'année et lecture du suivi l'année suivante.
    c,p=new(n=2);addcomp(c,1);addcomp(c,2);seedstock(c,2025,4000,{1:1000,2:3000})
    sale=cession.ceder_bien(c,1,'2026-06-30',12000);r=fiscal.cloturer(c,2026)
    first=snapshot(c,2026);open_(c,2027);r2=fiscal.cloturer(c,2027)
    emit('cession_milieu_exercice',dict(dotation_cession=sale['dotation_complementaire'],cloture=r,etat=first,suivant=r2,etat_suivant=snapshot(c,2027)));c.close()
    # Témoins transactionnels : une lecture doit laisser le rollback agir.
    class Trace(sqlite3.Connection):
        commits=0
        def commit(self):self.commits+=1;return super().commit()
    res={}
    for name,fn in [('table',lambda c:fiscal._table_39c_bien(c)),('suivi',lambda c:fiscal.suivi_39c_par_bien(c,2026)),('exclusions',fiscal.comptes_hors_plafond_39c),('stock',lambda c:fiscal._stock_39c_ouverture(c,2026)),('parametre',lambda c:parametres.valeur(c,'retraitement_alur_auto','2026-01-01'))]:
        c,p=new();c.close();c=sqlite3.connect(p,factory=Trace);c.row_factory=sqlite3.Row
        c.execute('CREATE TABLE temoin_audit(val INTEGER)');c.commit();c.commits=0
        c.execute('BEGIN');c.execute('INSERT INTO temoin_audit VALUES(1)');fn(c)
        opened=c.in_transaction;c.rollback()
        res[name]=dict(commits=c.commits,transaction_avant_rollback=opened,temoins=c.execute('SELECT COUNT(*) FROM temoin_audit').fetchone()[0]);c.close()
    emit('lectures_transactionnelles',res)

def main():
    emit('environnement',dict(python=sys.version,sqlite=sqlite3.sqlite_version,sha256={f:hashlib.sha256((SRC/f).read_bytes()).hexdigest() for f in ('modules/fiscal.py','modules/amortissement.py','modules/liasse.py','modules/parametres.py','modules/controles.py','modules/migrations.py','modules/liasse_pdf.py','schema.sql')}))
    for fn in (pure,accounts_cases,legal_distribution,repeated_labels,histories,legacy,rounding,manual_and_pdf,complements):
        try:fn()
        except Exception as e:emit('ERREUR_'+fn.__name__,str(e));raise
    (ART/'resultats.json').write_text(json.dumps(OUT,ensure_ascii=False,indent=2,default=str)+'\n')
if __name__=='__main__':main()
