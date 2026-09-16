"""Vérifie les observations exécutées ; ne remplace pas reproduire.py."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE.parents[1] / 'compta_lmnp'
x = json.loads((HERE / 'resultats.json').read_text())
n = 0

def check(condition, label):
    global n
    n += 1
    if not condition:
        raise AssertionError(label)

for f, expected in x['environnement']['sha256'].items():
    check(hashlib.sha256((SRC / f).read_bytes()).hexdigest() == expected, f'Version source : {f}')

cuts = 0
for mode, r in x['sigkill_tous_points'].items():
    check(r['commits'] == 1, mode + ': commit unique')
    check(len(r['trace']) == len(r['coupures']) == 37, mode + ': couverture')
    for c in r['coupures']:
        cuts += 1
        label = f'{mode} point {c["point"]}'
        check(c['code'] == -9, label + ': SIGKILL')
        check(c['integrite'] == 'ok', label + ': intégrité')
        check(c['identique'], label + ': état persistant')
        if c['etat_attendu'] == 'initial':
            check(c['transaction'] and c['relance_identique'], label + ': relance')
        else:
            check(not c['transaction'] and 'déjà clos' in c['relance']['erreur'], label + ': refus après commit')
check(cuts == 74, 'nombre de coupures')

r = x['cloture_anterieure_apres_suivante']
check(r['cloture_2025']['revenu_imposable'] == 600, 'K01 revenu tardif')
check(r['etat_2025']['deficits'][0]['solde'] == 1000, 'K01 stock tardif')
check(r['ordre_chronologique']['revenu_imposable'] == 0, 'K01 revenu chronologique')
check(r['ordre_chronologique']['deficits']['stock_deficits'] == 400, 'K01 stock chronologique')
r = x['suppression_an_reconstruction']
check('déjà' in r['second_refuse']['erreur'], 'K02 reprise initialement refusée')
check(r['affectations'] == 2, 'K02 double affectation')
check(r['apres']['balance']['108000'] == -12600 and r['apres']['balance']['120000'] == 600, 'K02 soldes')
check(r['apres']['controles'] == [], 'K02 contrôles')
check('débit 12000.00 € / crédit 12600.00 €' in r['ouverture_2027']['erreur'], 'K02 blocage suivant')
r = x['jonction_un_centime']
check(r['controle'][0]['type'] == 'ok' and 'au centime' in r['controle'][0]['message'], 'K03 approbation')
check(r['controle_sans_tolerance'][0]['type'] == 'ecart' and len(r['controle_sans_tolerance'][0]['ecarts']) == 2, 'K03 écarts')

for y, r in x['trois_exercices']['rejeux']['False'].items():
    check(r['balance_identique'] and r['fiscal_identique'], 'cycle ' + y)
check('déjà générée' in x['trois_exercices']['rejeux']['True']['2024']['erreur'], 'dotation native reconnue')
check(x['comptes_externes']['rc_fiscal'] == x['comptes_externes']['rc_liasse'] == -4000, 'RC sept chiffres')
check(x['an_un_centime']['equilibre'] == [0.01, 0.01], 'AN un centime')
r = x['an_desequilibre_refuse']
check(r['ecritures'] == 0 and r['appels_controle_equilibre'] == 0 and 'déséquilibrée' in r['retour']['erreur'], 'refus automatique AN')
check('AN_ABSENTS' in x['ouverture_sans_an']['controles'], 'avertissement AN')
for y in ('2025', '2040'):
    r = x['exercice_vide_' + y]
    check('sans ligne' in r['ouverture_suivante']['erreur'] and r['exercices'][1]['statut'] == 'ouvert', 'Q11 vide ' + y)
check(x['dates_an-janvier']['ecritures'] == 2, 'AN janvier')
check(x['dates_an-decembre']['annee_detectee'] == 2024 and x['dates_an-decembre']['ecritures'] == 0, 'AN décembre')
r = x['rejeu_interrompu']
check(r['restantes'] == 0 and r['final'] == 3, 'rejeu rollback et relance')
r = x['parite_web_cli']
check(r['bases_identiques'] and r['cli_code'] == 0 and r['web_code'] == 302, 'parité web CLI')
archives = [{h for f, h in r['fichiers'][side].items() if f.startswith('archives/') and f.endswith('.txt')} for side in ('web', 'cli')]
check(len(archives[0]) == 1 and archives[0] == archives[1], 'empreinte FEC')
check(r['differences_sauvegardes'] == {'regle_fiscale': {'web': [], 'cli': None}}, 'différence sauvegardes circonscrite')
for side in ('web', 'cli'):
    r = x['archive_' + side + '_refusee']
    check(r['etat']['exercice']['statut'] == 'clos', side + ': archive sans annulation')
    message = str(r['message']) if side == 'web' else r['sortie']
    check('EST clôturé' in message, side + ': avertissement explicite')
r = x['fermeture_et_retraitements_figes']
for name, result in r['tentatives'].items():
    check('clos' in result['erreur'], 'refus ' + name)
check(r['liasse_avant'] == r['liasse_apres_parametre'], 'retraitements figés')
check(set(r['differences']) == {'bien', 'composant'}, 'extensions de schéma seulement')
for table, d in r['differences'].items():
    check([row + [None] for row in d['avant']] == d['apres'], 'colonne NULL ' + table)
check(x['restaurer_et_recloturer']['etat']['ecritures'] == 4, 'restauration sans doublon')
check(x['migration_schema_exercice_clos']['fec_identique'] and x['migration_schema_exercice_clos']['statut'] == 'clos', 'migration conserve FEC')
check(not x['ajout_sql_apres_cloture']['etat']['conforme'], 'SQL direct : divergence visible')
print(f'{n} vérifications réussies sur {cuts} coupures SIGKILL et les autres scénarios exécutés.')
