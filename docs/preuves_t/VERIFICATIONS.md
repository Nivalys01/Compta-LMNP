# Vérifications de la passe T

État audité : commit `e953974cd6b161a9d055120f6b1fe5331d64f964`, version 8.52.0, 16 septembre 2026.

| Commande | Résultat observé |
|---|---|
| `.venv/bin/python -m pytest -q compta_lmnp/tests` | 1 failed, 1161 passed, 2 skipped in 38.06s ; seul échec : `test_lanceur.py::test_app_port_configurable` |
| `.venv/bin/python -m pytest -q compta_lmnp/tests/test_lanceur.py::test_app_port_configurable` hors restrictions réseau du bac à sable, autorisé | 1 passed in 0.53s |
| `.venv/bin/python -m pytest -q -rs compta_lmnp/tests/test_passe_r.py` | 12 passed in 0.21s |
| `.venv/bin/python -m ruff check compta_lmnp` | All checks passed! |
| `.venv/bin/python compta_lmnp/verifier_depot.py` | code 0 (garde locale de publication, périmètre propre à cet outil) |
| `.venv/bin/python docs/preuves_t/reproduire.py` | code 0 ; détails dans `resultats.json` |

Le script de preuve emploie exclusivement des bases blanches temporaires. Les substitutions imposent des entrelacements précis : migration suspendue, deux lectures du registre avant publication, même seconde de sauvegarde et synchronisation avant création de destination. Elles prouvent une possibilité, pas une fréquence. Les appels métier et leurs écritures restent réels. Le scénario HTML vérifie la réponse, pas l'exécution JavaScript dans un navigateur.

Les traces d'erreur de migration sur stderr sont attendues : une panne fictive est injectée. Le script est un outil de caractérisation : il rapporte les valeurs observées sans exiger que les défauts restent présents après correction. Les délais des barrières, eux, font échouer une reproduction incomplète.

Les sources externes consultées pour la vérification ciblée des dépendances sont liées dans le rapport. Aucun scan CVE exhaustif n'a été exécuté. Les sorties pytest complètes ne sont pas publiées pour éviter d'inclure des chemins ou données de fixtures privées ; ce fichier en conserve les résultats utiles.
