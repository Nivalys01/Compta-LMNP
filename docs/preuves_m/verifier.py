"""Vérifie les résultats produits par reproduire.py, sans relire du code métier."""
import json
from pathlib import Path
r=json.loads((Path(__file__).parent/'resultats.json').read_text())
assert len(r['couverture']) == 27
assert len(r['inventaire']) == 27
assert not r['fonctions_non_enregistrees']
assert all(v and all(a['code']==k for a in v) for k,v in r['couverture'].items())
assert all(not a for a in r['chaque_controle_vide'].values())
assert len(r['equilibre_oppose']['anomalies'])==2 and r['equilibre_oppose']['solde_global']==0
assert len(r['equilibre_clos'])==2 and r['equilibre_fec_corrompu']
assert r['attente_sept_chiffres']['solde']==800 and not r['attente_sept_chiffres']['anomalies']
assert r['attente_compensee']['cloture']['revenu_imposable']==0
assert r['attente_compensee_reference']['revenu_imposable']==800
assert all(v['statut']=='clos' for v in r['web_attentes_non_detectees'].values())
assert all(v['statut']=='ouvert' for v in r['web_bloquants'].values())
for channel in ['web','cli']:
    assert r[channel]['False']['statut']=='ouvert'
    assert r[channel]['True']['statut']=='clos'
assert r['cli']['False']['code_retour']==0
assert r['api_sans_forcer']['statut']=='clos'
assert r['pdf_attente']['conforme'] and len(r['pdf_attente']['controles_liasse'])==5
assert not r['pdf_attente']['COMPTE_ATTENTE_imprime'] and not r['pdf_attente']['non_solde_imprime']
assert r['an_absents_bilan']['False']['bilan']['immo_corporelles_net']==-1200
assert r['an_absents_bilan']['True']['bilan']['immo_corporelles_net']==9600
assert r['amort_anterieurs_cloture']['bilan']['immo_corporelles_net']==10800
assert r['amort_avant_panne'] and not r['amort_panne']
assert r['deficit_avant_panne'] and not r['deficit_panne']
assert r['rapport_date_composant_invalide']=='Contrôles 2026 : aucune anomalie. ✓'
assert r['plan_panne_globale']=='plan fictif indisponible'
for key in ['audit_nominal','audit_peremption_fausse','audit_date_degradee','audit_sans_compte_attente']:
    assert r[key]['succes'] and r[key]['nombre']==41
assert len(r['audit_sans_dotation']['echecs'])==7
assert len(r['audit_plafond_faux']['echecs'])==3
assert r['audit_peremption_fausse']['stocks_non_vides_rencontres']==0
assert r['temoin_peremption']['avant']==1200 and r['temoin_peremption']['apres']==0
assert r['seuil_emprunt']['agregats']['produits']==0 and r['seuil_emprunt']['anomalies']
assert r['seuil_annule']['agregats']['produits']==0 and r['seuil_annule']['anomalies']
assert {'IMMOBILISABLE','ANNUEL_MULTIPLE','LOYER_ATYPIQUE'} <= {a['code'] for a in r['annulations']['anomalies']}
assert r['annulations']['agregats']['produits']==3200 and r['annulations']['agregats']['charges_hors_daa']==300
assert len(r['dossier_ordinaire'])==3 and all(a['niveau']=='INFO' for a in r['dossier_ordinaire'])
assert r['loyer_personnalise']=={'manquants':[],'atypique':[],'produits':1680.0}
assert r['seuils_infinis']=={'immo':[],'lmp':[]}
for k in ['regles_supprimees','regles_hors_millesime']:
    assert {'IMMOBILISABLE','SEUIL_LMP'} <= {a['code'] for a in r[k]}
assert r['requalifier_drapeau'] and r['annuel_personnalise']
assert r['exercice_inexistant']=='Contrôles 2099 : aucune anomalie. ✓'
print('Preuves M vérifiées : 27 déclenchements, 14 constats, clôtures et mutations cohérentes avec les sorties.')
