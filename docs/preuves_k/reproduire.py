"""Passe K : dossiers fictifs, coupures SIGKILL et cycle pluriannuel."""
import contextlib,csv,hashlib,io,json,os,re,shutil,signal,sqlite3,subprocess,sys,tempfile
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[2];SRC=ROOT/'compta_lmnp_v8.41.0/compta_lmnp'
sys.path[:0]=[str(SRC/'modules'),str(SRC)]
import init_db,fiscal,amortissement,liasse,operations,ecritures,reprise,cession,migrations,perennite,parametres,controles,export_fec,rejeu_fec,migration_fec,fec_io
ART=Path(__file__).parent;TMP=tempfile.TemporaryDirectory(prefix='audit-k-');WORK=Path(TMP.name);SEQ=0;OUT={}
def emit(k,v):OUT[k]=v;print(k,json.dumps(v,ensure_ascii=False,default=str),flush=True)
def attempt(fn):
    try:return {'retour':fn()}
    except Exception as e:return {'erreur':type(e).__name__+': '+str(e)}
def connect(p):
    c=sqlite3.connect(p);c.row_factory=sqlite3.Row;c.execute('PRAGMA foreign_keys=ON');return c
def new(y=2025,component=False):
    global SEQ
    SEQ+=1;p=WORK/f'base-{SEQ}.db';c=init_db.init_blanc(str(p),y);c.row_factory=sqlite3.Row
    c.execute("INSERT INTO exploitant VALUES(1,'Exploitant fictif','000000000','Adresse fictive')")
    c.execute("INSERT INTO bien(id,exploitant_id,libelle,prix_total) VALUES(1,1,'Bien fictif',12000)")
    if component:c.execute("INSERT INTO composant(bien_id,libelle,valeur_brute,duree_annees,date_mise_service,compte_immo,compte_amort,amortissable) VALUES(1,'Composant fictif',12000,10,?,'218400','281840',1)",(f'{y}-01-01',))
    c.commit();return c,p
def entry(c,y,lines,journal='OD',date=None,lib='Écriture fictive'):
    return ecritures.inserer(c,journal=journal,date=date or f'{y}-12-31',annee=y,piece_ref='FICTIF',libelle=lib,lignes=lines)
def asset(c,y=2025):return entry(c,y,[('218400',12000,0),('108000',0,12000)],date=f'{y}-01-01')
def income(c,m,y=2025):return operations.saisir(c,type='loyer',montant=m,date_operation=f'{y}-12-01')
def charge(c,m,y=2025):return operations.saisir(c,type='maintenance',montant=m,date_operation=f'{y}-12-02')
def close(c,y=2025,gen=False):return fiscal.cloturer(c,y,generer_dotation=gen)
def logical(c):
    data={}
    for (t,) in c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"):
        data[t]=sorted([list(r) for r in c.execute('SELECT * FROM "'+t.replace('"','""')+'"')],key=lambda x:json.dumps(x,default=str))
    return data
def digest(c):return hashlib.sha256(json.dumps(logical(c),sort_keys=True,default=str).encode()).hexdigest()
def state(c,y=2025):
    l=liasse.generer(c,y)
    return dict(exercice=dict(c.execute('SELECT * FROM exercice WHERE annee=?',(y,)).fetchone()),balance=reprise.lire_balance_interne(c,y),ecritures=c.execute('SELECT COUNT(*) FROM ecriture WHERE exercice_annee=?',(y,)).fetchone()[0],lignes=c.execute('SELECT COUNT(*) FROM ligne l JOIN ecriture e ON l.ecriture_id=e.id WHERE e.exercice_annee=?',(y,)).fetchone()[0],deficits=[dict(r) for r in c.execute('SELECT * FROM deficit_lmnp')],suivi=[dict(r) for r in c.execute('SELECT * FROM suivi_39c')],cloture=[dict(r) for r in c.execute('SELECT * FROM cloture_fiscale')],controles=[a.code for a in controles.controler(c,y)],rc_liasse=l['f2033b']['benefice_ou_perte_310'],rf_liasse=l['f2033b']['resultat_fiscal_lmnp'],conforme=l['conforme'])

# Chaque exécution SQL d'écriture terminée est un point de coupure distinct.
# executemany est déroulé pour couper aussi entre ses insertions individuelles.
class Cursor(sqlite3.Cursor):
    def execute(self,sql,parameters=()):
        r=super().execute(sql,parameters);self.connection.after(sql);return r
    def executemany(self,sql,parameters):
        for p in parameters:self.execute(sql,p)
        return self
class Trace(sqlite3.Connection):
    def cursor(self,*a,**kw):return super().cursor(factory=Cursor)
    def execute(self,sql,parameters=()):
        r=super().execute(sql,parameters);self.after(sql);return r
    def executemany(self,sql,parameters):
        for p in parameters:self.execute(sql,p)
        return self
    def event(self,label):
        self.events.append(dict(point=len(self.events)+1,etape=label,transaction=self.in_transaction))
        if self.target==len(self.events):
            print(json.dumps(dict(dernier=self.events[-1],commits=self.commits)),flush=True)
            os.kill(os.getpid(),signal.SIGKILL)
    def after(self,sql):
        if re.match(r'^\s*(INSERT|UPDATE|DELETE|CREATE|ALTER|BEGIN|SAVEPOINT|RELEASE)\b',sql,re.I):self.event('SQL '+re.sub(r'\s+',' ',sql).strip())
    def commit(self):
        self.commits+=1;self.event('avant commit');super().commit();self.event('apres commit')
def worker(db,target):
    c=sqlite3.connect(db,factory=Trace);c.row_factory=sqlite3.Row;c.events=[];c.commits=0;c.target=int(target)
    c.execute('PRAGMA foreign_keys=ON')
    originals={n:getattr(fiscal,n) for n in ('_calcul_fiscal','_ventiler_39c_par_bien','traiter_deficit')}
    def wrap(name,fn):
        def call(*a,**kw):
            c.event('avant '+name);r=fn(*a,**kw);c.event('apres '+name);return r
        return call
    for name,fn in originals.items():setattr(fiscal,name,wrap(name,fn))
    amortissement.generer_cloture=wrap('generer_cloture',amortissement.generer_cloture)
    fiscal.cloturer(c,2025)
    print(json.dumps(dict(events=c.events,commits=c.commits,empreinte=digest(c))),flush=True);c.close()

def kills():
    results={}
    for mode in ('creation_deficit','imputation_deficit'):
        c,p=new(component=True);asset(c);income(c,1000 if mode=='creation_deficit' else 4000)
        if mode=='creation_deficit':charge(c,1300)
        c.execute('INSERT INTO deficit_lmnp(annee_origine,montant_initial,solde,annee_expiration) VALUES(2024,1000,1000,2034)')
        # Le stock initial de 39 C est nul ici.
        c.commit();initial=digest(c);c.close();normal=WORK/(mode+'-normal.db');shutil.copyfile(p,normal)
        run=subprocess.run([sys.executable,__file__,'worker',str(normal),'0'],capture_output=True,text=True,check=True)
        trace=json.loads(run.stdout);finished=trace['empreinte'];cases=[]
        for event in trace['events']:
            dest=WORK/(mode+'-'+str(event['point'])+'.db');shutil.copyfile(p,dest)
            r=subprocess.run([sys.executable,__file__,'worker',str(dest),str(event['point'])],capture_output=True,text=True)
            c=connect(dest);got=digest(c);post=event['etape']=='apres commit'
            check=dict(point=event['point'],etape=event['etape'],transaction=event['transaction'],code=r.returncode,integrite=c.execute('PRAGMA integrity_check').fetchone()[0],etat_attendu='clos' if post else 'initial',identique=got==(finished if post else initial))
            if not post:
                close(c,gen=True);check['relance_identique']=digest(c)==finished
            else:check['relance']=attempt(lambda:close(c,gen=True))
            c.close();cases.append(check)
        results[mode]=dict(commits=trace['commits'],trace=trace['events'],coupures=cases)
    emit('sigkill_tous_points',results)

def chronology():
    c,p=new();asset(c);income(c,600);r25=close(c);reprise.ouvrir_exercice(c,2024,avec_reprise=False);charge(c,1000,2024);r24=close(c,2024)
    late=dict(cloture_2025=r25,cloture_2024=r24,etat_2025=state(c));c.close()
    c,p=new(2024);charge(c,1000,2024);close(c,2024);reprise.ouvrir_exercice(c,2025);asset(c);income(c,600)
    late['ordre_chronologique']=close(c);late['etat_chronologique']=state(c);c.close()
    emit('cloture_anterieure_apres_suivante',late)
    for y in (2025,2040):
        c,p=new(y);r=attempt(lambda:close(c,y));next_=attempt(lambda:reprise.ouvrir_exercice(c,y+1))
        emit('exercice_vide_'+str(y),dict(cloture=r,ouverture_suivante=next_,exercices=[dict(x) for x in c.execute('SELECT * FROM exercice')],controles=[a.code for a in controles.controler(c,y+1)]));c.close()
    c,p=new();asset(c);income(c,600);close(c);reprise.ouvrir_exercice(c,2026)
    before=state(c,2026);refusal=attempt(lambda:reprise.construire_an_interne(c,2026));c.rollback()
    c.execute("DELETE FROM ecriture WHERE exercice_annee=2026 AND journal_code='AN'");c.commit()
    again=reprise.construire_an_interne(c,2026)
    after=state(c,2026);close(c,2026);following=attempt(lambda:reprise.ouvrir_exercice(c,2027))
    emit('suppression_an_reconstruction',dict(avant=before,second_refuse=refusal,reconstruction=again,apres=after,affectations=c.execute("SELECT COUNT(*) FROM ecriture WHERE exercice_annee=2026 AND libelle='Affectation du résultat'").fetchone()[0],ouverture_2027=following));c.close()
    c,p=new();asset(c);close(c);reprise.ouvrir_exercice(c,2026,avec_reprise=False)
    emit('ouverture_sans_an',state(c,2026));c.close()

def multiyear():
    c,p=new(2024,True);asset(c,2024);files=[];native={}
    for y,r,ch in [(2024,1000,1300),(2025,2400,200),(2026,4000,200)]:
        if y!=2024:reprise.ouvrir_exercice(c,y)
        income(c,r,y);charge(c,ch,y);res=close(c,y,True);f=WORK/f'cycle-{y}.txt';export_fec.exporter(c,y,str(f));files.append(str(f));native[y]=dict(cloture=res,balance=reprise.lire_balance_interne(c,y))
    comps=[tuple(x) for x in c.execute('SELECT bien_id,libelle,valeur_brute,duree_annees,date_mise_service,compte_immo,compte_amort,amortissable FROM composant')];c.close()
    order=migration_fec.ordonner(list(reversed(files)));obs=migration_fec.controler_jonctions(order)
    with Path(files[1]).open() as f:records=list(csv.reader(f,delimiter='\t'))
    for r in records[1:]:
        if r[0]=='AN' and r[4]=='218400':r[11]=str(float(r[11].replace(',','.'))+.01).replace('.',',')
        if r[0]=='AN' and r[4]=='108000':r[12]=str(float(r[12].replace(',','.'))+.01).replace('.',',')
    modified=WORK/'jonction-centime.txt'
    with modified.open('w',newline='') as f:csv.writer(f,delimiter='\t',lineterminator='\r\n').writerows(records)
    pair=[order[0],dict(annee=2025,chemin=str(modified))]
    emit('jonction_un_centime',dict(avant=migration_fec._balance_bilan(files[0]),apres=migration_fec._balance_bilan(str(modified),ouverture=True),controle=migration_fec.controler_jonctions(pair),controle_sans_tolerance=migration_fec.controler_jonctions(pair,tolerance=0)))
    comparisons={}
    for gen in (False,True):
        c,p=new(2024);c.executemany('INSERT INTO composant(bien_id,libelle,valeur_brute,duree_annees,date_mise_service,compte_immo,compte_amort,amortissable) VALUES(?,?,?,?,?,?,?,?)',comps);c.commit();rs={}
        for item in order:
            y=item['annee']
            if y!=2024:reprise.ouvrir_exercice(c,y,avec_reprise=False)
            rej=rejeu_fec.rejouer(c,item['chemin'],y)
            try:r=close(c,y,gen)
            except Exception as exc:
                c.rollback();rs[y]=dict(rejeu=rej,erreur=type(exc).__name__+': '+str(exc));break
            bal=reprise.lire_balance_interne(c,y)
            rs[y]=dict(rejeu=rej,cloture=r,balance=bal,balance_identique=bal==native[y]['balance'],fiscal_identique=r==native[y]['cloture'])
        comparisons[str(gen)]=rs;c.close()
    emit('trois_exercices',dict(natif=native,rejeux=comparisons,jonctions=obs))

def external():
    c,p=new();
    for n,t in [('3100000','actif'),('4010000','passif'),('4110000','actif'),('5120000','actif'),('6450000','charge'),('6580000','charge'),('6811000','charge'),('6950000','charge')]:
        c.execute('INSERT OR IGNORE INTO compte VALUES(?,?,?,?)',(n,'Compte fictif',t,int(n[0])))
    c.commit();entry(c,2025,[('3100000',100,0),('4110000',200,0),('5120000',300,0),('4010000',0,400),('108000',0,200)])
    for n in ('6450000','6580000','6811000','6950000'):entry(c,2025,[(n,1000,0),('108000',0,1000)])
    f=WORK/'cabinet-fictif.txt';export_fec.exporter(c,2025,str(f));c.close();c,p=new();r=rejeu_fec.rejouer(c,str(f),2025);ag=fiscal.agregats(c,2025);b=liasse.resultat_2033b(c,2025);close(c);reprise.ouvrir_exercice(c,2026)
    emit('comptes_externes',dict(rejeu=r,rc_fiscal=ag['resultat_comptable'],rc_liasse=b['benefice_ou_perte_310'],ouverture=state(c,2026),equilibre=reprise.controle_equilibre(c,2026)));c.close()
    c,p=new();entry(c,2025,[('218400',.01,0),('108000',0,.01)]);close(c);reprise.ouvrir_exercice(c,2026)
    emit('an_un_centime',dict(balance=reprise.lire_balance_interne(c,2026),equilibre=reprise.controle_equilibre(c,2026)));c.close()
    c,p=new(2026)
    with patch.object(reprise,'controle_equilibre',wraps=reprise.controle_equilibre) as check:
        bad=attempt(lambda:reprise._construire_an_depuis_balance(c,{'218400':800,'108000':-799},2026))
        calls=check.call_count
    c.close();c=connect(p);emit('an_desequilibre_refuse',dict(retour=bad,appels_controle_equilibre=calls,ecritures=c.execute('SELECT COUNT(*) FROM ecriture').fetchone()[0]));c.close()
    # Dates d'AN : le même fichier a quatre lignes AN et deux lignes courantes.
    c,p=new()
    entry(c,2025,[('218400',12000,0),('108000',0,11000),('120000',0,500),('108000',0,500)],journal='AN',date='2025-01-01');income(c,600)
    good=WORK/'an-janvier.txt';export_fec.exporter(c,2025,str(good));c.close()
    with good.open() as handle:records=list(csv.reader(handle,delimiter='\t'))
    for row in records[1:]:
        if row[0]=='AN':row[3]='20241231'
    old=WORK/'an-decembre.txt'
    with old.open('w',newline='') as handle:csv.writer(handle,delimiter='\t',lineterminator='\r\n').writerows(records)
    for f in (good,old):
        c,p=new();v=attempt(lambda:rejeu_fec.rejouer(c,str(f),2025));c.close();c=connect(p)
        emit('dates_'+f.stem,dict(annee_detectee=migration_fec.annee_du_fec(str(f)),rejeu=v,ecritures=c.execute('SELECT COUNT(*) FROM ecriture').fetchone()[0]));c.close()
    # Échec du troisième lot après deux insertions réelles.
    c,p=new();income(c,100);income(c,200);income(c,300);f=WORK/'interruption.txt';export_fec.exporter(c,2025,str(f));c.close();c,p=new();original=ecritures.inserer;count=0
    def fail(*a,**kw):
        nonlocal count
        count+=1
        if count==3:raise RuntimeError('Interruption fictive au troisième lot')
        return original(*a,**kw)
    with patch.object(ecritures,'inserer',fail):r=attempt(lambda:rejeu_fec.rejouer(c,str(f),2025))
    c.commit();left=c.execute('SELECT COUNT(*) FROM ecriture').fetchone()[0];retry=rejeu_fec.rejouer(c,str(f),2025)
    emit('rejeu_interrompu',dict(erreur=r,restantes=left,relance=retry,final=c.execute('SELECT COUNT(*) FROM ecriture').fetchone()[0]));c.close()

def web_cli():
    c,p=new(component=True);asset(c);income(c,1000);charge(c,1300);c.close();paths={}
    for name in ('web','cli'):
        folder=WORK/name;folder.mkdir();paths[name]=folder/'compta.db';shutil.copyfile(p,paths[name])
    env=dict(os.environ,COMPTA_DB=str(paths['cli']),COMPTA_DB_BAC_A_SABLE=str(WORK/'jamais.db'))
    cli=subprocess.run([sys.executable,str(SRC/'cli.py'),'cloturer','--annee','2025'],env=env,capture_output=True,text=True)
    with patch.dict(os.environ,COMPTA_DB=str(paths['web']),COMPTA_DB_BAC_A_SABLE=str(WORK/'jamais.db')):import app as web
    from urllib.parse import urlsplit,parse_qs
    with patch.object(web,'_db_path',return_value=str(paths['web'])),patch.object(web,'_en_bac_a_sable',return_value=False):
        with web.app.test_request_context('/cloturer',method='POST',data={'annee':'2025'}):r=web.cloturer()
    cs={name:connect(path) for name,path in paths.items()};states={name:state(c) for name,c in cs.items()};same=logical(cs['web'])==logical(cs['cli'])
    for c in cs.values():c.close()
    def files(path):
        return {str(f.relative_to(path.parent)):hashlib.sha256(f.read_bytes()).hexdigest() for f in path.parent.rglob('*') if f.is_file() and f.name!='compta.db' and f.suffix.lower()!='db'}
    backups={}
    for n,p in paths.items():
        b=next((p.parent/'sauvegardes').glob('*.db'));conn=connect(b);backups[n]=logical(conn);conn.close()
    differences={k:dict(web=backups['web'].get(k),cli=backups['cli'].get(k)) for k in set(backups['web'])|set(backups['cli']) if backups['web'].get(k)!=backups['cli'].get(k)}
    emit('parite_web_cli',dict(cli_code=cli.returncode,cli_sortie=cli.stdout.replace(str(WORK),'DOSSIER_FICTIF'),cli_erreur=cli.stderr.replace(str(WORK),'DOSSIER_FICTIF'),web_code=r.status_code,web_message=parse_qs(urlsplit(r.location).query),bases_identiques=same,etats=states,fichiers={n:files(p) for n,p in paths.items()},differences_sauvegardes=differences))
    # Échec d'archivage après commit, avec vrai gestionnaire web.
    c,p=new();income(c,600);c.close()
    with patch.object(web,'_db_path',return_value=str(p)),patch.object(web,'_en_bac_a_sable',return_value=False),patch.object(perennite,'archiver_fec',side_effect=PermissionError('Archive fictive inaccessible')):
        with web.app.test_request_context('/cloturer',method='POST',data={'annee':'2025'}):r=web.cloturer()
    c=connect(p);emit('archive_web_refusee',dict(message=parse_qs(urlsplit(r.location).query),etat=state(c)));c.close()

    import cli as module_cli
    from types import SimpleNamespace
    c,p=new();income(c,600);c.close();output=io.StringIO()
    with patch.object(module_cli,'DB',str(p)),patch.object(perennite,'archiver_fec',side_effect=PermissionError('Archive fictive inaccessible')),contextlib.redirect_stdout(output):
        r=attempt(lambda:module_cli.cmd_cloturer(SimpleNamespace(annee=2025,forcer=False,retraitements=0)))
    c=connect(p);emit('archive_cli_refusee',dict(retour=r,sortie=output.getvalue().replace(str(WORK),'DOSSIER_FICTIF'),etat=state(c)));c.close()

def immutable_and_frozen():
    c,p=new(component=True);asset(c);op=income(c,1200)
    operations.saisir(c,type='fonds_travaux_alur',montant=200,date_operation='2025-02-01')
    backup=perennite.sauvegarder(str(p),'avant-cloture');r=close(c,gen=True);before=logical(c)
    attempts={
        'insertion':attempt(lambda:entry(c,2025,[('108000',100,0),('708810',0,100)])),
        'annulation':attempt(lambda:operations.annuler(c,op['operation_id'])),
        'cession':attempt(lambda:cession.ceder_bien(c,1,'2025-12-31',12000)),
        'reprise_an':attempt(lambda:reprise._construire_an_depuis_balance(c,{'218400':12000,'108000':-12000},2025)),
        'double_cloture':attempt(lambda:close(c,gen=True))}
    c.rollback();after=logical(c);same=after==before
    differences={k:dict(avant=before.get(k),apres=after.get(k)) for k in set(before)|set(after) if before.get(k)!=after.get(k)}
    preserved=all(before[k]==after[k] for k in ('ecriture','ligne','operation','exercice','cloture_fiscale','deficit_lmnp','suivi_39c','composant'))
    initial_liasse=liasse.resultat_2033b(c,2025)
    parametres.definir(c,'retraitement_alur_auto',0,'2025-01-01');changed=liasse.resultat_2033b(c,2025)
    emit('fermeture_et_retraitements_figes',dict(cloture=r,tentatives=attempts,etat_inchange=same,donnees_comptables_inchangees=preserved,differences=differences,liasse_avant=initial_liasse,liasse_apres_parametre=changed))
    # Bypass SQL explicite déjà documenté en G, pour examiner la réaction de la liasse.
    num=ecritures.prochain_num(c,2025)
    cur=c.execute("INSERT INTO ecriture(journal_code,ecriture_num,ecriture_date,exercice_annee,piece_ref,piece_date,libelle,valid_date) VALUES('OD',?,'2025-12-31',2025,'FICTIF','2025-12-31','Ajout SQL fictif','2025-12-31')",(num,))
    c.executemany('INSERT INTO ligne(ecriture_id,compte_num,libelle,debit,credit) VALUES(?,?,?,?,?)',[(cur.lastrowid,'108000','Ajout fictif',1000,0),(cur.lastrowid,'708810','Ajout fictif',0,1000)]);c.commit()
    emit('ajout_sql_apres_cloture',dict(etat=state(c),tableau=liasse.resultat_2033b(c,2025)));c.close()
    # La restauration retourne à tout l'état antérieur, puis le guichet clôt une fois.
    perennite.restaurer(str(p),backup);c=connect(p);r=close(c,gen=True);emit('restaurer_et_recloturer',dict(cloture=r,etat=state(c)));c.close()
    c,p=new(component=True);asset(c);income(c,1200);close(c,gen=True);f=WORK/'avant-schema.txt';export_fec.exporter(c,2025,str(f));a=f.read_bytes()
    c.execute("UPDATE meta SET valeur='2' WHERE cle='version_schema'");c.commit();c.close();m=migrations.migrer(str(p));c=connect(p);export_fec.exporter(c,2025,str(f))
    emit('migration_schema_exercice_clos',dict(avant=m['avant'],apres=m['apres'],fec_identique=f.read_bytes()==a,statut=c.execute('SELECT statut FROM exercice WHERE annee=2025').fetchone()[0]));c.close()

def main():
    emit('environnement',dict(python=sys.version,sqlite=sqlite3.sqlite_version,sha256={f:hashlib.sha256((SRC/f).read_bytes()).hexdigest() for f in ('modules/fiscal.py','modules/reprise.py','modules/rejeu_fec.py','modules/migration_fec.py','modules/ecritures.py','modules/liasse.py','schema.sql','app.py','cli.py')}))
    for fn in (kills,chronology,multiyear,external,web_cli,immutable_and_frozen):fn()
    (ART/'resultats.json').write_text(json.dumps(OUT,ensure_ascii=False,indent=2,default=str)+'\n')
if __name__=='__main__':
    if len(sys.argv)>1 and sys.argv[1]=='worker':worker(sys.argv[2],sys.argv[3])
    else:main()
