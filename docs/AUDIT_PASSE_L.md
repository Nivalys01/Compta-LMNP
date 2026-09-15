# Passe L — Cession : écritures, neutralisation et liasse

Audit du 15 septembre 2026. **Quatre constats reproduits : trois majeurs, un mineur.** Les corrections de neutralisation fiscale, de ligne 352 et de charge de cession gratuite tiennent sur les scénarios exécutés.

## Périmètre et preuves

Source examinée : `compta_lmnp_v8.41.0/compta_lmnp/`. Les chemins et numéros de ligne ci-dessous sont relatifs à cette racine. Les quatre modules demandés et `schema.sql` sont présents. Les colonnes de sortie ne figurent pas dans ce schéma initial ; elles sont ajoutées par le logiciel. Les modules complémentaires utilisés, notamment `liasse_pdf.py`, `pense_bete.py`, `rejeu_fec.py` et `init_db.py`, existent également.

Lecture préalable des récapitulatifs du CHANGELOG, notamment v8.35.0 et v8.38.0, et des rapports disponibles G à K et Q pour les sujets concernés. Les anciennes passes C, E et F ne sont pas disponibles comme rapports complets dans l'arbre courant : leurs corrections ne sont pas reconstituées au-delà du CHANGELOG. Les données privées, les FEC de référence et le fichier d'identité ne sont pas utilisés. Toutes les fixtures sont fictives et créées dans des bases temporaires vierges. Aucun code applicatif n'a été modifié.

Preuves : [reproducteur](preuves_l/reproduire.py), [résultats complets](preuves_l/resultats.json), [vérificateur](preuves_l/verifier.py), [PDF du cycle](preuves_l/cycle.pdf), [texte extrait de ce PDF](preuves_l/cycle.txt). **32 groupes de résultats ; 120 vérifications réussies**, incluant les empreintes des sources. Les vérifications portent sur des sorties d'appels réels, des écritures en base et des PDF effectivement générés.

Depuis la racine du dépôt :

```bash
compta_lmnp_v8.41.0/compta_lmnp/.venv/bin/python docs/preuves_l/reproduire.py
compta_lmnp_v8.41.0/compta_lmnp/.venv/bin/python docs/preuves_l/verifier.py
```

Le reproducteur nécessite `pdftotext`. Les tests existants de cession utilisant des fichiers privés n'ont pas été lancés.

### Référentiel et limite juridique

La cession immobilière du LMNP relève du régime des particuliers ; la différence comptable prix–VNC ne constitue donc pas, à elle seule, la plus-value immobilière imposable. La moins-value comptable doit elle aussi sortir du résultat BIC dans ce périmètre. Le régime immobilier prévoit en principe la non-prise en compte des moins-values, avec une exception pour certaines acquisitions par fractions : cela ne rend pas la perte comptable déductible des loyers. Sources : [CGI, article 150 U](https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000053544910/2026-05-05), [BOFiP, location meublée, régime fiscal](https://bofip.impots.gouv.fr/bofip/3610-PGP.html/identifiant=BOI-BIC-CHAMP-40-20-20220223), [BOFiP, détermination de la plus-value immobilière](https://bofip.impots.gouv.fr/bofip/292-PGP.html/identifiant=BOI-RFPI-PVI-20-20-20230718).

Le CERFA 2033-SD 2026 annoncé comme joint n'a pas été trouvé dans l'arbre courant, y compris parmi les fichiers ignorés. La confrontation a donc été faite avec le [formulaire officiel 2026, pages 2 et 3](https://www.impots.gouv.fr/sites/default/files/formulaires/2033-sd/2026/2033-sd_5394.pdf). Il comporte bien les cases 290 et 300, les mouvements de diminution des immobilisations et amortissements, et un cadre III de plus-values et moins-values. L'existence de ce dernier ne suffit pas à établir que la plus-value immobilière privée doit y être portée comme une plus-value professionnelle : cette qualification reste une question en fin de rapport.

## L-01 — La sortie reprend le cumul théorique au lieu du cumul comptabilisé

**Gravité : majeur.**

**Fichier et fonctions :** `modules/cession.py`, `_dotation_prorata`, ligne **55**, appel au plan à la ligne **75** ; `ceder_bien`, ligne **95**, construction de la sortie aux lignes **131–143**.

**Scénario reproductible :** premier exercice du dossier en 2026 ; un seul composant de construction de **12 000 €**, mis en service le 1er janvier 2025, durée actuelle dix ans. La reprise comptable porte **3 000 €** d'amortissements antérieurs en 281315. Cette écriture fictive est exportée en FEC puis réellement rejouée dans une autre base ; le référentiel des composants est fourni séparément. Céder le bien le 30 juin 2026 pour **15 000 €**. Preuves : `cumul_rejeu`, `cumul_repris_*`.

La discordance entre historique comptabilisé et plan courant est volontaire : elle représente un historique de cabinet ou un changement de paramètres à rapprocher, pas une justification fiscale des 3 000 €.

**Attendu :** refuser la sortie jusqu'à réconciliation, ou sortir le cumul comptable confirmé. Avec les 3 000 € repris et la dotation calculée de **595,07 €**, le cumul à solder vaut **3 595,07 €** ; la VNC vaut **8 404,93 €**. Après sortie complète, le compte d'amortissement doit être nul.

**Produit — sortie réelle :**

```text
Rejeu : ecritures=1 ; normalisees=0 ; comptes_crees=[]
Dotation complémentaire = 595.07
VNC sortie = 10204.93 ; plus-value comptable = 4795.07
Après clôture : brut au bilan = 0.00
Amortissements au bilan = 1800.00 ; actif net = -1800.00
Résultat comptable = 4200.00 ; conforme=False
```

**Conséquence :** **1 800 € de VNC en trop** dans la charge de cession, **1 800 € de résultat comptable en moins**, et **1 800 € d'amortissements résiduels sans actif**. La plus-value comptable attendue serait 6 595,07 €. La neutralisation fiscale compense ici l'écart de VNC : le scénario ne démontre pas une majoration de l'impôt BIC. Le contrôle de concordance signale le bilan incohérent après la sortie ; celle-ci et la clôture ont néanmoins été acceptées.

Ce constat concerne la détermination et le solde du cumul **à la sortie**, distincts du plafonnement de dotation annuelle déjà examiné en H-02. Le calcul de cession ne consulte pas la base pour rapprocher les amortissements : sa signature ne reçoit que les paramètres du plan.

## L-02 — Le 2033-C efface aussi l'ouverture et les mouvements du bien cédé

**Gravité : majeur.**

**Fichier et fonctions :** `modules/liasse.py`, `immobilisations_2033c`, ligne **309**, exclusion du bien aux lignes **322–332** ; `generer`, ligne **588**, contrôles limités aux soldes finaux. Rendu : `modules/liasse_pdf.py`, `generer_pdf`, ligne **146**, tableau à partir de la ligne **313**.

**Scénario reproductible :** acquérir un composant de construction de **12 000 €** le 1er janvier 2025, durée dix ans ; clôturer 2025 sans loyers, puis ouvrir 2026 avec les à-nouveaux. Céder le 30 juin 2026 pour **15 000 €**, clôturer et générer le PDF. Preuves : `cycle_avant`, `cycle_cession`, `cycle_2026`, `cycle.pdf`.

**Attendu :** en 2033-C, brut d'ouverture **12 000 €**, diminution **12 000 €**, brut final zéro ; amortissements d'ouverture **1 200 €**, dotation **595,07 €**, diminution **1 795,07 €**, amortissements finaux zéro. L'exclusion du solde final ne doit pas supprimer l'historique de l'exercice.

**Produit — calcul et extraction du PDF exécutés :**

```text
2033-C, totaux :
brut_debut=0 ; augmentations=0 ; brut_fin=0
amort_debut=0 ; dotation=0 ; amort_fin=0
detail_composants=[]
PDF : Totaux  0,00 €  0,00 €  0,00 €  0,00 €  0,00 €  0,00 €
Aucune colonne Diminutions dans le tableau produit.
conforme=True ; les cinq contrôles de liasse valent ok=True
```

**Conséquence :** **12 000 € de brut d'ouverture et de sortie**, **1 200 € de cumul d'ouverture** et **595,07 € de dotation** ne sont pas fournis au déclarant pour les mouvements du 2033-C. Les soldes finaux du bilan et du tableau sont bien nuls : le défaut est l'omission des flux et de l'ouverture, pas le maintien du bien au bilan déjà corrigé en v8.35.0. Le contrôle approuve parce qu'il ne rapproche que la fin d'exercice. Aucun effet BIC supplémentaire n'est chiffré.

## L-03 — Une vente antérieure à l'acquisition est acceptée et validée par la liasse

**Gravité : majeur.**

**Fichier et fonctions :** `modules/cession.py`, `ceder_bien`, ligne **95**, validation de la date aux lignes **106–110** ; `_dotation_prorata`, ligne **55**. La date est syntaxiquement contrôlée, sans rapprochement avec la date d'acquisition.

**Scénario reproductible :** bien acquis et composant mis en service le **1er juillet 2026**, valeur brute **12 000 €**, acquisition comptabilisée à cette date. Saisir la cession au **30 juin 2026**, pour **15 000 €**. Preuves : `avant_acquisition` et `avant_acquisition_etat`.

**Attendu :** refuser une cession antérieure à l'acquisition enregistrée, sans sortir le bien ni passer le prix. L'utilisateur doit corriger la date ou l'historique.

**Produit — sortie réelle :**

```text
Cession acceptée : dotation_complementaire=0
valeur_brute_sortie=12000 ; vnc_sortie=12000 ; prix_cession=15000
pv_comptable=3000
Deux écritures de cession datées du 2026-06-30, exercice 2026.
Bilan : brut=0 ; 2033-C : detail_composants=[]
conforme=True
```

**Conséquence :** **12 000 € d'actif sont sortis**, et **15 000 € de produit** sont enregistrés sur une chronologie impossible, sans demande de correction. Le bien devient cédé et cesse de produire des dotations. Le scénario ne permet pas de choisir à la place du déclarant la bonne date de vente ; aucun manque d'amortissement ni impôt définitif n'est donc inventé.

## L-04 — Le PDF ne rappelle pas la déclaration immobilière séparée

**Gravité : mineur.**

**Fichier et fonction :** `modules/liasse_pdf.py`, `generer_pdf`, ligne **146**. Contre-épreuve : `modules/pense_bete.py`, `rappels`, ligne **363**, rappel de cession à partir de la ligne **433**.

**Scénario reproductible :** bien de **12 000 €** mis en service le 1er janvier 2026, loyers **3 000 €**, vente le 30 juin pour **15 000 €** ; clôturer, générer le PDF et exécuter le pense-bête au 1er juillet. Preuves : `prix_15000`, `pdf`, `rappels`, [PDF](preuves_l/cession.pdf), [texte intégral](preuves_l/cession.txt).

**Attendu :** le document remis au déclarant précise que la neutralisation BIC ne calcule pas la plus-value immobilière imposable et renvoie au traitement séparé de la vente, notamment au notaire et à la 2048-IMM.

**Produit — extraction et appel réels :**

```text
PDF : présence de « notaire » = False ; présence de « 2048 » = False
PDF : Déduction — Produit de cession (régime des particuliers) : 3595.07
Pense-bête : un rappel de cession mentionne le notaire et la 2048-IMM.
```

**Conséquence :** le destinataire du seul PDF voit la vente neutralisée, sans indication précise du calcul et de la déclaration restant à traiter séparément. Le risque est une démarche omise, sans montant d'impôt quantifiable dans cet essai. **Diagnostic limité au PDF** : il serait faux de dire que le logiciel entier ne prévient pas, puisque le pense-bête le fait. La mention générale de validation par un expert-comptable figure bien au pied du PDF.

## Ce qui a été vérifié et tenu

### Neutralisation unique, symétrique et cession gratuite

`fiscal.agregats` (60), `_calcul_fiscal` (363), `cloturer` (471) et `liasse.resultat_2033b` (103) sont exécutés sur un bien de 12 000 €, mis en service le 1er janvier 2026, vendu le 30 juin, avec 3 000 € de loyers. Dotation : **595,07 €** ; VNC : **11 404,93 €**.

| Prix | Plus/moins-value comptable | Neutralisation VNC − prix | Résultat comptable 310 | Résultat fiscal ouvert / clos | Ligne 352 ouverte / close |
|---:|---:|---:|---:|---:|---:|
| 15 000 € | 3 595,07 € | −3 595,07 € | 6 000 € | 2 404,93 € / 2 404,93 € | 0 / 0 |
| 5 000 € | −6 404,93 € | +6 404,93 € | −4 000 € | 2 404,93 € / 2 404,93 € | 0 / 0 |
| 0 € | −11 404,93 € | +11 404,93 € | −9 000 € | 2 404,93 € / 2 404,93 € | 0 / 0 |

La moins-value n'est pas laissée en charge BIC déductible. Aucun double retraitement n'apparaît ; les trois résultats fiscaux sont exactement les loyers moins la dotation. Le prix nul ne provoque aucune division par zéro, conserve la charge 675000 et ne majore pas artificiellement le résultat comptable. L'ancien défaut de 5NA et celui de ligne 352 ne sont pas reproduits dans ces fixtures.

Le PDF du cycle affiche effectivement **15 000 € en 290**, **10 204,93 € en 300**, **4 200 € en 310**, puis une déduction de cession de **4 795,07 €**. Les cases 290/300 correspondent au CERFA consulté. L'écart comptable/fiscal est donc visible. Le libellé « Produit de cession » désigne toutefois ici la neutralisation **nette**, et non le prix brut : ne pas confondre les deux montants.

### Prorata, dates et exercices suivants

`cession._dotation_prorata` (55) applique l'annuité pleine à la période allant de la mise en service, ou du 1er janvier, jusqu'au **jour de vente inclus**, en jours réels sur base 365 :

- 12 000 € sur dix ans, du 1er janvier au 30 juin 2026 : **595,07 €**, soit 1 200 × 181/365.
- Mise en service le 1er juillet, vente le 30 septembre 2026 : **302,47 €**, soit 1 200 × 92/365 ; pas de double prorata.
- Vente le 1er janvier 2026 : **3,29 €** ; vente le 31 décembre : **1 200 €**. Toutes les écritures sont rattachées à 2026, pas à 2027.
- Dernière annuité : 12 000 € sur un an depuis le 1er juillet 2025, vente fin 2026 : cumul antérieur **6 049,32 €**, complément plafonné à **5 950,68 €** ; somme **12 000 €**.

Dans le cycle 2025–2027 exécuté, après la cession de 2026, `amortissement.dotations_exercice` (99) retourne **[]** en 2027. Après clôture 2027 : dotation zéro, aucun détail de composant, brut et amortissements au bilan nuls. Le tableau garde ses rubriques standard à zéro ; il n'affiche plus de ligne individuelle du bien.

Les écritures des trois scénarios de prix sont toutes équilibrées. Sur exercice clos, la cession est refusée et le nombre d'écritures reste **2 avant / 2 après**. Une panne volontaire sur la sortie, après la première dotation réellement insérée, donne **1 écriture avant, 2 avant rollback, 1 après rollback**. Cela confirme le rollback effectué par l'appelant ; cela ne prouve pas que `ceder_bien` annule elle-même tout son lot sur exception. Ce contrat était déjà documenté en Q.

### Absence de comptes de cession et suivi 39 C

Base vierge : `comptes=[]` pour 675000/775000, mais `fiscal.agregats` (60) retourne **produits_cession=0 et vnc_cession=0**, sans erreur. La recherche porte sur les lignes, avec agrégat et valeur de repli ; un compte absent ne fait pas échouer le calcul.

Dans le cycle sans loyers, le suivi 39 C mémorise en 2026 : ouverture **1 200 €**, report courant **595,07 €**, sortie du bien **1 795,07 €**, clôture zéro. La sortie existe dans le suivi global et par bien ; elle n'est pas une disparition inexpliquée en base. Son omission dans le PDF mono-bien et les problèmes d'affectation multi-biens sont déjà traités en passe I ; ils ne deviennent pas de nouveaux constats L. L'exécution ne qualifie pas cette sortie logicielle de perte fiscale définitive dans tous les cas.

### Limites exécutées et diagnostics non renumérotés

- **Cumul courant déjà doté — extension de H-02 :** appeler `amortissement.generer_cloture` (303), puis céder le 31 décembre, produit **2 400 €** de dotations au total et **1 200 €** d'amortissements résiduels pour un actif entièrement sorti. Le mot « complémentaire » ne garantit donc pas que les dotations déjà présentes sont déduites. Le phénomène de dotation courante non reconnue reste rattaché à H-02.
- **Sortie partielle :** l'API `cession.ceder_bien` (95) porte sur un bien entier ; l'absence de commande de cession d'un seul composant est déjà annoncée dans le CHANGELOG. Une fixture SQL explicite sort le composant de 12 000 € et conserve celui de 6 000 € : le bilan donne **6 000 € de brut et 600 € d'amortissements**, tandis que le 2033-C donne **18 000 € et 1 800 €**, `conforme=False`. `dotations_exercice` respecte la date du composant, `immobilisations_2033c` filtre seulement le bien. Il s'agit d'une limite mesurée sur un état fourni manuellement, pas d'un parcours utilisateur de cession partielle prétendument disponible. La cession ultérieure du reste en 2027 préserve bien la première date de sortie de 2026 : le correctif de non-réécriture tient.
- **Modification SQL après clôture :** augmenter le prix comptabilisé de 15 000 à 16 000 €, avec sa contrepartie, fait passer la déduction nette de **3 595,07 à 4 595,07 €**. La neutralisation est recalculée ; le résultat fiscal figé reste **2 404,93 €**, la ligne 352 zéro, et `conforme=True`. Le résultat comptable recalculé passe de 6 000 à 7 000 €. Il serait donc faux d'annoncer ici un écart de résultat fiscal entre clôture et liasse. Ce contournement SQL de l'exercice clos n'est pas renuméroté comme un nouveau défaut d'immuabilité.
- **Filtrage multi-biens :** le rapprochement par libellés de dotation de cession dans `fiscal._ventiler_39c_par_bien` (252) reste soumis au constat I-06 ; cette passe ne prétend pas avoir établi une affectation correcte pour toutes les collisions de libellés. Les comptes importés à sept chiffres restent rattachés à I-03.

## Non vérifiable avec les pièces fournies

- Où se trouve le CERFA 2033-B-SD 2026 annoncé comme joint, et est-il identique au millésime officiel consulté en ligne ?
- Pour une vente immobilière relevant de l'article 150 U, quelle instruction de remplissage impose de servir le cadre III du 2033-C, et avec quelles valeurs, sans y déclarer à tort une plus-value professionnelle ? Le PDF exécuté ne comporte pas ce cadre : faut-il un renvoi explicite vers la déclaration immobilière séparée, un état comptable annexe, ou des lignes de ce cadre ?
- Quel parcours pris en charge permet de reprendre une sortie partielle de composant issue d'un cabinet, avec son cumul propre, sa date et son éventuel stock 39 C, alors que la commande disponible cède le bien entier ?
- Quelle pièce ou ventilation fait autorité pour rapprocher le cumul d'un cabinet et le plan courant, notamment lorsque plusieurs composants partagent un même compte d'amortissement ?
- Comment qualifier le devenir fiscal du stock 39 C dans chaque cas de cessation de location, de cession et de poursuite de l'activité, au-delà de sa sortie constatée du suivi logiciel et des réserves de la passe I ?
- Les mêmes résultats tiennent-ils avec les particularités des dossiers privés de référence, qui n'ont pas été ouverts, et quel serait l'impôt personnel effectif compte tenu du foyer, de la plus-value immobilière et des exonérations applicables ?

## Tableau récapitulatif numéroté

| N° | Constat | Gravité | Conséquence reproduite |
|---|---|---|---|
| L-01 | Cumul théorique utilisé pour sortir un historique comptable différent | Majeur | VNC surévaluée de 1 800 € ; amortissements résiduels de 1 800 € |
| L-02 | Ouverture et mouvements du bien cédé absents du 2033-C | Majeur | Brut de 12 000 € et mouvements d'amortissement absents ; contrôles positifs |
| L-03 | Cession antérieure à l'acquisition acceptée | Majeur | Actif de 12 000 € sorti sur une date impossible ; liasse conforme |
| L-04 | Déclaration immobilière séparée non rappelée dans le PDF | Mineur | Démarche restante non explicitée au destinataire du PDF ; pense-bête correct sur ce point |

**État du suivi :** les quatre constats ont été corrigés en production le 16 septembre 2026 (version 8.47.0). Les preuves de `preuves_l/` sont conservées **telles qu'observées avant correction** : elles restent la référence du défaut, pas de l'état actuel du code. La non-régression est figée par `tests/test_passe_l.py` (24 tests), dont 13 échouent si l'on retire les correctifs.

Trois précisions sur le traitement retenu. Pour L-01, le cumul à solder est lu dans les comptes via `cession._cumuls_a_solder`, appelé **avant toute insertion** ; lorsque le compte d'amortissement est partagé avec des composants qui ne sont pas cédés et que son solde s'écarte du plan au-delà du seuil de matérialité déjà employé ailleurs (1 € ou 1 %), la cession est **refusée** plutôt qu'arbitrée — un partage concordant, lui, ne bloque rien. Pour L-02, les montants de diminution sont lus dans les écritures de cession, qui portent l'identifiant du bien dans leur référence de pièce depuis la passe I ; ils ne sont pas recalculés depuis le plan, par le même principe que L-01. Pour L-04, la liasse expose désormais une clé `cession_de_l_exercice` plutôt que de laisser le rendu déduire la présence d'une cession de montants, ce qui couvre la cession à titre gratuit.

Deux questions du rapport restent ouvertes et ne sont pas tranchées ici : le remplissage du cadre III du 2033-C pour une plus-value relevant de l'article 150 U, et la reprise d'une sortie partielle de composant issue d'un cabinet — la commande disponible cède le bien entier.
