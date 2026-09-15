"""Audit P : données entièrement fictives, aucun accès aux sources privées."""
import sys, sqlite3, tempfile, json, hashlib, shutil, importlib.util, threading, subprocess
from pathlib import Path
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import unquote
ROOT=Path(__file__).resolve().parents[2]
SRC=ROOT/'compta_lmnp_v8.41.0/compta_lmnp'
sys.path[:0]=[str(SRC/'modules'),str(SRC)]
import init_db, operations as op, quittances as q, perennite as p, fiscal, export_fec, liasse, liasse_pdf, controles
import app as web
OUT={}; ART=Path(__file__).parent
def emit(k,v): OUT[k]=v; print(k,json.dumps(v,ensure_ascii=False,default=str),flush=True)
def attempt(fn):
    try:return {'retour':fn()}
    except Exception as e:return {'erreur':type(e).__name__+': '+str(e)}
def new(root,name):
    folder=root/name;folder.mkdir();path=folder/'compta.db'
    c=init_db.init_blanc(str(path),2026)
    c.execute("INSERT INTO exploitant VALUES(1,'Bailleur Alpha Fictif','000000000','Adresse bailleur fictive')")
    c.execute("INSERT INTO bien(id,exploitant_id,libelle,adresse,prix_total) VALUES(1,1,'Logement Alpha Fictif','Adresse logement fictive',120000)")
    c.commit();return c,path
def loc(c,nom='Locataire Alpha Fictif',entree='2026-01-01',sortie=None,charges=80):
    return q.ajouter_locataire(c,bien_id=1,nom=nom,date_entree=entree,date_sortie=sortie,loyer_mensuel=800,charges_mensuelles=charges)
def rent(c,amount=800,period='2026-01',typ='loyer',**kw):
    return op.saisir(c,type=typ,montant=amount,date_operation=period+'-10',periode=period,**kw)
def html(path,id):
    with patch.object(web,'DB',str(path)),patch.object(web,'HERE',str(path.parent)):
        r=web.app.test_client().get('/quittance/'+str(id));assert r.status_code==200;return r.get_data(as_text=True)
def count(c):return c.execute('SELECT count(*) FROM quittance').fetchone()[0]
with tempfile.TemporaryDirectory(prefix='audit-p-') as tmp:
    root=Path(tmp)
    c,path=new(root,'impaye');lid=loc(c)
    auto=attempt(lambda:q.emettre(c,locataire_id=lid,periode='2026-01'))
    with patch.object(web,'DB',str(path)),patch.object(web,'HERE',str(path.parent)):
        r=web.app.test_client().post('/quittances/emettre',data={'locataire_id':lid,'periode':'2026-01','loyer':'800','charges':'80'})
    h=html(path,1);ART.joinpath('impaye.html').write_text(h)
    emit('impaye',dict(auto=auto,http=r.status_code,message=unquote(r.location),operations=c.execute('select count(*) from operation').fetchone()[0],quittance=q.detail(c,1),attestation='déclare avoir reçu' in h))
    c.close()
    c,path=new(root,'ventilation');lid=loc(c);rent(c);rent(c,80,typ='charges_locatives')
    r=q.emettre(c,locataire_id=lid,periode='2026-01',loyer=880,charges=0)
    emit('ventilation',dict(encaisse=q.montants_depuis_ecritures(c,1,'2026-01'),quittance=r,alerte=q.detail(c,r['id'])['ecart_ecritures']))
    c.close()
    c,path=new(root,'partiel');lid=loc(c,charges=0);rent(c,400)
    r=q.emettre(c,locataire_id=lid,periode='2026-01');h=html(path,r['id']);ART.joinpath('partiel.html').write_text(h)
    second=rent(c,400)
    emit('partiel',dict(premiere=r,titre_quittance='<h1>Quittance de loyer</h1>' in h,alerte_apres_solde=q.detail(c,r['id'])['ecart_ecritures'],solde=attempt(lambda:q.emettre(c,locataire_id=lid,periode='2026-01')),total_encaisse=q.montants_depuis_ecritures(c,1,'2026-01')))
    c.close()
    c,path=new(root,'colocation');a=loc(c,charges=0);b=loc(c,'Locataire Beta Fictif',charges=0);rent(c)
    first=q.emettre(c,locataire_id=a,periode='2026-01',loyer=400,charges=0)
    emit('colocation_parts',dict(premiere=first,seconde=attempt(lambda:q.emettre(c,locataire_id=b,periode='2026-01',loyer=400,charges=0)),nombre=count(c)))
    c.close()
    c,path=new(root,'relocation');a=loc(c,sortie='2026-02-14',charges=0);b=loc(c,'Locataire Beta Fictif',entree='2026-02-15',charges=0);rent(c,400,'2026-02',tiers='Locataire Alpha Fictif');op.saisir(c,type='loyer',montant=400,date_operation='2026-02-20',periode='2026-02',tiers='Locataire Beta Fictif')
    first=q.emettre(c,locataire_id=a,periode='2026-02')
    emit('relocation',dict(premiere=first,seconde=attempt(lambda:q.emettre(c,locataire_id=b,periode='2026-02')),presence=[q.present_le(x,'2026-02') for x in q.locataires(c)]))
    c.close()
    c,path=new(root,'annulation');lid=loc(c);r=rent(c);issued=q.emettre(c,locataire_id=lid,periode='2026-01');op.annuler(c,r['operation_id'])
    h=html(path,issued['id']);ART.joinpath('apres_annulation.html').write_text(h)
    emit('annulation',dict(nombre=count(c),detail=q.detail(c,issued['id']),avertissement_html='Cette quittance ne correspond plus' in h))
    c.close()
    c,path=new(root,'restauration');lid=loc(c)
    for m in range(1,5):rent(c,800,f'2026-{m:02}')
    q.emettre(c,locataire_id=lid,periode='2026-01');sv=p.sauvegarder(str(path),'avant-deux')
    for m in [2,3]:q.emettre(c,locataire_id=lid,periode=f'2026-{m:02}')
    before=hashlib.sha256(path.read_bytes()).hexdigest();c.close()
    with patch.object(web,'DB',str(path)),patch.object(web,'HERE',str(path.parent)):
        r=web.app.test_client().post('/sauvegardes/restaurer',data={'nom':Path(sv).name},follow_redirects=True)
    c=sqlite3.connect(path);fourth=q.emettre(c,locataire_id=lid,periode='2026-04')
    emit('restauration_normale',dict(http=r.status_code,refus_visible='Restauration refusée' in r.get_data(as_text=True),compte_juste='2 quittance(s)' in r.get_data(as_text=True),nouvelle=fourth,numeros=[x[0] for x in c.execute('select numero from quittance order by numero')]))
    # Altération SQL explicite : aucun bouton de suppression n'est supposé.
    c.execute('delete from quittance where numero=4');c.commit()
    replay=q.emettre(c,locataire_id=lid,periode='2026-05',loyer=500,charges=0)
    emit('suppression_sql',dict(numero_reutilise=replay['numero'],ancien_total=fourth['total'],nouveau_total=replay['total']))
    c.close()
    c,path=new(root,'compteur-illisible');lid=loc(c)
    for m in [1,2,3]:rent(c,800,f'2026-{m:02}')
    q.emettre(c,locataire_id=lid,periode='2026-01');sv=p.sauvegarder(str(path),'avant-deux')
    for m in [2,3]:q.emettre(c,locataire_id=lid,periode=f'2026-{m:02}')
    # Catalogue altéré : la garde de lecture ne peut plus travailler.
    c.execute('alter table quittance rename column numero to numero_endommage');c.commit();c.close()
    result=attempt(lambda:p.restaurer(str(path),sv));c=sqlite3.connect(path)
    replay=q.emettre(c,locataire_id=lid,periode='2026-03')
    emit('compteur_illisible',dict(restauration=result,nouvelle=replay,nombre=count(c)));c.close()
    c,path=new(root,'identite');lid=loc(c);rent(c);r=q.emettre(c,locataire_id=lid,periode='2026-01');before=q.detail(c,r['id']);sv=p.sauvegarder(str(path),'identite-initiale')
    c.execute("update locataire set nom='Locataire Beta Fictif' where id=?",(lid,));c.execute("update bien set adresse='Autre adresse fictive' where id=1");c.commit()
    changed=q.detail(c,r['id']);h=html(path,r['id']);c.close();p.restaurer(str(path),sv);c=sqlite3.connect(path)
    emit('identite_non_figee',dict(avant=before['locataire'],apres=changed['locataire'],adresse=changed['bien_adresse'],numero=changed['numero'],html_beta='Locataire Beta Fictif' in h,apres_restauration=q.detail(c,r['id'])['locataire']));c.close()
    c,path=new(root,'mentions');lid=loc(c,'Alpha & <script>alert(1)</script> Fictif');rent(c)
    c.execute("update bien set adresse='' where id=1");c.execute("update exploitant set adresse='' where id=1");c.commit()
    fiscal.cloturer(c,2026);before=[tuple(x) for x in c.execute('select * from ecriture')];r=q.emettre(c,locataire_id=lid,periode='2026-01');h=html(path,r['id']);ART.joinpath('mentions.html').write_text(h)
    emit('mentions_clos',dict(date_paiement=q.detail(c,r['id'])['date_paiement'],mention_paiement='Paiement reçu le' in h,libelle_utilise='Logement Alpha Fictif' in h,echappe='&lt;script&gt;' in h and '&amp;' in h,injection='<script>alert(1)</script>' in h,siren='000000000' in h,ecritures_identiques=before==[tuple(x) for x in c.execute('select * from ecriture')],statut=c.execute('select statut from exercice').fetchone()[0]));c.close()
    c,path=new(root,'transaction');rent(c,800,commit=False);before=c.in_transaction;q.assurer_schema(c);after=c.in_transaction;c.rollback()
    emit('recoupement_q01',dict(transaction_avant=before,transaction_apres=after,operations_apres_rollback=c.execute('select count(*) from operation').fetchone()[0]));c.close()
    c,path=new(root,'concurrence');a=loc(c);b=loc(c,'Locataire Beta Fictif');rent(c);c.close()
    original=q.prochain_numero;barrier=threading.Barrier(2)
    def same_number(conn):
        n=original(conn);barrier.wait(timeout=10);return n
    def worker(lid):
        con=sqlite3.connect(path)
        try:return attempt(lambda:q.emettre(con,locataire_id=lid,periode='2026-01'))
        finally:con.close()
    with patch.object(q,'prochain_numero',same_number),ThreadPoolExecutor(2) as pool:results=list(pool.map(worker,[a,b]))
    c=sqlite3.connect(path);emit('recoupement_q04_collision',dict(retours=results,nombre=count(c),operations=c.execute('select count(*) from operation').fetchone()[0]));c.close()
    # Données personnelles synthétiques : table seule, puis libellé comptable.
    c,path=new(root,'donnees');lid=loc(c,'Locataire Traceur Fictif');rent(c);r=q.emettre(c,locataire_id=lid,periode='2026-01')
    fec=path.parent/'export.txt';export_fec.exporter(c,2026,str(fec));fec_table='Locataire Traceur Fictif' in fec.read_text()
    sv=p.sauvegarder(str(path),'donnees');sc=sqlite3.connect(sv);backup=sc.execute('select nom from locataire').fetchone()[0];sc.close()
    before=set(path.parent.rglob('*'));html(path,r['id']);after=set(path.parent.rglob('*'))
    rent(c,800,'2026-02',libelle='Loyer Locataire Traceur Fictif');export_fec.exporter(c,2026,str(fec))
    pdf=path.parent/'liasse.pdf';liasse_pdf.generer_pdf(liasse.generer(c,2026),str(pdf));pdftext=subprocess.check_output(['pdftotext',str(pdf),'-'],text=True)
    with patch.object(web,'DB',str(path)),patch.object(web,'HERE',str(path.parent)):
        client=web.app.test_client();page=client.get('/quittances').get_data(as_text=True)
        with web.app.test_request_context('/quittance/1'):
            handlers=set(web.app.logger.handlers);web._journal_erreurs()
            try:
                try:raise RuntimeError('Incident Locataire Traceur Fictif')
                except RuntimeError as exc:web._erreur_globale(exc)
            finally:
                for handler in set(web.app.logger.handlers)-handlers:web.app.logger.removeHandler(handler);handler.close()
    journal=(path.parent/'logs/erreurs.log').read_text()
    emit('donnees',dict(nom_table_dans_fec=fec_table,nom_libelle_dans_fec='Locataire Traceur Fictif' in fec.read_text(),nom_dans_sauvegarde=backup,nouveaux_fichiers_impression=[x.name for x in after-before],nom_dans_pdf_liasse='Locataire Traceur Fictif' in pdftext,nom_dans_erreur= 'Locataire Traceur Fictif' in journal,fevrier_non_quittance_visible='2026-02' in page));c.close()
    # Importer l'outil uniquement depuis une copie à HERE fictif : ses constantes
    # sont évaluées à l'import, donc ne jamais importer l'original directement.
    sandbox=root/'outil';sandbox.mkdir();(sandbox/'reference').mkdir();(sandbox/'demo').mkdir()
    for name in ['outils_demo.py','verifier_depot.py']:shutil.copyfile(SRC/name,sandbox/name)
    seed="INSERT INTO exploitant(id,nom,siren,adresse) VALUES(1,'Bailleur Source Fictif','111111111','Adresse source fictive');\nINSERT INTO bien(id,exploitant_id,libelle,prix_total) VALUES(1,1,'Appartement fictif',120000);\nINSERT INTO locataire(id,bien_id,nom,date_entree) VALUES(1,1,'Locataire Secret Fictif','2026-01-01');\n"
    (sandbox/'seed_exemple.sql').write_text(seed);(sandbox/'reference/termes_a_anonymiser.txt').write_text('TermeAbsentFictif\n')
    # Un FEC valide synthétique pour les prérequis et le rapprochement.
    shutil.copyfile(fec,sandbox/'reference/FEC_REFERENCE_2025.txt');shutil.copyfile(fec,sandbox/'demo/FEC_DEMO_2025.txt')
    sys.path.insert(0,str(sandbox))
    spec=importlib.util.spec_from_file_location('outils_demo_fictif',sandbox/'outils_demo.py');demo=importlib.util.module_from_spec(spec);spec.loader.exec_module(demo)
    result=attempt(demo.construire_seed_demo);output=sandbox/'seed_demo.sql'
    emit('demo_locataire',dict(generation=result,sortie_existe=output.exists(),nom_locataire_conserve=output.exists() and 'Locataire Secret Fictif' in output.read_text(),promesse_absence=output.exists() and 'AUCUNE donnée personnelle' in output.read_text()))
    (sandbox/'reference/termes_a_anonymiser.txt').write_text('Locataire Secret Fictif\n')
    try:demo.construire_seed_demo();known={'retour':'succes'}
    except SystemExit as e:known={'refus':str(e),'fichier_supprime':not output.exists()}
    emit('demo_empreinte_connue',known)
    # Le seed destiné au client est exécuté à part. On ne restitue aucun champ
    # d'identité, uniquement le nombre de lignes des deux tables du périmètre.
    published=sqlite3.connect(':memory:')
    published.executescript((SRC/'schema.sql').read_text())
    published.executescript((SRC/'seed_referentiel.sql').read_text())
    published.execute("INSERT INTO exercice(annee,date_debut,date_fin,statut) VALUES(2025,'2025-01-01','2025-12-31','ouvert')")
    published.executescript((SRC/'seed_demo.sql').read_text())
    emit('seed_client_present',dict(locataires=published.execute('select count(*) from locataire').fetchone()[0],quittances=published.execute('select count(*) from quittance').fetchone()[0]))
    published.close()
    emit('environnement',dict(python=sys.version,sqlite=sqlite3.sqlite_version,sha256={f:hashlib.sha256((SRC/f).read_bytes()).hexdigest() for f in ['modules/quittances.py','modules/operations.py','modules/pages.py','schema.sql','app.py','modules/perennite.py','outils_demo.py','verifier_depot.py']}))
def clean(x):
    if isinstance(x,str):return x.replace(tmp,'<TEMP_FICTIF>')
    if isinstance(x,dict):return {k:clean(v) for k,v in x.items()}
    if isinstance(x,list):return [clean(v) for v in x]
    return x
ART.joinpath('resultats.json').write_text(json.dumps(clean(OUT),indent=2,ensure_ascii=False,default=str)+'\n')
