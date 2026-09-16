# Passe K — Clôture et continuité pluriannuelle

Audit exécuté le 15 septembre 2026 sur `compta_lmnp/`.

**Trois nouveaux constats : deux majeurs, un mineur.** Sur les deux scénarios instrumentés, la clôture tient son contrat atomique : un seul commit, 74 interruptions SIGKILL, aucune clôture partielle persistante. Les défauts nouveaux concernent la chronologie des clôtures, la reconstruction des à-nouveaux et la précision annoncée par le contrôle de jonction.

## Périmètre et méthode

Les essais utilisent exclusivement des bases temporaires créées vierges et des identités fictives. Aucun FEC réel, aucune base de travail ni aucun fichier d’identité de l’auteur n’est utilisé comme fixture. Le code applicatif n’est pas modifié.

Les récapitulatifs du CHANGELOG et des passes précédentes ont été examinés avant les essais. Les problèmes déjà établis sont rattachés à leurs anciens numéros ci-dessous, sans nouveau constat de même cause. Les choix de contrepartie 108000 et de présentation du résultat LMNP sont respectés.

Preuves : [script d’exécution](preuves_k/reproduire.py), [sorties complètes](preuves_k/resultats.json), [vérification des sorties](preuves_k/verifier.py), [mode d’emploi](preuves_k/README.md). Les clés JSON citées permettent de retrouver chaque scénario. Les numéros de ligne désignent les fichiers sous le répertoire source indiqué ci-dessus ; leurs empreintes sont enregistrées dans `environnement.sha256`.

Les appels applicatifs sont réels. Les substitutions servent à diriger les accès vers les bases fictives, à instrumenter les transactions ou à provoquer une panne déterminée. Pour le web, la vraie fonction de route est exécutée dans un contexte de requête Flask ; cet essai n’est pas un parcours de navigateur avec l’ensemble des traitements avant requête.

## K-01 — Une clôture antérieure peut rendre incohérent un exercice déjà clos

**Gravité : majeur.**

**Localisation :** `modules/fiscal.py`, `cloturer`, ligne 471 ; `modules/reprise.py`, `ouvrir_exercice`, ligne 176. Le contrôle chronologique de clôture recherche les exercices antérieurs encore ouverts, mais ne refuse pas l’ajout puis la clôture d’un exercice antérieur à un exercice déjà clos.

**Scénario reproductible :** créer 2025, enregistrer une immobilisation fictive de 12 000 € et un loyer de 600 €, puis clore sans génération de dotation. Ouvrir ensuite 2024 sans reprise, y saisir 1 000 € de maintenance et clore 2024. Comparer à un dossier où les mêmes mouvements sont saisis et les exercices clos dans l’ordre 2024, puis 2025 avec reprise.

**Attendu :** refuser cette clôture rétroactive tant que la chaîne postérieure n’est pas reconstruite de manière cohérente. Dans le dossier chronologique, les 600 € de bénéfice 2025 consomment 600 € du déficit 2024 ; le revenu imposable est nul et le déficit restant vaut 400 €.

**Produit — exécution `cloture_anterieure_apres_suivante` :**

```text
Ordre 2025 puis 2024 : les deux clôtures sont acceptées.
Clôture 2025 enregistrée : revenu_imposable = 600.0 ; impute_deficits = 0.0
Déficit 2024 après clôture tardive : solde = 1000.0
Ordre 2024 puis 2025 : revenu_imposable = 0.0 ; impute_sur_benefice = 600.0
Déficit restant dans le dossier chronologique : 400.0
```

2025 conserve son statut clos. L’avertissement `AN_ABSENTS` apparaît ensuite, mais il ne refuse pas la clôture antérieure et ne remet pas en cohérence le revenu imposable figé.

**Conséquence pour le déclarant :** le revenu imposable mémorisé pour 2025 est supérieur de **600 €** à celui obtenu chronologiquement ; le stock de déficits est également supérieur de **600 €**. Ce sont deux représentations incompatibles de la même imputation. Le montant d’impôt effectivement payé dépend du report effectué dans la déclaration ; l’essai ne le chiffre pas. Le résultat fiscal avant imputation reste bien de 600 € dans les deux dossiers : il ne faut pas le confondre avec le revenu imposable après déficits.

## K-02 — Supprimer seulement les AN puis les reconstruire double l’affectation du résultat

**Gravité : majeur.**

**Localisation :** `modules/reprise.py`, `construire_an_interne`, ligne 64, et `_construire_an_depuis_balance`, ligne 97. La détection de reprise existante ne recherche que le journal AN ; l’OD d’affectation survivante n’est pas reconnue comme une reprise partiellement supprimée.

**Scénario reproductible :** clore 2025 avec une immobilisation de 12 000 € et un bénéfice de 600 €, sans dotation. Ouvrir 2026 avec reprise. Supprimer manuellement par SQL l’écriture AN de 2026, en conservant l’OD d’affectation ; les clés étrangères sont activées et les lignes AN sont supprimées en cascade. Appeler à nouveau `construire_an_interne`. Clore ensuite 2026 sans activité et tenter d’ouvrir 2027.

Il s’agit explicitement du geste de suppression manuelle demandé dans cette passe, sur un exercice **ouvert**. Aucun bouton de suppression d’AN dans l’interface n’est supposé.

**Attendu :** détecter l’OD résiduelle et refuser la reconstruction partielle, ou reconstruire le lot AN + affectation sans doublon. Après une reprise correcte, le solde 120000 est nul et le crédit 108000 vaut 12 000 €.

**Produit — exécution `suppression_an_reconstruction` :**

```text
Deuxième reprise avant suppression : refus « contient déjà des à-nouveaux ».
Après suppression de l’AN : reconstruction acceptée.
Nombre d’OD « Affectation du résultat » : 2
Avant : 108000 = -12000.0 ; 120000 = 0.0
Après : 108000 = -12600.0 ; 120000 = 600.0
Contrôles de 2026 : []
Ouverture 2027 : ValueError: Écriture déséquilibrée : débit 12000.00 € / crédit 12600.00 €.
```

**Conséquence pour le déclarant :** **600 € d’affectation sont comptabilisés deux fois** ; le FEC conserve des soldes 108000 et 120000 erronés, puis la prochaine reprise est bloquée. L’équilibre global ne détecte pas la double OD, qui est elle-même équilibrée. L’erreur de 2027 apparaît lorsque le solde résiduel 120000 est exclu des comptes repris.

**Limite du diagnostic :** cet essai ne montre pas une variation immédiate de 600 € du résultat fiscal ou du bilan synthétique, qui ne reprend pas directement ces deux soldes. Le témoin sans composants présente déjà `conforme=False` avant la suppression ; ce drapeau ne prouve donc pas la détection du doublon. Le maintien du nouvel exercice après une reprise échouée relève du constat Q-11, et n’est pas renuméroté ici.

## K-03 — Une jonction déclarée exacte masque des écarts d’un centime

**Gravité : mineur.**

**Localisation :** `modules/migration_fec.py`, `controler_jonctions`, ligne 140.

**Scénario reproductible :** exporter le cycle fictif 2024–2026 décrit plus bas. Dans les AN du FEC 2025, augmenter de 0,01 € le débit 218400 et de 0,01 € le crédit 108000. Le fichier reste équilibré. Comparer les FEC 2024 et 2025 avec la tolérance par défaut, puis avec `tolerance=0`.

**Attendu :** rendre les écarts visibles, éventuellement comme écarts tolérés. Une tolérance peut être un choix de contrôle ; son application ne doit pas être présentée comme une égalité au centime.

**Produit — exécution `jonction_un_centime` :**

```text
218400 : 12000.00 → 12000.01
108000 : -12300.00 → -12300.01
Contrôle par défaut : type = ok
« Jonction 2024 → 2025 : les bilans se raccordent au centime. »
Contrôle avec tolerance=0 : type = ecart ; 2 comptes signalés
```

**Conséquence pour le déclarant :** **0,01 € de discontinuité sur chacun de deux comptes** est masqué par une approbation. Le contrôle ne modifie pas les écritures et ne crée pas lui-même cet écart. Le constat porte sur la précision trompeuse du compte rendu, sans prétendre que toute tolérance serait interdite.

## Ce qui a été vérifié et tenu

### Atomicité de la clôture et relance

Dans `modules/fiscal.py`, `cloturer` (471), deux branches sont exécutées avec une immobilisation amortissable de 12 000 € sur dix ans et un déficit antérieur fictif de 1 000 € :

- **Création d’un déficit :** loyers 1 000 €, maintenance 1 300 €, dotation 1 200 € ; déficit de l’année 300 €, report 39 C 1 200 €.
- **Imputation d’un déficit :** loyers 4 000 €, dotation 1 200 € ; bénéfice avant déficits 2 800 €, imputation 1 000 €, revenu imposable 1 800 €.

Pour chaque branche, la connexion SQLite instrumentée enregistre **un seul appel à `commit`**. Les 37 points comprennent les insertions individuelles de lignes, les écritures des suivis, le traitement des déficits, le marquage de l’exercice, et les deux côtés du commit final. Les `executemany` sont déroulés pour permettre une coupure entre deux insertions. À chaque point, un processus séparé s’inflige réellement SIGKILL.

```text
2 branches × 37 points = 74 processus interrompus, code de sortie -9
72 coupures avant commit : toutes les tables retrouvent l’état initial
72 relances : état final identique à la clôture complète de référence
2 coupures après commit : état final complet conservé ; nouvelle clôture refusée
74 contrôles integrity_check : ok
in_transaction : True jusqu’avant commit ; False après commit
```

La comparaison énumère toutes les tables utilisateur SQLite et leurs lignes, sans liste manuelle limitée aux tables fiscales. La relance utilise la connexion ordinaire, sans instrumentation. Aucun commit intermédiaire n’est observé sur ces chemins, y compris à travers les savepoints de `modules/ecritures.py`, `inserer` (98).

Le test existant `tests/test_fiabilite.py`, `test_crash_en_pleine_cloture_ne_laisse_rien` (98), ne coupe qu’après la génération de dotation. Il constitue un test utile mais ne couvre pas à lui seul les autres étapes. Les 74 essais élargissent cette couverture ; ils ne simulent pas une panne électrique du matériel ni une coupure à l’intérieur de l’implémentation SQLite du commit.

### Cycle interne et reprise de trois FEC

Une immobilisation de 12 000 €, mise en service le 1er janvier 2024, est amortie sur dix ans. Le cycle interne donne :

| Exercice | Loyers | Maintenance | Dotation | Résultat comptable | Résultat fiscal avant déficits | Stock 39 C final | Déficit restant | Revenu imposable |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2024 | 1 000 € | 1 300 € | 1 200 € | −1 500 € | −300 € | 1 200 € | 300 € | 0 € |
| 2025 | 2 400 € | 200 € | 1 200 € | 1 000 € | 0 € | 200 € | 300 € | 0 € |
| 2026 | 4 000 € | 200 € | 1 200 € | 2 600 € | 2 400 € | 0 € | 0 € | 2 100 € |

Les FEC exportés sont triés, rejoués dans un autre dossier fictif, puis clos avec `generer_dotation=False`, les dotations figurant déjà dans les fichiers. **Pour chaque exercice, la balance complète et le dictionnaire fiscal retourné sont identiques au cycle interne.** Les deux jonctions non altérées sont approuvées (`trois_exercices`).

Avec `generer_dotation=True`, le FEC natif 2024 rejoué provoque au contraire le refus « Dotation aux amortissements déjà générée pour 2024 (écriture OD n°4). » : aucune duplication de cette dotation native n’est constatée. Cet essai ne valide pas les libellés de dotation arbitraires d’un cabinet, déjà concernés par H-02.

### À-nouveaux, équilibre et comptes externes

- Les classes **1 à 5** sont conservées, notamment les comptes externes `3100000`, `4010000`, `4110000`, `5120000`. Les comptes 6 et 7 ne sont pas repris ; le solde 120000 devient nul après affectation. Le résultat transite par 120000 **à l’ouverture suivante**, puis est affecté à 108000 : aucune écriture de transfert du résultat à la clôture elle-même n’est supposée.
- Un lot de quatre charges externes de 1 000 € sur `6450000`, `6580000`, `6811000`, `6950000` donne un résultat comptable de **−4 000 € dans les deux moteurs**, `fiscal.agregats` et `liasse.resultat_2033b`. La classification fiscale de la dotation à sept chiffres reste hors de cette conclusion, conformément à I-01.
- Un solde de **0,01 € est repris**, avec débit et crédit de 0,01 €. Le seuil du code est 0,005 €, et non une exclusion des soldes inférieurs ou égaux à un centime.
- Une balance de reprise de 800 € au débit contre 799 € au crédit est refusée ; après fermeture et réouverture de la base, **zéro écriture demeure**. `reprise.controle_equilibre` (166) n’est pas appelé dans ce chemin (compteur : 0), mais le guichet `ecritures.inserer` assure effectivement le refus.
- Une ouverture demandée sans reprise est possible ; `controles.c_an_absents` (508) produit bien `AN_ABSENTS` lorsqu’un exercice précédent clos existe. Ce témoin peut cependant conserver `conforme=True` dans la liasse : l’avertissement n’est pas un blocage.

### Rejeu interrompu et datation des AN

Dans `modules/rejeu_fec.py`, `rejouer` (28), une exception volontaire au troisième lot, après l’insertion réelle de deux loyers sur trois (100 €, 200 €, 300 €), laisse **zéro écriture persistante**, même si l’appelant committe après avoir intercepté l’erreur. La relance produit exactement trois écritures (`rejeu_interrompu`). Cette propriété d’un fichier ne résout pas Q-09, qui concerne une boucle web de plusieurs fichiers déjà committés séparément.

Le FEC fictif à quatre lignes AN du 1er janvier 2025 et deux lignes d’activité 2025 est détecté comme 2025 et rejoué intégralement. En datant les quatre AN du 31 décembre 2024, `migration_fec.annee_du_fec` (41) détecte **2024** ; un rejeu explicitement demandé sur 2025 est refusé pour date hors exercice et laisse zéro écriture. Il n’y a donc ni rattachement automatique réussi ni perte partielle silencieuse sur ce cas. La recevabilité et la politique de normalisation de ce format restent des questions ci-dessous.

### Web, CLI, sauvegarde et archive

La route `app.py`, `cloturer` (1219), et `cli.py`, `cmd_cloturer` (132), sont exécutées sur deux copies du même dossier fictif. Résultats : retour web 302 avec succès, code CLI 0, **toutes les tables finales identiques**, quatre écritures et huit lignes, résultat comptable −1 500 €, résultat fiscal −300 €, déficit créé 300 €, report 39 C 1 200 €.

Les deux FEC archivés ont l’empreinte SHA-256 :

```text
59ed6f39ac5a6567d14babd732331fd0bef325afee3654beae83e956d1c87562
```

Les sauvegardes antérieures ne sont **pas identiques octet par octet** : le web a déjà créé une table vide `regle_fiscale`, absente de la sauvegarde CLI. La comparaison logique ne trouve que cette différence ; les données comptables sauvegardées concordent. Les horodatages des noms de fichiers ne constituent pas un critère d’identité comptable.

Lorsque l’archive est rendue volontairement inaccessible, les deux chemins conservent la clôture et disent explicitement que l’exercice **EST clôturé**, avec un avertissement d’archive manquante. L’échec d’archivage ne se présente pas comme une annulation de clôture. Le web utilise un `try` imbriqué pour cette distinction : l’exigence est satisfaite en exécution, indépendamment de l’expression « hors du try » du prompt.

### Exercice clos, restauration et retraitements figés

Après clôture du témoin avec loyer 1 200 €, fonds ALUR 200 € et dotation 1 200 € :

- L’insertion par `ecritures.inserer` (98), l’annulation par `operations.annuler` (350), la cession par `cession.ceder_bien` (95), la reprise AN et la seconde clôture sont toutes refusées sur 2025 clos. Aucune écriture supplémentaire n’est constatée.
- La comparaison de l’ensemble des tables n’est toutefois **pas strictement identique** : le chemin de cession ajoute des colonnes NULL à `bien` et `composant`. Les indicateurs bruts `etat_inchange` et `donnees_comptables_inchangees` valent donc False. Le détail des différences contient uniquement ces extensions de schéma, sans modification des valeurs comptables préexistantes ; ces indicateurs ne doivent pas être cités comme True.
- Désactiver ensuite le paramètre du retraitement automatique ALUR ne change pas le tableau 2033-B de l’exercice clos : les **200 € figés** restent repris. Voir `liasse.resultat_2033b` (103).
- Restaurer la sauvegarde prise avant clôture par `perennite.restaurer` (123), puis reclore, retrouve une seule dotation de 1 200 €, quatre écritures, et un résultat fiscal nul. Le retour à un exercice ouvert provient du retour intégral à la sauvegarde, non d’une seconde clôture superposée.
- Une migration de schéma exécutée par `migrations.migrer` (100), du palier 2 au palier 7 dans ce témoin, conserve le statut clos et un FEC strictement identique.

Un ajout **SQL direct** de loyer de 1 000 € après clôture reste possible : le résultat comptable recalculé devient 800 € alors que celui de l’exercice reste −200 € ; le résultat fiscal LMNP figé reste nul et `conforme=False`. Ce contournement SQL, déjà documenté en passe G, n’est pas un nouveau constat. Il ne valide pas l’immuabilité face au défaut concurrent Q-03.

### Résultats rattachés aux passes antérieures

- **Q-03 :** insertion concurrente passant le test de statut avant la clôture. Les refus séquentiels ci-dessus ne démontrent pas la correction de cette course.
- **Q-09 :** interruption d’une reprise web de plusieurs FEC ; l’atomicité d’un seul rejeu ne rend pas le lot entier atomique.
- **Q-10 :** atomicité des migrations. L’identité du FEC avant/après une migration réussie n’est pas un test de coupure de migration.
- **Q-11 :** ouverture persistante malgré échec des AN. Le cas supplémentaire d’un exercice entièrement vide, clos en 2025 ou en 2040, produit « Écriture sans ligne. » à la reprise suivante ; le nouvel exercice reste ouvert et `AN_ABSENTS` est émis. La cause de persistance n’est pas renumérotée.
- **H-02, I-01 et J :** reconnaissance des dotations importées, classification fiscale à sept chiffres et historique des déficits restent soumis aux constats de ces passes. L’égalité des résultats sur le cycle natif ne les invalide pas.

## Non vérifiable avec les pièces fournies

- Les garanties observées avec SIGKILL aux frontières des appels tiennent-elles lors d’une coupure électrique réelle, avec le système de fichiers, les caches et le support de stockage effectivement utilisés par le déclarant ?
- Les branches de clôture non exercées ici — notamment d’autres historiques de cession et répartitions multi-biens — conservent-elles un seul commit à chacun de leurs propres points d’écriture ?
- Quel parcours web ou CLI permet de clore un FEC importé qui contient déjà une dotation native, en demandant explicitement de ne pas la générer à nouveau, comme dans le cycle réussi par API ?
- Pour un fichier présenté comme celui de N mais dont les AN portent le 31 décembre N−1, quel format exact le cabinet garantit-il, et quelle normalisation est attendue sans dénaturer le fichier d’origine ?
- Le cycle synthétique reproduit-il tous les particularismes du calage de cabinet sur trois exercices réels, sans lequel une équivalence générale avec ce cabinet ne peut être établie ici ?
- Quelle procédure de reconstruction des exercices postérieurs est prévue lorsqu’un exercice ancien est ajouté après leur clôture, pour remettre simultanément en cohérence AN, déficits, suivi 39 C et archives ?

## Tableau récapitulatif numéroté

| N° | Constat | Gravité | Conséquence exécutée |
|---|---|---|---|
| K-01 | Clôture rétroactive après un exercice déjà clos | Majeur | Revenu imposable mémorisé et déficit restant chacun supérieurs de 600 € au cycle chronologique |
| K-02 | Reconstruction après suppression des seuls AN | Majeur | Affectation de 600 € doublée ; prochaine reprise déséquilibrée et refusée |
| K-03 | Jonction annoncée exacte malgré la tolérance | Mineur | Deux écarts de 0,01 € masqués par une approbation « au centime » |

**État du suivi :** les trois constats ont été corrigés en production le 16 septembre 2026 (version 8.46.0). Les preuves de `preuves_k/` sont conservées **telles qu'observées avant correction** : elles restent la référence du défaut, pas de l'état actuel du code. La non-régression est figée par `tests/test_passe_k.py` (18 tests), dont 9 échouent si l'on retire les correctifs — les 9 autres sont des contre-épreuves, qui doivent passer dans les deux états.

Deux précisions sur le traitement retenu. K-01 est traité par un **refus**, et non par un recalcul des exercices postérieurs : ceux-ci sont scellés, leur FEC est archivé et leur liasse a pu être déclarée, de sorte que les rouvrir relèverait d'une décision de l'utilisateur et non du logiciel. Le message indique explicitement la sortie — restaurer une sauvegarde antérieure à la clôture du premier exercice postérieur, puis reprendre les clôtures dans l'ordre. La garde ne se déclenche que sur un exercice postérieur **clos** : en ouvrir un d'avance, geste ordinaire en début d'année, ne bloque rien.

K-02 est traité en déplaçant la garde vers `_construire_an_depuis_balance`, point de passage unique des deux chemins de reprise, plutôt que de la dupliquer chez leurs appelants — la reprise depuis un FEC externe portait d'ailleurs sa propre garde, redondante et devenue morte, qui a été retirée. La fonction `reprise.reprise_deja_presente` nomme la moitié du lot qui subsiste, ce qui rend le message d'erreur exploitable par l'utilisateur.

Pour K-03, le type de verdict `tolere` s'ajoute à `ok` et `ecart`. La page d'analyse le rend en orange, comme les autres observations non bloquantes, sans modification de la présentation : elle colorait déjà en vert le seul type `ok` et en rouge le seul type `ecart`.
