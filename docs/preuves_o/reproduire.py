"""Preuves O : uniquement des bases blanches et des montants fictifs."""
import sys, os, json, sqlite3, tempfile, shutil, hashlib, ast, subprocess
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[2]
SRC=ROOT/'compta_lmnp'
sys.path[:0]=[str(SRC/'modules'),str(SRC)]
import init_db, perennite as p, dossiers as d, migrations as m, operations, fiscal, reprise, quittances
import app as web
OUT={}
def emit(k,v):
    OUT[k]=v
    print(k,json.dumps(v,ensure_ascii=False),flush=True)
def error(fn):
    try: return {'retour':fn()}
    except Exception as e: return {'exception':type(e).__name__,'message':str(e)}
def connect(path): return sqlite3.connect(path)
def rent(c,amount=800,year=2026):
    operations.saisir(c,type='loyer',montant=amount,date_operation=f'{year}-01-10',periode=f'{year}-01')
def new(root,name='cas',amount=800):
    folder=root/name;folder.mkdir(parents=True,exist_ok=True);path=str(folder/'compta.db')
    c=init_db.init_blanc(path,2026)
    c.execute("INSERT INTO exploitant VALUES(1,'Exploitant Fictif','000000000','Adresse fictive')")
    c.execute("INSERT INTO bien(id,exploitant_id,libelle,prix_total) VALUES(1,1,'Bien fictif',120000)")
    c.commit()
    if amount:rent(c,amount)
    c.close();return path
def state(path):
    with connect(path) as c:
        return {'operations':c.execute('select count(*) from operation').fetchone()[0],'montant':c.execute('select coalesce(sum(montant),0) from operation').fetchone()[0],'version':init_db.version_base(c),'integrite':c.execute('pragma integrity_check').fetchone()[0]}
def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
with tempfile.TemporaryDirectory(prefix='audit-o-') as tmp:
    root=Path(tmp)
    path=new(root,'wal'); c=connect(path);c.execute('pragma journal_mode=WAL');rent(c);None
    c.execute("UPDATE operation SET montant=9999 WHERE id=1")
    sv=p.sauvegarder(path);emit('wal',{'wal_present':Path(path+'-wal').exists(),'copie':state(sv),'transaction_source':c.in_transaction});c.rollback();c.close()
    path=new(root,'quotidienne');folder=Path(p.dossier_sauvegardes(path));folder.mkdir()
    bad=folder/f"compta-{p.datetime.now():%Y%m%d}-000000-demarrage.db";bad.touch()
    emit('quotidienne_vide',{'retour':p.sauvegarde_quotidienne(path),'copies':[(x['nom'],x['taille']) for x in p.lister_sauvegardes(path)]})
    # Corruption d'un index, détectable par SQLite mais copiée par backup.
    path=new(root,'index');c=connect(path);c.execute('pragma writable_schema=ON');c.execute("UPDATE sqlite_master SET rootpage=(SELECT rootpage FROM sqlite_master WHERE name='idx_ligne_compte') WHERE name='idx_ligne_ecriture'");c.commit();c.close()
    result=error(lambda:p.sauvegarder(path));emit('sauvegarde_corrompue',{'appel':result,'verdict_copie':error(lambda:state(result['retour'])) if 'retour' in result else None})
    path=new(root,'rotation');folder=Path(p.dossier_sauvegardes(path));folder.mkdir()
    for i in range(35):(folder/f'compta-20260101-{i:06}-manuel.db').touch()
    for motif in p.MOTIFS_SURETE:(folder/f'compta-20250101-000000-{motif}.db').touch()
    p._rotation(str(folder),'compta',30);emit('rotation',{'total':len(list(folder.iterdir())),'surete':sum('avant-' in x.name for x in folder.iterdir()),'premier_ordinaire':min(x.name for x in folder.iterdir() if 'manuel' in x.name)})
    path=new(root,'restore');sv=p.sauvegarder(path,'ancien');c=connect(path);rent(c);c.close();sure=p.restaurer(path,sv);after=state(path)
    # Nom différent évite de retester la collision déjà Q-05.
    recovery=str(Path(sure).with_name('compta-retour-manuel.db'));shutil.copyfile(sure,recovery);p.restaurer(path,recovery)
    emit('retour_arriere',{'apres_restaurer':after,'apres_retour':state(path)})
    before=digest(path);emit('init_protege',{'appel':error(lambda:init_db.init_blanc(path,2026)),'identique':before==digest(path)})
    empty=new(root,'vide',0);local=str(Path(p.dossier_sauvegardes(path))/'compta-vide.db');shutil.copyfile(empty,local)
    emit('restauration_vide',{'appel':error(lambda:p.restaurer(path,local)),'identique':before==digest(path)})
    other=new(root,'autre',2500);foreign=p.sauvegarder(other)
    refused=error(lambda:p.restaurer(path,foreign));local=str(Path(p.dossier_sauvegardes(path))/'compta-copie-autre.db');shutil.copyfile(foreign,local)
    accepted=error(lambda:p.restaurer(path,local));emit('appartenance',{'direct':refused,'deplace':accepted,'base':state(path)})
    path=new(root,'archives');c=connect(path);a=p.archiver_fec(c,2026,path);b=p.archiver_fec(c,2026,path);c.close()
    manifest=Path(a['manifeste']);original=manifest.read_text();file=Path(a['chemin'])
    valid=p.verifier_archives(path);file.write_text('FEC fictif altere');modified=p.verifier_archives(path);file.unlink();missing=p.verifier_archives(path)
    manifest.write_text(original.splitlines()[0]+'\nligne illisible\n'+original.splitlines()[2]+'\n');malformed=p.verifier_archives(path)
    manifest.unlink();no_manifest=p.verifier_archives(path)
    emit('archives_controle',{'valides':valid,'modifie':modified,'absent':missing,'ligne_illisible':malformed,'sans_manifeste':no_manifest})
    manifest.write_text(original);Path(a['chemin']).write_text('FEC fictif altere')
    with patch.object(web,'DB',path),patch.object(web,'HERE',str(Path(path).parent)):
        client=web.app.test_client();res=client.get('/archives');download=client.get('/archives/'+Path(a['chemin']).name)
        emit('archives_web',{'status':res.status_code,'sha_affiche':a['sha256'][:16] in res.get_data(as_text=True),'telechargement':download.status_code,'contenu':download.get_data(as_text=True)})
    # Restauration avant clôture et exercice suivant : archive externe reste intacte.
    path=new(root,'chaine');sv=p.sauvegarder(path,'avant-cycle');c=connect(path);fiscal.cloturer(c,2026);a=p.archiver_fec(c,2026,path);reprise.ouvrir_exercice(c,2027);rent(c,900,2027);c.close()
    before=state(path);p.restaurer(path,sv)
    with connect(path) as c: years=c.execute('select annee,statut from exercice').fetchall()
    emit('chaine_restauree',{'avant':before,'apres':state(path),'exercices':years,'archives':p.verifier_archives(path)})
    c=connect(path);rent(c,1000);fiscal.cloturer(c,2026);p.archiver_fec(c,2026,path);c.close()
    emit('seconde_cloture',{'archives':p.verifier_archives(path),'recettes_base':state(path)['montant'],'lignes_manifeste':Path(a['manifeste']).read_text().splitlines()})
    # Cache de migration peuplé avant restauration d'un schéma ancien.
    path=new(root,'cache');c=connect(path);c.execute("DELETE FROM compte WHERE numero='164000'");c.execute("UPDATE meta SET valeur='6' WHERE cle='version_schema'");c.commit();c.close();sv=p.sauvegarder(path,'v6');m.migrer(path)
    with patch.object(web,'DB',path),patch.object(web,'HERE',str(Path(path).parent)):
        client=web.app.test_client();client.get('/dossiers');res=client.post('/sauvegardes/restaurer',data={'nom':Path(sv).name});client.get('/dossiers')
        with connect(path) as c: count=c.execute("SELECT count(*) FROM compte WHERE numero='164000'").fetchone()[0]
        emit('cache_restauration',{'status':res.status_code,'message':res.location,'base':state(path),'compte164000':count,'cache':path in web._MIGRES})
    # Base future : migration ne touche pas ; restauration la remplace avant refus web.
    path=new(root,'futur');c=connect(path);c.execute("UPDATE meta SET valeur='99' WHERE cle='version_schema'");c.commit();c.close();sv=p.sauvegarder(path,'v99');before=digest(path);r=m.migrer(path);emit('migration_future',{'retour':r,'identique':before==digest(path)})
    c=connect(path);c.execute("UPDATE meta SET valeur='7' WHERE cle='version_schema'");c.commit();c.close()
    with patch.object(web,'DB',path),patch.object(web,'HERE',str(Path(path).parent)):
        client=web.app.test_client();res=client.post('/sauvegardes/restaurer',data={'nom':Path(sv).name});get=client.get('/dossiers');emit('restauration_future',{'post':res.status_code,'message':res.location,'get':get.status_code,'version':state(path)['version']})
    # Registre : lecture silencieuse, adoption et base absente.
    reg=root/'registre';reg.mkdir();principal=new(reg,'principal');a=d.creer(str(reg),'Dossier Alpha',2026);c=connect(a['chemin']);c.execute("INSERT INTO exploitant VALUES(1,'Exploitant Fictif','000000000','Adresse fictive')");c.execute("INSERT INTO bien(id,exploitant_id,libelle,prix_total) VALUES(1,1,'Bien fictif',120000)");c.commit();rent(c);c.close();d.renommer(str(reg),a['slug'],'Nouveau nom fictif');stable=d.chemin_db(str(reg),a['slug'])==a['chemin']
    (reg/'dossiers.json').write_text('{tronque');listed=d.lister(str(reg),principal)
    with patch.object(web,'DB',principal),patch.object(web,'HERE',str(reg)):
        client=web.app.test_client();client.set_cookie('dossier',a['slug']);res=client.get('/dossiers');
        with web.app.test_request_context('/dossiers',headers={'Cookie':f"dossier={a['slug']}"}):active=web._db_path()
        emit('registre_corrompu',{'liste':[x['slug'] for x in listed],'web':res.status_code,'retombe_principal':active==principal,'base_alpha':state(a['chemin'])})
    adopted=d.creer(str(reg),'Dossier Alpha',2026);emit('adoption',{'adopte':adopted['adopte'],'base':state(a['chemin']),'renommage_stable':stable,'collision':error(lambda:d.creer(str(reg),'Dossier Alpha',2026)),'separateur':d.slug_sur('../ailleurs')})
    Path(a['chemin']).unlink()
    with patch.object(web,'DB',principal),patch.object(web,'HERE',str(reg)):
        client=web.app.test_client();client.set_cookie('dossier',a['slug']);res=client.get('/dossiers');emit('dossier_absent',{'status':res.status_code,'base_recree':Path(a['chemin']).exists()})
    # Démarrage réel exécuté depuis AST pour rediriger HERE avant le bloc main.
    path=new(root,'startup');tree=ast.parse((SRC/'app.py').read_text());main=tree.body[-1]
    assert isinstance(main,ast.If) and '__name__' in ast.unparse(main.test)
    env=dict(vars(web));env.update(__name__='__main__',HERE=str(Path(path).parent),DB=path)
    with patch.object(p,'sauvegarde_quotidienne',side_effect=OSError(28,'Disque fictif plein')),patch.object(web.app,'run') as run:
        result=error(lambda:exec(compile(ast.Module(body=main.body,type_ignores=[]),'app.py','exec'),env));emit('demarrage_disque_plein',{'resultat':result,'serveur_lance':run.called})
    # Assertion : simulation explicite d'une future version 8 sans son palier, sous -O.
    path=new(root,'palier');code="import sys;sys.path[:0]="+repr([str(SRC/'modules')])+";import init_db;init_db.VERSION_SCHEMA=8;import migrations;print(migrations.migrer(sys.argv[1]))"
    normal=subprocess.run([sys.executable,'-c',code,path],capture_output=True,text=True)
    optimized=subprocess.run([sys.executable,'-O','-c',code,path],capture_output=True,text=True)
    emit('assertion_optimisee',{'normal_code':normal.returncode,'normal_assertion':'AssertionError' in normal.stderr,'optimise_code':optimized.returncode,'optimise_stdout':optimized.stdout.strip(),'version':state(path)['version']})
    # Numérotation : table minimale de test, même lecteur de production.
    path=new(root,'quittance');c=connect(path);c.execute("INSERT INTO locataire(id,bien_id,nom,date_entree) VALUES(1,1,'Locataire Fictif','2026-01-01')");c.execute("INSERT INTO quittance(numero,locataire_id,periode,date_emission,loyer) VALUES(1,1,'2026-01','2026-01-10',800)");c.commit();c.close();sv=p.sauvegarder(path);c=connect(path);c.execute("INSERT INTO quittance(numero,locataire_id,periode,date_emission,loyer) VALUES(2,1,'2026-02','2026-02-10',800)");c.commit();c.close();before=digest(path);emit('quittances',{'appel':error(lambda:p.restaurer(path,sv)),'identique':before==digest(path)})
    # La rotation de la copie de sûreté peut supprimer la source déjà validée.
    path=new(root,'source-purge');folder=Path(p.dossier_sauvegardes(path));folder.mkdir()
    for i in range(31):shutil.copyfile(path,folder/f'compta-20260101-{i:06}-manuel.db')
    selected=str(folder/'compta-20260101-000000-manuel.db');r=error(lambda:p.restaurer(path,selected))
    with connect(path) as c:tables=c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    emit('source_purgee',{'restaurer':r,'tables_apres':tables,'source_taille':Path(selected).stat().st_size,'surete':state(r['retour']) if 'retour' in r else None})
    # Retour effectif après la purge, puis contrôle web d'une base vide.
    with patch.object(web,'DB',path),patch.object(web,'HERE',str(Path(path).parent)):
        with web.app.test_request_context('/sauvegardes/restaurer',method='POST',data={'nom':Path(r['retour']).name}):
            web_result=error(web.sauvegardes_restaurer)
    recovery=str(Path(r['retour']).with_name('compta-retour-manuel.db'));shutil.copyfile(r['retour'],recovery);p.restaurer(path,recovery)
    emit('retour_source_purgee',{'web':web_result,'moteur':state(path)})
    # Échec d'un palier : scénario déjà Q-10, seulement confirmation.
    path=new(root,'migration-echec');c=connect(path);c.execute("UPDATE meta SET valeur='2' WHERE cle='version_schema'");c.execute("DELETE FROM compte WHERE numero IN ('675000','775000')");c.commit();c.close()
    with patch.dict(m.PALIERS,{5:lambda c:(_ for _ in ()).throw(RuntimeError('Palier fictif interrompu'))}):r=error(lambda:m.migrer(path))
    with connect(path) as c:comptes=c.execute("SELECT COUNT(*) FROM compte WHERE numero IN ('675000','775000')").fetchone()[0]
    emit('migration_echec_deja_q10',{'appel':r,'version':state(path)['version'],'comptes_cession':comptes,'copies':len(p.lister_sauvegardes(path))})
    path=new(root,'sorties');created=[];network=[]
    import socket
    def deny_network(*args,**kwargs):network.append('appel');raise RuntimeError('Réseau interdit pendant cet essai')
    def hook(event,args):
        if event=='open' and isinstance(args[0],str) and str(root) in args[0]:
            flags=args[2]
            if isinstance(flags,int) and flags & (os.O_WRONLY|os.O_RDWR|os.O_CREAT):created.append(args[0])
    sys.addaudithook(hook)
    with patch.object(socket.socket,'connect',deny_network),patch.object(web,'DB',path),patch.object(web,'HERE',str(Path(path).parent)):
        p.sauvegarder(path)
        with web.app.test_request_context('/liasse/pdf'):
            pdf=web.liasse_pdf_route();pdf.direct_passthrough=False;data=pdf.get_data()
        with web.app.test_request_context('/import/proposer'):imports=web._dossier_imports()
        with web.app.test_request_context('/archives'):
            c=connect(path);a=p.archiver_fec(c,2026,path);c.close()
        emit('sorties_locales',{'pdf_status':pdf.status_code,'pdf_signature':data[:4].decode(errors='replace'),'imports_dans_dossier':Path(imports).parent==Path(path).parent,'fichiers_ecrits':sorted(set(created)),'appels_reseau':network})
    manifest=Path(a['manifeste']);source=manifest.read_text();manifest.write_text(source.replace(';2026;',';illisible;'))
    malformed=error(lambda:p.verifier_archives(path));manifest.write_text(source)
    file=Path(a['chemin']);file.write_text('Document fictif remplace');manifest.write_text(source.replace(a['sha256'],p._sha256(str(file))))
    emit('manifeste_modifiable',{'exercice_illisible':malformed,'fec_et_hash_remplaces':p.verifier_archives(path)})
    reg=root/'registre-double';reg.mkdir();path=new(reg,'commun');rel=os.path.relpath(path,reg)
    d._enregistrer(str(reg),[{'slug':k,'nom':k,'chemin':rel} for k in ('alpha','beta')])
    emit('registre_double_injecte',{'meme_base':d.chemin_db(str(reg),'alpha')==d.chemin_db(str(reg),'beta')})
    OUT['sources']={str(x.relative_to(SRC)):digest(x) for x in [SRC/'app.py',*(SRC/'modules'/f'{n}.py' for n in ('perennite','dossiers','migrations','init_db'))]}
    # Remplacer seulement la racine temporaire, aucune donnée privée n'est chargée.
    (Path(__file__).parent/'resultats.json').write_text(json.dumps(OUT,ensure_ascii=False,indent=2).replace(tmp,'<TEMP_FICTIF>')+'\n')
