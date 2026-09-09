# Revue passe F — chaîne de distribution et protection des données

Périmètre : `construire_distribution.py`, `verifier_depot.py`, `outils_demo.py`.

**Le dossier `revue-passe-F` annoncé n'existe pas** — ni dans le dépôt, ni
ailleurs sur la machine. Les trois fichiers ont été audités **dans l'arbre de
travail, au commit `fa8daca`**. Deux d'entre eux portent des modifications
faites lors de la passe E par l'auteur de ce rapport (`verifier_depot.py` au
commit `4615db4`, `outils_demo.py` au commit `018fbe0`) : l'indépendance de la
revue en souffre sur ces deux fichiers, et c'est signalé ici plutôt que passé
sous silence.

Tous les constats ci-dessous ont été **reproduits par exécution**, sur des
identités **fictives** — aucune donnée réelle n'a été écrite pendant la revue.

---

## 1. Critique

### F-01 — Le contrôle déclare « aucune donnée personnelle » sans avoir rien cherché

**Fichier / fonction** : `verifier_depot.main`, lignes 173-183.

**Scénario** — un dépôt sans le dossier privé : un clone, un runner de CI, un
poste neuf, ou simplement `reference/` déplacé le temps d'un essai. Un fichier
`note.md` à la racine contient une identité.

**Attendu** : le contrôle refuse de conclure. Il ne peut pas chercher des
empreintes qu'il n'a pas pu lire.

**Produit** (sortie réelle) :

```
Fichiers qui seraient publiés : 2
Empreintes du dossier réel recherchées : 0
  (dossier privé absent : contrôle des chemins uniquement)

✓ Aucune donnée personnelle dans ce qui serait publié.
--> code de sortie : 0
```

La réserve est imprimée **avant** le verdict. La dernière ligne — celle qu'on
lit, celle qui reste — est une affirmation positive que le script n'a aucun
moyen de soutenir. Le code de sortie vaut **0**.

**Conséquence** : le seul contrôle de contenu de toute la chaîne rend un feu
vert sur la seule foi des chemins. Un garde-fou qui se tait quand il ne peut
pas travailler est plus dangereux que pas de garde-fou, parce qu'on lui fait
confiance — et celui-ci ne se tait pas : il approuve.

**Gravité : critique.**

**Correctif** : `empreintes_cherchees == 0` doit être une alerte BLOQUANTE, ou
au minimum un code de sortie non nul et un verdict reformulé
(« CONTRÔLE INCOMPLET — empreintes indisponibles »).

---

### F-02 — Même feu vert quand le contrôle ne peut lister aucun fichier

**Fichier / fonction** : `verifier_depot._fichiers_publies` (lignes 124-125)
et `main` (lignes 170-172).

**Scénario** — répertoire sans dépôt git initialisé (ou `git` absent du PATH,
ou `git` en échec pour toute autre raison). Un fichier `fuite.txt` contient
une identité.

**Attendu** : refus de conclure.

**Produit** :

```
Fichiers qui seraient publiés : 0
⚠ Aucun fichier listé : dépôt git non initialisé ici ?
--> code de sortie : 0
--> en mode --json (CI) : code 0
```

`_fichiers_publies` rattrape `CalledProcessError` et `FileNotFoundError` et
rend `[]` — un échec d'outil devient un « rien à signaler ». En mode `--json`,
destiné à la CI, le code de sortie est calculé sur les seules alertes
(ligne 165) : **une CI verte sur un contrôle qui n'a rien examiné.**

**Gravité : critique.**

---

### F-03 — La garde du paquet ne contrôle que des noms, tirés d'une liste fermée

**Fichier / fonction** : `construire_distribution.construire`, garde
anti-fuite lignes 98-105.

La garde compare `INTERDITS` aux noms des fichiers du zip. Or ces fichiers
sont exactement `MODULES_PROD + DOCS + LANCEURS` — une liste écrite à la main,
qui ne contient par construction aucun nom interdit. **La garde vérifie qu'une
liste que l'auteur a lui-même rédigée ne contient pas ce qu'il n'y a pas mis.**

Elle est structurellement incapable de détecter :

- un fichier dont le **nom est autorisé** et le **contenu personnel** ;
- une donnée réelle entrée par un fichier légitime du paquet.

Rien, à aucun moment, ne lit le contenu de ce qui est livré. Le message final
l'affirme pourtant :

```
✓ Paquet client : …zip (288 Ko, 45 fichiers, aucune donnée personnelle)
```

**Gravité : critique** — la phrase est fausse au sens propre : elle énonce un
fait que le programme n'établit jamais.

**Correctif** : appliquer les empreintes de `verifier_depot._empreintes()` au
**contenu** de chaque entrée du zip avant de conclure, et refuser de conclure
si les empreintes sont indisponibles (cf. F-01).

---

### F-04 — La chaîne complète : une anonymisation muette livre l'identité réelle, deux gardes au vert

**Fichiers** : `outils_demo.construire_seed_demo` → `seed_demo.sql` →
`construire_distribution.construire`.

**Scénario reproduit** — `seed_demo.sql` porte une identité réelle, ce qui est
exactement le résultat de F-05 ou F-06. On construit le paquet.

**Produit** (sortie réelle) :

```
✓ Paquet client : …zip (288 Ko, 45 fichiers, aucune donnée personnelle)
  seed_demo.sql EST dans le paquet : True
  identité livrée : INSERT INTO exploitant (nom,siren,adresse) VALUES ('MARTIN CAMILLE','123456789',…
```

`seed_demo.sql` est dans `MODULES_PROD` : il est livré **par construction**,
et son contenu n'est vérifié nulle part. Le jeu de démonstration est le seul
fichier du paquet dérivé des données réelles, et c'est précisément celui que
personne ne relit.

**Conséquence** : trois fichiers présentés comme les gardiens de la frontière
laissent passer le cas central pour lequel ils existent, en imprimant chacun
un message rassurant.

**Gravité : critique.**

---

## 2. Majeur

### F-05 — La liste des termes à masquer, absente, ne fait rien échouer

**Fichier / fonction** : `outils_demo._termes_prives`, lignes 87-88.

```python
if not os.path.exists(FICHIER_TERMES):
    return []
```

**Scénario** : `reference/termes_a_anonymiser.txt` absent, renommé, ou vide.

**Produit** : `[]`. `REMPLACEMENTS_LIBELLE += []` — la génération se poursuit
**sans une seule règle nominative**, et le FEC de démonstration publié
conserve les noms de tiers intacts. Aucune exception, aucun avertissement,
aucun compteur.

**Attendu** : la construction du jeu publié doit refuser de s'exécuter sans la
liste des termes qu'elle est chargée de masquer.

**Gravité : majeur.** C'est la variante « anonymisation » de F-01 : l'outil
travaille avec ce qu'il a, sans dire ce qui lui manque.

---

### F-06 — L'identité n'est pas remplacée si l'`INSERT` s'écarte de la forme attendue

**Fichier / fonction** : `outils_demo.construire_seed_demo`, lignes 224-231.

```python
m = re.search(r"INSERT INTO exploitant[^;]*?VALUES\s*\(([^;]*?)\);", src, re.S)
if m:
    ...
```

Le `if m:` sans `else` : si le motif ne correspond pas, **l'identité réelle
traverse la fonction sans être touchée**, et le fichier est écrit quand même.

**Scénario** (sorties réelles, quatre écritures SQL équivalentes) :

| Forme du seed | Résultat |
|---|---|
| `INSERT INTO exploitant (nom,siren,adresse) VALUES (…)` | remplacé |
| `INSERT INTO "exploitant" (nom,siren) VALUES (…)` | **IDENTITÉ CONSERVÉE** |
| `insert into exploitant (nom,siren) values (…)` | **IDENTITÉ CONSERVÉE** |
| `INSERT OR REPLACE INTO exploitant (nom) VALUES (…)` | **IDENTITÉ CONSERVÉE** |

Trois formes sur quatre passent. Le seed privé est un fichier que l'auteur
édite à la main : sa forme n'est garantie par rien.

**Gravité : majeur.**

---

### F-07 — L'appariement des valeurs de l'`INSERT` est positionnel

**Fichier / fonction** : `outils_demo.construire_seed_demo`, lignes 227-231.

```python
valeurs = re.findall(r"'((?:[^']|'')*)'", m.group(1))
for ancienne, nouvelle in zip(valeurs, [DEMO_NOM, DEMO_SIREN, DEMO_ADRESSE]):
    if len(ancienne) >= 4:
        src = src.replace(...)
```

Les valeurs sont appariées **par position**, sans regarder les colonnes.

**Scénario** — même INSERT, colonnes déclarées `(siren, nom, adresse)` :

```
'123456789'      -> 'MARTIN CAMILLE'
'MARTIN CAMILLE' -> '000000000'
'14 Rue …'       -> '14 Rue Gergovia, 63000 Clermont-Ferrand'
```

Le SIREN reçoit le nom fictif, le nom reçoit le SIREN fictif. Le seed reste
syntaxiquement valide et **paraît anonymisé**. Pire : `if len(ancienne) >= 4`
laisse **intacte** toute valeur de moins de quatre caractères — un code
postal, des initiales, un numéro court.

**Gravité : majeur.**

---

### F-08 — Trois colonnes du FEC anonymisées sur dix-huit

**Fichier / fonction** : `outils_demo.construire_fec_demo`, lignes 201-207.

Sont traitées : `EcritureLib`, `PieceRef`, `CompAuxLib`. Ne le sont pas les
quinze autres, dont :

| Colonne | Ce qu'elle peut porter |
|---|---|
| `CompAuxNum` | le code du compte auxiliaire — souvent le nom du locataire abrégé |
| `CompteLib` | le libellé du compte — « 411 DUPONT » est un usage courant |
| `JournalLib` | libellé de journal personnalisé |
| `Idevise` | rarement, mais non contrôlé |

`CompAuxLib` est anonymisée alors que `CompAuxNum`, son pendant immédiat, ne
l'est pas : la paire est traitée à moitié.

**Attendu** : soit toutes les colonnes textuelles passent par `_anonymiser`,
soit celles qui ne le sont pas font l'objet d'un contrôle après génération
(cf. F-10).

**Gravité : majeur** (dépend du contenu réel du FEC source, non inspecté).

---

### F-09 — La recherche d'empreintes est sensible à la casse, aux accents et aux espaces

**Fichier / fonction** : `verifier_depot.verifier`, ligne 153 — `if valeur in
contenu`.

**Scénario** — empreinte `MARTIN CAMILLE` :

| Forme dans le fichier publié | Détecté |
|---|---|
| `MARTIN CAMILLE` | oui |
| `Martin Camille` | **non** |
| `martin camille` | **non** |
| `MARTIN  CAMILLE` (deux espaces) | **non** |
| `MARTIN\nCAMILLE` (coupé sur deux lignes) | **non** |
| `MARTÍN CAMILLE` | **non** |

**Ironie du code** : le dédoublonnage juste au-dessus (ligne 90) compare
`valeur.lower()`. L'auteur avait la casse en tête ; la comparaison qui compte
ne l'applique pas.

**Gravité : majeur.** Un nom recopié dans une documentation, un commentaire ou
un message de commit ne s'écrit presque jamais avec la casse exacte du seed.

**Correctif** : comparer sur une forme normalisée des deux côtés — minuscules,
accents repliés, espaces multiples réduits — comme le fait déjà
`import_bancaire._norm`.

---

### F-10 — Le jeu de démonstration n'est jamais vérifié après génération

**Fichiers** : `outils_demo.construire_fec_demo` et `construire_seed_demo`.

Les deux fonctions **écrivent puis rendent un chemin**. Aucune relecture,
aucune assertion, aucun contrôle des empreintes sur le fichier produit.

Vérifié : le mot-clé `assert` n'apparaît pas dans `outils_demo.py`, et le seul
`raise` (ligne 320) porte sur l'absence du dossier source. Côté tests, quatre
fichiers mentionnent `FEC_DEMO` ou `seed_demo` : tous vérifient que ces
fichiers sont **sélectionnés**, aucun qu'ils sont **propres**.

Or ces deux fichiers sont les seuls du paquet dérivés des données réelles, et
ils sont écrits **en place, dans l'arbre source**, en écrasant la version
précédente.

**Conséquence** : toute défaillance de F-05 à F-08 se solde par un jeu publié
silencieusement dégradé, que rien ne rattrape avant la publication.

**Gravité : majeur.**

**Correctif** : à la fin de chaque fonction, relire le fichier écrit et y
chercher les empreintes du dossier privé ; en cas de trouvaille, **supprimer
le fichier** et échouer — exactement ce que `construire_distribution` fait
avec son zip (`os.remove(cible)` puis `SystemExit`), qui est le bon réflexe
appliqué au mauvais objet.

---

## 3. Mineur

### F-11 — Le patronyme et le nom de rue figurent en clair dans deux fichiers suivis

`outils_demo.py` lignes 66-67 :

```python
(re.compile(r"(?i)\bfaure\b\s*\w*"), "MARTIN"),
(re.compile(r"(?i)berteaux"), "Gergovia"),
```

`berteaux` est le nom de la rue de l'auteur ; il apparaît aussi dans
`tests/test_usage_reel.py` (2 occurrences). Les deux fichiers sont **suivis
par git**.

Le rapport indique que « l'outil d'anonymisation contenait en clair le nom et
l'adresse qu'il sert à masquer » a été corrigé. La correction a porté sur les
**valeurs complètes** ; les **fragments servant de motifs** sont restés. C'est
donc le résidu d'un constat déjà traité, signalé parce qu'il est encore vivant.

**Et la garde ne le voit pas** : `_empreintes()` construit l'adresse complète
l'adresse **complète**, telle qu'elle figure dans le seed ;
le nom de rue seul n'y correspond pas. Vérifié : `verifier_depot` ne signale pas `outils_demo.py`.

Le patronyme seul, lui, ne peut pas être purgé : il est la mention de
paternité de 73 fichiers. Seul le **nom de rue** est à traiter.

**Gravité : mineur** (dépôt privé aujourd'hui), **majeur le jour d'un passage
en public.**

---

### F-12 — Deux catégories de fichiers échappent en silence au contrôle de contenu

`verifier_depot.verifier`, lignes 146-151.

**Encodage.** `open(..., encoding="utf-8", errors="ignore")` : un fichier
cp1252 — l'encodage d'export des banques françaises — voit ses caractères
accentués **supprimés**. Reproduit :

```
fichier cp1252, empreinte 'MARTÍN CAMILLE'
contenu lu : 'Locataire : MARTN CAMILLE'
empreinte détectée : False
```

**Taille.** Tout fichier de plus de 5 Mo est ignoré sans un mot. Aucun motif
de `CHEMINS_INTERDITS` ne couvre un `.txt` volumineux à la racine — or un
export comptable dépasse facilement cette taille.

**Gravité : mineur** séparément, mais les deux se combinent : un gros export
bancaire en cp1252 traverse le contrôle deux fois.

---

## 4. Ce qui a été vérifié et tenu

1. **Le principe « les empreintes ne sont jamais écrites dans le script » est
   respecté.** `_empreintes()` lit tout depuis `seed_exemple.sql` et
   `reference/`. `outils_demo.construire_seed_demo` fait de même pour
   l'identité. Le raisonnement est juste — c'est son échec silencieux qui pose
   problème (F-01, F-05), pas son principe.
2. **Les motifs de chemin de `verifier_depot` sont corrects et ancrés sur un
   segment**, donc valables à toute profondeur. Vérifié sur huit chemins,
   `demo/FEC_DEMO_2025.txt` correctement épargné.
3. **Le jeu de démonstration actuellement publié est propre.** Recherche de
   `faure`, `berteaux`, `sylvain`, `clermont`, et du terme tiers dans
   `demo/FEC_DEMO_2025.txt` et `seed_demo.sql` : aucune occurrence
   identifiante. Les deux occurrences de `clermont` dans `seed_demo.sql`
   appartiennent à l'adresse **fictive** `DEMO_ADRESSE`.
4. **`construire_distribution` détruit son zip en cas de fuite détectée**
   (`os.remove(cible)` avant `SystemExit`) plutôt que de le laisser sur le
   disque. Le réflexe est bon ; c'est la détection qui manque (F-03).
5. **Les répertoires générés sont couverts par les motifs de chemin** :
   `dist/`, `logs/`, `imports_tmp/`, `sauvegardes/`, `archives/`, `*.db`.
   `git ls-files --others --exclude-standard` respectant le `.gitignore`, ces
   motifs ne servent qu'en filet — ce qui est leur rôle.

---

## 5. Non vérifiable avec les pièces fournies

- **Le contenu réel du FEC source** n'a pas été inspecté : la portée de F-08
  dépend de ce que `CompAuxNum` et `CompteLib` contiennent réellement dans le
  dossier de l'auteur. *Test à faire : extraire les valeurs distinctes de ces
  deux colonnes du FEC de référence et les relire.*
- **`fec_io.lire_brut`** n'a pas été fourni : le comportement de
  `construire_fec_demo` sur un FEC malformé (colonne manquante, ligne courte)
  n'a pas pu être établi. La ligne 195 filtre `len(x) >= len(COLONNES)` — les
  lignes plus courtes sont **écartées en silence**, ce qui mériterait d'être
  regardé.
- **`reprise.lire_balance_fec`**, appelé par `_accorder_composants_au_fec`, lit
  `FEC_DEMO` — donc le fichier de la génération **précédente** si l'ordre
  d'appel change. Non exploré.
- **Le `.gitignore`** n'était pas dans le périmètre : les conclusions sur ce
  que git publierait supposent qu'il est correct, hypothèse que
  `verifier_depot` a précisément pour but de ne pas faire.

---

## Récapitulatif

| # | Constat | Fichier | Gravité |
|---|---|---|---|
| F-01 | Verdict « aucune donnée personnelle » sans aucune empreinte chargée | verifier_depot | Critique |
| F-02 | Même verdict quand aucun fichier n'a pu être listé (CI comprise) | verifier_depot | Critique |
| F-03 | La garde du paquet ne contrôle que des noms d'une liste fermée | construire_distribution | Critique |
| F-04 | Chaîne complète : anonymisation muette → identité livrée → gardes vertes | les trois | Critique |
| F-05 | Liste des termes absente = anonymisation sans règles, en silence | outils_demo | Majeur |
| F-06 | Identité conservée si l'`INSERT` s'écarte de la forme attendue | outils_demo | Majeur |
| F-07 | Appariement positionnel des valeurs ; valeurs courtes ignorées | outils_demo | Majeur |
| F-08 | 3 colonnes FEC anonymisées sur 18 | outils_demo | Majeur |
| F-09 | Recherche sensible à la casse, aux accents, aux espaces | verifier_depot | Majeur |
| F-10 | Aucune vérification du jeu de démonstration après génération | outils_demo | Majeur |
| F-11 | Nom de rue en clair dans deux fichiers suivis, invisible pour la garde | outils_demo, tests | Mineur |
| F-12 | cp1252 et fichiers > 5 Mo ignorés en silence | verifier_depot | Mineur |

**Lecture d'ensemble.** Les trois fichiers ne forment pas une chaîne : ils
forment trois contrôles qui se croisent sans se recouvrir. `outils_demo`
produit sans vérifier. `construire_distribution` vérifie des noms qu'il a
lui-même choisis. `verifier_depot` vérifie du contenu, mais sur le dépôt et
non sur le paquet, et il rend un feu vert dès qu'il ne peut pas travailler.

Le point commun des quatre constats critiques est celui que le prompt
désignait : **aucun ne produit d'erreur.** Chacun se termine par un message
rassurant. Un dossier privé déplacé, un `git` en échec, un `INSERT` reformaté
à la main — trois gestes anodins, aucun signal, et la frontière est franchie.

La correction la plus rentable ne demande pas de réécrire ces fichiers : il
suffit qu'**aucun des trois ne puisse conclure positivement sans avoir
effectivement examiné quelque chose**. Trois conditions d'échec, quelques
lignes chacune — F-01, F-05 et F-03 — referment les quatre critiques.
