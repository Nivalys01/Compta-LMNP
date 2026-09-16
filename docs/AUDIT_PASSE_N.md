# Audit — Passe N : règles versionnées, gabarits et veille

Date : 15 septembre 2026. Version exécutée : `compta_lmnp_v8.41.0/compta_lmnp`.

## Périmètre et preuves

Les quatre modules demandés sont présents. `schema.sql` est présent, mais les tables `regle_fiscale`, `gabarit_personnalise` et `meta` sont créées par les modules à l'exécution, et non par des déclarations de ces trois tables dans ce fichier. Leurs créateurs réels ont été examinés. Les consommateurs nécessaires sont également disponibles : fiscalité, liasse, contrôles, opérations, import bancaire et interface.

Lecture du CHANGELOG, des résultats pertinents des passes J, K, M et Q et des corrections mentionnées dans le code. Les anciens rapports D2, E et F sont absents de l'arbre de travail ; leurs suppressions préexistantes n'ont pas été modifiées. Les défauts déjà décrits dans les rapports présents ne sont pas renumérotés ici, notamment l'évolution du suivi des déficits après une clôture ultérieure (J), les agrégations incorrectes du contrôle LMP (M) et les autres ruptures d'atomicité (Q).

Toutes les reproductions utilisent des bases temporaires initialisées en mode blanc, un référentiel générique et une identité fictive. Aucun FEC réel, seed d'identité ou fichier d'empreintes privées n'est utilisé. Aucun fichier du logiciel n'a été corrigé.

Reproduction depuis la racine du dépôt :

```sh
python3 docs/preuves_n/reproduire.py
```

Le [script](preuves_n/reproduire.py) conserve ses sorties dans [sorties.json](preuves_n/sorties.json). `python3 docs/preuves_n/verifier.py` vérifie les observations et les localisations des fonctions. Les extraits ci-dessous sont des résultats d'exécution. Les modifications de règles utilisées pour éprouver le moteur sont fictives ; elles ne prétendent pas décrire des changements de droit adoptés. Les chemins de source ci-dessous sont relatifs au répertoire de version indiqué en tête ; les numéros désignent les lignes de cette version.

## Constats

### N-01 — Une insertion rétroactive laisse deux versions ouvertes

**Gravité : mineur.**

**Fichier et fonctions :** `modules/parametres.py`, `definir`, ligne **146**, insertion ligne **170** ; `valeur`, ligne **126**.

**Scénario :** partir du seuil livré à 500 €, saisir 1 000 € au `2026-07-01`, puis 700 € au `2025-01-01`. Lire les périodes enregistrées. Preuve : `desordre`.

**Attendu :** 500 € jusqu'au 31 décembre 2024, 700 € du 1er janvier 2025 au 30 juin 2026, puis 1 000 €. Une seule période ouverte.

**Produit réel :**

```text
500  : 2000-01-01 → 2024-12-31
700  : 2025-01-01 → NULL
1000 : 2026-07-01 → NULL
```

La nouvelle version rétroactive ne reçoit pas la veille du début de sa suivante comme date de fin. Le chevauchement est donc possible par l'API normale.

**Conséquence :** historique contradictoire pour justifier la règle utilisée. **Aucun écart de calcul n'est établi par le seul chevauchement** : le tri décroissant sélectionne bien 1 000 € en 2026 et ensuite. C'est pourquoi ce constat est mineur.

**Variante explicite par SQL, distincte de la saisie normale :** terminer la version de 1 000 € au `2026-09-30`. Sortie `fin_septembre` : `2026=1000`, `2027=700`. L'ancienne version laissée ouverte ressurgit. Cette variante révèle aussi que le sélecteur ne demande pas une règle valide au 31 décembre : il suffit qu'elle ait rencontré l'année. Elle ne démontre pas que l'interface permet de saisir une date de fin.

### N-02 — Les valeurs aberrantes sont enregistrées et peuvent supprimer un report

**Gravité : majeur.**

**Fichiers et fonctions :** `modules/parametres.py`, `definir`, **146** ; `modules/fiscal.py`, `traiter_deficit`, **157**, lecture de la durée **171**, création de l'expiration **183**. Le formulaire transmet la valeur via `app.py`, `reglementation_regle`, **1444**.

**Scénario :** sur trois bases séparées, enregistrer un seuil de −1 €, 0 €, puis 10 000 000 €, effectif au 1er janvier 2026 ; saisir un équipement de 800 €. Sur une quatrième base, enregistrer une durée de report de zéro année, créer un déficit 2026 de 1 200 €, puis traiter un bénéfice 2027 de 1 200 €.

**Attendu :** refus d'une durée nulle et des valeurs négatives ; une valeur extrême doit au minimum être explicitement signalée avant de désactiver pratiquement un contrôle. Avec la durée livrée de dix ans, le déficit 2026 demeure imputable en 2027. Le report sur les dix années suivantes est confirmé par le [BOFiP, III-A](https://bofip.impots.gouv.fr/bofip/3610-PGP.html/identifiant%3DBOI-BIC-CHAMP-40-20-20260819).

**Produit réel :**

```text
seuil=-1       : lu=-1 ; contrôle=[IMMOBILISABLE]
seuil=0        : lu=0  ; contrôle=[IMMOBILISABLE]
seuil=10000000 : lu=10000000 ; contrôle=[]
déficit créé  : origine=2026 ; solde=1200 ; expiration=2026
traitement 2027 : perimes=1 ; impute_sur_benefice=0 ; stock_deficits=0
```

**Conséquence :** **1 200 € de déficit perdus dans le moteur**, et 1 200 € de bénéfice laissés sans cette imputation. Ce montant est une base imposable, pas un montant d'impôt. Le seuil extrême, lui, supprime l'avertissement sur 800 € ; il ne reclasse pas directement l'écriture. Le caractère versionnable ne dispense pas de valider le domaine d'une règle : durée entière positive, interrupteur ALUR limité à 0/1, seuil cohérent.

### N-03 — Le pense-bête ignore le seuil LMP versionné

**Gravité : majeur.**

**Fichiers et fonctions :** `modules/pense_bete.py`, `rappels`, **363**, comparaison fixe **458** ; témoin `modules/controles.py`, `c_seuil_lmp`, **549**.

**Scénario :** exercice 2026 ouvert, loyers de 20 000 €, règle fictive `seuil_lmp_recettes=15000` effective au 1er janvier 2026. Exécuter les deux consommateurs au 15 septembre 2026.

**Attendu :** même seuil de 15 000 € pour le même exercice et rappel demandant de vérifier la seconde condition du statut.

**Produit réel — `lmp` :**

```text
contrôle métier : [SEUIL_LMP]
pense-bête, rappels LMP : []
```

**Conséquence :** le rappel annoncé comme consommateur de cette règle ne prévient pas le déclarant, alors que ses recettes dépassent la valeur enregistrée de **5 000 €**. Aucun impôt ni basculement effectif en LMP n'est chiffré : les autres revenus du foyer ne sont pas renseignés. Le contrôle métier reste opérationnel. Ce défaut est distinct de M-09 : ici, les recettes sont exclusivement des loyers et leur total est correct ; c'est la constante `23000` du pense-bête qui ignore la configuration.

### N-04 — Créer un gabarit valide aussi les opérations en attente

**Gravité : majeur.**

**Fichier et fonction :** `modules/gabarits.py`, `ajouter_personnalise`, **213**, `conn.commit()` **233**. Saisie témoin : `modules/operations.py`, `saisir`, **23**.

**Scénario :** saisir un loyer fictif de 800 € avec `commit=False`. Dans la même connexion, créer `fictif`, compte `606320`, nature `charge`. Exécuter `rollback`, puis compter les opérations.

**Attendu pour une API composable dans la transaction de l'appelant :** transaction encore ouverte et zéro opération après rollback, ou refus explicite de participer à cette transaction.

**Produit réel — `transaction_ajouter_personnalise` :**

```text
transaction_apres=False
operations_apres_rollback=1
```

**Conséquence :** **800 € de recettes persistent malgré l'annulation demandée**. Le contrat de préservation de la transaction n'est respecté que par les lecteurs et le créateur de table, pas par la création métier du gabarit. La reproduction porte sur l'API avec une connexion partagée ; aucun import bancaire standard appelant cette création pendant sa validation n'a été établi. Le correctif D2-08 sur les lectures reste valide.

### N-05 — Des règles perdues sont remplacées sans signalement par les valeurs livrées

**Gravité : majeur.**

**Fichier et fonctions :** `modules/parametres.py`, `assurer`, **99**, réinsertion **114** ; `valeur`, **126**, repli **141** ; consommateur `modules/controles.py`, `c_depense_immobilisable`, **85**.

**Scénario :** enregistrer un seuil fictif de 300 € pour 2026, saisir un équipement de 400 €, puis vider `regle_fiscale` par SQL afin de simuler une perte de configuration. Relancer le contrôle. Un autre essai lit une table vide avec capture des sorties et des avertissements Python.

**Attendu :** distinguer une première initialisation de la disparition d'un historique fiscal, et signaler le remplacement avant de présenter le contrôle comme exploitable.

**Produit réel — `regles_perdues`, `table_vide` :**

```text
avant : [IMMOBILISABLE]
après : [] ; valeur_recreee=500
lecture table vide : valeur=500 ; regles_apres=5 ; messages="" ; warnings=0
```

**Conséquence :** l'avertissement sur **400 €** disparaît avec la règle perdue. La perte initiale est injectée, pas attribuée au logiciel ; le défaut est son traitement indifférencié comme une initialisation normale. Aucun écart fiscal automatique de 400 € n'est allégué.

**Diagnostic précisé :** une table vide ne déclenche pas directement le `defaut` de l'appelant pour une clé livrée : `assurer` recrée d'abord les cinq règles. En revanche, si la clé existe seulement à partir de 2027, la lecture 2026 retourne réellement `defaut=500` (`trou`). Ce repli n'apporte aucun indicateur disant qu'aucune version ne couvre l'exercice. La table d'historique permet de voir les valeurs présentes, mais ne restitue pas celles qui ont disparu.

### N-06 — Une veille future ou indisponible supprime le rappel

**Gravité : mineur.**

**Fichiers et fonctions :** `modules/veille_fiscale.py`, `enregistrer_veille`, **147**, `veille_a_refaire`, **159** ; `modules/pense_bete.py`, `rappels`, **363**, traitement de l'exception **498**.

**Scénario :** enregistrer par l'API la date `2099-01-01`, puis interroger la veille au `2029-09-15`. Variante indépendante : faire lever une `sqlite3.OperationalError('panne fictive')` par la consultation de veille pendant l'exécution de `rappels`.

**Attendu :** une date future doit être signalée comme incohérente, et une consultation impossible comme indisponible ; aucune ne prouve qu'une veille récente a été réalisée.

**Produit réel :**

```text
date future : a_refaire=False ; rappels=[]
panne : [Frais d'acquisition : rien d'enregistré, Aucun mobilier immobilisé]
        aucun rappel de veille ni diagnostic d'indisponibilité
```

**Conséquence :** l'utilisateur peut rester sans invitation à vérifier les règles pendant des années après une mauvaise date, ou pendant une panne. Aucun montant déclaré faux n'est établi. L'enregistrement d'une date fournie est testé à l'API ; le bouton usuel de veille emploie la date courante. Les dates absentes et illisibles sont, elles, correctement signalées.

### N-07 — Un seuil illisible fait accepter une proposition bancaire auparavant refusée

**Gravité : majeur.**

**Fichier et fonctions :** `modules/import_bancaire.py`, `_seuil_immobilisation`, **198**, exception et repli **211** ; `categoriser`, **215** ; `_depasse_le_seuil`, **252**.

**Scénario :** enregistrer un seuil fictif de 300 € pour 2026. Catégoriser `mobilier fictif`, débit de 400 €. Refaire l'appel en utilisant l'autoriseur SQLite pour interdire uniquement les lectures de `regle_fiscale`. Après rétablissement de l'accès, saisir la proposition obtenue et calculer le résultat. Cette panne est injectée explicitement ; le classificateur lui-même n'est pas remplacé.

**Attendu :** une règle inaccessible doit rendre la proposition incertaine, avec un diagnostic, plutôt que permettre la charge que la règle disponible excluait.

**Produit réel — `import_regle_inaccessible` :**

```text
lecture directe : DatabaseError: access to regle_fiscale.cle is prohibited
catégorisation normale : attente_decaissement
catégorisation en panne : petit_equipement
après saisie de cette proposition : resultat_comptable=-400
contrôle après rétablissement : [IMMOBILISABLE]
```

**Conséquence :** **400 € entrent en charge** après adoption de la proposition dégradée, sans que la proposition indique l'impossibilité de lire le seuil. Ce montant n'est pas assimilé à un écart définitif d'impôt : le contrôle rétabli avertit, et la qualification comptable doit être décidée par l'utilisateur. Le défaut est le passage silencieux de l'attente à la charge lorsque le garde-fou ne peut pas travailler. Ce n'est pas la régression d'un correctif d'application du millésime : l'année 2026 est bien transmise.

### N-08 — La liste de veille omet une règle qui modifie réellement la clôture

**Gravité : mineur.**

**Fichier et fonction :** `modules/veille_fiscale.py`, `prompt_veille`, **174**, consommation de `CORPUS` **183**. Règle effectivement utilisée : `modules/fiscal.py`, `retraitement_automatique`, **443**.

**Scénario :** calculer la différence entre les clés livrées par `parametres.LIBELLES` et les clés rattachées au corpus, puis générer le prompt pour 2029 et rechercher la mention ALUR.

**Attendu :** chaque règle livrée doit être couverte explicitement ou déclarée non couverte, en particulier celle qui réintègre des charges à la clôture.

**Produit réel :**

```text
corpus_regles_manquantes = [retraitement_alur_auto]
prompt_couverture : alur=False ; prelevements=True ; date_exercice=True
```

**Conséquence :** la revue guidée ne demande pas explicitement de vérifier le traitement des fonds ALUR, alors qu'il peut modifier le résultat fiscal. Aucun montant actuellement faux n'est établi. Le prompt demande aussi de rechercher des textes nouveaux : c'est utile, mais cela ne remplace pas la couverture d'une règle déjà connue du logiciel. Ce constat ne prétend pas que le corpus entier serait dépourvu de références aux charges déductibles.

## Ce qui a été vérifié et tenu

### Quelle version est réellement appliquée ?

`parametres.valeur` (**126**) prend **la version ayant le début le plus récent parmi celles qui rencontrent l'année civile** : début au plus tard le 31 décembre et fin absente ou au plus tôt le 1er janvier. Ce n'est ni une lecture à la date d'opération ni strictement une lecture au jour de clôture.

Avec 500 € à partir de 2000 et 1 000 € au 1er juillet 2026, les sorties sont `2025=500`, `2026=1000`, `2029=1000`. Un équipement de 800 € daté du **1er février 2026** ne reçoit plus l'alerte ; le lecteur bancaire retourne également 1 000 € pour 2026. Le résultat correspond au contrat annuel documenté, sans établir que toute disposition légale s'applique rétrospectivement aux opérations de janvier. La question de la bonne granularité juridique reste ci-dessous.

- Une date d'effet **antérieure au premier exercice du dossier** est bien retenue : le dossier créé pour 2026 utilise la version de 2000.
- Une seconde saisie au **même jour d'effet** remplace la précédente : 700 puis 900 € au 1er janvier 2026 donnent `lu=900`, `versions=1`. Le correctif de collision de dates tient.
- Les contrôles d'immobilisation et LMP, le lecteur bancaire, le traitement des déficits et l'ALUR passent l'année traitée. Le pense-bête LMP est l'exception établie N-03.

### Liasse close et durée des déficits

Exercice 2026 : loyers **2 400 €**, ALUR **200 €**, équipement **800 €**, sans dotation. Après clôture, changer rétroactivement le seuil de 500 à 1 000 € et désactiver l'ALUR au 1er janvier 2026. Deux appels complets à `liasse.generer` (**588**) donnent :

```text
liasse_identique=True
resultat_fiscal_avant=1600 ; resultat_fiscal_apres=1600
```

Le retraitement figé protège donc bien cette liasse. Le contrôle de l'exercice clos change de `[IMMOBILISABLE]` à `[]` parce que la version **de 2026 elle-même** a été remplacée. Cela ne prouve pas qu'il lit la règle de l'année courante ; les contrôles ne constituent pas un instantané archivé.

La péremption n'est **pas** une constante de dix ans dans le moteur de création : avec une durée fictive de douze ans à partir de 2026, l'exécution de `fiscal.traiter_deficit` (**157**) donne `2025 → expiration 2035`, `2026 → expiration 2038`. L'expiration est enregistrée avec le déficit ; les purges ultérieures utilisent cette date. Les défauts de restitution des stocks historiques signalés en J ne sont pas requalifiés en défauts de ce versionnement.

### Gabarits et transactions

- Clé standard `loyer` : `ValueError` ; compte absent `999999` : `ValueError` ; nature invalide : contrainte `CHECK` refusée.
- Clé personnalisée désactivée : `IntegrityError: UNIQUE constraint failed`, donc **aucun écrasement silencieux**. Le message est technique, mais la protection existe.
- Suppression du compte `606320` référencé par un gabarit inactif : `IntegrityError: FOREIGN KEY constraint failed`, sur les connexions initialisées par le logiciel. La suppression n'orpheline pas le gabarit.
- Gabarit `charge` sur `164000`, saisie 800 € : produits, charges et résultat **zéro**. Sur `472000` : résultat zéro et `COMPTE_ATTENTE`. La nature pilote le sens débit/crédit ; elle n'affirme pas à elle seule une déductibilité. Ces résultats sont cohérents avec les gabarits de bilan assumés. Le formulaire usuel filtre en outre les comptes de charge/produit ; le test de classe 1/4 vise l'API.
- Pour chacun des lecteurs testés — `parametres.assurer`, `valeur`, `historique`, `gabarits.assurer_table`, `_personnalises`, `tous`, `par_groupe`, `veille_fiscale.derniere_veille`, `veille_a_refaire`, `pense_bete.lire_notes`, `rappels` — un loyer de 800 € non validé reste en transaction et disparaît après rollback. Deux saisies successives de 800 et 900 € avec `commit=False` laissent **zéro opération** après rollback. Le défaut antérieur de lecture qui committait n'est pas reproduit dans ces chemins.

### Veille, calendrier et constantes : portée exacte

- Dernière veille absente, `illisible`, ou `2028-01-01` au 15 septembre 2029 : `a_refaire=True`, avec rappel pour les valeurs enregistrées. Une date impossible n'est donc pas assimilée systématiquement à une veille récente.
- Le module documente explicitement que le logiciel ne se met pas à jour seul. `prompt_veille` produit des instructions pour une recherche extérieure et exige des sources officielles. Aucune actualisation automatique des règles n'est établie ni annoncée par ce mécanisme.
- Le prompt produit pour 2029 contient bien **2029** et demande les taux de prélèvements sociaux. Le corpus comprend les amortissements par composants, le seuil d'immobilisation, le LMP, les déficits et le plafond 39 C. Son défaut de couverture ALUR est circonscrit en N-08.
- `pense_bete.actualites` (**317**) retourne toujours les échéances **1er septembre 2026** et **1er septembre 2027**, même avec l'horloge du module simulée au 15 septembre 2029. Il ne calcule pas un calendrier annuel. Toutefois, ce sont des événements datés, accompagnés de `verifie_le="13 août 2026"` : ils ne sont pas présentés comme nouvellement vérifiés en 2029. Les échéances récurrentes sont des textes génériques et les rappels déclaratifs utilisent l'année de l'horloge ; ils demandent de vérifier les dates exactes. Je ne transforme pas la seule présence d'une actualité ancienne en preuve d'une échéance légale fausse.
- **Constantes à maintenir :** `23000` du pense-bête est un seuil calculatoire non versionné (N-03). Les délais documentaires de conservation, les jours et mois des échéances, et les taux mentionnés dans l'actualité sont des textes statiques. Aucun calcul de prélèvements sociaux à 17,2 % ou 18,6 % n'a été identifié dans les consommateurs examinés : ces textes ne prouvent pas une taxation à un mauvais taux.
- La formule 39 C est implémentée dans `fiscal.calculer_39c` (**113**) et `_calcul_fiscal` (**363**) ; ce n'est pas un plafond monétaire configurable. Les durées d'amortissement sont portées par les composants, consommées par `amortissement.plan` (**60**), et non toutes imposées par une constante fiscale unique. Les dix cases historiques de l'aide déclarative restent codées dans `liasse.aide_2042c` (**429**, décalage de dix années **475**) : faire évoluer la durée du moteur ne suffit donc pas à faire évoluer les formulaires. La validité d'un formulaire futur relève des questions suivantes.

## Non vérifiable avec les pièces fournies

- Pour chaque règle, quelle convention juridique doit gouverner un changement en cours d'année : date de l'opération, début d'exercice ou clôture ? Quelle disposition et quel jeu d'exemples validés permettent d'établir l'attendu légal d'un changement réel au 1er juillet ?
- Les versions anciennes des rapports D2, E et F peuvent-elles être fournies pour compléter la comparaison avec leurs récapitulatifs, absents de l'arbre de travail audité ?
- Quelle procédure valide la source officielle et le domaine admissible d'une nouvelle règle avant son enregistrement, notamment lorsqu'elle vise un exercice déjà clos ?
- Où sont conservés les paramètres et le rapport de contrôles ayant servi à la clôture, si une justification ultérieure doit reproduire aussi les avertissements d'origine ?
- Quelle procédure mettra à jour les formulaires et les dix cases de déficits si la durée légale venait à changer ? Quels millésimes officiels futurs permettraient de vérifier cette adaptation ?
- Qui revoit et date les délais de conservation, le calendrier déclaratif, les actualités de facturation et les taux sociaux statiques ? Quels documents à jour permettraient de certifier leur exactitude pour un usage en 2029 ?
- Quel inventaire juridique indépendant permet de certifier l'exhaustivité du corpus au-delà de la comparaison exécutée avec les cinq règles actuellement livrées ?

## Tableau récapitulatif numéroté

| N° | Constat | Conséquence exécutée | Gravité |
|---|---|---|---|
| N-01 | Insertion rétroactive sans fin de validité | Deux versions ouvertes ; aucun écart monétaire par le seul chevauchement | mineur |
| N-02 | Valeurs fiscales aberrantes acceptées | 1 200 € de déficit purgés après une durée saisie à zéro | majeur |
| N-03 | Seuil LMP fixe dans le pense-bête | Rappel absent pour 20 000 € de recettes et un seuil configuré de 15 000 € | majeur |
| N-04 | Création de gabarit qui valide la transaction | 800 € de recettes survivent au rollback | majeur |
| N-05 | Configuration perdue remplacée silencieusement | Alerte sur 400 € supprimée par le retour à 500 € | majeur |
| N-06 | Veille future ou indisponible sans rappel | Rappel absent malgré une date incohérente ou une consultation en échec | mineur |
| N-07 | Repli bancaire sur un seuil illisible | Proposition de charge de 400 € au lieu d'une attente | majeur |
| N-08 | ALUR absent de la liste explicite de veille | Règle de réintégration omise de la revue guidée | mineur |

**État du suivi :** les constats de cette passe ont été corrigés en production le 16 septembre 2026 (version 8.48.0). Les preuves de `preuves_n/` sont conservées **telles qu'observées avant correction** : elles restent la référence du défaut, pas de l'état actuel du code. La non-régression est figée par `tests/test_passe_n.py`.
