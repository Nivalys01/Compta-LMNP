# Passe J — Déficits LMNP : péremption, imputation et déclaration

Audit du **15 septembre 2026**, sur `compta_lmnp_v8.41.0/compta_lmnp/`.

**Cinq nouveaux constats reproduits : un critique, trois majeurs, un mineur.** Le moteur respecte l'année limite et l'ordre FIFO sur les cas exécutés. Les défauts nouveaux concernent surtout les montants remis au déclarant et la conservation de leur historique. Les confusions entre déficit ordinaire et amortissement différé déjà établies en passe I sont prolongées jusqu'en N+11, sans nouvelle numérotation.

## Correctifs appliqués — 15 septembre 2026

Les constats et preuves ci-dessous décrivent **l'état avant correction** et sont conservés
sans réécriture. Seule la passe J a été traitée ; les autres fichiers de passe n'ont pas
été lus pour cette intervention.

| Priorité | Constat | Correction |
|---|---|---|
| Critique | J-01 | L'aide 2042 lit les soldes d'ouverture réellement enregistrés à la clôture, y compris les millésimes entièrement consommés. Les lignes de même origine sont additionnées avant arrondi. |
| Majeur | J-02 | Un instantané annuel conserve chaque millésime, son ouverture, son imputation, son solde final et sa perte par péremption. Les rééditions utilisent cet instantané, même vide, et ne voient plus les déficits futurs. |
| Majeur | J-03 | La perte effective par péremption est enregistrée distinctement du montant initial et du solde final. Le PDF indique le total perdu et son détail par origine après clôture. |
| Majeur | J-04 | Le contrôle du seuil utilise les loyers acquis issus des écritures, via `fiscal.agregats`, pour couvrir aussi le FEC rejoué. Il ne cumule pas opérations et écritures. Le franchissement reste un avertissement invitant à vérifier le second critère du foyer. |
| Mineur | J-05 | Les cases utilisent `Decimal` et `ROUND_HALF_UP` : 100,50 → 101 et 0,50 → 1, après regroupement par millésime. |

### Persistance et dossiers existants

La nouvelle table `suivi_deficits` associe un exercice à un instantané JSON autonome.
Elle figure dans `schema.sql` et est créée à la première clôture d'un dossier ancien.
La création et l'enregistrement ne provoquent aucun commit intermédiaire ; la clôture
reste atomique. Un second appel au moteur des déficits pour un exercice déjà tracé est
refusé **avant toute modification des stocks**. Cela renforce aussi la protection des
appels directs, au-delà de la protection déjà assurée par `cloturer`.

**Limite des anciennes clôtures :** aucun historique n'est inventé à partir du montant
initial et du solde courant. Une demande de suivi ou de liasse pour un exercice clos
sans instantané est refusée avec un message explicite indiquant de consulter les
archives de déclaration ou une sauvegarde antérieure à la clôture. Le correctif ne
répare donc pas automatiquement les états historiques des dossiers déjà clos avant
son installation. Les nouvelles clôtures enregistrent les stocks effectivement
présents à leur ouverture ; leurs rééditions sont stables.

### Résultats de non-régression

Tests dédiés : [test_passe_j.py](../compta_lmnp_v8.41.0/compta_lmnp/tests/test_passe_j.py).
**35 tests réussis**, exclusivement sur bases blanches et données fictives :

- restitution de 1 000 € entièrement consommés et de 6 000 € répartis sur trois années ;
- bonne attribution de 500 € en 5GF et 1 000 € en 5GJ lorsque le stock de reprise était déjà partiellement consommé ;
- stabilité du suivi et du texte PDF après consommation ultérieure puis création d'un déficit futur ;
- conservation de 1 200 € perdus sur un déficit initial de 2 000 €, avec 800 € disponibles ;
- expiration à N+11, disponibilité à N+10 et stabilité d'un instantané vide ;
- alerte identique après saisie native et rejeu FEC, seuil strict et absence de double comptage ;
- 18 cas d'arrondi : bénéfice, déficit courant et déficit antérieur, dont 0,49 et 0,50 € ;
- migration d'un ancien schéma, rollback après interruption réelle du moteur, `commit=False`, refus d'un double traitement et refus explicite d'une ancienne réédition non traçable.

```bash
compta_lmnp_v8.41.0/compta_lmnp/.venv/bin/python -m pytest -q compta_lmnp_v8.41.0/compta_lmnp/tests/test_passe_j.py
```

La suite complète exécutée avant l'ajout des cinq derniers tests dédiés a donné
**896 réussites, 2 tests ignorés et 2 échecs** : contrôle de publication signalant
les PDF d'audit déjà présents, et test de serveur local inaccessible dans le bac à
sable. Le test du serveur local a ensuite été réexécuté hors du bac à sable :
**1 réussite**. Il reste donc le contrôle de publication, dont les avertissements
concernent les PDF existants. Le contrôle
Ruff des quatre modules modifiés et du nouveau fichier de tests est passé.
Les scripts et fichiers `preuves_j` originaux sont conservés : leur vérificateur
fige les anomalies et empreintes **avant** correction et n'est pas un test de
non-régression du nouvel état.

Références revérifiées pour les règles utilisées :
[DGFiP, location meublée](https://www.impots.gouv.fr/particulier/location-meublee)
et [BOFiP, arrondis des bases](https://bofip.impots.gouv.fr/bofip/5709-PGP.html/identifiant%3DBOI-BIC-BASE-30-20160203).
Les observations historiques relatives à I-01/I-02 restent hors du décompte J.

---

## Pièces et méthode

Les modules demandés, le schéma, `controles.py`, `parametres.py`, ainsi que les fonctions nécessaires d'ouverture, de rejeu et de restauration sont présents et ont été examinés. Les chemins et lignes ci-dessous sont relatifs à la racine source précisée ci-dessus.

**Rectification de l'inventaire annoncé :** [2042_Cpro.pdf](../2042_Cpro.pdf) est présent à la racine. C'est le CERFA **11222*28, revenus 2025**. Sa page 5 a été extraite et examinée visuellement, puis confrontée au [2042-C-PRO officiel publié en 2026](https://www.impots.gouv.fr/sites/default/files/formulaires/2042/2026/2042_5474.pdf). En revanche, aucun PDF 2033 n'a été trouvé à la racine actuelle ; le [2033-SD officiel 2026](https://www.impots.gouv.fr/sites/default/files/formulaires/2033-sd/2026/2033-sd_5394.pdf) a été consulté en ligne. Le millésime du formulaire ne doit pas être confondu avec l'année des revenus.

Les invariants et les corrections pertinentes du CHANGELOG ont été relus, notamment : exclusion des déficits périmés du total, restitution des stocks d'ouverture pour la 2042, avertissement sur la priorité du 39 C et protection des clôtures. Les passes G, H, I et Q disponibles ont été consultées pour éviter de renuméroter leurs constats. Les anciens rapports absents de l'arbre de travail n'ont pas été reconstitués.

**Exécutions :** [script](preuves_j/reproduire.py), [résultats complets](preuves_j/resultats.json), [vérificateur des résultats](preuves_j/verifier.py), [index des preuves](preuves_j/README.md). **50 groupes exécutés**, dont 15 cas d'arrondi ; **85 vérifications réussies** des sorties et des empreintes des six principaux fichiers source. Python 3.14.6, SQLite 3.51.2.

```bash
compta_lmnp_v8.41.0/compta_lmnp/.venv/bin/python docs/preuves_j/reproduire.py
compta_lmnp_v8.41.0/compta_lmnp/.venv/bin/python docs/preuves_j/verifier.py
```

Le reproducteur utilise des bases blanches temporaires, une identité fictive, des écritures fictives et `pdftotext`. Les tests de clôture appellent réellement le moteur ; les PDF sont réellement générés puis leur texte extrait. Les tests historiques indiquent lorsqu'un stock d'ouverture est injecté en SQL. Le test d'ancienne déclaration suit aussi une chronologie complète par les fonctions publiques. Aucun FEC privé, fichier d'identité ou fichier d'empreintes privées n'est utilisé. Le logiciel n'est pas modifié.

### Référentiel fiscal retenu

Le déficit LMNP ne s'impute pas sur le revenu global : son report est limité aux bénéfices de même nature des dix années suivantes. N+10 reste donc une année utile ; N+11 ne l'est plus. Un passage en LMP ne transforme pas le stock LMNP antérieur en déficit imputable sur le revenu global. [CGI, article 156, I-1° ter](https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000054373682), [BOFiP, régime fiscal de la location meublée, III-A, § 240 à 250](https://bofip.impots.gouv.fr/bofip/3610-PGP.html/identifiant=BOI-BIC-CHAMP-40-20-20260819).

Les numéros de cases sont contrôlés sur le formulaire des revenus 2025, pour le **déclarant 1, régime réel, cas général**. L'aide officielle distingue le résultat courant et les déficits antérieurs non encore imputés. Les pertes d'imputation chiffrées ci-dessous supposent que le déclarant recopie l'aide du logiciel sans rétablir les déficits depuis ses propres justificatifs ou un préremplissage administratif. [Aide officielle à la déclaration 2026](https://simulateur-ir-ifi.impots.gouv.fr/calcul_impot/2026/aides/revenus_professions.htm).

## J-01 — Les déficits entièrement consommés disparaissent de l'aide à la déclaration

**Gravité : critique.**

**Fichier et fonctions :** `modules/liasse.py`, `suivi_reports`, ligne **376**, et `aide_2042c`, ligne **429** ; `modules/liasse_pdf.py`, `generer_pdf`, ligne **146**, rendu de l'aide à partir de la ligne **413**.

**Scénario :** injecter un déficit d'origine 2024 de **1 000 €**, encore entièrement disponible à l'ouverture de 2025. Enregistrer **1 000 € de loyers en 2025**, sans autre charge ni amortissement. Clôturer et générer le PDF. Preuve : `restitution_1000`, [PDF produit](preuves_j/deficit_epuise.pdf).

**Attendu :** moteur : imputation de 1 000 €, revenu imposable nul. Pour la déclaration, `5NA=1000` et `5GJ=1000` : le déficit d'ouverture doit accompagner le bénéfice avant imputation. Le fait qu'il soit désormais consommé dans la comptabilité ne doit pas l'enlever des éléments nécessaires à l'imputation administrative de cette année.

**Produit réel :**

```text
clôture : impute_sur_benefice=1000 ; revenu_imposable=0
SQL : origine=2024 ; montant_initial=1000 ; solde=0
aide : case_5NA=1000 ; cases_deficits_anterieurs=[]
PDF : « 5NA — bénéfice location meublée non professionnelle  1 000,00 € »
      aucune ligne 5GJ
liasse : conforme=True ; contrôles métier=[]
```

**Conséquence :** **1 000 € de base restent sans déficit compensateur dans l'aide**, alors que le moteur calcule zéro imposable. La variante `fifo_7000` impute réellement 6 000 € sur un bénéfice de 7 000 €, puis propose `5NA=7000` sans aucune case de déficit antérieur : **6 000 € de déduction omis** dans ce cas. Il ne s'agit pas d'un impôt de ces montants, ni d'une preuve de ce que conserverait un préremplissage administratif.

**Pourquoi le correctif antérieur ne suffit pas :** avec un bénéfice limité à 500 €, le même déficit laisse un solde de 500 € et l'aide reconstitue correctement `5GJ=1000`. Le correctif fonctionne donc pour ce cas partiel. Lorsque le solde atteint zéro, `suivi_reports` élimine la ligne avant que `aide_2042c` puisse la remonter à l'ouverture.

**Diagnostic amendé — une mauvaise année n'est pas toujours une perte supplémentaire :** la variante `restitution_mauvais_millesime` fournit à l'ouverture 500 € de 2020 et 1 000 € de 2024, ce dernier millésime ayant initialement valu 2 000 €. Avec un bénéfice de 500 €, l'aide propose seulement **1 500 € en 5GJ**, au lieu de **500 € en 5GF et 1 000 € en 5GJ**. Le total à l'ouverture reste alors correct ; après imputation du bénéfice, le reliquat reste 1 000 €. Ce sous-cas prouve une mauvaise attribution de l'année, **pas** une déduction supplémentaire ni une prolongation de 500 € après imputation. Il n'est pas compté comme un second constat financier.

## J-02 — Une clôture ultérieure change le suivi et l'aide d'un exercice déjà clos

**Gravité : majeur.**

**Fichier et fonctions :** `modules/liasse.py`, `suivi_reports`, ligne **376**, `aide_2042c`, ligne **429**, et `generer`, ligne **588** ; `modules/fiscal.py`, `traiter_deficit`, ligne **157**, qui fait évoluer le solde courant.

**Scénario, sans injection de déficit historique :**

1. En 2024, saisir 3 000 € de maintenance et clôturer : déficit de 3 000 €.
2. Ouvrir 2025, saisir 1 000 € de loyers et clôturer ; générer l'aide et le PDF 2025.
3. Ouvrir 2026, saisir 2 000 € de loyers et clôturer ; régénérer l'aide et le PDF **2025**.

Preuve : `ancienne_declaration`, [PDF avant](preuves_j/historique_avant.pdf), [PDF après](preuves_j/historique_apres.pdf).

**Attendu :** pour 2025, toujours 3 000 € de déficit à déclarer à l'ouverture en 5GJ et 2 000 € de stock après l'imputation de 2025. La consommation intervenue en 2026 ne change pas ces montants historiques.

**Produit réel :**

| État demandé : 2025 | Avant clôture 2026 | Après clôture 2026 |
|---|---:|---:|
| 5NA | 1 000 € | 1 000 € |
| 5GJ | 3 000 € | ligne absente |
| Total des déficits en stock | 2 000 € | 0 € |
| Liasse déclarée conforme | oui | oui |

La continuation `deficit_futur_dans_ancien_suivi` crée ensuite un déficit de **700 € en 2027** : le suivi demandé pour **2025** affiche ce millésime 2027 et un total de **700 €**. L'exercice 2025 est toujours clos.

**Conséquence :** une réédition de la déclaration 2025 perd **3 000 € de déficit d'ouverture** et laisse ses **1 000 € de bénéfice** sans compensation dans l'aide. Le suivi historique affiche ensuite **700 € d'une année future**. Les écritures comptables closes ne sont pas modifiées ; c'est le document reconstruit qui change. La table conserve un solde courant, pas les soldes par exercice nécessaires à une restitution historique fiable.

## J-03 — Après purge, la perte par péremption n'apparaît plus dans le PDF

**Gravité : majeur.**

**Fichier et fonctions :** `modules/fiscal.py`, `traiter_deficit`, ligne **157** ; `modules/liasse.py`, `suivi_reports`, ligne **376** ; `modules/liasse_pdf.py`, `generer_pdf`, ligne **146**, tableau à partir de la ligne **397**.

**Scénario :** exercice 2025 sans résultat, avec un déficit 2014 de **1 200 €**, expirant fin 2024, et un déficit 2024 de **800 €**. Générer le PDF avant clôture, clôturer puis générer le PDF après. Preuve : `trace_peremption`, [avant](preuves_j/peremption_avant.pdf), [après](preuves_j/peremption_apres.pdf).

**Attendu :** les 1 200 € ne sont plus disponibles, mais leur perte doit rester identifiable dans le suivi de l'exercice où la purge est appliquée. Total imputable : 800 € dans les deux états.

**Produit réel :**

```text
Avant : millésime 2014 affiché « 2024 — périmé »
        total_deficits=800 ; total_deficits_perimes=1200
Clôture : perimes=1
Après : total_deficits=800 ; total_deficits_perimes=0
        seul le millésime 2024 apparaît dans le PDF
SQL : deux lignes conservées ; ligne 2014 montant_initial=1200, solde=0
```

**Conséquence :** **1 200 € de perte ne sont plus expliqués dans le suivi imprimé après clôture**. Le compteur `perimes=1` est un nombre de lignes dans le retour de clôture, pas une trace imprimée du montant perdu. La ligne SQL n'est pas supprimée : il serait faux d'annoncer une suppression physique. Son montant initial ne dit pas à lui seul quelle part a été consommée et quelle part a expiré.

**Distinction de la correction antérieure :** le total disponible de 800 € est correct avant comme après. Le défaut n'est donc pas l'inclusion de déficits périmés dans le total, déjà corrigée ; c'est la disparition de leur explication après passage du solde à zéro.

## J-04 — Le contrôle du seuil LMP ne voit pas les recettes d'un FEC rejoué

**Gravité : majeur.**

**Fichier et fonctions :** `modules/controles.py`, `c_seuil_lmp`, ligne **549**, et `controler`, ligne **785** ; `modules/fiscal.py`, `cloturer`, ligne **471**, et `traiter_deficit`, ligne **157**.

**Scénario :** saisir 30 000 € de loyers par `operations.saisir` et 35 000 € de maintenance en 2025. Comparer la clôture de cette base avec l'export de ses écritures en FEC, leur rejeu dans une base blanche et la clôture de celle-ci. Preuves : `seuil_lmp_import_False` et `_True`.

**Attendu :** les mêmes 30 000 € de recettes doivent déclencher le même avertissement de seuil, quelle que soit leur origine. Le seuil dépassé exige de vérifier le second critère au niveau du foyer ; il ne suffit pas à déclarer automatiquement le contribuable LMP.

**Produit réel :**

| Sortie | Saisie native | Après rejeu du FEC |
|---|---:|---:|
| Recettes comptabilisées | 30 000 € | 30 000 € |
| Contrôles avant clôture | `SEUIL_LMP` | aucun |
| Lignes dans `operation` | 1 | 0 |
| Déficit créé | 5 000 € LMNP | 5 000 € LMNP |
| Aide 5NY | 5 000 € | 5 000 € |

**Conséquence :** **5 000 € sont affectés au régime LMNP sans l'avertissement prévu**, alors que le critère de recettes à examiner est dépassé. Le contrôle additionne les opérations de saisie, pas les recettes comptables importées. Le moteur de déficit suppose le statut LMNP ; il ne reçoit pas de qualification du foyer et ne la vérifie pas. En saisie native, l'alerte est un avertissement et n'empêche pas à elle seule la clôture.

La fixture ne fournit pas les autres revenus du foyer : **aucune erreur effective de statut ni imputation sur le revenu global de 5 000 € n'est prétendue établie**. Le constat est le garde-fou inopérant sur un chemin explicitement supporté. Les deux critères et le changement de traitement doivent être appréciés au niveau du foyer. [DGFiP, location meublée](https://www.impots.gouv.fr/particulier/location-meublee).

## J-05 — L'aide arrondit certains demi-euros dans le mauvais sens

**Gravité : mineur.**

**Fichier et fonction :** `modules/liasse.py`, `aide_2042c`, ligne **429**, filtrage des soldes ligne **472**, arrondis des cases lignes **479–481** ; `modules/liasse_pdf.py`, `generer_pdf`, ligne **146**, impression des valeurs déjà arrondies.

**Scénario :** trois bases indépendantes, exercice 2025 : bénéfice de 100,50 €, déficit courant de 100,50 €, ou déficit antérieur 2024 de 100,50 € sans imputation. Clôturer et lire l'aide. Variantes à 100,49 €, 100,51 €, 101,50 € et 0,50 €. Preuves : les quinze groupes `arrondi_*`, [PDF du déficit courant](preuves_j/arrondi_deficit.pdf).

**Attendu :** 100,50 € donne **101 €** dans chacune des cases concernées ; un déficit antérieur de 0,50 € donne **1 €**. La fraction exactement égale à un demi-euro est comptée pour un dans l'arrondi fiscal. [CGI, article 193](https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000054373592).

**Produit réel :**

```text
Bénéfice 100.50 : case_5NA=100
Déficit 100.50 : case_5NY=100 ; PDF 5NY=100,00 €
Déficit 2024 de 100.50 : 5GJ=100
Déficit 2024 de 0.50 : cases_deficits_anterieurs=[]
Témoins : 100.49 → 100 ; 100.51 → 101 ; 101.50 → 102
```

**Conséquence :** **1 € manque dans la case** du bénéfice ou du déficit testé. Les montants comptables ne sont pas amputés en base : l'écart apparaît dans l'aide arrondie que le déclarant recopie. Le comportement est celui de l'arrondi Python au pair aux demi-unités ; le filtre strict `> 0.5` élimine également le déficit antérieur de 0,50 €.

## Confusion déficit / amortissement : conséquences après dix ans des constats I-01 et I-02

Ces causes ont déjà leur numéro dans [la passe I](AUDIT_PASSE_I.md) ; elles ne sont pas présentées comme de nouvelles découvertes J.

**Chemin exécuté :** écritures fictives → `export_fec.exporter` → nouvelle base → `rejeu_fec.rejouer` → `fiscal.cloturer(generer_dotation=False)` → `agregats` → `_calcul_fiscal` → `traiter_deficit`. Les écritures de dotation viennent du FEC : aucune dotation supplémentaire n'est générée. Après 2025, dix exercices sans nouveau résultat ni nouvelle dotation sont ouverts et clos, puis 1 500 € de loyers sont enregistrés en 2036. Cette séquence isole la mémoire des reports ; elle ne constitue pas un plan d'amortissement prospectif validé pour un immeuble réel.

**Fichiers et fonctions des causes conservées :** `modules/fiscal.py`, `agregats`, ligne **60**, `comptes_hors_plafond_39c`, ligne **36**, `_calcul_fiscal`, ligne **363**, et `traiter_deficit`, ligne **157**.

| Variante exécutée | Création en 2025 | Fin 2035, dernière année utile du déficit | Revenu imposable produit en 2036 |
|---|---|---|---:|
| Loyers 1 000 €, dotation 2 000 € en 681120 | Report 39 C : 1 000 € ; déficit : 0 € | Report 39 C : 1 000 € | 500 € |
| Mêmes flux, dotation en 6811200 — I-01 | Report 39 C : 0 € ; déficit : 1 000 € | Déficit encore disponible : 1 000 € | **1 500 €**, déficit purgé |
| Loyers 1 000 €, dotation native 2 000 €, comptabilité 500 € en 622610 | Report 39 C : 1 000 € ; déficit : 500 € | Les deux stocks subsistent | 500 €, déficit de 500 € purgé |
| Mêmes flux, comptabilité en 6226100 — I-02 | Report 39 C : 1 500 € ; déficit : 0 € | Report 39 C : 1 500 € | **0 €**, report intégralement utilisé |

Preuves : `dix_ans_normal`, `dix_ans_dotation7`, `dix_ans_honoraires6`, `dix_ans_honoraires7`.

- **I-01, critique : attendu 500 €, produit 1 500 € imposables en 2036.** Une erreur de qualification transforme 1 000 € d'amortissement sans péremption en déficit, puis les fait expirer : **1 000 € de déduction perdus** dans cette séquence.
- **I-02, majeur : attendu 500 €, produit zéro imposable en 2036.** Le mauvais traitement des honoraires déplace 500 € du déficit vers le report d'amortissement : **500 € de déduction deviennent utilisables après la date où le déficit correct aurait expiré**.

La comparaison porte sur des flux de même nature dont seul le numéro de compte change. Elle ne remet pas en cause le calage antérieur du plafond sur les comptes natifs ni le retraitement manuel légitime du fonds ALUR. Aucun montant issu des dossiers réels n'est utilisé. La durée sans péremption du report d'amortissement se distingue bien des dix ans du déficit : l'erreur se produit ici **avant** le moteur de péremption. [CGI, article 39 C, II-3](https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000029355753), [article 156, I-1° ter](https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000054373682).

## Cases du formulaire et visibilité de l'imputation

La page 5 du formulaire fourni confirme les correspondances suivantes. Le groupe `cases_dix_millesimes` crée dix stocks distincts non consommés ; il produit les montants ci-dessous et les imprime dans [dix_millesimes.pdf](preuves_j/dix_millesimes.pdf).

| Case | Rubrique / année sur le formulaire des revenus 2025 | Produit par l'exécution | Verdict sur le numéro |
|---|---|---:|---|
| 5NA | Bénéfice, déclarant 1, cas général | 1 000 € dans `restitution_1000` | correct |
| 5NY | Déficit, déclarant 1, cas général | 300 € dans `creation_ordinaire` | correct |
| 5GA | 2015 | 100 € | correct |
| 5GB | 2016 | 200 € | correct |
| 5GC | 2017 | 300 € | correct |
| 5GD | 2018 | 400 € | correct |
| 5GE | 2019 | 500 € | correct |
| 5GF | 2020 | 600 € | correct |
| 5GG | 2021 | 700 € | correct |
| 5GH | 2022 | 800 € | correct |
| 5GI | 2023 | 900 € | correct |
| 5GJ | 2024 | 1 000 € | correct |

**Aucun de ces numéros n'est faux dans ce périmètre.** Cela ne valide pas les montants omis ou mal reconstitués de J-01/J-02, ni les cas du déclarant 2, des revenus étrangers ou des organismes sociaux. [Formulaire officiel 2042-C-PRO 2026, page 5](https://www.impots.gouv.fr/sites/default/files/formulaires/2042/2026/2042_5474.pdf).

**2033-B :** dans le cas bénéfice 1 000 € / déficit antérieur 1 000 €, l'exécution retourne `resultat_fiscal_352=0` et `resultat_fiscal_370=0`. Aucun champ 360 ni 356 n'est servi par le tableau retourné ; aucune de ces lignes n'est imprimée dans le PDF testé. Le montant imputé de **1 000 €** reste présent dans le retour de clôture et `cloture_fiscale.impute_deficits`. La page de garde imprime un revenu imposable de **0 €**, tandis que la récapitulation 2031 bis porte le bénéfice avant imputation de **1 000 €**. L'imputation ne disparaît donc pas partout avec la mise à zéro de 352 : c'est l'aide 2042 incomplète de J-01 qui rompt la transmission dans ce cas.

La case 356 existe sur le formulaire officiel, mais aucun report en arrière n'est produit dans les scénarios déficitaires exécutés. L'absence d'imputation sur un résultat 2033-B volontairement nul n'est pas signalée comme un défaut du modèle. [2033-B-SD 2026, page 2 du formulaire](https://www.impots.gouv.fr/sites/default/files/formulaires/2033-sd/2026/2033-sd_5394.pdf).

## Ce qui a été vérifié et tenu

| Vérification exécutée | Résultat observé |
|---|---|
| Année pivot | Déficit 2015 de 800 € et bénéfice de 300 € : en 2024 et 2025, imputation de 300 €, reste 500 €. En 2026, purge puis bénéfice imposable de 300 €. N+10 est inclus, pas purgé prématurément. |
| Conservation physique après purge | La ligne reste en SQL avec son montant initial et un solde nul. Ce n'est pas un `DELETE`. L'insuffisance du rendu est J-03. |
| Total PDF avec déficit périmé | Avant clôture, 1 200 € périmés sont marqués et exclus du total, qui vaut 800 €. Après clôture, le total reste 800 €. La question laissée ouverte par l'ancienne passe est tranchée : le total ne les inclut pas dans ce scénario. |
| FIFO | Stocks 2017=1 000 €, 2019=2 000 €, 2024=3 000 € ; bénéfice de 2 000 € : soldes finaux **0 / 1 000 / 3 000 €**. L'ordre annoncé est bien exécuté. |
| Bénéfice supérieur au stock | Avec les mêmes 6 000 € de stocks et 7 000 € de bénéfice : imputation 6 000 €, reliquat imposable **1 000 €** dans le moteur. L'aide est affectée séparément par J-01. |
| Imputation au centime | Stocks de 0,01 € et 0,02 €, bénéfice de 0,04 € : imputation de **0,03 €**, deux soldes nuls, reliquat **0,01 €**. Aucun reste flottant n'est conservé. |
| Résultat nul ou bénéficiaire | Le résultat nul ne crée aucun déficit. Les scénarios bénéficiaires testés n'en créent pas par erreur de signe. |
| Déficit de charges ordinaires | Loyers 1 000 €, maintenance 1 300 € : RC=RF=−300 €, déficit créé **300 €**, aucun report 39 C. |
| Amortissement seul, comptes natifs | Loyers 1 000 €, dotation 1 200 € : RC=−200 €, report 39 C **200 €**, RF nul, aucun déficit ordinaire créé. |
| Mélange charges et amortissement | Loyers 1 000 €, maintenance 1 300 €, dotation 1 200 € : RC=−1 500 €, report 39 C **1 200 €**, RF=−300 €, déficit ordinaire **300 €**. |
| Retraitement ALUR avant création | Loyers 1 000 €, maintenance 1 300 €, ALUR 200 € : RC=−500 €, réintégration automatique **200 €**, RF=−300 €, déficit créé **300 €**, pas 500 €. |
| Deux clôtures successives | Déficit de 600 € : la première clôture crée une ligne ; la seconde est refusée comme déjà close ; une seule ligne de 600 € reste. |
| Deux clôtures concurrentes | Deux connexions démarrées avec une barrière : une réussite, un refus « déjà clos », une seule ligne de 600 €. |
| Restauration puis nouvelle clôture | Sauvegarde avant clôture, création de 600 €, restauration complète, nouvelle clôture : zéro déficit après restauration, puis une seule ligne de 600 €. Aucun cumul avec la clôture remplacée. |
| Moteur isolé | Deux appels directs de `traiter_deficit(..., −600)` créent deux lignes : il n'est pas idempotent. La protection vérifiée est celle de `cloturer`, pas une unicité de `annee_origine`. Aucun second chemin utilisateur contournant cette protection n'a été établi ici. |
| Échec après imputation réelle | Une exception est injectée après l'appel effectif au moteur des déficits. Fermeture puis réouverture : solde ancien **1 000 €** rétabli, exercice **ouvert**, zéro suivi 39 C. L'imputation de 600 € n'a pas survécu. |
| `commit=False` | Transaction ouverte, témoin inséré, déficit créé sans commit, rollback : transaction était encore ouverte, **zéro déficit et zéro témoin** après rollback. |
| Règle versionnée | Modification fictive à 12 ans effective en 2026 : un déficit 2025 expire en 2035 ; un déficit 2026 en 2038. La règle de création suit la version applicable à l'année. L'essai vérifie le versionnement, pas la légalité d'une durée de douze ans. |
| Alerte LMP en saisie native | Le cas à 30 000 € de loyers déclenche bien `SEUIL_LMP`. La portée manquante après rejeu est isolée en J-04. |

**Ordre d'imputation :** le FIFO privilégie effectivement le millésime qui expire le plus tôt lorsque la durée est de dix ans pour tous. Cela évite de consommer un stock plus récent en laissant se périmer un ancien. Les textes consultés établissent le délai et la nature des bénéfices imputables ; ils ne sont pas présentés ici comme une preuve d'une prescription expresse du FIFO propre au LMNP. La question normative résiduelle figure ci-dessous. Le cas connu où le 39 C absorbe le bénéfice avant le déficit n'est pas renuméroté : il relève de la correction et de l'avertissement déjà documentés.

## Non vérifiable avec les pièces fournies

- Quelle référence normative propre aux déficits LMNP prescrit expressément l'ordre FIFO, au-delà de son intérêt démontré pour préserver les millésimes proches de la péremption ?
- Quels autres revenus du foyer et quelles recettes des autres locations permettraient de qualifier effectivement le contribuable LMP ou LMNP dans le scénario J-04 ?
- Le service de déclaration préremplit-il et conserve-t-il les déficits antérieurs dans le dossier réel du déclarant, et pourrait-il ainsi compenser une omission de l'aide J-01 sans intervention de sa part ?
- Quels justificatifs d'ouverture permettraient de réconcilier les stocks déjà partiellement consommés avant la création du dossier logiciel, notamment ceux utilisés dans la variante de reconstitution par millésime ?
- Quelle procédure garantit l'archivage de la déclaration et de son suivi de déficits **avant** les clôtures ultérieures, afin de disposer d'une pièce historique indépendante de la réédition affectée par J-02 ?
- Quelle procédure empêche une modification injustifiée de la durée versionnée des déficits, et quelle référence légale accompagne effectivement chaque version saisie ?
- Les formulaires et règles de déclaration publiés en 2027 et au-delà conserveront-ils les mêmes correspondances ? La vérification unitaire des cases porte sur le document fourni, revenus 2025, pas sur des formulaires futurs.
- Quel taux et quelle situation fiscale du foyer permettraient de convertir les différences de bases et de déductions mesurées en montant d'impôt ?

## Tableau récapitulatif numéroté

| N° | Constat nouveau | Conséquence exécutée | Gravité |
|---|---|---|---|
| J-01 | Déficits épuisés exclus avant reconstitution de l'ouverture | 1 000 € omis dans l'aide ; jusqu'à 6 000 € dans la variante testée | critique |
| J-02 | Réédition d'un ancien exercice fondée sur le solde courant | 3 000 € d'ouverture disparaissent ; 700 € futurs apparaissent dans le suivi 2025 | majeur |
| J-03 | Trace imprimée de péremption perdue après purge | 1 200 € de perte non expliqués après clôture | majeur |
| J-04 | Seuil LMP non détecté sur FEC rejoué | 5 000 € classés LMNP sans l'alerte de seuil prévue | majeur |
| J-05 | Arrondi au pair et exclusion de 0,50 € | 1 € absent de la case testée | mineur |

**Constats antérieurs confirmés, hors décompte J :** I-01 et I-02, avec respectivement **1 000 € de déduction perdus** et **500 € utilisables indûment après dix ans** dans les séquences exécutées. Les chiffres désignent des bases, stocks ou déductions, jamais un impôt personnel présumé.
