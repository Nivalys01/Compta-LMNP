"""Oracles indépendants et propagation du défaut I-10, données fictives."""
import json
from decimal import Decimal, ROUND_HALF_EVEN
from pathlib import Path
import reproduire as a

def cents(value):
    return float(value.quantize(Decimal('.01'), rounding=ROUND_HALF_EVEN))

count = 0
for stock in (0, .01, .02, 1, 1234.56, 5000):
    for dot in (0, .01, .02, 1, 1200.01, 10000):
        for ceiling in (-1000, 0, .01, 1, 1500.99, 20000):
            s, d, p = map(lambda x: Decimal(str(x)), (stock, dot, ceiling))
            capacity = max(Decimal(0), p)
            current_deduction = min(d, capacity)
            deferred = d - current_deduction
            used = min(s, max(Decimal(0), capacity - d))
            expected = dict(stock_ouverture=cents(s), dotation_exercice=cents(d),
                            plafond_deductible=cents(p), report_annee=cents(deferred),
                            utilisation_annee=cents(used), stock_cloture=cents(s + deferred - used))
            assert a.fiscal.calculer_39c(stock, dot, ceiling) == expected
            count += 1

out = {'oracle_decimal': {'cas': count, 'divergences': 0}, 'propagation_I10': {}}
for manual in (0, 1000):
    c, path = a.new()
    a.addcomp(c)
    a.income(c, 200)
    first = a.fiscal.cloturer(c, 2026, autres_retraitements=manual)
    a.open_(c, 2027)
    a.income(c, 2200, 2027)
    second = a.fiscal.cloturer(c, 2027)
    out['propagation_I10'][str(manual)] = {
        'report_2026': first['suivi_39c']['stock_cloture'],
        'rf_2026': first['resultat_fiscal'],
        'utilisation_2027': second['suivi_39c']['utilisation_annee'],
        'revenu_imposable_2027': second['revenu_imposable']}
    c.close()
assert out['propagation_I10']['0'] == dict(report_2026=1000, rf_2026=0, utilisation_2027=1000, revenu_imposable_2027=0)
assert out['propagation_I10']['1000'] == dict(report_2026=0, rf_2026=0, utilisation_2027=0, revenu_imposable_2027=1000)
Path(__file__).with_name('complements.json').write_text(json.dumps(out, indent=2) + '\n')
print(json.dumps(out))
