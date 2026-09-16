# Passe I — Article 39 C : plafond, mémoire et ventilation par bien

Audit du 15 septembre 2026 — source examinée : `compta_lmnp/`.

**Onze constats reproduits : deux critiques, huit majeurs, un mineur.** Les écarts touchent la qualification fiscale de comptes importés, l'affectation du report, la reprise des historiques et son rendu. Le moteur élémentaire conserve correctement les stocks sur les entrées valides testées ; cela ne garantit pas que ses entrées ni leur ventilation soient justes.

## Pièces, méthode et portée

Les fichiers demandés sont présents. L'examen inclut aussi les modules effectivement nécessaires : `controles.py`, `rejeu_fec.py`, `cession.py`, `migrations.py`, `liasse_pdf.py`, `perennite.py` et le gestionnaire de clôture d'`app.py`. Les chemins et lignes cités ci-dessous sont relatifs à la racine source indiquée ci-dessus ; les fonctions existent dans cette copie.

Lecture des invariants, du CHANGELOG, des récapitulatifs disponibles des passes G, H et Q et du mécanisme du test de calage. Les rapports antérieurs absents de l'arbre de travail n'ont pas été reconstitués. Le test de calage sur trois exercices réels n'a **pas été exécuté** : ses fichiers comptables privés n'ont pas été ouverts. Aucune de leurs valeurs n'est reprise ici. Les scénarios utilisent des identités fictives et des bases temporaires blanches.

**Preuves :** [script reproducteur](preuves_i/reproduire.py), [sorties intégrales](preuves_i/resultats.json), [vérificateur des sorties](preuves_i/verifier.py). Les sorties proviennent de **38 groupes d'exécution**, dont une matrice de **216 cas du moteur**. Le vérificateur a réussi **65 vérifications** portant sur ces résultats et les empreintes des sources. Ce ne sont pas 65 lectures de code présentées comme des tests fonctionnels.

Depuis la racine du dépôt :

```bash
compta_lmnp/.venv/bin/python docs/preuves_i/reproduire.py
compta_lmnp/.venv/bin/python docs/preuves_i/verifier.py
```

Le script exige `pdftotext` pour extraire les PDF réellement générés. Il recrée uniquement ses bases temporaires et ses preuves. Il ne modifie pas le logiciel. Python 3.14.6 et SQLite 3.51.2 ont été utilisés ; les empreintes des huit principaux fichiers examinés figurent dans le JSON.

Les scénarios de comptes externes créent un FEC fictif, l'exportent, le rejouent dans une **autre base**, puis clôturent avec `generer_dotation=False`, puisque la dotation est déjà importée. Les composants fictifs sont fournis séparément : le FEC ne décrit pas à lui seul un plan par composants. Les fixtures historiques insèrent explicitement les anciens suivis en SQL ; elles éprouvent l'acceptation d'un historique incomplet, sans prétendre établir comment chaque dossier réel aurait atteint cet état.

### Référentiel et diagnostics amendés

- La limitation porte sur les loyers et les charges afférentes au bien ; les frais purement liés à la structure en sont exclus. Pour plusieurs biens, le calcul du plafond est global, mais l'affectation du report doit viser les biens dont la dotation dépasse leur marge locative. Le scénario I-05 choisit un seul bien éligible à cette affectation, sans extrapoler une formule pour les marges nulles ou négatives. [BOFiP, II, § 40 à 100](https://bofip.impots.gouv.fr/bofip/4527-PGP.html/identifiant=BOI-BIC-AMT-20-40-10-20-20170301).
- Le report prévu par l'article 39 C est distinct du déficit LMNP. Le texte organise également le devenir de l'amortissement différé lors de la cessation de location et de la cession : on ne peut pas résumer toutes ces situations par une perte fiscale définitive. Les constats de sortie ci-dessous mesurent les montants retirés **du suivi logiciel**, notamment au détriment d'un bien conservé. [CGI, article 39 C, II-2 et II-3](https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000029355753).
- La case 318 du 2033-B 2026 couvre aussi les autres amortissements non déductibles ; sa mention de l'article 39-4 ne transforme pas le report 39 C en mécanisme de l'article 39-4. Le 2033-C porte sur les immobilisations et amortissements : le tableau de stock 39 C du PDF est un suivi complémentaire. [Formulaire officiel 2033-SD 2026, pages 2 et 3](https://www.impots.gouv.fr/sites/default/files/formulaires/2033-sd/2026/2033-sd_5394.pdf).

**Confrontation au calage antérieur :** aucune proposition ne supprime la majoration du plafond par un retraitement manuel légitime de charge afférente au bien. Deux exécutions fictives, ALUR automatique ou ALUR manuel avec automatique désactivé, donnent le même résultat. Les cas nouveaux concernent des numéros de comptes externes, plusieurs biens ou le moment où l'avertissement peut agir. Ils ne contredisent pas les chiffres du calage mono-bien et ne prétendent pas le remplacer.

## I-01 — Une dotation importée en 6811200 devient un déficit ordinaire

**Gravité : critique.**

**Localisation :** `modules/fiscal.py`, `agregats`, ligne 60, puis `_calcul_fiscal`, ligne 363. La dotation est reconnue par égalité avec `681120` ; les autres comptes de classe 6 alimentent les charges hors dotation.

**Scénario :** exercice 2026, composant fictif de 20 000 € sur dix ans, loyers de 1 000 €, dotation de 2 000 € portée au débit de `6811200` et au crédit de `281840`. Export puis rejeu du FEC et clôture sans régénération de dotation. Preuve : `comptes_dotation7`.

**Attendu :** dotation reconnue de 2 000 €, plafond de 1 000 €, report 39 C de 1 000 €, résultat fiscal nul et aucun déficit créé par cet amortissement.

**Produit, extrait d'exécution :**

```text
rejeu : ecritures=3, comptes_crees=['6811200'], renumerotees=False
agregats : dotation=0, charges_hors_daa=2000, plafond_39c=-1000
cloture : report_annee=0, stock_cloture=0
resultat_fiscal=-1000 ; deficit_cree=1000
controles=[] ; les cinq contrôles de liasse valent ok=True
```

**Conséquence :** **1 000 € d'amortissement différé sont enregistrés dans la mauvaise catégorie**, avec les règles d'imputation et de péremption du déficit. La case 254 affiche pourtant bien les 2 000 € : la correction antérieure de visibilité des comptes de charges ne corrige pas cette qualification fiscale. Ce constat ne reprend donc pas l'ancien défaut de ligne omise.

## I-02 — Les honoraires comptables à sept chiffres abaissent indûment le plafond

**Gravité : majeur.**

**Localisation :** `modules/fiscal.py`, `comptes_hors_plafond_39c`, ligne 36, et `agregats`, ligne 60.

**Scénario :** même bien, loyers de 1 000 €, dotation native de 2 000 €, frais de tenue comptable de 500 €. Deux FEC fictifs ne diffèrent que par le compte de ces frais : `622610` ou `6226100`. Preuves : `comptes_normal`, `comptes_charges7` et `liste_exclusions`.

**Attendu :** pour ces frais de même nature, plafond de 1 000 €, report de 1 000 €, déficit de 500 €. L'exclusion des frais comptables résulte du § 70 du référentiel BOFiP cité plus haut.

**Produit :**

| Compte exécuté | Charges hors plafond | Plafond | Report 39 C | Déficit créé |
|---|---:|---:|---:|---:|
| 622610 | 500 € | 1 000 € | 1 000 € | 500 € |
| 6226100 | 0 € | 500 € | 1 500 € | aucun |

Le second cas ne produit aucune anomalie dans `controler` et tous les contrôles de liasse passent.

**Conséquence :** **500 € passent du déficit au report 39 C** ; leur disponibilité ultérieure change. La table est extensible : l'ajout SQL du compte exact `6226100` rétablit l'exclusion dans l'essai dédié. Elle ne reconnaît cependant pas automatiquement cette subdivision importée. Il ne s'agit pas d'exclure indistinctement tous les honoraires : le scénario désigne précisément des frais de tenue comptable.

## I-03 — Les comptes de cession à sept chiffres échappent aux deux neutralisations

**Gravité : critique.**

**Localisation :** `modules/fiscal.py`, `agregats`, ligne 60, et `_calcul_fiscal`, ligne 363.

**Scénario :** FEC fictif 2026 : loyers 1 000 €, dotation 2 000 €, produit de cession 15 000 €, valeur comptable sortie 10 000 €. Deux rejeux comparent `775000`/`675000` à `7750000`/`6750000`. La nature des flux et tous les montants sont identiques. Il s'agit ici des écritures importées ; ce test n'appelle pas `ceder_bien` et n'attribue pas une date de sortie au référentiel. Preuves : `comptes_cession6`, `comptes_cession7`.

**Attendu :** même résultat que pour les comptes natifs : produit de cession exclu du plafond, charge de sortie exclue des charges afférentes, neutralisation fiscale des flux de cession selon le traitement LMNP du logiciel.

**Produit :**

| Sortie réelle | Six chiffres | Sept chiffres |
|---|---:|---:|
| Produit de cession reconnu | 15 000 € | 0 € |
| VNC de cession reconnue | 10 000 € | 0 € |
| Plafond 39 C | 1 000 € | 6 000 € |
| Report 39 C | 1 000 € | 0 € |
| Revenu imposable LMNP | 0 € | 4 000 € |

Dans le second cas, `controles=[]` et les cinq contrôles de liasse passent.

**Conséquence :** **4 000 € supplémentaires sont proposés comme revenu imposable LMNP**, et 1 000 € de report ne sont pas constitués. Ce montant n'est pas une estimation d'impôt personnel. Le correctif de liasse de cession en comptes natifs tient ; son absence d'effet sur ces comptes importés est le nouveau périmètre du constat.

## I-04 — Un produit financier est assimilé à un loyer pour le plafond

**Gravité : majeur.**

**Localisation :** `modules/fiscal.py`, `agregats`, ligne 60 : produits de classe 7 diminués des seules cessions reconnues.

**Scénario :** exercice 2026, loyers 1 000 €, produit financier fictif de 1 000 € en `768000`, dotation 2 000 €, aucune autre charge. Export, rejeu, clôture. Preuve : `comptes_produit_financier`.

**Attendu :** le produit financier distinct du loyer ne doit pas augmenter la capacité d'amortissement locative ; plafond de 1 000 € et report de 1 000 €. Ce critère découle de la définition des loyers acquis dans l'article 39 C et le § 50 du BOFiP cités plus haut.

**Produit :** `produits=2000`, `plafond_39c=2000`, `report_annee=0`, `stock_cloture=0`, `resultat_fiscal=0`. Aucune anomalie ; contrôles de liasse tous positifs.

**Conséquence :** **1 000 € d'amortissement supplémentaires sont absorbés immédiatement**, au lieu d'être mémorisés. Le traitement du produit financier dans la déclaration personnelle dépend de sa qualification fiscale ; ce constat établit l'erreur de base du plafond, sans chiffrer un impôt ni présumer cette qualification.

## I-05 — Le report est affecté à un bien qui n'en produit pas, puis sorti avec lui

**Gravité : majeur.**

**Localisation :** `modules/fiscal.py`, `_ventiler_39c_par_bien`, ligne 252, et `_repartir`, ligne 236. La clé exécutée est le poids des dotations de tous les biens.

**Scénario :** deux biens mis en service le 1er janvier 2026, sur dix ans : A de 10 000 €, loyers 2 000 € ; B de 30 000 €, loyers 1 000 €. Aucune autre charge. Variante : cession effective de A le 31 décembre pour 10 000 €, puis clôture. Preuves : `ventilation_bien_couvert_False`, `ventilation_bien_couvert_True`, `annee_apres_cession`.

**Attendu :** plafond **global** de 3 000 €, dotation totale de 4 000 €, report de 1 000 €. A couvre sa dotation de 1 000 € par ses loyers : le report doit être affecté à B, seul bien en insuffisance, conformément au § 100 du BOFiP. La cession de A ne doit donc pas emporter une part de ce report de B.

**Produit :**

```text
Sans cession : report A=250 ; report B=750 ; stock global=1000
Avec cession A : sortie A=250 ; stock B=750 ; stock global=750
Exercice suivant : ouverture B=750 ; dotation B=3000 ; clôture B=3750
```

**Conséquence :** **250 € de report du bien conservé sont retirés du suivi**, puis manquent à l'ouverture suivante. Les sommes locales et globales concordent : un simple contrôle de total ne détecterait pas cette mauvaise propriété du stock. L'alerte de fixture `VENTILATION_INCOMPLETE` concerne le prix ventilé, pas ce mouvement 39 C. Le calage mono-bien ne peut éprouver cette clé multi-biens.

## I-06 — Deux libellés de composants identiques font compter deux fois les dotations de cession

**Gravité : majeur.**

**Localisation :** `modules/fiscal.py`, `_ventiler_39c_par_bien`, ligne 252, requête sur les libellés à partir de la ligne 300 ; `modules/cession.py`, `ceder_bien`, ligne 95.

**Scénario :** A, B et C ont un composant de 10 000 €, 20 000 € et 30 000 €, chacun sur dix ans depuis le 1er janvier 2026. Aucun loyer. A et B sont cédés le 31 décembre, respectivement pour 10 000 € et 20 000 €. Refaire exactement le scénario en donnant aux trois composants le même libellé fictif, `Mobilier fictif`. Preuves : `cessions_libelles_identiques_False` et `_True`.

**Attendu :** changer seulement un libellé ne doit pas changer les montants attribués. Les dotations de cession réelles sont 1 000 € et 2 000 € ; celle de C est 3 000 €. Le rapprochement doit identifier le bien, pas une chaîne descriptive non unique.

**Produit :**

| Résultat exécuté | Libellés distincts | Libellés identiques |
|---|---:|---:|
| Dotations réellement passées à la cession | 1 000 € / 2 000 € | 1 000 € / 2 000 € |
| Dotations retenues dans le suivi A / B / C | 1 000 / 2 000 / 3 000 € | 3 000 / 3 000 / 3 000 € |
| Somme des dotations par bien | 6 000 € | 9 000 € |
| Sorties de stock | 3 000 € | 4 000 € |
| Stock conservé pour C | 3 000 € | 2 000 € |

**Conséquence :** **1 000 € de stock supplémentaire disparaissent** uniquement à cause des libellés. Le correctif v8.38.0 tient pour les libellés distincts ; le rattachement restant par nom reproduit le problème sur une collision de noms. Ce n'est pas l'affirmation que l'ancien correctif n'existe pas. Aucun contrôle 39 C ne rapproche ici les 9 000 € locaux des 6 000 € globaux.

## I-07 — La migration ne reconstitue pas le suivi ; le repli peut attribuer une dotation à un bien déjà cédé

**Gravité : majeur.**

**Localisation :** `modules/migrations.py`, `_palier_2`, ligne 28, et `migrer`, ligne 100 ; `modules/fiscal.py`, `_ventiler_39c_par_bien`, ligne 252, replis vers le premier identifiant de bien.

**Scénario :** base fictive avec deux biens, exercice 2025 clos et stock global de 5 000 €, sans ventilation historique. Supprimer la table locale et marquer le schéma au palier 1, puis exécuter la migration réelle. Pour 2026, A est déclaré cédé au 31 décembre 2025 ; seul B porte un composant actif de 10 000 € sur dix ans et une dotation comptabilisée de 1 000 €, sans ligne de plan générée. Clôturer avec `generer_dotation=False`. Preuve : `migration_stock_historique`.

**Attendu :** conserver le stock global historique, rendre son affectation manquante visible et demander une ventilation avant d'en sortir une part. La nouvelle dotation de B ne doit pas être attribuée à A, déjà sorti. La propriété des 5 000 € anciens n'est pas déductible de la fixture.

**Produit :**

```text
migration : avant=1, apres=7
après migration : global 2025=5000 ; biens=[]
clôture 2026 : A ouverture=5000, dotation=1000, report=1000, sortie=6000
               B ouverture=0, dotation=0, report=0, clôture=0
stock global 2026=0
```

**Conséquence :** **6 000 € sont sortis sur une affectation arbitraire**, dont **1 000 € de report courant appartenant au seul bien actif**. La part erronée du stock historique de 5 000 € ne peut pas être chiffrée sans sa ventilation. Les alertes exécutées sont `AN_ABSENTS` et `VENTILATION_INCOMPLETE`, aucune n'annonce ce repli d'affectation ; les cinq contrôles de liasse restent positifs. Ce test ne prétend pas qu'une migration normale crée rétroactivement une cession : la date est une donnée explicite de la fixture ancienne.

## I-08 — Les stocks global et locaux peuvent être repris de deux années différentes

**Gravité : majeur.**

**Localisation :** `modules/fiscal.py`, `_stock_39c_ouverture`, ligne 134, et `_ventiler_39c_par_bien`, ligne 252 ; `modules/liasse.py`, `generer`, ligne 588, pour le résultat des contrôles de cohérence.

**Scénario :** historique fictif incomplet : 2024 clos, stock global de 2 000 €, ventilé A=1 000 € et B=1 000 € ; 2025 clos, stock global de 5 000 € mais aucune ligne par bien. En 2026, loyers de 1 000 €, aucune dotation. Clôture sans génération. Preuve : `historique_partiel_par_bien`.

**Attendu :** ouverture globale de 5 000 € ; absence de détail 2025 signalée et réconciliation requise avant de présenter une ventilation comme complète. Après utilisation de 1 000 €, les parts validées doivent totaliser 4 000 €.

**Produit :**

```text
Global : ouverture=5000 ; utilisation=1000 ; clôture=4000
Somme par bien : ouverture=2000 ; utilisation=1000 ; clôture=1000
Contrôles : ['AN_ABSENTS'] ; cinq contrôles de liasse ok=True
```

**Conséquence :** **3 000 € du stock disponible n'ont pas de propriétaire dans le suivi affiché**, sans alerte portant sur cet écart. Le global n'a pas disparu dans cette exécution ; il serait faux d'annoncer une perte immédiate de 3 000 €. Contrairement à I-07, le détail existe mais provient d'un millésime plus ancien, ce qui empêche le repli prévu pour une liste entièrement vide.

## I-09 — L'ajustement du dernier centime produit une utilisation négative

**Gravité : mineur.**

**Localisation :** `modules/fiscal.py`, `_repartir`, ligne 236, et `_ventiler_39c_par_bien`, ligne 252.

**Scénario :** quatre biens avec chacun un composant de 10 € amorti sur dix ans depuis le 1er janvier 2026 ; total des loyers de 3,98 €. Clôturer. Preuve : `repartition_centimes` ; l'appel isolé avec total 0,02 et quatre poids égaux est aussi conservé dans `repartition_limites`.

**Attendu :** dotation de 4 €, report de 0,02 €, somme des stocks de 0,02 €, aucune utilisation en l'absence de stock d'ouverture et aucune part négative.

**Produit :**

```text
reports par bien = [0.01, 0.01, 0.01, -0.01]
utilisations par bien = [0, 0, 0, -0.01]
stocks de clôture par bien = [0.01, 0.01, 0.01, 0]
stock global=0.02 ; somme des stocks locaux=0.03
```

**Conséquence :** **un centime de stock local en excès** et un mouvement de reprise négatif sont enregistrés. La répartition brute conserve bien son total, mais le plafonnement ultérieur de l'utilisation casse cet invariant. Les avertissements sur les prix ventilés et les contrôles de liasse exécutés ne signalent pas cet écart.

## I-10 — Le retraitement manuel du report est accepté avant que son avertissement puisse agir

**Gravité : majeur.**

**Localisation :** `modules/controles.py`, `c_retraitement_manuel_majore_le_plafond`, ligne 254 ; `app.py`, `cloturer`, ligne 1219 ; `modules/fiscal.py`, `_calcul_fiscal`, ligne 363.

**Scénario :** bien de 12 000 € sur dix ans, loyers de 200 €, aucune autre charge. Le report à calculer est de 1 000 €. L'utilisateur saisit aussi `1000` dans le champ de retraitements manuels de clôture. Le script exécute le gestionnaire Flask dans un vrai contexte POST avec cette valeur ; seules la base temporaire et l'absence d'archivage du mode jetable sont substituées. Preuves : `report_saisi_manuellement_0`, `_1000`, `web_retraitement_manuel`.

**Attendu :** l'avertissement sur l'effet de la saisie manuelle doit pouvoir examiner la valeur en cours de soumission **avant** de figer l'exercice. Pour ce scénario où la somme saisie représente le report lui-même, le traitement normal produit un stock de 1 000 €.

**Produit :**

```text
Sans saisie manuelle : plafond=200 ; report=1000 ; stock=1000 ; RF=0
Avec saisie manuelle : plafond=1200 ; report=0 ; stock=0 ; RF=0
contrôles avant clôture=[]
gestionnaire Flask : HTTP 302, paramètre ok='Exercice 2026 clôturé…'
statut en base=clos
contrôles après clôture=['RETRAITEMENT_MANUEL_PLAFOND']
```

**Conséquence :** **1 000 € de report ne sont pas mémorisés**, alors que le résultat fiscal immédiat reste nul. L'hypothèse initiale d'une double réintégration immédiate est donc amendée : c'est ici une disparition du report, pas un RF de 1 000 €. Le garde-fou existe, mais ne lit que les retraitements déjà sauvegardés dans `cloture_fiscale`. Ce constat porte sur son moment d'action, pas sur l'interdiction des retraitements manuels légitimes déjà refusée lors du calage.

## I-11 — Pour un bien unique, le PDF n'explique pas la sortie du stock 39 C

**Gravité : majeur.**

**Localisation :** `modules/liasse.py`, `suivi_reports`, ligne 376 ; `modules/liasse_pdf.py`, `generer_pdf`, ligne 146, tableau global aux lignes 360–366 et condition du tableau par bien ligne 372.

**Scénario :** un seul bien, stock d'ouverture de 5 000 €, composant de 12 000 € sur dix ans, aucun loyer, cession effective le 31 décembre 2026 pour 12 000 €. Clôturer puis générer le PDF. Preuve : `pdf_cession_un_bien`, [PDF produit](preuves_i/cession_un_bien.pdf), [texte extrait](preuves_i/cession_un_bien.txt). La page 2 a également été rendue en image et examinée.

**Attendu :** afficher le mouvement de sortie de 6 200 € qui explique `5 000 + 1 200 − 0 − 6 200 = 0`.

**Produit :** la clôture retourne `sorties_39c=6200`, mais le tableau imprimé contient seulement :

```text
Stock d'ouverture                         5 000,00 €
Amortissements reportés cette année        1 200,00 €
Amortissements repris cette année              0,00 €
Stock à la clôture                             0,00 €
```

Aucune ligne de sortie, aucun montant de 6 200 € dans le texte du PDF. Le détail par bien est omis lorsque la liste n'a qu'un élément. La variante à deux biens imprime effectivement une colonne de sortie : elle n'est pas déclarée absente partout.

**Conséquence :** **6 200 € de mouvement ne sont pas expliqués dans l'état archivable**, dont le tableau ne se réconcilie pas visuellement. Il ne s'agit pas d'une nouvelle perte en base ni du défaut d'écran déjà corrigé en v8.23.0. La sortie est calculée et disponible ; son rendu est incomplet dans le cas mono-bien.

## Ce qui a été vérifié et tenu

| Vérification exécutée | Résultat observé |
|---|---|
| Moteur `calculer_39c`, 216 combinaisons de stocks, dotations et plafonds finis, stocks/dotations non négatifs | Aucun échec des invariants testés : conservation `ouverture + report − utilisation`, stock non négatif, report compris entre zéro et la dotation. |
| Plafond nul ou négatif | Avec ouverture 5 000 €, dotation 1 200 €, plafond −300 € : report 1 200 €, utilisation zéro, stock 6 200 €. Le plafond négatif n'entraîne pas de reprise négative dans le moteur global. |
| Stock présent sans dotation | Ouverture 5 000 €, dotation zéro, plafond 1 500 € : utilisation 1 500 €, stock 3 500 €. Avec plafond zéro, le stock reste 5 000 €. |
| Dotation courante et utilisation ancienne | Ouverture 5 000 €, dotation 1 200 €, plafond 1 500 € : utilisation 300 €, stock 4 700 €. |
| Absence d'exercice N−1 | Le dernier stock clos de 2024 est retrouvé pour 2026, même sans exercice 2025 ; ouverture 5 000 €, utilisation 1 500 €, clôture 3 500 €. La correction de recherche historique tient. |
| Exercice antérieur ouvert | La lecture isolée peut lire sa ligne de suivi, mais la clôture 2026 refuse effectivement de passer avant la clôture de 2024. Aucun suivi 2026 n'est créé. |
| Report sans péremption | En 2040, un stock 39 C de 2020 de 5 000 € reste utilisable : reprise 1 500 €, reste 3 500 €. Dans la même base, le déficit fictif de 5 000 € expiré en 2030 est soldé. Le compteur `perimes` vaut **1** : c'est un nombre de lignes, pas un montant. |
| Restauration complète | Après clôture 2026, stock 3 500 €. Restauration de la sauvegarde antérieure : exercice ouvert, zéro suivi 2026, ouverture historique retrouvée de 5 000 €, sauvegarde de sécurité créée. La mémoire revient avec l'ensemble du dossier restauré. |
| Exclusions vidées | Effacer la liste ne la laisse pas vide si les comptes natifs de défaut existent : ils sont réinsérés au prochain accès. Dans le référentiel minimal sans ces comptes, la liste est réellement vide ; loyers 1 000 € et maintenance 200 € donnent correctement un plafond de 800 €. Une liste vide n'est donc pas, à elle seule, un calcul faux. |
| Configuration de l'exclusion | Ajouter le compte exact à la table SQL modifie le plafond dans l'essai. Cette extensibilité a été exécutée ; aucune interface de configuration n'est présumée. |
| Neutralisation native de cession | Le produit de 15 000 € est soustrait une seule fois de la base des produits ; sa VNC de 10 000 € est exclue des charges afférentes. Le plafond reste 1 000 €. Les deux neutralisations n'ont pas le même objet. |
| ALUR automatique ou manuel légitime | Loyers 1 200 €, ALUR 200 €, dotation 1 200 € : automatique actif sans saisie manuelle, ou automatique désactivé et manuel de 200 €, donnent le même plafond effectif de 1 200 €, RF nul et report nul. `retraitement_automatique` ne contient pas le report 39 C lui-même. |
| Acquisition en juillet, absence de loyer, autre bien à marge négative | Dotations 604,93 € et 1 200 € ; loyers 500 €, charges 800 € : report 1 804,93 €, déficit 300 €, sommes locales/globales concordantes. Ce test établit la conservation, pas une doctrine générale de répartition des marges négatives. |
| Cession au 30 juin et exercice suivant | Avec ouverture A=1 000 €, B=3 000 €, dotation de cession A=595,07 € et dotation B=1 200 €, sortie calculée A=1 595,07 €, stock conservé B=4 200 €. L'année suivante reprend 4 200 €, ajoute 1 200 €, sans ressortir le stock de A. |
| Réintégration imprimée | Dans `reintegration.pdf`, 1 000 € sont imprimés en case 318 comme réintégration. |
| Utilisation imprimée | Dans `utilisation.pdf`, le stock antérieur de 1 000 € est utilisé en 2027 et imprimé en déduction case 350 ; le RF vaut 800 € pour 3 000 € de loyers et 1 200 € de dotation. Le stock final est nul. |
| Lectures et transaction | Pour `_table_39c_bien`, `suivi_39c_par_bien`, `comptes_hors_plafond_39c`, `_stock_39c_ouverture` et `parametres.valeur` : transaction ouverte, insertion d'un témoin, appel, rollback, comptage ; **zéro commit instrumenté, zéro témoin restant**, transaction encore ouverte avant rollback. |

Les chemins de liasse testés ne présentent pas d'omission générale des cases 318 et 350. Leur emplacement et leur sens correspondent aux rubriques de réintégration et déduction du [2033-B officiel 2026](https://www.impots.gouv.fr/sites/default/files/formulaires/2033-sd/2026/2033-sd_5394.pdf). Cela ne vaut pas validation d'un dépôt EDI.

Les défauts de génération d'amortissement déjà établis en passe H et ceux de transaction déjà établis en passe Q ne sont pas renumérotés dans cette passe. Les alertes réellement observées sont conservées dans le JSON, y compris lorsqu'elles portent sur une autre propriété de la fixture : « aucun contrôle 39 C sur l'écart » ne signifie pas « aucune alerte quelconque ».

## Non vérifiable avec les pièces fournies

- Le test de calage sur les trois exercices réels peut-il être relancé localement par leur détenteur, sans publier ses entrées ni ses sorties, pour compléter les exécutions fictives de cette passe ?
- Quelle ventilation historique documentée attribue les stocks globaux anciens aux biens, lorsque le dossier migré ne contient aucune ligne correspondante ?
- Pour les historiques locaux incomplets, quelle procédure métier les a constitués, et quelle réconciliation doit précéder leur réutilisation ? Le scénario I-08 éprouve leur acceptation, mais ne démontre pas qu'une clôture normale actuelle crée spontanément cet état.
- Quelle règle validée doit couvrir la répartition du § 100 lorsque plusieurs biens éligibles ont des marges nulles ou négatives ? La conservation arithmétique testée ne suffit pas à trancher cette application fiscale.
- Quel traitement applicable au bien concerné articule la sortie logicielle du report, l'article 39 C II-3 et le régime de plus-value immobilière des particuliers ? Quelles pièces permettent de vérifier son traitement chez le déclarant plutôt que de qualifier toute sortie de perte fiscale définitive ? [Article 39 C](https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000029355753).
- Quelle qualification fiscale exacte s'applique au produit financier de I-04 dans le dossier déclaré, indépendamment de son exclusion de la base des loyers ?
- Quel contrat d'entrée garantit les valeurs finies et non négatives du moteur isolé, et quel chemin utilisateur pourrait atteindre les comportements hors contrat conservés dans `moteur_limites`, sans refus en amont ?
- Quelle preuve de réception ou de validation EDI permet de certifier l'acceptation administrative du fichier effectivement remis ? Les PDF et les textes officiels ont été examinés, aucun dépôt administratif n'a été effectué.

## Tableau récapitulatif numéroté

Les euros ci-dessous mesurent un résultat fiscal, un stock ou un mouvement ; ils ne sont pas un calcul de l'impôt du foyer.

| N° | Constat | Conséquence reproduite | Gravité |
|---|---|---|---|
| I-01 | Dotation 6811200 traitée comme charge ordinaire | 1 000 € de déficit au lieu de report 39 C | critique |
| I-02 | Honoraires 6226100 non exclus | 500 € transférés du déficit au report | majeur |
| I-03 | Cession 6750000/7750000 non neutralisée | 4 000 € de revenu imposable supplémentaire ; report de 1 000 € absent | critique |
| I-04 | Produit financier intégré au plafond | 1 000 € d'amortissement absorbés au lieu d'être reportés | majeur |
| I-05 | Report affecté à un bien couvert par ses loyers | 250 € du bien conservé sortis lors d'une autre cession | majeur |
| I-06 | Collision de libellés de composants cédés | 1 000 € supplémentaires retirés du stock conservé | majeur |
| I-07 | Migration sans détail et repli vers un bien cédé | 6 000 € sortis arbitrairement, dont 1 000 € courants mal affectés | majeur |
| I-08 | Historiques global/local de millésimes différents | 3 000 € d'écart de ventilation non signalé | majeur |
| I-09 | Dernière part négative après arrondi | 0,01 € de stock local en excès | mineur |
| I-10 | Avertissement manuel disponible après clôture seulement | 1 000 € de report non mémorisés | majeur |
| I-11 | Sortie omise du PDF mono-bien | 6 200 € de mouvement inexpliqué dans le tableau | majeur |
