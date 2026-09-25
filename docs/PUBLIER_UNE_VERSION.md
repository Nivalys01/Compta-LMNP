# Publier une version

Procédure de publication d'une version de Compta LMNP sur GitHub. Elle
s'exécute sur le poste du mainteneur, qui détient le dossier privé
(`compta_lmnp/reference/`, `compta_lmnp/seed_exemple.sql`) : sans lui, la
construction refuse de conclure, faute de pouvoir vérifier qu'aucune donnée
réelle ne part.

## Deux dossiers, deux rôles

| Dossier | Contenu | Fiable ? |
|---|---|---|
| `compta_lmnp/dist/` | Constructions de l'arbre de travail | **Non.** La suite de tests d'un commit antérieur à 8.58.0 y écrit et y efface le paquet de sa version. Le 2026-09-25, les zips 8.55.0, 8.56.0 et 8.57.0 de `dist/` ne correspondaient pas à leur tag. |
| `compta_lmnp/paquets-publies/` | Paquets **publiés**, identiques aux fichiers des releases GitHub, et leur `SHA256SUMS` | **Oui.** Aucun code n'y écrit ; la garde de session des tests fait échouer la suite si elle y touche. |

Les deux dossiers sont ignorés par git. Le paquet qui fait foi est celui de
la release GitHub ; `paquets-publies/` en est la copie locale.

## Étapes

1. **Tag annoté** sur le commit de la version (`vX.Y.Z`), au format des tags
   précédents : résumé, puis « État à ce commit » (tests, paquet éprouvé,
   fichiers contrôlés).

2. **Construire depuis le tag, jamais depuis l'arbre de travail** :

   ```bash
   git worktree add /tmp/wt-X.Y.Z vX.Y.Z
   cp -r compta_lmnp/reference compta_lmnp/seed_exemple.sql /tmp/wt-X.Y.Z/compta_lmnp/
   (cd /tmp/wt-X.Y.Z/compta_lmnp && python construire_distribution.py)
   ```

   La ligne finale doit annoncer **4 empreintes**. Moins, c'est que le
   dossier privé n'a pas été copié : le contrôle ne prouve rien.

3. **Vérifier le zip contre le tag** : chaque fichier embarqué identique à
   celui du tag, aux réécritures de liens près (`REECRITURES` de
   `construire_distribution.py`) ; `MANIFESTE.json` est généré.

4. **Éprouver le paquet décompressé**, hors du dépôt : contrôle d'intégrité
   (`integrite.verifier`, 0 manquant, 0 différent), puis toutes les pages
   servies sur le dossier de démonstration.

5. **Supprimer le worktree** (`git worktree remove --force`) : il contient
   une copie du dossier privé.

6. **Publier** : `gh release create vX.Y.Z <zip> --verify-tag`, notes au
   format des releases précédentes (installation, SHA-256, nombre de
   fichiers du manifeste, tests). Retélécharger l'asset et comparer son
   SHA-256.

7. **Archiver** le zip dans `compta_lmnp/paquets-publies/` et ajouter sa
   ligne à `SHA256SUMS`.
