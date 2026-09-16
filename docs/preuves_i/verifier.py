"""Vérifie les résultats d'exécution conservés de la passe I, pas le code métier."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
j = json.loads((HERE / 'resultats.json').read_text())
checks = 0

def eq(actual, expected):
    global checks
    assert actual == expected, (actual, expected)
    checks += 1

def suivi(key):
    return j[key]['cloture']['suivi_39c']

eq(len(j), 38)
eq(j['moteur_matrice'], {'cas': 216, 'erreurs': []})
eq(suivi('comptes_dotation7')['stock_cloture'], 1000)
eq(j['comptes_dotation7']['cloture']['deficits']['deficit_cree'], None)
eq(suivi('comptes_charges7')['stock_cloture'], 1000)
eq(suivi('comptes_normal')['stock_cloture'], 1000)
eq(j['comptes_normal']['cloture']['deficits']['deficit_cree'], 500)
eq(j['comptes_cession6']['cloture']['revenu_imposable'], 0)
eq(j['comptes_cession7']['cloture']['revenu_imposable'], 0)
eq(j['comptes_produit_financier']['agregats']['plafond_39c'], 1000)
eq(suivi('comptes_produit_financier')['stock_cloture'], 1000)
eq(suivi('ventilation_bien_couvert_True')['stock_cloture'], 1000)
eq(j['ventilation_bien_couvert_False']['etat']['biens'][0]['report_bien'], 0)
eq(suivi('cessions_libelles_identiques_False')['stock_cloture'], 3000)
eq(suivi('cessions_libelles_identiques_True')['stock_cloture'], 3000)
eq(j['cessions_libelles_identiques_True']['etat']['sommes']['dotation_bien'], 6000)
eq(j['migration_stock_historique']['migration'], {'avant': 1, 'apres': 7})
eq(j['migration_stock_historique']['apres_migration']['biens'], [])
eq(j['migration_stock_historique']['cloture_suivante']['suivi_39c']['sorties_39c'], 1000)
eq(suivi('historique_partiel_par_bien')['stock_cloture'], 4000)
eq(j['historique_partiel_par_bien']['etat']['sommes']['stock_cloture'], 4000)
eq(suivi('repartition_centimes')['stock_cloture'], .02)
eq(j['repartition_centimes']['etat']['sommes']['stock_cloture'], .02)
eq(j['repartition_centimes']['etat']['sommes']['utilisation_bien'], 0)
eq(j['report_saisi_manuellement_1000']['controles_avant'], [])
eq(suivi('report_saisi_manuellement_1000')['stock_cloture'], 0)
eq(j['web_retraitement_manuel']['statut'], 'clos')
eq(j['web_retraitement_manuel']['status'], 302)
eq('ok' in j['web_retraitement_manuel']['redirection'], True)
eq([a['code'] for a in j['web_retraitement_manuel']['etat']['controles']], ['RETRAITEMENT_MANUEL_PLAFOND'])
eq(suivi('pdf_cession_un_bien')['sorties_39c'], 6200)
one = (HERE / 'cession_un_bien.txt').read_text()
eq('6 200,00' in one, False)
eq('Stock à la clôture' in one, True)
for name, fragment in [('reintegration', '318'), ('utilisation', '350'), ('suivi_deux_biens', '1 000,00')]:
    eq(fragment in (HERE / (name + '.txt')).read_text(), True)
eq(j['alur_equivalence_0'], j['alur_equivalence_1'])
eq(j['liste_exclusions']['initiale'], j['liste_exclusions']['apres_vidage'])
eq(j['liste_reellement_vide']['agregats']['plafond_39c'], 800)
eq(j['restauration_memoire']['apres_stock_ouverture'], 5000)
eq(j['restauration_memoire']['suivi_2026'], 0)
eq(j['absence_peremption_39c']['cloture']['suivi_39c']['stock_cloture'], 3500)
eq(j['absence_peremption_39c']['cloture']['deficits']['perimes'], 1)
eq(j['cession_milieu_exercice']['suivant']['suivi_39c']['stock_ouverture'], 4200)
for v in j['lectures_transactionnelles'].values():
    eq(v, {'commits': 0, 'transaction_avant_rollback': True, 'temoins': 0})
for key in ['comptes_dotation7', 'comptes_charges7', 'comptes_cession7', 'comptes_produit_financier']:
    eq(j[key]['etat']['controles'], [])
    eq(all(c['ok'] for c in j[key]['etat']['liasse']), True)
src = HERE.parents[1] / 'compta_lmnp'
for path, digest in j['environnement']['sha256'].items():
    eq(hashlib.sha256((src / path).read_bytes()).hexdigest(), digest)
extra = json.loads((HERE / 'cas_complementaires.json').read_text())
eq(extra['cle_marges']['suivi']['stock_cloture'], 2000)
eq(extra['cle_marges']['suivi']['sorties_39c'], 500)
eq(extra['honoraires']['suivi']['stock_cloture'], 800)
eq(extra['honoraires']['suivi']['sorties_39c'], 200)
complements = json.loads((HERE / 'complements.json').read_text())
eq(complements['oracle_decimal'], {'cas': 216, 'divergences': 0})
eq(complements['propagation_I10']['0']['revenu_imposable_2027'], 0)
eq(complements['propagation_I10']['1000']['revenu_imposable_2027'], 1000)
calage = json.loads((HERE / 'calage.json').read_text())
eq(calage['code_sortie'], 0)
eq(calage['reussites'], 5)
eq(calage['exercices_verifies'], 3)
for path, digest in json.loads((HERE / 'reverification_source.json').read_text()).items():
    eq(hashlib.sha256((src / path).read_bytes()).hexdigest(), digest)
print(f'{checks} vérifications réussies ; sources inchangées depuis la copie figée.')
