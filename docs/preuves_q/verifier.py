"""Vérifie les sorties exécutées de Q et identifie le code examiné (sans données privées)."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE.parents[1] / 'compta_lmnp_v8.41.0/compta_lmnp'
r = json.loads((HERE / 'resultats.json').read_text())
assert not any(k.startswith('HARNESS_ERROR_') for k in r)
assert len(r['lectures']) == 13
for row in r['lectures']:
    durable = row['fonction'].startswith('quittances.') or row['fonction'] == 'init_db.creer_index'
    assert row['temoins'] == int(durable)
    assert row['transaction_apres'] != durable
assert r['lecture_loyer_durable']['montant'] == 800
assert r['annulations_paralleles']['loyers'] == -800
assert r['ecriture_apres_cloture']['exercice'] == ['clos', 800]
assert r['ecriture_apres_cloture']['produits'] == 1600
assert r['quittances_double']['total'] == 1600
assert r['restaurations_paralleles'] == dict(meme_copie_surete=True, avant=2, apres=1, copie_surete=1)
assert r['appel_interrompu']['montant'] == 700
assert r['composant_web']['valeur'] == 12000 and r['composant_web']['ecritures'] == 0
assert r['import_nettoyage']['operations_apres_relance'] == 20
assert r['multi_fec']['exercices'] == [2024, 2026] and not r['multi_fec']['source_temporaire']
assert r['migration_interrompue']['version'] == 2 and r['migration_interrompue']['comptes_cession'] == 2
assert r['garde_migration_echec']['retour'] is None
assert r['ouverture_web']['exercices'] == 2
assert not r['import_interrompu']['journal_persistant']
assert r['import_interrompu']['operations'] == 0
assert len(r['gabarits']) == 44 and all(x[1] and x[3:] == [0, 0] for x in r['gabarits'])
assert r['cloture_commits']['commits'] == 1
assert r['arret_processus_cloture']['code'] == 77
assert r['arret_processus_cloture']['ecritures'] == 1
assert r['arret_processus_cloture']['suivi'] == 0
assert r['clotures_paralleles']['dotations'] == 1
assert r['saisies_paralleles']['numeros'] == list(range(1, 21))
assert r['cinquieme_collision']['tentatives'] == 5
assert r['verrou']['busy_timeout_ms'] == 5000
assert r['an_interruption']['durable'] == r['cession_interruption']['durable'] == 0
assert r['rejeu_interrompu']['ecritures'] == 0
assert r['savepoint_ligne_invalide']['ecritures'] == 0
inventory = json.loads((HERE / 'inventaire.json').read_text())
assert len(inventory) == 43
manifest = {str(p.relative_to(SRC)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(SRC.rglob('*.py'))
            if '.venv' not in p.parts and 'tests' not in p.parts}
(HERE / 'code_examine.json').write_text(json.dumps(manifest, indent=2) + '\n')
print('12 constats confirmés ; 13 lecteurs ; 44 gabarits ; 43 sites de commit/script recensés.')
