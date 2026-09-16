# Passe I — Article 39 C : plafond, mémoire et ventilation par bien

Réexamen du 15 septembre 2026. **Cinq constats majeurs actifs : I-07, I-10, I-11, I-12 et I-13. Huit constats initiaux ne se reproduisent plus.** Leur numérotation est conservée pour permettre le suivi des corrections.

## Version examinée et méthode

Le répertoire source est `compta_lmnp/`, mais son fichier `VERSION` indique désormais **8.43.0**. Des modifications de production sont apparues pendant cette reprise de l'audit, notamment dans `fiscal.py`. Les premières exécutions confirmaient le rapport initial ; elles ne décrivent plus le code final examiné. Une copie des sources a donc été figée, les scénarios réexécutés sur cette copie puis sur le répertoire courant, et leurs empreintes comparées. Le [manifeste de 40 fichiers](preuves_i/reverification_source.json) identifie exactement cette version, y compris ses modifications non commitées. Aucun correctif de production n'a été appliqué par cette passe.

Les cinq pièces demandées sont présentes. `controles.py`, `cession.py`, `migrations.py`, `liasse_pdf.py`, `rejeu_fec.py`, `perennite.py` et `app.py` ont aussi été utilisés : ils sont nécessaires pour vérifier les alertes, les importations, la restauration et le document réellement imprimé. Les références fichier/ligne ci-dessous sont relatives à la racine source. Les invariants, le CHANGELOG, les correctifs antérieurs et le test de calage ont été consultés.

Toutes les reproductions publiées utilisent des identités fictives et des bases temporaires blanches. **Exception strictement privée : les assertions du calage historique ont été exécutées sur leurs FEC de référence, sans conserver ni publier leurs valeurs, libellés ou sorties brutes.** Les copies temporaires de ce calage sont supprimées à la fin.

### Preuves exécutables

- [Reproduction principale](preuves_i/reproduire.py) et [résultats](preuves_i/resultats.json) : 38 groupes, dont 216 combinaisons du moteur, export/rejeu de FEC fictifs et quatre PDF.
- [Deux nouveaux scénarios de répartition](preuves_i/cas_complementaires.py) et [sorties](preuves_i/cas_complementaires.json).
- [Oracle décimal indépendant et propagation en N+1](preuves_i/complements_reverification.py), [sorties](preuves_i/complements.json) : 216 comparaisons supplémentaires de la formule complète, puis deux chaînes de clôtures.
- [Lanceur du calage privé](preuves_i/calage.py), [statut sans données privées](preuves_i/calage.json) : **cinq exécutions réussies**, couvrant les trois exercices, les reports finaux et l'imputation historique. `pytest` étant absent, le lanceur retire uniquement son import et ses décorateurs ; les corps de la fixture et des assertions existantes sont exécutés sans modification. Ce n'est pas une exécution de toute la suite pytest.
- [Vérificateur](preuves_i/verifier.py) : **115 vérifications réussies**, y compris les empreintes des sources. Il vérifie les résultats effectivement produits, dont les comportements défectueux, et ne constitue pas une spécification à conserver après correction.

Commandes depuis la racine :

```bash
compta_lmnp/.venv/bin/python docs/preuves_i/reproduire.py
compta_lmnp/.venv/bin/python docs/preuves_i/cas_complementaires.py
compta_lmnp/.venv/bin/python docs/preuves_i/complements_reverification.py
compta_lmnp/.venv/bin/python docs/preuves_i/calage.py
compta_lmnp/.venv/bin/python docs/preuves_i/verifier.py
```

Environnement : Python 3.14.6, SQLite 3.51.2, `pdftotext` pour l'extraction des PDF. La page contenant le suivi mono-bien a aussi été rendue en image et examinée. Le [rapport antérieur](preuves_i/rapport_avant_correctifs.md) et ses [sorties antérieures](preuves_i/resultats_avant_correctifs.json) restent des pièces historiques, pas le bilan actif.

## Référentiel et confrontation au calage

Le plafond porte sur les loyers acquis diminués des charges afférentes ; les frais de comptabilité de structure en sont exclus. Le plafond est global pour plusieurs biens, mais la ventilation du report vise les seuls biens en insuffisance, avec la clé précisée au § 100. [BOFiP, BOI-BIC-AMT-20-40-10-20, § 40–100](https://bofip.impots.gouv.fr/bofip/4527-PGP.html/identifiant=BOI-BIC-AMT-20-40-10-20-20170301).

Le report se déduit ultérieurement dans les limites prévues, y compris après extinction de l'annuité courante. Sa sortie du logiciel n'établit pas à elle seule une perte fiscale définitive : cessation de location et cession appellent leurs règles propres. [CGI, article 39 C, II-2 et II-3](https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000029355753), [BOFiP, conséquences des limitations](https://bofip.impots.gouv.fr/bofip/4555-PGP.html/identifiant=BOI-BIC-AMT-20-40-10-30-20120912).

Le **2033-C n'est pas le tableau de stock 39 C**. Sa notice porte sur les immobilisations et amortissements. Le suivi complémentaire relève notamment du modèle BOI-FORM-000038. La case 318 du 2033-B 2026 inclut les autres amortissements non déductibles ; son intitulé mentionnant l'article 39-4 ne confond pas les deux mécanismes. [Formulaire 2033-SD 2026, pages 2–3](https://www.impots.gouv.fr/sites/default/files/formulaires/2033-sd/2026/2033-sd_5394.pdf), [notice 2033-NOT-SD 2026](https://www.impots.gouv.fr/sites/default/files/formulaires/2033-sd/2026/2033-sd_5395.pdf), [obligations de suivi](https://bofip.impots.gouv.fr/bofip/4545-PGP.html/identifiant=BOI-BIC-AMT-20-40-10-40-20130826), [modèle officiel](https://bofip.impots.gouv.fr/bofip/4547-PGP.html/identifiant=BOI-FORM-000038-20130826).

**Le calage mono-bien passe sur le code réexaminé.** Aucun constat ne remet en cause la majoration du plafond par une réintégration manuelle légitime d'une charge afférente. Les cas multi-biens ci-dessous confrontent la ventilation au BOFiP, une propriété que ce calage mono-bien ne peut établir. Les valeurs privées du calage ne figurent pas dans ce rapport.

## Constats actifs

### I-07 — Après migration, une dotation du bien conservé est encore affectée au bien déjà cédé

**Gravité : majeur.** Diagnostic initial amendé : les 5 000 € historiques sont maintenant conservés ; la perte reproduite porte sur les **1 000 € de report courant**.

**Fichiers et fonctions :** `modules/migrations.py`, `_palier_2`, ligne **28**, et `migrer`, ligne **100** ; `modules/fiscal.py`, `_ventiler_39c_par_bien`, ligne **472**, repli de dotation à **536**.

**Scénario :** base fictive à deux biens ; 2025 clos, stock global de 5 000 €, aucun détail par bien. Supprimer la table locale et marquer le schéma en version 1, puis exécuter la migration. Pour 2026, déclarer A cédé au 31 décembre 2025 ; B seul possède un composant actif de 10 000 € sur dix ans. Comptabiliser sa dotation de 1 000 €, sans ligne de plan, puis clôturer avec `generer_dotation=False`. Preuve : `migration_stock_historique`.

**Attendu :** conserver les 5 000 € en attente d'affectation documentée ; attribuer les 1 000 € de dotation courante au bien actif, ou refuser une affectation indéterminée. Ne pas sortir son report au titre de A.

**Produit réel :**

```text
migration : avant=1 ; apres=7 ; détail historique=[]
A : ouverture=0 ; dotation=1000 ; report=1000 ; sortie=1000 ; clôture=0
B : ouverture=5000 ; dotation=0 ; report=0 ; clôture=5000
global : ouverture=5000 ; report=1000 ; sorties=1000 ; clôture=5000
```

**Conséquence :** **1 000 € de report courant disparaissent du suivi** alors qu'ils appartiennent au bien conservé. Le repli du stock d'ouverture utilise désormais un bien conservé ; celui des dotations conserve le premier identifiant, même cédé. La migration ne fabrique pas cette cession : elle est explicitement fournie par le scénario. La propriété des 5 000 € anciens reste inconnue ; aucune perte de cette somme n'est affirmée.

### I-10 — L'avertissement sur le retraitement manuel arrive après la clôture

**Gravité : majeur.**

**Fichiers et fonctions :** `modules/controles.py`, `c_retraitement_manuel_majore_le_plafond`, ligne **314** ; `app.py`, `cloturer`, ligne **1225** ; `modules/fiscal.py`, `_calcul_fiscal`, ligne **615**.

**Scénario :** bien de 12 000 € sur dix ans, loyers 2026 de 200 €, aucune autre charge. Le report attendu est de 1 000 €. Saisir aussi 1 000 € dans le champ manuel de clôture et exécuter le POST Flask. Comparer ensuite deux chaînes 2026–2027, avec ou sans cette saisie, pour des loyers 2027 de 2 200 € et une dotation de 1 200 €. Preuves : `web_retraitement_manuel`, `report_saisi_manuellement_1000`, `complements.json`.

**Attendu :** l'avertissement doit examiner la valeur soumise avant de figer la clôture. Si l'utilisateur retire ce report déjà calculé automatiquement, le stock 2026 est de 1 000 €, utilisable en 2027.

**Produit réel :**

```text
Avant clôture : contrôles=[]
POST : HTTP 302 ; message de succès ; statut=clos
Après clôture : RETRAITEMENT_MANUEL_PLAFOND
                     sans saisie manuelle     avec saisie de 1000
stock fin 2026                1000                      0
résultat fiscal 2026             0                      0
utilisation 2027              1000                      0
revenu imposable 2027            0                   1000
```

**Conséquence :** **1 000 € de report manquent, puis 1 000 € de revenu imposable supplémentaires sont produits en 2027**. Le défaut n'est pas une double réintégration immédiate : la saisie augmente aussi le plafond et efface le report. `retraitement_automatique` ne contient pas lui-même le report 39 C. Le contrôle existe mais lit la valeur déjà sauvegardée ; les retraitements manuels justifiés restent nécessaires.

### I-11 — Le PDF mono-bien omet le mouvement de sortie du stock

**Gravité : majeur.**

**Fichiers et fonctions :** `modules/liasse.py`, `suivi_reports`, ligne **405** ; `modules/liasse_pdf.py`, `generer_pdf`, ligne **146**, tableau global à **360–366**, condition du détail à **372**.

**Scénario :** un bien, stock d'ouverture de 5 000 €, composant de 12 000 € sur dix ans, aucun loyer, cession le 31 décembre 2026 pour 12 000 €. Clôturer et générer le PDF. Preuves : `pdf_cession_un_bien`, [PDF](preuves_i/cession_un_bien.pdf), [texte extrait](preuves_i/cession_un_bien.txt).

**Attendu :** rendre visible la sortie de 6 200 €, pour expliquer `5 000 + 1 200 − 0 − 6 200 = 0`.

**Produit réel :** la clôture retourne `sorties_39c=6200`, mais le PDF imprime :

```text
Stock d'ouverture                          5 000,00 €
Amortissements reportés cette année         1 200,00 €
Amortissements repris cette année               0,00 €
Stock à la clôture                              0,00 €
```

**Conséquence :** **6 200 € de mouvement restent inexpliqués dans le document conservé**. La base contient la sortie : ce n'est pas une nouvelle perte comptable. Le tableau par bien, qui pourrait l'expliquer, est masqué quand il n'y a qu'un bien. Le contrôle porte sur un PDF réellement généré, extrait et examiné visuellement.

### I-12 — Avec deux biens éligibles, la nouvelle clé reste différente de celle du BOFiP

**Gravité : majeur.** Nouveau scénario, distinct du cas I-05 corrigé où un seul bien était éligible.

**Fichier et fonctions :** `modules/fiscal.py`, `_insuffisances_par_bien`, ligne **395**, et `_ventiler_39c_par_bien`, ligne **472**.

**Scénario :** A : composant de 10 000 € sur dix ans, loyers de 500 € ; B : composant de 30 000 € sur dix ans, loyers de 1 000 €. Mise en service au 1er janvier 2026, aucune charge. Céder A le 31 décembre pour 10 000 €, puis clôturer. Preuve : `cas_complementaires.json`, clé `cle_marges`.

**Attendu :** dotation globale de 4 000 €, plafond de 1 500 €, report de 2 500 €. Les deux biens sont éligibles. Le § 100 retient les excédents de loyers sur charges comme poids : 500 et 1 000. Report A **833,33 €**, B **1 666,67 €**. Après sortie de A, reste **1 666,67 €**. [BOFiP, § 100](https://bofip.impots.gouv.fr/bofip/4527-PGP.html/identifiant=BOI-BIC-AMT-20-40-10-20-20170301).

**Produit réel :**

```text
report global=2500 ; report A=500 ; report B=2000
sortie A=500 ; stock global conservé=2000
```

**Conséquence :** **333,33 € de stock supplémentaires sont conservés pour B**. Le code pondère par l'insuffisance de dotation, ici 500 et 2 000, au lieu des marges locatives positives. Le total concorde avant cession ; cette concordance n'établit pas la bonne propriété du report. Ce scénario ne requiert aucune interprétation des marges nulles ou négatives.

### I-13 — Les frais de structure reviennent dans la marge par bien

**Gravité : majeur.**

**Fichier et fonctions :** `modules/fiscal.py`, `_insuffisances_par_bien`, ligne **395**, et `_ventiler_39c_par_bien`, ligne **472**.

**Scénario :** mêmes composants A de 10 000 € et B de 30 000 €, sur dix ans depuis le 1er janvier 2026. Loyers A=2 000 €, B=1 000 €. Saisir 1 500 € de frais de tenue comptable avec le gabarit `honoraires`, rattachés à A. Céder A le 31 décembre pour 10 000 €, puis clôturer. Preuve : `cas_complementaires.json`, clé `honoraires`.

**Attendu :** ces frais de structure ne diminuent pas la marge locative. A couvre sa dotation ; le report global de 1 000 € appartient intégralement à B et reste après la cession de A. [BOFiP, § 70 et 100](https://bofip.impots.gouv.fr/bofip/4527-PGP.html/identifiant=BOI-BIC-AMT-20-40-10-20-20170301).

**Produit réel :**

```text
plafond global=3000 ; report global=1000
report A=200 ; report B=800 ; sortie A=200 ; stock conservé=800
```

**Conséquence :** **200 € du report du bien conservé sont retirés du suivi**. L'exclusion tient dans `agregats`, mais la marge locale additionne les opérations de charge sans reprendre cette exclusion. Les alertes produites concernent la ventilation du prix et des postes habituels absents ; aucune ne signale cette affectation 39 C erronée.

## Ce qui a été vérifié et tenu

### Huit constats initiaux corrigés dans les scénarios rejoués

| Référence | Résultat réel actuel |
|---|---|
| I-01 — compte 6811200 | Dotation reconnue 2 000 € ; report 1 000 € ; aucun déficit artificiel. |
| I-02 — compte 6226100 | Frais exclus 500 € ; report 1 000 € ; déficit 500 €, identiques au compte natif. |
| I-03 — comptes 6750000/7750000 | Même plafond et mêmes neutralisations que les comptes natifs ; revenu imposable nul, report 1 000 €. |
| I-04 — produit financier 768000 | Produit hors loyers ; plafond 1 000 €, report 1 000 €. |
| I-05 — seul B en insuffisance | Report A=0, B=1 000 € ; après cession de A, stock conservé=1 000 €. Les nouveaux cas I-12/I-13 ne retirent pas ce succès. |
| I-06 — composants cédés de même nom | Dotations locales totales=6 000 € ; sorties=3 000 € ; stock conservé=3 000 €, comme avec des noms distincts. |
| I-08 — détail plus ancien que le global | Ouverture globale et locale=5 000 € ; utilisation=1 000 € ; clôture globale et locale=4 000 €. L'affectation historique à un bien reste à documenter ; la divergence arithmétique initiale a disparu. |
| I-09 — quatre parts pour 0,02 € | Reports locaux `[0.01, 0.01, 0, 0]` ; aucune utilisation négative ; total local=global=0,02 €. |

### Autres propriétés éprouvées

- **Moteur isolé :** 216 cas d'invariants, puis comparaison complète de 216 cas avec une formule indépendante en `Decimal`, sans divergence. Plafond −300 €, stock 5 000 €, dotation 1 200 € : report 1 200 €, reprise zéro, clôture 6 200 €. Stock 5 000 €, dotation zéro, plafond 1 500 € : reprise 1 500 €, clôture 3 500 €.
- **Mémoire :** sans exercice N−1, le dernier suivi antérieur est repris. Une clôture est refusée tant qu'un exercice antérieur est ouvert. Un report de 2020 reste utilisable en 2040 ; le déficit expiré de la même fixture est, lui, soldé. Une restauration complète ramène l'exercice à l'état ouvert et son stock d'ouverture à 5 000 €, sans suivi résiduel de l'exercice restauré.
- **Liste d'exclusions :** configurable par ajout SQL d'un compte exact ; les défauts sont réinsérés après vidage lorsque leurs comptes existent. Sur référentiel minimal sans ces comptes, liste vide, loyers 1 000 €, maintenance 200 € : plafond 800 €. Le vide n'est pas à lui seul une erreur ; l'omission de frais de structure présents abaisserait le plafond. Aucune interface de configuration n'est présumée.
- **Cession native :** 15 000 € de produit et 10 000 € de VNC sont neutralisés sans double soustraction du produit ; le plafond locatif reste 1 000 € dans le scénario.
- **ALUR :** automatique actif sans manuel et automatique désactivé avec manuel légitime de 200 € donnent les mêmes chiffres. Le report 39 C est calculé séparément des retraitements automatiques.
- **Acquisition et absence de loyers :** acquisition en juillet d'un bien sans loyer, second bien à marge négative : report 1 804,93 €, déficit 300 €, conservation locale/globale. Cela établit les sommes, pas une règle fiscale générale pour toutes les marges négatives.
- **Cession en juin puis N+1 :** sortie locale de 1 595,07 €, stock du bien conservé de 4 200 €, repris l'année suivante sans nouvelle sortie du stock déjà éliminé.
- **Liasse réellement imprimée :** report de 1 000 € en réintégration case 318 ; utilisation ultérieure de 1 000 € en déduction case 350. Les cases sont présentes avec leur montant et le bon sens. La ligne 352 nulle reste le choix de présentation expressément exclu des constats.
- **Transactions des lectures :** témoin inséré avant `_table_39c_bien`, `suivi_39c_par_bien`, `comptes_hors_plafond_39c`, `_stock_39c_ouverture` ou `parametres.valeur` ; chaque lecture produit zéro commit instrumenté et zéro témoin après rollback.
- **Calage historique :** les cinq assertions exécutées sur les trois exercices et leurs reports réussissent ; aucune valeur réelle n'est reprise dans les preuves publiques.

## Non vérifiable avec les pièces fournies

- Quelle ventilation historique justifiée affecte les stocks globaux anciens aux biens ? La conservation du total et son affectation provisoire à un bien conservé ne reconstituent pas cette information.
- Quelle procédure a produit les historiques volontairement incomplets des fixtures ? Une clôture courante complète les produit-elle réellement, ou faut-il une reprise incomplète ?
- Quelle règle validée applique le § 100 lorsque plusieurs biens éligibles ont des marges nulles ou négatives ? Les scénarios I-12 et I-13 évitent cette ambiguïté.
- Quel traitement propre au bien articule sa sortie du suivi logiciel, l'article 39 C II-3 et la plus-value immobilière des particuliers effectivement déclarée ? Les montants sortis du suivi ne sont pas présentés comme une perte fiscale définitive universelle.
- Quelle qualification fiscale appliquer à un produit financier particulier dans la déclaration du foyer, au-delà de son exclusion testée de la base des loyers ?
- Quels contrôles en amont empêchent réellement toute entrée non finie ou négative dans le moteur isolé ? Les essais hors contrat sont conservés dans `moteur_limites`, sans en faire un défaut utilisateur faute de chemin établi.
- Les sources modifiées après les empreintes jointes reproduisent-elles encore ces résultats ? Le rapport porte sur la version identifiée, pas sur des corrections ultérieures éventuelles.
- Quelle preuve de réception EDI permet de conclure à l'acceptation administrative des états ? Aucun dépôt n'a été effectué.

## Tableau récapitulatif numéroté

Les montants désignent des stocks, des mouvements ou du revenu imposable, jamais un impôt personnel calculé.

| N° | État après réexécution | Conséquence active | Gravité active |
|---|---|---|---|
| I-01 | Corrigé dans le scénario de dotation à sept chiffres | — | — |
| I-02 | Corrigé dans le scénario d'honoraires à sept chiffres | — | — |
| I-03 | Corrigé dans le scénario de cession à sept chiffres | — | — |
| I-04 | Corrigé dans le scénario de produit financier | — | — |
| I-05 | Corrigé lorsque seul un bien produit le report | — | — |
| I-06 | Corrigé pour les nouvelles cessions de composants homonymes | — | — |
| I-07 | Partiellement corrigé ; dotation encore mal affectée | 1 000 € de report courant sortis à tort | majeur |
| I-08 | Divergence arithmétique corrigée ; propriété historique non établie | — | — |
| I-09 | Corrigé dans le cas des quatre parts de centimes | — | — |
| I-10 | Maintenu ; propagation en N+1 exécutée | 1 000 € de report manquants ; revenu imposable N+1 majoré de 1 000 € | majeur |
| I-11 | Maintenu | Sortie de 6 200 € inexpliquée dans le PDF mono-bien | majeur |
| I-12 | Nouveau : mauvaise clé entre deux biens éligibles | 333,33 € de stock conservés en trop après cession | majeur |
| I-13 | Nouveau : frais de structure dans la marge locale | 200 € du report du bien conservé sortis à tort | majeur |

**État du suivi :** les onze constats ont été corrigés en production le 15 septembre 2026 (version 8.44.0). Les preuves de `preuves_i/` sont conservées **telles qu'observées avant correction** : elles restent la référence du défaut, pas de l'état actuel du code. La non-régression est figée par `tests/test_passe_i.py` (39 tests), dont 22 échouent si l'on retire les correctifs.

Trois choix de traitement méritent d'être signalés. D'abord, les comptes ne sont plus reconnus par égalité mais par **racine PCG** (`6811`, `775`, `675`, et les exclusions du plafond réduites à leur racine) : une subdivision hérite de la qualification de sa racine, ce qui règle I-01, I-02 et I-03 d'un même mouvement. Ensuite, la répartition du report suit l'**insuffisance** de chaque bien — sa dotation moins sa marge locative, lue dans les opérations — conformément au § 100 du BOFiP ; la question laissée ouverte par le rapport pour les marges nulles ou négatives est tranchée par `max(0, dotation − max(0, marge))`, choix conservateur qui n'attribue jamais de report à un bien bénéficiaire, et le repli par dotations subsiste quand aucune opération n'est rattachée aux biens. Enfin, ce que la ventilation historique ne sait pas attribuer est rattaché au premier bien **non cédé** afin que la somme des stocks locaux égale toujours le stock global : c'est un pis-aller assumé, et le contrôle `VENTILATION_39C` demande à l'utilisateur de le vérifier avant toute cession.

Le constat I-10 est traité en faisant consulter l'avertissement par la route de clôture avec la valeur soumise, et en exigeant la case « Forcer » pour passer outre — mécanisme déjà employé pour les anomalies bloquantes. Le retraitement manuel légitime reste donc possible, ce que le calage sur liasses réelles exige.
