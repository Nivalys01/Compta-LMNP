# Audit — passe O : sauvegardes, restauration et pérennité

**15 septembre 2026 — 10 constats reproduits, tous majeurs.**

Le risque principal est de confondre une copie créée avec une sauvegarde utilisable. Un autre essai remplace effectivement la comptabilité par une base sans table pendant une restauration annoncée réussie ; sa copie de sûreté permet toutefois une récupération par le moteur.

## Périmètre et méthode

Code : `compta_lmnp/`. Les fichiers et lignes ci-dessous sont relatifs à cette racine. Lecture du récapitulatif B du CHANGELOG v8.37.0, des compléments D2/E/F consultables dans Git et des rapports présents, notamment K et Q. Les suppressions préexistantes des anciens rapports ne sont pas modifiées.

Les cinq fichiers demandés sont présents. Les modules appelés et les modèles HTML ont également été consultés. **Aucune base réelle, aucun FEC réel, aucun seed privé et aucun fichier d'empreintes privées n'ont été utilisés.** Les bases sont initialisées en mode blanc, avec une identité fictive et des loyers de 800 €. Aucun correctif de production n'est appliqué.

Preuves livrées : [script exécutable](preuves_o/reproduire.py), [résultats et empreintes des cinq sources](preuves_o/resultats.json).

```bash
compta_lmnp/.venv/bin/python docs/preuves_o/reproduire.py
```

Les injections sont distinguées des usages ordinaires : corruption SQL, fichier vide, registre tronqué, panne disque simulée et évolution de version simulée. Les vues web utilisent Flask avec des chemins redirigés vers les bases fictives. Le bloc de démarrage est exécuté depuis son AST, avec ces mêmes chemins, sans lancer de serveur réel. Les bases temporaires sont supprimées à la fin. Le script termine en code 0 ; une erreur inattendue interrompt sa production de résultats.

Cette passe vérifie les mécanismes logiciels de conservation demandés ; elle ne certifie ni une durée légale ni la résistance physique du support.

## Constats

### O-01 — Une sauvegarde illisible est retournée comme une copie réussie

**Gravité : majeur.**

**Fichier et fonction :** `modules/perennite.py`, `sauvegarder`, **64**, copie à **85**, rotation et retour à **91–92**.

**Scénario :** base blanche avec un loyer de **800 €**. Injecter une corruption du catalogue SQLite : sous `PRAGMA writable_schema=ON`, attribuer à l'index `idx_ligne_ecriture` la page racine de `idx_ligne_compte`. Fermer puis appeler `sauvegarder`. Il s'agit d'une corruption volontaire de la source, pas d'une écriture métier créant cette corruption.

**Attendu :** conserver éventuellement la copie à titre de récupération, mais signaler qu'elle n'est pas une sauvegarde vérifiée et ne pas poursuivre une rotation comme après un succès sain.

**Produit réel** (`sauvegarde_corrompue`) :

```text
appel : retour=<TEMP_FICTIF>/index/sauvegardes/compta-…-manuel.db
lecture de la copie : DatabaseError
malformed database schema (idx_ligne_compte) - invalid rootpage
```

**Conséquence :** une copie censée protéger **800 € de recettes** est inutilisable par les lectures normales, sans échec de sauvegarde. Le moteur de restauration la refuserait ; le défaut est découvert au moment où l'on a besoin de la copie. Aucune perte supplémentaire des 800 € n'est attribuée à la copie elle-même : la source a été délibérément corrompue. L'API backup garantit ici une copie, pas la validité du schéma copié.

### O-02 — Une copie quotidienne vide empêche toute nouvelle tentative du jour

**Gravité : majeur.**

**Fichier et fonction :** `modules/perennite.py`, `sauvegarde_quotidienne`, **225**, décision sur le seul nom à **238–240** ; `lister_sauvegardes`, **254**.

**Scénario :** base contenant **800 €** ; déposer dans son répertoire de sauvegardes un fichier de **zéro octet**, nommé `compta-20260915-000000-demarrage.db`, puis appeler la sauvegarde quotidienne le 15 septembre 2026. Le script adapte cette date au jour de son exécution.

**Attendu :** considérer cette copie comme invalide, le dire et retenter la sauvegarde.

**Produit réel** (`quotidienne_vide`) :

```text
retour=null
copies=[["compta-20260915-000000-demarrage.db",0]]
```

**Conséquence :** aucune copie utilisable des **800 €** n'est créée ce jour-là par ce mécanisme. Le fichier vide apparaît dans la liste. Le scénario reproduit l'état résiduel ; il ne prétend pas avoir provoqué une coupure physique pendant backup.

### O-03 — La sauvegarde de sûreté peut purger la source choisie, puis restaurer du vide

**Gravité : majeur.**

**Fichiers et fonctions :** `modules/perennite.py`, `restaurer`, **123**, validation à **159**, sauvegarde préalable à **184**, réouverture de la source à **189** ; `sauvegarder`, **64** ; `_rotation`, **211**.

**Scénario :** base de **800 €**, et **31 copies ordinaires valides** dans `sauvegardes/`, nommées `compta-20260101-000000-manuel.db` à `compta-20260101-000030-manuel.db`. Cette situation est notamment compatible avec un quota antérieur de 31 ou un rapatriement de copies. Restaurer la première.

**Attendu :** garder la source disponible jusqu'à la fin ; restaurer sa comptabilité de 800 €, ou refuser sans modifier la base.

**Produit réel** (`source_purgee`, `retour_source_purgee`) :

```text
restaurer : retour=<copie avant-restauration>
tables_apres=[]
source_taille=0
surete : operations=1 ; montant=800.0 ; integrite=ok
vue de restauration suivante : OperationalError: no such table: exercice
retour par le moteur : operations=1 ; montant=800.0 ; integrite=ok
```

La source a passé la validation, puis la rotation déclenchée par la copie de sûreté l'a supprimée. Sa réouverture par SQLite recrée un fichier vide ; backup remplace alors la destination par ce vide.

**Conséquence :** **800 € disparaissent de la base active**, avec retour réussi. L'interface de restauration ne peut plus lire l'exercice. La perte n'est **pas irréversible** : la récupération par le moteur depuis une copie distinctement nommée a été exécutée et rend les 800 €. Ce défaut est distinct de la collision d'horodatage Q-05.

### O-04 — Déplacer une copie d'un autre dossier suffit à lui attribuer l'appartenance

**Gravité : majeur.**

**Fichier et fonction :** `modules/perennite.py`, `restaurer`, **123**, comparaison des répertoires à **142–144**.

**Scénario :** dossier A avec **1 600 €** de recettes, dossier B avec **2 500 €**. Restaurer directement la sauvegarde de B dans A ; puis copier ce même fichier dans le répertoire `sauvegardes/` de A et recommencer.

**Attendu :** le déplacement ne transforme pas une comptabilité B en sauvegarde de A ; le second appel doit également refuser, ou exiger un rattachement explicitement distinct d'une restauration ordinaire.

**Produit réel** (`appartenance`) :

```text
chemin d'origine : ValueError: Cette sauvegarde n'appartient pas au dossier courant.
copie déplacée : retour=<copie avant-restauration>
base A : operations=1 ; montant=2500.0 ; integrite=ok
```

**Conséquence :** substitution d'une comptabilité par une autre ; dans l'essai, **900 € de recettes supplémentaires** dans le dossier A. Ce n'est pas une démonstration de l'impôt correspondant. La copie de sûreté offre un retour sous les réserves Q-05.

**Diagnostic amendé :** le correctif B tient pour le chemin externe directement fourni. Il ne crée aucune marque d'identité interne. Le constat nouveau vise le fichier déplacé, geste plausible lors d'une récupération de disque ; il ne répète pas le refus déjà corrigé.

### O-05 — La vérification des archives omet les preuves qu'elle ne peut plus lire

**Gravité : majeur.**

**Fichier et fonction :** `modules/perennite.py`, `verifier_archives`, **317**, manifeste absent à **326–327**, ligne ignorée à **334–335**.

**Scénario :** archiver deux fois le FEC d'un exercice portant **800 €**. Supprimer le premier FEC ; vérifier. Remplacer ensuite sa ligne du manifeste par `ligne illisible` ; vérifier. Supprimer enfin le manifeste en laissant le second FEC sur disque.

**Attendu :** conserver un diagnostic de contrôle incomplet, distinct d'un dossier sans archive ; ne pas faire disparaître l'absence déjà constatée.

**Produit réel** (`archives_controle`, extraits) :

```text
avant altération du manifeste : statuts=[absent,ok]
après ligne illisible : statuts=[ok]
sans manifeste : []
```

**Conséquence :** la perte d'une preuve portant sur **800 €** cesse d'être signalée. Un consommateur cherchant les statuts différents de `ok` ne voit plus d'anomalie. La fonction ne produit toutefois pas littéralement un verdict global « conforme » : elle rend une liste incomplète ou vide.

**Limite vérifiée :** une ligne de quatre champs dont l'exercice vaut `illisible` lève au contraire `ValueError`. Toutes les corruptions du manifeste ne sont donc pas silencieuses.

### O-06 — L'interface propose une archive modifiée sans exploiter le contrôle d'intégrité

**Gravité : majeur.**

**Fichier et fonctions :** `app.py`, `archives_page`, **1512**, lecture du manifeste à **1533–1536** ; `archive_telecharger`, **1552**.

**Scénario :** produire une archive de **800 €**, garder son manifeste, remplacer son contenu par `FEC fictif altere`, puis ouvrir `/archives` et télécharger le fichier par son lien.

**Attendu :** montrer l'écart détectable et empêcher de prendre ce téléchargement pour une archive vérifiée ; afficher l'empreinte effectivement rattachée au fichier.

**Produit réel** (`archives_web`) :

```text
page : HTTP 200
empreinte attendue affichée : false
téléchargement : HTTP 200
contenu reçu : FEC fictif altere
```

Le contrôle moteur exécuté séparément rend bien `modifie`. La page ne l'appelle pas. Elle indexe également les empreintes par le premier champ du manifeste — l'horodatage — alors que le nom de fichier est le deuxième.

**Conséquence :** un document altéré remplace à l'usage le FEC de **800 €**, sans avertissement de cette interface. Le contrôle est disponible par appel Python, mais l'écart n'est ni bloquant ni affiché dans ce parcours. Aucun montant fiscal n'est déduit du texte altéré.

### O-07 — Restaurer un ancien schéma ne réactive pas sa migration en session

**Gravité : majeur.**

**Fichier et fonctions :** `app.py`, `_migrer_si_besoin`, **121**, cache à **132–134** ; `sauvegardes_restaurer`, **1565**, restauration à **1575**.

**Scénario :** base de **800 €**, version 6, sans compte `164000`. Prendre une sauvegarde, migrer en version 7, ouvrir `/dossiers` pour peupler le cache, restaurer la sauvegarde v6 par POST puis rouvrir `/dossiers` dans le même processus.

**Attendu :** invalider le cache de ce chemin et migrer la base restaurée avant les accès métier.

**Produit réel** (`cache_restauration`) :

```text
POST : 302, message « Dossier restauré depuis … »
base après l'affichage suivant : version=6 ; montant=800.0 ; integrite=ok
compte164000=0
chemin présent dans _MIGRES=true
```

**Conséquence :** le dossier est utilisé avec un schéma que le logiciel devait mettre à niveau ; ici le compte ajouté par le palier 7 reste absent. Les **800 €** restent présents ; aucun écart fiscal supplémentaire n'est établi. Le redémarrage peut relancer la migration. Ce n'est pas l'exception de migration avalée déjà décrite en Q-10.

### O-08 — Une sauvegarde future est installée avant que la garde ne bloque le dossier

**Gravité : majeur.**

**Fichiers et fonctions :** `modules/perennite.py`, `restaurer`, **123** ; `app.py`, `sauvegardes_restaurer`, **1565** ; `_garde_version_schema`, **207**.

**Scénario :** sauvegarder une base de **800 €** dont la version est marquée **99** ; remettre la base active en version 7 ; restaurer cette sauvegarde par POST puis suivre vers `/dossiers`.

**Attendu :** refuser la version future avant de remplacer la base active.

**Produit réel** (`restauration_future`) :

```text
POST : 302, message de restauration réussie
GET /dossiers : 409
version durable de la base active : 99
```

**Conséquence :** le dossier devient inaccessible avec cette version du logiciel, après une opération annoncée réussie. Les **800 €** ne sont pas effacés. La copie de sûreté existe, mais le retour ordinaire par la route de restauration traverse la même garde de version. Le moteur de migration seul préserve correctement une base future, empreinte inchangée : le défaut est en amont, dans la restauration.

### O-09 — Un registre corrompu efface silencieusement les dossiers de la sélection

**Gravité : majeur.**

**Fichiers et fonctions :** `modules/dossiers.py`, `_charger`, **59**, repli à **68–69** ; `lister`, **112** ; `app.py`, `_db_path`, **339**.

**Scénario :** créer `Dossier Alpha`, y saisir **800 €**, conserver son cookie actif et remplacer `dossiers.json` par `{tronque`. Ouvrir `/dossiers`.

**Attendu :** signaler le registre illisible et éviter de changer silencieusement de comptabilité active.

**Produit réel** (`registre_corrompu`) :

```text
liste=[principal]
web=200
retombe_principal=true
base_alpha : operations=1 ; montant=800.0 ; integrite=ok
```

**Conséquence :** les **800 €** subsistent sur disque mais leur dossier disparaît de l'interface ; la session sélectionne le principal. Aucune saisie dans le mauvais dossier n'a été exécutée ici. Recréer le nom initial réadopte effectivement la base sans l'effacer, mais suppose de connaître ce nom/slug. Le registre n'est pas inclus dans la copie SQLite.

**Diagnostic amendé :** une base absente avec une entrée de registre intacte reçoit bien HTTP 409, sans création d'un fichier vierge. Le défaut porte sur le registre illisible, pas sur ce correctif antérieur.

### O-10 — Après restauration, les archives ne distinguent pas les deux histoires comptables

**Gravité : majeur.**

**Fichier et fonctions :** `modules/perennite.py`, `restaurer`, **123** ; `archiver_fec`, **283**, entrée de manifeste à **311–313** ; `verifier_archives`, **317**.

**Scénario :** sauvegarder 2026 ouvert avec **800 €** ; clôturer et archiver ; ouvrir 2027 et saisir **900 €**. Restaurer la sauvegarde de 2026. Ajouter ensuite **1 000 €** à 2026, clôturer et archiver à nouveau.

**Attendu :** conserver les anciennes preuves, tout en identifiant la restauration et le lien entre l'archive antérieure et celle correspondant à la base actuelle.

**Produit réel** (`chaine_restauree`, `seconde_cloture`) :

```text
avant restauration : operations=2 ; montant=1700.0
après : operations=1 ; montant=800.0 ; exercices=[[2026,ouvert]]
ancienne archive 2026 : statut=ok
après nouvelle clôture : recettes_base=1800.0
archives 2026 : statuts=[ok,ok]
entête du manifeste : horodatage;fichier;exercice;sha256
```

Les deux fichiers distincts et leurs empreintes sont conservés ; aucune ligne du manifeste ne rattache une archive à la restauration ni n'indique une substitution. L'horodatage permet de constater l'ordre de production, pas de prouver à lui seul laquelle a été déclarée.

**Conséquence :** coexistence de deux FEC portant respectivement **800 € et 1 800 €** de recettes, soit **1 000 € d'écart**, tous deux intègres au sens de leur empreinte. L'utilisateur doit reconstruire le contexte hors du logiciel. Les **900 € de 2027** reviennent en arrière avec toute la base : ce retour global est attendu, pas une perte sélective des à-nouveaux. La copie de sûreté conserve cet état précédent sous les réserves Q-05.

## Ce qui a été vérifié et tenu

### Sauvegarde, rotation et retour arrière

- **WAL et transaction concurrente :** deux loyers validés de 800 €, WAL encore présent, puis modification à 9 999 € non validée sur une connexion maintenue ouverte. La sauvegarde séparée contient **deux opérations, 1 600 €, `integrity_check=ok`**. La modification en attente n'entre pas dans la copie. Ce test démontre le cas WAL/transaction ouverte, pas tous les entrelacements matériels.
- **Rotation :** 35 fichiers ordinaires et les quatre motifs de sûreté actuels donnent **30 ordinaires + 4 copies de sûreté**. Le tri est lexical sur le nom horodaté, pas sur la date de modification ni sur une validation de contenu. Les 30 copies ne constituent pas une garantie de six années ; les archives ont un autre rôle. Les copies de sûreté restent hors quota, mais leur création déclenche quand même la purge ordinaire (O-03).
- **Restauration réversible ordinaire :** **1 600 → 800 → 1 600 €**, chaque état rouvert et compté. Le fichier de récupération est renommé pour isoler ce test de la collision d'horodatage déjà Q-05 ; cela ne certifie pas le double clic de restauration.
- **`init_db.init` (ligne 57) sans écrasement :** `FileExistsError`, empreinte de la base inchangée. **Restauration d'une base blanche sans écriture :** refus explicite, empreinte active inchangée. L'intégrité contrôlée ne se limite donc pas à la structure SQLite ; elle compte aussi les en-têtes d'écritures, sans constituer un audit de leur contenu comptable.
- **Quittances :** sauvegarde au n° 1, base au n° 2 : refus de recul et empreinte inchangée. La table réelle de quittances est utilisée ; les deux enregistrements fictifs sont injectés par SQL pour isoler ce garde.
- **Appartenance :** le chemin direct d'un autre dossier est refusé. Un renommage d'affichage conserve bien slug et chemin. Aucun identifiant de dossier interne n'est vérifié par la restauration ; la protection ne doit pas être décrite comme une marque embarquée survivant à toute copie.

### Archives et registre

- Deux archivages séquentiels dans la même seconde donnent des noms distincts, le second suffixé `-2`, avec **deux lignes** ajoutées au manifeste. Le code ouvre le manifeste en ajout ; il ne réécrit pas les lignes antérieures lors de ces appels.
- FEC altéré et FEC disparu, avec manifeste intact : statuts exacts **`modifie` et `absent`**. Ce succès ne couvre pas la perte du manifeste ni l'interface web.
- Le manifeste est un fichier ordinaire modifiable : remplacer ensemble le FEC fictif et son empreinte donne `ok` (`manifeste_modifiable`). Ce test précise la portée du SHA-256 : détection d'écart avec une référence conservée, sans authentification externe de cette référence. Il n'est pas renuméroté comme une attaque distante.
- Une collision de nom de dossier est refusée. `slug_sur('../ailleurs')` vaut **false**. L'adoption après perte du registre conserve **800 €** ; le renommage ne déplace pas la base. L'entrée intacte pointant une base disparue donne **409**, sans recréation.
- Deux entrées JSON explicitement injectées avec le même chemin donnent `meme_base=true`. Le créateur normal n'a pas produit ce doublon : aucun constat de collision spontanée n'en est déduit. Le registre n'est ni un inventaire automatique du disque ni une sauvegarde de celui-ci.

### Démarrage et migrations : limites des protections annoncées

- Injection de `OSError(28, 'Disque fictif plein')` dans la sauvegarde quotidienne appelée par le bloc réel de démarrage : exception propagée, **`serveur_lance=false`**. Le logiciel ne démarre donc pas quand même dans ce scénario. Il ne masque pas cet échec en succès ; une traceback n'est cependant pas un message web. La panne disque physique n'a pas été provoquée.
- Base future version 99, appel direct à `migrations.migrer` : **avant=99, après=99, sauvegarde=null**, empreinte inchangée. La restauration O-08 n'a pas ce garde préalable.
- **Q-10 confirmé, sans nouveau numéro :** base version 2, suppression des comptes 675/775, échec injecté à l'entrée du palier 5 : version durable **2**, les **deux comptes** des paliers précédents persistent et **une copie préalable** existe. La migration n'est pas entièrement annulée, mais sa version n'est pas marquée à tort comme terminée.
- **Assertion des paliers : diagnostic corrigé.** Les paliers 2 à 7 actuels sont présents. En simulant explicitement une évolution à la version **8 sans écrire son palier**, l'import normal échoue en `AssertionError` ; sous **`python -O`**, l'appel réussit, code **0**, et marque effectivement la base **8**. Ce n'est pas un défaut de palier absent dans la version livrée : c'est la limite exécutée du garde présenté dans le récapitulatif B comme rendant l'omission impossible. Le contrôle doit aussi exister à l'exécution si ce contrat est voulu en mode optimisé.
- **Q-05 demeure une réserve distincte** : la collision des copies de sûreté à la seconde est déjà documentée, pas une découverte O. La passe K documente aussi le traitement d'un échec d'archivage après clôture ; il n'est pas renuméroté ici.

### Copies et sorties du dossier

Revue ciblée des chemins de sauvegarde, archive, PDF, import et journal, complétée par `sorties_locales` :

| Chemin | Résultat et portée |
|---|---|
| Sauvegarde SQLite | Sous `sauvegardes/` du dossier ; aucune destination réseau dans ce mécanisme |
| Archive FEC et manifeste | Sous `archives/` du dossier ; fichiers effectivement écrits et relus |
| PDF web, `liasse_pdf_route`, app.py:1387 | Réponse **200**, signature **`%PDF`** ; buffer mémoire, aucun PDF temporaire observé par le traceur des ouvertures Python |
| Préparation d'import, `_dossier_imports`, app.py:1821 | Répertoire effectivement créé sous le dossier actif, pas dans le répertoire temporaire global |
| Journal, `_journal_erreurs`, app.py:253 | Destination locale `logs/erreurs.log` à côté de la base, rotation 512 000 octets × 3 ; revue de structure ici, contenu fictif déjà exécuté en Q |
| Audit de cycle, `audit_cycle.executer`, modules/audit_cycle.py:474 | Usage d'un répertoire temporaire, mais création en **mode blanc**, pas copie de la comptabilité réelle ; revue de structure, sans relancer cet audit dans O |
| Téléchargements | FEC et PDF sont transmis au navigateur à la demande ; leur destination finale dépend du navigateur |

Dans l'essai regroupant sauvegarde, PDF, import et archivage, les connexions réseau par `socket.connect` étaient interdites et tracées : **zéro appel**. L'inventaire des ouvertures Python ne trace pas toutes les écritures internes de SQLite ; il n'est pas présenté comme une surveillance complète du système. Aucun envoi automatique de sauvegarde ni destination synchronisée imposée n'a été trouvé dans ces chemins. Le journal peut contenir le texte d'une exception, donc des informations saisies ; ce point déjà établi en Q n'est pas une preuve de copie intégrale de la base.

## Gestes et possibilité de retour

| Geste | Retour possible ? | Ce que l'utilisateur apprend |
|---|---|---|
| Initialiser sur une base existante sans `ecraser` | Aucune modification à annuler | Refus explicite vérifié |
| Restaurer une copie ordinaire saine | Oui, copie de sûreté ; retour exécuté | Succès et mention de cette copie |
| Restaurer alors que la source entre dans la purge | Oui par le moteur, retour exécuté ; interface en erreur | Faux succès initial, puis table manquante (O-03) |
| Restaurer une sauvegarde avec version future | Copie de sûreté disponible, intervention hors parcours bloqué nécessaire | Succès, puis 409 (O-08) |
| Restaurer avant une clôture/année suivante | Oui si copie de sûreté conservée ; ancienne base globalement sauvegardée | Pas de lien explicite avec les archives restées sur disque (O-10) |
| Deux restaurations dans la même seconde | Pas garanti : réserve Q-05 | Copies susceptibles de partager le même nom |
| Purger les ordinaires au-delà du quota | Les fichiers purgés n'ont pas de corbeille applicative | Aucun bilan de fichiers purgés retourné par `sauvegarder` |
| Perdre/corrompre le registre | Bases intactes ; adoption par nom testée | Repli silencieux sur le principal (O-09) |
| Supprimer un FEC ou son manifeste hors application | Une empreinte ne reconstitue pas le fichier ; copie externe nécessaire | FEC absent détecté seulement si sa ligne reste lisible (O-05) |
| Migration interrompue | Copie préalable disponible ; état courant potentiellement partiel | Version non avancée ; réserve Q-10 sur la garde web |

## Non vérifiable avec les pièces fournies

- Une coupure électrique réelle, un stockage saturé pendant backup, les permissions Windows ou un montage réseau qui se déconnecte produisent-ils les mêmes garanties d'atomicité et de lisibilité que les essais SQLite locaux ?
- Le lanceur visible par l'utilisateur conserve-t-il assez longtemps la traceback de démarrage pour comprendre le refus dû à un disque plein ou non accessible ?
- Quels quotas, outils de synchronisation et sauvegardes externes protègent réellement le dossier de l'utilisateur, son registre et ses archives sur six ans ? Une copie à côté de la base ne permet pas d'établir cette protection.
- Après sinistre, existe-t-il une procédure documentée de reconstruction du registre à partir des répertoires retrouvés, sans connaître les noms d'affichage antérieurs ?
- Quelle archive a effectivement été transmise avec chaque déclaration, et quelle règle doit distinguer une archive conservée pour historique d'une archive qui la remplace ? Le manifeste seul ne répond pas à cette question.
- Des copies historiques ou des journaux réels contiennent-ils des données privées hors des emplacements recensés ? Leur contenu n'a pas été inspecté ; aucune conclusion de propreté historique n'est possible.
- Où le navigateur enregistre-t-il les téléchargements, et ces destinations sont-elles synchronisées ou sauvegardées ? Ce réglage est extérieur aux fichiers examinés.
- Les créations concurrentes de dossiers, les archivages concurrents et une écriture concurrente entre la copie de sûreté et le remplacement sont-ils sérialisés par un mécanisme extérieur ? O teste les séquences décrites, pas tous ces entrelacements.
- Pour les vingt anciens constats D-10 à D-29 indiqués comme perdus dans les récapitulatifs antérieurs, existe-t-il des pièces permettant une comparaison précise avec ces scénarios ?

## Tableau récapitulatif numéroté

| N° | Constat | Conséquence reproduite | Gravité |
|---|---|---|---|
| O-01 | Copie corrompue retournée comme réussie | Sauvegarde des 800 € illisible | majeur |
| O-02 | Fichier quotidien vide tenu pour suffisant | Pas de nouvelle sauvegarde des 800 € | majeur |
| O-03 | Source de restauration supprimée par la rotation | Base sans table ; 800 € récupérables par le moteur | majeur |
| O-04 | Appartenance fondée seulement sur le répertoire | Dossier A remplacé : 1 600 → 2 500 € | majeur |
| O-05 | Manifeste absent ou tronqué sans alerte complète | Preuve manquante omise du résultat | majeur |
| O-06 | Archive altérée téléchargeable sans signal | Document altéré servi en HTTP 200 | majeur |
| O-07 | Cache de migration conservé après restauration | Version 6 ouverte sans compte du palier 7 | majeur |
| O-08 | Version future installée avant refus | Succès de restauration puis dossier bloqué en 409 | majeur |
| O-09 | Registre illisible changé en liste vide | Dossier de 800 € masqué, sélection du principal | majeur |
| O-10 | Archives non rattachées à l'histoire restaurée | Deux FEC intègres de 800 et 1 800 € sans lien de substitution | majeur |

**État du suivi :** les constats de cette passe ont été corrigés en production le 16 septembre 2026 (version 8.48.0). Les preuves de `preuves_o/` sont conservées **telles qu'observées avant correction** : elles restent la référence du défaut, pas de l'état actuel du code. La non-régression est figée par `tests/test_passe_o.py`.
