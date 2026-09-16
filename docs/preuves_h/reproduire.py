"""Audit H : bases blanches et identité fictive exclusivement. Aucun seed privé."""
import calendar, datetime, hashlib, json, sqlite3, sys, tempfile
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlparse, parse_qs
ROOT=Path(__file__).resolve().parents[2]
SRC=ROOT/'compta_lmnp'
sys.path[:0]=[str(SRC/'modules'),str(SRC)]
import init_db, amortissement as am, ecritures, operations, fiscal, controles, liasse, reprise, plan_immo, rejeu_fec, export_fec
TMP=tempfile.TemporaryDirectory(prefix='audit-h-'); WORK=Path(TMP.name); OUT={}; SEQ=0

def emit(k,v):
    OUT[k]=v; print(k,json.dumps(v,ensure_ascii=False,default=str),flush=True)
def attempt(fn):
    try:return {'retour':fn()}
    except Exception as e:return {'erreur':type(e).__name__+': '+str(e)}
def new(year=2026):
    global SEQ
    SEQ+=1;p=WORK/f'{SEQ}.db';c=init_db.init_blanc(str(p),year);c.row_factory=sqlite3.Row
    c.execute("INSERT INTO exploitant VALUES(1,'Exploitant fictif','000000000','Adresse fictive')")
    c.execute("INSERT INTO bien(id,exploitant_id,libelle,prix_total) VALUES(1,1,'Bien fictif',12000)")
    c.commit();return c,p

def comp(c,value=12000,duration=10,dms='2026-01-01',account='218400',amort='281840',active=1):
    cid=c.execute('INSERT INTO composant(bien_id,libelle,valeur_brute,duree_annees,date_mise_service,compte_immo,compte_amort,amortissable) VALUES(1,?,?,?,?,?,?,?)',('Composant fictif',value,duration,dms,account,amort,active)).lastrowid
    c.commit();return cid

def ins(c,year,lines,piece='MANUEL'):
    return ecritures.inserer(c,journal='OD',date=f'{year}-12-31',annee=year,piece_ref=piece,libelle='Écriture fictive',lignes=lines)
def acquisition(c,year=2026,value=12000,account='218400'):
    return ins(c,year,[(account,value,0),('108000',0,value)],'ACQUIS')
def manual(c,year,amount,account='281840',inverse=False):
    lines=[('681120',amount,0),(account,0,amount)]
    if inverse:lines=[(n,cr,d) for n,d,cr in lines]
    return ins(c,year,lines,'INVERSE' if inverse else 'MANUEL')
def codes(c,year):return [{'code':x.code,'niveau':x.niveau,'message':x.message} for x in controles.controler(c,year)]
def balance(c,y):
    return {r[0]:r[1] for r in c.execute('SELECT l.compte_num,ROUND(SUM(l.debit-l.credit),2) FROM ligne l JOIN ecriture e ON e.id=l.ecriture_id WHERE e.exercice_annee=? GROUP BY l.compte_num',(y,))}
def state(c,y):
    return dict(suivi_39c=[dict(r) for r in c.execute('SELECT * FROM suivi_39c WHERE exercice_annee=?',(y,))],bilan=liasse.bilan_2033a(c,y),tableau=liasse.immobilisations_2033c(c,y)['totaux'],plans=[dict(r) for r in c.execute('SELECT * FROM plan_amortissement WHERE exercice_annee=?',(y,))],controles=codes(c,y),liasse_controles=liasse.generer(c,y)['controles'])
def open_year(c,y,an=True):
    reprise.ouvrir_exercice(c,y,avec_reprise=an)

def plans():
    samples={}
    for val,dur,date in [(1299.87,15,'2026-06-17'),(1299.87,15,'2026-12-31'),(1299.87,1,'2026-12-31'),(365,1,'2024-07-01'),(.01,50,'2026-01-01'),(.01,3,'2026-12-31'),(1,50,'2026-01-01')]:
        p=am.plan(val,dur,date);samples[f'{val}/{dur}/{date}']={'plan':p,'total_decimal':str(sum((Decimal(str(v)) for _,v in p),Decimal(0))),'total_float':sum(v for _,v in p)}
    emit('plans_cibles',samples)
    errors=[];tested=0
    for year in (2023,2024):
        for day in range(1,367 if calendar.isleap(year) else 366):
            date=(datetime.date(year,1,1)+datetime.timedelta(days=day-1)).isoformat()
            for dur in (1,2,3,8,10,15,20,25,50,100):
                for val in (1299.87,12000,100000.01):
                    p=am.plan(val,dur,date);total=sum((Decimal(str(v)) for _,v in p),Decimal(0));tested+=1
                    if total!=Decimal(str(val)) or any(v<0 for _,v in p):errors.append([val,dur,date,str(total)])
    emit('matrice_plans',dict(cas=tested,erreurs=errors))
    emit('durees_invalides_plan',{str(x):attempt(lambda x=x:am.plan(12000,x,'2026-01-01')) for x in (0,-1,-10,None)})
    emit('prorata',{'non_bissextile':[str(am.fraction_prorata('2023-07-01')),str(am.fraction_prorata('2024-01-01','2024-06-30'))], 'bissextile':[str(am.fraction_prorata('2024-07-01')),str(am.fraction_prorata('2025-01-01','2025-06-30'))]})

def basic():
    c,p=new();comp(c);acquisition(c)
    first=am.generer_cloture(c,2026);second=attempt(lambda:am.generer_cloture(c,2026));emit('double_generation',dict(premier=first,second=second,solde=balance(c,2026)));c.close()
    c,p=new();comp(c);acquisition(c);before=c.execute('SELECT COUNT(*) FROM ecriture').fetchone()[0]
    am.generer_cloture(c,2026,commit=False);inside=c.in_transaction;c.rollback();emit('generation_rollback',dict(transaction=inside,avant=before,apres=c.execute('SELECT COUNT(*) FROM ecriture').fetchone()[0],plans=c.execute('SELECT COUNT(*) FROM plan_amortissement').fetchone()[0]));c.close()
    for duration in (0,-1,None):
        c,p=new();comp(c,duration=duration)
        emit('base_duree_'+str(duration),dict(dotation=attempt(lambda:am.dotations_exercice(c,2026)),controles=attempt(lambda:codes(c,2026)),cloture=attempt(lambda:fiscal.cloturer(c,2026)),ecritures=c.execute('SELECT COUNT(*) FROM ecriture').fetchone()[0]));c.close()
    for active,account in [(0,None),(1,None),(1,'281840')]:
        c,p=new();comp(c,duration=10,account='211550',amort=account,active=active)
        emit(f'terrain_{active}_{account}',dict(controles=controles.c_composant_non_amortissable(c,2026),cloture=attempt(lambda:am.generer_cloture(c,2026)),solde=balance(c,2026)));c.close()

def omissions():
    for date in ('2026-01-01','2026-12-31'):
        c,p=new();comp(c,dms=date);acquisition(c)
        before=codes(c,2026);fiscal.cloturer(c,2026,generer_dotation=False)
        after=state(c,2026);open_year(c,2027);next_=dict(dotations=am.dotations_exercice(c,2027),controles=codes(c,2027),manquants=operations.amortissements_anterieurs_manquants(c,2027))
        fix=attempt(lambda:operations.reprendre_amortissements_anterieurs(c,2027));emit('omission_'+date,dict(avant=before,apres=after,suivant=next_,reprise=fix,solde_apres_reprise=balance(c,2027)));c.close()
    c,p=new();comp(c);acquisition(c);open_year(c,2027,False)
    emit('precedent_ouvert',dict(dotation_proposee=am.dotations_exercice(c,2027),cloture=attempt(lambda:fiscal.cloturer(c,2027)),ecritures_2027=c.execute('SELECT COUNT(*) FROM ecriture WHERE exercice_annee=2027').fetchone()[0]));c.close()

def manual_cases():
    c,p=new();comp(c);acquisition(c);manual(c,2026,1200)
    operations.saisir(c,type='loyer',montant=1800,date_operation='2026-01-10',bien_id=1)
    avant=codes(c,2026);result=fiscal.cloturer(c,2026)
    emit('manuel_resultat_fiscal',dict(controles_avant=avant,cloture=result,etat=state(c,2026)));c.close()
    for inverse in (False,True):
        c,p=new();comp(c,duration=1);acquisition(c);manual(c,2026,12000)
        if inverse:manual(c,2026,12000,inverse=True)
        before=state(c,2026);fiscal.cloturer(c,2026);after=state(c,2026)
        emit('manuel_'+str(inverse),dict(avant=before,apres=after,solde=balance(c,2026)));c.close()
    c,p=new();comp(c);acquisition(c);am.generer_cloture(c,2026);manual(c,2026,1200,inverse=True)
    emit('daa_annulee',dict(etat=state(c,2026),seconde=attempt(lambda:am.generer_cloture(c,2026)),solde=balance(c,2026)));c.close()

def duration_changes():
    for shared in (False,True):
        c,p=new();comp(c,8000,5)
        if shared:comp(c,8000,5)
        acquisition(c,value=16000 if shared else 8000)
        for y in (2026,2027,2028):
            if y>2026:open_year(c,y)
            fiscal.cloturer(c,y)
        open_year(c,2029);c.execute('UPDATE composant SET duree_annees=8');c.commit()
        initial=codes(c,2029);series=[]
        for y in range(2029,2034):
            if y>2029:open_year(c,y)
            dots=am.dotations_exercice(c,y);fiscal.cloturer(c,y)
            series.append(dict(annee=y,dotations=dots,solde=balance(c,y),etat=state(c,y)))
        emit('duree_allongee_partage_'+str(shared),dict(controles_initiaux=initial,exercices=series));c.close()
    for mutation in ('raccourcie','valeur_corrigee'):
        c,p=new();comp(c,8000,8);acquisition(c,value=8000)
        for y in (2026,2027,2028):
            if y>2026:open_year(c,y)
            fiscal.cloturer(c,y)
        open_year(c,2029)
        c.execute('UPDATE composant SET duree_annees=4' if mutation=='raccourcie' else 'UPDATE composant SET valeur_brute=2000');c.commit()
        emit(mutation,dict(dotation=am.dotations_exercice(c,2029),etat=state(c,2029)));c.close()

def ventilation():
    emit('quote_parts',{str(q):dict(normalisation=am.normaliser_quote_part(q,100000),lignes=am.ventilation_proposee(100000,q)) for q in ('7,35',.0735,1.0,0,None)})
    for total in (0,1000,11400,12000):
        c,p=new()
        if total:comp(c,total)
        acquisition(c)
        emit('ventilation_'+str(total),dict(controles=codes(c,2026),dotation=am.dotations_exercice(c,2026),liasse=liasse.generer(c,2026)['controles']));c.close()

def imported():
    cols=['JournalCode','JournalLib','EcritureNum','EcritureDate','CompteNum','CompteLib','CompAuxNum','CompAuxLib','PieceRef','PieceDate','EcritureLib','Debit','Credit','EcritureLet','DateLet','ValidDate','Montantdevise','Idevise']
    rows=[]
    entries=[('2180000',8000,0),('2181000',12000,0),('2818000',0,800),('2818100',0,1200),('108000',0,18000)]
    for n,d,cr in entries:
        row=['AN','À nouveau fictif','1','20260101',n,'Compte fictif','','','AN-1','20260101','Reprise fictive',str(d),str(cr),'','','20260101','',''];rows.append(row)
    path=WORK/'cabinet.txt';path.write_text('\r\n'.join(['\t'.join(cols)]+['\t'.join(r) for r in rows])+'\r\n')
    c,p=new();ret=rejeu_fec.rejouer(c,str(path),2026)
    emit('fec_sans_composants',dict(rejeu=ret,etat=state(c,2026),menu=plan_immo.pour_la_saisie()))
    comp(c,8000,10,'2025-01-01','2180000','2818000');comp(c,12000,10,'2025-01-01','2181000','2818100')
    fiscal.cloturer(c,2026)
    emit('fec_avec_composants',dict(etat=state(c,2026),rubriques=liasse.immobilisations_2033c(c,2026)['rubriques'],solde=balance(c,2026),cumul=am._cumul_comptabilise(c,1,'2818000',2026)));c.close()

def web_cases():
    import app as web
    def call(p,fn,data):
        with patch.object(web,'_db_path',return_value=str(p)),web.app.test_request_context('/',method='POST',data=data):
            response=fn();return parse_qs(urlparse(response.location).query)
    for duration in ('-1','0',''):
        c,p=new();c.close()
        ret=call(p,web.creer_composant,dict(annee='2026',bien_id='1',libelle='Composant fictif',compte_immo='218400',valeur_brute='12000',duree_annees=duration,date_mise_service='2026-01-01'))
        c=sqlite3.connect(p);c.row_factory=sqlite3.Row
        emit('web_creation_duree_'+duration,dict(reponse=ret,composants=[dict(r) for r in c.execute('SELECT * FROM composant')],dotation=attempt(lambda:am.dotations_exercice(c,2026)),cloture=attempt(lambda:fiscal.cloturer(c,2026)),tableau=liasse.immobilisations_2033c(c,2026)['totaux'],solde=balance(c,2026)));c.close()
    c,p=new();cid=comp(c);acquisition(c);fiscal.cloturer(c,2026);before=state(c,2026);c.close()
    ret=call(p,lambda:web.composant_duree(cid),dict(annee='2026',duree_annees='20'))
    c=sqlite3.connect(p);c.row_factory=sqlite3.Row;emit('web_modification_clos',dict(reponse=ret,avant=before,apres=state(c,2026)));c.close()

def extra_cases():
    c,p=new();comp(c,8000,8,'2025-01-01');acquisition(c,value=8000)
    ecritures.inserer(c,journal='AN',date='2026-01-01',annee=2026,piece_ref='AN-1',libelle='Historique fictif',lignes=[('108000',8000,0),('281840',0,8000)])
    before=am._cumul_comptabilise(c,1,'281840',2026);fiscal.cloturer(c,2026)
    emit('an_premier_exercice',dict(cumul_lu=before,etat=state(c,2026),solde=balance(c,2026)));c.close()
    c,p=new();comp(c,8000,8);acquisition(c,value=8000)
    for y in (2026,2027,2028):
        if y>2026:open_year(c,y)
        fiscal.cloturer(c,y)
    c.execute('UPDATE composant SET duree_annees=4');c.commit()
    series=[]
    for y in (2029,2030,2031):
        open_year(c,y);dots=am.dotations_exercice(c,y);fiscal.cloturer(c,y)
        series.append(dict(annee=y,dotations=dots,solde=balance(c,y),etat=state(c,y)))
    emit('raccourcie_fin_plan',series);c.close()
    # Un composant unique : plan figé réconcilié à 8000, tableau recalculé à 7000.
    c,p=new();comp(c,1299.87,15);acquisition(c,value=1299.87);fiscal.cloturer(c,2026)
    emit('arrondi_cumul_normal',state(c,2026));c.close()
    for val,dur in [(.24,50),(100000.01,50)]:
        pp=am.plan(val,dur,'2026-01-01')
        emit('plan_residuel_'+str(val),dict(nb=len(pp),premier=pp[0],dernier=pp[-1],somme=str(sum((Decimal(str(d)) for _,d in pp),Decimal(0)))))
    # Injection d'une interruption APRÈS l'écriture DAA, lors de la trace du plan.
    c,p=new();comp(c);acquisition(c)
    c.execute("CREATE TRIGGER refus_plan BEFORE INSERT ON plan_amortissement BEGIN SELECT RAISE(ABORT,'interruption fictive'); END");c.commit()
    ret=attempt(lambda:am.generer_cloture(c,2026,commit=False));pending=c.in_transaction;c.rollback();c.close()
    c=sqlite3.connect(p);emit('interruption_plan',dict(retour=ret,transaction_avant_rollback=pending,ecritures=c.execute('SELECT COUNT(*) FROM ecriture').fetchone()[0],lignes=c.execute('SELECT COUNT(*) FROM ligne').fetchone()[0],plans=c.execute('SELECT COUNT(*) FROM plan_amortissement').fetchone()[0]));c.close()
    c,p=new();comp(c);acquisition(c)
    # Simule une erreur de lecture SQLite dans la table comptable, sans modifier le calcul.
    c.execute('ALTER TABLE ecriture RENAME TO ecriture_indisponible');c.commit()
    emit('lecture_cumul_indisponible',dict(cumul=am._cumul_comptabilise(c,1,'281840',2026),dotations=attempt(lambda:am.dotations_exercice(c,2026)),controle_anterieurs=controles.c_amortissements_anterieurs(c,2027),controle_complet=attempt(lambda:codes(c,2027))));c.close()


def contracts():
    import gabarits, parametres
    class Trace(sqlite3.Connection):
        commits=0
        commit_states=[]
        def commit(self):
            self.commits+=1
            self.commit_states.append(self.in_transaction)
            return super().commit()
    c,p=new();c.close();c=sqlite3.connect(p,factory=Trace);c.execute('PRAGMA foreign_keys=ON')
    gabarits.ajouter_personnalise(c,cle='audit_fictif',libelle='Fictif',compte_num='614100',nature='charge',retraitement='total')
    parametres.definir(c,'retraitement_alur_auto',1,'2026-01-01')
    rows=[]
    for kind in gabarits.tous(c):
        c.commits=0;c.commit_states=[]
        for _ in range(2):operations.saisir(c,type=kind,montant=800,date_operation='2026-01-10',commit=False)
        active=c.in_transaction;c.rollback()
        rows.append(dict(type=kind,transaction=active,commits=c.commits,transactions_aux_commits=list(c.commit_states),operations=c.execute('SELECT COUNT(*) FROM operation').fetchone()[0],ecritures=c.execute('SELECT COUNT(*) FROM ecriture').fetchone()[0]))
    emit('contrat_gabarits',rows)
    c.execute('CREATE TABLE temoin(montant REAL)');c.commit();rows=[]
    for kind in gabarits.tous(c):
        c.execute('BEGIN');c.execute('INSERT INTO temoin VALUES(800)');c.commits=0;c.commit_states=[]
        for _ in range(2):operations.saisir(c,type=kind,montant=800,date_operation='2026-01-10',commit=False)
        active=c.in_transaction;c.rollback()
        rows.append(dict(type=kind,transaction=active,commits=c.commits,temoins=c.execute('SELECT COUNT(*) FROM temoin').fetchone()[0],operations=c.execute('SELECT COUNT(*) FROM operation').fetchone()[0],ecritures=c.execute('SELECT COUNT(*) FROM ecriture').fetchone()[0]))
    emit('contrat_gabarits_transaction_englobante',rows)
    comp(c);acquisition(c);c.commits=0;first=fiscal.cloturer(c,2026);commits=c.commits
    second=attempt(lambda:fiscal.cloturer(c,2026));c.rollback()
    emit('cloture_commits',dict(commits=commits,dotation=first['agregats']['dotation'],seconde=second,ecritures=c.execute('SELECT COUNT(*) FROM ecriture').fetchone()[0]));c.close()
    # Modifier une durée puis utiliser le geste recommandé par AMORT_ANTERIEURS.
    c,p=new();comp(c,8000,8);acquisition(c,value=8000)
    for y in (2026,2027,2028):
        if y>2026:open_year(c,y)
        fiscal.cloturer(c,y)
    open_year(c,2029);c.execute('UPDATE composant SET duree_annees=4');c.commit()
    prev=balance(c,2029);fix=operations.reprendre_amortissements_anterieurs(c,2029)
    emit('raccourcie_reprise_suggeree',dict(avant=prev,reprise=fix,apres=balance(c,2029)));c.close()
    # Terrain : appeler la vraie route de saisie, sans remplacer son traitement.
    import app as web
    c,p=new();c.close()
    with patch.object(web,'_db_path',return_value=str(p)),web.app.test_request_context('/',method='POST',data=dict(annee=2026,bien_id=1,libelle='Terrain fictif',compte_immo='211550',valeur_brute=12000,duree_annees=10,date_mise_service='2026-01-01')):
        response=web.creer_composant();ret=parse_qs(urlparse(response.location).query)
    c=sqlite3.connect(p);emit('terrain_saisie_refusee',dict(reponse=ret,composants=c.execute('SELECT COUNT(*) FROM composant').fetchone()[0],ecritures=c.execute('SELECT COUNT(*) FROM ecriture').fetchone()[0]));c.close()
    # Couverture explicite du défaut déjà décrit dans G-12, sans nouveau constat.
    v=am.ventilation_proposee(100000.01,.73117)
    emit('renvoi_G12',dict(terrain=v[0]['montant'],total=round(sum(x['montant'] for x in v),2)))


def main():
    emit('environnement',dict(python=sys.version,sqlite=sqlite3.sqlite_version,sha256={f:hashlib.sha256((SRC/f).read_bytes()).hexdigest() for f in ('modules/amortissement.py','modules/controles.py','modules/operations.py','modules/liasse.py','modules/plan_immo.py','app.py','schema.sql')}))
    for fn in (plans,basic,omissions,manual_cases,duration_changes,ventilation,imported,web_cases,extra_cases,contracts):
        try:fn()
        except Exception as e:
            emit('ERREUR_'+fn.__name__,type(e).__name__+': '+str(e));raise
    Path(__file__).with_name('resultats.json').write_text(json.dumps(OUT,ensure_ascii=False,indent=2,default=str)+'\n')
if __name__=='__main__':main()
