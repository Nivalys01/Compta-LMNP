# Audit — passe P : quittances et données des locataires

**15 septembre 2026 — 7 constats : 6 majeurs, 1 mineur.**

Le parcours web peut attester **880 € sans encaissement**. Un paiement partiel reçoit le titre de quittance, puis le paiement du solde ne peut plus être quittancé. La restauration ordinaire protège les numéros ; lorsque la lecture du compteur échoue, cette protection laisse au contraire réattribuer le **n° 2**.

## Périmètre et preuves

Racine des sources citées : `compta_lmnp_v8.41.0/compta_lmnp/`. Les cinq pièces demandées sont présentes. Les fonctions réellement appelées dans `modules/perennite.py`, `outils_demo.py` et `verifier_depot.py` ont également été examinées. Lecture préalable du récapitulatif de la passe B, notamment les trois corrections de quittancement, et des recoupements O et Q. Le récapitulatif F a été retrouvé et lu dans Git : les suppressions préexistantes des anciens rapports dans l'arbre de travail n'ont pas été modifiées. Les corrections d'anonymisation F ont aussi été consultées dans les fonctions concernées.

**Aucune source privée de comptabilité, d'identité ou d'empreintes n'a été utilisée.** Les scénarios emploient des bases temporaires blanches et des personnes fictives. Seul le seed destiné au client a aussi été exécuté en mémoire, pour compter ses locataires et quittances, sans restituer ses valeurs d'identité. Aucun correctif de production appliqué.

Preuves : [script](preuves_p/reproduire.py), [résultats réels et empreintes des sources](preuves_p/resultats.json), [HTML sans encaissement](preuves_p/impaye.html), [paiement partiel](preuves_p/partiel.html), [après annulation](preuves_p/apres_annulation.html), [mentions et échappement](preuves_p/mentions.html).

```bash
compta_lmnp_v8.41.0/compta_lmnp/.venv/bin/python docs/preuves_p/reproduire.py
```

Exécution terminée en **code 0**, Python 3.14.6, SQLite 3.51.2. Une traceback fictive est volontairement produite pour vérifier le journal. Les réponses web passent par le client Flask et les gabarits réels, avec chemins redirigés vers les dossiers temporaires. Les altérations SQL et la synchronisation artificielle de deux threads sont explicitement distinguées des parcours ordinaires. Les HTML ont été générés ; aucune impression physique ni exécution des CSS par un navigateur n'est revendiquée.

Les montants ci-dessous mesurent des écarts entre encaissements et justificatifs. **L'émission seule n'ajoute pas de recette fiscale** : aucun supplément d'impôt n'est déduit de ces écarts.

## Constats

### P-01 — Les montants manuels permettent une attestation sans paiement et une ventilation fausse sans alerte

**Gravité : majeur.**

**Fichiers et fonctions :** `modules/quittances.py`, `emettre`, **180**, reprise facultative des montants à **234**, insertion à **257** ; `detail`, **287**, comparaison du seul total à **312–313** ; `app.py`, `quittances_emettre`, **1146**, `quittance_imprimable`, **1165**.

**Scénario A :** logement avec un locataire fictif, **zéro opération**. Poster `/quittances/emettre` avec janvier 2026, loyer **800**, charges **80**, date de paiement vide. Ouvrir le document créé.

**Attendu :** refuser l'attestation faute d'encaissement, ou demander un rapprochement explicite avec une preuve de paiement avant émission. Un montant dû seul ne doit pas devenir une somme reçue.

**Produit réel — `impaye` :**

```text
POST : HTTP 302, message de succès « Quittance n° 00001 émise … : 880.00 € »
operations=0 ; quittance.total=880.0
HTML : « déclare avoir reçu »
detail.ecart_ecritures : encaisse=0.0 ; atteste=880.0
```

L'avertissement existe à la consultation ; **l'émission n'est pas bloquée**. Le même appel sans montants manuels est correctement refusé. Le diagnostic ne prétend donc pas que le contrôle automatique est absent.

**Scénario B indépendant :** saisir **800 € de loyer + 80 € de charges locatives** par `operations.saisir`, puis émettre manuellement **880 € de loyer + 0 € de charges**.

**Attendu :** détecter l'écart de ventilation, même si le total est exact.

**Produit réel — `ventilation` :**

```text
encaisse={loyer:800.0, charges:80.0}
quittance={loyer:880.0, charges:0.0, total:880.0}
alerte=null
```

**Conséquence :** A atteste **880 € non encaissés** ; B transforme **80 € de charges en loyer** dans le justificatif sans alerte. Le locataire reçoit une preuve incompatible avec les écritures ou leur ventilation. La distinction loyer/charges est expressément prévue par [l'article 21 de la loi du 6 juillet 1989](https://www.legifrance.gouv.fr/loda/article_lc/LEGIARTI000028806698/2026-03-12).

### P-02 — Un paiement partiel devient une quittance, puis empêche celle du paiement complet

**Gravité : majeur.**

**Fichiers et fonctions :** `modules/quittances.py`, `emettre`, **180**, refus du doublon à **218–223**, validation du montant positif à **244–254** ; `detail`, **287**, alerte à sens unique à **313** ; `app.py`, `quittance_imprimable`, **1165**. Gabarit réel `PAGE_QUITTANCE_IMPRIMABLE`, `modules/pages.py`, **2038**, titre à **2069**.

**Scénario :** locataire présent tout janvier 2026, loyer mensuel enregistré **800 €**, charges **0 €**. Encaisser **400 €**, émettre automatiquement et ouvrir le document. Encaisser ensuite les **400 €** restants pour la même période et demander le justificatif complet.

**Attendu :** délivrer un reçu pour les premiers 400 €, puis permettre une quittance de 800 € après règlement intégral, en conservant la trace du reçu. L'article 21 distingue expressément le [reçu pour paiement partiel](https://www.legifrance.gouv.fr/loda/article_lc/LEGIARTI000028806698/2026-03-12).

**Produit réel — `partiel` :**

```text
premiere : numero=1 ; total=400.0
HTML : <h1>Quittance de loyer</h1>
après solde : encaisse={loyer:800.0, charges:0.0} ; alerte=null
nouvelle émission : ValueError: Une quittance existe déjà … en 2026-01 (n° 00001).
```

**Conséquence :** les premiers **400 € restant dus** ne sont pas distingués sur le document. Une fois payés, **400 € supplémentaires restent hors du justificatif disponible**, sans alerte de sous-attestation ni parcours de complément. Cela ne démontre pas qu'un juge effacerait la dette : le défaut établi est le mauvais type de document et l'impossibilité de produire ensuite le justificatif complet.

### P-03 — La ventilation conseillée est refusée ; la relocation attribue le total au premier occupant

**Gravité : majeur.**

**Fichier et fonctions :** `modules/quittances.py`, `emettre`, **180**, recherche et refus par logement à **212–232** ; `montants_depuis_ecritures`, **140**, agrégation à **173–176** ; `present_le`, **119**.

**Scénario A :** deux colocataires fictifs, **800 € encaissés** pour janvier. Suivre le conseil de l'erreur : émettre **400 €**, charges 0, pour chacun.

**Attendu :** permettre deux parts contrôlées totalisant 800 €, ou proposer un document global nommant les bénéficiaires concernés. Ne pas conseiller un parcours qui refuse la seconde part.

**Produit réel — `colocation_parts` :**

```text
premiere : numero=1 ; total=400.0
seconde : ValueError: Le logement a déjà été quittancé pour 2026-01 …
message : « indiquez le montant revenant à chacun dans les champs Loyer et Charges »
nombre=1
```

**Scénario B indépendant :** février 2026 compte **28 jours**. Alpha sort le 14 février, Beta entre le 15. Le loyer mensuel est 800 €, charges 0. Saisir **400 € le 10 février pour Alpha**, puis **400 € le 20 pour Beta**, avec les tiers correspondants. Émettre automatiquement pour Alpha, puis pour Beta.

**Attendu :** chaque occupant a payé sa part de **14/28 × 800 = 400 €**. Attester ce paiement identifié ; ne pas attribuer à Alpha les fonds de Beta. Ce scénario ne demande pas de calculer un montant dû à la place d'un encaissement.

**Produit réel — `relocation` :**

```text
presence=[true,true]
premiere : locataire=Alpha ; total=800.0
seconde : ValueError: Le logement a déjà été quittancé pour 2026-02 …
```

**Conséquence :** A laisse **400 € sans quittance** ; B atteste **400 € de trop au nom d'Alpha** et empêche le document des **400 € payés par Beta**. Les dates servent à autoriser le mois, pas à répartir les fonds ; le tiers saisi n'est pas exploité par le rapprochement.

**Diagnostic amendé par rapport à B :** le refus séquentiel d'une seconde quittance automatique tient. Il empêche bien les deux documents de 800 € initialement décrits. Il ne réalise toutefois pas la ventilation qu'il conseille, ni l'affectation correcte du premier document lors d'un changement d'occupant. Le contournement concurrent demeure traité séparément en Q-04, sans nouveau numéro ici.

### P-04 — Un compteur illisible autorise la restauration et le rejeu d'un numéro remis

**Gravité : majeur.**

**Fichier et fonctions :** `modules/perennite.py`, `_max_quittance`, **93**, repli sur 0 à **104–105** ; `_avertir_quittances_perdues`, **108** ; `restaurer`, **123**, appel de la garde à **157**.

**Scénario :** base indépendante avec trois encaissements de **800 €**, janvier à mars. Émettre janvier n° 1, sauvegarder, émettre février n° 2 et mars n° 3. Injecter un défaut de schéma par `ALTER TABLE quittance RENAME COLUMN numero TO numero_endommage`, fermer la connexion, restaurer la sauvegarde au n° 1, puis émettre mars.

Cette altération est **volontaire**, pour rendre la lecture du compteur impossible tout en gardant une base SQLite copiable. Elle ne représente pas une migration produite spontanément par le logiciel.

**Attendu :** annoncer que le contrôle des quittances remises est impossible et empêcher une reprise automatique de la numérotation tant que leur dernier numéro n'a pas été retrouvé.

**Produit réel — `compteur_illisible` :**

```text
restaurer : retour=<TEMP_FICTIF>/…/compta-…-avant-restauration.db
nouvelle : numero=2 ; periode=2026-03 ; total=800.0
nombre en base active=2
```

**Conséquence :** deux documents différents portent le **n° 2**, février avant restauration et mars après restauration, chacun pour **800 €**. L'échec de lecture a été assimilé à l'absence de quittance. Une copie de sûreté est créée : les anciennes lignes ne sont pas déclarées irrécupérables, mais leur existence n'empêche pas le rejeu.

**Limite du correctif B confirmée :** sans altération, le scénario demandé **1 → sauvegarde → 2 → 3 → restauration** est bloqué, annonce correctement **2 quittances menacées**, puis l'émission suivante reçoit **4**. Il reste alors **un seul document portant le n° 2**. P-04 vise exclusivement le contrôle incapable de lire, pas ce parcours corrigé.

### P-05 — Le document ne conserve pas l'identité et l'adresse de son émission

**Gravité : majeur.**

**Fichiers et fonctions :** `modules/quittances.py`, `emettre`, **180**, champs conservés à **257–262** ; `detail`, **287**, jointures à **290–299** ; `app.py`, `quittance_imprimable`, **1165**. Schéma de `quittance` : `schema.sql`, **202**.

**Scénario :** émettre le n° 1, **800 €**, pour « Locataire Alpha Fictif », puis sauvegarder. Corriger directement le référentiel par SQL : remplacer le nom du locataire par « Locataire Beta Fictif » et l'adresse du logement par « Autre adresse fictive », sans modifier la quittance. Réouvrir `/quittance/1`. Restaurer ensuite la sauvegarde, qui porte également le maximum 1.

**Attendu :** conserver dans la réédition l'identité et l'adresse du document original ; distinguer explicitement tout nouveau document résultant d'une correction. Une restauration ne devrait pas substituer silencieusement une autre version sous le même numéro.

**Produit réel — `identite_non_figee` :**

```text
avant=Locataire Alpha Fictif
apres=Locataire Beta Fictif ; adresse=Autre adresse fictive ; numero=1
html_beta=true
apres_restauration=Locataire Alpha Fictif
```

**Conséquence :** le justificatif de **800 €** change de bénéficiaire et de logement imprimé sans changer de numéro ; la restauration revient à la première version sans refus. Le bailleur ne peut plus demander au logiciel une réédition fidèle indépendamment du référentiel courant.

**Portée précise :** la correction du référentiel est une intervention SQL contrôlée. Aucune route de modification de locataire n'a été inventée, ni aucun changement spontané du nom démontré. Le défaut est l'absence de conservation autonome du document après une correction de données ; il ne démontre pas un accès SQL offert au locataire.

### P-06 — Le gabarit accepte un justificatif sans adresse postale ni date du paiement

**Gravité : mineur.**

**Fichiers et fonctions :** `modules/quittances.py`, `emettre`, **180**, date facultative à **248–249** et **261** ; `detail`, **287** ; `app.py`, `quittance_imprimable`, **1165**. `PAGE_QUITTANCE_IMPRIMABLE`, `modules/pages.py`, adresse de repli à **2079–2083**, date conditionnelle à **2096**.

**Scénario :** logement dont le libellé est « Logement Alpha Fictif », adresse postale vide ; adresse du bailleur vide. Encaisser **800 € le 10 janvier 2026**, puis émettre la quittance sans renseigner à nouveau la date de paiement. L'exercice est réellement clôturé avant l'émission dans cet essai.

**Attendu :** reprendre la date de l'encaissement identifié ou demander sa confirmation, et empêcher qu'un simple libellé interne soit présenté comme l'adresse du logement sans avertissement.

**Produit réel — `mentions_clos` :**

```text
date_paiement=null ; mention_paiement=false
libelle_utilise=true
HTML : logement situé « Logement Alpha Fictif »
```

**Conséquence :** le document des **800 €** ne situe pas postalement le logement et ne date pas le paiement, alors que sa date est connue dans l'opération. La date d'émission reste présente. Aucun écart monétaire n'est établi ; il s'agit de la qualité et de la traçabilité du justificatif. Ce constat ne prétend pas que chacun de ces champs est énuméré comme obligatoire par l'article 21 : celui-ci impose expressément la ventilation, qui est bien imprimée.

### P-07 — Un locataire absent de la liste d'empreintes traverse le générateur de démonstration

**Gravité : majeur.**

**Fichiers et fonctions :** `outils_demo.py`, `construire_seed_demo`, **350**, écriture et contrôle à **449–451** ; `_controler_apres_generation`, **164** ; `verifier_depot.py`, `_empreintes`, **66**, `empreintes`, **118**.

**Scénario :** copier les deux outils dans un répertoire temporaire avec uniquement des sources fictives. Fournir un seed valide contenant un exploitant, un bien et une ligne `locataire` au nom « Locataire Secret Fictif ». Fournir un FEC synthétique et une liste d'empreintes non vide contenant seulement `TermeAbsentFictif`. Exécuter le véritable générateur, prérequis et contrôle final compris.

**Attendu :** anonymiser explicitement le contenu de la table `locataire`, l'exclure du seed de démonstration, ou refuser une table personnelle non prise en charge. Le contrôle ne doit pas dépendre exclusivement de l'inscription manuelle de chaque nouveau locataire.

**Produit réel — `demo_locataire` :**

```text
generation : retour=<TEMP_FICTIF>/outil/seed_demo.sql
sortie_existe=true
nom_locataire_conserve=true
promesse_absence=true  [en-tête : « AUCUNE donnée personnelle »]
```

**Conséquence :** si un seed source contient un locataire non inscrit dans la liste, son nom est conservé dans l'artefact destiné à la distribution, malgré la promesse d'anonymisation. Pas de montant d'impôt associé.

**Diagnostic borné :** le `seed_demo.sql` actuellement fourni a été exécuté séparément : **0 locataire, 0 quittance**. Aucune fuite réelle dans ce fichier n'est affirmée. En ajoutant le nom fictif à la liste, le contrôle final refuse la génération et supprime le fichier : `ANONYMISATION INCOMPLÈTE`, `fichier_supprime=true`. Les corrections F sur l'absence d'empreintes et le contrôle après génération ne sont donc pas resignalisées ; le cas nouveau est une table personnelle non couverte par l'inventaire nominatif.

## Ce qui a été vérifié et tenu

### Les trois corrections antérieures

- **Restauration normale : protection bloquante**, pas simple confirmation. Après trois émissions et une sauvegarde au n° 1, le POST de restauration suivi de sa redirection rend HTTP 200 avec « Restauration refusée » et **2 quittances menacées**. Les numéros restent **1, 2, 3** ; une nouvelle émission prend **4**. Le message de refus n'est pas un succès de restauration. La fragilité en cas de lecture impossible est P-04.
- **Colocation séquentielle :** le deuxième document automatique pour le même logement/mois est refusé, y compris en relocation. Les deux quittances intégrales du scénario initial ne sont plus émises séquentiellement. Les limites de ventilation sont décrites en P-03.
- **Contre-passation :** `operations.annuler` (**350**) conserve la quittance n° 1 de **800 €** ; `detail` rend **encaisse=0, atteste=800** et le HTML affiche l'avertissement. La ligne n'est pas supprimée et son numéro ne disparaît pas. L'avertissement annonce qu'une quittance remise ne se corrige pas ; il ne constitue pas à lui seul un processus d'émission de rectificative. Le rendu imprimé de cet avertissement reste une question ci-dessous.

### Numérotation, transactions et exercice clos

- **Collision simultanée du même numéro, réexécutée :** deux connexions sont synchronisées juste après leur lecture du prochain numéro. Une émission réussit ; l'autre reçoit `IntegrityError: UNIQUE constraint failed: quittance.numero`. Après fermeture : **1 quittance, 1 opération**, aucune quittance précédemment validée perdue. C'est une erreur SQL brute côté moteur, pas un numéro réservé ni un mécanisme de relance. Ce cas est déjà inclus dans **[Q-04](AUDIT_PASSE_Q.md)** ; le contournement du contrôle par logement avec deux numéros différents y est également documenté.
- **Transaction : protection non tenue, recoupement [Q-01](AUDIT_PASSE_Q.md).** Un loyer de 800 € saisi avec `commit=False`, puis `assurer_schema`, donne `transaction_avant=true`, `transaction_apres=false`, et **1 opération après rollback**. Le défaut déjà identifié n'est pas renuméroté P. Les tables étaient déjà présentes : la création à la volée n'est pas nécessaire pour le déclencher.
- **Suppression : portée limitée du schéma.** Après émission des n° 1 à 4, une suppression SQL explicite du n° 4, puis une émission de 500 € pour mai, réutilise **4**, auparavant porté par avril pour **800 €** (`suppression_sql`). `prochain_numero` (**129**) n'est donc pas un compteur indépendant : le maximum des lignes restantes fait foi. **Aucune route de suppression de quittance n'a été trouvée dans les pièces examinées** ; ce résultat n'est pas transformé en défaut de suppression accessible par l'interface.
- **Exercice clos :** clôture effective de 2026, puis émission et lecture d'une quittance : exercice toujours **clos**, contenu des écritures identique. La quittance peut être créée sans rouvrir ni modifier ces écritures. L'essai porte sur un paiement enregistré avant clôture.

### Document et données des tiers

- **Ventilation présente :** le HTML comporte des lignes distinctes « Loyer hors charges », « Provision pour charges » et « Total réglé ». Les valeurs peuvent toutefois être faussées manuellement, P-01. Identités, période en lettres, numéro et date d'émission sont présents dans le cas configuré.
- **Échappement réel :** le nom synthétique `Alpha & <script>alert(1)</script> Fictif` devient notamment `&amp;` et `&lt;script&gt;` dans la réponse Flask ; aucune balise `<script>alert(1)</script>` n'est rendue. Le SIREN fictif du bailleur est absent du document testé.
- **Impayé sans montants forcés :** refus explicite « Aucun encaissement trouvé ». Aucun avis d'échéance n'est créé à sa place. Le contournement manuel est P-01.
- **Encaissement sans quittance :** après encaissement de février sans émission, la page `/quittances` ne présente pas cette période comme restant à quittancer (`fevrier_non_quittance_visible=false`). L'essai n'établit pas une alerte dédiée ailleurs. L'absence d'émission systématique n'est pas en soi un défaut juridique : la remise est due au locataire qui la demande.
- **FEC :** un nom présent uniquement dans `locataire` n'apparaît pas dans l'export réel. Le même nom placé dans le libellé de l'opération apparaît dans le FEC. C'est une distinction entre export des écritures et export des tables de quittancement, pas une anonymisation du FEC.
- **Sauvegarde SQLite :** la copie contient effectivement le nom fictif de la table `locataire`. C'est une sauvegarde des données personnelles également, pas un export anonymisé.
- **PDF de liasse :** génération réelle, extraction par `pdftotext` ; le nom du locataire traceur est absent, y compris après son inscription dans un libellé comptable.
- **Journal d'erreurs :** après initialisation du vrai journal et exception synthétique contenant ce nom, `logs/erreurs.log` le conserve. Cela établit une possibilité de conservation locale ; aucune fuite réseau ni collecte automatique du nom par toutes les erreurs n'est affirmée.
- **Disque :** un GET de la quittance produit une réponse HTML et **aucun nouveau fichier dans le dossier du dossier comptable**. L'enregistrement volontaire en PDF par le navigateur n'a pas été exécuté. Les HTML joints sont enregistrés par le script d'audit lui-même.
- **Démonstration présente :** exécution du seed client fourni : **0 ligne dans `locataire`, 0 dans `quittance`**. Le contrôle final du générateur supprime correctement une sortie contenant une empreinte fictive connue. P-07 concerne l'ajout d'un locataire absent de cette liste.

## Non vérifiable avec les pièces fournies

- Dans les navigateurs utilisés pour remettre les quittances, que devient à l'impression l'avertissement après contre-passation ? Le HTML réel le place dans `class="noprint"` et le gabarit définit `@media print … .noprint { display: none; }` (`modules/pages.py`, **2057**, **2063**) ; un rendu d'impression est-il disponible pour confirmer le résultat sur le document remis ? Aucun moteur de navigateur n'a été exécuté ici.
- Où les navigateurs et imprimantes des utilisateurs conservent-ils leurs PDF, téléchargements, caches ou files d'impression, et pendant combien de temps ? Le GET serveur testé ne renseigne pas cette conservation extérieure.
- Des outils de maintenance, migrations ou procédures externes autorisent-ils la suppression d'une quittance ou la correction du référentiel après remise ? Aucun parcours web correspondant n'a été trouvé ; les scénarios SQL P-05 et `suppression_sql` ne prouvent pas son existence.
- Comment la dernière numérotation remise est-elle récupérée lorsqu'une base active est perdue ou devenue illisible, notamment si la copie de sûreté n'est plus accessible ? Existe-t-il un registre externe de remise, indépendant du maximum SQLite ?
- Quelle procédure métier permet de délivrer une rectificative, de la rattacher à l'original et de conserver la preuve de sa transmission au locataire ? Le message d'avertissement ne démontre pas ce suivi.
- Quelles règles de bail doivent couvrir les paiements par colocataire, les solidarités, les proratas, les forfaits et les régularisations ? Le scénario février établit une mauvaise affectation de deux paiements connus, sans certifier tous les cas contractuels de calcul du dû.
- Les archives de distribution et historiques de démonstration déjà remis contiennent-ils des noms de locataires dans d'autres champs ? Le comptage du seed client présent et les scénarios fictifs ne permettent pas de certifier tous les anciens artefacts ; aucune comparaison avec des identités privées n'a été effectuée.
- Les journaux, sauvegardes et fichiers produits sont-ils partagés, synchronisés ou transmis au support dans l'installation réelle ? Les chemins locaux et contenus synthétiques testés ne prouvent pas la destination de données réelles ni l'absence de toute communication réseau.

## Tableau récapitulatif numéroté

| N° | Constat | Conséquence établie | Gravité |
|---|---|---|---|
| P-01 | Montants manuels sans rapprochement contraignant | 880 € attestés sans paiement ; 80 € de charges transformés en loyer sans alerte | majeur |
| P-02 | Paiement partiel traité comme quittance définitive | 400 € restants non distingués, puis impossibilité de quittancer le solde payé | majeur |
| P-03 | Parts refusées et fonds de deux occupants agrégés | 400 € attribués au mauvais occupant ; seconde part non quittançable | majeur |
| P-04 | Échec de lecture du compteur assimilé à zéro | N° 2 réattribué après restauration, deux périodes différentes de 800 € | majeur |
| P-05 | Identité et adresse non conservées à l'émission | Même n° 1 de 800 € réédité pour un autre nom après correction SQL | majeur |
| P-06 | Adresse et date de paiement manquantes acceptées | Justificatif de 800 € incomplet, sans écart monétaire | mineur |
| P-07 | Table personnelle non couverte par l'anonymisation | Nom fictif conservé dans le seed généré malgré le contrôle final | majeur |

**Recoupements sans nouvelle numérotation : Q-01 (commit implicite), Q-04 (concurrence).** Aucun choix de modèle comptable expressément assumé n'est signalé comme défaut.

**État du suivi :** les sept constats ont été corrigés en production le 16 septembre 2026 (version 8.49.0). Les preuves de `preuves_p/` sont conservées **telles qu'observées avant correction** : elles restent la référence du défaut, pas de l'état actuel du code. La non-régression est figée par `tests/test_passe_p.py` (30 tests), dont 23 échouent si l'on retire les correctifs.

Trois précisions. **P-02 et P-03 ont demandé une évolution de schéma** (palier 8) : le type de document et l'identité figée entrent dans la table `quittance`, et l'unicité passe de (locataire, période) à (locataire, période, type). Une contrainte d'unicité déclarée dans un `CREATE TABLE` ne s'altère pas : la table est reconstruite au premier accès sur les bases existantes, les quittances déjà émises étant reprises comme telles. **P-03 inverse la logique du garde-fou** : ce n'est plus le nombre de documents qui est borné, mais le montant attesté — deux parts de 400 € sur 800 € encaissés sont légitimes, une troisième ne l'est pas. Enfin, **P-04 ne bloque pas une base globalement sinistrée** : refuser la restauration quand la base courante est elle-même illisible enfermerait l'utilisateur dans sa panne ; le refus vise le cas où la base est saine mais sa table de quittances ne se lit plus.

Un point de méthode sur **P-01** : le rapprochement avec l'encaissement est désormais bloquant à l'émission, avec une dérogation `forcer=True`. Onze appels de tests existants ont dû la déclarer — ce sont des fixtures qui attestaient sans saisir d'encaissement, pour éprouver la numérotation ou l'impression.
