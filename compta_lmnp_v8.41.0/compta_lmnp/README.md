# Compta LMNP

**© 2026 Sylvain FAURE — tous droits réservés.** Logiciel **gratuit** :
utilisez-le sans limite pour votre comptabilité, partagez le paquet officiel
intact. La vente, la modification diffusée et la réutilisation du code dans
un autre produit sont interdites — détail dans `LICENSE.txt`. Fourni sans
garantie : les états produits (liasse, FEC) sont des aides à la préparation,
à faire valider avant tout dépôt.

Logiciel de comptabilité LMNP au réel destiné à **remplacer les acteurs payants actuels**, testé
contre les chiffres réels de clôture 2023-2025 (au centime).

## Installation et lancement

**→ Tout est dans [LISEZ-MOI.md](LISEZ-MOI.md)** : première installation
sur Windows, Linux et macOS, mise à jour d'une installation existante,
dépannage du lancement, emplacement de vos données.

Ce document-ci décrit ce que fait le logiciel et comment il est construit.
La marche à suivre pour l'installer n'est écrite qu'à UN seul endroit : une
consigne recopiée dans deux fichiers finit par diverger, et c'est ce qui
s'était produit — le README annonçait encore un démarrage en HTTPS
abandonné depuis la v8.15.0.

## Contenu

| Fichier | Jalon | Rôle |
|---------|-------|------|
| `schema.sql` | J1 | Schéma SQLite : cœur comptable + tables fiscales + vue `v_fec` |
| `seed.sql` | J1 | Référentiels : 4 journaux, 22 comptes, 14 composants, stocks fiscaux d'entrée |
| `reprise.py` | J0 | Lit un FEC de clôture → génère l'AN + l'OD d'affectation de l'exercice suivant |
| `gabarits.py` | J2 | Mapping type d'opération → compte / sens / périodicité |
| `operations.py` | J2 | Saisie d'un fait métier → écriture en partie double générée |
| `import_bancaire.py` | J2 | Import relevé CSV + catégorisation assistée par mots-clés |
| `controles.py` | — | Moteur de cohérence pré-clôture (façon « Observations » des offres payantes) |
| `amortissement.py` | J4 | Moteur d'amortissement par composants + écriture OD de dotation |
| `fiscal.py` | J5 | Limitation art. 39 C + déficits LMNP + clôture fiscale |
| `cli.py` | J2/J5 | Interface ligne de commande (init / saisir / importer / controler / cloturer / exporter) |
| `export_fec.py` | J3 | Sérialiseur FEC conforme A47 A-1 (tab / virgule / CRLF / AAAAMMJJ) |
| `valider_fec.py` | J3 | Validateur indépendant (réplique Test Compta Demat) |
| `init_db.py` | — | Orchestrateur : crée la base, applique schéma + seed, lance la reprise |
| `dossiers.py` | J8 | Multi-dossiers : registre des comptabilités indépendantes |
| `perennite.py` | J6 | Sauvegardes automatiques (rotation) + archivage FEC avec empreinte SHA-256 |
| `liasse_pdf.py` | J7 | Export PDF de la liasse (2031, 2033-A/B/C, reports, 2042C-PRO) |
| `tests/` | — | 416 tests de non-régression |
| `reference/` | — | FEC 2025 réel, utilisé comme source de reprise et fixture de test |

### Deux modes d'amorçage

- **blanc** — référentiel générique seul (4 journaux + plan de comptes), un exercice
  ouvert, **aucune donnée personnelle**. C'est le mode à livrer en cas de revente.
- **demo** — référentiel + dossier d'exemple complet (FAURE) + reprise des à-nouveaux
  depuis un FEC. Pour le développement et la démonstration ; **à ne jamais distribuer**
  (données personnelles / RGPD).

Le seed est scindé en conséquence : `seed_referentiel.sql` (générique, livré) et
`seed_exemple.sql` (personnel, démo uniquement).

### CLI (saisie par gabarits + import bancaire)

```bash
python cli.py init                         # initialise la base (reprise 2026)
python cli.py gabarits                     # liste les types d'opération
python cli.py saisir --type loyer --montant 795 --periode 2026-03 --date 2026-03-05
python cli.py importer --csv releve.csv            # propose (ne saisit pas)
python cli.py importer --csv releve.csv --valider  # saisit les propositions
python cli.py controler --annee 2026       # rapport de cohérence pré-clôture
python cli.py cloturer --annee 2026 --retraitements 61   # dotation + 39C + déficits
python cli.py exporter --annee 2026 --out FEC2026.txt
```

On ne saisit jamais un débit/crédit : on déclare un **fait** (un loyer, une
charge…), et le gabarit génère l'écriture équilibrée (contrepartie 108000).
La clôture enchaîne dotation (J4) → limitation 39 C → résultat fiscal → déficits (J5).

## Ce qui est garanti par les tests

- Dossier de démonstration complet : 4 journaux, 22 comptes, 14 composants.
- À-nouveaux équilibrés (chaque écriture **et** l'exercice).
- Actif net du bilan = VNC des immobilisations, au centime.
- Capitaux propres après affectation : le résultat est soldé sur le compte
  de l'exploitant.
- **Deux files fiscales distinctes** : report d'amortissement (art. 39 C) et
  déficits LMNP par millésime (péremption à 10 ans), jamais cumulés.
- Vue `v_fec` : 18 colonnes dans l'ordre A47 A-1, dates AAAAMMJJ.
- **Export FEC conforme** : régénéré depuis la base, repassé au validateur avec succès.
- **Validateur** : accepte les 3 FEC réels ; rejette déséquilibre 1 centime, date
  malformée, décimale en point, séparateur de milliers, débit+crédit sur une ligne,
  colonne obligatoire vide, trou de numérotation, écriture à une seule ligne, en-tête
  ou nombre de champs incorrect.
- **Saisie par opérations** : un fait métier → une écriture équilibrée automatique ;
  type inconnu et montant nul rejetés ; numérotation continue après la reprise.
- **Contrôles de cohérence** (pré-clôture, façon des offres payantes) : doublons, articles « Autres »
  à requalifier, dépenses immobilisables au-dessus du seuil, loyers mensuels manquants,
  sens comptable (charge au crédit / produit au débit), équilibre par écriture (bloquant).
- **Import bancaire** : catégorisation par mots-clés ; l'inconnu tombe en « autres_charges »
  (donc signalé, jamais silencieux) ; le FEC reste conforme après import.
- **Amortissement (J4)** : reproduit au centime les dotations d'une liasse réelle ; prorata
  l'année d'entrée ; plafonnement la dernière année (les meubles 5 ans finissent en 2026,
  dotation 4 984 € < 5 184 €) ; écriture OD de dotation par composant.
- **Fiscal (J5)** : limitation 39 C (report borné à la dotation, y compris plafond négatif),
  déficits LMNP FIFO avec péremption à 10 ans, clôture complète (dotation → 39 C → résultat
  fiscal → déficits), reproduisant l'enchaînement réel du stock 39 C (0 → 297 → 556).

## Conventions reprises des acteurs payants actuels

- 4 journaux seulement (`AN`, `AC`, `BQ`, `OD`), pas de compte 512 : la
  trésorerie passe par le compte courant de l'exploitant **108000**.
- L'à-nouveaux porte le résultat de l'exercice clos sur **120000**, qu'une OD
  d'affectation déverse ensuite sur **108000**.
- `code_immo` des composants = référence de pièce d'origine, conservée comme
  identifiant stable d'immobilisation lors d'une reprise.

## Moteur de contrôles (19 vérifications)

Trois niveaux — BLOQUANT (empêche la clôture), AVERTISSEMENT, INFO — inspirés
des « Observations » des acteurs payants actuels et des anomalies réellement constatées dans les
exercices 2023-2025 :

- **Structurels bloquants** : écriture déséquilibrée, écriture datée hors des
  bornes de l'exercice, compte d'attente 472000 non soldé, opération à
  montant nul ou négatif (import corrompu) ;
- **Qualité de saisie** : doublons, articles « Autres » à requalifier,
  dépense au-dessus du seuil d'immobilisation (règle versionnée par
  millésime), loyers mensuels manquants, sens comptable anormal, charge
  annuelle saisie deux fois (CFE ×2…), période ≠ mois de la date,
  **intérêts d'emprunt mal classés** (libellé « intérêts/emprunt/échéance »
  hors gabarit dédié — le cas réel des exercices 2023-2025) ;
- **Plausibilité & cohérence fiscale** : variation d'un poste > 50 % et
  > 100 € vs N-1 (muet si N-1 migré sans opérations), loyer mensuel
  s'écartant > 15 % de la médiane, **à-nouveaux absents** alors que N-1 est
  clos (bilan faux), dotation comptabilisée ≠ plan d'amortissement,
  recettes > seuil LMP (règle versionnée, art. 155 IV CGI) ;
- **Rappels INFO** : taxe foncière / CFE / assurance absentes malgré des
  loyers, fonds ALUR présent en N-1 mais oublié en N.

## Import bancaire (CSV) et suggestions

`import_bancaire.py` lit un relevé `date;libellé;montant` et propose des
opérations pré-catégorisées — jamais insérées sans validation. Priorité des
suggestions : 1) **l'historique de vos saisies validées** (un libellé déjà
rencontré reprend son type — vos propres écritures sont le meilleur
référentiel) ; 2) mots-clés génériques (syndic, PNO, fibre…) ; 3) sinon
`autres_charges`, donc signalé « à requalifier » par les contrôles :
comportement prudent, aucun classement silencieux. Les libellés
historiquement en fourre-tout ne font pas suggestion. Pour un dossier
mono-bien (~40 écritures/an), ce niveau rules + historique est le bon
compromis : toute la valeur, sans moteur d'apprentissage disproportionné.

## Réglementation versionnée (future-proof)

Le principe : **aucune disposition légale n'est figée dans le code**. Menu
« Réglementation » (ou module `parametres.py`) :

- **Règles fiscales datées** — chaque seuil/durée vit dans la table
  `regle_fiscale` avec sa période de validité et sa référence légale
  (CGI, BOFiP, loi de finances). Quand une LF change une valeur, on
  enregistre une nouvelle version avec sa **date d'effet** : les exercices
  passés restent calculés avec les règles de leur millésime (indispensable
  pour rejouer ou justifier un exercice ancien). Règles livrées : seuil
  d'immobilisation (500 €, BOI-BIC-CHG-20-30-10), report des déficits LMNP
  (10 ans, art. 156 I-1° ter CGI), seuils LMP (23 000 €) et micro-BIC
  (77 700 €), activation de la réintégration ALUR.
- **Catégories d'opérations personnalisées** — table `gabarit_personnalise` :
  une disposition future crée une nouvelle charge/produit ? On l'ajoute par
  formulaire (libellé, compte, nature, périodicité, réintégration fiscale
  éventuelle) et elle apparaît immédiatement dans la saisie, sans toucher au
  code.
- **Plan de comptes extensible** — création de comptes par formulaire pour
  accueillir les gabarits futurs.
- **Retraitements fiscaux automatiques** — les gabarits marqués
  `retraitement: reintegration` (ex. fonds travaux ALUR, provision non
  déductible) sont réintégrés automatiquement à la clôture, comme les
  « divers à réintégrer » des acteurs payants actuels ; désactivable par règle datée.

## Catalogue de saisie (37 gabarits)

Les listes déroulantes couvrent l'intégralité des articles constatés dans les
exercices 2023-2025 (FEC + liasses de référence) et les charges officiellement
déductibles au réel, groupés : **Produits** (loyer, provision, forfait,
régularisation de charges, indemnité d'assurance…), **Copropriété** (charges,
fonds travaux ALUR), **Abonnements & énergie**, **Assurances** (PNO,
emprunteur, GLI), **Entretien & équipement** (réparations, petit équipement,
électroménager, fournitures), **Emprunt & banque** (intérêts d'emprunt en
661100 — charge financière, ligne 294 du 2033-B —, frais de dossier, tenue de
compte), **Honoraires & gestion** (comptabilité, OGA, gestion locative,
juridique, frais d'acquisition option charges, annonces, cotisations, frais
postaux), **Déplacements** (carburant, péage/parking, voyages), **Impôts &
taxes** (CFE, taxe foncière, TEOM), **Divers** (autres charges, à
requalifier). Le plan de comptes passe à 33 comptes (dont les 606100, 606200
et 625100 présents dans le FEC 2023 mais absents jusqu'ici).

## Appels de charges de copropriété (ventilation)

Un appel du syndic mélange plusieurs composantes fiscales. L'assistant de
ventilation (page Saisie, ou `operations.saisir_appel_charges`) éclate un
appel en une fois, écritures rattachées à la même pièce `APPEL AAAA-MM` :

- **Charges courantes** (614100) — déductibles en totalité, **y compris la
  quote-part récupérable sur le locataire** : en BIC les provisions
  encaissées du locataire sont imposées en produits (708810), la déduction
  est donc symétrique (conventions des offres payantes ; à la différence des revenus
  fonciers 2044 où les charges récupérables ne sont pas déductibles) ;
- **Fonds travaux ALUR** (614100) — comptabilisé en charge mais **réintégré
  automatiquement** à la clôture (contribution capitalisée attachée au lot,
  art. 14-2 loi de 1965 : non déductible) ;
- **Travaux hors budget** (615200) — en entretien ; pour de gros travaux
  votés (ravalement, toiture…), préférer une immobilisation amortissable.

La régularisation annuelle du syndic (arrêté des comptes) se saisit avec les
gabarits existants : solde débiteur → « Charges de copropriété », solde
créditeur reversé/refacturé au locataire → « Régularisation de charges
locatives » (produit). Le détail récupérable / non récupérable (décret
87-713) n'est pas suivi ligne à ligne : il ne sert qu'à la régularisation
avec le locataire, pas au calcul fiscal.

## Reprise interne des à-nouveaux (cycle pluri-annuel autonome)

L'ouverture d'un exercice ne dépend plus d'un FEC externe : quand l'exercice
précédent est **clos**, cochez « Reprendre les à-nouveaux » dans « Nouvel
exercice » (ou appelez `reprise.construire_an_interne(conn, annee)`). Le
logiciel lit la balance de clôture directement dans la base et génère l'AN +
l'OD d'affectation du résultat, exactement comme la reprise FEC — équivalence
vérifiée **au centime** par les tests sur le FEC 2025 réel.

Garde-fous : exercice précédent absent ou non clôturé → refus ; AN déjà
présents → refus ; AN déséquilibrés → reprise annulée.

La création d'un composant via l'interface génère désormais **l'écriture
d'acquisition** (débit 2xx / crédit 108000), sans laquelle le bilan et le FEC
seraient faux. Une case « ne pas générer l'écriture » couvre la reprise d'un
historique déjà porté par les à-nouveaux.

## Liasse fiscale (modèle des acteurs payants actuels)

Menu « Liasse » (imprimable → PDF via le navigateur) ou `liasse.generer(conn,
annee)`. Contenu, alimenté depuis la base :

- **Page de garde** : CA HT, résultat fiscal, déficit LMNP, revenu imposable,
  restant à imputer (39 C + déficits) ;
- **2031-SD** (résultat fiscal 0 ; BIC non professionnels 7a/7b) et
  **2031 bis** ;
- **2033-A** bilan simplifié (immobilisations, amortissements, capital
  individuel, résultat) ;
- **2033-B** compte de résultat + réintégrations/déductions détaillées
  (art. 39 C ligne 318, divers ligne 330, déductions ligne 350) — convention
  les acteurs payants actuels : ligne 352 ramenée à 0, le résultat LMNP étant déclaré en 2031 bis ;
- **2033-C** immobilisations & amortissements par rubrique CERFA
  (420/430/450/470, 510-560) + détail par composant ;
- **Suivi des reports** : 39 C (SUIV39C) et déficits LMNP par millésime avec
  péremption ;
- **Aide 2042C-PRO** : cases 5NA/5NY et 5GA→5GJ (déficits antérieurs par
  millésime, 5GJ = N-1 … 5GA = N-10) pré-calculées et arrondies à l'euro.

Chaque liasse embarque ses **contrôles de cohérence** (actif = passif,
ligne 352 = 0, totaux 2033-C = bilan, résultat fiscal = clôture). Le dossier
démo réconcilie au centime le bilan d'ouverture repris d'un prestataire. Sur exercice ouvert, la liasse s'affiche en mode
« provisoire ». Télétransmission EDI-TDFC non incluse : la liasse sert de
support de contrôle et de report manuel (ou de dépôt papier/expert).

## Bac à sable & audit du cycle complet

Le **bac à sable** est un dossier comptable jetable (`bac_a_sable.db`),
totalement isolé de la comptabilité réelle. Depuis le menu « Bac à sable »
de l'interface web :

- **Entrer / quitter** le bac à sable (bandeau orange permanent tant qu'on y est ;
  tous les menus — saisie, immobilisations, clôture, nouvel exercice — opèrent
  alors sur le dossier d'essai) ;
- **Réinitialiser** en un clic : dossier vierge (mode blanc) ou dossier
  d'exemple (mode démo) ;
- **Lancer l'audit automatique** : rejoue tout le processus sur une base
  jetable et vérifie chaque étape.

L'audit est aussi lançable en ligne de commande — idéal pour valider la
version en développement à tout moment (ou dans une CI) :

```bash
python audit_cycle.py            # rapport texte, code retour 0/1
python audit_cycle.py --json     # sortie machine
python audit_cycle.py --garder   # conserve la base d'audit pour inspection
```

Cinq phases, 41 vérifications :

1. **Cycle nominal** — init blanc → exploitant/bien/composants → ouverture
   d'exercice → 12 loyers + 5 charges → contrôles (0 bloquant) → clôture
   (dotation exacte, résultat comptable/fiscal, 39 C) → export FEC → validation
   croisée du FEC.
2. **Détection d'anomalies** — injection volontaire de : doublon, « Autres
   charges » à requalifier, dépense > seuil d'immobilisation, loyer manquant,
   écriture déséquilibrée (bloquant), charge au crédit — le moteur de contrôles
   doit toutes les détecter.
3. **Fiscal pluri-exercices** — exercice à plafond 39 C insuffisant (report
   créé, résultat fiscal ramené à 0, files 39 C / déficits jamais cumulées),
   puis exercice bénéficiaire (consommation FIFO du stock 39 C).

## Qualité du code (audit v6)

Un audit complet du code a été mené, suivi d'un refactoring dont la
**neutralité comptable est prouvée** : sur un scénario de référence complet
(dossier, saisies, ventilation copro, intérêts, clôture), le FEC généré avant
et après refactoring est **identique octet par octet** et la liasse identique
au centime.

- **`ecritures.py`** — point de passage UNIQUE pour toute insertion
  d'écriture (saisie, acquisitions, à-nouveaux, affectation du résultat,
  dotation, injections d'audit) : numérotation séquentielle, PieceDate /
  ValidDate alignées, équilibre vérifié avant insertion. Un test
  d'architecture interdit toute insertion SQL brute hors de ce module.
- **Effets de bord supprimés** — plus aucune fonction ne mute le
  `row_factory` de la connexion de l'appelant (lectures nommées isolées).
- **Lint** — le dépôt passe `ruff check .` sans erreur (imports morts,
  variables inutilisées, style) ; configuration dans `pyproject.toml`
  (E402 toléré et documenté : imports locaux après l'amorçage `sys.path`).
  Un test exécute ruff pour que le dépôt reste propre.
- **Nettoyages** — imports remontés en tête de modules, code mort supprimé
  (`_prochain_num`), `seuil_immo` devenu simple drapeau (la valeur appliquée
  est la règle versionnée), normalisation FEC de l'audit simplifiée.

## Duplication d'écritures (→ M+1)

Chaque ligne du tableau des opérations porte un bouton **« → M+1 »** qui
réplique l'opération au mois suivant : même nature, même montant, même tiers,
date et période décalées d'un mois (jour borné à la fin du mois : 31/01 →
28-29/02). Le geste type : saisir le loyer de janvier puis enchaîner onze
clics. Garde-fous : libellé personnalisé conservé, nouvelle pièce (pas de
recopie de référence), refus explicite si l'exercice cible n'existe pas
encore ou est clos, et la date décalée ne déclenche pas le contrôle DOUBLON.

## Pérennité pluri-annuelle (vérifiée)

Le cycle « clôture N → ouverture N+1 avec reprise interne » est conçu pour
s'enchaîner indéfiniment. Un test d'endurance déroule **12 exercices
consécutifs** et vérifie chaque année : à-nouveaux équilibrés, compte 120000
soldé après affectation, liasse conforme (5 contrôles), dotation jamais
croissante — le mobilier (5 ans) s'éteint à son terme et la dotation retombe
au seul bâti —, **péremption des déficits** (un millésime non imputé est
purgé à origine + 10 ans, règle versionnée), et bilan final exact
(VNC = brut − amortissements cumulés plafonnés). Seule discipline
utilisateur : clôturer N avant d'ouvrir N+1 avec reprise (le logiciel refuse
sinon), et garder à l'esprit la fin de vie des plans d'amortissement — le
levier fiscal s'amenuise mécaniquement avec les années, ce n'est pas un bug.

## Télétransmission de la déclaration de résultats

Le dépôt papier n'est plus admis : la déclaration de résultats (2031 + 2033)
doit être télétransmise (art. 1649 quater B quater CGI). Le logiciel produit
la liasse complète, case par case ; deux voies pour la transmettre :

1. **EFI — saisie en ligne, gratuit (recommandé au réel simplifié)** : espace
   professionnel sur impots.gouv.fr → adhérer une fois au service
   « Déclarer › Résultats » → recopier les cases 2031 / 2033-A / B / C depuis
   la page Liasse. Délai : 2ᵉ jour ouvré suivant le 1ᵉʳ mai, + 15 jours de
   tolérance télédéclaration (EFI-RP comme EDI).
2. **EDI-TDFC — via un partenaire habilité DGFiP** : la voie qu'utilisait
   les acteurs payants actuels (mentions « N° Interchange » et « Acceptée le » des anciennes
   liasses). Des portails de saisie en ligne à bas coût existent — liste
   officielle sur impots.gouv.fr (« Tableau des solutions TDFC directes avec
   saisie en ligne »).

Devenir soi-même partenaire EDI (convention DGFiP, format EDIFACT/INFENT,
certification EDIFICAS) est disproportionné pour un dossier ; une éventuelle
intégration future passerait par l'API d'un partenaire existant. Ne pas
oublier le report final sur la **2042C-PRO** du foyer — cases pré-calculées
par la page Liasse.

## Note sur l'avertissement « development server »

Au démarrage, Flask affichait « This is a development server… ». Cet
avertissement vise les déploiements **publics sur internet** (montée en
charge, durcissement) et ne s'applique pas à un logiciel local
mono-utilisateur : l'application n'écoute que sur 127.0.0.1, n'est jamais
exposée au réseau, et le debug est désactivé. Le message est donc filtré et
remplacé au démarrage par une explication exacte du contexte.

## Prochains jalons

- **Télétransmission EDI-TDFC** — dépôt dématérialisé de la liasse (via
  partenaire EDI) ; en attendant, la liasse sert de support de report.
- **Phase 4 de l'audit** — décrire l'année de reprise interne dans le README
  commercial ; ajouter un scénario multi-biens.
- **Contrôles** — poursuivre l'enrichissement (19 en place : plausibilité
  vs N-1, périodicité, dotation/plan, seuil LMP versionné…) ; pistes
  suivantes : rapprochement bancaire ligne à ligne, contrôles multi-biens.
- **Migrations** — remplacer la recréation de base par des migrations versionnées.

Fait : J0 (reprise FEC + reprise interne), J1 (socle), J2 (saisie + import + acquisitions), J3 (export + validateur),
J4 (amortissement), J5 (39 C + déficits), J6 (liasse 2031/2033), moteur de contrôles,
bac à sable + audit automatique (5 phases), réglementation versionnée,
gabarits extensibles (37), HTTPS local, modes blanc/demo.

> ⚠️ **Le fiscal (J4/J5) doit être validé par un expert-comptable avant tout usage
> en déclaration réelle** — surtout durées d'amortissement, ventilation terrain/bâti,
> retraitements (fonds ALUR…) et limitation 39 C.

## Licence & revente

Logiciel **propriétaire** — voir `LICENSE.txt`. En France, la protection par le
droit d'auteur est automatique dès la création (aucune formalité requise) ; le
dépôt (APP, enveloppe Soleau INPI, commits git horodatés) ne sert qu'à prouver
l'antériorité. Le logiciel n'utilise **que la bibliothèque standard de Python**
(aucune dépendance à licence contaminante). Le logiciel est distribué
GRATUITEMENT ; son développement est soutenu par des dons volontaires
(encart PayPal sur la page d'accueil) — sans contrainte
open-source. Avant toute vente : remplacer `Sylvain FAURE` dans `LICENSE.txt` et les
en-têtes, livrer en **mode blanc** (jamais `seed_exemple.sql`), et faire relire le
contrat de licence par un conseil en propriété intellectuelle.
