# Couverture de la passe H

Le script `reproduire.py` crée uniquement des bases blanches temporaires et produit `resultats.json`. Il s'arrête sur une erreur de harnais. `verifier.py` contrôle les valeurs effectivement exécutées ; il ne conclut pas à partir de motifs présents dans le code source.

```bash
compta_lmnp/.venv/bin/python docs/preuves_h/reproduire.py
compta_lmnp/.venv/bin/python docs/preuves_h/verifier.py
```

## Correspondance avec les demandes

| Demande | Exécution / clé dans les résultats | Conclusion |
|---|---|---|
| Somme des annuités, durées et dates difficiles | `plans_cibles`, `matrice_plans` | 21 930 combinaisons usuelles conservent le total |
| Valeurs minuscules et fin effective du plan | `plan_residuel_0.24`, `plan_residuel_100000.01` | H-11 |
| Prorata, années bissextiles, conversion flottante | `prorata`, `plans_cibles`, matrice avec somme Decimal | Pas d'excès de valeur constaté ; convention fiscale non certifiée |
| Durée nulle, négative, NULL | `durees_invalides_plan`, `base_duree_*`, `web_creation_duree_*` | H-07, distinction formulaire / base incohérente |
| Terrain normal, compte absent, compte erroné | `terrain_*`, `terrain_saisie_refusee` | Protection web tenue ; H-12 sur référentiel incohérent injecté |
| N-1 non clos | `precedent_ouvert` | Clôture refusée avant insertion |
| DAA déjà saisie à la main | `manuel_resultat_fiscal`, `manuel_False` | H-02 |
| Annulation de DAA | `daa_annulee`, `manuel_True` | H-03 ; inverse passé par le guichet d'écriture |
| AN importé et cumul lu | `an_premier_exercice`, `fec_avec_composants` | H-02 ; lecture à zéro faute d'exercice précédent clos |
| Allongement, composant seul | `duree_allongee_partage_False` | Borne tenue ; alerte de durée présente |
| Allongement, compte partagé | `duree_allongee_partage_True` | H-01 ; 3 600 € excédentaires |
| Raccourcissement et années après fin théorique | `raccourcie`, `raccourcie_fin_plan`, `raccourcie_reprise_suggeree` | H-06 |
| Valeur brute corrigée après dotations | `valeur_corrigee` | Arrêt de dotation ; écarts signalés |
| Double génération et double clôture | `double_generation`, `cloture_commits` | Deuxièmes appels refusés ; séquentiel seulement |
| Omission en exercice sans loyers / fin d'année | `omission_2026-01-01`, `omission_2026-12-31` | H-04 ; AN proposé ou seuil qui empêche la reprise |
| 39 B et différence avec reprise / report 39 C | Omission et allongements ; sources officielles dans le rapport | Pas de contrôle général du minimum ; conséquences limitées à ce qui est établi |
| Ventilation et total du prix | `quote_parts`, `renvoi_G12` | Totaux conservés ; H-10 et renvoi G-12 |
| Fraction / pourcentage / 1,0 | `quote_parts` | 7,35 et 0,0735 équivalents ; 1 = 100 % |
| Contrôle VENTILATION_INCOMPLETE | `ventilation_0`, `ventilation_1000`, `ventilation_11400`, `ventilation_12000` | H-08 ; seuil de 5 % caractérisé |
| Comptes hors table, menu | `fec_sans_composants`, `fec_avec_composants` | Menu statique de quatre comptes ; H-09 |
| 2180000, 2181000, 2818000, 2818100 | Rejeu d'un FEC synthétique équilibré | Comptes et soldes conservés ; mauvais regroupement des agencements |
| 2033-C / bilan, avant et après clôture | Objets `etat`, `avant`, `apres`, séries annuelles | H-05 ; divergences importantes détectées dans la liasse |
| DOTATION_PLAN et AMORT_ANTERIEURS | Exécution de `controles.controler` dans chaque état | Portée et limites documentées, aucun fichier supposé absent |
| Lecture qui ne peut pas vérifier | `lecture_cumul_indisponible` | Contrôle isolé muet, mais contrôle complet en erreur ; pas de faux constat global |
| commit=False, savepoint et exception après DAA | `generation_rollback`, `interruption_plan` | Rollback suivi de réouverture : aucune DAA survivante |
| Commit unique final | `cloture_commits` | 1 commit réellement appelé |
| operations.saisir, gabarits et paramètre versionné | `contrat_gabarits`, `contrat_gabarits_transaction_englobante` | 44 types, deux opérations chacun, rollback ; aucun témoin survivant |

## Limites de l'exécution

- Les bases sont fictives ; aucune durée ni quote-part réelle n'a été examinée.
- Le plan de 0,24 € sert à éprouver la terminaison et les arrondis, pas à recommander une immobilisation de ce montant.
- La valeur brute corrigée, les durées 0/NULL avec `amortissable=1`, le terrain doté d'un mauvais compte 28 et la table comptable renommée sont des injections explicites. Le rapport distingue ces états des créations par formulaire.
- Les contre-passations sont des écritures inverses insérées par `ecritures.inserer`. Elles ne supposent pas que les DAA générées disposent d'une ligne `operation` annulable par la route des opérations.
- Le test web appelle une route dans un contexte de requête Flask ; il ne teste pas la validation HTML du navigateur.
- La concurrence, la coupure matérielle, le dépôt EDI et la fiscalité personnelle ne sont pas certifiés par cette passe.
- Les contrôles de publication dépendant des empreintes réelles n'ont pas été lancés. Le contenu ajouté est construit exclusivement à partir de fixtures fictives et de code générique.

## Vérification de la livraison

Le vérificateur compare les sorties numériques des douze constats, les contre-tests et les contrats de transaction. Les références de fonctions et leurs lignes de définition ont été recoupées dans les fichiers présents. Cette lecture sert à localiser les causes, jamais à établir le résultat comptable.
