"""Audit L : bases vierges et données fictives uniquement. Aucun fichier privé lu."""
import datetime, hashlib, json, sqlite3, subprocess, sys, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / 'compta_lmnp_v8.41.0/compta_lmnp'
sys.path[:0] = [str(SRC/'modules'), str(SRC)]
import init_db, cession, fiscal, liasse, liasse_pdf, amortissement, ecritures, reprise, pense_bete, export_fec, rejeu_fec
ART = Path(__file__).parent
TMP = tempfile.TemporaryDirectory(prefix='audit-l-')
OUT = {}; SEQ = 0
def new(y=2026, dms='2026-01-01', cumul=0):
    global SEQ
    SEQ += 1
    c = init_db.init_blanc(str(Path(TMP.name)/f'{SEQ}.db'), y)
    c.row_factory = sqlite3.Row
    c.execute("INSERT INTO exploitant VALUES(1,'Exploitant fictif','000000000','Adresse fictive')")
    c.execute("INSERT INTO bien(id,exploitant_id,libelle,prix_total,date_acquisition) VALUES(1,1,'Bien fictif',12000,?)", (dms,))
    c.execute("INSERT INTO composant(bien_id,libelle,valeur_brute,duree_annees,date_mise_service,compte_immo,compte_amort,amortissable) VALUES(1,'Composant fictif',12000,10,?,'213150','281315',1)",(dms,))
    c.commit()
    entry(c,y,[('213150',12000,0),('281315',0,cumul),('108000',0,12000-cumul)] if cumul else [('213150',12000,0),('108000',0,12000)],date=max(f'{y}-01-01',dms))
    return c
def entry(c,y,lines,date=None,piece='FICTIF'):
    return ecritures.inserer(c,journal='OD',date=date or f'{y}-01-01',annee=y,piece_ref=piece,libelle='Écriture fictive',lignes=lines)
def snap(c,y):
    L = liasse.generer(c,y)
    return dict(ag=fiscal.agregats(c,y),b=L['f2033b'],a=L['f2033a'],immo=L['f2033c'],reports=L['reports'],controles=L['controles'],conforme=L['conforme'],soldes=liasse._soldes(c,y),ecritures=[dict(r) for r in c.execute('SELECT ecriture_date,exercice_annee,piece_ref,ROUND(SUM(debit),2) debit,ROUND(SUM(credit),2) credit FROM ecriture JOIN ligne ON ecriture.id=ligne.ecriture_id GROUP BY ecriture.id')])
def attempt(fn):
    try: return {'retour':fn()}
    except Exception as e: return {'erreur':str(e)}
def pdf(c,y,name):
    p=ART/(name+'.pdf');liasse_pdf.generer_pdf(liasse.generer(c,y),str(p))
    t=subprocess.check_output(['pdftotext','-layout',str(p),'-'],text=True)
    (ART/(name+'.txt')).write_text(t)
    return {'fichier':p.name,'notaire': 'notaire' in t.lower(),'2048': '2048' in t,'cadre_III':'III' in t}

# Les deux signes et le prix zéro : dotation déjà passée à la cession.
for prix in (15000,5000,0):
    c=new();entry(c,2026,[('108000',3000,0),('708810',0,3000)])
    r=cession.ceder_bien(c,1,'2026-06-30',prix)
    before=snap(c,2026);cl=fiscal.cloturer(c,2026);after=snap(c,2026)
    OUT[f'prix_{prix}']=dict(cession=r,ouvert=before,cloture=cl,clos=after)
    if prix==15000:
        OUT['pdf']=pdf(c,2026,'cession')
        OUT['rappels']=pense_bete.rappels(c,aujourd_hui=datetime.date(2026,7,1))
        # Contournement SQL explicite, ne représente pas une édition autorisée.
        c.execute("UPDATE ligne SET credit=16000 WHERE compte_num='775000'")
        c.execute("UPDATE ligne SET debit=16000 WHERE libelle='Prix de cession' AND compte_num='108000'")
        c.commit();OUT['mutation_sql_apres_cloture']=snap(c,2026)
    c.close()

# Cycle historique normal, tableaux des mouvements et année suivante.
c=new(2025,'2025-01-01');fiscal.cloturer(c,2025);reprise.ouvrir_exercice(c,2026)
OUT['cycle_avant']=snap(c,2026)
OUT['cycle_cession']=cession.ceder_bien(c,1,'2026-06-30',15000)
fiscal.cloturer(c,2026);OUT['cycle_2026']=snap(c,2026);OUT['cycle_pdf']=pdf(c,2026,'cycle')
reprise.ouvrir_exercice(c,2027);OUT['cycle_dotations_2027']=amortissement.dotations_exercice(c,2027)
fiscal.cloturer(c,2027);OUT['cycle_2027']=snap(c,2027);c.close()

# Cumul comptable repris (un seul composant, aucun problème d'affectation).
c=new(dms='2025-01-01',cumul=3000)
# Export et rejeu réels de l'écriture de reprise fictive dans une autre base.
fec=Path(TMP.name)/'reprise-fictive.txt';export_fec.exporter(c,2026,str(fec));c.close()
c=new(dms='2025-01-01',cumul=3000)
c.execute('DELETE FROM ligne');c.execute('DELETE FROM ecriture');c.commit()
OUT['cumul_rejeu']=rejeu_fec.rejouer(c,str(fec),2026)
OUT['cumul_repris_avant']=snap(c,2026)
OUT['cumul_repris_cession']=cession.ceder_bien(c,1,'2026-06-30',15000)
fiscal.cloturer(c,2026);OUT['cumul_repris_apres']=snap(c,2026);c.close()

# Bornes de date, acquisition après la date saisie et refus sur exercice clos.
for dc in ('2026-01-01','2026-12-31'):
    c=new();OUT[dc]=cession.ceder_bien(c,1,dc,15000)
    fiscal.cloturer(c,2026);OUT[dc+'_etat']=snap(c,2026);c.close()
c=new(dms='2026-07-01');OUT['avant_acquisition']=cession.ceder_bien(c,1,'2026-06-30',15000)
OUT['avant_acquisition_etat']=snap(c,2026);c.close()
c=new();fiscal.cloturer(c,2026);n=c.execute('SELECT COUNT(*) FROM ecriture').fetchone()[0]
OUT['refus_clos']=attempt(lambda:cession.ceder_bien(c,1,'2026-06-30',15000))
OUT['refus_clos']['ecritures_avant_apres']=[n,c.execute('SELECT COUNT(*) FROM ecriture').fetchone()[0]];c.close()
c=new();OUT['sans_comptes']=dict(comptes=[r[0] for r in c.execute("SELECT numero FROM compte WHERE numero IN ('675000','775000')")],ag=fiscal.agregats(c,2026));c.close()
OUT['prorata']={}
for vb,duree,dms,y,dc in [(12000,10,'2026-07-01',2026,'2026-09-30'),(12000,10,'2024-01-01',2024,'2024-02-29'),(12000,1,'2025-07-01',2026,'2026-12-31')]:
    OUT['prorata'][dc+'_'+dms]=cession._dotation_prorata(vb,duree,dms,y,datetime.date.fromisoformat(dc))

# Le calcul de cession n'absorbe pas une dotation déjà passée (extension H-02).
c=new();amortissement.generer_cloture(c,2026)
OUT['dotation_deja_presente']=cession.ceder_bien(c,1,'2026-12-31',15000)
OUT['dotation_deja_presente_etat']=snap(c,2026);c.close()

# Échec réel après la première écriture puis rollback du lot par l'appelant.
c=new();before=c.execute('SELECT COUNT(*) FROM ecriture').fetchone()[0]
c.execute("CREATE TEMP TRIGGER echec_sortie BEFORE INSERT ON ecriture WHEN NEW.piece_ref='CESSION' BEGIN SELECT RAISE(ABORT,'Panne fictive sortie'); END")
OUT['panne']=attempt(lambda:cession.ceder_bien(c,1,'2026-06-30',15000))
OUT['panne']['avant']=before;OUT['panne']['avant_rollback']=c.execute('SELECT COUNT(*) FROM ecriture').fetchone()[0]
c.rollback();OUT['panne']['apres_rollback']=c.execute('SELECT COUNT(*) FROM ecriture').fetchone()[0];c.close()

# Geste partiel SQL explicite : un composant sorti, le logement conservé.
c=new();cession.assurer_schema(c)
c.execute("INSERT INTO composant(bien_id,libelle,valeur_brute,duree_annees,date_mise_service,compte_immo,compte_amort,amortissable) VALUES(1,'Composant conservé fictif',6000,10,'2026-01-01','213150','281315',1)")
c.commit();entry(c,2026,[('213150',6000,0),('108000',0,6000)])
dot,cum=cession._dotation_prorata(12000,10,'2026-01-01',2026,datetime.date(2026,6,30))
entry(c,2026,[('681120',dot,0),('281315',0,dot)],'2026-06-30','DAA-CESSION')
entry(c,2026,[('281315',dot,0),('675000',12000-dot,0),('213150',0,12000)],'2026-06-30')
c.execute("UPDATE composant SET date_sortie='2026-06-30' WHERE id=1");c.commit()
fiscal.cloturer(c,2026);OUT['partiel_sql']=snap(c,2026)
reprise.ouvrir_exercice(c,2027)
OUT['partiel_puis_total']=cession.ceder_bien(c,1,'2027-01-01',6000)
OUT['dates_sortie_preservees']=[dict(r) for r in c.execute('SELECT id,date_sortie FROM composant ORDER BY id')]
c.close()
OUT['sources']={str(p.relative_to(SRC)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [SRC/'modules'/f for f in ('cession.py','fiscal.py','liasse.py','amortissement.py','liasse_pdf.py','pense_bete.py')]+[SRC/'schema.sql']}
(ART/'resultats.json').write_text(json.dumps(OUT,ensure_ascii=False,indent=2,default=str)+'\n')
print('Scénarios terminés :',len(OUT),'groupes ; résultats dans docs/preuves_l/resultats.json')
