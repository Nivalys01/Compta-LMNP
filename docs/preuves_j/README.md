# Preuves de la passe J

Voir [le rapport](../AUDIT_PASSE_J.md), [les résultats](resultats.json), [le reproducteur](reproduire.py) et [le vérificateur](verifier.py).

## Exécution

Depuis la racine du dépôt :

```bash
compta_lmnp/.venv/bin/python docs/preuves_j/reproduire.py
compta_lmnp/.venv/bin/python docs/preuves_j/verifier.py
```

`pdftotext` est nécessaire. Les bases sont temporaires, les identités et écritures fictives. Aucun dossier réel n'est chargé. Les PDF et extractions sont régénérés dans ce répertoire. Les résultats incluent les empreintes des principaux fichiers métier.

Le vérificateur contrôle les **sorties observées, défauts compris**. Après correction, les assertions de défaut doivent échouer puis être remplacées par les attendus métier du rapport. Il ne faut pas conserver ces chiffres erronés comme spécification.

## Correspondance

| Constat / sujet | Groupes dans le JSON |
|---|---|
| J-01 | `restitution_500`, `restitution_1000`, `restitution_1500`, `fifo_7000`, `restitution_mauvais_millesime` |
| J-02 | `ancienne_declaration`, `deficit_futur_dans_ancien_suivi` |
| J-03 | `trace_peremption` |
| J-04 | `seuil_lmp_import_False`, `seuil_lmp_import_True` |
| J-05 | quinze groupes `arrondi_*` |
| Année limite | `pivot_2024`, `pivot_2025`, `pivot_2026` |
| FIFO / reliquat | `fifo_0`, `fifo_2000`, `fifo_7000`, `fifo_0.03`, `fifo_centimes` |
| Création après retraitements | `creation_ordinaire`, `creation_amortissement`, `creation_mixte`, `creation_alur` |
| Double clôture / restauration / concurrence | `double_cloture`, `restauration_recloture`, `clotures_concurrentes`, `double_appel_isole` |
| Interruption / rollback | `cloture_interrompue`, `moteur_commit_false` |
| Durée versionnée | `parametre_versionne` |
| Numéros de cases | `cases_dix_millesimes`, plus cas bénéficiaire et déficitaire |
| I-01 / I-02 prolongés jusqu'en N+11 | quatre groupes `dix_ans_*` |

Les essais d'ouverture de stocks commencent par des insertions SQL explicites. Le scénario historique J-02 crée au contraire le déficit et ses imputations successives avec les clôtures métier. La séquence sur dix ans n'ajoute aucune nouvelle dotation : elle isole la conservation et la péremption des stocks issus du FEC fictif.

Le PDF officiel fourni à la racine, `2042_Cpro.pdf`, a été examiné à la page 5 : CERFA 11222*28, revenus 2025. Les dix cases 5GA à 5GJ correspondent respectivement à 2015–2024. Le document officiel correspondant est disponible sur [impots.gouv.fr](https://www.impots.gouv.fr/sites/default/files/formulaires/2042/2026/2042_5474.pdf). Les PDF de ce répertoire sont les sorties du logiciel, pas des déclarations déposées.
