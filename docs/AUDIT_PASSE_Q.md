# Audit — passe Q : atomicité, concurrence et exceptions

Date : 15 septembre 2026. Code examiné : `compta_lmnp/`.

Rapport préexistant repris et vérifié le 15 septembre 2026 : les scénarios ont été réexécutés sur le code présent, avec sortie globale 0. Les douze constats ci-dessous restent reproduits ; leur numérotation est conservée. L'inventaire et les résultats ont été régénérés. [Vérification des résultats](preuves_q/verifier.py) et [empreintes SHA-256 du code examiné](preuves_q/code_examine.json) complètent les preuves. Ces empreintes identifient uniquement les sources Python applicatives, sans lire les bases, les FEC privés ni le seed d'identité.

**Douze constats reproduits, dont quatre critiques.** Les plus graves portent sur la double annulation, une écriture ajoutée après clôture, la perte de la copie de sûreté d'une restauration et le double import après une erreur de nettoyage.

## Méthode et pièces

Lecture préalable de la règle 2 de `docs/audit/00-INVARIANTS.md`, du CHANGELOG et des récapitulatifs et suivis D2, E et F. Ces rapports et leur synthèse sont supprimés dans l'arbre de travail fourni ; leur contenu a été consulté par `git show HEAD:…`, sans restaurer ni modifier ces suppressions. Les choix comptables exclus par la demande ne sont pas des constats.

Toutes les bases sont créées en **mode blanc**, avec un exploitant et des locataires fictifs. Aucun FEC réel, seed privé ou journal personnel n'est utilisé. Le code de production n'a pas été modifié.

Pièces reproductibles :

- [Script d'exécution](preuves_q/reproduire.py), créant puis supprimant ses bases temporaires.
- [Résultats complets](preuves_q/resultats.json), avec les valeurs observées.
- [Inventaire des commits et scripts SQL](preuves_q/inventaire.json), extrait de tous les fichiers Python applicatifs, hors dépendances et tests.
- [Annexe de couverture](preuves_q/COUVERTURE.md), classement de chaque commit, exceptions et courses examinées.

Commande depuis la racine du dépôt :

```bash
compta_lmnp/.venv/bin/python docs/preuves_q/reproduire.py
```

Exécution retenue : Python **3.14.6**, SQLite **3.51.2**, Flask de l'environnement local. Un premier essai avec le Python système a signalé l'absence de Flask ; tous les scénarios ont ensuite été rejoués avec le bon interpréteur. Le script échoue explicitement si un scénario ne peut pas s'exécuter.

Les courses utilisent deux connexions et de vrais threads ; des barrières arrêtent un appel à un endroit identifié pour imposer un entrelacement reproductible. Elles établissent la possibilité de cet entrelacement, pas sa fréquence. Les vues web s'exécutent dans des contextes Flask de requête, avec la résolution du chemin redirigée vers une base fictive. Le parseur bancaire est remplacé par des propositions connues dans les tests de transaction : sa reconnaissance des relevés n'est pas réauditée ici. Les pannes injectées sont identifiées ci-dessous. Aucun constat ne repose uniquement sur une recherche textuelle.

Les montants indiqués sont des écarts comptables, de justificatifs ou de données récupérables ; ils ne constituent pas un calcul d'impôt personnel.

## Constats

### Q-01 — Lire les quittances valide la transaction de l'appelant

**Gravité : majeur.**

**Fichiers et fonctions :** `modules/quittances.py`, `assurer_schema`, lignes **53–56** ; `locataires`, ligne **111** ; `prochain_numero`, ligne **129** ; `lister`, ligne **269**.

**Scénario :** dans une base blanche configurée pour 2026, ouvrir une transaction, insérer un témoin de valeur 800, appeler successivement chacun des lecteurs sur une base indépendante, puis exécuter `rollback()` et compter le témoin. Refaire avec un véritable loyer de **800 €**, saisi par `operations.saisir(commit=False)`, puis `quittances.lister` et rollback.

**Attendu :** transaction toujours ouverte après la lecture, zéro témoin et zéro loyer après rollback.

**Produit :** pour `assurer_schema`, `locataires`, `lister` et `prochain_numero` :

```text
transaction_apres=false ; commits=1 ; commit_sql=1 ; temoins=1
lecture_loyer_durable : operations=1 ; montant=800.0
```

**Cause confirmée :** `executescript(SCHEMA)` valide déjà la transaction avant le `conn.commit()` explicite. Conditionner seulement ce dernier ne suffirait donc pas. Le défaut existe même lorsque les tables sont déjà présentes.

**Conséquence :** **800 € restent enregistrés malgré l'annulation demandée par l'appelant**. Il n'est pas établi que l'import bancaire courant passe par ce lecteur ; ce constat ne remet pas en cause son correctif D2 testé séparément. Le contrat de composition avec ces lecteurs est néanmoins rompu.

### Q-02 — Deux annulations simultanées annulent deux fois le même loyer

**Gravité : critique.**

**Fichiers et fonctions :** `modules/operations.py`, `annuler`, ligne **350**, lecture et contrôle du marqueur à **365–371**, insertion à **389** ; `modules/ecritures.py`, `inserer`, ligne **98**.

**Scénario :** saisir un loyer de **800 €** le 10 janvier 2026. Deux connexions appellent `annuler` pour son identifiant. La barrière, placée à l'entrée d'`ecritures.inserer`, garantit que les deux ont lu le marqueur « non annulée ». Laisser les deux terminer.

**Attendu :** une contre-passation, un refus sur la seconde demande, solde du compte de loyers **0 €**.

**Produit :**

```text
deux retours réussis : ecriture_annulation=3 et ecriture_annulation=2
ecritures=3 ; loyers=-800.0
```

**Conséquence :** le loyer est contre-passé deux fois ; les produits sont minorés de **800 €** par rapport à l'annulation correcte. Les deux écritures sont équilibrées : l'équilibre débit/crédit ne révèle pas l'erreur. Le verrou pris par l'insertion sérialise les écritures, mais ne fait pas relire le marqueur contrôlé avant le verrou.

### Q-03 — Une écriture peut être ajoutée après la clôture sans actualiser le résultat figé

**Gravité : critique.**

**Fichier et fonction :** `modules/ecritures.py`, `inserer`, lecture du statut à **134**, verrou à **157–163**, insertion à **181**.

**Scénario :** un exercice 2026 contient **800 €** de loyer. Une seconde connexion commence l'insertion d'un autre loyer de **800 €** et est suspendue juste après avoir obtenu le statut `ouvert`. La première connexion clôture l'exercice, sans génération de dotation. La seconde reprend ensuite son insertion.

**Attendu :** refus de la seconde écriture, ou clôture intégrant les deux loyers. Aucune divergence entre résultat enregistré et écritures d'un exercice clos.

**Produit :**

```text
retour : ecriture_id=2 ; ecriture_num=2
exercice : ["clos", 800.0]
produits : 1600.0
```

**Conséquence :** **800 € d'écart** entre le résultat comptable figé et les écritures servant aux exports. La protection contre deux clôtures simultanées tient ; elle ne couvre pas cette course entre une clôture et une saisie. Le contrôle de statut de l'insertion précède le verrou et n'est pas refait après son acquisition.

### Q-04 — Deux quittances parallèles contournent le contrôle par logement

**Gravité : majeur.**

**Fichier et fonctions :** `modules/quittances.py`, `emettre`, ligne **180**, contrôle des concurrentes à **219**, numéro et insertion à **255–263** ; `prochain_numero`, ligne **129**.

**Scénario :** deux locataires fictifs occupent le même bien depuis le 1er janvier 2026 ; un seul loyer de **800 €** est encaissé pour janvier. Les deux demandes franchissent le contrôle d'absence de quittance. Suspendre la seconde avant le calcul du numéro jusqu'à ce que la première ait terminé ; reprendre ensuite la seconde.

**Attendu :** une seule quittance de **800 €** ; la seconde demande rencontre le refus prévu pour un logement déjà quittancé.

**Produit :**

```text
premier retour : numero=1 ; total=800.0
second retour : numero=2 ; total=800.0
nombre=2 ; total=1600.0
```

**Conséquence :** **800 € de trop attestés à des tiers**. Le correctif de la passe B fonctionne en séquentiel ; le cas nouveau est son contournement concurrent. La contrainte `(locataire_id, periode)` ne protège pas l'unicité par logement.

**Autre entrelacement exécuté :** si les deux lisent le même maximum avant l'insertion, une seule quittance subsiste, mais l'autre demande reçoit `UNIQUE constraint failed: quittance.numero`. Cette variante n'a pas créé de double montant ; elle est incluse ici, sans constat supplémentaire.

### Q-05 — Deux restaurations à la même seconde effacent l'état de sûreté initial

**Gravité : critique.**

**Fichier et fonctions :** `modules/perennite.py`, `sauvegarder`, ligne **64**, nom horodaté à **76–78**, copie à **85** ; `restaurer`, ligne **123**, sauvegarde préalable à **184**, restauration à **194**.

**Scénario :** sauvegarder une base contenant un loyer de **800 €**, puis saisir un second loyer de **800 €**. Lancer deux restaurations de cette même sauvegarde. Les deux entrent dans la sauvegarde de sûreté ; la seconde reprend après la fin de la première restauration. L'horloge est fixée à la même seconde pour rendre la collision de nom déterministe. Aucune copie SQLite n'est simulée.

**Attendu :** la restauration laisse les 800 € de la sauvegarde choisie, et une copie de sûreté conserve les **1 600 €** présents avant la première demande.

**Produit :**

```text
meme_copie_surete=true
avant=2 ; apres=1 ; copie_surete=1
```

Ces compteurs portent sur les opérations de 800 €. Les deux appels réussissent et retournent le même chemin. La seconde sauvegarde remplace la première par l'état déjà restauré.

**Conséquence :** le second loyer de **800 €** disparaît aussi de la copie censée permettre le retour en arrière. Dans ce scénario, ni la sauvegarde source ni la copie de sûreté finale ne le conservent. L'intégrité structurelle SQLite reste compatible avec cette perte de données.

### Q-06 — Un appel de charges échoué conserve ses premières composantes

**Gravité : majeur.**

**Fichier et fonctions :** `modules/operations.py`, `saisir_appel_charges`, ligne **272**, liste d'appels à **307–310** ; `saisir`, commit à **95**. Le point d'entrée web est `app.py`, `saisir_appel`, ligne **682**.

**Scénario :** appeler la ventilation du 10 janvier 2026 avec charges courantes **600 €**, fonds ALUR **100 €**, travaux `float('inf')` — valeur non finie, également obtenue par la conversion numérique de `1e309`. L'erreur survient sur la troisième composante. Faire un rollback puis compter.

**Attendu :** rejet de l'appel entier ; zéro opération et zéro écriture.

**Produit :**

```text
erreur="Montant invalide : inf."
operations=2 ; ecritures=2 ; montant=700.0
```

**Conséquence :** **700 € de charges comptables persistent** pour un appel annoncé en erreur. Chaque composante utilise le commit par défaut. Une relance complète n'est donc pas sûre. Les 100 € d'ALUR ont leur traitement propre : les 700 € ne sont pas présentés comme une déduction fiscale intégrale.

### Q-07 — Une acquisition refusée laisse son composant enregistré

**Gravité : majeur.**

**Fichier et fonction :** `app.py`, `creer_composant`, ligne **837**, insertion à **868**, commit à **875**, acquisition à **905**, traitement d'erreur à **912**.

**Scénario :** exécuter la vue avec bien 1, mobilier fictif, valeur **12 000 €**, durée 10 ans, compte `218400`, date de mise en service `2026-02-30`, génération de l'écriture activée. L'exercice 2026 est ouvert.

**Attendu :** rejet de la date avant toute persistance ; aucun composant ni écriture.

**Produit :**

```text
err="Date d'écriture invalide : '2026-02-30' (format attendu AAAA-MM-JJ)."
composants=1 ; ecritures=0 ; valeur=12000.0
```

**Conséquence :** le référentiel contient **12 000 €** d'immobilisation sans écriture d'acquisition correspondante, avec une date invalide durable. Le message d'erreur ne dit pas qu'une partie est enregistrée. La ventilation groupée `immo_ventiler` dispose d'un autre chemin ; ce constat vise l'ajout unitaire réellement exécuté.

### Q-08 — L'échec du nettoyage d'un import validé conduit à le saisir deux fois

**Gravité : critique.**

**Fichier et fonction :** `app.py`, `import_valider`, ligne **1892**, commit à **1921**, suppression à **1931**, message d'échec à **1935–1936**.

**Scénario :** dix propositions de loyers fictifs de **800 €**, toutes cochées. Laisser les dix insertions et le commit s'exécuter. Injecter un `PermissionError` uniquement sur la suppression du CSV temporaire. Relancer avec le même jeton et les mêmes propositions, cette fois sans panne.

**Attendu :** succès de l'import annoncé malgré l'échec du nettoyage, et absence de double enregistrement lors d'une relance du même lot.

**Produit :**

```text
err="Import interrompu : suppression fictive refusée"
operations_apres_erreur=10
ok="Import terminé : 10 opération(s) enregistrée(s), 0 écartée(s)."
operations_apres_relance=20 ; montant=16000.0
```

**Conséquence :** **8 000 € de recettes supplémentaires** après la relance. Ce n'est pas le défaut D2 d'interruption dans la boucle : le rollback à la septième ligne tient. La panne nouvelle se situe **après** le commit, dans le même bloc qui annonce l'échec.

### Q-09 — Une reprise multi-FEC échouée conserve le premier exercice et supprime la préparation

**Gravité : majeur.**

**Fichiers et fonctions :** `app.py`, `exercice_reprendre_fec_multi`, ligne **1990**, boucle à **2011**, rollback à **2034**, suppression à **2040** ; `modules/rejeu_fec.py`, `rejouer`, commit à **110**.

**Scénario :** préparer deux FEC fictifs, chacun portant deux loyers de **800 €**, pour 2024 et 2025. Dans la deuxième écriture de 2025, remplacer le crédit de 800 par **801 €**. Exécuter la reprise multiple dans une base qui ne contient initialement que l'exercice vide 2026.

**Attendu :** soit retour à l'état initial, soit bilan explicite de reprise partielle nommant l'exercice conservé et possibilité de reprendre la préparation restante.

**Produit :**

```text
err="Reprise interrompue : Écriture déséquilibrée : débit 800.00 € / crédit 801.00 €."
exercices=[2024,2026] ; ecritures=2 ; source_temporaire=false
```

**Conséquence :** **1 600 €** de recettes 2024 sont durablement repris alors que l'action globale se termine en erreur ; le dossier temporaire contenant les deux fichiers est supprimé. La source originale détenue par l'utilisateur n'est pas supprimée. La protection contre les exercices déjà présents évite une duplication automatique de 2024 ; le défaut est l'état partiel non détaillé et la préparation détruite, pas un double import démontré.

### Q-10 — Une migration partielle peut échouer sans que la garde web bloque l'accès

**Gravité : majeur.**

**Fichiers et fonctions :** `modules/migrations.py`, `migrer`, ligne **100**, boucle à **109** ; `_palier_4`, ligne **45** ; `modules/init_db.py`, `creer_index`, ligne **317**, commit à **320** ; `app.py`, `_migrer_si_besoin`, ligne **121**, exception à **142–143** ; `_garde_version_schema`, ligne **207**.

**Scénario A :** base fictive marquée version 2, comptes de cession absents. Exécuter les paliers 3 et 4, puis injecter un échec à l'entrée du palier 5. Fermer et rouvrir la base. Le test isolé du témoin confirme également que `creer_index` valide une transaction ouverte.

**Scénario B :** sur une base marquée version 2, faire lever `RuntimeError('migration fictive impossible')` par la migration appelée depuis la garde web.

**Attendu :** soit migration annulée, soit état intermédiaire explicite et accès métier bloqué jusqu'à une migration réussie.

**Produit :**

```text
migration_interrompue : version=2 ; comptes_cession=2 ; sauvegardes=1
garde_migration_echec : retour=null ; version=2 ; memorise=false
```

`null` signifie ici que la garde ne retourne aucune réponse de refus et laisse la requête continuer. La version n'est pas faussement élevée ; la sauvegarde existe ; ces deux protections sont conservées.

**Conséquence :** le déclarant peut accéder à une base partiellement migrée sans message de la garde. Pas de perte monétaire établie dans cet essai ; le problème confirmé est l'échec silencieux sur un schéma non terminé. Le verrou ajouté en D2 sur le test/ajout de `_MIGRES` n'est pas remis en cause par cet énoncé : il ne traite pas cette exception avalée.

### Q-11 — L'ouverture avec reprise refusée laisse le nouvel exercice ouvert

**Gravité : majeur.**

**Fichier et fonction :** `app.py`, `exercice_ouvrir`, ligne **1320**, commit à **1335**, reprise à **1342**, message d'erreur à **1351**. Mécanisme analogue à examiner côté API : `modules/reprise.py`, `ouvrir_exercice`, ligne **176** ; le résultat ci-dessous porte sur la vue web.

**Scénario :** 2026 existe et reste ouvert. Demander 2027, du 1er janvier au 31 décembre, en cochant la reprise des à-nouveaux.

**Attendu :** refus avant création, ou annonce explicite « exercice créé, reprise non effectuée ».

**Produit :**

```text
err="L'exercice 2026 n'est pas clôturé : clôturez-le avant d'ouvrir avec reprise des à-nouveaux."
exercices=2 ; ecritures=0
```

**Conséquence :** l'exercice 2027 existe déjà, sans reprise, alors que l'instruction invite à recommencer après clôture de 2026. Aucun écart en euros n'est mesuré sur cette base vide ; l'état de l'ouverture ne correspond pas à l'action demandée et n'est pas annoncé.

### Q-12 — Un premier import annulé n'est pas conservé dans le journal persistant

**Gravité : mineur.**

**Fichier et fonctions :** `app.py`, `import_valider`, journalisation à **1924** ; `_journal_erreurs`, ligne **253** ; `_erreur_globale`, initialisation paresseuse à **285–289**.

**Scénario :** processus Flask sans incident antérieur ; dix propositions de 800 €, avec une valeur non finie à la septième. Exécuter la vue d'import, puis chercher `logs/erreurs.log` dans le répertoire fictif. Aucun gestionnaire de fichier n'est préinstallé par le test.

**Attendu :** conservation de l'annulation et de son rang dans le journal persistant prévu pour le diagnostic.

**Produit :**

```text
Import ANNULÉ à la ligne 7 sur 10
operations=0 ; journal_persistant=false
```

La trace apparaît bien sur la sortie d'erreur du processus. Elle n'est pas écrite dans le fichier de journal, car ce chemin d'erreur gérée ne déclenche pas son initialisation.

**Conséquence :** après fermeture du lanceur, cet incident ne dispose pas de la trace persistante attendue pour un diagnostic ultérieur. **Aucune perte comptable** dans cet essai : le rollback est complet.

## Ce qui a été vérifié et tenu

- **Lecteurs nommés :** témoin inséré dans une transaction, appel, rollback, comptage. `cession.assurer_schema`, `fiscal._table_39c_bien`, `operations.assurer_colonne_annulee`, `gabarits.assurer_table`, `parametres.assurer` et les trois chemins de veille testés laissent la transaction ouverte : **zéro commit, zéro témoin durable**. Ils ne sont pas assimilés au défaut des quittances.
- **Tous les gabarits recensés dynamiquement :** 43 standards et un personnalisé, deux saisies de 800 € avec `commit=False` pour chacun : transaction ouverte, puis **zéro opération et zéro écriture après rollback**. Un appel de commit d'initialisation est observé avant la transaction de la première saisie ; il ne conserve aucune des deux opérations. Le scénario avec une règle ALUR versionnée, un témoin préalable et calcul du retraitement produit **zéro commit et zéro témoin durable**.
- **Clôture :** un loyer de 800 € et un composant de 12 000 € amorti sur dix ans : **un seul appel à `conn.commit()`**. Une exception après les premières écritures, suivie de fermeture/réouverture, laisse l'exercice ouvert, le seul loyer initial et aucun suivi 39 C. Un arrêt brutal de processus par `os._exit(77)` au même stade, sans fermeture Python, produit aussi `statut=ouvert`, `ecritures=1`, `suivi=0`, `integrite=ok` après réouverture. Cela éprouve l'arrêt du processus, pas une panne matérielle du disque.
- **Deux clôtures simultanées :** une réussite, un refus explicite « déjà clos », **une seule dotation**. Ce succès n'est pas étendu à la course saisie/clôture de Q-03.
- **Numérotation des écritures :** quatre threads, cinq loyers chacun : **20 opérations, 20 écritures, numéros 1 à 20 sans doublon**. La cinquième collision forcée sur le numéro 1 lève bien `IntegrityError` après **cinq tentatives**, sans nouvelle écriture. La transaction reste ouverte jusqu'à sa fermeture par l'appelant ; aucun succès fictif ni rejeu infini observé. Ce forçage teste la borne, pas une collision naturelle sous `BEGIN IMMEDIATE`.
- **Savepoint :** seul `ecritures.inserer` en utilise dans le code applicatif inventorié. Les scénarios `commit=False` confirment que son `RELEASE` ne valide pas les saisies. Un essai supplémentaire insère un témoin, puis tente une écriture équilibrée de 800 € dont la seconde ligne vise le compte absent `799999`. Après `FOREIGN KEY constraint failed`, un commit volontaire conserve le témoin mais **zéro en-tête et zéro ligne comptable** : le savepoint protège bien contre la persistance d'une écriture incomplète, sans annuler le travail antérieur de l'appelant.
- **Attente SQLite :** `PRAGMA busy_timeout` rend **5 000 ms** avec la connexion utilisée. Un verrou concurrent conservé provoque `database is locked` après **5,0 s**, pas immédiatement. L'absence d'une instruction explicite `PRAGMA busy_timeout` dans `_conn` ne signifie donc pas absence d'attente. Aucun constat d'absence de timeout n'est retenu.
- **Import bancaire interrompu à la septième proposition :** **zéro opération durable**, message d'annulation explicite. Le correctif D2 tient pendant la boucle.
- **Rejeu d'un seul FEC :** interruption injectée à la deuxième écriture : **zéro écriture, transaction fermée** par le rollback interne. Ce résultat ne s'étend pas à la boucle multi-exercices Q-09.
- **À-nouveaux et cession :** interruption injectée avant la deuxième écriture : une première écriture est visible dans la connexion, **zéro après fermeture et réouverture**. L'appelant doit bien fermer ou annuler : ces deux fonctions ne sont pas présentées comme effectuant elles-mêmes un rollback sur toute exception.
- **Migration :** la sauvegarde préalable existe et la version reste 2 après l'échec. Le diagnostic ne prétend pas qu'elle serait marquée 7.
- **Journal :** après initialisation explicite, une exception contenant un nom et un montant entièrement fictifs les conserve dans le fichier. Le journal doit donc être traité comme susceptible de contenir des informations comptables et personnelles ; aucune valeur réelle n'a été lue pour établir ce comportement. Son caractère local n'est pas présenté comme un défaut.

## Non vérifiable avec les pièces fournies

- Quels étaient précisément les vingt constats D-10 à D-29, dont le récapitulatif fourni indique la perte, et recoupaient-ils certains scénarios nouveaux de cette passe ?
- Sur les environnements réellement distribués autres que Python 3.14.6 / SQLite 3.51.2, les mêmes entrelacements et délais d'attente produisent-ils les mêmes résultats ?
- Une coupure électrique physique, les options de montage et les garanties de synchronisation du support préservent-elles l'atomicité observée lors de l'arrêt brutal du processus ?
- Des journaux historiques réels contiennent-ils déjà des identités ou montants, et quelle politique de sauvegarde/protection locale leur est appliquée ? Leur contenu privé n'a pas été inspecté.
- Pour les chemins marqués « lecture seule de la structure » dans l'annexe, que produit l'injection de chaque panne de rendu, de fermeture, de rollback ou de suppression secondaire ? Une revue des blocs `except` ne suffit pas à certifier chacune de ces combinaisons ; seules les exécutions identifiées fondent les constats.
- Les modifications concurrentes du registre des dossiers et la réinitialisation simultanée du bac à sable ont-elles une sérialisation externe aux fichiers examinés ? Ces autres motifs « tester puis agir » sont recensés dans l'annexe, sans constat de perte non reproduit.
- Que produit une requête métier arrivant pendant qu'une autre termine sa migration, notamment si la première échoue ? La garde d'échec a été exécutée ; tous les entrelacements de migration et d'accès métier n'ont pas été éprouvés.
- Quelle politique est attendue pour une reprise multi-exercices partiellement réussie : annulation globale ou compte rendu des exercices conservés ? Q-09 établit la persistance et le message actuels, sans imposer que tous les exercices partagent nécessairement une transaction.

## Tableau récapitulatif numéroté

| N° | Constat | Conséquence observée | Gravité |
|---|---|---|---|
| Q-01 | Lecture des quittances qui valide | 800 € persistent après rollback | majeur |
| Q-02 | Double annulation concurrente | Produits minorés de 800 € | critique |
| Q-03 | Saisie après clôture | 800 € d'écart avec le résultat figé | critique |
| Q-04 | Double quittancement concurrent | 1 600 € attestés pour 800 € | majeur |
| Q-05 | Copies de sûreté de restauration écrasées | 800 € perdus aussi du retour arrière | critique |
| Q-06 | Appel de charges partiellement validé | 700 € persistent après erreur | majeur |
| Q-07 | Composant conservé sans acquisition | 12 000 € au référentiel sans écriture | majeur |
| Q-08 | Import annoncé échoué après son commit | 8 000 € de recettes en double à la relance | critique |
| Q-09 | Reprise multiple partielle, préparation supprimée | 1 600 € conservés sans bilan de reprise partielle | majeur |
| Q-10 | Migration partielle, garde muette sur l'échec | Accès autorisé au schéma non terminé | majeur |
| Q-11 | Ouverture conservée malgré reprise refusée | Exercice vide créé sans annonce de succès partiel | majeur |
| Q-12 | Premier import annulé sans journal de fichier | Incident non conservé après fermeture du lanceur | mineur |

Aucun correctif de production appliqué dans cette passe. Les sorties reproductibles constituent l'état de référence avant correction.

**État du suivi :** les douze constats ont été corrigés en production le 16 septembre 2026 (version 8.50.0). Les preuves de `preuves_q/` sont conservées **telles qu'observées avant correction** : elles restent la référence du défaut, pas de l'état actuel du code. La non-régression est figée par `tests/test_passe_q.py` (32 tests), dont 18 échouent si l'on retire les correctifs.

Quatre précisions de méthode. **Le correctif de Q-02, Q-03 et Q-04 tient en un déplacement**, pas en un contrôle nouveau : la lecture d'état passe *après* `BEGIN IMMEDIATE`. Deux tests le prouvent par l'ordre réel des instructions SQL, et non par leur seul effet — un essai séquentiel passerait aussi sur l'ancien code, puisque la clôture ou l'annulation concurrente y est déjà validée quand la lecture a lieu. Corollaire : lorsque le contrôle refuse, il ne défait la transaction que s'il l'a lui-même ouverte, faute de quoi il annulerait la saisie composée d'un appelant qui ne lui a rien demandé.

**Q-08 va dans le sens inverse des autres.** Partout ailleurs cette passe resserre ; ici elle desserre. Le code annonçait une annulation là où le commit était passé, et l'utilisateur relançait un import qui n'avait aucune clé d'idempotence pour le rattraper. Un échec de nettoyage devient donc un avertissement sur un import *réussi* — même raisonnement que pour l'archivage après clôture. La contre-épreuve est explicite dans les tests : un échec pendant la boucle d'insertion reste, lui, une erreur qui annule tout.

**Q-09 conserve la préparation.** Le `finally` effaçait le dossier téléversé y compris quand la reprise échouait : l'action se terminait en erreur et de quoi recommencer avait disparu. La suppression est maintenant conditionnée au succès, et le message dit explicitement que les fichiers restent chargés.

**Q-10 refuse sans enfermer.** La garde bloque l'accès métier à un schéma incomplet, mais la page 409 laisse joignable le retour au dossier principal, et le chemin est retiré des dossiers déjà migrés pour qu'un redémarrage puisse réessayer. Un refus sans issue, avec un cookie de dossier valable 180 jours, rendrait le logiciel inutilisable pour tous les dossiers.

Un mot sur **Q-01**, qui n'est pas un défaut de quittances mais un défaut de *contrat* : `executescript` valide implicitement la transaction en cours, et n'importe quel appelant en `commit=False` pouvait donc voir ses écritures figées par une simple lecture. Le correctif n'a pas rendu ce `executescript` inoffensif : il a supprimé son appel quand il n'y a rien à créer. C'est le même raisonnement que celui appliqué aux autres chemins de lecture du logiciel — lire ne doit jamais écrire.
