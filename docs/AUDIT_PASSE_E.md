# Revue passe E — import bancaire, liasse PDF, plan comptable

Périmètre : `import_bancaire.py`, `liasse_pdf.py`, `seed-referentiel.md`.
Les trois pièces annoncées ont bien été fournies.

Tous les constats ci-dessous ont été **reproduits par exécution** du code joint
(`import_bancaire` sur des CSV construits, `liasse_pdf._table` / `_eur` avec
reportlab 4.4.10). Les valeurs « produit » sont des sorties réelles, pas des
lectures. Ce qui n'a pas pu être vérifié faute de fichier est isolé en §5.

---

## 1. Critique

### E-01 — Tout encaissement non identifié devient un loyer imposable

**Fichier / fonction** : `import_bancaire.categoriser`, ligne
`if montant > 0: return "loyer"`.

**Scénario** — relevé de janvier 2026 comportant quatre encaissements :

| Libellé | Montant | Type proposé |
|---|---|---|
| `VIREMENT DEPOT DE GARANTIE LOCATAIRE` | +700,00 | `loyer` |
| `VIR M DUPONT APPORT` | +5 000,00 | `loyer` |
| `REMB SINISTRE GMF DEGAT DES EAUX` | +800,00 | `loyer` |
| `VIR CAF ALLOCATION LOGEMENT` | +320,00 | `loyer` |

**Attendu** : dépôt de garantie = dette (compte 165), apport = compte de
l'exploitant (108000, qui existe), indemnité d'assurance = produit divers,
APL versée en tiers payant = complément de loyer. Quatre natures, trois
comptes différents.

**Produit** : quatre lignes `{"type": "loyer"}`, soit **6 820 € de recettes
supplémentaires** dont 5 700 € ne sont pas des produits du tout.

**Conséquence pour le déclarant** : CA HT surévalué, résultat fiscal
surévalué du même montant, IR + 17,2 % de prélèvements sociaux sur des
sommes non imposables. Et le jour où le dépôt de garantie est restitué, il
n'a aucun compte d'accueil (cf. E-10) : il repartira en charge.

**Gravité : critique.** C'est le seul cas où l'outil crée de l'impôt qui
n'est pas dû, et rien dans la proposition ne le signale — `autres_charges`
est signalé aux contrôles, `loyer` ne l'est pas.

---

### E-02 — Un export « Date;Libellé;Débit;Crédit » est accepté et inverse tout

**Fichier / fonction** : `import_bancaire.proposer`, test `if len(r) < 3`.

**Scénario** — une seule ligne, format à quatre colonnes (celui du Crédit
Agricole, de la Banque Populaire et de la plupart des exports Excel) :

```
05/01/2026;PRLV SYNDIC;120,50;
```

**Attendu** : refus explicite, comme pour le fichier binaire — le module
documente `date;libelle;montant` et ne sait pas lire une paire débit/crédit.

**Produit** (sortie réelle) :

```python
{'date_operation': '2026-01-05', 'libelle': 'PRLV SYNDIC',
 'montant': 120.5, 'type': 'loyer', 'periode': '2026-01'}
```

`r[2]` est la colonne **débit**, non signée : la charge de copropriété
devient une **recette de loyer** avec une période servie.

**Conséquence** : sur un relevé annuel complet, la totalité des charges est
convertie en produits. Le résultat fiscal est faux du double du total des
charges. Aucun avertissement n'est émis, l'import « réussit ».

**Gravité : critique.** Le test `len(r) < 3` accepte 4, 5 ou 12 colonnes ;
il faut soit exiger exactement 3 colonnes, soit détecter l'en-tête et
demander à l'utilisateur quelle colonne porte le montant.

---

### E-03 — Des lignes entières sont ignorées en silence

**Fichier / fonction** : `import_bancaire.proposer`, bloc
`try: montant = float(...) except ValueError: continue`.

**Scénario** — cinq écritures de charge, une par format rencontré chez les
banques françaises. Sortie réelle de `proposer()` pour chacune :

| Ligne CSV | Propositions |
|---|---|
| `05/01/2026;PRLV SYNDIC;120,50-` | `[]` |
| `05/01/2026;PRLV SYNDIC;(120,50)` | `[]` |
| `05/01/2026;PRLV SYNDIC;-120,50 EUR` | `[]` |
| `05/01/2026;PRLV SYNDIC;-1 234,50 €` | `[]` |
| `05/01/2026<TAB>PRLV SYNDIC<TAB>-120,50` | `[]` |

**Attendu** : ou bien ces formats sont lus (signe suffixe, parenthèses,
devise accolée, tabulation), ou bien la ligne est comptée et restituée à
l'utilisateur (« 47 lignes ignorées »).

**Produit** : liste vide, aucune exception, aucun compteur. Un relevé
entièrement au format « signe suffixe » produit **zéro proposition** et
l'utilisateur conclut que son relevé ne contenait rien.

**Ironie du code** : la docstring de `proposer` justifie longuement le
nettoyage des séparateurs de milliers parce que « sinon la ligne serait
ignorée EN SILENCE, une perte de données invisible ». Le `continue` deux
lignes plus bas fait exactement cela pour quatre autres formats — et le
symbole € que le même bloc laisse passer relève du même cas.

**Conséquence** : import partiel présenté comme complet. Les charges
manquantes ne sont pas déductibles ; à l'inverse, si ce sont des loyers qui
sautent, le déclarant sous-déclare sans le savoir.

**Gravité : critique** (perte de données silencieuse, sur la porte
d'entrée).

**Correctif minimal** : normaliser avant `float()` — retirer `€`, `EUR`,
convertir `(x)` et `x-` en `-x` — et faire renvoyer à `proposer` un compte
des lignes rejetées, affiché au guichet.

---

### E-04 — Le remboursement d'emprunt est classé en « petit équipement »

**Fichier / fonction** : `import_bancaire.categoriser`, règle
`("ikea", "electromenager", "darty", "boulanger", "mobilier")`.

**Scénario** :

```python
categoriser("ECHEANCE PRET IMMOBILIER 001234", -890.0)
```

**Attendu** : aucune règle ne devrait matcher ; à défaut, une nature
« emprunt » ventilant capital (dette) et intérêts (661100).

**Produit** : `'petit_equipement'`. La sous-chaîne `mobilier` est contenue
dans `IMMOBILIER`. Le test `any(k in lib for k in cles)` ne pose aucune
frontière de mot.

Même cause, deux autres cas reproduits :

- `AGENCE IMMOBILIERE HONORAIRES GESTION`, −65,00 → `petit_equipement`
- `VIR RECU PARENTS AIDE`, −300,00 → `loyer` (`rent` ⊂ `PARENTS`, et la
  règle `loyer` s'applique aux **décaissements** puisque les encaissements
  sortent avant — voir E-01)

**Conséquence pour le déclarant** : 10 680 € de mensualités sur l'année
passés en charge de petit équipement. Le capital remboursé n'est pas
déductible : c'est le redressement le plus classique en LMNP au réel, et
ici il est produit automatiquement, sur la ligne la plus grosse du relevé.
Accessoirement, un décaissement libellé « loyer » devient un produit.

**Gravité : critique.**

**Correctif** : matcher sur des mots délimités (`\b…\b`) et non des
sous-chaînes ; ajouter une règle `pret|emprunt|echeance` qui ne propose
rien mais bascule en compte d'attente (cf. E-06).

---

## 2. Majeur

### E-05 — Le sens du montant n'est jamais confronté à la nature retenue

**Fichier / fonction** : `import_bancaire.categoriser`, ordre des trois
branches (historique, puis signe, puis mots-clés).

**Scénario** — l'historique contient une saisie validée
`('assurance', 'PRLV GMF PNO', 'saisie')`. L'assureur rembourse un sinistre
sous le même libellé :

```python
categoriser("PRLV GMF PNO", +800.0, conn)   # -> 'assurance'
```

**Attendu** : un encaissement ne peut pas prendre une nature de charge. Le
guichet impose des montants strictement positifs et une nature qui porte le
sens ; c'est donc à l'import de vérifier la cohérence signe ↔ nature, car
plus rien en aval ne dispose de l'information de signe (`round(abs(montant), 2)`
la détruit).

**Produit** : `'assurance'` — un produit de 800 € enregistré en charge
déductible. Symétriquement (E-04), un décaissement peut ressortir en
`loyer`.

**Conséquence** : double erreur sur le résultat — recette omise et charge
créée, soit 1 600 € d'écart pour 800 € encaissés.

**Gravité : majeur.**

**Correctif** : après avoir choisi un type, vérifier qu'il appartient au
bon camp ; si `montant > 0` et que le type est une charge, basculer en
compte d'attente plutôt que d'accepter.

---

### E-06 — Le fourre-tout est une charge déductible, pas un compte d'attente

**Fichier / fonction** : `import_bancaire.categoriser`, `return "autres_charges"`.

**Scénario** (sorties réelles) :

| Libellé | Montant | Type proposé |
|---|---|---|
| `REMBOURSEMENT PRET N.12345` | −890,00 | `autres_charges` |
| `INTERETS EMPRUNT` | −210,00 | `autres_charges` |
| `PRLV EDF ELECTRICITE` | −95,00 | `autres_charges` |

**Attendu** : le plan livré contient `472000 — A nouveaux en attente`, de
type `attente`. Une ligne non reconnue devrait y aller. Le compte 606100
« Énergie » existe et n'a aucune règle qui y mène ; 661100 « Intérêts des
emprunts » non plus.

**Produit** : `autres_charges`, qui pointe vers `628800 — Autres charges`,
un compte de **classe 6 immédiatement déductible**. La docstring affirme que
ce cas est « signalé à requalifier par les contrôles — comportement prudent,
pas silencieux » : le comportement prudent serait un compte d'attente, qui
bloque la liasse tant qu'il n'est pas soldé. Une charge déductible ne bloque
rien.

**Conséquence** : si le déclarant valide l'import sans relire, un
remboursement de capital est déduit. La différence entre « signalé » et
« bloquant » est ici toute la différence entre un contrôle qui protège et un
contrôle qui informe.

**Gravité : majeur.**

---

### E-07 — Les mots-clés sont écrits sans accents, les libellés bancaires en ont

**Fichier / fonction** : `import_bancaire._norm` (qui ne fait que
`strip().lower()`) et le tableau `REGLES`.

**Scénario** — même charge, deux libellés selon la banque :

```python
categoriser("PRELEVEMENT TAXE FONCIERE 2026",  -1420.0)  # -> 'impot_local'
categoriser("PRELEVEMENT TAXE FONCIÈRE 2026",  -1420.0)  # -> 'autres_charges'
```

**Attendu** : même résultat. Les clés `taxe fonciere`, `chaudiere`,
`copropriete`, `reparation` sont toutes écrites sans accent alors que les
libellés SEPA des banques en ligne (Boursorama, Fortuneo, BoursoBank) les
conservent.

**Produit** : la ligne accentuée tombe en `autres_charges`, avec la
conséquence E-06.

**Gravité : majeur** par le volume : taxe foncière, entretien chaudière et
appels de copropriété sont l'essentiel des charges d'un dossier LMNP.

**Correctif** : `unicodedata.normalize('NFD', s)` puis filtrage des
combinantes dans `_norm`.

---

### E-08 — La CFE est captée par la règle « impôts locaux »

**Fichier / fonction** : `import_bancaire.REGLES`, ordre des règles
`impot_local` (7ᵉ) puis `cfe` (8ᵉ), commentaire « premier match gagne ».

**Scénario** (sorties réelles) :

```python
categoriser("DGFIP COTISATION FONCIERE DES ENTREPRISES", -310.0)  # -> 'impot_local'
categoriser("TRESOR PUBLIC CFE 2026",                    -310.0)  # -> 'impot_local'
categoriser("CFE 2026 DGFIP",                            -310.0)  # -> 'impot_local'
```

Les trois libellés réalistes d'un avis de CFE contiennent `dgfip` ou
`tresor public`, qui matchent avant que la règle `cfe` ne soit atteinte.
Elle est **inatteignable en pratique**.

**Attendu** : `'cfe'`.

**Conséquence** : le plan distingue bien `635110 — Contribution Economique
Territoriale` de `635130 — Autres impots locaux`, et `liasse_pdf` imprime
une ligne dédiée « Impôts et taxes (case 244) — dont CFE … » alimentée par
`b["dont_cfe_243"]`. Si le type gouverne le compte (mapping non fourni,
cf. §5), la case 243 est servie à 0 alors qu'une CFE a été payée : une
incohérence visible dans le PDF que le déclarant recopie.

**Gravité : majeur** (mécanisme certain, montant de la conséquence à
confirmer avec le mapping).

---

### E-09 — Mobilier et électroménager systématiquement passés en charge

**Fichier / fonction** : `import_bancaire.REGLES`, règle `petit_equipement`.

**Scénario** :

```python
categoriser("ACHAT MOBILIER CONFORAMA", -1850.0)  # -> 'petit_equipement'
```

**Attendu** : au-delà de 500 € HT, un meuble ou un appareil destiné au
logement meublé est une **immobilisation** — le plan livré contient
`218400 — Mobilier` et son amortissement `281840`. La tolérance de 500 €
(BOI-BIC-CHG-20-30-20) ne couvre pas un achat de 1 850 €.

**Produit** : `petit_equipement`, donc `606320`, charge de l'exercice.
Aucun test de montant n'existe dans le module.

**Conséquence** : sur-déduction l'année de l'achat, sous-déduction les
années suivantes (aucun amortissement), et un 2033-C amputé. C'est aussi la
raison d'être du régime réel qui disparaît.

**Piège de nommage** : le mot-clé `mobilier` conduit à un compte de
**petit équipement**, alors que le compte littéralement nommé « Mobilier »
est `218400`, à l'actif. Un lecteur du référentiel ne peut pas le deviner.

**Gravité : majeur.**

---

### E-10 — Quatre comptes manquants au plan livré

**Fichier** : `seed-referentiel.md`.

Vérification faite : **aucune erreur de type ni de classe** dans les
33 comptes livrés. Les trois comptes d'amortissement `281315`, `281810`,
`281840` portent bien le type `amortissement` en classe 2 ; le terrain
`211550` n'a pas de compte d'amortissement, ce qui est correct ; toutes les
classes correspondent au premier chiffre du numéro. Le défaut est ailleurs :
ce sont des **absences**.

| Compte manquant | Ce qui devient impossible | Où ça se voit |
|---|---|---|
| `164000 — Emprunts auprès des établissements de crédit` (passif, cl. 1) | Enregistrer un prêt et distinguer capital / intérêts. `661100` existe pour les intérêts mais il n'y a **aucune dette financière** en face. | E-04, E-06 : la mensualité entière part en charge, faute de destination correcte. |
| `165000 — Dépôts et cautionnements reçus` (passif, cl. 1) | Encaisser un dépôt de garantie sans le déclarer. | E-01 : les 700 € deviennent un loyer. Le bilan 2033-A ne porte pas la dette. |
| `401000 / 411000` (ou `408100 / 418100`) | Constater à la clôture une facture reçue non payée ou un loyer impayé. | Même en comptabilité super-simplifiée (art. 302 septies A ter A CGI), créances et dettes doivent être régularisées à la clôture. Sans ces comptes, le résultat est décalé d'un exercice. |
| `758000 — Produits divers de gestion courante` (produit, cl. 7) | Loger une indemnité d'assurance ou un remboursement courant ailleurs qu'en `778800`, qui est un compte **exceptionnel** (778 = autres produits exceptionnels). | Le 2033-B sépare produits d'exploitation et produits exceptionnels : un produit courant rangé en 778 déforme la case 218/232 que `liasse_pdf` imprime. |

**Libellé à revoir** : `708810 — Loyers et autres produits`. Deux réserves.
D'abord le compte : le revenu principal d'une location meublée relève
normalement de `706` (prestations de services) ou `7083` (locations
diverses) ; `7088` est un compte d'activités *annexes*. Ensuite le libellé
« et autres produits » en fait un second fourre-tout : les charges
locatives refacturées au locataire n'ont pas de compte propre et se
mélangent au loyer, alors que `614100` existe côté charge. Le module
d'import connaît d'ailleurs un type `charges_locatives` (cf. E-13) qui n'a
nulle part où aller.

**Gravité : majeur** pour `164`/`165` (erreurs fiscales directes), moyen
pour le reste.

---

## 3. Mineur

### E-11 — Aucune validation de date

`import_bancaire._date_iso`. Sorties réelles :

| Entrée | Sortie | Attendu |
|---|---|---|
| `05/01/26` | `26-01-05`, période `26-01` | refus, ou `2026-01-05` |
| `31/13/2026` | `2026-13-31` | refus (mois 13) |
| `ab/cd/2026` | `ValueError` non rattrapée, remontée hors de `proposer` | message clair |

Une année sur deux chiffres produit une date de l'an 26 et une période
`26-01` ; selon ce que fait le guichet d'un tel format, la ligne est rejetée
plus tard ou rattachée à un exercice inexistant. **Gravité : mineur**
(probablement bloqué en aval, mais le message d'erreur sera incompréhensible).

### E-12 — L'apprentissage par historique ne se déclenche presque jamais

`import_bancaire.suggerer_depuis_historique` compare le libellé par
**égalité stricte** après `lower()/strip()`. Or les libellés bancaires
portent une référence ou une date variable. Sorties réelles avec un
historique contenant `FACTURE CABINET DUPONT 2025` :

- `FACTURE CABINET DUPONT 2025` → `honoraires`
- `FACTURE CABINET DUPONT 2026` → `None`
- `VIR FACTURE CABINET DUPONT 2025` → `None`

La fonctionnalité présentée comme « Priorité 1 » et « le meilleur
référentiel » est donc inopérante sur des relevés réels, sauf libellés
parfaitement stables. Par ailleurs le filtre `source='saisie'` exclut les
opérations issues d'un import précédent : une correction faite au moment de
l'import ne sera pas réapprise (comportement peut-être voulu, mais il
prive l'outil de sa seule source d'amélioration).
**Gravité : mineur** (fonctionnalité absente plutôt que fausse).

### E-13 — Le type `charges_locatives` est inatteignable

`import_bancaire.proposer`, ligne
`mensuel = type_op in ("loyer", "charges_locatives")`.
Aucune règle de `REGLES` ne produit `charges_locatives` — la règle syndic
produit `charge_copro`. Le seul chemin possible est l'historique. La
provision pour charges refacturée mensuellement n'aura donc pas de période
servie, alors que c'est un flux mensuel comme le loyer. **Gravité : mineur**,
mais c'est le symptôme du compte manquant relevé en E-10.

### E-14 — Mot-clé parasite dans `REGLES`

```python
(("les acteurs payants actuels", "comptab", "expert comptable"), "honoraires"),
```

`les acteurs payants actuels` n'est pas un mot-clé bancaire : c'est un
fragment de prose resté dans la table. Sans effet fonctionnel (il ne
matchera jamais), mais il signale que la table n'a pas été relue, et il
occupe la place qu'aurait dû prendre un vrai mot-clé (`fiduciaire`, `cabinet`,
`bilan`). **Gravité : mineur / hygiène.**

### E-15 — Le PDF ne porte aucune date d'édition

`liasse_pdf.generer_pdf` et `_pied_de_page`. Le document affiche l'année de
l'exercice, un filigrane « PROVISOIRE » et une mention de bas de page, mais
**ni date ni heure d'édition, ni version du logiciel**. Deux tirages
successifs d'un même exercice, entre lesquels une écriture a été corrigée,
sont visuellement indiscernables. Pour une pièce destinée à un
expert-comptable ou à un dossier de contrôle, c'est la première chose qui
manque. La mention « état de travail » est bien présente et correctement
formulée ; en revanche l'avertissement de la docstring — « pas un
fac-similé des formulaires CERFA » — ne figure nulle part **dans** le PDF,
alors que la page de garde s'intitule « Liasse fiscale LMNP ».
**Gravité : mineur**, correctif trivial et à fort rendement.

### E-16 — Débordement possible du tableau 2033-C

`liasse_pdf.generer_pdf`, boucle `for rub in c["rubriques"]`. Les libellés
de rubrique sont passés en **chaînes brutes**, dans une colonne de 46 mm
(118,4 pt utiles à 8,5 pt). Une chaîne ne se coupe pas dans un tableau
reportlab : elle déborde sur la colonne voisine. Largeurs mesurées :

- `Installations et agencements` → 107,7 pt — tient de justesse
- `Installations generales, agencements et amenagements des constructions`
  → 279,2 pt — **déborde sur trois colonnes de montants**

Le tableau « Détail par composant », juste en dessous, enveloppe pourtant
ses libellés dans `Paragraph(...)` avec 58 mm de large. L'incohérence est
interne au même fichier. **Gravité : mineur** (dépend des libellés de
rubriques réels, non fournis), correctif : envelopper en `Paragraph` comme
partout ailleurs.

### E-17 — Montants non alignés dans le suivi 39 C par logement

`liasse_pdf.generer_pdf`, `E.append(_table(lignes_b, largeurs=larg))` : le
paramètre `aligne_droite` n'est pas passé, donc la valeur par défaut `(1,)`
s'applique. Seule la colonne « Ouverture » est alignée à droite ; les
colonnes « Reporté », « Repris », « Sorti (G′) » et « Stock fin » restent à
gauche. Tous les autres tableaux de montants passent explicitement leur
plage (`range(1, 7)`, `range(1, 6)`, `(1, 2)`). **Gravité : mineur**, mais
c'est le tableau où l'on compare des colonnes entre elles.

### E-18 — Zéro négatif à l'affichage

`liasse_pdf._eur(-0.004)` → `'-0,00 €'` (sortie réelle). Un résidu
d'arrondi produit un montant nul affecté d'un signe moins, dans un document
où le signe porte le sens. `_eur` ne fait par ailleurs aucun calcul et un
arrondi unique : c'est correct. **Gravité : mineur.** Correctif : `x = 0.0 if abs(x) < 0.005 else x`.

### E-19 — Une seule chaîne non échappée

`liasse_pdf.generer_pdf` : `Paragraph(aide["note"], st["note"])`. Tous les
autres textes issus des données passent par `_xml(...)` — nom de
l'exploitant, libellés de composants, de biens, de contrôles. Si
`aide["note"]` contient un `&` ou un `<`, la génération lève. La note est
vraisemblablement une constante interne, d'où le classement en mineur, mais
l'exception à la règle n'est pas motivée. **Gravité : mineur.**

### Remarques ponctuelles

- `import_bancaire.proposer` : `open(csv_path, "rb").read()` ne referme pas
  le descripteur (`with` attendu).
- `import_bancaire.proposer` : la détection de séparateur ne teste que `;`
  et `,` ; un export tabulé passe par `;`, produit une colonne unique et
  tombe dans E-03.
- `liasse_pdf` : vérifié — un tableau à 2 lignes (en-tête + 1) et un
  tableau à 1 ligne ne lèvent pas malgré le style
  `LINEBELOW (0,1)→(-1,-2)`. Non défectueux.

---

## 4. Ce qui a été vérifié et tenu

Trois points explicitement demandés, et qui sont **bons** :

1. **`liasse_pdf.py` ne recalcule rien.** Recherche exhaustive
   d'opérateurs arithmétiques et de `sum()`/`round()` hors conversions
   d'unités : aucune occurrence. Chaque montant imprimé est une valeur lue
   dans le dictionnaire produit par `liasse.generer()`. Le défaut majeur de
   la passe précédente n'a pas de récidive ici.
2. **`_eur` n'arrondit qu'une fois** et formate correctement le négatif,
   l'absence de valeur (`—`) et les milliers (`1 234 567,89 €`).
3. **Le plan comptable ne comporte aucune erreur de type ni de classe.**
   Les 33 comptes ont été contrôlés un à un : classe = premier chiffre,
   type cohérent avec la nature, comptes 28x tous typés `amortissement`.

---

## 5. Non vérifiable avec les pièces fournies

Ces points sont posés comme **questions**, pas comme constats.

- **Doublons à la réimportation.** `importer(conn, csv_path, valider=True)`
  appelle `operations.saisir(...)` pour chaque proposition. Ce module n'a
  pas été fourni. Ce que je peux dire du fichier joint : `proposer` ne
  produit **aucune clé d'idempotence** (empreinte date+libellé+montant), ne
  consulte pas les opérations déjà importées, et ne conserve aucune trace
  du fichier traité. Si le guichet ne déduplique pas, réimporter janvier
  deux fois double janvier. *Test à faire : importer deux fois le même CSV,
  compter les lignes.*
- **Mapping type → compte.** Les conséquences comptables de E-06, E-08 et
  E-09 (`autres_charges` → 628800, `impot_local` → 635130,
  `petit_equipement` → 606320) reposent sur une correspondance qui n'est
  dans aucun des trois fichiers. Les erreurs de **classement** sont
  certaines ; les numéros de compte cités sont des déductions.
- **Contrôle de l'exercice.** Rien dans `import_bancaire` ne compare la
  date importée à l'exercice courant ni à un exercice clos ; le guichet le
  fait peut-être.
- **Absence de compte de trésorerie (512/530).** Le seed documente
  explicitement « contrepartie trésorerie = 108000 ». C'est un choix, pas un
  oubli — mais il faudrait vérifier ce que le 2033-A imprime alors en
  disponibilités et si `total_actif_net_112` reste cohérent.
- **Déficits périmés.** `liasse_pdf` affiche `— périmé` à côté de l'année
  d'expiration mais reprend `rep["total_deficits"]` tel quel. Si le moteur
  inclut un déficit périmé dans ce total, le PDF affichera un total
  supérieur à la somme réellement imputable. Le calcul appartient à
  `liasse.py`, non fourni.
- **Libellés réels des rubriques 2033-C** (E-16) : le débordement est
  démontré pour un libellé de 70 caractères, pas observé sur vos données.

---

## Récapitulatif

| # | Constat | Fichier | Gravité |
|---|---|---|---|
| E-01 | Tout encaissement inconnu → loyer imposable | import_bancaire | Critique |
| E-02 | Export 4 colonnes accepté, débits → recettes | import_bancaire | Critique |
| E-03 | Lignes ignorées en silence (signe suffixe, €, parenthèses, tab) | import_bancaire | Critique |
| E-04 | `IMMOBILIER` ⊃ `mobilier` → mensualité en petit équipement | import_bancaire | Critique |
| E-05 | Nature retenue jamais confrontée au sens du montant | import_bancaire | Majeur |
| E-06 | Fourre-tout en charge déductible au lieu du compte d'attente | import_bancaire | Majeur |
| E-07 | Mots-clés sans accents contre libellés accentués | import_bancaire | Majeur |
| E-08 | Règle `cfe` inatteignable, captée par `impot_local` | import_bancaire | Majeur |
| E-09 | Mobilier > 500 € passé en charge, jamais immobilisé | import_bancaire | Majeur |
| E-10 | Comptes 164, 165, 401/411, 758 absents ; 708810 fourre-tout | seed | Majeur |
| E-11 | Dates non validées (année sur 2 chiffres, mois 13) | import_bancaire | Mineur |
| E-12 | Historique inopérant (égalité stricte du libellé) | import_bancaire | Mineur |
| E-13 | Type `charges_locatives` inatteignable | import_bancaire | Mineur |
| E-14 | Mot-clé parasite dans `REGLES` | import_bancaire | Mineur |
| E-15 | PDF sans date d'édition ni mention « non CERFA » | liasse_pdf | Mineur |
| E-16 | Libellés 2033-C non enveloppés, débordement mesuré | liasse_pdf | Mineur |
| E-17 | Montants non alignés dans le suivi 39 C par bien | liasse_pdf | Mineur |
| E-18 | `-0,00 €` | liasse_pdf | Mineur |
| E-19 | `aide["note"]` seule chaîne non échappée | liasse_pdf | Mineur |
| E-20 | Produits exceptionnels non isolés (case 218/232 gonflée) | liasse | À qualifier |

**Lecture d'ensemble.** Le déséquilibre entre les trois pièces est net.
`liasse_pdf.py` est sain sur le point qui comptait le plus — il ne
recalcule rien — et ses défauts sont cosmétiques. Le plan comptable est
correctement typé mais incomplet sur deux comptes qui décident du sort
fiscal d'un dossier LMNP ordinaire (emprunt, dépôt de garantie).
`import_bancaire.py` est d'un autre ordre : quatre défauts critiques, dont
trois produisent des écritures fausses sans aucun signal. La mention
« fonction expérimentale » dans l'interface ne suffit pas, parce que le
résultat de l'expérience est indiscernable d'un import correct. Tant que
E-01, E-02 et E-03 ne sont pas traités, cet import devrait au minimum
refuser tout fichier dont le format ne correspond pas exactement à ce qu'il
sait lire, et rendre compte de chaque ligne rejetée.

---

## Suivi des correctifs

### Lot 1 — E-02 + E-03 (traité)

`import_bancaire.py` :

- `_montant()` lit désormais `-120,50`, `120,50-`, `(120,50)`, `-120,50 EUR`,
  `-1 234,50 €` et les espaces insécables ; elle **lève** sur le reste au lieu
  de renvoyer un `continue` muet.
- `_delimiteur()` reconnaît la **tabulation** en plus de `;` et `,`, le
  point-virgule l'emportant à égalité (la virgule est d'abord un séparateur
  décimal en France).
- `analyser()` remplace le cœur de `proposer()` et renvoie
  `{"propositions": [...], "rejets": [...]}`. Chaque rejet porte son numéro de
  ligne, son contenu et la raison. `proposer()` subsiste et renvoie toujours
  une liste : `app.py`, `cli.py` et les tests existants sont inchangés.
- Toute ligne de données qui ne porte pas **exactement trois colonnes** fait
  échouer le fichier avec un message nommant la ligne, le nombre de colonnes
  et la manœuvre de sortie.
- `open(csv_path, "rb")` passe en `with` (remarque ponctuelle du §3).

`app.py` et `cli.py` affichent le nombre de lignes rejetées, et l'erreur
« aucune ligne exploitable » cite désormais la première raison réelle.

Non-régression : `tests/test_passe_e.py`, 26 tests reprenant les scénarios
du rapport.

### Lot 2 — E-10 (traité)

`seed_referentiel.sql` passe de 33 à 38 comptes :

| Compte | Type / classe | Ce qu'il rend possible |
|---|---|---|
| `164000` Emprunts auprès des établissements de crédit | passif, 1 | séparer capital (dette) et intérêts (`661100`) |
| `165000` Dépôts et cautionnements reçus | passif, 1 | encaisser un dépôt de garantie sans le déclarer |
| `401000` Fournisseurs | passif, 4 | facture reçue non payée à la clôture |
| `411000` Locataires | actif, 4 | loyer impayé à la clôture (créance, donc actif) |
| `758000` Produits divers de gestion courante | produit, 7 | produit COURANT hors du compte exceptionnel 778 |

`init_db.VERSION_SCHEMA` passe à 7, avec `migrations._palier_7` : sans lui, un
dossier existant n'aurait pas ces comptes et les nouveaux gabarits
échoueraient sur la clé étrangère `compte(numero)` **chez l'utilisateur**.

`gabarits.py` gagne six entrées et en corrige une :

- `depot_garantie_recu` / `depot_garantie_restitue` → `165000` ;
- `emprunt_recu` / `emprunt_capital_rembourse` → `164000` ;
- `attente_encaissement` / `attente_decaissement` → `472000` ;
- `indemnite_assurance` : `778800` → `758000`.

Deux mécanismes préexistants font que cela suffit, sans toucher au moteur :
`fiscal.agregats` agrège le résultat par **classe** de compte (6 et 7), donc
les classes 1 et 4 en sont exclues d'office ; et `controles.c_compte_attente`
refuse déjà en **BLOQUANT** un solde 472000 non apuré. Le compte d'attente
réclamé par E-06 bloque donc réellement la liasse, là où `628800` se contente
d'un avertissement sur une charge déjà déduite.

Effet de bord corrigé au passage : la reconstruction des opérations de
démonstration (`init_db`) mappait compte → gabarit sans filtre. Le nouveau
gabarit sur `472000` faisait de la ligne d'attente des à-nouveaux une
« opération » de démo. La reconstruction est désormais restreinte aux
gabarits de résultat (classes 6 et 7), ce qui était le comportement de fait
avant la passe E.

Non-régression : 15 tests supplémentaires dans `tests/test_passe_e.py`.

### Lot 3 — E-01, E-04, E-05, E-06 (traité)

`import_bancaire.categoriser` est réécrit autour de trois idées.

**Le sens du flux gouverne le jeu de règles.** `REGLES_ENCAISSEMENT` traite
les crédits (dépôt de garantie, déblocage de prêt, indemnité, régularisation
de charges, loyer — CAF/APL comprises), `REGLES` les débits. `if montant > 0:
return "loyer"` disparaît : un encaissement inconnu ne crée plus d'impôt.

**Les mots-clés sont ancrés en DÉBUT DE MOT.** `_contient()` remplace
`any(k in lib …)`. « mobilier » ne matche plus dans « IMMOBILIER », « rent »
plus dans « PARENTS ». L'ancrage ne porte volontairement **que sur le début**
du mot : les libellés bancaires fléchissent les terminaisons, et un `\b` des
deux côtés aurait fait tomber « comptab » → COMPTABLE, « reparation » →
RÉPARATIONS, « assurance » → ASSURANCES. Les six règles historiques passent
toujours.

**Le type retenu est confronté au signe.** `_coherent()` compare la `nature`
du gabarit au sens du montant ; en cas de désaccord, la ligne part en attente.
Ce contrôle s'applique aussi au chemin de l'historique, qui était précisément
le scénario d'E-05.

**Le fourre-tout devient un compte d'attente.** `autres_charges` (628800,
charge déductible) cesse d'être la destination par défaut au profit de
`attente_encaissement` / `attente_decaissement` (472000). `autres_charges`
reste au catalogue pour la saisie manuelle.

**Une mensualité de prêt ne propose rien.** `VENTILATION_REQUISE` capte
pret / emprunt / echeance / mensualite / credit immobilier et bascule en
attente : la mensualité mêle capital non déductible et intérêts déductibles,
aucune proposition automatique ne peut être juste.

`suggerer_depuis_historique` ne resuggère plus un fourre-tout — le test porte
désormais sur le drapeau `requalifier` du gabarit et non sur un nom de type
écrit en dur, puisque `autres_charges` n'est plus le seul concerné.

Bout en bout, le relevé d'E-01 (4 encaissements, 6 820 €) n'ajoute plus que
**1 120 €** au résultat : l'allocation logement et l'indemnité d'assurance.
Le dépôt de garantie devient une dette, l'apport part en attente.

Non-régression : 15 tests supplémentaires. Trois tests existants mis à jour,
tous sur le changement de fourre-tout (`autres_charges` → `attente_*`).

### Incident — nom réel recopié dans un test, attrapé par le contrôle du projet

En écrivant les tests d'E-01 j'ai recopié tel quel le libellé
« VIR M \<nom\> APPORT » du tableau du rapport : il porte le nom réel de
l'exploitant. `tests/test_audit_production.py`, qui exécute le contrôle de
publication, a échoué en BLOQUANT et l'a signalé. Le libellé est anonymisé
(« VIR M DUPONT APPORT »), dans le test **et dans ce rapport**.

Deux enseignements :

1. Le garde-fou fonctionne, et il a fonctionné dans la seule direction qui
   compte — il a bloqué avant publication, pas après.
2. **`verifier_depot.py` ne couvre pas `docs/`.** Il inspecte ce que le
   paquet publierait, c'est-à-dire l'arborescence `compta_lmnp/`. Le rapport
   d'audit, à la racine du dépôt, portait le même nom réel sans qu'aucun
   contrôle ne le voie. Un dépôt public expose `docs/` comme le reste : le
   contrôle devrait porter sur les fichiers **suivis par git**, pas seulement
   sur le contenu du paquet. **À traiter.**

### Réserve — la conséquence annoncée pour les cases 218/232 n'existe pas

E-10 conclut qu'un produit courant logé en `778800` « déforme la case 218/232
que liasse_pdf imprime ». Vérification faite dans `liasse.py` :

    produits = round(-_somme(s, ("7",)), 2)      # 218 / 232

**Tous** les comptes de classe 7 sont additionnés sans distinction : la liasse
ne sépare aujourd'hui ni 706, ni 708, ni 758, ni 778. Créer `758000` et y
router l'indemnité d'assurance reste juste sur le fond — c'est le bon compte,
778 étant exceptionnel — mais cela ne corrige aucun chiffre de la liasse
actuelle. Le défaut réel, non relevé par l'audit, est que la liasse ne
distingue pas les produits exceptionnels des produits d'exploitation.
**À arbitrer** : est-ce un constat à ouvrir pour une passe ultérieure ?

### Point ouvert — apport de l'exploitant (issu d'E-01)

E-01 attend qu'un apport soit dirigé vers « le compte de l'exploitant
108000 ». Or `gabarits.COMPTE_CONTREPARTIE` vaut déjà `108000` : dans ce
modèle de caisse, 108000 tient à la fois le rôle de trésorerie et celui de
compte de l'exploitant. Un apport y serait donc débité **et** crédité — une
écriture nulle. Aucun gabarit d'apport n'a été créé pour cette raison ; le
traitement d'E-01 devra router ces lignes vers l'attente, ou le modèle devra
introduire un compte de trésorerie distinct (question déjà posée au §5 du
rapport, « absence de compte 512/530 »).

### E-20 — Les produits exceptionnels ne sont pas isolés (constat ouvert)

**Fichier / fonction** : `liasse.py`, calcul des cases 218/232.

Constat né de la vérification d'E-10, et absent du rapport initial. La liasse
traite les deux moitiés de l'exceptionnel de façon **asymétrique** :

```python
ligne 123 :  charges_exc = _somme(s, ("67",))    # -> case 300, ISOLÉE
ligne 110 :  produits    = -_somme(s, ("7",))    # -> cases 218/232, TOUT CONFONDU
```

Les charges exceptionnelles ont leur case dédiée ; les produits exceptionnels
n'en ont pas. `775000` — produits des cessions d'éléments d'actif, créé par
`cession.py` — est donc additionné aux loyers dans le chiffre d'affaires.

**Conséquence** : sur un exercice de cession, la case 218 est gonflée du prix
de vente. Le résultat FINAL reste juste, la neutralisation opérant par
ailleurs (`fiscal.agregats` isole `produits_cession` et `vnc_cession`), mais
la **ventilation imprimée est fausse** — et c'est elle que le déclarant
recopie sur sa déclaration.

**Portée en LMNP.** L'exceptionnel n'y est pas anecdotique mais il est
étroit : la cession d'un bien ou d'un composant, et l'indemnité d'assurance
liée à la destruction d'un actif. Un sinistre courant — dégât des eaux, perte
de loyers — est un produit d'exploitation ordinaire (`758000`), ce que le
lot 2 a mis en place. Les comptes 67/77 existent ici précisément pour être
**sortis** du résultat BIC, la cession relevant en LMNP non professionnel des
plus-values des particuliers.

**Gravité : à qualifier** (majeur si la ventilation imprimée fait foi pour le
déclarant, mineur si elle n'est qu'indicative). Les numéros de case sont à
recouper avec le CERFA 2033-B en vigueur avant correction.

### Point ouvert — support des exports à colonnes débit/crédit séparées

E-02 est traité par un **refus explicite**, correctif minimal du rapport.
Lire réellement un export « Date;Libellé;Débit;Crédit » (Crédit Agricole,
Banque Populaire, la plupart des exports Excel) reste à faire, et n'a pas
été construit : il faut d'abord constater le format exact des relevés
réellement utilisés. Deux conséquences à assumer d'ici là :

1. Un utilisateur dont la banque exporte quatre colonnes ne peut plus
   importer du tout, là où l'import « fonctionnait » auparavant — en
   produisant des écritures fausses. La régression est fonctionnelle,
   l'ancien comportement était comptablement faux.
2. Le choix entre *détecter* la paire débit/crédit et *demander* à
   l'utilisateur quelle colonne porte le montant n'est pas tranché.

**À trancher une fois le format des relevés confirmé.**
