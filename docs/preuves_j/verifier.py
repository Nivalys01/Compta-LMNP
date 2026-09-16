"""Vérifications des sorties d'exécution de la version auditée, défauts compris."""
import json,hashlib
from pathlib import Path
P=Path(__file__).resolve().parent
j=json.loads((P/'resultats.json').read_text());n=0
def eq(a,b):
    global n
    assert a==b,(a,b)
    n+=1
def close(k):return j[k]['cloture']
def aide(k):return j[k]['etat']['aide']
eq(len(j),50)
for y in (2024,2025):
    eq(close('pivot_'+str(y))['deficits']['impute_sur_benefice'],300)
    eq(j['pivot_'+str(y)]['etat']['lignes'][0]['solde'],500)
eq(close('pivot_2026')['deficits']['perimes'],1)
eq(close('pivot_2026')['revenu_imposable'],300)
eq([x['solde'] for x in j['fifo_2000']['etat']['lignes']],[0,1000,3000])
eq(close('fifo_7000')['revenu_imposable'],1000)
eq(close('fifo_centimes')['revenu_imposable'],.01)
eq(close('fifo_centimes')['deficits']['impute_sur_benefice'],.03)
eq(j['trace_peremption']['avant']['reports']['total_deficits'],800)
eq(j['trace_peremption']['avant']['reports']['total_deficits_perimes'],1200)
eq(j['trace_peremption']['apres']['reports']['total_deficits'],800)
eq(j['trace_peremption']['apres']['reports']['total_deficits_perimes'],0)
eq(len(j['trace_peremption']['apres']['lignes']),2)
eq(j['trace_peremption']['apres']['lignes'][0]['solde'],0)
eq('périmé' in (P/'peremption_avant.txt').read_text(),True)
eq('périmé' in (P/'peremption_apres.txt').read_text(),False)
eq(aide('restitution_500')['cases_deficits_anterieurs'][0]['montant'],1000)
eq(aide('restitution_1000')['case_5NA'],1000)
eq(aide('restitution_1000')['cases_deficits_anterieurs'],[])
eq(close('restitution_1000')['revenu_imposable'],0)
eq('5GJ' in (P/'deficit_epuise.txt').read_text(),False)
eq(aide('restitution_mauvais_millesime')['cases_deficits_anterieurs'],[{'case':'5GJ','annee_origine':2024,'montant':1500}])
eq(j['ancienne_declaration']['avant']['aide']['cases_deficits_anterieurs'][0]['montant'],3000)
eq(j['ancienne_declaration']['apres']['aide']['cases_deficits_anterieurs'],[])
eq(j['ancienne_declaration']['apres']['conforme'],True)
eq(j['deficit_futur_dans_ancien_suivi']['reports']['deficits'][0]['annee_origine'],2027)
eq(j['deficit_futur_dans_ancien_suivi']['reports']['total_deficits'],700)
eq(aide('cases_dix_millesimes')['cases_deficits_anterieurs'],[dict(case=c,annee_origine=2015+i,montant=(i+1)*100) for i,c in enumerate(['5GA','5GB','5GC','5GD','5GE','5GF','5GG','5GH','5GI','5GJ'])])
for case,rf,stock in [('ordinaire',-300,0),('amortissement',0,200),('mixte',-300,1200),('alur',-300,0)]:
    eq(close('creation_'+case)['resultat_fiscal'],rf)
    eq(close('creation_'+case)['suivi_39c']['stock_cloture'],stock)
    eq(j['creation_'+case]['etat']['f2033b']['resultat_fiscal_352'],0)
    eq(j['creation_'+case]['etat']['f2033b']['resultat_fiscal_370'],0)
eq('erreur' in j['double_cloture']['seconde'],True)
eq(len(j['double_cloture']['lignes']),1)
eq(j['restauration_recloture']['apres_restauration'],[])
eq(len(j['restauration_recloture']['lignes']),1)
eq(sum('retour' in x for x in j['clotures_concurrentes']['retours']),1)
eq(len(j['clotures_concurrentes']['lignes']),1)
eq(len(j['double_appel_isole']),2)
eq(j['cloture_interrompue']['lignes'][0]['solde'],1000)
eq(j['cloture_interrompue']['statut'],'ouvert')
eq(j['cloture_interrompue']['suivi'],0)
eq(j['moteur_commit_false'],{'transaction':True,'lignes':[],'temoins':0})
eq(j['seuil_lmp_import_False']['controles_avant'],['SEUIL_LMP'])
eq(j['seuil_lmp_import_True']['controles_avant'],[])
eq(j['seuil_lmp_import_True']['operations'],0)
eq(close('seuil_lmp_import_True')['deficits']['deficit_cree'],5000)
eq([x['annee_expiration'] for x in j['parametre_versionne']],[2035,2038])
for case,imposable in [('normal',500),('dotation7',1500),('honoraires6',500),('honoraires7',0)]:
    eq(j['dix_ans_'+case]['apres_dix_ans']['revenu_imposable'],imposable)
for sens,cle in [('benefice','case_5NA'),('deficit','case_5NY')]:
    for value,result in [('100.49',100),('100.5',100),('100.51',101),('101.5',102),('0.5',0)]:
        eq(j['arrondi_'+sens+'_'+value]['aide'][cle],result)
eq(j['arrondi_anterieur_0.5']['aide']['cases_deficits_anterieurs'],[])
eq(j['arrondi_anterieur_100.5']['aide']['cases_deficits_anterieurs'][0]['montant'],100)
for f,h in j['environnement']['sha256'].items():
    eq(hashlib.sha256((P.parents[1]/'compta_lmnp'/f).read_bytes()).hexdigest(),h)
print(f'{n} vérifications réussies sur 50 groupes exécutés, dont 15 cas d’arrondi.')
