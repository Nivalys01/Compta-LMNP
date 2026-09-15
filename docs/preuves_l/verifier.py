"""Vérifie les sorties exécutées de la passe L et leur version de source."""
import hashlib, json
from pathlib import Path
P=Path(__file__).parent; X=json.loads((P/'resultats.json').read_text())
SRC=P.parents[1]/'compta_lmnp_v8.41.0/compta_lmnp'
N=0
def eq(actual,expected):
    global N
    assert actual == expected, (actual,expected)
    N+=1
for f,h in X['sources'].items():eq(hashlib.sha256((SRC/f).read_bytes()).hexdigest(),h)
for prix,rc in [(15000,6000),(5000,-4000),(0,-9000)]:
    r=X[f'prix_{prix}'];eq(r['cession']['dotation_complementaire'],595.07)
    for status in ['ouvert','clos']:
        b=r[status]['b'];eq(b['benefice_ou_perte_310'],rc)
        eq(b['resultat_fiscal_lmnp'],2404.93);eq(b['resultat_fiscal_352'],0)
        eq(b['produits_exceptionnels_290'],prix);eq(b['charges_exceptionnelles_300'],11404.93)
        for e in r[status]['ecritures']:eq(e['debit'],e['credit']);eq(e['exercice_annee'],2026)
eq(X['cycle_2026']['immo']['totaux'],dict.fromkeys(['brut_debut','augmentations','brut_fin','amort_debut','dotation','amort_fin'],0))
eq(X['cycle_2026']['conforme'],True)
eq(X['cycle_2027']['immo']['detail_composants'],[])
eq(X['cycle_2027']['ag']['dotation'],0)
eq(X['cumul_repris_cession']['vnc_sortie'],10204.93)
eq(X['cumul_repris_apres']['a']['amortissements_030'],1800)
eq(X['cumul_repris_apres']['conforme'],False)
eq(X['avant_acquisition']['vnc_sortie'],12000)
eq(X['avant_acquisition_etat']['conforme'],True)
eq(X['refus_clos']['ecritures_avant_apres'],[2,2])
eq(X['sans_comptes']['comptes'],[])
eq(X['sans_comptes']['ag']['produits_cession'],0)
eq(X['sans_comptes']['ag']['vnc_cession'],0)
eq(X['pdf']['notaire'],False);eq(X['pdf']['2048'],False)
eq(X['panne']['avant'],X['panne']['apres_rollback'])
eq(X['panne']['avant_rollback'],X['panne']['avant']+1)
eq(X['2026-01-01']['dotation_complementaire'],3.29)
eq(X['2026-12-31']['dotation_complementaire'],1200)
eq(X['dates_sortie_preservees'][0]['date_sortie'],'2026-06-30')
t=(P/'cycle.txt').read_text()
eq('15 000,00' in t,True);eq('10 204,93' in t,True)
eq('4 795,07' in t,True);eq('notaire' in t.lower(),False)
print(f'{N} vérifications réussies sur les sorties réelles et les empreintes source.')
