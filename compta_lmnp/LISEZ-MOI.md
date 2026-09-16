# Compta LMNP

**© 2026 Sylvain FAURE et les contributeurs — logiciel libre sous licence
[AGPL-3.0-or-later](../LICENSE).** Utilisez-le, copiez-le, modifiez-le,
redistribuez-le, vendez-le si vous voulez : la seule contrepartie est que
toute version diffusée — y compris exposée comme service en ligne — le soit
sous la même licence, code source compris. Fourni sans garantie : les états
produits (liasse, FEC) sont des aides à la préparation, à faire valider avant
tout dépôt.

Logiciel de comptabilité LMNP au réel destiné à **remplacer les logiciels du marché**, testé
contre les chiffres réels de clôture 2023-2025 (au centime).

> **Document unique.** `README.md` et `LISEZ-MOI.md` disaient chacun une
> moitié de la même chose, et se renvoyaient l'un à l'autre. Ils sont
> fusionnés ici : installation d'abord, puis ce que le logiciel fait et
> comment il est construit. Une consigne recopiée dans deux fichiers finit
> par diverger — c'était déjà arrivé, le README annonçant encore un
> démarrage HTTPS abandonné depuis la v8.15.0.

---

# Installation et mise à jour

## Installation (première fois)

### 1. Installer Python (une seule fois)

Le logiciel a besoin de **Python 3.12 ou plus récent**. Vérifiez d'abord
s'il est déjà là : ouvrez un terminal (ou l'invite de commandes) et tapez
`python3 --version` — si un numéro s'affiche, passez à l'étape 2.

| Système | Où le prendre |
|---|---|
| **Windows** | [python.org/downloads/windows](https://www.python.org/downloads/windows/) — prenez le « Windows installer (64-bit) ». **Cochez impérativement « Add python.exe to PATH »** sur le premier écran de l'installateur : sans cette case, le lanceur ne trouvera pas Python. |
| **macOS** | [python.org/downloads/macos](https://www.python.org/downloads/macos/), ou bien `xcode-select --install` dans le Terminal. |
| **Debian, Ubuntu, Mint** | `sudo apt install python3 python3-venv` |
| **Fedora, RHEL, Bazzite** | `sudo dnf install python3` |
| **Arch, Manjaro** | `sudo pacman -S python` |
| **openSUSE** | `sudo zypper install python3` |

> Si vous utilisez une version de Python **très récente** (sortie il y a
> moins de quelques mois) et que l'installation échoue, prenez la version
> précédente : certaines dépendances mettent du temps à s'y adapter.

### 2. Décompresser le logiciel

Décompressez le zip où vous voulez, par exemple `Documents/compta_lmnp`.
**Évitez un dossier synchronisé** (OneDrive, Google Drive, Dropbox) : une
synchronisation déclenchée pendant une écriture peut corrompre la base.

### 3. Lancer

| Système | Comment |
|---|---|
| **Windows** | Double-cliquez `Compta-LMNP-Windows.bat`. Un raccourci « Compta LMNP » est créé sur le Bureau au premier lancement. |
| **Linux** | Dans un terminal, **placez-vous d'abord dans le dossier**, puis lancez (voir ci-dessous). Le double-clic ouvre souvent le fichier dans un éditeur au lieu de l'exécuter. |
| **macOS** | Idem : `cd` dans le dossier, puis `bash Compta-LMNP-Linux-macOS.sh`. Ensuite, `bash Compta-LMNP-Linux-macOS.sh --raccourci` crée un « Compta LMNP.command » sur le Bureau, double-cliquable. |

**Linux et macOS — les deux commandes, dans l'ordre :**

```
cd ~/Documents/compta_lmnp          ← le dossier où vous avez décompressé
bash Compta-LMNP-Linux-macOS.sh
```

La première ligne est **indispensable** et souvent oubliée : sans elle, le
terminal cherche le fichier là où il se trouve (votre dossier personnel) et
répond « Aucun fichier ou dossier de ce nom ». Astuce : dans la plupart des
gestionnaires de fichiers, un clic droit dans le dossier propose « Ouvrir un
terminal ici » — le `cd` est alors déjà fait.

Le premier lancement dure **1 à 3 minutes** : le logiciel crée son
environnement local et télécharge Flask. Ne fermez pas la fenêtre. Les
lancements suivants sont immédiats.

L'application s'ouvre sur **http://localhost:5000**. Pas de cadenas dans
la barre d'adresse, et c'est normal : vos données ne quittent pas votre
ordinateur et ne traversent aucun réseau.

### 4. Premier démarrage

Une base **vierge** est créée à côté du logiciel (`compta.db`). Renseignez
l'exploitant (nom, SIREN, adresse d'activité) dans la page
Immobilisations, puis créez votre premier bien.

> **Pour découvrir le logiciel sans rien saisir** : la page *Dossiers*
> propose un **bac à sable** contenant une année de location complète et
> déjà clôturée — écritures, liasse, FEC. Vous pouvez tout y essayer sans
> aucun risque pour vos données.

### Options du lanceur

| Option | Effet |
|---|---|
| `--verifier` | contrôle l'environnement sans rien lancer |
| `--raccourci` | installe une entrée dans le menu (Linux) ou sur le Bureau (macOS) |
| `--https` | active HTTPS (certificat auto-signé : le navigateur affichera un avertissement — inutile en local) |

### Messages Windows au premier lancement (normaux)

- **SmartScreen** (« Windows a protégé votre ordinateur ») : le lanceur
  n'est pas signé numériquement. Cliquez « Informations complémentaires »
  puis « Exécuter quand même ».
- **Pare-feu** : autorisez l'accès « réseaux privés ». Le logiciel n'écoute
  que sur votre machine (127.0.0.1) — rien n'est accessible de l'extérieur
  ni envoyé sur internet.
- **Certificat du navigateur** : la connexion locale est chiffrée avec un
  certificat auto-signé ; acceptez l'avertissement (Avancé → Continuer).

## Mise à jour (installation existante)

Le code se remplace, **les données restent** :

1. Fermez le logiciel.
2. (Ceinture et bretelles) copiez le dossier `sauvegardes/` ailleurs.
3. Décompressez la nouvelle version PAR-DESSUS l'ancienne (remplacez les
   fichiers). Vos données ne sont pas dans le code : `compta.db`,
   `dossiers/`, `dossiers.json`, `sauvegardes/` et `archives/` ne sont pas
   touchés.
4. Relancez. Au démarrage, chaque dossier est automatiquement mis au
   niveau (migrations versionnées) **après une copie de sûreté
   « avant-migration »** — visible dans la page Dossiers, section
   Sauvegardes, restaurable en un clic.

Ne JAMAIS ouvrir un dossier avec une version plus ancienne que celle qui
l'a mis à jour : le logiciel le refuse de lui-même avec un message clair
(aucune donnée modifiée) — installez simplement la dernière version.

## Où sont mes données ?

Tout est local, dans le dossier du logiciel : `compta.db` (dossier
principal), `dossiers/<nom>/compta.db` (autres dossiers), `sauvegardes/`
(une par jour + avant chaque clôture/migration/restauration), `archives/`
(FEC de chaque clôture, empreinte SHA-256 au manifeste). Pour un
déménagement complet : copier tout le dossier du logiciel suffit.


## Exécutable autonome Windows : retiré

Un script `construire_exe.py` fabriquait un exécutable PyInstaller, pour que
l'utilisateur n'ait plus rien à installer. **Il est retiré du périmètre**, et
il vaut mieux dire pourquoi que laisser croire à une option disponible.

Il était cassé, et personne ne l'avait vu parce qu'il ne se construit que sur
Windows, là où la suite de tests ne tourne pas : il n'embarquait que
`schema.sql` — ni `seed_referentiel.sql`, ni `seed_demo.sql` — et ne gérait
pas `sys._MEIPASS`, le chemin sous lequel PyInstaller dépose les données
embarquées. Autrement dit, l'exécutable produit ne pouvait pas initialiser sa
base. Il embarquait par ailleurs Flask et reportlab **sans leurs notices
BSD**, ce qui en faisait une redistribution binaire non conforme (voir
`NOTICES-TIERS.md`).

Deux défauts dont aucun n'est difficile à corriger ; mais les corriger sans
pouvoir exécuter le résultat reviendrait à valider par lecture ce que seule
l'exécution établit — exactement ce que ce projet s'interdit ailleurs. Le
jour où une machine Windows sera disponible pour l'éprouver, le script
reviendra.

En attendant, l'installation passe par les lanceurs `.bat` / `.sh`, qui sont
éprouvés en conditions réelles. Ce qu'on perd : l'utilisateur doit installer
Python une fois. Ce qu'on ne perd pas : SmartScreen bloquait de toute façon
un exécutable non signé — et une signature de code est un certificat payant,
à renouveler, hors de portée d'un logiciel gratuit.


## Linux : pourquoi un double-clic ne lance rien

Sur la plupart des bureaux Linux (GNOME, KDE…), **double-cliquer sur un
fichier `.sh` l'ouvre dans un éditeur de texte au lieu de l'exécuter**.
C'est un choix de sécurité du système, pas un défaut du logiciel : vous
voyez alors le code s'afficher, et rien ne démarre.

Trois façons de lancer, de la plus sûre à la plus pratique :

**1. Par le terminal (fonctionne toujours)**
```
cd /chemin/vers/compta_lmnp
bash Compta-LMNP-Linux-macOS.sh
```
Si rien n'apparaît alors que vous avez double-cliqué, regardez
`logs/demarrage.log` : le logiciel y écrit pourquoi il n'a pas pu ouvrir de
fenêtre, et la commande exacte à taper. **L'application a probablement
démarré quand même** — essayez `http://localhost:5000` dans votre
navigateur avant toute chose.
La forme `bash <fichier>` est la plus robuste : elle fonctionne même si le
droit d'exécution a été perdu à la décompression, ce qui arrive avec
certains gestionnaires d'archives.

**2. En rendant le fichier exécutable, une fois pour toutes**
```
chmod +x Compta-LMNP-Linux-macOS.sh
./Compta-LMNP-Linux-macOS.sh
```
Certains gestionnaires de fichiers proposent ensuite « Exécuter » ou
« Lancer dans un terminal » au clic droit.

**3. Par le raccourci fourni**
Le fichier `Compta-LMNP.desktop` sert de lanceur graphique. Selon le
bureau, il faut d'abord l'autoriser : clic droit → *Autoriser le
lancement* (GNOME), ou lui donner le droit d'exécution. Vous pouvez le
copier sur votre bureau ou dans `~/.local/share/applications/` pour le
retrouver dans le menu des applications.

> **Un seul fichier `.sh` est livré** — celui qui porte le nom du logiciel.
> S'il y en avait deux, ce serait une erreur d'empaquetage.

---

# Ce que fait le logiciel

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
| `tests/` | — | 1 150 tests de non-régression |
| `reference/` | — | FEC 2025 réel, utilisé comme source de reprise et fixture de test |

### Deux modes d'amorçage

- **blanc** — référentiel générique seul (4 journaux + plan de comptes), un exercice
  ouvert, **aucune donnée personnelle**. C'est le mode livré dans le paquet client.
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
  les logiciels du marché : ligne 352 ramenée à 0, le résultat LMNP étant déclaré en 2031 bis ;
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
   les logiciels du marché (mentions « N° Interchange » et « Acceptée le » des anciennes
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
- **Phase 4 de l'audit** — décrire l'année de reprise interne ; ajouter un
  scénario multi-biens.
- **Contrôles** — poursuivre l'enrichissement (32 en place : plausibilité
  vs N-1, périodicité, dotation/plan, seuil LMP versionné…) ; pistes
  suivantes : rapprochement bancaire ligne à ligne, contrôles multi-biens.
- **Migrations** — remplacer la recréation de base par des migrations versionnées.
- **Correspondance des plans comptables** — sur un FEC de cabinet, la case 243
  « dont CFE et CVAE » reste vide, faute de préfixe distinguant la CET des
  autres impôts directs. Limite connue, figée par un test.

Fait : J0 (reprise FEC + reprise interne), J1 (socle), J2 (saisie + import + acquisitions), J3 (export + validateur),
J4 (amortissement), J5 (39 C + déficits), J6 (liasse 2031/2033), moteur de contrôles,
bac à sable + audit automatique (5 phases), réglementation versionnée,
gabarits extensibles (37), HTTPS local, modes blanc/demo.

> ⚠️ **Le fiscal (J4/J5) doit être validé par un expert-comptable avant tout usage
> en déclaration réelle** — surtout durées d'amortissement, ventilation terrain/bâti,
> retraitements (fonds ALUR…) et limitation 39 C.

## Licence

Logiciel **libre**, sous **AGPL-3.0-or-later** — texte intégral dans
[`LICENSE`](../LICENSE), résumé en français courant dans le
[`README.md`](../README.md) du dépôt. Vous pouvez l'utiliser, le modifier, le
forker, le redistribuer et le vendre ; toute version diffusée, y compris un
service en ligne accessible à des tiers, doit l'être sous la même licence avec
son code source.

En France, la protection par le droit d'auteur est automatique dès la création
(aucune formalité requise) ; le dépôt (APP, enveloppe Soleau INPI, commits git
horodatés) ne sert qu'à prouver l'antériorité. Placer le code sous licence
libre ne cède **pas** le droit d'auteur : l'auteur reste titulaire, il concède
des droits d'usage.

**Dépendances.** Contrairement à ce que ce document a longtemps affirmé, le
logiciel n'utilise pas que la bibliothèque standard : **Flask** est une
dépendance d'exécution obligatoire, et **reportlab** une dépendance
facultative (export PDF). Toutes deux sont sous licence permissive (BSD),
compatibles avec l'AGPL — le détail et les obligations qui en découlent sont
dans [`NOTICES-TIERS.md`](../NOTICES-TIERS.md). L'affirmation « uniquement la
bibliothèque standard » était fausse depuis l'introduction de la couche web,
et c'est précisément le genre de phrase qu'on ne relit plus une fois écrite.

**Dons.** Le développement est soutenu par des dons volontaires (encart sur la
page d'accueil). Un don ne confère aucun droit supplémentaire : tout est déjà
ouvert, il n'y a pas de version payante.

**Contribuer** : voir [`CONTRIBUTING.md`](../CONTRIBUTING.md) — commits signés
(DCO), aucune donnée réelle, un test de non-régression par correctif.
