# Audit — passe G : régularité comptable et intégrité du FEC

**15 septembre 2026 — 15 constats reproduits : 2 critiques, 11 majeurs, 2 mineurs.**

Code examiné : `compta_lmnp_v8.41.0/compta_lmnp/`. Les chemins de modules ci-dessous sont relatifs à ce répertoire.

Les risques principaux sont une reprise qui perd des lignes sans annoncer leur rejet, une cession acceptée avec un prix non numérique, et des contrôles capables de déclarer conformes des écritures qu'ils n'ont pas correctement vérifiées.

## Pièces, méthode et références

Lecture préalable des invariants, du récapitulatif de la passe A dans le CHANGELOG v8.36.0, des correctifs D2/E/F déjà consultés et du [rapport Q](AUDIT_PASSE_Q.md). Les rapports antérieurs supprimés dans l'arbre de travail restent consultables dans Git ; ces suppressions n'ont pas été modifiées. Les défauts Q ne sont pas renumérotés comme des découvertes G.

Les essais utilisent exclusivement des bases **blanches**, un exploitant fictif et des FEC construits pour l'audit. Aucune donnée de `reference/`, aucun seed privé, aucune base comptable réelle n'est utilisé. Aucun code de production n'a été corrigé.

Livraison reproductible : [script](preuves_g/reproduire.py), [sorties complètes et empreintes des sources](preuves_g/resultats.json), [matrice de couverture](preuves_g/COUVERTURE.md).

```bash
compta_lmnp_v8.41.0/compta_lmnp/.venv/bin/python docs/preuves_g/reproduire.py
```

Environnement exécuté : **Python 3.14.6 / SQLite 3.51.2**. Les bases temporaires sont supprimées après exécution. Les erreurs attendues sont capturées et leur persistance en base mesurée ; une erreur du dispositif d'audit produit un code de sortie non nul. Les vues web sont exécutées dans un contexte Flask de requête, avec des chemins temporaires et de vrais fichiers transmis à la vue.

Les sources officielles suivantes ont été consultées le jour de l'audit :

- **R1 — [Article A47 A-1 du LPF](https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000027804775)** : premières colonnes, types des champs, séparateurs, dates, encodages et ordre de validation. Le texte admet tabulation ou barre verticale, ainsi que retour chariot et/ou fin de ligne ; CRLF est donc un choix admis, pas l'unique fin de ligne permise.
- **R2 — [BOI-CF-IOR-60-40-20, §100, 120 et 250](https://bofip.impots.gouv.fr/bofip/9028-PGP.html/identifiant=BOI-CF-IOR-60-40-20-20170607)** : numérotation globale ou par journal ; distinction entre date comptable et date de validation, avec égalité possible sans mode brouillard.
- **R3 — [Questions-réponses DGFiP, mise à jour du 19 décembre 2014](https://www.impots.gouv.fr/portail/1metier2professionnelcomptabiliteinformatiseequestionreponsepdf)** : notamment question 14 sur les trous justifiables par le mode brouillard et questions 5–7 de la partie technique sur les colonnes supplémentaires. Cette notice complète la lecture de la norme ; les exemples observés dans un cabinet ne suffisent pas à définir celle-ci.
- **R4 — [Plan de comptes ANC 2026](https://www.anc.gouv.fr/files/anc/files/1_Normes_fran%C3%A7aises/Plans%20comptables/2026/Plan-de-comptes-2026.pdf)** : qualification des comptes de tiers.

Les constats ci-dessous décrivent les sorties de ce logiciel. **Un verdict du validateur local n'est pas une décision d'acceptation de l'administration.** Les euros cités mesurent les écarts observés, sans simuler l'impôt personnel.

## Constats

### G-01 — Le contrôle d'équilibre précède l'arrondi réellement enregistré

**Gravité : majeur.**

**Fichier et fonction :** `modules/ecritures.py`, `inserer`, ligne **98** ; sommes contrôlées à **119–122**, arrondi des lignes à **190**.

**Scénario :** appeler le guichet avec deux débits de **100,004 €** sur `108000` et un crédit de **200,008 €** sur `708810`, exercice 2026, date `2026-01-10`, contrôles activés par défaut.

**Attendu :** refuser la précision ou vérifier l'équilibre des montants qui seront effectivement inscrits. Aucun déséquilibre durable.

**Produit :**

```text
retour : ecriture_id=1, ecriture_num=1
ecriture=1, ligne=3
totaux en base : [200.0, 200.01]
validation : conforme=false
Écriture 1 déséquilibrée: débit 200.00 ≠ crédit 200.01.
```

**Conséquence :** **0,01 € de déséquilibre durable** et FEC refusé par le validateur local. Le contrôle arrondit la somme alors que l'insertion somme ensuite des lignes arrondies. Aucune absorption de ce centime dans un compte n'est effectuée. Les saisies ordinaires arrondissent leur montant avant cet appel ; le défaut établi concerne le guichet général acceptant plus de deux décimales.

### G-02 — Le rejeu perd des écritures raccourcies et annonce une reprise réussie

**Gravité : critique.**

**Fichiers et fonctions :** `modules/fec_io.py`, `lignes_nommees`, ligne **162**, filtre à **169–170** ; `modules/rejeu_fec.py`, `rejouer`, ligne **28** ; `app.py`, `exercice_reprendre_fec`, ligne **2044**. Autre consommateur : `modules/reprise.py`, `lire_balance_fec`, ligne **26**, filtre à **37–38**.

**Scénario :** un FEC contient deux loyers de **800 €**, soit quatre lignes. Retirer seulement les deux dernières colonnes vides des deux lignes du second loyer : elles conservent donc seize champs, dont tous les montants. Rejouer le fichier ; faire aussi passer sa variante 2025 par la vue d'import web.

**Attendu :** rejet explicite avant import, ou compte rendu des lignes écartées empêchant de confondre la reprise avec un succès complet.

**Produit :**

```text
lignes_brutes=4 ; lignes_nommees=2
balance lue : 108000=1600.0 ; 708810=-1600.0
rejeu : ecritures=1, normalisees=0, renumerotees=false
produits en base=800.0
web : « Exercice 2025 repris depuis le FEC : 1 écritures rejouées ... »
```

Appelé séparément, `valider` signale bien `L.4: 16 champs au lieu de 18` et `L.5: 16 champs au lieu de 18`. Il n'est pas le garde préalable de cette reprise. Une variante de onze champs est également ignorée par `lire_balance_fec`, sans rapport de rejet.

**Conséquence :** **800 € de recettes disparaissent de la reprise**, de façon équilibrée. Le lecteur brut préserve les lignes comme annoncé ; la perte intervient plus loin. Un fichier à dix-sept colonnes est même repris avec un retour réussi `ecritures=0`.

### G-03 — Le validateur fusionne des journaux et contrôle la mauvaise séquence

**Gravité : majeur.**

**Fichier et fonction :** `modules/valider_fec.py`, `valider`, ligne **79**, regroupement à **175–179**, continuité à **198–203**. Comparaison exécutée avec `modules/rejeu_fec.py`, `rejouer`, ligne **28**.

**Scénario A :** `AC/1` contient seulement un débit de **800 €** ; `BQ/1` contient seulement un crédit de **800 €**.

**Attendu :** signaler les deux écritures déséquilibrées et à une seule ligne.

**Produit :**

```text
valider : conforme=true, nb_erreurs=0, observations=[]
rejouer : ValueError: Écriture déséquilibrée : débit 800.00 € / crédit 0.00 €.
rejeu durable : ecriture=0, ligne=0
```

**Scénario B :** quatre écritures équilibrées, séquences `AC:10,11` et `BQ:20,21`.

**Produit :** le rejeu conserve quatre écritures, mais le validateur réclame les numéros **12 à 19**. Inversement, `AC:1,3` et `BQ:1,2` donnent `conforme=true` : le numéro 2 de BQ masque le trou d'AC.

**Conséquence :** des écarts de **800 € par écriture** sont approuvés par compensation entre journaux ; des séquences par journal admises sont rejetées. Le regroupement corrigé dans le **rejeu** en passe A tient ; il n'a pas été porté dans le validateur. La numérotation par journal est explicitement admise. [R2, §100](https://bofip.impots.gouv.fr/bofip/9028-PGP.html/identifiant=BOI-CF-IOR-60-40-20-20170607)

**Nuance sur les trous :** la notice DGFiP admet des ruptures explicables par la validation du brouillard ; un rejet réglementaire automatique de tout trou est donc trop catégorique. Le logiciel peut conserver un contrôle strict sur **ses propres** numéros sans assimiler tout écart externe à une non-conformité certaine. [R3, question 14](https://www.impots.gouv.fr/portail/1metier2professionnelcomptabiliteinformatiseequestionreponsepdf)

### G-04 — Les numéros d'écriture alphanumériques empêchent la migration

**Gravité : majeur.**

**Fichiers et fonctions :** `modules/valider_fec.py`, `valider`, ligne **175** ; `modules/rejeu_fec.py`, `rejouer`, ligne **71**.

**Scénario :** deux écritures équilibrées de **800 €**, numérotées `BQ0001` et `BQ0002`, journal BQ, toutes les autres colonnes renseignées normalement.

**Attendu :** lire ces identifiants ; le champ réglementaire est alphanumérique. [R1, VII-1](https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000027804775)

**Produit :**

```text
L.2: EcritureNum 'BQ0001' non entier.
... quatre erreurs de même nature
rejeu : ValueError: invalid literal for int() with base 10: 'BQ0001'
ecriture=0 ; ligne=0
```

**Conséquence :** impossibilité de reprendre ce FEC de **1 600 €** ; pas de perte durable mesurée sur cet essai. La conversion en entier est une contrainte du logiciel, pas du format légal.

### G-05 — Trois variantes admises du format sont déclarées non conformes

**Gravité : majeur.**

**Fichiers et fonctions :** `modules/fec_io.py`, `lire_brut`, ligne **140**, tabulation imposée à **155** ; `nombre`, ligne **38** ; `modules/valider_fec.py`, `_parse_montant`, ligne **31**, et `valider`, comparaison d'en-tête à **98**.

**Scénarios indépendants :** partir d'une écriture équilibrée de 800 €, puis appliquer chacune des variantes suivantes, en conservant une structure homogène.

| Variante | Attendu | Produit réel |
|---|---|---|
| Séparateur `\|` au lieu de tabulation | Lecture des dix-huit champs | En-tête « reçu 1 » ; rejeu réussi de **0 écriture** |
| Montants négatifs `800,00-` au lieu de `-800` | Lecture du signe suffixé | Deux « montant illisible » ; rejeu en `ValueError` |
| Dix-neuvième colonne nommée `Information`, vide | Reconnaissance des dix-huit premières et du champ supplémentaire | En-tête « reçu 19 » ; le rejeu, lui, conserve l'écriture |

La barre verticale et le signe suffixé sont admis par le texte ; les dix-huit informations sont les **premières**, pas un maximum de colonnes. [R1, VI, VII et XII](https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000027804775), [R3, partie technique, questions 5–7](https://www.impots.gouv.fr/portail/1metier2professionnelcomptabiliteinformatiseequestionreponsepdf)

**Conséquence :** rejet injustifié de fichiers de cabinet. Dans la variante `|`, **800 € ne sont pas importés**, avec le même défaut de compte rendu que G-02. Les trois essais détaillés figurent sous `variantes_format` ; ils ne prouvent pas une acceptation administrative individuelle de leurs données fictives.

### G-06 — Des montants non numériques ou non finis passent le validateur

**Gravité : majeur.**

**Fichier et fonctions :** `modules/valider_fec.py`, `_parse_montant`, ligne **31**, conversion à **48** ; `valider`, calculs à **175–196**, appariement devise à **169–171**.

**Scénarios :** remplacer le débit par `NaN` et le crédit par **999** ; puis essayer deux montants `inf`, deux montants `1e309`, et une écriture normale de 800 € avec `Montantdevise=BOGUS`, `Idevise=USD` sur une ligne.

**Attendu :** refuser une valeur monétaire non finie ou non numérique, avant d'affirmer l'équilibre.

**Produit, pour chacun de ces quatre fichiers :**

```text
conforme=true ; nb_erreurs=0 ; erreurs=[] ; observations=[]
```

**Conséquence :** le garde affirme un résultat qu'il ne peut pas calculer. Aucun écart monétaire fini ne peut être établi pour NaN. Le guichet `ecritures.inserer` refuse pourtant NaN et inf ; il n'y a pas de preuve que ces valeurs aient été enregistrées par une saisie ordinaire. Deux `1e3` passent également sans signal sur la notation.

**Diagnostic amendé par exécution :** `inf` opposé à 999 est bien signalé comme déséquilibré ; c'est notamment **inf face à inf**, ou une somme contaminée par NaN, qui neutralise les comparaisons. Il serait faux d'écrire que toute occurrence d'inf obtient un succès.

### G-07 — Le validateur approuve des dates impossibles et un préfixe de compte invalide

**Gravité : majeur.**

**Fichier et fonctions :** `modules/valider_fec.py`, `_date_valide`, ligne **53** ; `valider_nom_fichier`, ligne **62** ; `valider`, ligne **79**, contrôle du compte à **146–150**.

**Scénarios indépendants :** deux lignes équilibrées de 800 € datées `20260230`, puis le fichier ordinaire dont un `CompteNum` devient `4AB`. Tester aussi le nom fictif `000000000FEC20260230.txt`.

**Attendu :** refuser le 30 février ; contrôler les trois premiers caractères numériques du compte. [R1, VII-1 et XII](https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000027804775)

**Produit :**

```text
date_impossible : conforme=true, nb_erreurs=0
compte_non_pcg : conforme=true, nb_erreurs=0
valider_nom_fichier(...20260230.txt) : null
```

**Conséquence :** des fichiers portant des données obligatoires invalides sont annoncés conformes ; pas de différence en euros dans ces essais. `_date_valide` borne le jour à 31 sans vérifier le calendrier ; le compte est contrôlé en longueur seulement. Le guichet de saisie utilise une validation de date réelle et n'a pas ce défaut.

### G-08 — Le rejeu ne conserve pas les informations du FEC source

**Gravité : majeur.**

**Fichiers et fonctions :** `modules/rejeu_fec.py`, `rejouer`, ligne **28**, construction des lignes et appel à **91–109** ; `modules/ecritures.py`, `inserer`, insertion à **181–190** ; `modules/export_fec.py`, `lignes_fec`, ligne **67**.

**Scénario :** une écriture de **800 €** sur les comptes à sept chiffres `4110000` et `7088100`, date comptable 10 janvier 2026. Fournir les champs ci-dessous, rejouer puis réexporter.

**Attendu :** conserver les champs renseignés, ou annoncer explicitement une transformation qui ne restitue pas le FEC d'origine.

**Produit réel, première ligne :**

| Champ | Source | Réexport |
|---|---|---|
| CompAuxNum | AUX-FICTIF | vide |
| CompAuxLib | Tiers fictif | vide |
| PieceDate | 20260102 | 20260110 |
| EcritureLet | LET-1 | vide |
| DateLet | 20260125 | vide |
| ValidDate | 20260120 | 20260110 |
| Montantdevise | 900 | vide |
| Idevise | USD | vide |

Les deux fichiers reçoivent `conforme=true`. Le libellé du journal existant est aussi remplacé par celui du référentiel.

**Conséquence :** perte de l'identification auxiliaire, du lettrage et de la devise, et modification des dates de preuve. Les **800 €** restent équilibrés ; la fidélité du document est perdue. La vacuité de champs **inutilisés** dans la comptabilité native ne justifie pas d'effacer ceux fournis par un cabinet.

**Autre essai :** dans une même paire journal/numéro, une ligne datée 2026 et une ligne datée 2025 sont toutes deux reprises sous **2026-01-10**, avec retour réussi d'une écriture. Le validateur source signale ce mélange, mais le rejeu ne vérifie que la date de la première ligne du groupe. La protection contre un autre exercice tient lorsque chaque écriture possède un groupe distinct.

Il ne s'agit pas du constat D2 annulé « ValidDate jamais écrit » : **le champ est écrit**, mais sa valeur source n'est pas conservée.

### G-09 — Un FEC natif peut sortir en ordre décroissant de validation

**Gravité : majeur.**

**Fichiers et fonctions :** `modules/ecritures.py`, `inserer`, ligne **98**, affectation de date à **185** ; `modules/export_fec.py`, `lignes_fec`, ligne **67**, requête ordonnée par numéro à **63** ; `modules/valider_fec.py`, `valider`, ligne **79**.

**Scénario :** saisir un loyer de **800 €** daté du 10 mars 2026, puis celui de janvier, de **800 €**, daté du 10 janvier. Clôturer sans dotation puis exporter.

**Attendu :** un mécanisme cohérent de validation et d'export respectant son ordre chronologique. [R1, VII-1](https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000027804775)

**Produit :**

```text
EcritureNum / ValidDate :
1 / 20260310
1 / 20260310
2 / 20260110
2 / 20260110
validation : conforme=true
```

**Conséquence :** le fichier de **1 600 €** présente une chronologie de validation inversée sans alerte locale. Aucun écart de total constaté. L'égalité entre date comptable et date de validation peut être licite sans brouillard ; le constat vise **l'ordre observé du fichier**, pas cette égalité en elle-même. [R2, §250](https://bofip.impots.gouv.fr/bofip/9028-PGP.html/identifiant=BOI-CF-IOR-60-40-20-20170607)

### G-10 — L'export masque des lignes orphelines et le validateur approuve le résultat vide

**Gravité : majeur.**

**Fichiers et fonctions :** `modules/export_fec.py`, `lignes_fec`, ligne **67**, jointures internes à **58–61** ; `exporter`, ligne **86** ; `modules/valider_fec.py`, `valider`, ligne **79**. Structures concernées : `schema.sql`, tables à **68** et **81**, vue `v_fec` à **163**.

**Scénario :** créer et clôturer un loyer de **800 €**. Sur une connexion SQL de test, désactiver explicitement les clés étrangères et supprimer du plan les comptes `108000` et `708810`, en laissant les deux lignes comptables. Exporter. Variante : garder les comptes mais supprimer les lignes pour laisser un en-tête sans ligne.

**Attendu :** l'export signale qu'il ne peut pas restituer des écritures présentes ; le garde distingue un fichier sans écriture d'une vérification complète des données de la base.

**Produit :**

```text
compte absent : ecriture=1, ligne=2, totaux=[800.0,800.0]
lignes_exportees=0 ; validation conforme=true ; integrity_check=ok
en-tête sans ligne : ecriture=1, ligne=0, lignes_exportees=0
validation conforme=true
```

**Conséquence :** **800 €** présents dans la première base disparaissent du FEC sans échec d'export. Le contrôle d'intégrité structurelle SQLite n'est pas un contrôle des relations ni de l'exhaustivité de l'export.

**Limite explicite :** l'état défectueux est injecté par SQL ; les tests du guichet n'ont pas créé cet orphelin. Un exercice réellement sans mouvement peut donner un fichier vide de données. Ici, le fait déterminant est l'écart mesuré entre **la base** et son export.

**Correction du périmètre annoncé :** l'exporteur actuel ne lit pas directement `v_fec`. Il utilise une requête similaire, filtrée sur l'exercice ; ce filtre tient. Le problème reproduit est la disparition dans ses jointures internes. Pour un libellé de ligne `NULL`, la ligne reste exportée avec un champ vide, et le validateur la signale correctement.

### G-11 — Une cession avec prix NaN est enregistrée définitivement

**Gravité : critique.**

**Fichiers et fonctions :** `modules/cession.py`, `ceder_bien`, ligne **95**, contrôle du prix à **112**, test de génération du produit à **156**, commit à **168** ; `app.py`, `bien_ceder`, ligne **1748**, et `_form_float`, ligne **101**.

**Scénario :** bien fictif avec mobilier de **12 000 €**, durée dix ans, mis en service le 1er janvier 2026. Demander une cession le 30 juin avec `prix_cession=nan`. Exécuter la fonction et la vue web.

**Attendu :** prix refusé comme non fini ; aucune sortie d'actif ni date de cession persistante.

**Produit :**

```text
retour : dotation_complementaire=595.07 ; vnc_sortie=11404.93
prix_cession="nan" ; pv_comptable="nan"
durable : ecriture=2, ligne=5 ; date_cession="2026-06-30"
web : ok="Cession de Bien fictif enregistrée ... prix nan € ..."
FEC : conforme=true
```

**Conséquence :** **12 000 € d'actif sont sortis**, dont **11 404,93 € de VNC**, pour une demande qui aurait dû être rejetée ; aucune écriture de prix n'est générée. Le refus de NaN dans `ecritures.inserer` n'intervient jamais sur ce prix : `nan > 0` ne déclenche pas l'insertion du produit.

**Contre-épreuves :** prix négatif refusé ; prix inf refusé après deux écritures encore provisoires, toutes deux absentes après fermeture ; prix zéro accepté comme une cession sans produit. Ces comportements ne sont pas assimilés au défaut NaN.

### G-12 — L'absorption d'arrondi modifie une quote-part de terrain renseignée

**Gravité : majeur.**

**Fichier et fonction :** `modules/amortissement.py`, `ventilation_proposee`, ligne **272**, arrondi des proportions à **291**, compensation sur la plus grosse ligne à **296–299**.

**Scénario :** prix total **100 000,01 €**, quote-part de terrain fournie **0,73117**. Appeler la ventilation.

**Attendu :** terrain égal à l'arrondi de `100000.01 × 0.73117`, soit **73 117,01 €**, et répartition du solde entre les composants amortissables.

**Produit :**

```text
total=100000.01
ajustement : cle="terrain", compte="211550"
avant=73117.01 ; apres=73130.01
```

**Conséquence :** **13 €** déplacés vers le terrain non amortissable, malgré la quote-part fournie ; potentiel amortissable diminué d'autant si la proposition est utilisée. Ce n'est pas un centime sans effet : l'arrondi préalable des proportions à quatre décimales produit ici l'écart de 13 €, puis le compte le plus élevé l'absorbe.

Autre exécution, sans quote-part fournie : un centime est absorbé par le gros œuvre, de **45 000,00 à 45 000,01 €**, avec total conservé. Le problème établi est la modification de la composante fixée par l'utilisateur.

### G-13 — Un fichier ISO-8859-15 est lu avec altération silencieuse du texte

**Gravité : mineur.**

**Fichier et fonction :** `modules/fec_io.py`, `lire_texte`, ligne **48**, ordre des encodages à **45**, boucle à **64**.

**Scénario :** FEC fictif encodé en ISO-8859-15, libellé `Loyer fictif 800 €`. Lire puis rejouer le fichier.

**Attendu :** conserver le caractère euro, ou demander l'encodage si le décodage est ambigu.

**Produit :**

```text
conforme=true
rejeu : ecritures=1
libelles=["Loyer fictif 800 ¤", "Loyer fictif 800 ¤"]
```

**Conséquence :** altération des libellés et perte de fidélité textuelle ; **aucun montant numérique modifié** dans cet essai. CP1252 accepte cet octet avant que l'essai ISO-8859-15 ait lieu.

**Amendement du diagnostic antérieur :** la correction A supprime bien certains échecs de décodage ; elle ne garantit pas l'identité du texte décodé. Le même libellé encodé en CP1252 est correctement restitué avec `€`, et le BOM UTF-8 est correctement pris en charge. Le constat ne réclame pas une détection automatique certaine entre encodages ambigus.

### G-14 — Le validateur autonome retourne un succès système après des erreurs bloquantes

**Gravité : majeur.**

**Fichier :** `modules/valider_fec.py`. Fonction exécutée : `valider`, ligne **79** ; point d'entrée autonome au niveau du module, lignes **243–255** — il n'existe pas de fonction `main` dans ce fichier.

**Scénario :** lancer le script dans un sous-processus sur une écriture de **800 € au débit et 799 € au crédit**. Capturer sortie et code retour.

**Attendu :** message bloquant accompagné d'un code système non nul.

**Produit :**

```text
✗ .../invalide-cli.txt — 2 erreur(s) bloquante(s)
Écriture 1 déséquilibrée: débit 800.00 ≠ crédit 799.00.
Déséquilibre global: débit 800.00 ≠ crédit 799.00.
code_retour=0
```

**Conséquence :** une automatisation qui se fonde sur le code retour peut poursuivre avec un FEC présentant **1 € de déséquilibre**. Le texte est explicite pour le lecteur humain ; le défaut est le contrat de commande, pas l'absence de message.

### G-15 — Le typage par préfixe inverse certains sous-comptes de tiers

**Gravité : mineur.**

**Fichier et fonctions :** `modules/fec_io.py`, `type_du_compte`, ligne **77**, décisions à **108–113** ; `modules/rejeu_fec.py`, `rejouer`, création du compte à **52–56**.

**Scénario :** importer des lignes fictives de 800 € sur les comptes à sept chiffres `4090000`, `4190000`, `4250000`, puis lire `numero, type, classe` en base.

**Attendu :** `409` débiteur et `425` d'avances à l'actif ; `419` créditeur au passif. Ces sous-comptes sont identifiés distinctement dans le plan de comptes. [R4, classes 40 à 42](https://www.anc.gouv.fr/files/anc/files/1_Normes_fran%C3%A7aises/Plans%20comptables/2026/Plan-de-comptes-2026.pdf)

**Produit :**

```text
["4090000", "passif", 4]
["4190000", "actif", 4]
["4250000", "passif", 4]
```

**Conséquence :** métadonnée de classement incorrecte. Les numéros, classe et montants sont conservés ; **aucun écart déclaré en euros n'est établi** sur le modèle fourni. Les comptes 401 et 411 sont correctement typés comme corrigé en D2 ; étendre cette correction à toutes les tranches 40, 41 et 42 manque leurs exceptions. Les tranches mixtes 44/45/46/48 restent un repli au passif : elles ne sont pas présentées comme déduites automatiquement du solde.

## Résultats particuliers sur l'immuabilité et la continuité

Ces résultats délimitent les protections effectivement exécutées ; ils ne démontrent pas l'existence d'un bouton web de modification d'une écriture close.

| Geste sur une base fictive close, initialement à 800 € | Sortie réelle |
|---|---|
| `operations.annuler` sur l'opération close | Refus explicite ; une écriture et deux lignes conservées |
| Nouvelle saisie par `operations.saisir` | Refus « exercice 2026 clos » |
| SQL direct : multiplier débit et crédit par deux | Totaux 1 600/1 600 ; résultat figé 800 ; FEC localement conforme |
| SQL direct : renuméroter l'écriture en 99 | Mise à jour acceptée ; FEC localement conforme |
| SQL direct : supprimer opération puis écriture | Zéro écriture et zéro ligne ; résultat figé encore à 800 |
| Migration de schéma depuis une version marquée 2 | Version 7 ; octets du FEC avant/après identiques |
| Restaurer une sauvegarde antérieure à la clôture | Exercice de nouveau ouvert ; copie de sûreté conservant l'état clos |

Le scellement est donc une protection du **guichet applicatif**, pas un refus imposé par les tables SQLite contre tout SQL direct. La restauration est un retour arrière explicite et sauvegardé : sa capacité à rouvrir un exercice n'est pas signalée comme un défaut en soi. Les courses déjà reproduites en Q-02/Q-03 et le défaut de sûreté Q-05 restent dans le rapport Q.

La contrainte d'unicité refuse deux numéros identiques dans un exercice. Un numéro **imposé** à l'API peut néanmoins créer un trou : insertion de 1 puis 3 acceptée, validateur signalant le 2 manquant. Après annulation normale, les numéros 1 et 2 sont conservés ; après le rollback du groupe interrompu, le prochain numéro redevient **1**. Aucun trou issu du savepoint normal n'est observé.

## Ce qui a été vérifié et tenu

1. **FEC natif ordinaire fermé :** en-tête égal aux dix-huit noms attendus et dans leur ordre, quatre lignes de dix-huit champs, tabulations, UTF-8 sans BOM, cinq CRLF et aucun LF isolé, CRLF final. Les valeurs 800,25 et 100 sont sérialisées `800,25` et `100` ; les zéros sont vides. Les dates sont sur huit chiffres. Le validateur local renvoie **zéro erreur**.
2. **ValidDate sur un exercice clos :** renseignée dans l'export normal. La retirer d'une ligne produit une erreur obligatoire ; retirer PieceDate est aussi signalé. Lettrage, auxiliaires et devise sont vides dans les écritures natives testées. Les champs facultatifs inutilisés peuvent être vides. [R1, VII-1](https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000027804775)
3. **Équilibre usuel au guichet :** 800/799 est refusé **avant** insertion d'en-tête. NaN, inf et une liste vide le sont également. Un montant négatif ou un compte inexistant atteint l'insertion, puis la contrainte et le savepoint annulent tout : même après un commit volontaire, **zéro en-tête et zéro ligne**. Deux lignes à zéro sont acceptées par le guichet général ; la saisie d'opération refuse zéro. Cette distinction n'est pas transformée en écart fiscal non démontré.
4. **Contrat `commit=False` :** 43 gabarits standards et un personnalisé, deux opérations de 800 € chacun : transaction encore ouverte, puis **zéro opération, zéro écriture et zéro ligne après rollback**. Six loyers suivis d'un septième invalide donnent aussi zéro après rollback. Le lecteur de quittances conserve toutefois une opération après rollback : recoupement explicite de **Q-01**, pas nouveau constat.
5. **Annulation :** le loyer du 10 janvier 2026 est contre-passé en OD, dans 2026, à la même date, avec `PieceRef=ANNUL-1`, `PieceDate=2026-01-10`, numéro 2. Les débits/crédits sont inversés ; les deux écritures restent disponibles. Une tentative sur exercice clos est refusée.
6. **Cabinet à sept chiffres :** 24 écritures et 25 comptes créés, total **19 200 € au débit comme au crédit** ; comptes de banque, tiers, charges et produits conservés. 401 au passif, 411 à l'actif ; classe égale au premier chiffre. Les exceptions G-15 et le repli des tranches mixtes sont documentés dans la matrice, sans faire passer ce repli pour un classement au solde.
7. **À-nouveaux avec banque :** FEC source à 800 € sur `5120000` contre produit ; après reprise et affectation, solde banque **+800 €**, exploitant **−800 €**, résultat reporté soldé ; FEC équilibré et localement conforme. Un AN à 800 contre 799 est refusé ; zéro écriture durable après fermeture.
8. **Cession normale :** prix 15 000 €, mobilier 12 000 €, cession au 30 juin : trois écritures, sept lignes, débits/crédits égaux à **27 595,07 €**, FEC localement conforme. L'inf n'est pas durable après fermeture ; voir G-11 pour NaN.
9. **Guillemets :** le libellé commençant par un guillemet non refermé reste identique et ne fusionne pas les lignes : le correctif A tient. UTF-8 avec BOM et CP1252 testés sans altération ; ISO-8859-15 fait l'objet de G-13.
10. **Structure invalide :** `lire_brut` conserve les lignes courtes. Le validateur les signale, ainsi que la tabulation ajoutant un dix-neuvième champ et le saut de ligne coupant une ligne en fragments. L'en-tête absent provoque un signal du validateur et un `KeyError` au rejeu, pas un import réussi. Le rejeu avec tabulations décalant les montants est refusé et annulé.
11. **Exercices :** un FEC 2025 ciblé sur 2026 est refusé, zéro écriture durable ; un fichier mélangeant deux années dans des groupes distincts est également refusé. Un fichier entièrement 2025 reste cohérent pour le validateur de contenu, qui ne reçoit pas d'année cible. Le cas divergent **au sein d'un même groupe** est décrit en G-08.
12. **Rejeu par journal :** AC/1 et BQ/1 restent deux écritures distinctes, renumérotées 1 et 2 avec `renumerotees=true`. La fusion corrigée en A n'est pas réapparue. Les négatifs préfixés sont normalisés par inversion débit/crédit, avec compteur `normalisees=2` ; aucune ligne perdue dans cet essai.

## Non vérifiable avec les pièces fournies

- **Régularité de fond sans 512 :** les flux réels peuvent-ils tous être justifiés comme mouvements de l'exploitant dans ce modèle, et cette tenue satisfait-elle les obligations comptables applicables au dossier ? L'article de format ne prescrit pas à lui seul la présence d'un compte 512. Cela permet d'écarter l'affirmation « absence de 512 = rejet de format automatique », mais ne certifie pas la régularité de la comptabilité sous-jacente. Une validation sur le dossier et ses justificatifs par un professionnel ou l'administration reste à établir. Aucun constat n'est porté contre le choix 108000. [R1](https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000027804775)
- L'outil DGFiP de contrôle, puis le service vérificateur, acceptent-ils les fichiers produits après correction, avec leur nom de remise et leur description technique ? Aucun verdict de ces deux acteurs n'a été exécuté ici ; seul le validateur du logiciel l'a été.
- Quelle politique de conservation du FEC d'origine, de correspondance des numéros et d'archivage s'applique après la reprise d'un cabinet ? Une renumérotation d'import signalée ne prouve pas que le FEC historique remis à l'administration doit être remplacé par ce réexport.
- Quelle procédure documente les ruptures de numérotation des FEC externes lorsqu'elles proviennent d'un mode brouillard ? La seule liste des entiers manquants ne permet pas de trancher leur justification.
- Les exports natifs devraient-ils être bloqués, ou marqués provisoires, avant la clôture et les contrôles ? L'audit de format n'établit pas la politique de remise de ces fichiers.
- Quelles protections d'accès au fichier SQLite et quelles procédures de restauration rendent impossible ou traçable une modification directe d'un exercice clos dans l'installation distribuée ? Les tests SQL établissent ce que permet la base, sans établir qu'une telle modification soit accessible par une commande métier ordinaire.
- Les comptes mixtes 44/45/46/48 doivent-ils être décrits par un type neutre ou par leur solde dans les usages futurs ? Leur valeur actuelle `passif` est mesurée ; aucune perte de montant n'est déduite de cette métadonnée seule.
- Quel encodage accompagne les FEC externes lorsque les mêmes octets ont plusieurs décodages possibles ? Le contenu seul ne permet pas toujours un choix certain.

## Tableau récapitulatif numéroté

| N° | Constat | Effet mesuré | Gravité |
|---|---|---|---|
| G-01 | Équilibre contrôlé avant arrondi des lignes | 0,01 € de déséquilibre enregistré | majeur |
| G-02 | Lignes courtes perdues au rejeu | 800 € de recettes non repris, succès web | critique |
| G-03 | Journaux fusionnés dans le validateur | Deux écarts de 800 € approuvés ; faux trous | majeur |
| G-04 | Numéros alphanumériques refusés | FEC de 1 600 € non migrable | majeur |
| G-05 | Variantes normées rejetées | Barre verticale : zéro écriture au lieu d'une | majeur |
| G-06 | Montants non finis/non numériques approuvés | Verdict positif sans équilibre calculable | majeur |
| G-07 | Calendrier et préfixe PCG insuffisamment contrôlés | 30 février et compte 4AB approuvés | majeur |
| G-08 | Métadonnées et dates source perdues au rejeu | Huit champs de la ligne altérés/effacés | majeur |
| G-09 | Chronologie de validation inversée à l'export | FEC de 1 600 € approuvé malgré ordre inversé | majeur |
| G-10 | Export silencieux d'une base incomplètement liée | 800 € en base, zéro ligne exportée | majeur |
| G-11 | Prix NaN accepté lors d'une cession | Actif de 12 000 € sorti sans prix valide | critique |
| G-12 | Ajustement de ventilation sur le terrain fixé | 13 € retirés du potentiel amortissable | majeur |
| G-13 | ISO-8859-15 décodé en CP1252 | `€` devient `¤`, montants inchangés | mineur |
| G-14 | Code retour zéro sur FEC bloquant | Erreur de 1 € non bloquante pour le shell | majeur |
| G-15 | Exceptions de typage des tiers oubliées | 409/419/425 mal typés, montants conservés | mineur |

**État du suivi :** les quinze constats ont été corrigés en production le 15 septembre 2026 (version 8.42.0). Les résultats et empreintes de `preuves_g/` sont conservés **tels qu'observés avant correction** : ils restent la référence du défaut, pas de l'état actuel du code. La non-régression est figée par `tests/test_passe_g.py` (65 tests), dont 50 échouent si l'on retire les correctifs.

Deux points de méthode, pour qui relancerait `preuves_g/reproduire.py` : trois de ses fonctions s'interrompent désormais sur une `ValueError` — lignes courtes au rejeu, lignes courtes à la balance, export d'une écriture sans ligne. Ce ne sont pas des défauts du dispositif, ce sont les refus attendus. Et le script appelait ces fonctions hors de tout `try`, faute de prévoir qu'elles puissent échouer.
