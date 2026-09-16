"""Passe G : données fictives, base blanche, aucune lecture du dossier privé."""
import hashlib
import io
import json
import math
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlparse, parse_qs

ROOT=Path(__file__).resolve().parents[2]
SRC=ROOT/'compta_lmnp'
sys.path[:0]=[str(SRC/'modules'),str(SRC)]
import init_db, ecritures, operations, export_fec, fec_io, valider_fec
import rejeu_fec, reprise, fiscal, cession, amortissement, controles, migrations, perennite
import gabarits, quittances

WORK=tempfile.TemporaryDirectory(prefix='audit-g-')
TMP=Path(WORK.name)
OUT={}
SEQ=0
COLS=['JournalCode','JournalLib','EcritureNum','EcritureDate','CompteNum','CompteLib',
      'CompAuxNum','CompAuxLib','PieceRef','PieceDate','EcritureLib','Debit','Credit',
      'EcritureLet','DateLet','ValidDate','Montantdevise','Idevise']

def emit(name,value):
    OUT[name]=value
    print(name,json.dumps(value,ensure_ascii=False),flush=True)

def new():
    global SEQ
    SEQ+=1;p=TMP/f'base-{SEQ}.db'
    c=init_db.init_blanc(str(p),2026)
    c.execute("INSERT INTO exploitant VALUES (1,'Exploitant fictif','000000000','Adresse fictive')")
    c.execute("INSERT INTO bien(id,exploitant_id,libelle,prix_total) VALUES (1,1,'Bien fictif',12000)")
    c.commit();return c,p

def counts(c):
    return {t:c.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0] for t in ('ecriture','ligne','operation')}

def totals(c):
    return list(c.execute('SELECT ROUND(COALESCE(SUM(debit),0),2),ROUND(COALESCE(SUM(credit),0),2) FROM ligne').fetchone())

def rent(c,amount=800,date='2026-01-10',**kw):
    return operations.saisir(c,type='loyer',montant=amount,date_operation=date,periode=date[:7],**kw)

def insert(c,lines,**kw):
    return ecritures.inserer(c,journal='BQ',date='2026-01-10',annee=2026,libelle='Fait fictif',piece_ref='P-1',lignes=lines,**kw)

def row(num='1',journal='BQ',account='108000',debit='800',credit='',date='20260110',**kw):
    d={k:'' for k in COLS}
    d.update(JournalCode=journal,JournalLib='Journal fictif',EcritureNum=str(num),EcritureDate=date,
             CompteNum=account,CompteLib='Compte fictif',PieceRef='P-1',PieceDate=date,
             EcritureLib='Loyer fictif',Debit=debit,Credit=credit,ValidDate=date)
    d.update(kw);return d

def pair(num='1',journal='BQ',amount='800',date='20260110'):
    return [row(num,journal,debit=amount,date=date),row(num,journal,account='708810',debit='',credit=amount,date=date)]

def fec(name,rows,header=COLS,separator='\t',encoding='utf-8',ending='\r\n'):
    p=TMP/name
    lines=[separator.join(header)]
    lines += [separator.join(r.get(k,'') for k in header) if isinstance(r,dict) else separator.join(r) for r in rows]
    p.write_bytes((ending.join(lines)+ending).encode(encoding));return p

def export(c,name='export.txt'):
    p=TMP/name;export_fec.exporter(c,2026,str(p));return p

def verdict(p):return valider_fec.valider(str(p),comme_dict=True)

def replay(c,p,year=2026):
    try:return {'retour':rejeu_fec.rejouer(c,str(p),year)}
    except Exception as e:return {'erreur':type(e).__name__+': '+str(e)}

def baseline():
    c,p=new();rent(c,800.25);rent(c,100,date='2026-02-10');fiscal.cloturer(c,2026,generer_dotation=False)
    f=export(c);raw=f.read_bytes();header,rs=fec_io.lire_brut(str(f))
    emit('export_normal',dict(entete=header,entete_attendue=header==COLS,champs=[len(r) for r in rs],
        bom=raw.startswith(b'\xef\xbb\xbf'),crlf=raw.count(b'\r\n'),lf_isole=raw.replace(b'\r\n',b'').count(b'\n'),
        fin_crlf=raw.endswith(b'\r\n'),montants=[[r[11],r[12]] for r in rs],valid_dates=[r[15] for r in rs],
        facultatifs_vides=all(not r[i] for r in rs for i in (6,7,13,14,16,17)),validation=verdict(f)))
    c.close()

def balances_and_values():
    cases={
        'desequilibre':[('108000',800,0),('708810',0,799)],
        'negatif':[('108000',-800,0),('708810',0,-800)],
        'nul':[('108000',0,0),('708810',0,0)],
        'nan':[('108000',float('nan'),0),('708810',0,800)],
        'inf':[('108000',float('inf'),0),('708810',0,float('inf'))],
        'arrondi':[('108000',100.004,0),('108000',100.004,0),('708810',0,200.008)],
        'vide':[],
        'compte_inconnu':[('108000',800,0),('799999',0,800)],
    }
    all_results={}
    for name,lines in cases.items():
        c,p=new();trace=[];c.set_trace_callback(trace.append)
        try:r={'retour':insert(c,lines)}
        except Exception as e:r={'erreur':str(e)}
        r['insert_entete_tente']=any('INSERT INTO ecriture' in s for s in trace)
        c.commit();r.update(counts(c));r['totaux']=totals(c);r['validation']=verdict(export(c,name+'.txt'))
        all_results[name]=r;c.close()
    emit('guichet_valeurs',all_results)
    results={}
    for name,x in [('negatif',-1),('zero',0),('nan',float('nan')),('inf',float('inf'))]:
        c,p=new()
        try:rent(c,x);r={'retour':'succès'}
        except Exception as e:r={'erreur':str(e)}
        c.commit();r.update(counts(c));results[name]=r;c.close()
    emit('operations_valeurs',results)

def validator_cases():
    variants={}
    for x in ('NaN','inf','1e309','1e3'):
        rs=pair();rs[0]['Debit']=x;rs[1]['Credit']='999';variants['montant_'+x]=rs
    for x in ('inf','1e309','1e3'):
        variants['deux_montants_'+x]=pair(amount=x)
    rs=pair(date='20260230');variants['date_impossible']=rs
    rs=pair();rs[0]['CompteNum']='4AB';variants['compte_non_pcg']=rs
    rs=pair();rs[0].update(Montantdevise='BOGUS',Idevise='USD');variants['devise_non_numerique']=rs
    rs=pair();rs[0]['PieceDate']='';variants['piece_date_vide']=rs
    rs=pair();rs[0]['ValidDate']='';variants['valid_date_vide']=rs
    variants['entete_seule']=[]
    emit('validateur_mutations',{name:verdict(fec(name+'.txt',rs)) for name,rs in variants.items()})
    emit('nom_date_impossible',valider_fec.valider_nom_fichier('000000000FEC20260230.txt'))

def journals():
    rs=[row(journal='AC',debit='800'),row(journal='BQ',account='708810',debit='',credit='800')]
    f=fec('journaux-desequilibres.txt',rs);c,p=new();r=replay(c,f);r.update(counts(c));c.close()
    emit('equilibre_par_journal',dict(validation=verdict(f),rejeu=r))
    rs=pair(1,'AC')+pair(3,'AC')+pair(1,'BQ')+pair(2,'BQ')
    emit('trou_par_journal',verdict(fec('trou-journal.txt',rs)))
    rs=pair(10,'AC')+pair(11,'AC')+pair(20,'BQ')+pair(21,'BQ')
    f=fec('sequences-journaux.txt',rs);c,p=new();r=replay(c,f);r['nums']=[x[0] for x in c.execute('SELECT ecriture_num FROM ecriture')];c.close()
    emit('sequences_distinctes',dict(validation=verdict(f),rejeu=r))
    rs=pair('BQ0001')+pair('BQ0002');f=fec('numeros-alpha.txt',rs);c,p=new();r=replay(c,f);r.update(counts(c));c.close()
    emit('numeros_alphanumeriques',dict(validation=verdict(f),rejeu=r))
    rs=pair(1,'AC')+pair(1,'BQ');f=fec('numeros-par-journal.txt',rs);c,p=new();r=replay(c,f);r['ecritures']=[list(x) for x in c.execute('SELECT journal_code,ecriture_num FROM ecriture ORDER BY id')];c.close()
    emit('rejeu_journaux_correct',dict(validation=verdict(f),rejeu=r))

def malformed():
    good=pair();second=pair(2)
    short=[[r[k] for k in COLS[:-2]] for r in second]
    f=fec('lignes-courtes.txt',good+short);c,p=new();r=replay(c,f);r.update(counts(c));r['produits']=c.execute("SELECT SUM(credit-debit) FROM ligne WHERE compte_num='708810'").fetchone()[0];c.close()
    emit('lignes_courtes',dict(lignes_brutes=len(fec_io.lire_brut(str(f))[1]),lignes_nommees=len(fec_io.lignes_nommees(str(f))),balance=reprise.lire_balance_fec(str(f)),validation=verdict(f),rejeu=r))
    for name,header,rs in [('colonne_absente',COLS[:-1],good),('entete_vide',[],good)]:
        f=fec(name+'.txt',rs,header=header);c,p=new();r=replay(c,f);r.update(counts(c));c.close();emit(name,dict(validation=verdict(f),rejeu=r))
    f=TMP/'sans-entete.txt';f.write_bytes(('\r\n'.join('\t'.join(r[k] for k in COLS) for r in good)+'\r\n').encode())
    c,p=new();r=replay(c,f);r.update(counts(c));c.close();emit('entete_absente',dict(validation=verdict(f),rejeu=r))
    rs=pair()+pair(2);rs[2]['EcritureLib']='Libellé\tavec tabulation';rs[3]['EcritureLib']='Libellé\tavec tabulation'
    f=fec('tabulation.txt',rs);c,p=new();r=replay(c,f);c.rollback();r.update(counts(c));c.close();emit('tabulation_import',dict(validation=verdict(f),rejeu=r))
    rs=pair();rs[0]['EcritureLib']='Première ligne\nDeuxième ligne';f=fec('saut-ligne.txt',rs)
    emit('saut_ligne_import',dict(longueurs=[len(r) for r in fec_io.lire_brut(str(f))[1]],validation=verdict(f)))

def variants():
    all_results={}
    for name,opts,rs in [
        ('pipe',{'separator':'|'},pair()),
        ('signe_suffixe',{},pair(amount='800,00-')),
        ('negatifs_normalises',{},pair(amount='-800')),
        ('colonne_supplementaire',{'header':COLS+['Information']},pair()),
        ('guillemets',{},[dict(r,EcritureLib='"Loyer fictif') for r in pair()]),
        ('latin15',{'encoding':'iso-8859-15'},[dict(r,EcritureLib='Loyer fictif 800 €') for r in pair()]),
        ('utf8_bom',{'encoding':'utf-8-sig'},pair()),
        ('cp1252',{'encoding':'cp1252'},[dict(r,EcritureLib='Loyer fictif 800 €') for r in pair()]),
        ('lf',{'ending':'\n'},pair()),
        ('colonnes_permutees',{'header':list(reversed(COLS))},pair()),
    ]:
        f=fec(name+'.txt',rs,**opts);c,p=new();r=replay(c,f);r.update(counts(c));r['libelles']=[x[0] for x in c.execute('SELECT libelle FROM ligne')];c.close()
        all_results[name]=dict(validation=verdict(f),rejeu=r)
    emit('variantes_format',all_results)

def metadata():
    rs=pair()
    rs[0].update(CompteNum='4110000',CompteLib='Locataires')
    rs[1].update(CompteNum='7088100',CompteLib='Loyers')
    for i,r in enumerate(rs):r.update(CompAuxNum='AUX-FICTIF',CompAuxLib='Tiers fictif',PieceDate='20260102',
        ValidDate='20260120',EcritureLet='LET-1',DateLet='20260125',Montantdevise='900' if i==0 else '-900',Idevise='USD')
    f=fec('metadata.txt',rs);c,p=new();r=replay(c,f);out=fec_io.lignes_nommees(str(export(c,'metadata-sortie.txt')))
    changes={k:[rs[0][k],out[0][k]] for k in COLS if rs[0][k]!=out[0][k]}
    emit('metadonnees_rejeu',dict(validation_source=verdict(f),rejeu=r,changements_premiere_ligne=changes,validation_sortie=verdict(TMP/'metadata-sortie.txt')));c.close()
    rs=pair();rs[1]['EcritureDate']='20250110';f=fec('annee-ligne-divergente.txt',rs);c,p=new();r=replay(c,f);r['dates']=[x[0] for x in c.execute('SELECT ecriture_date FROM ecriture')];c.close()
    emit('annee_interne_ecriture',dict(validation_source=verdict(f),rejeu=r))

def years_and_numbers():
    for name,rs in [('autre_annee',pair(date='20250110')),('plusieurs_exercices',pair()+pair(2,date='20250110'))]:
        f=fec(name+'.txt',rs);c,p=new();r=replay(c,f);c.commit();r.update(counts(c));c.close();emit(name,dict(validation=verdict(f),rejeu=r))
    c,p=new();insert(c,[('108000',800,0),('708810',0,800)],num=1)
    try:insert(c,[('108000',800,0),('708810',0,800)],num=1)
    except Exception as e:collision=str(e)
    c.rollback();insert(c,[('108000',800,0),('708810',0,800)],num=3)
    emit('num_impose',dict(collision=collision,nums=[r[0] for r in c.execute('SELECT ecriture_num FROM ecriture')],validation=verdict(export(c))));c.close()
    c,p=new();rent(c,date='2026-03-10');rent(c,date='2026-01-10');fiscal.cloturer(c,2026,generer_dotation=False)
    f=export(c);rows=fec_io.lignes_nommees(str(f));emit('ordre_validation',dict(nums_dates=[[r['EcritureNum'],r['ValidDate']] for r in rows],validation=verdict(f)));c.close()

def closed_sql_and_export():
    all_results={}
    for action in ('modifier','renumeroter','supprimer','sans_ligne','compte_absent','libelle_null'):
        c,p=new();op=rent(c);fiscal.cloturer(c,2026,generer_dotation=False)
        if action=='modifier':c.execute('UPDATE ligne SET debit=debit*2,credit=credit*2')
        if action=='renumeroter':c.execute('UPDATE ecriture SET ecriture_num=99')
        if action=='supprimer':c.execute('DELETE FROM operation');c.execute('DELETE FROM ecriture')
        if action=='sans_ligne':c.execute('DELETE FROM ligne')
        if action=='compte_absent':
            c.execute('PRAGMA foreign_keys=OFF');c.execute("DELETE FROM compte WHERE numero IN ('108000','708810')")
        if action=='libelle_null':c.execute('UPDATE ligne SET libelle=NULL')
        c.commit();f=export(c)
        all_results[action]=dict(comptes_base=counts(c),totaux=totals(c),resultat_fige=c.execute('SELECT resultat_comptable FROM exercice').fetchone()[0],
            lignes_exportees=len(fec_io.lignes_nommees(str(f))),validation=verdict(f),integrite=c.execute('PRAGMA integrity_check').fetchone()[0])
        c.close()
    emit('sql_clos_export',all_results)

def cancellation_and_group():
    c,p=new();op=rent(c);r=operations.annuler(c,op['operation_id'])
    before=[list(x) for x in c.execute('SELECT journal_code,ecriture_num,ecriture_date,exercice_annee,piece_ref,piece_date,valid_date FROM ecriture ORDER BY id')]
    fiscal.cloturer(c,2026,generer_dotation=False)
    try:rent(c)
    except Exception as e:closed=str(e)
    emit('annulation',dict(retour=r,ecritures=before,totaux=totals(c),saisie_close=closed,validation=verdict(export(c))));c.close()
    c,p=new();op=rent(c);fiscal.cloturer(c,2026,generer_dotation=False)
    try:operations.annuler(c,op['operation_id'])
    except Exception as e:closed=str(e)
    emit('annulation_close',dict(erreur=closed,comptages=counts(c)));c.close()
    c,p=new()
    for _ in range(6):rent(c,commit=False)
    try:rent(c,float('nan'),commit=False)
    except ValueError:c.rollback()
    emit('groupe_rollback',dict(comptages=counts(c),prochain=ecritures.prochain_num(c,2026)));c.close()
    c,p=new();rent(c,commit=False);quittances.lister(c);c.rollback()
    emit('recoupement_Q01',counts(c));c.close()

def accounts():
    nums=['1640000','2110000','2818400','3010000','3910000','4010000','4090000','4110000','4190000','4210000','4250000','4310000','4410000','4510000','4610000','4710000','4810000','4910000','5120000','5910000','6152000','6811000','7088100','7910000']
    rs=[]
    for i,n in enumerate(nums,1):rs.extend([row(i,account=n,debit='800'),row(i,account='1080000',debit='',credit='800')])
    f=fec('comptes7.txt',rs);c,p=new();r=replay(c,f)
    emit('comptes_sept_chiffres',dict(rejeu=r,totaux=totals(c),comptes=[list(x) for x in c.execute("SELECT numero,type,classe FROM compte WHERE length(numero)=7 ORDER BY numero")],validation=verdict(export(c))));c.close()

def cession_values():
    out={}
    for name,price in [('negatif',-1),('zero',0),('nan',float('nan')),('inf',float('inf')),('normal',15000)]:
        c,p=new();c.execute("INSERT INTO composant(bien_id,libelle,valeur_brute,duree_annees,date_mise_service,compte_immo,compte_amort) VALUES (1,'Mobilier fictif',12000,10,'2026-01-01','218400','281840')");c.commit()
        try:
            result=cession.ceder_bien(c,1,'2026-06-30',price)
            r={'retour':{k:str(v) if isinstance(v,float) and not math.isfinite(v) else v for k,v in result.items()}}
        except Exception as e:r={'erreur':str(e)}
        r['avant_fermeture']=counts(c);c.close();c=sqlite3.connect(p)
        r['durable']=counts(c);r['date_cession']=c.execute('SELECT date_cession FROM bien').fetchone()[0]
        r['totaux']=totals(c);r['validation']=verdict(export(c));c.close();out[name]=r
    emit('cession_valeurs',out)

def an_and_rounding():
    rs=[row(account='5120000',debit='800'),row(account='7088100',debit='',credit='800')]
    f=fec('an-source.txt',rs);c,p=new();reprise.construire_an(c,str(f),2026)
    emit('an_banque',dict(totaux=totals(c),soldes=[list(x) for x in c.execute('SELECT compte_num,SUM(debit-credit) FROM ligne GROUP BY compte_num')],validation=verdict(export(c))));c.close()
    c,p=new()
    try:reprise._construire_an_depuis_balance(c,{'5120000':800,'7088100':-799},2026)
    except Exception as e:r={'erreur':str(e)}
    c.close();c=sqlite3.connect(p);r['durable']=counts(c);c.close();emit('an_desequilibre',r)
    rows=[]
    for price,share in [(100000.01,None),(100000.01,0.73117),(0.05,None)]:
        result=amortissement.ventilation_proposee(price,share)
        diffs=[dict(cle=x['cle'],compte=x['compte_immo'],avant=round(price*x['part'],2),apres=x['montant']) for x in result if round(price*x['part'],2)!=x['montant']]
        rows.append(dict(prix=price,quote_part=share,total=round(sum(x['montant'] for x in result),2),ajustements=diffs))
    emit('absorption_arrondis',rows)

def metadata_preserved_schema_migration():
    c,p=new();rent(c);fiscal.cloturer(c,2026,generer_dotation=False)
    before=export(c,'avant-migration.txt').read_bytes();c.execute("UPDATE meta SET valeur='2' WHERE cle='version_schema'");c.commit();c.close()
    migrations.migrer(str(p));c=sqlite3.connect(p);after=export(c,'apres-migration.txt').read_bytes()
    emit('migration_fec_inchange',dict(identique=before==after,version=init_db.version_base(c)));c.close()

def web_and_cli():
    import app as web
    rs=pair('1',date='20250110')+[[r[k] for k in COLS[:-2]] for r in pair('2',date='20250120')]
    f=fec('court-web.txt',rs);c,p=new();c.close();stage=TMP/'import-web';stage.mkdir()
    with patch.object(web,'_db_path',return_value=str(p)),patch.object(web,'_dossier_imports',return_value=str(stage)),web.app.test_request_context('/',method='POST',data={'annee':'2025','fec':(io.BytesIO(f.read_bytes()),'fec-fictif.txt')}):
        response=web.exercice_reprendre_fec()
    c=sqlite3.connect(p);emit('rejeu_web_lignes_courtes',dict(reponse=parse_qs(urlparse(response.location).query),comptages=counts(c),produits=c.execute("SELECT SUM(credit-debit) FROM ligne WHERE compte_num='708810'").fetchone()[0]));c.close()
    c,p=new();c.execute("INSERT INTO composant(bien_id,libelle,valeur_brute,duree_annees,date_mise_service,compte_immo,compte_amort) VALUES (1,'Mobilier fictif',12000,10,'2026-01-01','218400','281840')");c.commit();c.close()
    with patch.object(web,'_db_path',return_value=str(p)),web.app.test_request_context('/',method='POST',data={'annee':'2026','date_cession':'2026-06-30','prix_cession':'nan'}):
        response=web.bien_ceder(1)
    c=sqlite3.connect(p);emit('cession_web_nan',dict(reponse=parse_qs(urlparse(response.location).query),comptages=counts(c),date_cession=c.execute('SELECT date_cession FROM bien').fetchone()[0]));c.close()
    rs=pair();rs[1]['Credit']='799';f=fec('invalide-cli.txt',rs)
    child=subprocess.run([sys.executable,str(SRC/'modules/valider_fec.py'),str(f)],capture_output=True,text=True,timeout=10)
    emit('validateur_cli',dict(code_retour=child.returncode,sortie=child.stdout.replace(str(TMP),'DOSSIER_FICTIF'),stderr=child.stderr))

def all_templates():
    c,p=new();gabarits.ajouter_personnalise(c,cle='personnalise_fictif',libelle='Charge fictive',compte_num='614100',nature='charge')
    results=[]
    for name in gabarits.tous(c):
        for _ in range(2):operations.saisir(c,type=name,montant=800,date_operation='2026-01-10',commit=False)
        active=c.in_transaction;c.rollback();results.append(dict(type=name,transaction_avant_rollback=active,comptages=counts(c)))
    emit('tous_gabarits_rollback',results);c.close()

def balance_short_and_closed_restore():
    rs=pair()+[[r[k] for k in COLS[:11]] for r in pair(2)]
    f=fec('balance-courte.txt',rs);emit('balance_filtre_court',dict(lignes_brutes=len(fec_io.lire_brut(str(f))[1]),balance=reprise.lire_balance_fec(str(f))))
    c,p=new();rent(c);c.close();sv=perennite.sauvegarder(str(p),'fictif-avant-cloture')
    c=sqlite3.connect(p);fiscal.cloturer(c,2026,generer_dotation=False);c.close();surete=perennite.restaurer(str(p),sv)
    c=sqlite3.connect(p);s=sqlite3.connect(surete)
    emit('restauration_cloture',dict(apres_restauration=c.execute('SELECT statut FROM exercice').fetchone()[0],statut_copie_surete=s.execute('SELECT statut FROM exercice').fetchone()[0],comptages=counts(c)));c.close();s.close()

if __name__=='__main__':
    emit('environnement',dict(python=sys.version.split()[0],sqlite=sqlite3.sqlite_version,
        sha256={str(p.relative_to(SRC)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [SRC/'schema.sql']+sorted((SRC/'modules').glob('*.py'))}))
    for fn in (baseline,balances_and_values,validator_cases,journals,malformed,variants,metadata,years_and_numbers,closed_sql_and_export,cancellation_and_group,accounts,cession_values,an_and_rounding,metadata_preserved_schema_migration,web_and_cli,all_templates,balance_short_and_closed_restore):
        try:fn()
        except Exception as e:emit('HARNESS_ERROR_'+fn.__name__,repr(e))
    (Path(__file__).parent/'resultats.json').write_text(json.dumps(OUT,ensure_ascii=False,indent=2)+'\n')
    if any(k.startswith('HARNESS_ERROR_') for k in OUT):sys.exit(1)
