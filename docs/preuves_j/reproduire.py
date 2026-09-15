"""Audit J : bases blanches, données fictives ; aucune entrée comptable privée."""
import hashlib,json,sqlite3,sys,tempfile,subprocess,threading
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[2];SRC=ROOT/'compta_lmnp_v8.41.0/compta_lmnp'
sys.path[:0]=[str(SRC/'modules'),str(SRC)]
import init_db,fiscal,liasse,liasse_pdf,operations,ecritures,reprise,perennite,parametres,controles,export_fec,rejeu_fec
ART=Path(__file__).parent;TMP=tempfile.TemporaryDirectory(prefix='audit-j-');WORK=Path(TMP.name);SEQ=0;OUT={}

def emit(k,v):OUT[k]=v;print(k,json.dumps(v,ensure_ascii=False,default=str),flush=True)
def attempt(fn):
    try:return {'retour':fn()}
    except Exception as e:return {'erreur':type(e).__name__+': '+str(e)}
def new(y=2025):
    global SEQ
    SEQ+=1;p=WORK/f'base-{SEQ}.db';c=init_db.init_blanc(str(p),y);c.row_factory=sqlite3.Row
    c.execute("INSERT INTO exploitant VALUES(1,'Exploitant fictif','000000000','Adresse fictive')")
    c.execute("INSERT INTO bien(id,exploitant_id,libelle,prix_total) VALUES(1,1,'Bien fictif',12000)");c.commit();return c,p
def rows(c):return [dict(x) for x in c.execute('SELECT * FROM deficit_lmnp ORDER BY annee_origine,id')]
def deficit(c,y,m,solde=None,expiration=None):
    c.execute('INSERT INTO deficit_lmnp(annee_origine,montant_initial,solde,annee_expiration) VALUES(?,?,?,?)',(y,m,m if solde is None else solde,y+10 if expiration is None else expiration));c.commit()
def entry(c,y,lines):return ecritures.inserer(c,journal='OD',date=f'{y}-12-31',annee=y,piece_ref='FICTIF',libelle='Écriture fictive',lignes=lines)
def income(c,m,y=2025):return entry(c,y,[('108000',m,0),('708810',0,m)])
def charge(c,m,y=2025,account='614100'):return entry(c,y,[(account,m,0),('108000',0,m)])
def open_(c,y):return reprise.ouvrir_exercice(c,y)
def state(c,y):
    l=liasse.generer(c,y)
    return dict(lignes=rows(c),reports=l['reports'],aide=l['aide_2042c'],page=l['page_garde'],f2031=l['f2031'],f2033b=l['f2033b'],controles=[dict(code=a.code,niveau=a.niveau,message=a.message) for a in controles.controler(c,y)],conforme=l['conforme'])
def pdf(c,y,name):
    path=ART/(name+'.pdf');liasse_pdf.generer_pdf(liasse.generer(c,y),str(path))
    text=subprocess.check_output(['pdftotext','-layout',str(path),'-'],text=True)
    (ART/(name+'.txt')).write_text(text);return dict(fichier=path.name,texte=text)
def close(c,y=2025):return fiscal.cloturer(c,y,generer_dotation=False)

def pivots_fifo():
    for y in (2024,2025,2026):
        c,p=new(y);deficit(c,2015,800);income(c,300,y)
        r=close(c,y);emit('pivot_'+str(y),dict(cloture=r,etat=state(c,y)));c.close()
    for benef in (0,2000,7000,.03):
        c,p=new()
        for y,m in [(2017,1000),(2019,2000),(2024,3000)]:deficit(c,y,m)
        if benef:income(c,benef)
        r=close(c);emit('fifo_'+str(benef),dict(cloture=r,etat=state(c,2025)));c.close()
    c,p=new();deficit(c,2023,.01);deficit(c,2024,.02);income(c,.04)
    emit('fifo_centimes',dict(cloture=close(c),lignes=rows(c)));c.close()
    # Après purge le montant initial reste en SQL ; quel rendu reste-t-il ?
    c,p=new();deficit(c,2014,1200);deficit(c,2024,800)
    before=state(c,2025);before_pdf=pdf(c,2025,'peremption_avant');r=close(c)
    emit('trace_peremption',dict(avant=before,pdf_avant=before_pdf,cloture=r,apres=state(c,2025),pdf_apres=pdf(c,2025,'peremption_apres')));c.close()

def opening_and_history():
    for benefit in (500,1000,1500):
        c,p=new();deficit(c,2024,1000);income(c,benefit)
        r=close(c);v=dict(cloture=r,etat=state(c,2025))
        if benefit==1000:v['pdf']=pdf(c,2025,'deficit_epuise')
        emit('restitution_'+str(benefit),v);c.close()
    # Imputation de A, puis rendement erroné à B qui avait déjà consommé
    # une partie de son montant initial avant l'ouverture de cet exercice.
    c,p=new();deficit(c,2020,1000);deficit(c,2024,2000,solde=1000);income(c,5000)
    # 5000 consomme tout : variante mixte juste après avec bénéfice 500.
    r=close(c);emit('restitution_tout_epuise',dict(cloture=r,etat=state(c,2025)));c.close()
    c,p=new();deficit(c,2020,1000,solde=500);deficit(c,2024,2000,solde=1000);income(c,500)
    r=close(c);emit('restitution_mauvais_millesime',dict(cloture=r,etat=state(c,2025)));c.close()
    # Chronologie normale : les clôtures suivantes changent-elles l'ancienne aide ?
    c,p=new(2024);charge(c,3000,2024);close(c,2024);open_(c,2025);income(c,1000);close(c)
    first=state(c,2025);first_pdf=pdf(c,2025,'historique_avant')
    open_(c,2026);income(c,2000,2026);close(c,2026)
    emit('ancienne_declaration',dict(avant=first,apres=state(c,2025),pdf_avant=first_pdf,pdf_apres=pdf(c,2025,'historique_apres')))
    open_(c,2027);charge(c,700,2027);close(c,2027)
    emit('deficit_futur_dans_ancien_suivi',state(c,2025));c.close()
    # Cases en présence de dix millésimes non consommés, exercice des revenus 2025.
    c,p=new()
    for i,y in enumerate(range(2015,2025),1):deficit(c,y,i*100)
    close(c);emit('cases_dix_millesimes',dict(etat=state(c,2025),pdf=pdf(c,2025,'dix_millesimes')));c.close()

def creation_and_guards():
    for case in ('ordinaire','amortissement','mixte','alur'):
        c,p=new();income(c,1000)
        if case in ('ordinaire','mixte','alur'):charge(c,1300)
        if case in ('amortissement','mixte'):
            c.execute("INSERT INTO composant(bien_id,libelle,valeur_brute,duree_annees,date_mise_service,compte_immo,compte_amort,amortissable) VALUES(1,'Composant fictif',12000,10,'2025-01-01','218400','281840',1)");c.commit()
            entry(c,2025,[('218400',12000,0),('108000',0,12000)]);entry(c,2025,[('681120',1200,0),('281840',0,1200)])
        if case=='alur':operations.saisir(c,type='fonds_travaux_alur',montant=200,date_operation='2025-02-01')
        r=close(c);emit('creation_'+case,dict(cloture=r,etat=state(c,2025)));c.close()
    c,p=new();charge(c,600);a=close(c);second=attempt(lambda:close(c));c.rollback()
    emit('double_cloture',dict(premiere=a,seconde=second,lignes=rows(c)));c.close()
    c,p=new();charge(c,600);bak=perennite.sauvegarder(str(p),'avant-audit');close(c);one=rows(c);c.close()
    perennite.restaurer(str(p),bak);c=sqlite3.connect(p);c.row_factory=sqlite3.Row
    before=rows(c);r=close(c);emit('restauration_recloture',dict(premiere=one,apres_restauration=before,recloture=r,lignes=rows(c)));c.close()
    c,p=new();charge(c,600);c.close();bar=threading.Barrier(2)
    def worker(_):
        c=sqlite3.connect(p);c.row_factory=sqlite3.Row;bar.wait();v=attempt(lambda:close(c));c.close();return v
    with ThreadPoolExecutor(max_workers=2) as pool:rs=list(pool.map(worker,range(2)))
    c=sqlite3.connect(p);c.row_factory=sqlite3.Row;emit('clotures_concurrentes',dict(retours=rs,lignes=rows(c)));c.close()
    # Moteur isolé sans guichet : propriété non idempotente, pas une double clôture.
    c,p=new();fiscal.traiter_deficit(c,2025,-600);fiscal.traiter_deficit(c,2025,-600)
    emit('double_appel_isole',rows(c));c.close()
    # Exception APRÈS modification réelle des déficits ; fermeture et réouverture.
    c,p=new();deficit(c,2024,1000);income(c,600);original=fiscal.traiter_deficit
    def fail(*a,**kw):original(*a,**kw);raise RuntimeError('Interruption fictive après imputation')
    with patch.object(fiscal,'traiter_deficit',fail):r=attempt(lambda:close(c))
    c.close();c=sqlite3.connect(p);c.row_factory=sqlite3.Row
    emit('cloture_interrompue',dict(retour=r,lignes=rows(c),statut=c.execute('SELECT statut FROM exercice WHERE annee=2025').fetchone()[0],suivi=c.execute('SELECT COUNT(*) FROM suivi_39c').fetchone()[0]));c.close()
    c,p=new();c.execute('CREATE TABLE temoin(x)');c.commit();c.execute('BEGIN');c.execute('INSERT INTO temoin VALUES(1)')
    fiscal.traiter_deficit(c,2025,-600,commit=False);opened=c.in_transaction;c.rollback()
    emit('moteur_commit_false',dict(transaction=opened,lignes=rows(c),temoins=c.execute('SELECT COUNT(*) FROM temoin').fetchone()[0]));c.close()

def lmp_and_parameters():
    for imported in (False,True):
        c,p=new();operations.saisir(c,type='loyer',montant=30000,date_operation='2025-02-01');charge(c,35000)
        if imported:
            f=WORK/'recettes-fictives.txt';export_fec.exporter(c,2025,str(f));c.close();c,p=new();rejeu_fec.rejouer(c,str(f),2025)
        before=[a.code for a in controles.controler(c,2025)];r=close(c)
        emit('seuil_lmp_import_'+str(imported),dict(controles_avant=before,cloture=r,etat=state(c,2025),operations=c.execute('SELECT COUNT(*) FROM operation').fetchone()[0]));c.close()
    c,p=new();parametres.definir(c,'duree_report_deficit_lmnp',12,'2026-01-01')
    fiscal.traiter_deficit(c,2025,-100);fiscal.traiter_deficit(c,2026,-200)
    emit('parametre_versionne',rows(c));c.close()

def arrondis_declaration():
    for sens in ('benefice','deficit','anterieur'):
        for m in (100.49,100.50,100.51,101.50,.50):
            c,p=new()
            if sens=='benefice':income(c,m)
            elif sens=='deficit':charge(c,m)
            else:deficit(c,2024,m)
            close(c);v=dict(montant=m,aide=liasse.aide_2042c(c,2025))
            if m==100.50 and sens=='deficit':v['pdf']=pdf(c,2025,'arrondi_deficit')
            emit('arrondi_'+sens+'_'+str(m),v);c.close()

def separation_sur_dix_ans():
    for variant in ('normal','dotation7','honoraires6','honoraires7'):
        c,p=new();income(c,1000)
        dot='6811200' if variant=='dotation7' else '681120'
        c.execute('INSERT OR IGNORE INTO compte VALUES(?,?,?,?)',(dot,'Dotation fictive','charge',6));c.commit()
        entry(c,2025,[('218400',20000,0),('108000',0,20000)]);entry(c,2025,[(dot,2000,0),('281840',0,2000)])
        if variant.startswith('honoraires'):
            ch='6226100' if variant=='honoraires7' else '622610';c.execute('INSERT OR IGNORE INTO compte VALUES(?,?,?,?)',(ch,'Honoraires comptables fictifs','charge',6));c.commit();charge(c,500,account=ch)
        f=WORK/(variant+'.txt');export_fec.exporter(c,2025,str(f));c.close();c,p=new();replay=rejeu_fec.rejouer(c,str(f),2025)
        r=close(c)
        for y in range(2026,2036):open_(c,y);pivot=close(c,y)
        open_(c,2036);income(c,1500,2036);later=close(c,2036)
        emit('dix_ans_'+variant,dict(rejeu=replay,creation=r,pivot=pivot,apres_dix_ans=later,lignes=rows(c)));c.close()

def main():
    emit('environnement',dict(python=sys.version,sqlite=sqlite3.sqlite_version,sha256={f:hashlib.sha256((SRC/f).read_bytes()).hexdigest() for f in ('modules/fiscal.py','modules/liasse.py','modules/liasse_pdf.py','modules/controles.py','modules/parametres.py','schema.sql')}))
    for fn in (pivots_fifo,opening_and_history,creation_and_guards,lmp_and_parameters,separation_sur_dix_ans,arrondis_declaration):fn()
    (ART/'resultats.json').write_text(json.dumps(OUT,ensure_ascii=False,indent=2,default=str)+'\n')
if __name__=='__main__':main()
