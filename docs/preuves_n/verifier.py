"""Vérifie les observations de la passe N, sans lire de données privées."""
import ast
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
src = HERE.parents[1] / 'compta_lmnp_v8.41.0/compta_lmnp'
d = json.loads((HERE / 'sorties.json').read_text())
assert d['desordre'] == [[500.0,'2000-01-01','2024-12-31'],[700.0,'2025-01-01',None],[1000.0,'2026-07-01',None]]
assert d['duree_zero']['2027']['stock_deficits'] == 0
assert d['duree_zero']['avant'] == [[2026,1200.0,2026]]
assert d['lmp'] == {'controle':['SEUIL_LMP'],'rappel':[]}
assert d['transaction_ajouter_personnalise'] == {'transaction_apres':False,'operations_apres_rollback':1}
assert d['regles_perdues'] == {'avant':['IMMOBILISABLE'],'apres':[],'valeur_recreee':500.0}
assert not d['veille_2099-01-01']['a_refaire']
assert all('veille' not in x.lower() for x in d['veille_panne'])
assert d['import_regle_inaccessible']['normal'] == 'attente_decaissement'
assert d['import_regle_inaccessible']['panne'] == 'petit_equipement'
assert d['import_regle_inaccessible']['resultat_comptable'] == -400
assert d['corpus_regles_manquantes'] == ['retraitement_alur_auto']
assert d['prompt_couverture']['alur'] is False
assert d['clos']['liasse_identique'] and d['clos']['rf_apres'] == 1600
assert d['duree_versionnee'] == [[2025,2035],[2026,2038]]
assert d['deux_saisies'] == 0
for name, value in d.items():
    if name.startswith('transaction_') and name != 'transaction_ajouter_personnalise':
        assert value == {'transaction_apres':True,'operations_apres_rollback':0}, name
for name in ('refus_loyer','refus_absent','refus_nature','collision_inactive','suppression_compte'):
    assert 'erreur' in d[name], name

# Ce contrôle de localisation complète les exécutions ; il ne les remplace pas.
locations = {
    'parametres': {'assurer':99,'valeur':126,'definir':146,'historique':177},
    'gabarits': {'assurer_table':185,'ajouter_personnalise':213,'_personnalises':236},
    'veille_fiscale': {'enregistrer_veille':147,'veille_a_refaire':159,'prompt_veille':174},
    'pense_bete': {'rappels':363,'actualites':317},
    'fiscal': {'traiter_deficit':157,'retraitement_automatique':443,'calculer_39c':113,'_calcul_fiscal':363},
    'import_bancaire': {'_seuil_immobilisation':198,'categoriser':215,'_depasse_le_seuil':252},
    'controles': {'c_depense_immobilisable':85,'c_seuil_lmp':549},
    'operations': {'saisir':23},
    'liasse': {'generer':588,'aide_2042c':429},
    'amortissement': {'plan':60},
}
for module, expected in locations.items():
    tree = ast.parse((src / 'modules' / (module + '.py')).read_text())
    actual = {n.name:n.lineno for n in tree.body if isinstance(n,ast.FunctionDef)}
    for name, line in expected.items():
        assert actual[name] == line, (module,name,actual[name],line)
print('Observations et localisations vérifiées : 8 constats, témoins conformes.')
