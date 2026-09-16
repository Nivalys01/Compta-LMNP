# Architecture — Compta LMNP

## Arborescence du paquet

```
compta_lmnp/
├── app.py, cli.py              points d'entrée — ce que les lanceurs appellent
├── Compta-LMNP-*.sh/.bat       lanceurs, un par plateforme
├── LISEZ-MOI.md                document d'accueil UNIQUE (installation + fonctions)
├── ARCHITECTURE.md, CHANGELOG.md, LICENSE.txt, VERSION
├── schema.sql, seed_*.sql      schéma et référentiels
├── demo/                       jeu de démonstration anonymisé, PUBLIÉ
├── modules/                    les 26 modules métier
├── tests/                      la suite
└── outils : construire_distribution.py, verifier_depot.py, outils_demo.py…
```

Les modules métier sont regroupés dans `modules/` : à plat, trente-cinq
fichiers Python noyaient `LISEZ-MOI.md` et les lanceurs, c'est-à-dire
exactement ce que l'utilisateur doit trouver en premier. Les points d'entrée
et les fichiers cités par les lanceurs restent à la racine — un lanceur
appelle `app.py` par son nom.

Le paquet n'étant pas installé par pip (distribution par simple
décompression), `app.py` et `cli.py` ajoutent `modules/` au chemin d'import
en tête de fichier, avant le premier import métier. Les modules déplacés
calculent leur `HERE` avec deux `dirname` au lieu d'un : la base, les seeds,
`VERSION`, `reference/` et `demo/` vivent à la racine du paquet, pas à côté
du code.

Document destiné à un développeur expérimenté découvrant le code. Le code
suit le **cycle comptable de la profession** : chaque module correspond à
une étape que connaît tout comptable. Le vocabulaire du code est celui du
métier (français, termes du PCG et de la DGFiP).

## Le cycle, module par module

```
    saisie ──► écritures ──► contrôles ──► clôture ──► liasse ──► FEC
  (gabarits)  (guichet)    (pré-clôture)  (fiscal)   (CERFA)   (A47 A-1)
```

| Étape métier | Module | Rôle |
|---|---|---|
| Plan de comptes, journaux | `schema.sql`, `seed_referentiel.sql` | Référentiel calqué sur les FEC réels des logiciels du marché (comptes réellement utilisés, pas le PCG intégral). |
| Saisie par fait métier | `operations.py` + `gabarits.py` | L'utilisateur saisit « un loyer », « une assurance » ; le gabarit impose le compte. Contrepartie unique : 108000 (Exploitant) — il n'y a pas de 512 car la trésorerie n'est pas suivie (choix des logiciels du marché). |
| **Guichet unique** | `ecritures.py` | TOUTE écriture passe par `inserer()` : partie double au centime, exercice ouvert, **conformité FEC par construction** (libellé/pièce obligatoires, date dans l'exercice, pas de caractères tabulaires). Transactions `BEGIN IMMEDIATE` + SAVEPOINT (atomicité crash), rejeu borné des collisions de numéro. C'est le module le plus défendu du code : le lire en premier. |
| Import de relevés | `import_bancaire.py` | CSV bancaires (encodages Windows, montants « sales » tolérés), catégorisation par mots-clés. |
| Reprise d'historique | `reprise.py`, `rejeu_fec.py` | `reprise` : balance N-1 → à-nouveaux (AN). `rejeu_fec` : réimport intégral d'un exercice depuis son FEC (migration depuis un autre outil). |
| Amortissements | `amortissement.py` | Linéaire par composants, prorata temporis entrée/sortie, plafond dernière annuité (jamais de VNC négative). Écriture unique DAA à la clôture. |
| Cession d'un bien | `cession.py` | Dotation complémentaire prorata, sortie 675/28x/2x, prix en 775. La PV relève du régime des particuliers : **neutralisée** dans le BIC (cf. fiscal). |
| Contrôles pré-clôture | `controles.py`, `audit_cycle.py` | Philosophie « Observations » (comme le fait un cabinet) : les anomalies non structurelles sont DÉTECTÉES avant clôture, pas rejetées à la saisie. `audit_cycle` injecte des anomalies volontaires pour tester la détection (`verifier_conformite=False`). |
| **Clôture fiscale** | `fiscal.py` | Le cœur fiscal : limitation 39 C (plafond = loyers acquis − charges **afférentes au bien**, table `compte_hors_plafond_39c`), ventilation du stock par bien (ligne G' à la cession), déficits LMNP FIFO 10 ans, neutralisation des cessions, retraitements (ALUR). Statut d'exercice = verrou : un exercice clos est scellé. |
| Règles versionnées | `parametres.py` | Les règles fiscales datées (activation par année) — jamais de constante fiscale en dur ailleurs. |
| Liasse | `liasse.py`, `liasse_pdf.py` | 2031/2033-A/B/C + suivis, conventions des offres payantes (résultat LMNP hors ligne 352, déclaré au 2031 bis). Le PDF échappe TOUTE donnée utilisateur (`_xml`). |
| **FEC** | `export_fec.py`, `valider_fec.py`, `fec_io.py` (lecture commune) | Export A47 A-1 (CRLF, UTF-8 sans BOM, virgule décimale — conventions des FEC réellement acceptés) et validateur indépendant, plus strict que Test Compta Demat sur certains points. |
| Pérennité | `perennite.py` | Sauvegardes quotidiennes + rotation, archivage FEC horodaté + manifeste SHA-256, restauration avec intégrité vérifiée AVANT écrasement. |
| Rappels | `pense_bete.py` | Démarches manuelles (déclarer, payer, INPI) croisant calendrier × état du dossier. |
| Interfaces | `app.py` (routes web), `pages.py` (gabarits HTML), `cli.py` | Flask local (127.0.0.1, HTTPS auto-signé), multi-dossiers (`dossiers.py`), bac à sable. |

## Les invariants à ne jamais casser

1. **Conformité par construction** : toute écriture acceptée par le guichet
   produit un FEC conforme (`tests/test_rapprochement_fec.py`, fuzz inclus).
2. **Le test en or** (`tests/test_or_liasses_reelles.py`) : les 3 exercices réels
   2023-2025 rejoués doivent reproduire À L'EURO chaque montant des liasses
   réellement télétransmises. Toute dérive du moteur fiscal fait échouer la
   suite. Ne JAMAIS ajuster les cibles pour « faire passer » un changement.
3. **Σ ventilation par bien = suivi global**, au centime, à chaque clôture.
3 bis. **Prorata temporis en JOURS RÉELS** (base 365, jour de mise en
   service ou de cession inclus) : convention établie empiriquement contre
   les 13 composants de la liasse 2025 réelle. Un prorata au mois
   surévalue une entrée de fin de mois — risque de redressement. Verrouillé
   par `test_or_liasses_reelles.py::test_cumul_amortissement_conforme_liasse`.
4. **Clôture atomique** : un commit unique final ; `inserer(commit=False)`
   ne committe jamais (piège RELEASE-SAVEPOINT documenté dans le code).
5. **Règle des règles** : ne coder que des comportements **vérifiés sur des
   documents réels acceptés par l'administration** (FEC, liasses), jamais
   des principes théoriques (deux faux positifs évités : montants négatifs
   des à-nouveaux, CRLF).

## Choix assumés (à connaître avant de « corriger »)

- Pas de comptes de trésorerie (512) : contrepartie exploitant 108000
  partout, comme le fait un cabinet. Le relevé bancaire n'est pas rapproché.
- Migrations de schéma « à la volée » (`CREATE TABLE IF NOT EXISTS`,
  `ALTER TABLE` sous try/except) : chaque fonctionnalité s'active sur une
  base existante sans procédure. À consolider en vraies migrations
  versionnées au jalon J9 (packaging/mise à jour).
- Templates HTML inline dans `app.py` : assumé pour la distribution
  mono-fichier, mais voir Dette ci-dessous.

## Dette technique — état

1. ~~`app.py` mêlait 1 300 lignes de HTML à la logique~~ **soldée (v8.6.0)** :
   les gabarits vivent dans `pages.py` (présentation pure, zéro logique),
   `app.py` ne contient plus que les routes. Le chiffre annoncé ici
   (« ~1 200 l. ») était périmé de moitié — voir plus bas, les compteurs
   ne sont plus recopiés à la main.
2. ~~Trois parseurs FEC~~ **soldée (v8.6.0)** : socle commun `fec_io.py`
   (colonnes A-47 A-1, tokenisation, montants). Les RÈGLES restent chez
   chaque consommateur ; l'écriture (`export_fec`) reste séparée pour que
   le validateur puisse contredire l'export.
3. ~~`audit_cycle._ouvrir_exercice`~~ **soldée (v7.8.0)** :
   `reprise.ouvrir_exercice`, nom public, point d'entrée unique.
4. Les libellés de gabarits et la liste des comptes hors plafond 39 C
   mériteraient une page d'administration (aujourd'hui : base uniquement).
5. **Cycles d'imports et grandes unités** — ouverte, constat T-07.
   `fiscal ↔ controles` et `init_db ↔ perennite` s'importent mutuellement ;
   les imports différés évitent le plantage au chargement mais ne
   suppriment pas le couplage. `generer_pdf` et `valider` dépassent
   chacune 290 lignes. Direction retenue si le sujet est repris : extraire
   les calculs purs partagés dans un module sans dépendance au service de
   clôture, décomposer le PDF par sections et le validateur par phases,
   avec les mêmes tests de sortie. **L'indépendance du validateur
   vis-à-vis de l'exportateur doit être préservée** : mutualiser leurs
   décisions créerait un angle mort commun. Non entrepris à ce jour —
   c'est un chantier de refonte, pas un correctif.
6. **Configuration globale** — ouverte, constat T-07. Les chemins, le
   journal et les états de migration sont des variables de module ; les
   tests passent donc par des substitutions globales. Un
   `create_app(config)` et un contexte de dossier injecté lèveraient la
   contrainte. Même remarque : chantier, pas correctif.

## Par où commencer une modification

- Une règle fiscale change → `parametres.py` (règle datée) + `fiscal.py`,
  puis vérifier que le test en or reste vert (si les liasses réelles
  d'origine restent sous l'ancienne règle, il DOIT rester vert).
- Un nouveau type d'opération → `gabarits.py` uniquement (compte, nature,
  périodicité, éventuel `retraitement`).
- Un nouveau contrôle pré-clôture → `controles.py` (fonction `c_*`
  retournant des `Anomalie`), + injection de test dans `audit_cycle.py`.
- Toute écriture nouvelle → passer par `ecritures.inserer`, jamais
  d'INSERT direct dans `ecriture`/`ligne`.

## Suite de tests

Le nombre de tests figurait ici, écrit à la main, et annonçait 279 pour
plus de mille : un compteur recopié se périme en silence, et donne au
mainteneur un modèle mental faux (constat T-09). L'inventaire se demande
désormais à l'outil, qui ne se trompe pas :

```bash
pytest -q --collect-only | tail -1     # nombre de tests
ruff check .                           # doit rester vierge
```

`pytest -q` (~10 s). Familles notables : test en or (`test_or_liasses_reelles`),
rapprochement guichet↔FEC (`test_rapprochement_fec`), fiabilité
crash/concurrence/restauration (`test_fiabilite`), stress moteur
(`test_stress_compta`), web+FEC (`test_stress_web_fec`), 39 C par bien,
cession, pense-bête. `ruff check .` doit rester vierge (testé par
`test_qualite`).
