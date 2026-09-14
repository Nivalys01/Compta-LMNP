# Synthèse des passes E et F

Deux revues, deux périmètres, un même motif de fond. La passe **E** portait sur
l'import bancaire, la liasse PDF et le plan comptable — ce qui produit des
chiffres. La passe **F** portait sur la chaîne de distribution — ce qui
empêche les données réelles de sortir.

## Les chiffres

| | Passe E | Passe F |
|---|---|---|
| Constats | **22** | **12** |
| dont critiques | 4 | 4 |
| dont majeurs | 6 | 6 |
| dont mineurs | 9 | 2 |
| dont à qualifier | 3 | — |
| Traités | **21** (E-22 ouvert) | **12** |
| Tests de non-régression | 127 | 28 |
| Commits | 11 | 5 |

Suite complète : **690 tests, 0 échec** sur le poste de développement ;
**545 passés, 147 ignorés, 0 échec** sur un clone public. `ruff` propre,
contrôle de publication vert, CI verte.

Sur les 22 constats de la passe E, **19 venaient du rapport d'audit** et
**3 ont été ouverts en cours de travail** (E-20, E-21, E-22).

---

## Passe E — ce qui produisait des chiffres faux

### L'import bancaire : la porte d'entrée (E-01 à E-14)

C'est là que tout se jouait. Quatorze constats sur un module de 142 lignes,
dont les quatre critiques de la passe.

**Le sens du flux n'existait pas.** `if montant > 0: return "loyer"` faisait
de **tout** crédit un loyer imposable. Sur le relevé du rapport — dépôt de
garantie, apport, indemnité d'assurance, allocation logement — cela donnait
6 820 € de recettes dont 5 700 € qui ne sont pas des produits. L'import ne
crée plus d'impôt qui n'est pas dû : le même relevé n'ajoute que **1 120 €**
au résultat.

**Les mots-clés n'avaient aucune frontière.** `any(k in lib for k in cles)`
cherchait une sous-chaîne : « mobilier » matchait dans « IMMOBILIER », donc
une mensualité de prêt immobilier devenait du petit équipement — 10 680 € de
capital passés en charge sur l'année, le redressement le plus classique en
LMNP au réel. « rent » matchait de même dans « PARENTS ».

L'ancrage porte désormais sur le **début du mot**, pas sur sa fin : les
libellés bancaires fléchissent les terminaisons, et un `\b` des deux côtés
aurait fait tomber « comptab » → COMPTABLE ou « reparation » → RÉPARATIONS.

**Le fourre-tout était déductible.** Une ligne non reconnue tombait en
`628800`, charge immédiatement déductible : le contrôle « signalait » sans
rien empêcher. Elle va maintenant en `472000`, sur lequel un contrôle
**BLOQUANT** existait déjà. La différence entre un contrôle qui informe et un
contrôle qui protège tenait à un numéro de compte.

**Un export à quatre colonnes était lu à l'envers.** Le test `len(r) < 3`
acceptait 4, 5 ou 12 colonnes et prenait la colonne débit, non signée, pour un
montant : sur un relevé annuel, la totalité des charges basculait en produits.
Refus explicite désormais, avec un message qui nomme la ligne et la sortie de
secours.

**Des lignes disparaissaient sans un mot.** Quatre formats de montant courants
— `120,50-`, `(120,50)`, `-120,50 EUR`, `-1 234,50 €` — et les exports tabulés
tombaient dans un `continue` muet. Un relevé entièrement dans l'un de ces
formats produisait zéro proposition, et l'utilisateur concluait que son relevé
était vide. La docstring justifiait pourtant le nettoyage des séparateurs de
milliers par le refus de toute « perte de données invisible » : le `continue`
deux lignes plus bas en produisait une.

`analyser()` rend désormais **propositions ET rejets**, chacun avec son numéro
de ligne, son contenu et sa raison — et `app.py` comme `cli.py` les affichent.

**Et le reste** : nature jamais confrontée au signe du montant (E-05), accents
absents des mots-clés alors que les libellés SEPA en portent (E-07), règle
`cfe` inatteignable parce que placée après `impot_local` (E-08), seuil
d'immobilisation jamais testé (E-09), dates non validées — `05/01/26` donnait
une date de l'an 26 (E-11), historique inopérant pour deux causes (E-12), et un
mot-clé inerte (E-14).

### Le plan comptable (E-10)

Aucune erreur de type ni de classe dans les 33 comptes livrés : le défaut était
fait d'**absences**. Cinq comptes ajoutés — `164000` emprunts, `165000` dépôts
de garantie, `401000` fournisseurs, `411000` locataires, `758000` produits
divers — avec `VERSION_SCHEMA` à 7 et le palier de migration correspondant.

Deux mécanismes préexistants ont suffi : `fiscal.agregats` agrège par **classe**
de compte, donc les classes 1 et 4 sont hors résultat d'office ; et
`controles.c_compte_attente` refusait déjà en BLOQUANT un solde `472000` non
apuré.

### La liasse (E-15 à E-20, E-22)

Le module PDF ne recalculait rien — le point qui comptait le plus était sain.
Ses défauts étaient cosmétiques, sauf un : **le document ne portait ni date, ni
heure, ni version**. Deux tirages d'un même exercice, entre lesquels une
écriture avait été corrigée, étaient indiscernables. Pour une pièce destinée à
un expert-comptable, c'est la première chose qui manque.

Plus grave, trouvé en recoupant avec le CERFA 2033-B-SD 2026 fourni : la liasse
isolait les **charges** exceptionnelles en case 300 mais additionnait tous les
comptes de classe 7 dans les cases 218/232. Le prix de cession gonflait donc le
chiffre d'affaires imprimé — et c'est lui que le déclarant recopie. Le résultat
final restait juste, la ventilation était fausse.

La vérification exhaustive des **29 cases** contre le formulaire officiel a
confirmé le reste et révélé que les huit numéros de rubrique du 2033-C étaient
**calculés puis jamais imprimés** — même classe de défaut.

---

## Passe F — ce qui devait empêcher une fuite

Trois fichiers présentés comme les gardiens de la frontière. Le constat est
plus dur que pour la passe E : **ils ne formaient pas une chaîne mais trois
contrôles qui se croisaient sans se recouvrir.**

- `outils_demo` **produisait sans vérifier** : les deux fonctions écrivaient le
  jeu de démonstration publié puis rendaient un chemin, sans jamais relire leur
  sortie.
- `construire_distribution` **vérifiait des noms qu'il avait lui-même choisis** :
  la garde comparait `INTERDITS` aux fichiers du zip, lesquels sont exactement
  la liste écrite à la main. Elle vérifiait qu'une liste ne contenait pas ce
  qu'on n'y avait pas mis — structurellement incapable de rien détecter.
- `verifier_depot` **vérifiait du contenu**, mais sur le dépôt et non sur le
  paquet, et **rendait un feu vert dès qu'il ne pouvait pas travailler**.

La chaîne complète a été reproduite : un seed de démonstration portant une
identité réelle était livré dans le zip, les deux gardes au vert, chacune
imprimant « aucune donnée personnelle ».

Les six majeurs déclinaient le même thème sur l'anonymisation : liste des
termes absente sans un mot (F-05), identité conservée si l'`INSERT` s'écartait
de la forme attendue — trois formes SQL sur quatre passaient (F-06),
appariement positionnel des valeurs (F-07), **3 colonnes FEC anonymisées sur
18** (F-08), recherche d'empreintes sensible à la casse, aux accents et aux
espaces (F-09), aucune vérification après génération (F-10).

### Ce qui a été mis en place

**Aucun des trois ne peut plus conclure positivement sans avoir examiné
quelque chose.** Deux alertes BLOQUANTES nouvelles dans `verifier_depot`, une
garde de contenu sur le zip, un refus de générer sans les prérequis, et un
contrôle d'après génération qui **supprime** le fichier fautif — le réflexe que
`construire_distribution` avait déjà pour son zip, appliqué enfin au bon objet.

---

## Le motif commun : le silence

Les huit constats critiques des deux passes ont un trait unique en commun :
**aucun ne produisait d'erreur.**

| | Ce qui se passait | Ce qui s'affichait |
|---|---|---|
| E-01 | tout crédit devenait un loyer imposable | un import réussi |
| E-02 | les charges devenaient des recettes | un import réussi |
| E-03 | des lignes disparaissaient | un import réussi |
| E-04 | 10 680 € de capital en charge | une proposition plausible |
| F-01 | aucune empreinte n'avait été cherchée | « aucune donnée personnelle » |
| F-02 | aucun fichier n'avait pu être listé | code de sortie 0 |
| F-03 | le contenu n'avait jamais été lu | « aucune donnée personnelle » |
| F-04 | l'identité réelle partait dans le paquet | « aucune donnée personnelle » |

C'est ce qui rend ces défauts coûteux : non pas qu'ils soient subtils, mais
qu'ils ressemblent au succès. Un garde-fou qui se tait quand il ne peut pas
travailler est plus dangereux que pas de garde-fou, parce qu'on lui fait
confiance.

---

## Cinq amendements aux rapports d'audit

Le travail a corrigé le diagnostic sur cinq points :

1. **E-10** annonçait que loger un produit courant en `778800` déformait les
   cases 218/232. Vérification faite, la liasse n'y distinguait ni 708 ni 778 :
   la conséquence annoncée n'existait pas, mais le vrai défaut était plus
   large → ouvert en **E-20**.
2. **E-12** attribuait l'inefficacité de l'historique à la seule égalité
   stricte du libellé. Une deuxième cause, indépendante : `LOWER()` de SQLite
   est ASCII, l'historique ne retrouvait **aucun** libellé accentué.
3. **E-13** était déjà réglé par un lot antérieur — aucune correction
   nécessaire, seulement des tests pour le figer.
4. **E-14** voyait « un fragment de prose resté dans la table », signe d'une
   table non relue. C'était le produit d'un **remplacement global**
   d'anonymisation : 25 occurrences dans 17 fichiers, dont deux qui servent de
   motif à l'anonymisation du jeu publié et qu'il ne faut surtout pas toucher.
5. Le **§5** déclarait le mapping type → compte manquant. Il est dans
   `gabarits.py`, et les trois déductions du rapport étaient exactes.

---

## Ce que les garde-fous du projet ont attrapé

Six fois, un contrôle déjà en place a arrêté une faute — dont **cinq étaient
les miennes**. C'est la meilleure mesure de leur valeur.

| Garde-fou | Ce qu'il a arrêté |
|---|---|
| Contrôle de publication | le nom réel de l'exploitant, recopié depuis le rapport dans un test |
| Contrôle de publication | l'adresse réelle, écrite en clair dans le rapport de la passe F **qui décrit cette faute** |
| Assertion des paliers de migration | un `VERSION_SCHEMA` relevé sans le palier correspondant |
| Contrôle d'après génération (F-10) | ma propre régression sur l'appariement par colonne, au premier essai |
| Clone de simulation | cinq tests cassés par les correctifs de la passe F — la CI aurait été rouge |
| `ruff` | un import inutilisé dans le fichier de tests de la passe F |

Le quatrième mérite un mot : en réécrivant l'appariement par nom de colonne
(F-07), je collectais encore les seules valeurs **quotées**. Or le seed déclare
`(id, nom, siren, adresse)` et `id` ne l'est pas : `nom` recevait la valeur de
`id`, et l'identité traversait intacte. Le contrôle que je venais d'écrire a
refusé le fichier et l'a supprimé. **Sans lui, cette régression partait dans le
jeu publié sans un mot** — la démonstration la plus courte de ce que valait
F-10.

Deux autres corrections m'incombent aussi : j'ai nommé la rue de l'auteur dans
les commentaires expliquant qu'il ne faut pas la nommer, et j'ai affirmé
qu'`/tmp` était lisible par les autres utilisateurs alors que pytest le crée
en `0700` — énoncé corrigé dans le rapport, gravité d'E-21 ramenée de majeur
à mineur.

---

## Ce qui reste ouvert

| Sujet | Pourquoi ce n'est pas fait |
|---|---|
| ~~**E-22**~~ — le bilan ignore dettes et créances | **Clos : choix assumé.** La comptabilité est tenue sans tiers ni trésorerie. Ce qui devait être garanti l'est — un FEC de cabinet portant ces comptes s'importe sans rien perdre, figé par `test_import_cabinet.py`. |
| **Exports bancaires à 4 colonnes** | En attente du format exact des relevés réellement utilisés. Le refus explicite est en place ; lire la paire débit/crédit reste à construire. |
| **Cases 5NA / 5NY** | Elles appartiennent au formulaire 2042-C-PRO, non fourni. |
| **Filtre `source='saisie'` de l'historique** | Conservé : le guichet d'import ne permet pas de corriger le type avant validation, donc apprendre des lignes importées reviendrait à réapprendre les propositions de l'outil. À rouvrir quand le guichet le permettra. |
| **Prose anonymisée** | Reformulée en « les logiciels du marché » sur décision de l'auteur, en sachant que la formule reste inexacte là où le mot désignait un cabinet et non un logiciel (`schema.sql`, `cession.py`, `export_fec.py`). |

### Points d'entretien

- Trois archives de pré-purge dans `~/sauvegardes-git-purge/` portent encore
  l'historique **non purgé** — à supprimer quand le retour en arrière ne sera
  plus envisagé.
- La CI ne couvre que Python 3.13. La syntaxe du projet est compatible 3.10
  (vérifié par analyse), le runtime n'a été éprouvé que localement.
- `verifier_depot.py` reste un geste **local**, avant push : il refuse
  délibérément de conclure sur un runner, faute d'empreintes.
