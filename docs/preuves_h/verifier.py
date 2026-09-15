"""Vérifie les résultats d'exécution de la passe H, sans lire le code pour conclure."""
import json
from pathlib import Path
r=json.loads(Path(__file__).with_name('resultats.json').read_text())
assert len(r)==48 and not any(k.startswith('ERREUR_') for k in r)
assert r['matrice_plans']=={'cas':21930,'erreurs':[]}
s=r['duree_allongee_partage_True']['exercices']
assert s[-1]['solde']['281840']==-19600 and s[-1]['solde']['218400']==16000
assert s[-1]['etat']['suivi_39c'][0]['stock_cloture']==19600
assert not any(a['code']=='DUREE_ALLONGEE' for a in r['duree_allongee_partage_True']['controles_initiaux'])
s=r['manuel_resultat_fiscal']['cloture']
assert s['revenu_imposable']==0 and s['agregats']['dotation']==2400 and s['suivi_39c']['stock_cloture']==600
assert r['manuel_False']['solde']['281840']==-24000
assert r['an_premier_exercice']['cumul_lu']==0 and r['an_premier_exercice']['solde']['281840']==-9000
assert r['daa_annulee']['etat']['controles']==[] and r['daa_annulee']['solde']['681120']==0
assert 'erreur' in r['daa_annulee']['seconde']
assert any(a['code']=='DOTATION_PLAN' for a in r['manuel_True']['apres']['controles'])
s=r['omission_2026-01-01'];assert s['apres']['controles']==[] and s['apres']['bilan']['amortissements_030']==0 and s['reprise']['retour']['total']==1200
s=r['omission_2026-12-31'];assert s['apres']['tableau']['amort_fin']==3.29 and all(a['ok'] for a in s['apres']['liasse_controles'])
s=r['web_modification_clos'];assert s['avant']['tableau']['amort_fin']==1200 and s['apres']['tableau']['amort_fin']==600 and s['apres']['plans'][0]['dotation']==1200
s=r['raccourcie_fin_plan'];assert s[-1]['dotations']==[] and s[-1]['solde']['281840']==-5000
assert r['raccourcie_reprise_suggeree']['reprise']['total']==3000
s=r['web_creation_duree_-1'];assert 'ok' in s['reponse'] and s['tableau']['amort_fin']==-12000 and s['dotation']['retour']==[]
for x in ('0','None'):
    s=r['base_duree_'+x];assert s['controles']['retour']==[] and 'erreur' in s['cloture'] and s['ecritures']==0
assert r['ventilation_0']['controles']==[] and r['ventilation_0']['dotation']==[]
s=r['fec_avec_composants'];assert s['rubriques'][2]['brut_fin']==0 and s['rubriques'][3]['brut_fin']==20000 and all(a['ok'] for a in s['etat']['liasse_controles'])
assert r['quote_parts']['0']['normalisation'][0]==0 and r['quote_parts']['0']['lignes'][0]['montant']==15000
assert r['plan_residuel_0.24']['somme']=='0.0' and r['plan_residuel_100000.01']['dernier']==[2076,.01]
assert r['terrain_1_281840']['controles']==[] and r['terrain_1_281840']['cloture']['retour']['total']==1200
assert r['terrain_saisie_refusee']['composants']==r['terrain_saisie_refusee']['ecritures']==0
assert r['interruption_plan']['ecritures']==1 and r['interruption_plan']['lignes']==2 and r['interruption_plan']['plans']==0
assert r['generation_rollback']['apres']==r['generation_rollback']['avant']==1
assert r['cloture_commits']['commits']==1
for x in r['contrat_gabarits']:
    assert x['transaction'] and x['transactions_aux_commits']==[False] and x['operations']==x['ecritures']==0
assert len(r['contrat_gabarits_transaction_englobante'])==44
for x in r['contrat_gabarits_transaction_englobante']:
    assert x['transaction'] and x['commits']==x['temoins']==x['operations']==x['ecritures']==0
assert r['duree_allongee_partage_False']['exercices'][-1]['solde']['281840']==-8000
assert 'erreur' in r['precedent_ouvert']['cloture'] and r['precedent_ouvert']['ecritures_2027']==0
assert r['lecture_cumul_indisponible']['controle_complet']['erreur'].startswith('OperationalError:')
assert r['renvoi_G12']=={'terrain':73130.01,'total':100000.01}
print('48 groupes vérifiés ; 12 constats corroborés ; 21 930 plans usuels ; 44 gabarits, avec et sans transaction englobante.')
