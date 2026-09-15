# Preuves de la passe I — réexamen

Voir [le rapport actif](../AUDIT_PASSE_I.md). Le répertoire source a conservé son ancien nom, mais la version examinée annonce 8.43.0 et comprend des modifications non commitées identifiées dans `reverification_source.json`.

## Rejouer

Depuis la racine, avec l'environnement Python fourni et `pdftotext` :

```bash
compta_lmnp_v8.41.0/compta_lmnp/.venv/bin/python docs/preuves_i/reproduire.py
compta_lmnp_v8.41.0/compta_lmnp/.venv/bin/python docs/preuves_i/cas_complementaires.py
compta_lmnp_v8.41.0/compta_lmnp/.venv/bin/python docs/preuves_i/complements_reverification.py
compta_lmnp_v8.41.0/compta_lmnp/.venv/bin/python docs/preuves_i/calage.py
compta_lmnp_v8.41.0/compta_lmnp/.venv/bin/python docs/preuves_i/verifier.py
```

Les trois premiers scripts emploient exclusivement des bases et identités fictives. Ils exécutent 38 groupes principaux, deux nouveaux scénarios de ventilation, un oracle décimal de 216 cas et deux chaînes 2026–2027. Ils génèrent les quatre PDF et leurs extractions texte.

`calage.py` est différent : il lit les FEC privés au travers de la fixture existante, dans une base temporaire supprimée ensuite. Il ne conserve que le statut, les compteurs et l'empreinte du test source. Aucun message d'exception, valeur comptable ou sortie brute n'est publié. En l'absence de pytest, seuls son import et les décorateurs sont retirés de l'AST ; les corps des fonctions existantes sont exécutés tels quels. Cinq appels vérifient les trois exercices, les reports finaux et une imputation. Ce n'est pas toute la suite de tests.

`verifier.py` confronte les sorties enregistrées aux observations du rapport et contrôle les empreintes des sources. **Il vérifie aussi les défauts reproduits. Après correction, les assertions correspondantes doivent échouer puis être remplacées par les attendus métier.** Il n'approuve pas les comportements erronés comme spécification.

## Correspondance

| Référence | Preuve actuelle |
|---|---|
| I-01 à I-04 corrigés | `resultats.json`, clés `comptes_*` |
| I-05 corrigé sur son scénario initial | `ventilation_bien_couvert_False`, `ventilation_bien_couvert_True` |
| I-06 corrigé | `cessions_libelles_identiques_False`, `cessions_libelles_identiques_True` |
| I-07 résiduel | `migration_stock_historique` |
| I-08 divergence corrigée | `historique_partiel_par_bien` |
| I-09 corrigé | `repartition_centimes` |
| I-10 actif | `web_retraitement_manuel`, `report_saisi_manuellement_1000` et `complements.json` |
| I-11 actif | `pdf_cession_un_bien`, `cession_un_bien.pdf`, `cession_un_bien.txt` |
| I-12 nouveau | `cas_complementaires.json`, `cle_marges` |
| I-13 nouveau | `cas_complementaires.json`, `honoraires` |

## Historique et version

`rapport_avant_correctifs.md` et `resultats_avant_correctifs.json` documentent l'état antérieur, désormais dépassé. Les chemins et lignes qu'ils contiennent sont historiques. Le rapport actif distingue les huit cas corrigés des cinq défauts actifs ; il ne maintient pas les anciens chiffres contre les nouvelles exécutions.

`reverification_resultats.json` provient de la copie figée, `resultats.json` du dernier rejeu sur le répertoire courant. Le manifeste `reverification_source.json` permet de refuser une conclusion sur des sources qui auraient encore changé. Les bases historiques incomplètes sont des fixtures explicites : elles établissent le comportement d'acceptation, pas la façon dont un dossier réel aurait atteint cet état.
