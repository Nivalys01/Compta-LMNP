# Preuves de la passe K

Depuis la racine du dépôt :

```bash
compta_lmnp/.venv/bin/python docs/preuves_k/reproduire.py
compta_lmnp/.venv/bin/python docs/preuves_k/verifier.py
```

`reproduire.py` exécute le code applicatif sur des bases SQLite temporaires vierges, puis remplace `resultats.json` par les observations du nouvel essai. Les données sont entièrement fictives. Les sorties web et CLI remplacent le chemin temporaire par `DOSSIER_FICTIF`. Aucun fichier de référence privée ni base réelle n’est utilisé.

Les 74 processus enfants tués par SIGKILL sont intentionnels. Les deux erreurs d’archivage provoquées sont aussi attendues ; Flask peut en imprimer la trace sur stderr. La réussite du script ne suffit pas à valider les observations : exécuter ensuite `verifier.py`, qui contrôle le JSON et les empreintes des sources auditées. Ce vérificateur ne produit pas de nouvelle preuve d’exécution à lui seul.

## Index

| Clé de `resultats.json` | Objet |
|---|---|
| `environnement` | Python, SQLite, empreintes des sources |
| `sigkill_tous_points` | Deux branches, traces, 74 interruptions et relances |
| `cloture_anterieure_apres_suivante` | K-01 et dossier comparatif chronologique |
| `suppression_an_reconstruction` | K-02, soldes et échec de l’ouverture suivante |
| `jonction_un_centime` | K-03, comparaison avec et sans tolérance |
| `trois_exercices` | Cycle natif, exports et rejeux |
| `comptes_externes`, `an_un_centime`, `an_desequilibre_refuse` | Classes de comptes, centime, refus d’un déséquilibre |
| `exercice_vide_*`, `ouverture_sans_an` | Ouverture sans bilan et avertissements |
| `dates_an-*`, `rejeu_interrompu` | Dates d’AN, interruption et relance d’un FEC |
| `parite_web_cli`, `archive_*_refusee` | Bases, archives, sauvegardes, messages |
| `fermeture_et_retraitements_figes` | Refus sur exercice clos, colonnes ajoutées et paramètres |
| `ajout_sql_apres_cloture` | Limite connue du SQL direct |
| `restaurer_et_recloturer`, `migration_schema_exercice_clos` | Restauration et migration réussie |

Le nombre de vérifications n’est pas un nombre de scénarios indépendants : plusieurs assertions contrôlent les différentes propriétés d’une même coupure. Les essais SIGKILL portent sur les frontières SQL et fonctionnelles des deux branches exécutées, sans simuler une panne matérielle ni démontrer toutes les branches possibles de clôture.
