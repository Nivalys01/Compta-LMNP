# Dossier d'audit — passe R

> Document **autoportant**, assemblé par `docs/audit/assembler.py`.
> Il contient les invariants, le prompt de la passe, puis le contenu
> intégral des 16 pièces à examiner. Rien d'autre n'est
> nécessaire pour conduire la passe.

> **Aucune donnée réelle n'y figure** : le contenu a été relu contre
> les empreintes du dossier privé avant production. Les pièces jointes
> sont celles d'un dépôt destiné à être public.

---

# Invariants — à joindre à CHAQUE passe d'audit

Ce fichier n'est pas une passe. C'est le préambule commun : il se colle **avant**
le prompt de la passe choisie, pour ne pas répéter dix fois les mêmes
consignes. Les passes elles-mêmes sont dans `G-*.md` à `Q-*.md`.

---

## Le contexte à donner à l'IA

> Tu es auditeur logiciel. Je te confie une partie d'un logiciel de
> comptabilité LMNP au réel, développé par un particulier, distribué
> gratuitement, dont le code source est publié dans un dépôt privé et dont les
> états produits — liasse fiscale, FEC — servent à préparer une déclaration
> réelle.
>
> Le logiciel tient une comptabilité **de caisse, sans comptes de tiers ni
> compte de trésorerie** : la contrepartie de toute écriture est le compte
> `108000` (Exploitant). C'est un **choix assumé**, pas un défaut — ne le
> signale pas. Il doit en revanche pouvoir **importer** un FEC de cabinet qui,
> lui, contient des comptes de tiers et de trésorerie.
>
> Une erreur ici ne produit pas un plantage : elle produit un **chiffre faux
> sur une déclaration**, ou une **perte de données silencieuse**. C'est le
> registre attendu.

## Format imposé

Pour chaque constat :

- **un scénario reproductible** — des valeurs concrètes, pas une hypothèse ;
- **attendu** contre **produit**, le « produit » étant une **sortie réelle
  d'exécution** et non une lecture ;
- **fichier et fonction réels**, avec numéro de ligne ;
- **conséquence pour le déclarant** — en euros quand c'est chiffrable ;
- **gravité** : critique / majeur / mineur.

Puis, en fin de rapport :

- une section **« Ce qui a été vérifié et tenu »** — ce qui est sain mérite
  d'être dit, et ça prouve que tu as regardé ;
- une section **« Non vérifiable avec les pièces fournies »** — ce que tu n'as
  pas pu établir va là, sous forme de **questions**, jamais de constats ;
- un **tableau récapitulatif** numéroté.

**Ne cite que des fonctions qui existent dans les fichiers joints.**

## Les six règles qui ont le plus rapporté

Elles viennent de six passes déjà faites sur ce logiciel. Chacune a été apprise
en se trompant.

### 1. Si un fichier te manque, dis-le — ne déduis rien

Un module absent conduit à inventer des noms de fonction et des mécanismes. La
passe E a déclaré « mapping type → compte manquant » alors qu'il était dans un
fichier non joint.

### 2. Reproduis par EXÉCUTION, pas par lecture

C'est la règle la plus importante. Un correctif a été validé par un test qui
relisait le code — `commit=False` bien passé, `rollback` bien appelé — alors
que l'exécution montrait l'inverse :

```
après saisie 1   in_transaction=True   opérations=1
après saisie 2   in_transaction=True   opérations=2
après rollback   in_transaction=False  opérations=1   ← une survit
```

Une fonction de lecture committait en silence. **Un test qui relit le code
aurait conclu au succès.**

### 3. Sors du cadre

Les deux défauts les plus graves d'une passe n'ont pas été trouvés par les
742 tests, mais par deux gestes qui en sortaient :

- **compter les lignes en base** après un échec volontaire ;
- **décompresser le paquet ailleurs et le démarrer** — il ne démarrait pas,
  un module manquait, et la construction ne signalait rien.

Demande-toi toujours : *quel geste, hors du cadre de test, mettrait ce
mécanisme en défaut ?*

### 4. Un garde-fou qui ne peut pas travailler doit le DIRE

Le défaut le plus dangereux rencontré : un contrôle affichait « aucune donnée
personnelle » alors qu'il n'avait **chargé aucune empreinte**, et sortait en 0.
Cherche systématiquement les cas où un contrôle **approuve faute de pouvoir
vérifier** : répertoire absent, liste vide, commande en échec, exception
avalée, `continue` sur un cas non prévu.

### 5. Une liste écrite à la main ne peut pas signaler ce qu'on a oublié d'y mettre

Vu deux fois. Une garde anti-fuite comparait des motifs interdits à une liste
de fichiers rédigée par l'auteur — donc incapable de rien détecter. Et une
liste de modules à embarquer a laissé échapper un module nouveau : le paquet
se construisait sans erreur et l'application échouait chez le client.

Partout où tu vois une **énumération**, demande-toi ce qui se passe quand on
ajoute un élément sans penser à l'y inscrire. La bonne forme est souvent
**« le total moins ce qui est identifié »**, avec le reste rendu **visible**.

### 6. Amende le diagnostic si le code le contredit

La passe E a corrigé cinq de ses propres constats en cours de traitement : une
conséquence annoncée qui n'existait pas, une deuxième cause non vue, un constat
déjà réglé, un diagnostic faux, un fichier déclaré manquant qui existait. Si le
code contredit l'énoncé, **écris-le** — c'est plus utile qu'un constat
maintenu.

## Ce qu'il ne faut pas signaler

**Les choix de modèle assumés :**

- comptabilité sans comptes de tiers ni trésorerie, contrepartie unique
  `108000` — les cases 156, 166 et 068/070 du bilan restent vides, et
  l'équilibre tient parce que les deux omissions se compensent ;
- résultat fiscal LMNP **exclu de la ligne 352** du 2033-B, déclaré en
  2031 bis — la ligne 352 doit donc valoir zéro, c'est voulu et contrôlé ;
- `verifier_depot.py` refuse délibérément de conclure sur un runner
  d'intégration continue, faute d'empreintes : c'est un geste **local**, avant
  push.

**Ce qui est déjà corrigé.** Six passes ont traité : lecture/validation/
migration FEC, cycle de vie du dossier, liasse d'un exercice de cession, couche
web et ligne de commande, import bancaire + liasse PDF + plan de comptes,
chaîne de distribution. Le `CHANGELOG.md` et `docs/AUDIT_PASSE_*.md` en portent
le détail — **lis le récapitulatif de la passe concernée avant de commencer**,
et ne resignale pas ce qui y figure comme corrigé.

## Une consigne de sécurité, non négociable

Le répertoire de travail contient en permanence les données comptables
**réelles** de l'auteur : `reference/` (FEC réels), `seed_exemple.sql`
(identité), `reference/termes_a_anonymiser.txt`.

**Ne recopie JAMAIS une valeur réelle dans ton rapport** — ni nom, ni SIREN, ni
adresse, ni nom de rue, ni nom de tiers. Construis tes scénarios sur une
identité **fictive**. Si tu dois citer une donnée réelle pour désigner un
défaut, écris « le nom de l'exploitant », pas le nom.

Cette faute a été commise deux fois : un nom recopié depuis un rapport dans un
test, puis une adresse écrite en clair dans le rapport **qui décrivait
précisément cette faute**. Le contrôle de publication l'a bloquée les deux
fois — mais un rapport d'audit n'a pas à en dépendre.

## Livrable

Un fichier Markdown, à déposer dans `docs/`, nommé `AUDIT_PASSE_<lettre>.md`.
Les constats numérotés `<lettre>-01`, `<lettre>-02`…


---

# Passe R — Propriété intellectuelle, licence et redistribution

**Joindre `00-INVARIANTS.md` avant ce prompt.**

Cette passe diffère des autres : elle n'audite pas un calcul, elle audite ce
que le dépôt **affirme** — sur qui détient quoi, sous quelles conditions, et
avec quelles obligations envers des tiers. Le registre attendu n'est donc pas
« un chiffre faux sur une déclaration » mais : **une affirmation de conformité
qui ne tient pas**, ou **une obligation contractée sans être remplie**.

Le format imposé par les invariants s'applique tel quel — scénario
reproductible, attendu contre produit, fichier et ligne, gravité. Ce qui change
est la nature du « produit » : ici, la sortie réelle est souvent le **contenu
d'un livrable** (ce que contient le zip, ce que voit l'utilisateur, ce que
déclare un paquet installé), pas l'exécution d'une fonction.

## Pièces à joindre

| Fichier | Lignes |
|---|---|
| `LICENSE` (racine du dépôt) | 661 |
| `README.md` (racine) | 142 |
| `NOTICES-TIERS.md` (racine) | 61 |
| `CONTRIBUTING.md` (racine) | 100 |
| `compta_lmnp/LISEZ-MOI.md` | 616 |
| `compta_lmnp/construire_distribution.py` | 213 |
| `compta_lmnp/requirements-dev.txt` | 21 |
| `compta_lmnp/Compta-LMNP-Linux-macOS.sh` | 448 |
| `compta_lmnp/Compta-LMNP-Windows.bat` | 129 |
| `compta_lmnp/outils_sprite.py` | 183 |
| `compta_lmnp/modules/pense_bete.py` | 570 |
| `compta_lmnp/modules/veille_fiscale.py` | 274 |
| `compta_lmnp/modules/parametres.py` | 296 |
| `compta_lmnp/modules/gabarits.py` | 285 |
| `compta_lmnp/modules/liasse_pdf.py` | 524 |
| `compta_lmnp/modules/pages.py` | 2434 |

Et, si l'environnement le permet : la sortie de `pip show` sur les dépendances
installées, et le **contenu du zip** produit par `python build_client.py`.

---

## Le prompt

Ce logiciel vient de passer d'une licence maison — « gratuit, revente et
modification diffusée interdites » — à l'**AGPL-3.0-or-later** (version
8.51.0). Il est sur le point d'être publié dans un dépôt **public**, après
avoir vécu deux ans dans un dépôt privé.

Trois conséquences gouvernent cette passe.

1. **Une publication ne se rétracte pas.** Un fichier poussé reste dans
   l'historique git après suppression, et dans les clones déjà faits. Ce qui
   est mal licencié au moment de la publication le reste.
2. **Le projet contracte désormais des obligations envers des tiers** — envers
   les auteurs des composants qu'il utilise, et envers ses propres
   utilisateurs, à qui l'AGPL promet un accès au code source. Une obligation
   annoncée et non remplie est pire qu'une obligation non prise.
3. **Le changement de licence est récent.** Les contradictions résiduelles
   sont l'angle le plus probable : un document qui n'a pas été relu, un
   en-tête oublié, une phrase qui décrit encore l'ancien modèle.

### Ce que je te demande de chercher

**A. La licence dit-elle une seule chose, partout ?**

- Le dépôt contient-il, en un seul endroit faisant foi, le texte **intégral**
  de l'AGPL-3.0 ? Compare-le au texte canonique de la FSF : une licence
  tronquée, reformulée ou « résumée » ne concède pas ce qu'elle a l'air de
  concéder. La clause 13 (interaction réseau) est-elle bien là ? C'est elle
  qui distingue l'AGPL de la GPL, et c'est la seule qui compte vraiment pour
  une application qui est un serveur web.
- Cherche les **restes de l'ancien modèle** : « tous droits réservés »,
  « revente interdite », « logiciel propriétaire », « paquet officiel
  intact », « avant toute vente », « mode à livrer en cas de revente ». Ils
  ont été traqués, mais une liste de motifs écrite à la main ne peut pas
  signaler ce qu'on a oublié d'y mettre (invariant n°5). Cherche plutôt
  l'inverse : **quels documents n'ont manifestement pas été relus** depuis le
  changement ?
- Les fichiers portent-ils **tous** un `SPDX-License-Identifier` ? Et les
  fichiers **non Python** — `.sh`, `.bat`, `.sql`, `.desktop`, `.toml`, `.md`,
  les gabarits HTML enfouis dans `pages.py` ? Un fichier sans mention de
  licence, dans un dépôt public, se lit « tous droits réservés » par défaut.
- Le dépôt mélange-t-il des régimes différents sans le dire : le code sous
  AGPL, mais les **documents** (`docs/`, rapports d'audit, `CHANGELOG.md`) et
  les **données** (`seed_referentiel.sql`, plan de comptes, gabarits
  d'écritures) sous quoi ? Une licence de code ne couvre pas naturellement une
  base de données ni une documentation. Est-ce voulu, dit, ou simplement non
  pensé ?

**B. Qui détient les droits — et le projet peut-il prouver ce qu'il affirme ?**

- L'auteur affirme détenir les droits sur l'ensemble. Cherche dans le code ce
  qui **ne vient manifestement pas de lui** : un bloc au style étranger au
  reste, des commentaires en anglais dans un projet intégralement en français,
  un algorithme trop idiomatique pour être écrit de zéro, une constante ou une
  table recopiée. Signale ce que tu trouves **comme une question d'origine**,
  jamais comme une accusation.
- Le projet a été écrit en partie **avec l'assistance d'une IA** (les rapports
  d'audit de `docs/` en portent la trace). En droit français, une production
  sans intervention humaine créatrice n'est pas protégeable par le droit
  d'auteur, et la titularité d'un code assisté par IA est discutée. Quelle est
  la conséquence pratique pour un projet qui revendique un copyright et impose
  une licence à réciprocité ? Formule-la en **question**, dans la section
  prévue — ce n'est pas à toi de trancher un point de droit ouvert.
- `CONTRIBUTING.md` retient le **DCO** plutôt qu'une cession de droits. Le
  dispositif est-il complet : le texte du DCO est-il accessible, la
  vérification des `Signed-off-by` est-elle outillée ou seulement annoncée ?
  Une exigence annoncée et jamais contrôlée est une exigence qui n'existe pas
  — c'est le même défaut de principe qu'un garde-fou qui approuve sans
  vérifier (invariant n°4).
- Le copyright dit « Sylvain FAURE **et les contributeurs** » alors qu'il n'y
  a encore aucun contributeur extérieur. Est-ce exact, prématuré, ou sans
  conséquence ?

**C. Les composants tiers : la liste est-elle vraie, et surtout complète ?**

C'est l'endroit où une liste écrite à la main fait le plus de dégâts, et
`NOTICES-TIERS.md` **est** une liste écrite à la main.

- Reconstitue la liste réelle des dépendances **par lecture des imports et des
  installations**, pas par lecture de `NOTICES-TIERS.md` : que demandent les
  lanceurs `.sh` et `.bat` ? que contient `requirements-dev.txt` ? qu'importe
  réellement le code ? Compare ensuite. Qu'est-ce qui manque — y compris les
  dépendances **transitives**, que personne n'a choisies et qui arrivent
  quand même sur la machine de l'utilisateur ?
- Les licences annoncées sont-elles celles que les paquets **déclarent
  eux-mêmes** (métadonnées, fichier de licence livré), ou celles qu'on croit
  se rappeler ? Vérifie au moins Flask et reportlab. Une licence supposée est
  une licence non vérifiée.
- Y a-t-il un composant sous licence **à réciprocité ou non commerciale**
  quelque part — une police de caractères, une icône, un fragment de CSS, un
  jeu de sprites (`outils_sprite.py`), un extrait de code dans un gabarit de
  `pages.py` ? Ce sont les actifs **non-code** qui échappent aux inventaires
  de dépendances.
- `NOTICES-TIERS.md` affirme qu'aucun composant sous GPL ou assimilée n'est
  utilisé. Cette affirmation est-elle vérifiable avec les pièces fournies, ou
  est-ce une croyance ? Si elle n'est pas vérifiable, dis-le : une déclaration
  de conformité invérifiable est un constat en soi.

**D. Les obligations de redistribution sont-elles réellement remplies ?**

La distinction qui commande tout : le projet **redistribue-t-il** un composant
tiers, ou l'utilisateur l'installe-t-il lui-même ? Le paquet client ne devrait
rien redistribuer ; l'exécutable PyInstaller le faisait, ce pour quoi il a été
retiré.

- Construis le paquet et **regarde dedans** — ne te fie pas à la liste `DOCS`
  de `construire_distribution.py`. `LICENSE.txt` y est-il, complet, identique
  au `LICENSE` de la racine ? L'AGPL (art. 4) impose de livrer la licence
  **avec** le programme : le zip est une distribution à part entière.
- Le paquet contient-il un composant tiers que personne n'a remarqué —
  une bibliothèque vendorisée, un fichier minifié, une police, un binaire ?
- **L'article 13, matériellement.** L'application est un serveur web local. Le
  pied de page annonce un lien « code source ». Ce lien pointe-t-il vers un
  dépôt **réellement accessible** et correspondant à la **version installée** ?
  Que se passe-t-il pour un utilisateur qui a modifié son exemplaire — le
  logiciel lui offre-t-il un moyen de fournir **sa** source, ou l'AGPL est-elle
  respectée seulement tant que personne ne modifie rien ?
- L'article 5 impose que les fichiers modifiés portent une mention visible de
  modification. Le projet prévoit-il quoi que ce soit pour un forkeur, ou
  est-ce laissé à sa bonne volonté ?

**E. Les actifs qui ne sont pas du code.**

Angle qu'aucune passe n'a couvert, et le plus susceptible de rapporter.

- Le logiciel reproduit des **formulaires administratifs** : numéros de case
  des liasses 2031/2033, du 2042-C-PRO, libellés officiels, structure du FEC.
  Quel est le régime de ces éléments ? Les documents administratifs français
  relèvent d'un régime de réutilisation libre, mais le vérifier vaut mieux que
  le supposer — et la question se pose différemment pour un **numéro de case**
  (donnée factuelle), un **libellé recopié** (texte) et une **mise en page
  reproduite** (`liasse_pdf.py`).
- `pense_bete.py`, `veille_fiscale.py` et `parametres.py` contiennent des
  textes réglementaires, des références au BOFiP, des seuils datés. Ces textes
  sont-ils **recopiés** ou **reformulés** ? Le régime n'est pas le même, et une
  reformulation approximative d'un texte fiscal est aussi un risque d'erreur —
  double motif de le signaler.
- Le plan de comptes, les 37 gabarits d'écritures, le référentiel : œuvre de
  l'auteur, ou dérivés d'une source existante (plan comptable général, plan
  d'un cabinet, jeu de gabarits d'un logiciel du marché) ?
- Les **marques** : le nom « Compta LMNP » est-il revendiqué quelque part comme
  une marque, alors qu'il est purement descriptif et non déposé ? Le dépôt
  cite-t-il des marques de tiers — banques (mots-clés de l'import bancaire),
  logiciels concurrents, PayPal, Windows, systèmes d'exploitation — et le
  fait-il de façon qui puisse laisser croire à une affiliation ou à une
  comparaison dénigrante ? Le document d'accueil a annoncé vouloir
  « remplacer les logiciels du marché » : cette formulation est-elle tenable
  telle quelle ?

### Points d'attention nommés

- **La question qui gouverne cette passe : le dépôt promet-il quelque chose
  qu'il ne tient pas ?** Une licence est une promesse faite au lecteur, une
  notice une promesse faite à un auteur tiers, un lien « code source » une
  promesse faite à l'utilisateur. Cherche les promesses, puis vérifie-les une
  à une — c'est l'équivalent, pour cette passe, du « reproduis par exécution »
  des autres.
- **Une affirmation fausse a déjà été trouvée exactement ici**, et elle avait
  survécu des mois : le document d'accueil soutenait, dans sa section licence,
  que le logiciel n'utilisait « que la bibliothèque standard de Python » alors
  que Flask est une dépendance d'exécution obligatoire. Elle n'a pas été
  détectée parce que personne ne relit une phrase qu'il a écrite. Traite tout
  énoncé de conformité comme suspect **par construction**, et va chercher son
  contraire dans le code.
- **Ne conclus pas au vert par défaut.** Si tu ne peux pas vérifier la licence
  réelle d'un composant avec les pièces fournies, ce n'est pas « conforme » :
  c'est « non vérifiable », et ça va dans la section prévue, sous forme de
  question. Un audit de conformité qui approuve faute d'avoir pu vérifier est
  le défaut que ce projet chasse partout ailleurs.
- **Tu n'es pas juriste, et ce rapport n'est pas un avis juridique.** Distingue
  systématiquement ce qui est **vérifiable dans le dépôt** (un fichier manque,
  un texte se contredit, une notice est absente) de ce qui **relève de
  l'appréciation d'un conseil** (la titularité d'un code assisté par IA,
  l'opposabilité d'une clause, le risque de marque). Les premiers sont des
  constats ; les seconds sont des questions. Ne les mélange pas — un constat
  juridique mal fondé ferait perdre plus de temps qu'il n'en fait gagner.
- Rappel de la consigne de sécurité des invariants : elle s'applique
  intégralement ici. Le dossier de travail contient des données réelles, et
  cette passe t'amènera à lire des fichiers de configuration et des seeds.
  **Aucune valeur réelle dans le rapport.**


---

# Les pièces (16)


## `LICENSE`

````
                    GNU AFFERO GENERAL PUBLIC LICENSE
                       Version 3, 19 November 2007

 Copyright (C) 2007 Free Software Foundation, Inc. <https://fsf.org/>
 Everyone is permitted to copy and distribute verbatim copies
 of this license document, but changing it is not allowed.

                            Preamble

  The GNU Affero General Public License is a free, copyleft license for
software and other kinds of works, specifically designed to ensure
cooperation with the community in the case of network server software.

  The licenses for most software and other practical works are designed
to take away your freedom to share and change the works.  By contrast,
our General Public Licenses are intended to guarantee your freedom to
share and change all versions of a program--to make sure it remains free
software for all its users.

  When we speak of free software, we are referring to freedom, not
price.  Our General Public Licenses are designed to make sure that you
have the freedom to distribute copies of free software (and charge for
them if you wish), that you receive source code or can get it if you
want it, that you can change the software or use pieces of it in new
free programs, and that you know you can do these things.

  Developers that use our General Public Licenses protect your rights
with two steps: (1) assert copyright on the software, and (2) offer
you this License which gives you legal permission to copy, distribute
and/or modify the software.

  A secondary benefit of defending all users' freedom is that
improvements made in alternate versions of the program, if they
receive widespread use, become available for other developers to
incorporate.  Many developers of free software are heartened and
encouraged by the resulting cooperation.  However, in the case of
software used on network servers, this result may fail to come about.
The GNU General Public License permits making a modified version and
letting the public access it on a server without ever releasing its
source code to the public.

  The GNU Affero General Public License is designed specifically to
ensure that, in such cases, the modified source code becomes available
to the community.  It requires the operator of a network server to
provide the source code of the modified version running there to the
users of that server.  Therefore, public use of a modified version, on
a publicly accessible server, gives the public access to the source
code of the modified version.

  An older license, called the Affero General Public License and
published by Affero, was designed to accomplish similar goals.  This is
a different license, not a version of the Affero GPL, but Affero has
released a new version of the Affero GPL which permits relicensing under
this license.

  The precise terms and conditions for copying, distribution and
modification follow.

                       TERMS AND CONDITIONS

  0. Definitions.

  "This License" refers to version 3 of the GNU Affero General Public License.

  "Copyright" also means copyright-like laws that apply to other kinds of
works, such as semiconductor masks.

  "The Program" refers to any copyrightable work licensed under this
License.  Each licensee is addressed as "you".  "Licensees" and
"recipients" may be individuals or organizations.

  To "modify" a work means to copy from or adapt all or part of the work
in a fashion requiring copyright permission, other than the making of an
exact copy.  The resulting work is called a "modified version" of the
earlier work or a work "based on" the earlier work.

  A "covered work" means either the unmodified Program or a work based
on the Program.

  To "propagate" a work means to do anything with it that, without
permission, would make you directly or secondarily liable for
infringement under applicable copyright law, except executing it on a
computer or modifying a private copy.  Propagation includes copying,
distribution (with or without modification), making available to the
public, and in some countries other activities as well.

  To "convey" a work means any kind of propagation that enables other
parties to make or receive copies.  Mere interaction with a user through
a computer network, with no transfer of a copy, is not conveying.

  An interactive user interface displays "Appropriate Legal Notices"
to the extent that it includes a convenient and prominently visible
feature that (1) displays an appropriate copyright notice, and (2)
tells the user that there is no warranty for the work (except to the
extent that warranties are provided), that licensees may convey the
work under this License, and how to view a copy of this License.  If
the interface presents a list of user commands or options, such as a
menu, a prominent item in the list meets this criterion.

  1. Source Code.

  The "source code" for a work means the preferred form of the work
for making modifications to it.  "Object code" means any non-source
form of a work.

  A "Standard Interface" means an interface that either is an official
standard defined by a recognized standards body, or, in the case of
interfaces specified for a particular programming language, one that
is widely used among developers working in that language.

  The "System Libraries" of an executable work include anything, other
than the work as a whole, that (a) is included in the normal form of
packaging a Major Component, but which is not part of that Major
Component, and (b) serves only to enable use of the work with that
Major Component, or to implement a Standard Interface for which an
implementation is available to the public in source code form.  A
"Major Component", in this context, means a major essential component
(kernel, window system, and so on) of the specific operating system
(if any) on which the executable work runs, or a compiler used to
produce the work, or an object code interpreter used to run it.

  The "Corresponding Source" for a work in object code form means all
the source code needed to generate, install, and (for an executable
work) run the object code and to modify the work, including scripts to
control those activities.  However, it does not include the work's
System Libraries, or general-purpose tools or generally available free
programs which are used unmodified in performing those activities but
which are not part of the work.  For example, Corresponding Source
includes interface definition files associated with source files for
the work, and the source code for shared libraries and dynamically
linked subprograms that the work is specifically designed to require,
such as by intimate data communication or control flow between those
subprograms and other parts of the work.

  The Corresponding Source need not include anything that users
can regenerate automatically from other parts of the Corresponding
Source.

  The Corresponding Source for a work in source code form is that
same work.

  2. Basic Permissions.

  All rights granted under this License are granted for the term of
copyright on the Program, and are irrevocable provided the stated
conditions are met.  This License explicitly affirms your unlimited
permission to run the unmodified Program.  The output from running a
covered work is covered by this License only if the output, given its
content, constitutes a covered work.  This License acknowledges your
rights of fair use or other equivalent, as provided by copyright law.

  You may make, run and propagate covered works that you do not
convey, without conditions so long as your license otherwise remains
in force.  You may convey covered works to others for the sole purpose
of having them make modifications exclusively for you, or provide you
with facilities for running those works, provided that you comply with
the terms of this License in conveying all material for which you do
not control copyright.  Those thus making or running the covered works
for you must do so exclusively on your behalf, under your direction
and control, on terms that prohibit them from making any copies of
your copyrighted material outside their relationship with you.

  Conveying under any other circumstances is permitted solely under
the conditions stated below.  Sublicensing is not allowed; section 10
makes it unnecessary.

  3. Protecting Users' Legal Rights From Anti-Circumvention Law.

  No covered work shall be deemed part of an effective technological
measure under any applicable law fulfilling obligations under article
11 of the WIPO copyright treaty adopted on 20 December 1996, or
similar laws prohibiting or restricting circumvention of such
measures.

  When you convey a covered work, you waive any legal power to forbid
circumvention of technological measures to the extent such circumvention
is effected by exercising rights under this License with respect to
the covered work, and you disclaim any intention to limit operation or
modification of the work as a means of enforcing, against the work's
users, your or third parties' legal rights to forbid circumvention of
technological measures.

  4. Conveying Verbatim Copies.

  You may convey verbatim copies of the Program's source code as you
receive it, in any medium, provided that you conspicuously and
appropriately publish on each copy an appropriate copyright notice;
keep intact all notices stating that this License and any
non-permissive terms added in accord with section 7 apply to the code;
keep intact all notices of the absence of any warranty; and give all
recipients a copy of this License along with the Program.

  You may charge any price or no price for each copy that you convey,
and you may offer support or warranty protection for a fee.

  5. Conveying Modified Source Versions.

  You may convey a work based on the Program, or the modifications to
produce it from the Program, in the form of source code under the
terms of section 4, provided that you also meet all of these conditions:

    a) The work must carry prominent notices stating that you modified
    it, and giving a relevant date.

    b) The work must carry prominent notices stating that it is
    released under this License and any conditions added under section
    7.  This requirement modifies the requirement in section 4 to
    "keep intact all notices".

    c) You must license the entire work, as a whole, under this
    License to anyone who comes into possession of a copy.  This
    License will therefore apply, along with any applicable section 7
    additional terms, to the whole of the work, and all its parts,
    regardless of how they are packaged.  This License gives no
    permission to license the work in any other way, but it does not
    invalidate such permission if you have separately received it.

    d) If the work has interactive user interfaces, each must display
    Appropriate Legal Notices; however, if the Program has interactive
    interfaces that do not display Appropriate Legal Notices, your
    work need not make them do so.

  A compilation of a covered work with other separate and independent
works, which are not by their nature extensions of the covered work,
and which are not combined with it such as to form a larger program,
in or on a volume of a storage or distribution medium, is called an
"aggregate" if the compilation and its resulting copyright are not
used to limit the access or legal rights of the compilation's users
beyond what the individual works permit.  Inclusion of a covered work
in an aggregate does not cause this License to apply to the other
parts of the aggregate.

  6. Conveying Non-Source Forms.

  You may convey a covered work in object code form under the terms
of sections 4 and 5, provided that you also convey the
machine-readable Corresponding Source under the terms of this License,
in one of these ways:

    a) Convey the object code in, or embodied in, a physical product
    (including a physical distribution medium), accompanied by the
    Corresponding Source fixed on a durable physical medium
    customarily used for software interchange.

    b) Convey the object code in, or embodied in, a physical product
    (including a physical distribution medium), accompanied by a
    written offer, valid for at least three years and valid for as
    long as you offer spare parts or customer support for that product
    model, to give anyone who possesses the object code either (1) a
    copy of the Corresponding Source for all the software in the
    product that is covered by this License, on a durable physical
    medium customarily used for software interchange, for a price no
    more than your reasonable cost of physically performing this
    conveying of source, or (2) access to copy the
    Corresponding Source from a network server at no charge.

    c) Convey individual copies of the object code with a copy of the
    written offer to provide the Corresponding Source.  This
    alternative is allowed only occasionally and noncommercially, and
    only if you received the object code with such an offer, in accord
    with subsection 6b.

    d) Convey the object code by offering access from a designated
    place (gratis or for a charge), and offer equivalent access to the
    Corresponding Source in the same way through the same place at no
    further charge.  You need not require recipients to copy the
    Corresponding Source along with the object code.  If the place to
    copy the object code is a network server, the Corresponding Source
    may be on a different server (operated by you or a third party)
    that supports equivalent copying facilities, provided you maintain
    clear directions next to the object code saying where to find the
    Corresponding Source.  Regardless of what server hosts the
    Corresponding Source, you remain obligated to ensure that it is
    available for as long as needed to satisfy these requirements.

    e) Convey the object code using peer-to-peer transmission, provided
    you inform other peers where the object code and Corresponding
    Source of the work are being offered to the general public at no
    charge under subsection 6d.

  A separable portion of the object code, whose source code is excluded
from the Corresponding Source as a System Library, need not be
included in conveying the object code work.

  A "User Product" is either (1) a "consumer product", which means any
tangible personal property which is normally used for personal, family,
or household purposes, or (2) anything designed or sold for incorporation
into a dwelling.  In determining whether a product is a consumer product,
doubtful cases shall be resolved in favor of coverage.  For a particular
product received by a particular user, "normally used" refers to a
typical or common use of that class of product, regardless of the status
of the particular user or of the way in which the particular user
actually uses, or expects or is expected to use, the product.  A product
is a consumer product regardless of whether the product has substantial
commercial, industrial or non-consumer uses, unless such uses represent
the only significant mode of use of the product.

  "Installation Information" for a User Product means any methods,
procedures, authorization keys, or other information required to install
and execute modified versions of a covered work in that User Product from
a modified version of its Corresponding Source.  The information must
suffice to ensure that the continued functioning of the modified object
code is in no case prevented or interfered with solely because
modification has been made.

  If you convey an object code work under this section in, or with, or
specifically for use in, a User Product, and the conveying occurs as
part of a transaction in which the right of possession and use of the
User Product is transferred to the recipient in perpetuity or for a
fixed term (regardless of how the transaction is characterized), the
Corresponding Source conveyed under this section must be accompanied
by the Installation Information.  But this requirement does not apply
if neither you nor any third party retains the ability to install
modified object code on the User Product (for example, the work has
been installed in ROM).

  The requirement to provide Installation Information does not include a
requirement to continue to provide support service, warranty, or updates
for a work that has been modified or installed by the recipient, or for
the User Product in which it has been modified or installed.  Access to a
network may be denied when the modification itself materially and
adversely affects the operation of the network or violates the rules and
protocols for communication across the network.

  Corresponding Source conveyed, and Installation Information provided,
in accord with this section must be in a format that is publicly
documented (and with an implementation available to the public in
source code form), and must require no special password or key for
unpacking, reading or copying.

  7. Additional Terms.

  "Additional permissions" are terms that supplement the terms of this
License by making exceptions from one or more of its conditions.
Additional permissions that are applicable to the entire Program shall
be treated as though they were included in this License, to the extent
that they are valid under applicable law.  If additional permissions
apply only to part of the Program, that part may be used separately
under those permissions, but the entire Program remains governed by
this License without regard to the additional permissions.

  When you convey a copy of a covered work, you may at your option
remove any additional permissions from that copy, or from any part of
it.  (Additional permissions may be written to require their own
removal in certain cases when you modify the work.)  You may place
additional permissions on material, added by you to a covered work,
for which you have or can give appropriate copyright permission.

  Notwithstanding any other provision of this License, for material you
add to a covered work, you may (if authorized by the copyright holders of
that material) supplement the terms of this License with terms:

    a) Disclaiming warranty or limiting liability differently from the
    terms of sections 15 and 16 of this License; or

    b) Requiring preservation of specified reasonable legal notices or
    author attributions in that material or in the Appropriate Legal
    Notices displayed by works containing it; or

    c) Prohibiting misrepresentation of the origin of that material, or
    requiring that modified versions of such material be marked in
    reasonable ways as different from the original version; or

    d) Limiting the use for publicity purposes of names of licensors or
    authors of the material; or

    e) Declining to grant rights under trademark law for use of some
    trade names, trademarks, or service marks; or

    f) Requiring indemnification of licensors and authors of that
    material by anyone who conveys the material (or modified versions of
    it) with contractual assumptions of liability to the recipient, for
    any liability that these contractual assumptions directly impose on
    those licensors and authors.

  All other non-permissive additional terms are considered "further
restrictions" within the meaning of section 10.  If the Program as you
received it, or any part of it, contains a notice stating that it is
governed by this License along with a term that is a further
restriction, you may remove that term.  If a license document contains
a further restriction but permits relicensing or conveying under this
License, you may add to a covered work material governed by the terms
of that license document, provided that the further restriction does
not survive such relicensing or conveying.

  If you add terms to a covered work in accord with this section, you
must place, in the relevant source files, a statement of the
additional terms that apply to those files, or a notice indicating
where to find the applicable terms.

  Additional terms, permissive or non-permissive, may be stated in the
form of a separately written license, or stated as exceptions;
the above requirements apply either way.

  8. Termination.

  You may not propagate or modify a covered work except as expressly
provided under this License.  Any attempt otherwise to propagate or
modify it is void, and will automatically terminate your rights under
this License (including any patent licenses granted under the third
paragraph of section 11).

  However, if you cease all violation of this License, then your
license from a particular copyright holder is reinstated (a)
provisionally, unless and until the copyright holder explicitly and
finally terminates your license, and (b) permanently, if the copyright
holder fails to notify you of the violation by some reasonable means
prior to 60 days after the cessation.

  Moreover, your license from a particular copyright holder is
reinstated permanently if the copyright holder notifies you of the
violation by some reasonable means, this is the first time you have
received notice of violation of this License (for any work) from that
copyright holder, and you cure the violation prior to 30 days after
your receipt of the notice.

  Termination of your rights under this section does not terminate the
licenses of parties who have received copies or rights from you under
this License.  If your rights have been terminated and not permanently
reinstated, you do not qualify to receive new licenses for the same
material under section 10.

  9. Acceptance Not Required for Having Copies.

  You are not required to accept this License in order to receive or
run a copy of the Program.  Ancillary propagation of a covered work
occurring solely as a consequence of using peer-to-peer transmission
to receive a copy likewise does not require acceptance.  However,
nothing other than this License grants you permission to propagate or
modify any covered work.  These actions infringe copyright if you do
not accept this License.  Therefore, by modifying or propagating a
covered work, you indicate your acceptance of this License to do so.

  10. Automatic Licensing of Downstream Recipients.

  Each time you convey a covered work, the recipient automatically
receives a license from the original licensors, to run, modify and
propagate that work, subject to this License.  You are not responsible
for enforcing compliance by third parties with this License.

  An "entity transaction" is a transaction transferring control of an
organization, or substantially all assets of one, or subdividing an
organization, or merging organizations.  If propagation of a covered
work results from an entity transaction, each party to that
transaction who receives a copy of the work also receives whatever
licenses to the work the party's predecessor in interest had or could
give under the previous paragraph, plus a right to possession of the
Corresponding Source of the work from the predecessor in interest, if
the predecessor has it or can get it with reasonable efforts.

  You may not impose any further restrictions on the exercise of the
rights granted or affirmed under this License.  For example, you may
not impose a license fee, royalty, or other charge for exercise of
rights granted under this License, and you may not initiate litigation
(including a cross-claim or counterclaim in a lawsuit) alleging that
any patent claim is infringed by making, using, selling, offering for
sale, or importing the Program or any portion of it.

  11. Patents.

  A "contributor" is a copyright holder who authorizes use under this
License of the Program or a work on which the Program is based.  The
work thus licensed is called the contributor's "contributor version".

  A contributor's "essential patent claims" are all patent claims
owned or controlled by the contributor, whether already acquired or
hereafter acquired, that would be infringed by some manner, permitted
by this License, of making, using, or selling its contributor version,
but do not include claims that would be infringed only as a
consequence of further modification of the contributor version.  For
purposes of this definition, "control" includes the right to grant
patent sublicenses in a manner consistent with the requirements of
this License.

  Each contributor grants you a non-exclusive, worldwide, royalty-free
patent license under the contributor's essential patent claims, to
make, use, sell, offer for sale, import and otherwise run, modify and
propagate the contents of its contributor version.

  In the following three paragraphs, a "patent license" is any express
agreement or commitment, however denominated, not to enforce a patent
(such as an express permission to practice a patent or covenant not to
sue for patent infringement).  To "grant" such a patent license to a
party means to make such an agreement or commitment not to enforce a
patent against the party.

  If you convey a covered work, knowingly relying on a patent license,
and the Corresponding Source of the work is not available for anyone
to copy, free of charge and under the terms of this License, through a
publicly available network server or other readily accessible means,
then you must either (1) cause the Corresponding Source to be so
available, or (2) arrange to deprive yourself of the benefit of the
patent license for this particular work, or (3) arrange, in a manner
consistent with the requirements of this License, to extend the patent
license to downstream recipients.  "Knowingly relying" means you have
actual knowledge that, but for the patent license, your conveying the
covered work in a country, or your recipient's use of the covered work
in a country, would infringe one or more identifiable patents in that
country that you have reason to believe are valid.

  If, pursuant to or in connection with a single transaction or
arrangement, you convey, or propagate by procuring conveyance of, a
covered work, and grant a patent license to some of the parties
receiving the covered work authorizing them to use, propagate, modify
or convey a specific copy of the covered work, then the patent license
you grant is automatically extended to all recipients of the covered
work and works based on it.

  A patent license is "discriminatory" if it does not include within
the scope of its coverage, prohibits the exercise of, or is
conditioned on the non-exercise of one or more of the rights that are
specifically granted under this License.  You may not convey a covered
work if you are a party to an arrangement with a third party that is
in the business of distributing software, under which you make payment
to the third party based on the extent of your activity of conveying
the work, and under which the third party grants, to any of the
parties who would receive the covered work from you, a discriminatory
patent license (a) in connection with copies of the covered work
conveyed by you (or copies made from those copies), or (b) primarily
for and in connection with specific products or compilations that
contain the covered work, unless you entered into that arrangement,
or that patent license was granted, prior to 28 March 2007.

  Nothing in this License shall be construed as excluding or limiting
any implied license or other defenses to infringement that may
otherwise be available to you under applicable patent law.

  12. No Surrender of Others' Freedom.

  If conditions are imposed on you (whether by court order, agreement or
otherwise) that contradict the conditions of this License, they do not
excuse you from the conditions of this License.  If you cannot convey a
covered work so as to satisfy simultaneously your obligations under this
License and any other pertinent obligations, then as a consequence you may
not convey it at all.  For example, if you agree to terms that obligate you
to collect a royalty for further conveying from those to whom you convey
the Program, the only way you could satisfy both those terms and this
License would be to refrain entirely from conveying the Program.

  13. Remote Network Interaction; Use with the GNU General Public License.

  Notwithstanding any other provision of this License, if you modify the
Program, your modified version must prominently offer all users
interacting with it remotely through a computer network (if your version
supports such interaction) an opportunity to receive the Corresponding
Source of your version by providing access to the Corresponding Source
from a network server at no charge, through some standard or customary
means of facilitating copying of software.  This Corresponding Source
shall include the Corresponding Source for any work covered by version 3
of the GNU General Public License that is incorporated pursuant to the
following paragraph.

  Notwithstanding any other provision of this License, you have
permission to link or combine any covered work with a work licensed
under version 3 of the GNU General Public License into a single
combined work, and to convey the resulting work.  The terms of this
License will continue to apply to the part which is the covered work,
but the work with which it is combined will remain governed by version
3 of the GNU General Public License.

  14. Revised Versions of this License.

  The Free Software Foundation may publish revised and/or new versions of
the GNU Affero General Public License from time to time.  Such new versions
will be similar in spirit to the present version, but may differ in detail to
address new problems or concerns.

  Each version is given a distinguishing version number.  If the
Program specifies that a certain numbered version of the GNU Affero General
Public License "or any later version" applies to it, you have the
option of following the terms and conditions either of that numbered
version or of any later version published by the Free Software
Foundation.  If the Program does not specify a version number of the
GNU Affero General Public License, you may choose any version ever published
by the Free Software Foundation.

  If the Program specifies that a proxy can decide which future
versions of the GNU Affero General Public License can be used, that proxy's
public statement of acceptance of a version permanently authorizes you
to choose that version for the Program.

  Later license versions may give you additional or different
permissions.  However, no additional obligations are imposed on any
author or copyright holder as a result of your choosing to follow a
later version.

  15. Disclaimer of Warranty.

  THERE IS NO WARRANTY FOR THE PROGRAM, TO THE EXTENT PERMITTED BY
APPLICABLE LAW.  EXCEPT WHEN OTHERWISE STATED IN WRITING THE COPYRIGHT
HOLDERS AND/OR OTHER PARTIES PROVIDE THE PROGRAM "AS IS" WITHOUT WARRANTY
OF ANY KIND, EITHER EXPRESSED OR IMPLIED, INCLUDING, BUT NOT LIMITED TO,
THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR
PURPOSE.  THE ENTIRE RISK AS TO THE QUALITY AND PERFORMANCE OF THE PROGRAM
IS WITH YOU.  SHOULD THE PROGRAM PROVE DEFECTIVE, YOU ASSUME THE COST OF
ALL NECESSARY SERVICING, REPAIR OR CORRECTION.

  16. Limitation of Liability.

  IN NO EVENT UNLESS REQUIRED BY APPLICABLE LAW OR AGREED TO IN WRITING
WILL ANY COPYRIGHT HOLDER, OR ANY OTHER PARTY WHO MODIFIES AND/OR CONVEYS
THE PROGRAM AS PERMITTED ABOVE, BE LIABLE TO YOU FOR DAMAGES, INCLUDING ANY
GENERAL, SPECIAL, INCIDENTAL OR CONSEQUENTIAL DAMAGES ARISING OUT OF THE
USE OR INABILITY TO USE THE PROGRAM (INCLUDING BUT NOT LIMITED TO LOSS OF
DATA OR DATA BEING RENDERED INACCURATE OR LOSSES SUSTAINED BY YOU OR THIRD
PARTIES OR A FAILURE OF THE PROGRAM TO OPERATE WITH ANY OTHER PROGRAMS),
EVEN IF SUCH HOLDER OR OTHER PARTY HAS BEEN ADVISED OF THE POSSIBILITY OF
SUCH DAMAGES.

  17. Interpretation of Sections 15 and 16.

  If the disclaimer of warranty and limitation of liability provided
above cannot be given local legal effect according to their terms,
reviewing courts shall apply local law that most closely approximates
an absolute waiver of all civil liability in connection with the
Program, unless a warranty or assumption of liability accompanies a
copy of the Program in return for a fee.

                     END OF TERMS AND CONDITIONS

            How to Apply These Terms to Your New Programs

  If you develop a new program, and you want it to be of the greatest
possible use to the public, the best way to achieve this is to make it
free software which everyone can redistribute and change under these terms.

  To do so, attach the following notices to the program.  It is safest
to attach them to the start of each source file to most effectively
state the exclusion of warranty; and each file should have at least
the "copyright" line and a pointer to where the full notice is found.

    <one line to give the program's name and a brief idea of what it does.>
    Copyright (C) <year>  <name of author>

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU Affero General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU Affero General Public License for more details.

    You should have received a copy of the GNU Affero General Public License
    along with this program.  If not, see <https://www.gnu.org/licenses/>.

Also add information on how to contact you by electronic and paper mail.

  If your software can interact with users remotely through a computer
network, you should also make sure that it provides a way for users to
get its source.  For example, if your program is a web application, its
interface could display a "Source" link that leads users to an archive
of the code.  There are many ways you could offer source, and different
solutions will be better for different programs; see section 13 for the
specific requirements.

  You should also get your employer (if you work as a programmer) or school,
if any, to sign a "copyright disclaimer" for the program, if necessary.
For more information on this, and how to apply and follow the GNU AGPL, see
<https://www.gnu.org/licenses/>.
````


## `README.md`

````markdown
# Compta LMNP

Logiciel de comptabilité **LMNP au réel** : tenue des écritures, amortissement
par composants, article 39 C, déficits reportables, liasse fiscale 2031/2033,
export FEC conforme, quittances de loyer. Il fonctionne **entièrement sur votre
machine** — rien n'est transmis nulle part.

Écrit par un particulier pour son propre usage, puis éprouvé contre des clôtures
réelles 2023-2025 au centime près, et audité passe par passe (voir
[`docs/audit/`](docs/audit/)).

- **Installation, mode d'emploi, architecture** →
  [`compta_lmnp/LISEZ-MOI.md`](compta_lmnp/LISEZ-MOI.md)
- **Journal des versions** → [`compta_lmnp/CHANGELOG.md`](compta_lmnp/CHANGELOG.md)
- **Rapports d'audit et preuves reproductibles** → [`docs/`](docs/)

---

## ⚠️ Avertissement — à lire avant tout usage

Les états produits (liasse fiscale, FEC, déclarations, quittances) sont des
**aides à la préparation**, pas des documents certifiés. La réglementation
fiscale évolue ; les calculs d'amortissement, la ventilation terrain/bâti, les
retraitements et la limitation de l'article 39 C doivent être **vérifiés, au
besoin par un professionnel qualifié, avant tout dépôt ou télédéclaration**.

Vous restez seul responsable de vos déclarations. Ce logiciel est fourni sans
aucune garantie (voir les articles 15 à 17 de la licence).

Ce logiciel ne fournit **aucun conseil comptable ou fiscal** et ne remplace pas
un expert-comptable : c'est un outil de saisie et de calcul.

## Licence

**GNU Affero General Public License v3.0 ou ultérieure (AGPL-3.0-or-later).**
Texte intégral dans [`LICENSE`](LICENSE) — c'est lui qui fait foi.

En français courant, et sans valeur contractuelle :

- vous pouvez **utiliser** ce logiciel pour ce que vous voulez, sans limite de
  durée ni de nombre de dossiers ;
- vous pouvez le **copier**, le **modifier**, le **forker** et le
  **redistribuer**, y compris **le vendre** ;
- en contrepartie, toute version que vous diffusez doit être publiée **sous la
  même licence, code source compris** — y compris si vous ne la distribuez pas
  mais la faites tourner comme **service en ligne** accessible à des tiers
  (c'est la clause 13, propre à l'AGPL) ;
- vous devez **conserver les mentions d'auteur** et signaler vos modifications.

Autrement dit : prenez, améliorez, vendez si vous voulez — mais ne refermez
pas. Ce qui a été ouvert le reste.

### Ce que la licence couvre

Une licence de code ne couvre pas d'elle-même la documentation ni les données,
et le dépôt contient les trois. Le périmètre est donc dit explicitement plutôt
que laissé à déduire (constat R-06) :

| Catégorie | Régime |
|---|---|
| Code source (`compta_lmnp/`, scripts, tests) | AGPL-3.0-or-later |
| Documentation (`*.md`, `docs/`, rapports d'audit et preuves) | AGPL-3.0-or-later |
| Référentiel et données d'exemple (`schema.sql`, `seed_referentiel.sql`, `seed_demo.sql`, `demo/FEC_DEMO_2025.txt`) | AGPL-3.0-or-later, en tant que partie du logiciel |
| **Vos** données comptables | **à vous.** La licence ne porte sur rien de ce que vous saisissez |
| Composants tiers | leurs propres licences — voir [`NOTICES-TIERS.md`](NOTICES-TIERS.md) |

Deux réserves, dites parce qu'elles sont réelles :

- **Le plan de comptes** suit la nomenclature du Plan comptable général. La
  sélection et les libellés retenus sont l'œuvre de l'auteur ; la nomenclature
  elle-même ne lui appartient pas.
- **Les numéros et libellés de cases** des formulaires 2031, 2033 et
  2042-C-PRO reproduisent des formulaires administratifs. Ce sont des données
  factuelles nécessaires à l'interopérabilité, et non une revendication de
  droits sur les formulaires.

### Obtenir le code source

L'article 13 de l'AGPL vous donne droit au code source correspondant à la
version que vous utilisez, y compris lorsque vous y accédez par le réseau. Le
pied de page de l'application porte le lien du dépôt.

> ⚠️ **Tant que ce dépôt n'est pas public, ce lien répond 404 à qui n'y a pas
> accès** (constat R-01). Le paquet client contient toutefois l'intégralité des
> sources de production : il n'existe aucune distribution binaire de ce
> logiciel. L'ouverture du dépôt est un prérequis de la publication, pas une
> conséquence — voir la liste de contrôle ci-dessous.

> **Pourquoi l'AGPL, et pas une licence maison « gratuit mais non revendable ».**
> Ce logiciel a d'abord été diffusé sous une licence maison qui interdisait la
> vente et les versions dérivées. Une telle licence n'est pas un logiciel
> libre — le premier critère de l'open source est justement la liberté de
> redistribution, vente comprise — et elle entrait en contradiction avec
> l'hébergement du code sur une plateforme publique, dont les conditions
> d'utilisation accordent à chacun le droit de forker. L'AGPL dit la même
> intention de fond, mais avec un texte éprouvé, opposable, et compris
> partout : la contrepartie de la liberté n'est pas l'interdiction de vendre,
> c'est l'obligation de rendre.

## Données personnelles (RGPD)

Le logiciel s'exécute en local et **ne transmet aucune donnée** à l'auteur ni à
un tiers : ni télémétrie, ni compte, ni synchronisation. Aucun serveur distant
n'est contacté. Les données restent dans un fichier SQLite sur votre disque.

Il n'y a donc **pas de transfert**, mais il y a bien un **traitement** :

- **Vous êtes le responsable de traitement** au sens du RGPD pour les données
  que vous saisissez — en particulier celles de **vos locataires** (identité,
  adresse, montants, périodes), qui sont des données personnelles de tiers.
- **Base légale** : l'exécution du contrat de bail et le respect de vos
  obligations légales (comptables et fiscales).
- **Durées de conservation** : les pièces comptables se conservent **10 ans**
  (art. L123-22 du Code de commerce) ; les quittances, au moins **3 ans** après
  la fin du bail, durée de la prescription des actions locatives (art. 7-1 de
  la loi du 6 juillet 1989). Au-delà, supprimez le dossier ou archivez-le hors
  ligne.
- **Droits des personnes** : vos locataires peuvent vous demander l'accès, la
  rectification ou l'effacement de leurs données — la demande s'adresse à
  **vous**, pas à l'auteur du logiciel, qui n'y a aucun accès. L'effacement ne
  peut pas porter sur ce que la loi vous oblige à conserver.
- **Sécurité** : la base n'est pas chiffrée. Si votre machine est partagée ou
  transportée, chiffrez le disque, et gardez vos sauvegardes hors ligne.
- **Sous-traitance** : aucune. Il n'y a personne d'autre dans la chaîne.

Un bailleur particulier n'a ni registre des traitements obligatoire (sauf
traitement à risque), ni DPO à désigner. En cas de doute :
[cnil.fr](https://www.cnil.fr).

## Dons

Le développement peut être soutenu par des **dons volontaires**. Un don est une
libéralité : il ne constitue ni un achat ni une souscription, ne confère aucun
droit supplémentaire (support, fonctionnalité, priorité, délai) et n'est pas
remboursable. Tout est déjà débloqué — il n'y a pas de version payante.

## Le nom « Compta LMNP »

Le nom est descriptif et n'est **pas déposé** : la licence AGPL porte sur le
code, pas sur la marque. Si vous publiez un fork substantiellement modifié,
donnez-lui un autre nom — l'usage veut qu'on ne laisse pas croire à
l'utilisateur qu'il installe l'original.

## Composants tiers

Le logiciel s'appuie sur Flask, Jinja2, Werkzeug, MarkupSafe, itsdangerous,
click, blinker et (facultativement) reportlab — licences BSD et MIT,
compatibles avec l'AGPL. Détail et textes : [`NOTICES-TIERS.md`](NOTICES-TIERS.md).

## Contribuer

Les signalements de défauts et les correctifs sont bienvenus — voir
[`CONTRIBUTING.md`](CONTRIBUTING.md). Deux exigences non négociables : **aucune
donnée réelle** dans une contribution, et **un test de non-régression** par
correctif.

## Liste de contrôle avant ouverture du dépôt

Trois gestes, dans cet ordre, et le premier conditionne les deux autres :

1. **Rendre le dépôt public.** Tant qu'il ne l'est pas, l'offre de source de
   l'article 13 n'est pas tenue (constat R-01).
2. **Poser le tag de version**, pour rattacher la source publiée à la version
   qui tourne chez l'utilisateur.
3. **Vérifier le lien du pied de page anonymement** — déconnecté, ou en
   navigation privée. Un test automatique ne peut pas le faire à votre place :
   il constate la présence du lien, jamais son accessibilité.

## État du projet et limites connues

Le logiciel est utilisé en production par son auteur. Dix-huit passes d'audit
(A à Q, dont une reprise) ont été menées et documentées dans [`docs/`](docs/),
les plus récentes avec leurs preuves reproductibles. Les limites suivantes sont **connues, tracées et assumées** :

- **Comptabilité de caisse**, sans comptes de tiers ni compte de trésorerie :
  la contrepartie de toute écriture est le compte `108000` (Exploitant). C'est
  un choix de modèle, pas un défaut — l'import d'un FEC de cabinet contenant
  des comptes de tiers est géré à part.
- **Pas de table de correspondance des plans comptables** : sur un FEC produit
  par un cabinet, la case 243 « dont CFE et CVAE » reste vide, aucun préfixe de
  compte ne distinguant la CET des autres impôts directs.
- **Pas de télétransmission EDI-TDFC** : la liasse produite sert de support de
  report pour une saisie en ligne, elle ne se dépose pas directement.
- **Pas d'exécutable Windows** : la construction PyInstaller n'est pas
  maintenue ni testée. L'installation passe par les lanceurs `.bat` / `.sh`,
  eux éprouvés.

---

© 2026 Sylvain FAURE et les contributeurs — sous licence AGPL-3.0-or-later.
````


## `NOTICES-TIERS.md`

````markdown
# Composants tiers

Compta LMNP est distribué sous licence **AGPL-3.0-or-later**. Ce document
inventorie ce dont il dépend, et sous quel régime.

> **Inventaire borné et daté**, établi le **16 septembre 2026** sur la version
> **8.52.0**, à partir des **métadonnées des paquets installés** et des
> commandes réellement exécutées — pas de mémoire. Une version antérieure de
> ce document déclarait qu'aucun composant à réciprocité n'entrait dans le
> projet. C'était une **négation absolue**, et elle était fausse : l'outillage
> de ce dépôt exécute Poppler, qui est sous GPL (constat R-02). Une assurance
> générale de ce type ne peut pas être vérifiée, donc ne devrait jamais être
> écrite ; elle est remplacée par les trois rubriques ci-dessous.

## La distinction qui commande les obligations

Trois régimes, à ne jamais confondre — c'est la confusion entre eux qui
produit à la fois les fausses alertes et les vraies infractions :

| Régime | Ce que cela veut dire | Ce que cela oblige |
|---|---|---|
| **Redistribué** | le composant est **dans** le livrable que vous recevez | joindre copyright et texte de licence au livrable |
| **Installé** | téléchargé depuis PyPI **sur votre machine**, par les lanceurs | rien pour ce projet : c'est vous qui l'installez |
| **Exécuté** | programme externe appelé en sous-processus | rien : appeler un programme n'est pas en dériver |

**Le paquet client et le dépôt ne redistribuent aucun composant tiers.** La
colonne « redistribué » est vide, et c'est ce qui explique qu'aucun texte de
licence tiers ne soit livré à côté.

## 1. Installé sur la machine de l'utilisateur

Les lanceurs `.bat` / `.sh` créent un `.venv` et y installent :

| Composant | Version vérifiée | Licence déclarée | Nécessité |
|---|---|---|---|
| Flask | 3.1.3 | BSD-3-Clause | **obligatoire** — serveur web local |
| Werkzeug | 3.1.8 | BSD-3-Clause | transitive de Flask |
| Jinja2 | 3.1.6 | BSD License | transitive de Flask |
| MarkupSafe | 3.0.3 | BSD-3-Clause | transitive de Flask |
| itsdangerous | 2.2.0 | BSD License | transitive de Flask |
| click | 8.5.0 | BSD-3-Clause | transitive de Flask |
| blinker | 1.9.0 | MIT License | transitive de Flask |
| reportlab | 5.0.1 | BSD | **facultatif** — export PDF de la liasse |
| Pillow | 12.3.0 | MIT-CMU | transitive de reportlab |
| charset-normalizer | 3.5.1 | MIT | transitive de reportlab |
| cryptography | *non installé ici* | Apache-2.0 **ou** BSD-3-Clause | **conditionnel** — uniquement si `--https` est demandé et qu'aucun certificat n'existe (`generer_certificat.py`) |

Pillow et charset-normalizer sont des dépendances **déclarées sans condition**
par reportlab 5.0.1 : demander l'export PDF les installe. Elles manquaient à
cet inventaire (constat R-03).

La licence de `cryptography` est celle que le projet publie ; elle n'est pas
vérifiée sur un paquet installé, faute d'installation dans l'environnement
audité. Ses propres dépendances transitives ne sont pas inventoriées ici.

Python lui-même (PSF License) est un prérequis, installé par l'utilisateur.

## 2. Exécuté comme programme externe

| Programme | Licence | Appelé par |
|---|---|---|
| **Poppler** (`pdftotext`) | GPL-2.0-only OR GPL-3.0-only, **et** GPL-2.0-or-later, LGPL-2.0-or-later, LGPL-2.1-or-later, MIT selon les composants | `verifier_depot.texte_du_pdf`, quatre fichiers de tests, l'étape « Dépendances système » de la CI |

**Poppler est sous GPL, et c'est sans conséquence sur la licence de ce
logiciel.** Compta LMNP ne l'inclut pas, ne s'y lie pas et ne le redistribue
pas : il l'appelle en **sous-processus**, comme on appellerait `grep`. La GPL
ne s'étend pas à un programme qui se contente d'en exécuter un autre. Poppler
n'est utilisé que par l'**outillage** — le contrôle avant publication et les
tests — jamais par l'application comptable elle-même : un utilisateur qui
n'installe pas poppler perd la relecture du texte des PDF, rien d'autre.

## 3. Ressources embarquées dans une dépendance

reportlab 5.0.1 livre la police **DarkGarden** (`fonts/DarkGardenMK.pfb`) sous
GPL-2.0-or-later **avec exception d'incorporation** : incorporer la police
dans un document n'impose pas de licence au document.

Ce projet ne l'utilise pas. Les PDF produits emploient **Helvetica et
Helvetica-Bold, non incorporées**. Les liasses que vous imprimez ne sont donc
soumises à aucune obligation issue de cette police — point vérifié sur les
quatorze PDF suivis par le dépôt (constat R-02, limite indépendante).

## 4. Outillage de développement (jamais livré)

`requirements-dev.txt` installe aussi **pytest** 9.1.1 (MIT) et **ruff** 0.16.7
(MIT). Ils ne servent qu'au développement et ne sont ni livrés, ni nécessaires
à l'utilisateur.

## Si un exécutable autonome est un jour construit

La construction PyInstaller a été retirée (voir `compta_lmnp/LISEZ-MOI.md`).
Si elle revient, elle **redistribuerait** Flask, reportlab et leurs
transitives : la colonne « redistribué » cesserait d'être vide, et il faudrait
alors livrer à côté du binaire le fichier `LICENSE`, ce document, **et le
texte complet de chaque licence tierce** — la BSD-3-Clause exige la
reproduction du texte, pas un renvoi vers le projet d'origine.

## Retrouver les textes de licence

Ils ne sont pas recopiés ici tant qu'il n'y a pas de redistribution : ils sont
livrés avec chaque paquet installé.

```bash
python -m pip show -f flask reportlab pillow charset-normalizer
```

| Projet | Source |
|---|---|
| Python | <https://docs.python.org/3/license.html> |
| Flask, Werkzeug, Jinja2, MarkupSafe, itsdangerous, click | <https://github.com/pallets> |
| blinker | <https://github.com/pallets-eco/blinker> |
| reportlab | <https://www.reportlab.com/software/opensource/> |
| Pillow | <https://github.com/python-pillow/Pillow> |
| charset-normalizer | <https://github.com/jawah/charset_normalizer> |
| cryptography | <https://github.com/pyca/cryptography> |
| Poppler | <https://poppler.freedesktop.org/> |
````


## `CONTRIBUTING.md`

````markdown
# Contribuer à Compta LMNP

Les signalements de défauts et les correctifs sont bienvenus. Ce logiciel
produit des **chiffres qui partent sur une déclaration fiscale** : une
contribution acceptée engage le déclarant qui l'utilisera. Les exigences
ci-dessous viennent de là, pas d'un goût pour la procédure.

## Deux règles absolues

### 1. Aucune donnée réelle

Ni nom, ni SIREN, ni adresse, ni nom de rue, ni identité de locataire ou de
fournisseur — pas dans le code, pas dans un test, pas dans un rapport, pas dans
un message de commit, pas dans une capture d'écran. Construisez vos scénarios
sur une identité **fictive**.

Un fichier commité reste dans l'historique git même après suppression. C'est
irréversible, et ça concerne les données de **tiers** (vos locataires) autant
que les vôtres.

### 2. Un test de non-régression par correctif

Un correctif sans test se re-casse. Le test doit **échouer sans le correctif**
et passer avec — vérifiez-le en retirant temporairement votre correctif. Un
test qui passe dans les deux cas ne teste rien.

Nommez-le d'après le défaut qu'il fige, et placez-le dans
`compta_lmnp/tests/`.

## Avant d'ouvrir une pull request

```bash
cd compta_lmnp
pytest -q          # la suite complète doit passer
ruff check .       # aucune alerte
```

Le contrôle de publication `compta_lmnp/verifier_depot.py` ne vous concerne
pas : il cherche les empreintes des données réelles de l'auteur, qui ne sont
publiées nulle part, et refuse donc de conclure sur un clone. C'est un geste
local, joué automatiquement avant chaque push par le hook
[`.githooks/pre-push`](.githooks/pre-push) — que le mainteneur active une fois
par clone :

```bash
git config core.hooksPath .githooks
```

## Certificat d'origine (DCO)

Ce projet utilise le **Developer Certificate of Origin 1.1** plutôt qu'un
contrat de cession de droits : c'est plus léger pour vous, et suffisant pour
que le projet reste diffusable sous AGPL.

Signez chacun de vos commits :

```bash
git commit -s -m "votre message"
```

Cette option ajoute une ligne `Signed-off-by: Votre Nom <votre@email>`. En
l'ajoutant, vous certifiez que vous avez le droit de proposer ce code sous la
licence du projet — le texte complet du DCO est sur
<https://developercertificate.org/>.

Vous **conservez le droit d'auteur** sur vos contributions. Vous les placez
simplement sous la même licence que le reste : **AGPL-3.0-or-later**.

## Ce qui sera refusé — et pourquoi

- **Un changement de comportement fiscal ou comptable sans source.** Citez
  l'article du CGI, le BOFiP ou le CERFA. « C'est ce que fait mon logiciel
  habituel » n'est pas une source.
- **Un correctif validé par lecture du code plutôt que par exécution.** Un
  correctif de ce projet a déjà été validé par un test qui relisait le code
  pendant que l'exécution montrait l'inverse. Montrez une sortie réelle.
- **Une dépendance nouvelle**, sauf nécessité démontrée. Le logiciel doit
  s'installer chez un particulier qui découvre Python ; chaque dépendance est
  une panne d'installation possible. Une dépendance sous licence à réciprocité
  incompatible sera refusée d'office.
- **Une liste écrite à la main** là où une lecture de répertoire ferait
  l'affaire. Une énumération manuelle ne peut pas signaler ce qu'on a oublié
  d'y inscrire — ce défaut s'est produit deux fois ici, et les deux fois le
  logiciel échouait chez l'utilisateur, pas en test.
- **Un garde-fou qui approuve quand il ne peut pas vérifier.** Répertoire
  absent, liste vide, commande en échec, exception avalée : dans tous ces cas,
  un contrôle doit **le dire**, jamais conclure au vert.

## Style

Le code et les commentaires sont **en français**, y compris les noms de
fonctions et de variables. Les commentaires expliquent **pourquoi**, pas quoi —
de préférence en racontant le défaut qui a motivé la ligne. Le
[`CHANGELOG.md`](compta_lmnp/CHANGELOG.md) donne le ton attendu.

## Signaler une faille de sécurité

N'ouvrez **pas** de ticket public. Écrivez à l'auteur (adresse dans le
[`LISEZ-MOI.md`](compta_lmnp/LISEZ-MOI.md)) en décrivant le scénario, sans
joindre de données réelles.
````


## `compta_lmnp/LISEZ-MOI.md`

````markdown
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
````


## `compta_lmnp/construire_distribution.py`

````python
# Compta LMNP — Copyright © 2026 Sylvain FAURE et les contributeurs.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Construit le paquet de DISTRIBUTION (à remettre à un tiers) :

    python construire_distribution.py   →  dist/compta_lmnp_client_vX.Y.Z.zip

Contenu : le code de production, les lanceurs et la documentation.
JAMAIS : les tests, le dossier reference/ (FEC réels = données personnelles,
SIREN et adresse de l'exploitant), ni aucune base .db, sauvegarde, archive
ou registre de dossiers. Une GARDE vérifie le zip après construction et
échoue s'il contient le moindre fichier interdit — la fuite de données
personnelles est bloquante, pas simplement évitée.
"""
from __future__ import annotations

import os
import posixpath
import re
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))

# Points d'entrée et outils : à la RACINE du paquet, comme les lanceurs et
# les documents. Les lanceurs appellent app.py par son nom.
ENTREES = ["app.py", "cli.py", "verifier_depot.py"]

# Modules métier : regroupés dans modules/ pour que LISEZ-MOI.md et les
# lanceurs ne soient plus noyés sous trente-cinq fichiers Python. Le paquet
# reproduit l'arborescence — sinon l'amorçage du chemin d'import, qui pointe
# sur modules/, ne trouverait rien chez le client.
# TOUT modules/ est embarqué, par LECTURE DU RÉPERTOIRE et non par liste
# écrite à la main. La liste énumérée a laissé échapper `plan_immo.py` le jour
# de sa création : le paquet se construisait sans erreur, et l'application
# échouait à l'import CHEZ LE CLIENT — pas ici. La garde « PAQUET INCOMPLET »
# ne couvrait pas ce cas, elle ne vérifie que les fichiers cités par les
# LANCEURS. Même défaut de principe que la garde anti-fuite d'avant la passe F :
# une liste rédigée à la main ne peut pas signaler ce qu'on a oublié d'y mettre.
MODULES_PROD = sorted(f for f in os.listdir(os.path.join(HERE, "modules"))
                      if f.endswith(".py"))
# Un SEUL document d'accueil : README.md et LISEZ-MOI.md disaient chacun
# une moitié de la même chose et se renvoyaient l'un à l'autre.
# Données et documents : racine du paquet.
DONNEES = ["schema.sql", "seed_referentiel.sql", "seed_demo.sql",
           "demo/FEC_DEMO_2025.txt",
           # Manifeste des dépendances d'exécution : les lanceurs
           # l'installent (`pip install -r requirements.txt`). Sans lui dans
           # le paquet, le premier démarrage chez l'utilisateur échoue
           # (constat T-06).
           "requirements.txt"]
# Documents : (nom dans le paquet, chemin sur le disque relatif à HERE).
#
# La licence et les notices tierces vivent à la RACINE du dépôt, pas ici —
# c'est là que GitHub les cherche pour afficher la licence du projet, et c'est
# là qu'un lecteur les attend. Le paquet en reçoit une copie parce que l'AGPL
# l'exige (article 4 : « give all recipients a copy of this License along with
# the Program ») : le zip est une distribution à part entière. Une SEULE
# source, copiée — et non deux fichiers à maintenir en phase, qui divergent
# toujours.
DOCS = [("LICENSE.txt", os.path.join("..", "LICENSE")),
        ("NOTICES-TIERS.md", os.path.join("..", "NOTICES-TIERS.md")),
        ("CONTRIBUTING.md", os.path.join("..", "CONTRIBUTING.md")),
        ("README.md", os.path.join("..", "README.md")),
        ("CHANGELOG.md", "CHANGELOG.md"),
        ("ARCHITECTURE.md", "ARCHITECTURE.md"),
        ("LISEZ-MOI.md", "LISEZ-MOI.md"),
        ("VERSION", "VERSION")]

# Les documents de la racine sont d'un cran au-dessus du logiciel DANS LE
# DÉPÔT, et à côté de lui DANS LE PAQUET. Les liens relatifs écrits pour l'un
# sont donc faux dans l'autre : `../LICENSE` ne menait nulle part une fois le
# zip décompressé, et c'est justement vers la licence et la procédure de
# contribution que ces liens pointaient (constat R-04).
#
# Ils sont réécrits à la construction. La table dit ce que devient chaque
# cible ; la garde plus bas vérifie qu'AUCUN lien local du paquet ne pend,
# celui-ci compris — parce qu'une table de réécriture est encore une liste
# écrite à la main, et qu'elle ne peut pas signaler le lien qu'on n'y a pas
# inscrit.
#
# Deux cas, et il faut les distinguer : ce que le paquet CONTIENT sous un
# autre nom se réécrit en local ; ce qu'il ne contient pas — les rapports
# d'audit, le hook — devient un lien vers le dépôt, parce qu'un renvoi
# honnête vaut mieux qu'un chemin qui pend.
DEPOT = "https://github.com/Nivalys01/Compta-LMNP/"
REECRITURES = {
    # présents dans le paquet, sous un autre chemin
    "../LICENSE": "LICENSE.txt",
    "LICENSE": "LICENSE.txt",
    "../NOTICES-TIERS.md": "NOTICES-TIERS.md",
    "../CONTRIBUTING.md": "CONTRIBUTING.md",
    "../README.md": "README.md",
    "compta_lmnp/CHANGELOG.md": "CHANGELOG.md",
    "compta_lmnp/LISEZ-MOI.md": "LISEZ-MOI.md",
    # absents du paquet : renvoyés vers le dépôt
    ".githooks/pre-push": DEPOT + "blob/main/.githooks/pre-push",
    "docs/": DEPOT + "tree/main/docs/",
    "docs/audit/": DEPOT + "tree/main/docs/audit/",
}

# Un lien Markdown : [texte](cible). On ne retient que les cibles locales —
# ni http(s), ni ancre pure.
LIEN_MD = re.compile(r"\[([^\]]*)\]\(([^)\s]+)\)")
# Un SEUL fichier .sh est livré. Le générateur de certificat existait en
# double (.sh et .py) et s'affichait juste à côté du lanceur : sur un
# bureau Linux, l'utilisateur ouvrait l'un pour l'autre (constaté en
# usage). Le générateur Python fait le même travail, sur toutes les
# plateformes, et ne ressemble pas à un lanceur.
LANCEURS = ["Compta-LMNP-Linux-macOS.sh", "Compta-LMNP-Windows.bat",
            "Compta-LMNP.desktop",
            "generer_certificat.py", "ouvrir_navigateur.py"]

# Fichiers locaux référencés par les lanceurs : le paquet DOIT les contenir,
# sinon l'installation neuve échoue chez le client (défaut trouvé en v8.0.0 :
# les générateurs de certificat manquaient, HTTPS tombait en panne).
REFERENCES_LANCEURS = re.compile(
    r"\b([A-Za-z0-9_\-]+\.(?:py|sh|sql))\b")

# Motifs interdits dans le paquet (données personnelles ou de travail).
INTERDITS = [
    re.compile(r"\.db$"), re.compile(r"^reference/"),
    # Le dossier de référence porte une identité RÉELLE. Il était livré
    # (constat v8.13.0) alors que le fichier lui-même portait la mention
    # « NE JAMAIS LIVRER » : c'est désormais impossible.
    re.compile(r"^seed_exemple\.sql$"),
    re.compile(r"^\d{9}FEC\d{8}\.txt$"), re.compile(r"^tests/"),
    re.compile(r"^dossiers(/|\.json$)"), re.compile(r"^sauvegardes/"),
    re.compile(r"^archives/"), re.compile(r"__pycache__"),
]


def construire() -> str:
    version = open(os.path.join(HERE, "VERSION"), encoding="utf-8").read().strip()
    os.makedirs(os.path.join(HERE, "dist"), exist_ok=True)
    cible = os.path.join(HERE, "dist", f"compta_lmnp_client_v{version}.zip")

    # (chemin dans le paquet, chemin sur le disque)
    fichiers = ([(f"modules/{f}", f"modules/{f}") for f in MODULES_PROD]
                + [(f, f) for f in ENTREES + DONNEES + LANCEURS]
                + DOCS)
    manquants = [d for _, d in fichiers
                 if not os.path.exists(os.path.join(HERE, d))]
    if manquants:
        raise SystemExit(f"Fichiers manquants : {manquants}")

    # ── Garde Windows : un .bat DOIT etre en ASCII pur et en CRLF ────────
    #    cmd.exe lit un fichier de commandes octet par octet ; un caractere
    #    accentue (UTF-8, donc multi-octets) ou une fin de ligne Unix
    #    decale sa lecture et il avale le debut des lignes suivantes —
    #    « echo » devient « ho » puis « o », les variables ne sont jamais
    #    affectees, et le lanceur echoue de facon incomprehensible.
    #    Constate en conditions reelles sur Windows 10 (juillet 2026).
    for lanceur in LANCEURS:
        if not lanceur.lower().endswith(".bat"):
            continue
        octets = open(os.path.join(HERE, lanceur), "rb").read()
        non_ascii = [i for i, b in enumerate(octets) if b > 127]
        lf_seuls = octets.count(b"\n") - octets.count(b"\r\n")
        if non_ascii or lf_seuls:
            raise SystemExit(
                f"LANCEUR WINDOWS ILLISIBLE — {lanceur} : "
                f"{len(non_ascii)} octet(s) non-ASCII, {lf_seuls} fin(s) de "
                "ligne Unix. cmd.exe ne peut pas interpreter ce fichier : "
                "reecrivez-le en ASCII pur avec des fins de ligne CRLF.")

    with zipfile.ZipFile(cible, "w", zipfile.ZIP_DEFLATED) as z:
        for dans_paquet, sur_disque in fichiers:
            chemin = os.path.join(HERE, sur_disque)
            if dans_paquet.endswith(".md"):
                texte = open(chemin, encoding="utf-8").read()
                for avant, apres in REECRITURES.items():
                    texte = texte.replace(f"]({avant})", f"]({apres})")
                z.writestr(f"compta_lmnp/{dans_paquet}", texte)
            else:
                z.write(chemin, arcname=f"compta_lmnp/{dans_paquet}")

    # ── Garde anti-fuite n°1 : aucun NOM interdit ───────────────────────
    with zipfile.ZipFile(cible) as z:
        noms = [n.split("compta_lmnp/", 1)[-1] for n in z.namelist()]
    fuites = [n for n in noms for motif in INTERDITS if motif.search(n)]
    if fuites:
        os.remove(cible)
        raise SystemExit(f"FUITE BLOQUÉE — fichiers interdits : {fuites}")

    # ── Garde anti-lien mort : tout renvoi local doit aboutir ───────────
    #
    #    Cinq liens du document d'accueil pendaient dans le paquet, dont
    #    deux vers la licence et un vers la procédure de contribution
    #    (constat R-04). Aucune garde ne les voyait : le paquet se
    #    construisait, et c'est le lecteur du zip qui découvrait le trou.
    #
    #    Le contrôle porte sur le CONTENU RÉEL de l'archive et sur la
    #    totalité de ses liens — pas sur la table de réécriture, qui est
    #    une liste écrite à la main et ne peut donc pas signaler le lien
    #    qu'on a oublié d'y inscrire.
    with zipfile.ZipFile(cible) as z:
        presents = set(z.namelist())
        morts = []
        for entree in z.namelist():
            if not entree.endswith(".md"):
                continue
            texte = z.read(entree).decode("utf-8", "replace")
            for _libelle, vise in LIEN_MD.findall(texte):
                if "://" in vise or vise.startswith(("#", "mailto:")):
                    continue
                resolu = posixpath.normpath(posixpath.join(
                    posixpath.dirname(entree), vise.split("#")[0]))
                if resolu not in presents:
                    morts.append(f"{entree} → {vise}")
    if morts:
        os.remove(cible)
        raise SystemExit(
            "LIENS MORTS DANS LE PAQUET — un document livré renvoie vers "
            f"ce qu'il ne contient pas : {sorted(set(morts))}")

    # ── Garde anti-fuite n°2 : aucun CONTENU personnel ───────────────────
    #
    #    La garde ci-dessus compare des noms à une liste écrite à la main —
    #    or les fichiers du zip SONT cette liste. Elle vérifiait donc qu'une
    #    liste rédigée par l'auteur ne contenait pas ce qu'il n'y avait pas
    #    mis : structurellement incapable de rien détecter (constat F-03).
    #
    #    Le cas qu'elle laissait passer est précisément celui pour lequel
    #    elle existe : seed_demo.sql et le FEC de démonstration sont les
    #    seuls fichiers du paquet DÉRIVÉS des données réelles, leur nom est
    #    légitime, et personne ne relisait leur contenu (constat F-04).
    #
    #    Les empreintes viennent de verifier_depot, qui les lit dans le
    #    dossier privé : une seule définition de ce qui est sensible.
    #    HERE explicitement dans sys.path : ce script est aussi lancé par
    #    build_client.py via runpy, qui n'ajoute PAS le dossier du script
    #    aux chemins d'import. Sans cela la garde échouerait à l'import —
    #    donc bloquerait la construction, mais pour une mauvaise raison.
    if HERE not in sys.path:
        sys.path.insert(0, HERE)
    import verifier_depot
    liste = verifier_depot.empreintes()
    if not liste:
        os.remove(cible)
        raise SystemExit(
            "CONSTRUCTION REFUSÉE — aucune empreinte n'a pu être chargée "
            "(dossier privé absent ?). Le contenu du paquet n'a donc pas pu "
            "être contrôlé : produire un paquet dans ces conditions "
            "reviendrait à affirmer sans avoir vérifié.")
    cherchees = [(quoi, verifier_depot.normaliser(v)) for quoi, v in liste]
    fuites_contenu = []
    with zipfile.ZipFile(cible) as z:
        for entree in z.namelist():
            brut = z.read(entree)
            texte = None
            for enc in ("utf-8", "cp1252"):
                try:
                    texte = brut.decode(enc)
                    break
                except UnicodeDecodeError:
                    continue
            if texte is None:
                continue
            norme = verifier_depot.normaliser(texte)
            for quoi, valeur in cherchees:
                if valeur and valeur in norme:
                    fuites_contenu.append(f"{entree} ({quoi})")
    if fuites_contenu:
        os.remove(cible)
        raise SystemExit("FUITE BLOQUÉE — donnée personnelle dans le "
                         f"contenu : {sorted(set(fuites_contenu))}")

    # ── Garde anti-oubli : tout fichier local invoqué par un lanceur doit
    #    être dans le paquet (sinon panne à l'installation chez le client).
    embarques = set(noms)
    manquants_lanceurs = set()
    for lanceur in LANCEURS:
        texte = open(os.path.join(HERE, lanceur), encoding="utf-8",
                     errors="ignore").read()
        for ref in REFERENCES_LANCEURS.findall(texte):
            embarque = (ref in embarques
                        or f"modules/{ref}" in embarques)
            if os.path.exists(os.path.join(HERE, ref)) and not embarque:
                manquants_lanceurs.add(ref)
    if manquants_lanceurs:
        os.remove(cible)
        raise SystemExit("PAQUET INCOMPLET — fichiers utilisés par les "
                         f"lanceurs mais absents : {sorted(manquants_lanceurs)}")

    taille = os.path.getsize(cible) // 1024
    print(f"✓ Paquet client : {cible} ({taille} Ko, {len(fichiers)} fichiers, "
          f"contenu contrôlé contre {len(liste)} empreinte(s) du dossier "
          "réel : aucune donnée personnelle)")
    return cible


if __name__ == "__main__":
    sys.exit(0 if construire() else 1)
````


## `compta_lmnp/requirements-dev.txt`

````text
# Environnement de DÉVELOPPEMENT — versions ÉPINGLÉES.
#
# Un linter non épinglé transforme une release de l'outil en CI rouge : le
# jeu de règles par défaut de ruff s'est élargi entre deux versions et le
# projet est passé de « propre » à 234 erreurs sans qu'une ligne de code
# ait changé. Le jeu de règles est par ailleurs déclaré dans pyproject.toml.
#
# Installer l'ensemble :  pip install -r requirements-dev.txt
pytest==9.1.1
ruff==0.16.0

# Les deux suivantes ne sont pas de l'outillage : ce sont les dépendances
# RUNTIME, déclarées pour l'utilisateur dans `requirements.txt`, où elles
# sont BORNÉES et non épinglées — chez un particulier, une version exacte
# sans roue précompilée fait échouer l'installation.
#
# Ici, elles sont épinglées : le développement et l'intégration continue
# doivent éprouver UNE version connue, sans quoi une régression n'est pas
# reproductible d'une machine à l'autre (constat T-06). Ces épingles sont
# donc les versions de référence citées par `requirements.txt`, et les deux
# fichiers doivent rester cohérents — un test le vérifie.
#
# La suite de tests en dépend directement :
#   - flask     : les tests de bout en bout passent par le client web ;
#   - reportlab : cinq tests de la liasse PDF échouaient sans elle.
flask==3.1.3
reportlab==5.0.1
````


## `compta_lmnp/Compta-LMNP-Linux-macOS.sh`

````bash
#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════════
#   COMPTA LMNP — LANCEUR
#   Depuis un terminal :  bash <nom-de-ce-fichier>
#
#   Le lanceur s'occupe de tout :
#     1. vérifie Python 3 ;
#     2. crée un environnement local .venv et installe Flask (1er lancement) ;
#     3. démarre en HTTP local (HTTPS sur demande : --https) ;
#     4. démarre l'application et ouvre le navigateur.
#
#   Options :  --verifier    vérifie l'environnement sans rien lancer
#              --raccourci   installe une entrée dans le menu d'applications
#              --http        force le démarrage sans HTTPS
# ═══════════════════════════════════════════════════════════════════════════
set -euo pipefail

# Chemin ABSOLU résolu du script, calculé AVANT tout cd. Trois usages en
# dépendent, et chacun cassait avec un chemin relatif :
#   - le relancement dans un terminal (gnome-terminal et ptyxis sont
#     activés par D-Bus et NE conservent PAS le répertoire courant) ;
#   - le raccourci de menu, qui doit contenir un chemin absolu ;
#   - les messages d'aide, qui doivent donner une commande copiable.
# `readlink -f` est une extension GNU : BSD (donc macOS) ne l'a qu'à partir
# de la 12.3. Sur une version antérieure, la commande échoue — et comme
# c'est la PREMIÈRE instruction du script, `set -e` l'arrêtait net, avant
# le moindre message. On résout donc à la main, en POSIX pur.
_resoudre() {
    local p="$1" d
    while [ -L "$p" ]; do
        d="$(cd -P "$(dirname "$p")" && pwd)"
        p="$(readlink "$p")"
        case "$p" in /*) ;; *) p="$d/$p" ;; esac
    done
    printf '%s\n' "$(cd -P "$(dirname "$p")" && pwd)/$(basename "$p")"
}
MOI="$(_resoudre "$0")"
DOSSIER="$(dirname "$MOI")"

# macOS ou Linux ? Presque tout ce qui suit en dépend : ouverture du
# navigateur, terminal, notification, diagnostic de port, message
# d'installation de Python. Le fichier s'annonçait « Linux-macOS » alors
# qu'aucune de ces différences n'était traitée.
EST_MAC=0
[ "$(uname -s 2>/dev/null)" = "Darwin" ] && EST_MAC=1
NOM="$(basename "$MOI")"          # déduit, jamais écrit en dur : un
cd "$DOSSIER"                     # renommage ne peut plus le périmer

MODE="${1:-}"

# ── Double-clic depuis le gestionnaire de fichiers ? ─────────────────────────
# Sans terminal, l'utilisateur ne verrait rien : on se relance dans un
# émulateur de terminal. (Si le double-clic OUVRE ce fichier dans un éditeur
# au lieu de l'exécuter : clic droit → « Exécuter », ou installez le
# raccourci de menu avec :  bash <ce-fichier> --raccourci )
# Les modes qui ne font qu'afficher ou écrire un fichier n'ont pas besoin
# d'un terminal : les relancer dans une fenêtre était inutile, et cachait
# leur message de confirmation.
case "$MODE" in --verifier|--raccourci|--aide|-h|--help) SANS_FENETRE=1 ;;
                *) SANS_FENETRE=0 ;; esac
if [[ ! -t 1 && -z "${COMPTA_EN_TERMINAL:-}" && "$SANS_FENETRE" == "0" ]]; then
    export COMPTA_EN_TERMINAL=1
    # macOS : Terminal.app et iTerm sont des APPLICATIONS, pas des
    # commandes — `command -v` ne les trouve jamais. On passe par `open`.
    if [ "$EST_MAC" = "1" ]; then
        # Pas d'`exec` aveugle : si l'ouverture échoue, `exec` a déjà
        # remplacé le processus et le script meurt sans un mot. On teste,
        # et à défaut on continue vers le repli commun (journal + adresse).
        if [ -d "/Applications/iTerm.app" ] \
           && open -a iTerm "$MOI" >/dev/null 2>&1; then exit 0; fi
        if open -a Terminal "$MOI" >/dev/null 2>&1; then exit 0; fi
    fi

    # Ordre : les défauts des bureaux récents d'abord. ptyxis est le
    # terminal par défaut de Fedora 40+ et de Bazzite ; kgx/gnome-console
    # celui de GNOME ; konsole celui de KDE. Leur absence de cette liste
    # faisait échouer TOUT le relancement (constaté en usage réel).
    for term in ptyxis kgx gnome-console gnome-terminal konsole \
                io.elementary.terminal \
                x-terminal-emulator xfce4-terminal mate-terminal tilix \
                terminator alacritty kitty wezterm foot qterminal \
                lxterminal deepin-terminal urxvt xterm; do
        command -v "$term" >/dev/null 2>&1 || continue
        # Chemin ABSOLU : gnome-terminal et ptyxis passent par D-Bus et ne
        # transmettent pas le répertoire courant — un « bash ./script »
        # échouerait sans un mot.
        case "$term" in
            ptyxis)                   exec "$term" -- bash "$MOI" "$@" ;;
            gnome-terminal|tilix|kgx|gnome-console|io.elementary.terminal)
                                      exec "$term" -- bash "$MOI" "$@" ;;
            konsole|terminator|xfce4-terminal|mate-terminal|qterminal|\
            lxterminal|deepin-terminal)
                                      exec "$term" -e "bash '$MOI'" ;;
            alacritty|kitty|wezterm|foot|urxvt|xterm)
                                      exec "$term" -e bash "$MOI" "$@" ;;
        esac
    done
    # Aucun terminal graphique : NE PAS continuer en silence — c'est le
    # pire des cas, l'application démarre et l'utilisateur ne voit rien.
    # On prévient par tous les moyens disponibles, puis on continue.
    JOURNAL="${DOSSIER}/logs/demarrage.log"
    mkdir -p "${DOSSIER}/logs" 2>/dev/null || true
    {
        echo "[$(date '+%F %T')] Aucun terminal graphique trouvé."
        echo "  Compta LMNP démarre malgré tout : ouvrez http://localhost:5000"
        echo "  Pour voir les messages, lancez depuis un terminal :"
        echo "      bash \"$MOI\""
    } >> "$JOURNAL" 2>/dev/null || true
    if [ "$EST_MAC" = "1" ] && command -v osascript >/dev/null 2>&1; then
        osascript -e 'display notification "Ouvrez http://localhost:5000" with title "Compta LMNP"' >/dev/null 2>&1 || true
    elif command -v notify-send >/dev/null 2>&1; then
        notify-send "Compta LMNP démarre" \
            "Ouvrez http://localhost:5000 dans votre navigateur." \
            >/dev/null 2>&1 || true
    elif command -v zenity >/dev/null 2>&1; then
        (zenity --info --title="Compta LMNP" \
            --text="L'application démarre.\n\nOuvrez http://localhost:5000" \
            >/dev/null 2>&1 &) || true
    fi
fi

BLEU='\033[1;34m'; VERT='\033[1;32m'; JAUNE='\033[1;33m'; ROUGE='\033[1;31m'; FIN='\033[0m'
ok()   { echo -e "  ${VERT}✓${FIN} $1"; }
info() { echo -e "  ${BLEU}·${FIN} $1"; }
warn() { echo -e "  ${JAUNE}⚠${FIN} $1"; }
err()  { echo -e "  ${ROUGE}✗${FIN} $1"; }

# ── Ouverture du navigateur : robuste et JAMAIS silencieuse ─────────────────
# xdg-open seul ne suffit pas : il est absent ou inopérant sur beaucoup de
# systèmes (distributions immuables, navigateurs en Flatpak, sessions
# minimales). On essaie plusieurs voies, et si AUCUNE ne marche on affiche
# l'adresse en grand — l'utilisateur ne doit jamais rester devant un écran
# qui ne fait rien.
ouvrir_navigateur() {
    local url="$1"

    # a) Préférence explicite de l'utilisateur
    if [[ -n "${BROWSER:-}" ]] && command -v "${BROWSER%% *}" >/dev/null 2>&1; then
        "$BROWSER" "$url" >/dev/null 2>&1 & sleep 1; return 0
    fi
    # a bis) macOS : `open` est l'ouvreur du système. xdg-open n'y existe
    #        pas — sans cette branche, on tombait directement sur le repli.
    if [ "$EST_MAC" = "1" ]; then
        open "$url" >/dev/null 2>&1 && { sleep 1; return 0; }
    fi
    # b) Ouvreurs génériques du bureau
    for cmd in xdg-open gio gnome-open kde-open5 kde-open; do
        if command -v "$cmd" >/dev/null 2>&1; then
            if [[ "$cmd" == "gio" ]]; then
                gio open "$url" >/dev/null 2>&1 && { sleep 1; return 0; }
            else
                "$cmd" "$url" >/dev/null 2>&1 && { sleep 1; return 0; }
            fi
        fi
    done
    # c) Module Python webbrowser (connaît la plupart des navigateurs)
    if "$PY" -m webbrowser -t "$url" >/dev/null 2>&1; then sleep 1; return 0; fi
    # d) Navigateurs installés en direct
    for nav in firefox chromium chromium-browser google-chrome google-chrome-stable \
               brave-browser vivaldi-stable microsoft-edge epiphany falkon \
               open; do
        if command -v "$nav" >/dev/null 2>&1; then
            "$nav" "$url" >/dev/null 2>&1 & sleep 1; return 0
        fi
    done
    # e) Navigateurs en Flatpak (fréquent sur Fedora Silverblue, Bazzite…)
    if command -v flatpak >/dev/null 2>&1; then
        for app in org.mozilla.firefox com.google.Chrome org.chromium.Chromium \
                   com.brave.Browser com.microsoft.Edge; do
            if flatpak info "$app" >/dev/null 2>&1; then
                flatpak run "$app" "$url" >/dev/null 2>&1 & sleep 1; return 0
            fi
        done
    fi
    return 1                                   # aucune voie n'a fonctionné
}

# L'adresse est TOUJOURS affichée, même quand l'ouverture semble réussir :
# xdg-open (comme python -m webbrowser) renvoie « succès » même lorsqu'il
# n'ouvre RIEN — aucune détection fiable n'est possible. L'utilisateur doit
# donc toujours avoir l'adresse sous les yeux ; l'ouverture est un bonus.
adresse_en_grand() {
    echo
    echo -e "${JAUNE}  ┌────────────────────────────────────────────────────┐${FIN}"
    echo -e "${JAUNE}  │  Si aucune page ne s'ouvre, collez cette adresse    │${FIN}"
    echo -e "${JAUNE}  │  dans votre navigateur :                            │${FIN}"
    echo -e "${JAUNE}  └────────────────────────────────────────────────────┘${FIN}"
    echo
    echo -e "        ${VERT}$1${FIN}"
    echo
    echo -e "  ${BLEU}·${FIN} Astuce : pour choisir le navigateur, lancez par exemple"
    echo -e "    ${BLEU}BROWSER=firefox bash \"$MOI\"${FIN}"
    echo
}

echo -e "${BLEU}══════════════════════════════════════════${FIN}"
echo -e "${BLEU}   Compta LMNP — démarrage${FIN}"
echo -e "${BLEU}══════════════════════════════════════════${FIN}"


# ── 1. Python 3 ──────────────────────────────────────────────────────────────
if ! command -v python3 >/dev/null 2>&1; then
    if [ "$EST_MAC" = "1" ]; then
        err "Python 3 introuvable."
        info "Sur macOS, installez-le d'une de ces deux façons :"
        info "  · outils Apple :  xcode-select --install"
        info "  · ou le paquet officiel : https://www.python.org/downloads/"
    else
        err "Python 3 introuvable. Installez-le :"
        info "  · Debian/Ubuntu/Mint :  sudo apt install python3 python3-venv"
        info "  · Fedora/RHEL        :  sudo dnf install python3"
        info "  · Arch/Manjaro       :  sudo pacman -S python"
        info "  · openSUSE           :  sudo zypper install python3"
    fi
    read -rp "Appuyez sur Entrée pour fermer…"; exit 1
fi
ok "Python 3 : $(python3 --version 2>&1)"

# ── Option : installer un raccourci dans le menu d'applications ─────────────
if [[ "$MODE" == "--raccourci" ]]; then
    # macOS ignore les fichiers .desktop. Son équivalent natif est un
    # fichier « .command » : rendu exécutable, il se lance d'un
    # double-clic depuis le Finder et ouvre Terminal — exactement ce que
    # cherche l'utilisateur.
    if [ "$EST_MAC" = "1" ]; then
        CIBLE="${HOME}/Desktop/Compta LMNP.command"
        printf '#!/bin/sh\nexec bash "%s"\n' "$MOI" > "$CIBLE"
        chmod +x "$CIBLE"
        ok "Raccourci créé sur le Bureau : Compta LMNP.command"
        ok "Double-cliquez dessus pour lancer le logiciel."
        info "Au premier lancement, macOS peut demander une confirmation"
        info "(clic droit → Ouvrir) : c'est normal pour un fichier"
        info "téléchargé et non signé."
        exit 0
    fi
    DESK="${HOME}/.local/share/applications/compta-lmnp.desktop"
    mkdir -p "$(dirname "$DESK")"
    cat > "$DESK" <<EOF
[Desktop Entry]
Type=Application
Name=Compta LMNP
Comment=Comptabilité location meublée (LMNP réel)
Exec=bash "${MOI}"
Path=${DOSSIER}
Terminal=true
Categories=Office;Finance;
EOF
    chmod +x "$DESK"
    ok "Raccourci installé : ${DESK}"
    ok "« Compta LMNP » apparaît maintenant dans votre menu d'applications."
    exit 0
fi

# ── 2. Environnement local (.venv) + Flask ──────────────────────────────────
#
# Trois pièges appris en usage réel (Linux Mint, août 2026) :
#
#   1. Le SCRIPT ./.venv/bin/pip peut manquer alors que le MODULE pip est
#      présent — c'est le cas sur Debian et dérivés quand python3-venv est
#      installé sans le paquet pip. On appelle donc toujours « python -m
#      pip », jamais le script.
#   2. « python3 -m venv » peut échouer APRÈS avoir créé le dossier. Un
#      .venv incomplet subsiste alors, et un test « le dossier existe-t-il »
#      croit l'environnement prêt : le lancement suivant meurt sans un mot.
#      On teste donc que l'environnement FONCTIONNE, pas qu'il existe.
#   3. Sur Debian et dérivés, la création peut réussir SANS pip. ensurepip
#      permet de le rattraper sans réinstaller quoi que ce soit.
venv_operationnel() {
    [[ -x .venv/bin/python ]] && \
        ./.venv/bin/python -m pip --version >/dev/null 2>&1
}

if ! venv_operationnel; then
    if [[ -d .venv ]]; then
        warn "Environnement local incomplet ou abîmé — reconstruction."
        rm -rf .venv
    fi
    info "Premier lancement : création de l'environnement local (.venv)…"
    info "(1 à 3 minutes, ne fermez pas cette fenêtre)"
    if ! python3 -m venv .venv 2>/tmp/compta-venv.err; then
        err "Création de l'environnement impossible."
        [[ -s /tmp/compta-venv.err ]] && sed 's/^/      /' /tmp/compta-venv.err
        if [ "$EST_MAC" = "1" ]; then
            info "Vérifiez votre installation Python (python3 -m venv --help)."
        else
            info "Installez le paquet manquant, puis relancez :"
            info "  · Debian, Ubuntu, Mint :  sudo apt install python3-venv python3-pip"
            info "  · Fedora, RHEL, Bazzite:  sudo dnf install python3-virtualenv"
            info "  · Arch, Manjaro        :  sudo pacman -S python-pip"
        fi
        rm -rf .venv
        read -rp "Appuyez sur Entrée pour fermer…"; exit 1
    fi
    # La création a réussi — mais pip peut manquer malgré tout.
    if ! venv_operationnel; then
        info "pip absent de l'environnement — amorçage…"
        ./.venv/bin/python -m ensurepip --upgrade >/dev/null 2>&1 || true
    fi
    if ! venv_operationnel; then
        err "L'environnement a été créé, mais pip n'a pas pu y être installé."
        info "Sur Debian, Ubuntu et Mint, c'est le paquet python3-venv qui"
        info "fournit pip aux environnements virtuels :"
        info "  sudo apt install python3-venv python3-pip"
        info "Puis supprimez le dossier .venv et relancez ce fichier."
        read -rp "Appuyez sur Entrée pour fermer…"; exit 1
    fi
    ok "Environnement local créé."
else
    ok "Environnement local : .venv"
fi
PY=./.venv/bin/python

# « $PY -m pip » et non « ./.venv/bin/pip » : le module existe même quand le
# script d'appel manque.
if ! "$PY" -c "import flask" >/dev/null 2>&1; then
    info "Installation de Flask (une seule fois)…"
    "$PY" -m pip install --quiet --upgrade pip >/dev/null 2>&1 || true
    # Le manifeste borne les versions au lieu de laisser pip prendre
    # n'importe quoi : deux installations d'une même version du logiciel
    # doivent donner le même environnement (constat T-06).
    if ! "$PY" -m pip install --quiet -r "$DOSSIER/requirements.txt"; then
        err "Installation de Flask impossible."
        info "Une connexion internet est nécessaire au premier lancement."
        info "Derrière un proxy d'entreprise, renseignez la variable"
        info "https_proxy avant de relancer."
        read -rp "Appuyez sur Entrée pour fermer…"; exit 1
    fi
fi
# reportlab ne sert qu'à l'export PDF : son absence ne doit RIEN bloquer.
if ! "$PY" -c "import reportlab" >/dev/null 2>&1; then
    "$PY" -m pip install --quiet -r "$DOSSIER/requirements.txt" >/dev/null 2>&1 \
        || warn "reportlab non installé — tout fonctionne sauf l'export PDF."
fi
# Un import qui réussit ne dit PAS que l'environnement est celui qu'attend
# CETTE version du logiciel : le lanceur passait outre, et un .venv vieilli
# survivait à toutes les mises à jour (constat T-06).
#
# On compare donc l'empreinte du manifeste à celle enregistrée lors de la
# dernière installation réussie. C'est déterministe, ça ne demande pas le
# réseau quand rien n'a changé, et ça se déclenche exactement quand le
# manifeste bouge — c'est-à-dire quand l'utilisateur met à jour le logiciel.
EMPREINTE_REQ="$DOSSIER/.venv/.compta-requirements"
ATTENDUE="$("$PY" - "$DOSSIER/requirements.txt" <<'EOF'
import sys
from hashlib import sha256
print(sha256(open(sys.argv[1], "rb").read()).hexdigest())
EOF
)"
if [ "$(cat "$EMPREINTE_REQ" 2>/dev/null || true)" != "$ATTENDUE" ]; then
    info "Mise à niveau des dépendances vers les versions attendues…"
    if "$PY" -m pip install --quiet --upgrade \
            -r "$DOSSIER/requirements.txt" >/dev/null 2>&1; then
        printf '%s' "$ATTENDUE" > "$EMPREINTE_REQ"
    else
        warn "Dépendances non mises à niveau (hors ligne ?) — le logiciel"
        warn "démarre avec l'environnement existant."
    fi
fi
ok "Flask : $("$PY" -c 'import importlib.metadata as m; print(m.version("flask"))')"

# ── 3. Protocole ─────────────────────────────────────────────────────────────
# HTTP par défaut depuis la v8.15.0. Un certificat AUTO-SIGNÉ ne peut pas
# être validé : le navigateur affiche un avertissement plein écran puis un
# cadenas barré, définitivement. Or il ne protège rien ici — l'application
# n'écoute que sur la boucle locale et les données ne traversent aucun
# réseau. Son seul effet était d'habituer l'utilisateur à passer outre les
# avertissements de sécurité. HTTPS reste disponible avec --https.
URL="http://localhost:5000"
export COMPTA_HTTPS=0
if [[ "$MODE" == "--https" ]]; then
    if [[ ! -f certs/cert.pem || ! -f certs/key.pem ]]; then
        info "Génération du certificat HTTPS local (une seule fois)…"
        "$PY" -c "import cryptography" 2>/dev/null || "$PY" -m pip install --quiet cryptography
        "$PY" generer_certificat.py >/dev/null 2>&1 \
            && ok "Certificat créé (valide 10 ans)." \
            || warn "HTTPS indisponible — démarrage en HTTP."
    fi
    if [[ -f certs/cert.pem && -f certs/key.pem ]]; then
        URL="https://localhost:5000"
        export COMPTA_HTTPS=1
        warn "HTTPS demandé : le navigateur signalera un certificat non "
        warn "vérifié (auto-signé). C'est attendu."
    fi
fi

# ── Mode vérification seule ──────────────────────────────────────────────────
if [[ "$MODE" == "--verifier" ]]; then
    ok "Environnement opérationnel — tout est prêt pour lancer l'application."
    exit 0
fi

# ── 4. Choix du port (diagnostic si 5000 occupé) ─────────────────────────────
PORT=5000
proto="${URL%%:*}"                                  # https ou http

port_occupe() {                                      # test de bind : portable
    ! "$PY" -c "import socket; s=socket.socket(); s.bind(('127.0.0.1', $1)); s.close()" 2>/dev/null
}

serveur_repond() {                                   # 1 = URL à tester
    "$PY" - "$1" <<'PYEOF' >/dev/null 2>&1
import ssl, sys, urllib.request
ctx = ssl.create_default_context(); ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE
urllib.request.urlopen(sys.argv[1], timeout=2, context=ctx)
PYEOF
}

if port_occupe "$PORT"; then
    if serveur_repond "${proto}://localhost:${PORT}"; then
        ok "L'application tourne déjà — ouverture du navigateur."
        ouvrir_navigateur "${proto}://localhost:${PORT}" \
            || adresse_en_grand "${proto}://localhost:${PORT}"
        exit 0
    fi
    warn "Le port ${PORT} est occupé par un processus qui NE RÉPOND PAS."
    # Est-ce un ancien lancement de CE logiciel (même dossier) ? → on le stoppe.
    pid=""
    if [ "$EST_MAC" = "1" ] && command -v lsof >/dev/null 2>&1; then
        # macOS n'a ni ss (iproute2) ni /proc : lsof est l'équivalent.
        pid="$(lsof -ti :"${PORT}" -sTCP:LISTEN 2>/dev/null | head -1 || true)"
    elif command -v ss >/dev/null 2>&1; then
        pid="$(ss -ltnp 2>/dev/null | grep ":${PORT} " | grep -oP 'pid=\K[0-9]+' | head -1 || true)"
    fi
    if [[ -z "${pid:-}" ]] && command -v pgrep >/dev/null 2>&1; then
        pid="$(pgrep -f "\.venv/bin/python app\.py" | head -1 || true)"
    fi
    # Le processus tourne-t-il depuis CE dossier ? /proc est propre à
    # Linux ; sur macOS on interroge lsof.
    cwd_pid=""
    if [ -n "${pid:-}" ]; then
        if [ "$EST_MAC" = "1" ]; then
            cwd_pid="$(lsof -a -d cwd -p "$pid" -Fn 2>/dev/null | sed -n 's/^n//p' | head -1 || true)"
        else
            cwd_pid="$(readlink -f "/proc/${pid}/cwd" 2>/dev/null || true)"
        fi
    fi
    if [[ -n "${pid:-}" ]] && [[ "$cwd_pid" == "$(pwd)" ]]; then
        info "Ancien lancement de Compta LMNP détecté (pid ${pid}) — arrêt…"
        kill "$pid" 2>/dev/null || true; sleep 1
        kill -9 "$pid" 2>/dev/null || true; sleep 1
        ok "Port ${PORT} libéré."
    else
        info "Processus étranger : recherche d'un port libre…"
        for p in 5001 5002 5003 5004 5005 5006 5007 5008 5009 5010; do
            if ! port_occupe "$p"; then PORT="$p"; break; fi
        done
        [[ "$PORT" == "5000" ]] && { err "Aucun port libre entre 5000 et 5010."; exit 1; }
        ok "Repli sur le port ${PORT}."
    fi
fi
URL="${proto}://localhost:${PORT}"

# ── 5. Démarrage, puis navigateur UNE FOIS LE SERVEUR PRÊT ───────────────────
echo
ok "Démarrage de Compta LMNP"
adresse_en_grand "${URL}"
info "Premier accès HTTPS : le navigateur affichera un avertissement"
info "(certificat auto-signé, normal en local) : « Avancé → Continuer »."
info "Pour arrêter l'application : Ctrl+C dans cette fenêtre."
echo
(
    # On n'ouvre le navigateur QUE lorsque le serveur répond réellement —
    # jamais sur un port mort.
    for _ in $(seq 1 30); do
        sleep 0.5
        if serveur_repond "$URL"; then
            adresse_en_grand "$URL"
            ouvrir_navigateur "$URL" || true
            exit 0
        fi
    done
    echo -e "  ${JAUNE}⚠${FIN} Le serveur n'a pas répondu après 15 s — lisez les messages ci-dessus."
    adresse_en_grand "$URL"
) &
exec env COMPTA_PORT="$PORT" "$PY" app.py
````


## `compta_lmnp/Compta-LMNP-Windows.bat`

````bat
@echo off
rem =====================================================================
rem   COMPTA LMNP - LANCEUR WINDOWS
rem   Double-cliquez sur ce fichier.
rem
rem   MAINTENANCE : ce fichier doit rester en ASCII PUR (aucun accent,
rem   aucun caractere de dessin) et en fins de ligne CRLF. cmd.exe lit un
rem   .bat octet par octet : un caractere accentue ou une fin de ligne
rem   Unix decale sa lecture et il avale le debut des lignes suivantes.
rem   Un test automatique verifie ces deux proprietes a chaque livraison.
rem
rem   Le nom du fichier porte -Windows : sous Windows les extensions sont
rem   masquees par defaut, et le lanceur Linux (.sh) s'affichait sous un
rem   nom IDENTIQUE juste a cote. Deux fichiers jumeaux, un seul qui
rem   marche : constate en usage reel.
rem
rem   Prerequis (une seule fois) : installer Python 3 depuis
rem   https://www.python.org/downloads/ en COCHANT la case
rem   "Add python.exe to PATH" pendant l'installation.
rem =====================================================================
setlocal
cd /d "%~dp0"
title Compta LMNP

echo ==========================================
echo    Compta LMNP - demarrage
echo ==========================================

rem --- 1. Python 3 disponible ? ---------------------------------------
rem Le lanceur py est prefere : il trouve Python meme absent du PATH.
rem On EXECUTE la commande au lieu de tester sa seule presence, car
rem Windows 10 fournit un faux python.exe qui ouvre le Microsoft Store.
set "PYCMD="
py -3 --version >nul 2>nul && set "PYCMD=py -3"
if not defined PYCMD (
    python --version >nul 2>nul && set "PYCMD=python"
)
if not defined PYCMD goto :pas_de_python
for /f "tokens=*" %%v in ('%PYCMD% --version 2^>^&1') do set "PYVER=%%v"
echo   [OK] %PYVER% detecte.

rem --- 2. Environnement local (.venv) ----------------------------------
rem On teste que l'environnement FONCTIONNE, pas qu'il existe : une
rem creation interrompue laisse un .venv incomplet, et un simple test de
rem presence le croit pret (constate sous Linux, meme piege ici).
".venv\Scripts\python.exe" -m pip --version >nul 2>nul && goto :venv_ok
if exist ".venv" (
    echo   [!!] Environnement local incomplet - reconstruction.
    rmdir /s /q ".venv"
)
echo   [..] Premier lancement : creation de l'environnement local...
echo        (cette etape dure 1 a 3 minutes, ne fermez pas la fenetre)
%PYCMD% -m venv .venv
if errorlevel 1 goto :echec_venv
".venv\Scripts\python.exe" -m pip --version >nul 2>nul || ".venv\Scripts\python.exe" -m ensurepip --upgrade >nul 2>nul
".venv\Scripts\python.exe" -m pip install --quiet --upgrade pip
echo   [..] Installation de Flask...
".venv\Scripts\python.exe" -m pip install --quiet -r requirements.txt
if errorlevel 1 goto :echec_pip
rem reportlab sert uniquement a l'export PDF : son absence n'empeche
rem pas le logiciel de fonctionner (l'application le detecte et le dit).
echo   [..] Installation de reportlab (export PDF, facultatif)...
".venv\Scripts\python.exe" -m pip install --quiet -r requirements.txt
if errorlevel 1 echo   [!!] reportlab non installe - tout fonctionne sauf
if errorlevel 1 echo        l'export PDF de la liasse (l'affichage a l'ecran
if errorlevel 1 echo        et l'impression navigateur restent disponibles).
:venv_ok
set "PY=.venv\Scripts\python.exe"
"%PY%" -c "import flask" >nul 2>nul || "%PY%" -m pip install --quiet -r requirements.txt
echo   [OK] Environnement local pret.

rem --- 3. Raccourci sur le Bureau (une seule fois) ----------------------
rem Sans raccourci, il faut retrouver le dossier a chaque fois. Le
rem marqueur evite de le recreer si l'utilisateur l'a supprime volontairement.
if exist ".raccourci_bureau" goto :raccourci_ok
powershell -NoProfile -ExecutionPolicy Bypass -Command "$w = New-Object -ComObject WScript.Shell; $c = $w.CreateShortcut((Join-Path ([Environment]::GetFolderPath('Desktop')) 'Compta LMNP.lnk')); $c.TargetPath = '%~f0'; $c.WorkingDirectory = '%~dp0'; $c.Description = 'Comptabilite LMNP au reel'; $c.Save()" >nul 2>nul
if exist "%USERPROFILE%\Desktop\Compta LMNP.lnk" echo   [OK] Raccourci "Compta LMNP" cree sur le Bureau.
echo marqueur > ".raccourci_bureau"
:raccourci_ok

rem --- 4. Demarrage + navigateur ---------------------------------------
set "URL=http://localhost:5000"
echo.
echo   [OK] Demarrage de Compta LMNP  -^>  %URL%
echo        Pas de cadenas dans la barre d'adresse, et c'est normal :
echo        vos donnees ne quittent pas cet ordinateur et ne traversent
echo        aucun reseau. (HTTPS local possible : voir INSTALLATION.md.)
echo        Pour arreter : Ctrl+C ou fermer cette fenetre.
echo.
echo   Si aucune page ne s'ouvre, collez cette adresse dans votre
echo   navigateur :   %URL%
echo.
rem Le navigateur ne doit s'ouvrir QU'APRES le demarrage du serveur :
rem sinon la page s'affiche sur un port encore muet (site inaccessible).
start "" /b "%PY%" ouvrir_navigateur.py "%URL%"
"%PY%" app.py
pause
exit /b 0

:pas_de_python
echo   [XX] Python 3 introuvable.
echo.
echo        Installez-le depuis https://www.python.org/downloads/
echo        et COCHEZ "Add python.exe to PATH" pendant l installation,
echo        puis relancez ce fichier.
echo.
echo        Si Python est deja installe et que ce message apparait,
echo        c est que Windows ne le trouve pas : reinstallez-le en
echo        cochant bien la case, ou lancez l installation avec
echo        l option "Install launcher for all users".
pause
exit /b 1

:echec_venv
echo   [XX] Echec de creation de l environnement local (.venv).
echo        Verifiez que le dossier n est pas en lecture seule
echo        (evitez Program Files) ni synchronise par OneDrive.
pause
exit /b 1

:echec_pip
echo   [XX] Echec d installation de Flask.
echo        Une connexion internet est requise au premier lancement.
echo        Si vous utilisez une version tres recente de Python et que
echo        l installation echoue, installez Python 3.12 ou 3.13 :
echo        certaines dependances n ont pas encore de version prete
echo        pour les toutes dernieres moutures.
pause
exit /b 1
````


## `compta_lmnp/outils_sprite.py`

````python
# Compta LMNP — Copyright © 2026 Sylvain FAURE et les contributeurs.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Générateur du sprite de l'assistante (outil de développement).

Pourquoi du PIXEL ART
---------------------
Une illustration dessinée « à la main » en courbes SVG demande un métier
que ce projet n'a pas : la première tentative était laide, et à juste
titre. Le pixel art contourne le problème — il est honnête sur sa
définition, lisible à petite taille, et se dessine sur une grille plutôt
qu'au trait. C'est la seule technique où l'on peut obtenir un résultat
correct sans savoir dessiner.

Pourquoi un générateur plutôt qu'un SVG écrit à la main
--------------------------------------------------------
Le sprite est décrit par une CARTE en caractères, lisible et modifiable
d'un coup d'œil : changer une couleur ou un pixel se fait dans la carte,
pas dans 200 balises <rect>. Le script fusionne ensuite les pixels voisins
de même couleur en rectangles — un sprite de 22x24 tombe ainsi de ~300
rectangles à moins de 120.

Le SVG produit est collé dans pages.py, qui doit rester de la présentation
PURE (aucun import, aucune fonction — un test le vérifie).

Lancer :  python outils_sprite.py          # aperçu texte + SVG
"""
from __future__ import annotations
PALETTE = {
    "K": "#14121c",   # contour, noir franc
    "A": "#e8e6ef",   # armure, clair
    "a": "#a8a6b8",   # armure, demi-teinte
    "d": "#6e6c82",   # armure, ombre
    "B": "#3a6ea8",   # tissu, bleu
    "b": "#26507d",   # tissu, ombre
    "V": "#2f8f5f",   # visière (la signature comptable)
    "v": "#57c98d",   # visière, reflet
    "G": "#f2c14e",   # or
    "g": "#b8862a",   # or, ombre
    "E": "#8ad8ff",   # regard
    "T": "#1e2b3d",   # écran de la tablette
    "l": "#8fb4e0",   # ligne de chiffres
    "j": "#f2c14e",   # ligne mise en avant
    "N": "#0f3320",   # tablette, fond validé
    "M": "#57c98d",   # tablette, coche
    "R": "#4a1410",   # tablette, fond alerte
    "r": "#ff8a72",   # tablette, signe d'alerte
}

# Carte du sprite — 22 colonnes × 24 lignes. « . » = transparent.
SPRITE = [
    "........KKKKKK..........",
    "......KKaaaaaaKK........",
    "....KKaAAAAAAAAaKK......",
    "..KKaaAAAAAAAAAAaaKK....",
    "..KaAAAAAAAAAAAAAAaK....",
    "..KaAVVVVVVVVVVVVAaK....",
    "..KaAvvvvvvvvvvvvAaK....",
    "..KKaaaaaaaaaaaaaaKK....",
    "....KddEEddddEEddK......",
    "....KddddddddddddK...KKK",
    ".....KKddddddddKK...KTTK",
    ".......KKddddKK.....KTTK",
    "...KKKKKGGGGGGKKKKK.KTTK",
    "..KAAAAKBBBBBBKAAAAKKKKK",
    "..KAaaAKBBGGBBKAaaAK....",
    "..KAaaAKBBGGBBKAaaAK....",
    "..KKKKKKBBBBBBKKKKKK....",
    "......KbBBBBBBbK........",
    "......KbbBBBBbbK........",
    "......KKbbbbbbKK........",
    "........KKKKKK..........",
]

# Zone de la tablette (superposée, change selon l'état). Coordonnées en
# pixels du sprite : x, y, largeur, hauteur.
TABLETTE = (21, 10, 2, 3)   # x, y, largeur, hauteur de l'écran

# Superpositions : seuls les pixels qui CHANGENT d'un état à l'autre. Le
# corps est dessiné une fois ; on ne repeint que l'écran de la tablette, la
# bouche et les sourcils. Trois états coûtent ainsi une trentaine de
# rectangles, pas trois sprites entiers.
ETATS = {
    "info": {
        (21, 10): "l", (22, 10): "l",
        (21, 11): "j", (22, 11): "T",
        (21, 12): "l", (22, 12): "l",
    },
    "valide": {
        (21, 10): "N", (22, 10): "M",
        (21, 11): "M", (22, 11): "N",
        (21, 12): "M", (22, 12): "N",
        (7, 8): "v", (8, 8): "v", (13, 8): "v", (14, 8): "v",
    },
    "anomalie": {
        (21, 10): "R", (22, 10): "r",
        (21, 11): "R", (22, 11): "r",
        (21, 12): "R", (22, 12): "r",
        (7, 8): "r", (8, 8): "r", (13, 8): "r", (14, 8): "r",
    },
}


def _rects(carte: list[str]) -> list[tuple[int, int, int, int, str]]:
    """Fusionne les pixels voisins de même couleur en rectangles.

    Fusion horizontale puis verticale : un aplat de 6x8 devient 1 rectangle
    au lieu de 48. Sans cela le SVG pèserait trois fois plus.
    """
    bandes: list[tuple[int, int, int, int, str]] = []
    for y, ligne in enumerate(carte):
        x = 0
        while x < len(ligne):
            c = ligne[x]
            if c == ".":
                x += 1
                continue
            fin = x
            while fin + 1 < len(ligne) and ligne[fin + 1] == c:
                fin += 1
            bandes.append((x, y, fin - x + 1, 1, c))
            x = fin + 1
    # fusion verticale des bandes identiques et contiguës
    fusionnes: list[list] = []
    for x, y, w, h, c in bandes:
        for prec in fusionnes:
            if (prec[0] == x and prec[2] == w and prec[4] == c
                    and prec[1] + prec[3] == y):
                prec[3] += 1
                break
        else:
            fusionnes.append([x, y, w, h, c])
    return [tuple(r) for r in fusionnes]


def apercu(carte: list[str]) -> str:
    """Rendu texte, pour vérifier la silhouette sans navigateur."""
    return "\n".join(
        "".join("██" if c != "." else "  " for c in ligne) for ligne in carte)


def svg(carte: list[str], indent: str = "      ") -> str:
    lignes = []
    for x, y, w, h, c in _rects(carte):
        lignes.append(f'{indent}<rect x="{x}" y="{y}" width="{w}" '
                      f'height="{h}" fill="{PALETTE[c]}"/>')
    return "\n".join(lignes)


def svg_complet() -> str:
    """SVG prêt à coller dans pages.py : corps + trois superpositions."""
    larg, haut = len(SPRITE[0]), len(SPRITE)
    out = [f'  <svg class="perso" viewBox="0 0 {larg} {haut}" '
           'xmlns="http://www.w3.org/2000/svg" shape-rendering="crispEdges"',
           '       role="img" aria-hidden="true">',
           '    <g class="corps">',
           svg(SPRITE, "      "),
           '    </g>']
    for nom, pixels in ETATS.items():
        vide = ["." * larg for _ in range(haut)]
        carte = [list(ligne) for ligne in vide]
        for (x, y), c in pixels.items():
            carte[y][x] = c
        out.append(f'    <g class="sur-{nom}">')
        out.append(svg(["".join(x) for x in carte], "      "))
        out.append('    </g>')
    out.append('  </svg>')
    return "\n".join(out)


def main() -> None:
    print(apercu(SPRITE))
    r = _rects(SPRITE)
    pleins = sum(1 for ligne in SPRITE for c in ligne if c != ".")
    print(f"\n{pleins} pixels → {len(r)} rectangles "
          f"({100 - round(len(r) / pleins * 100)} % d'économie)")
    print(f"grille : {len(SPRITE[0])} × {len(SPRITE)}")
    print("\n--- SVG ---")
    print(svg_complet())


if __name__ == "__main__":
    main()
````


## `compta_lmnp/modules/pense_bete.py`

````python
# Compta LMNP — Copyright © 2026 Sylvain FAURE et les contributeurs.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Pense-bête — ce que le logiciel ne fait PAS à votre place.

La comptabilité est automatisée ; mais déclarer, payer, informer le greffe
restent des gestes MANUELS de l'exploitant. Ce module croise le calendrier
et l'état du dossier pour rappeler, au bon moment, ce qu'il faut faire :

  - échéances calendaires récurrentes (déclaration de résultats, 2042C-PRO,
    CFE, taxe foncière) — dates indicatives : les dates exactes varient
    chaque année, toujours vérifier sur impots.gouv.fr ;
  - événements du dossier : exercice à clôturer/déclarer, bien acquis dans
    l'année (formalités de début/extension d'activité), seuils LMP,
    fonds travaux ALUR jamais saisi, sauvegardes.

Chaque rappel : {niveau: 'important'|'a_prevoir'|'info', titre, detail}.

S'y ajoute une CHECKLIST des oublis récurrents (`OUBLIS_FREQUENTS`), qui ne
dépend pas de l'état du dossier : ce sont les fautes que les loueurs
meublés au réel commettent le plus souvent, regroupées par moment de la
vie du dossier. Elle sert de relecture avant clôture — pas de conseil
personnalisé : chaque situation mérite d'être vérifiée, au besoin auprès
d'un professionnel.
"""
from __future__ import annotations

import os
import sqlite3
from datetime import date


# ── Checklist des oublis récurrents ─────────────────────────────────────────
# Synthèse de sources spécialisées et de la doctrine administrative,
# recoupée en juillet 2026. Volontairement formulée en POINTS DE VIGILANCE
# et non en affirmations fiscales : le but est de déclencher une
# vérification, pas de tenir lieu de conseil.
OUBLIS_FREQUENTS = [
    # --- Au démarrage -------------------------------------------------------
    {"moment": "Au démarrage de l'activité",
     "titre": "Frais d'acquisition passés par pertes et profits",
     "detail": "Frais de notaire, droits de mutation et commission "
               "d'agence sont fréquemment considérés comme un coût "
               "d'entrée définitivement perdu. Ils ne le sont pas : selon "
               "l'option retenue, ils se déduisent l'année d'acquisition "
               "ou s'incorporent au prix de revient pour être amortis. "
               "C'est l'oubli le plus coûteux de la première année, et il "
               "est difficile à rattraper ensuite."},
    {"moment": "Au démarrage de l'activité",
     "titre": "Immatriculation et numéro SIRET",
     "detail": "L'activité doit être déclarée pour obtenir un SIRET, et "
               "ce numéro doit être reporté sur la déclaration "
               "complémentaire de revenus. Un dossier sans SIRET reporté "
               "est une anomalie visible immédiatement par "
               "l'administration."},
    {"moment": "Au démarrage de l'activité",
     "titre": "Terrain amorti par erreur",
     "detail": "La quote-part de terrain n'est jamais amortissable. Si "
               "elle a été noyée dans la valeur du bâti, l'amortissement "
               "est surévalué chaque année — et l'erreur se répète "
               "jusqu'à la revente."},

    # --- Charges oubliées ---------------------------------------------------
    {"moment": "Charges souvent oubliées",
     "titre": "CFE — découverte plusieurs années trop tard",
     "detail": "La cotisation foncière des entreprises s'applique à la "
               "location meublée, sauf cas d'exonération, et n'est "
               "généralement pas due la première année. Beaucoup de "
               "bailleurs la découvrent avec un rappel : vérifiez votre "
               "espace professionnel dès la deuxième année."},
    {"moment": "Charges souvent oubliées",
     "titre": "Frais de déplacement : ne pas confondre les deux barèmes",
     "detail": "Les trajets réellement engagés pour l'activité (état des "
               "lieux, remise des clés, assemblée générale, visite de "
               "travaux) sont des charges, sur justificatif et pour un "
               "motif professionnel. Attention à une confusion "
               "fréquente : le barème KILOMÉTRIQUE (indemnités "
               "kilométriques) ne s'applique PAS aux BIC — il vise les "
               "traitements et salaires et les BNC. En BIC, c'est le "
               "barème CARBURANT qui existe, ouvert aux exploitants "
               "individuels au réel simplifié ayant opté pour la "
               "comptabilité super-simplifiée. Et ce barème ne couvre que "
               "le carburant : les dépenses qu'il ne couvre pas — péages, "
               "stationnement, assurance, entretien — se déduisent EN "
               "PLUS, pour leur montant réel et au prorata de l'usage "
               "professionnel.",
     "sources": ["BOI-BAREME-000003 (barème carburant)",
                 "CGI, art. 302 septies A ter A",
                 "BOI-BIC-CHG-40-20-40 (frais de déplacement du chef "
                 "d'entreprise)"]},
    {"moment": "Charges souvent oubliées",
     "titre": "Frais de comptabilité et d'outillage",
     "detail": "Honoraires d'expert-comptable, abonnement à un service de "
               "télétransmission, logiciel : ce sont des charges "
               "d'exploitation. Note utile depuis 2025 : la réduction "
               "d'impôt pour adhésion à un organisme de gestion agréé est "
               "supprimée, mais la déduction des frais, elle, demeure."},
    {"moment": "Erreurs de classement",
     "titre": "Caution mutuelle d'emprunt : ce n'est pas une charge",
     "detail": "Les frais de garantie d'un prêt se partagent en deux. La "
               "commission de caution est acquise à l'organisme : c'est "
               "une charge. Mais la part versée au FONDS MUTUEL DE "
               "GARANTIE est restituable en fin de prêt : c'est une "
               "CRÉANCE, pas une dépense — la déduire revient à déduire "
               "une somme qui vous sera rendue. Votre offre de prêt "
               "distingue les deux montants. Les frais d'hypothèque ou de "
               "privilège de prêteur de deniers, eux, ne se restituent "
               "pas : ce sont bien des charges.",
     "sources": ["CGI, art. 39-1 (charge = dépense engagée et définitive)",
                 "PCG, compte 275 « Dépôts et cautionnements versés »"]},
    {"moment": "Au démarrage de l'activité",
     "titre": "Frais d'acquisition : deux conditions à connaître",
     "detail": "L'option pour la déduction immédiate des frais "
               "d'acquisition (notaire, droits de mutation, commission "
               "d'agence) est GLOBALE et irrévocable : elle vaut pour "
               "TOUTES vos immobilisations, pas bien par bien, et vous ne "
               "pourrez pas en changer pour le suivant. Seconde condition, "
               "beaucoup moins connue : si le logement a été acquis AVANT "
               "d'être affecté à la location meublée — le cas le plus "
               "fréquent —, il entre au bilan pour sa valeur à la date "
               "d'affectation, et les frais payés à l'achat d'origine ne "
               "sont alors pas déductibles.",
     "sources": ["CGI, annexe III, art. 38 quinquies",
                 "PCG, art. 213-8"]},
    {"moment": "Charges souvent oubliées",
     "titre": "Assurances et frais bancaires du prêt",
     "detail": "Assurance propriétaire non occupant, assurance loyers "
               "impayés, assurance emprunteur, frais de dossier et de "
               "garantie : souvent oubliés parce qu'ils sont prélevés "
               "automatiquement et n'arrivent pas sous forme de facture."},

    # --- Erreurs de classement ---------------------------------------------
    {"moment": "Erreurs de classement",
     "titre": "Entretien ou amélioration ?",
     "detail": "Une réparation se déduit l'année où elle est engagée ; un "
               "aménagement qui crée un élément nouveau ou augmente la "
               "valeur du bien s'immobilise et s'amortit. C'est l'un des "
               "points les plus regardés en cas de contrôle, parce qu'il "
               "déplace de la charge immédiate vers de l'amortissement "
               "étalé."},
    {"moment": "Erreurs de classement",
     "titre": "Taxe d'habitation : déductible seulement si elle suit le bien",
     "detail": "La taxe d'habitation due parce que VOUS conservez la "
               "jouissance du logement — résidence secondaire, logement "
               "vacant que vous gardez meublé à votre usage — n'est pas "
               "une charge de l'activité : elle ne se déduit pas. Ne la "
               "saisissez que si elle se rattache réellement à "
               "l'exploitation.",
     "sources": ["CGI, art. 39-1 (charges engagées dans l'intérêt de "
                 "l'exploitation)"]},
    {"moment": "Erreurs de classement",
     "titre": "Indemnité d'assurance sur un bien détruit",
     "detail": "Une indemnité qui répare un dommage courant (dégât des "
               "eaux, perte de loyers) est un produit de l'exercice. Mais "
               "une indemnité versée pour la DESTRUCTION ou la disparition "
               "d'un bien immobilisé ne se traite pas comme un produit "
               "ordinaire : elle relève du régime des plus-values, comme "
               "une cession. La confondre avec une indemnité courante "
               "gonfle le résultat imposable à tort.",
     "sources": ["CGI, art. 39 duodecies",
                 "CGI, art. 39 quaterdecies 1 ter"]},
    {"moment": "Erreurs de classement",
     "titre": "Mobilier passé en charge d'un bloc",
     "detail": "Un équipement durable de valeur significative n'est pas "
               "une charge de l'année : il s'amortit sur sa durée "
               "d'usage. L'électroménager et le mobilier ont des durées "
               "plus courtes que le bâti — les traiter en charge gonfle "
               "artificiellement une année et appauvrit les suivantes."},
    {"moment": "Erreurs de classement",
     "titre": "Rattachement : trésorerie en cours d'année, régularisation "
              "à la clôture",
     "detail": "La quasi-totalité des LMNP relèvent du réel SIMPLIFIÉ et "
               "peuvent opter pour la comptabilité « super-simplifiée » — "
               "une case à cocher en tête de la déclaration 2031-SD. Au "
               "quotidien, on enregistre alors les ENCAISSEMENTS et les "
               "PAIEMENTS : c'est une comptabilité de trésorerie, et c'est "
               "ce que fait ce logiciel. Mais l'option ne dispense pas de "
               "tout : à la CLÔTURE, les créances et les dettes doivent "
               "être constatées — une facture de décembre payée en janvier "
               "revient à l'exercice de décembre. Une exception notable "
               "demeure en trésorerie pure : les frais généraux payés à "
               "échéances régulières dont la périodicité n'excède pas un "
               "an (assurance, abonnements). L'administration est explicite "
               "sur le principe : on ne peut pas se limiter à la "
               "trésorerie en faisant abstraction des créances et dettes "
               "de clôture.",
     "sources": ["CGI, art. 302 septies A ter A",
                 "Code de commerce, art. L. 123-25",
                 "BOI-BIC-DECLA-30-20-20"]},
    {"moment": "Erreurs de classement",
     "titre": "Charges récupérables : penser la SYMÉTRIE",
     "detail": "Les provisions encaissées auprès du locataire sont "
               "imposées en produits ; les charges correspondantes se "
               "déduisent. L'erreur n'est pas de déduire, c'est de "
               "déduire SANS avoir déclaré le produit en face — ou "
               "l'inverse. Vérifiez que les deux côtés figurent bien."},

    # --- Avant de déclarer --------------------------------------------------
    {"moment": "Avant de déclarer",
     "titre": "Ne pas déclarer une année sans loyer",
     "detail": "Même sans recette, les charges et les amortissements "
               "existent et peuvent créer un déficit reportable sur les "
               "bénéfices futurs de l'activité. Ne rien déposer, c'est "
               "renoncer à ce report."},
    {"moment": "Avant de déclarer",
     "titre": "Justificatifs : 6 ans au minimum, 10 ans pour les pièces "
              "comptables",
     "detail": "Deux délais à ne pas confondre. Le droit de REPRISE de "
               "l'administration est de 3 ans en matière d'impôt sur le "
               "revenu (jusqu'au 31 décembre de la 3e année suivant celle "
               "de l'imposition), porté à 10 ans en cas d'activité "
               "occulte. L'obligation de CONSERVATION, elle, est de 6 ans "
               "pour les documents sur lesquels l'administration peut "
               "exercer son droit de contrôle, et le Code de commerce "
               "impose 10 ans pour les livres et pièces comptables. En "
               "pratique : gardez 10 ans. Le logiciel archive vos FEC — il "
               "n'archive pas vos factures.",
     "sources": ["LPF, art. L. 169 (droit de reprise : 3 ans)",
                 "LPF, art. L. 102 B (conservation : 6 ans)",
                 "Code de commerce, art. L. 123-22 (10 ans)"]},
    {"moment": "Avant de déclarer",
     "titre": "Deux dépôts, deux espaces, deux dates",
     "detail": "La liasse (2031-SD et tableaux 2033) se dépose depuis "
               "l'espace PROFESSIONNEL d'impots.gouv.fr — « Votre espace "
               "professionnel » puis « Déclarer » — généralement au "
               "2e jour ouvré suivant le 1er mai, avec une tolérance de "
               "15 jours pour la voie dématérialisée. Le résultat est "
               "ensuite reporté sur la 2042-C-PRO, qui se dépose depuis "
               "l'espace PARTICULIER — « Votre espace particulier » puis "
               "« Déclarer mes revenus » — à une date qui varie selon le "
               "département (trois zones). Les deux espaces sont "
               "distincts et demandent chacun leur création. Le "
               "calendrier exact est publié chaque année sur "
               "impots.gouv.fr, rubrique « Professionnel > Déclarer > "
               "Résultats ». Un dépôt tardif déclenche une majoration.",
     "sources": ["impots.gouv.fr — espaces professionnel et particulier",
                 "CGI, art. 1728 (majorations pour dépôt tardif)"]},
    {"moment": "Avant de déclarer",
     "titre": "Amortissements et revente",
     "detail": "Une évolution introduite en 2025 modifie le traitement "
               "des amortissements pratiqués lors du calcul de la "
               "plus-value de revente. Cela ne change rien à la tenue "
               "courante, mais beaucoup en découvrent l'effet au moment "
               "de vendre : si une cession se profile, faites le point "
               "avant de signer."},
]


# ── Actualités réglementaires ───────────────────────────────────────────────
# Faits DATÉS et sourcés, distincts de la checklist intemporelle. Ils
# vieillissent : chacun porte sa date de vérification, et le module de
# veille fiscale sert précisément à les remettre en question.
VERIFIE_LE = "13 août 2026"

ACTUALITES = [
    {"titre": "Facturation électronique : une échéance vous concerne au "
              "1er septembre 2026",
     "resume": "Contrairement à une idée répandue, la réforme touche AUSSI "
               "les loueurs meublés dont les loyers sont exonérés de TVA.",
     "detail":
        "La ligne de partage n'est pas l'exonération, mais "
        "l'ASSUJETTISSEMENT. Vos loyers d'habitation sont exonérés de TVA "
        "(CGI art. 261 D), mais votre activité reste assujettie dès lors "
        "qu'elle est immatriculée et dispose d'un SIREN. La fiche "
        "officielle de la DGFiP est explicite : les bailleurs exonérés "
        "n'ont pas d'obligation d'ÉMISSION, mais « en réception, bien "
        "qu'exonérés, ils restent assujettis à la TVA et devront recevoir "
        "des factures électroniques, sous réserve de disposer également "
        "d'un numéro SIREN ».\n\n"
        "Ce que cela implique concrètement :\n"
        "• RÉCEPTION — au 1er septembre 2026, vous devez être en mesure de "
        "recevoir les factures de vos fournisseurs professionnels "
        "(artisans, assureur, syndic, comptable) au format électronique, "
        "via une plateforme agréée. Il suffit de choisir une plateforme et "
        "d'y référencer votre SIREN.\n"
        "• ÉMISSION — elle ne vous concerne PAS si vos loyers sont "
        "exonérés. Une quittance de loyer n'est pas une facture. "
        "L'obligation d'émission vise les loueurs redevables de la TVA "
        "(para-hôtellerie, résidences de services), au 1er septembre 2027 "
        "pour les petites et moyennes entreprises.\n\n"
        "La liste officielle des plateformes agréées est publiée sur "
        "impots.gouv.fr. Aucune n'est imposée : le choix vous appartient, "
        "et méfiez-vous des messages qui présentent une plateforme "
        "particulière comme obligatoire.",
     "sources": [
        "DGFiP — fiche « Facturation électronique : je suis un loueur en "
        "meublé » (version octobre 2025)",
        "CGI, art. 261 D (exonération de TVA des loyers d'habitation)",
        "CGI, art. 289 bis (e-invoicing) et 290 (e-reporting)",
        "Ordonnance n° 2021-1190 du 15 septembre 2021"]},
]

# Échéances récurrentes de l'activité. Mois et jour seulement : l'année est
# calculée à l'affichage, pour que le tableau ne périme pas.
ECHEANCES = [
    {"quand": "2e jour ouvré après le 1er mai (+15 j en ligne)",
     "quoi": "Déclaration de résultats 2031-SD et tableaux 2033",
     "ou": "impots.gouv.fr — espace PROFESSIONNEL"},
    {"quand": "mai-juin, selon le département",
     "quoi": "Déclaration de revenus 2042-C-PRO (report du résultat)",
     "ou": "impots.gouv.fr — espace PARTICULIER"},
    {"quand": "1er septembre 2026",
     "quoi": "Être en mesure de RECEVOIR des factures électroniques",
     "ou": "plateforme agréée de votre choix (liste sur impots.gouv.fr)"},
    {"quand": "15 octobre (prélèvement : 20 octobre)",
     "quoi": "Taxe foncière",
     "ou": "impots.gouv.fr — espace particulier"},
    {"quand": "15 décembre",
     "quoi": "Cotisation foncière des entreprises (CFE)",
     "ou": "impots.gouv.fr — espace PROFESSIONNEL"},
    {"quand": "1er septembre 2027",
     "quoi": "Émission de factures électroniques — SEULEMENT si vous êtes "
             "redevable de la TVA (para-hôtellerie, résidences de services)",
     "ou": "votre plateforme agréée"},
]


def actualites() -> dict:
    """Actualités datées + échéances. Séparées de la checklist : les unes
    périment, l'autre non."""
    # Clé « faits » et non « items » : en gabarit Jinja, « actualites.items »
    # résout la MÉTHODE items() du dictionnaire, pas la clé — l'affichage
    # échouait sur « builtin_function_or_method is not iterable ».
    return {"verifie_le": VERIFIE_LE, "faits": ACTUALITES,
            "echeances": ECHEANCES}


# ── Bloc-notes personnel ────────────────────────────────────────────────────
# Conservé dans la table `meta` du dossier : il suit donc les sauvegardes,
# les restaurations et les changements de dossier, sans schéma supplémentaire.
CLE_NOTES = "notes_personnelles"


def lire_notes(conn) -> str:
    r = conn.execute("SELECT valeur FROM meta WHERE cle=?",
                     (CLE_NOTES,)).fetchone()
    return (r[0] if r else "") or ""


def ecrire_notes(conn, texte: str) -> None:
    conn.execute(
        "INSERT INTO meta (cle, valeur) VALUES (?,?) "
        "ON CONFLICT(cle) DO UPDATE SET valeur=excluded.valeur",
        (CLE_NOTES, (texte or "").strip()))
    conn.commit()


def oublis_frequents() -> list[dict]:
    """Checklist statique, groupée par moment de la vie du dossier."""
    groupes: dict[str, list[dict]] = {}
    for o in OUBLIS_FREQUENTS:
        groupes.setdefault(o["moment"], []).append(o)
    return [{"moment": m, "points": pts} for m, pts in groupes.items()]


def _ca(conn: sqlite3.Connection, annee: int) -> float:
    return conn.execute(
        "SELECT COALESCE(SUM(l.credit-l.debit),0) FROM ligne l "
        "JOIN ecriture e ON e.id=l.ecriture_id "
        "JOIN compte c ON c.numero=l.compte_num "
        "WHERE e.exercice_annee=? AND c.classe=7", (annee,)).fetchone()[0]


def rappels(conn: sqlite3.Connection, aujourd_hui: date | None = None,
            db_path: str | None = None) -> list[dict]:
    auj = aujourd_hui or date.today()
    N = auj.year
    out: list[dict] = []

    def add(niveau, titre, detail):
        out.append({"niveau": niveau, "titre": titre, "detail": detail})

    import operations as _ops
    _ops.assurer_colonne_annulee(conn)
    exercices = dict(conn.execute("SELECT annee, statut FROM exercice"))

    # ── Cycle déclaratif de l'exercice précédent ─────────────────────────
    prec = N - 1
    if exercices.get(prec) == "ouvert":
        if auj.month >= 5:
            add("important", f"Clôturer l'exercice {prec}",
                f"L'exercice {prec} est toujours ouvert alors que la période "
                "déclarative est engagée (télétransmission de la liasse "
                "généralement mi-mai). Passez les dernières écritures, lancez "
                "les contrôles puis la clôture — sans elle, pas de liasse "
                "définitive à déclarer.")
        elif auj.month >= 2:
            add("a_prevoir", f"Préparer la clôture de l'exercice {prec}",
                "Rassemblez les dernières pièces (relevés de décembre, "
                "quittances, factures) et saisissez le fonds travaux ALUR "
                "de l'année le cas échéant, avant de clôturer.")
    if exercices.get(prec) == "clos" and 2 <= auj.month <= 6:
        add("important", f"Déclarer les résultats {prec}",
            "La clôture ne déclare RIEN : télétransmettez la liasse "
            f"(2031 + 2033) au titre de {prec} — via votre "
            "expert-comptable/EDI ou votre espace impots.gouv.fr — "
            "généralement pour mi-mai, puis reportez le résultat sur la "
            "2042C-PRO de votre déclaration de revenus (aide dédiée dans "
            "l'onglet Liasse). Vérifiez les dates exactes de l'année sur "
            "impots.gouv.fr.")

    # ── Échéances calendaires ────────────────────────────────────────────
    if auj.month in (10, 11):
        add("a_prevoir", "Taxe foncière puis CFE",
            "La taxe foncière se paie généralement mi-octobre, l'avis de "
            "CFE arrive en novembre sur votre espace professionnel "
            "impots.gouv.fr (aucun avis papier n'est envoyé) pour un "
            "paiement au 15 décembre. Pensez à saisir ces paiements ici "
            "(gabarits Taxe foncière et CFE).")
    if auj.month == 12:
        add("important", "Payer la CFE avant le 15 décembre",
            "Le paiement se fait en ligne sur votre espace professionnel "
            "impots.gouv.fr. Saisissez ensuite l'opération (gabarit CFE — "
            "exclue à juste titre du plafond 39 C par le logiciel).")

    # ── Événements : biens ───────────────────────────────────────────────
    for bid, lib, acq in conn.execute(
            "SELECT id, libelle, date_acquisition FROM bien "
            "WHERE date_acquisition IS NOT NULL"):
        try:
            annee_acq = int(str(acq)[:4])
        except (ValueError, TypeError):
            continue
        if annee_acq == N:
            add("important", f"Formalités pour « {lib} » (acquis en {N})",
                "Un nouveau bien mis en location meublée doit être déclaré "
                "dans les 15 jours du début d'activité via le guichet unique "
                "de l'INPI (début ou extension d'activité — l'équivalent de "
                "l'ancien P0i/P2P2i) ; déposez aussi la déclaration initiale "
                "de CFE (1447-C) avant le 31 décembre. Si ce bien devient "
                "celui qui rapporte le plus, l'adresse d'activité (page "
                "Immobilisations) doit être mise à jour en conséquence.")

    # ── Événements : cession d'un bien dans l'année ──────────────────────
    try:
        cessions = conn.execute(
            "SELECT libelle, date_cession FROM bien WHERE date_cession IS NOT "
            "NULL AND date_cession >= ? AND date_cession < ?",
            (f"{N}-01-01", f"{N + 1}-01-01")).fetchall()
    except sqlite3.OperationalError:
        cessions = []
    for lib, dc in cessions:
        add("important", f"Cession de « {lib} » ({dc}) — démarches",
            "La plus-value relève du régime des PARTICULIERS : calculée et "
            "déclarée par le notaire (2048-IMM) lors de la vente — depuis "
            "2025, les amortissements déduits sont réintégrés dans son "
            "calcul. Le stock 39 C attaché au bien est définitivement perdu "
            "(ligne G' de l'état SUIV39C, suivi automatiquement). Si c'était "
            "votre DERNIER bien loué : déclarez la cessation d'activité au "
            "guichet INPI dans les 30 jours et déposez la liasse de "
            "cessation dans les 60 jours ; sinon, mettez à jour l'adresse "
            "d'activité si nécessaire.")

    # ── Seuils LMP ───────────────────────────────────────────────────────
    for annee, statut in sorted(exercices.items()):
        if statut != "ouvert" or annee > N:
            continue
        ca = _ca(conn, annee)
        # Le seuil est une RÈGLE VERSIONNÉE, comme pour le contrôle métier :
        # la constante écrite ici ignorait la valeur enregistrée, et le
        # rappel restait muet sur 20 000 € de recettes face à un seuil
        # configuré à 15 000 €. Les deux consommateurs de la même règle
        # doivent répondre la même chose.
        try:
            import parametres as _param
            seuil_lmp = float(_param.valeur(conn, "seuil_lmp_recettes",
                                            annee, defaut=23000.0))
        except Exception:                            # noqa: BLE001
            seuil_lmp = 23000.0
        if ca > seuil_lmp:
            add("important", f"CA {annee} : {ca:,.0f} € — seuil LMP franchi ?",
                f"Au-delà de {seuil_lmp:,.0f} € de recettes, le statut LMP "
                "s'applique "
                "si elles excèdent AUSSI les autres revenus d'activité du "
                "foyer — avec affiliation sociale (SSI) possible dès "
                "23 000 € selon le mode de location. Vérifiez votre "
                "situation (le logiciel est conçu pour le LMNP).")

    # ── Fonds travaux ALUR jamais saisi (copropriété probable) ───────────
    annee_ouverte = max((a for a, s in exercices.items() if s == "ouvert"),
                        default=None)
    if annee_ouverte:
        copro = conn.execute(
            "SELECT COUNT(*) FROM operation WHERE COALESCE(annulee,0)=0 "
            "AND exercice_annee=? AND type='charge_copro'", (annee_ouverte,)).fetchone()[0]
        alur = conn.execute(
            "SELECT COUNT(*) FROM operation WHERE COALESCE(annulee,0)=0 "
            "AND exercice_annee=? AND type='fonds_travaux_alur'", (annee_ouverte,)).fetchone()[0]
        if copro and not alur:
            add("a_prevoir", "Fonds travaux ALUR non saisi cette année",
                "Des charges de copropriété sont saisies mais aucun fonds "
                "travaux ALUR : si vos appels de fonds en contiennent un "
                "(relevé du syndic), saisissez-le via son gabarit dédié — "
                "il n'est pas déductible et le logiciel le réintègre "
                "automatiquement à la clôture.")

    # ── Veille fiscale ───────────────────────────────────────────────────
    try:
        import veille_fiscale
        if veille_fiscale.veille_a_refaire(conn, auj):
            derniere = veille_fiscale.derniere_veille(conn)
            add("a_prevoir", "Veille fiscale à faire",
                ("Aucune veille n'a encore été déclarée." if not derniere
                 else f"Dernière veille : {derniere}.")
                + " Une loi de finances par an peut modifier un seuil, la "
                "durée de report des déficits ou le traitement d'une "
                "cession — ce logiciel applique les règles telles qu'elles y "
                "sont enregistrées. Le menu « Veille fiscale » fournit le "
                "corpus des textes et une question type à poser à une IA.")
    except Exception as exc:               # noqa: BLE001
        # Le rappel était simplement abandonné : une consultation de veille
        # en panne produisait donc la même sortie qu'une veille à jour. Ne
        # pas pouvoir vérifier n'est pas avoir vérifié — on le dit.
        add("a_prevoir", "Veille fiscale : état inconnu",
            f"La date de dernière veille n'a pas pu être lue ({exc}). Le "
            "logiciel ne peut donc pas dire si les règles enregistrées ont "
            "été revues récemment — vérifiez-le depuis le menu « Veille "
            "fiscale ».")

    # ── Sauvegardes ──────────────────────────────────────────────────────
    if db_path:
        dossier = os.path.join(os.path.dirname(os.path.abspath(db_path)),
                               "sauvegardes")
        recentes = []
        if os.path.isdir(dossier):
            seuil = auj.toordinal() - 35
            recentes = [f for f in os.listdir(dossier)
                        if os.path.isfile(os.path.join(dossier, f)) and
                        date.fromtimestamp(os.path.getmtime(
                            os.path.join(dossier, f))).toordinal() >= seuil]
        if not recentes:
            add("info", "Aucune sauvegarde récente détectée",
                "Les sauvegardes automatiques se font au lancement du "
                "logiciel (une par jour) : lancez-le régulièrement, et "
                "copiez de temps en temps le dossier « sauvegardes » sur "
                "un support externe. Une restauration se teste AVANT d'en "
                "avoir besoin.")

    # ── Oublis récurrents DÉTECTABLES dans le dossier ──────────────────────
    # La checklist ci-dessous est générique ; ces deux rappels-ci, eux,
    # regardent réellement ce qui a été saisi. C'est toute la différence
    # entre un mémo et une alerte utile.
    biens = conn.execute("SELECT COUNT(*) FROM bien").fetchone()[0]
    if biens:
        frais = conn.execute(
            "SELECT COUNT(*) FROM composant WHERE libelle LIKE '%notaire%' "
            "OR libelle LIKE '%acquisition%' OR libelle LIKE '%agence%' "
            "OR categorie LIKE '%frais%'").fetchone()[0]
        if not frais:
            add("info", "Frais d'acquisition : rien d'enregistré",
                "Aucun composant ne correspond à des frais de notaire, "
                "droits de mutation ou commission d'agence. C'est l'oubli "
                "le plus coûteux de la première année : selon l'option "
                "retenue, ces frais se déduisent l'année de l'acquisition "
                "ou s'amortissent avec le bien. S'ils ont déjà été traités "
                "ailleurs, ignorez ce rappel.")
        mobilier = conn.execute(
            "SELECT COUNT(*) FROM composant WHERE compte_immo LIKE '2184%'"
        ).fetchone()[0]
        if not mobilier:
            add("info", "Aucun mobilier immobilisé",
                "La location meublée suppose un mobilier suffisant, qui "
                "s'amortit sur une durée plus courte que le bâti. Aucun "
                "composant de mobilier ou d'électroménager n'est "
                "enregistré : soit il a été passé en charge (à vérifier), "
                "soit il reste à saisir dans la page Immobilisations.")

    ordre = {"important": 0, "a_prevoir": 1, "info": 2}
    out.sort(key=lambda r: ordre[r["niveau"]])
    return out
````


## `compta_lmnp/modules/veille_fiscale.py`

````python
# Compta LMNP — Copyright © 2026 Sylvain FAURE et les contributeurs.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Veille fiscale — le logiciel ne se met PAS à jour tout seul.

Les règles sont versionnées (parametres.py) : le moteur applique la valeur
en vigueur pour l'exercice traité. Mais personne n'avertit le logiciel
qu'une loi de finances a changé un seuil — c'est à l'exploitant de le
faire, et ce module l'y aide à l'ouverture de chaque exercice :

  1. il recense le CORPUS des textes qui régissent le LMNP, chacun rattaché
     au module du logiciel qu'il gouverne et, le cas échéant, à la règle
     versionnée correspondante ;
  2. il fabrique un PROMPT prêt à coller dans n'importe quelle IA
     conversationnelle disposant d'une recherche web, pour demander ce qui
     a changé depuis la dernière vérification ;
  3. il mémorise la date de la dernière veille (table meta) pour la
     rappeler quand elle vieillit.

⚠️ Ce module ne donne AUCUN conseil fiscal : il aide à poser les bonnes
questions. Toute évolution constatée doit être vérifiée sur les sources
officielles (Légifrance, BOFiP, impots.gouv.fr) et, en cas de doute,
auprès d'un expert-comptable. Une réponse d'IA n'est pas une source.
"""
from __future__ import annotations

import datetime
import sqlite3

# Date à laquelle ce corpus a été revu. Sert à dater le prompt par défaut
# et à signaler que le corpus lui-même mériterait une relecture.
CORPUS_REVU_LE = "2026-07-20"

# (référence, intitulé, ce que le texte gouverne DANS CE LOGICIEL, règle liée)
CORPUS = [
    # ── Qualification et champ du régime ────────────────────────────────
    ("Art. 155, IV du CGI",
     "Définition du loueur en meublé professionnel (LMP)",
     "Frontière LMNP / LMP : recettes supérieures à 23 000 € ET supérieures "
     "aux autres revenus professionnels du foyer. Détermine si ce logiciel "
     "est adapté à votre situation.",
     "seuil_lmp_recettes"),
    ("Art. 156, I-1° ter du CGI",
     "Déficits de location meublée non professionnelle",
     "Les déficits ne s'imputent QUE sur des bénéfices de location meublée "
     "non professionnelle, pendant 10 ans. Moteur des déficits (FIFO par "
     "millésime, expiration).",
     "duree_report_deficit_lmnp"),
    ("Art. 50-0 du CGI",
     "Régime micro-BIC",
     "Seuils et abattements du forfait. Ce logiciel tient une comptabilité "
     "au RÉEL : le micro n'est rappelé qu'à titre de comparaison.",
     "seuil_micro_bic_meuble"),
    ("BOI-BIC-CHAMP-40-10 et BOI-BIC-CHAMP-40-20",
     "Doctrine administrative — champ et régime de la location meublée",
     "Commentaires de l'administration sur la qualification LMP/LMNP et le "
     "régime applicable.", None),

    # ── Amortissements (cœur du moteur) ─────────────────────────────────
    ("Art. 39 C, II-2 du CGI",
     "Limitation de la déduction des amortissements",
     "LE calcul central du logiciel : l'amortissement déductible est plafonné "
     "au loyer acquis diminué des autres charges afférentes au bien ; "
     "l'excédent est reporté sans limite de durée (état de suivi SUIV39C).",
     None),
    ("BOI-BIC-AMT-20-40-10-20 et -10-30",
     "Doctrine — calcul de l'amortissement déductible et suivi des "
     "amortissements excédentaires",
     "Modalités de calcul du plafond et obligation de suivi annuel du stock "
     "reportable, y compris logement par logement en cas de pluralité de "
     "biens.", None),
    ("Art. 39-1 du CGI et règlement ANC n° 2014-03 (PCG)",
     "Charges déductibles ; amortissement par composants",
     "Décomposition des biens (gros œuvre, étanchéité, agencements, "
     "mobilier…), durées d'usage, terrain non amortissable.",
     "seuil_immobilisation"),

    # ── Sortie du bien ──────────────────────────────────────────────────
    ("Art. 150 U et suivants du CGI",
     "Plus-values immobilières des particuliers",
     "Régime applicable à la cession d'un bien LMNP : la plus-value est "
     "calculée et déclarée par le NOTAIRE (2048-IMM). Le logiciel neutralise "
     "donc la cession dans le résultat BIC.", None),
    ("Art. 150 VB du CGI, modifié par la loi de finances pour 2025 "
     "(loi n° 2025-127 du 14 février 2025)",
     "Réintégration des amortissements dans la plus-value",
     "Depuis 2025, le prix d'acquisition retenu pour la plus-value est "
     "diminué des amortissements déduits. Le suivi des amortissements tenu "
     "par le logiciel devient une pièce à fournir au notaire.", None),

    # ── Obligations déclaratives et comptables ──────────────────────────
    ("Art. 53 A et 302 septies A bis du CGI",
     "Déclaration de résultats (2031-SD) et régime réel simplifié "
     "(2033-A à 2033-G)",
     "Contenu et structure de la liasse produite par le logiciel.", None),
    ("Art. L. 47 A-I du LPF et arrêté A-47 A-1 du LPF",
     "Fichier des écritures comptables (FEC)",
     "Format exigé lors d'un contrôle : 18 colonnes, dates AAAAMMJJ, "
     "séquence des écritures. Gouverne l'export ET le validateur.", None),
    ("Art. 286 quater du CGI et art. L. 102 B du LPF",
     "Conservation des pièces et documents comptables",
     "Durée de conservation des justificatifs, du FEC et des archives "
     "produites par le logiciel.", None),

    ("BOI-BIC-CHG-40-20",
     "Fonds de travaux ALUR : charge non déductible",
     "La contribution au fonds de travaux est CAPITALISÉE : elle est "
     "réintégrée au résultat fiscal à la clôture. Le logiciel le fait "
     "automatiquement, et cette réintégration majore aussi le plafond "
     "d'amortissement déductible de l'article 39 C — une règle qui change "
     "donc réellement le résultat, et qui doit être revue comme les "
     "autres.", "retraitement_alur_auto"),

    # ── Fiscalité annexe ────────────────────────────────────────────────
    ("Art. 261 D, 4° du CGI",
     "Exonération de TVA de la location meublée",
     "Pourquoi le logiciel raisonne en TTC et ne gère pas de TVA "
     "(sauf para-hôtellerie, hors périmètre).", None),
    ("Art. 1447 et suivants du CGI",
     "Cotisation foncière des entreprises (CFE)",
     "Due par le loueur en meublé ; déclaration initiale 1447-C. Rappelée "
     "par le pense-bête, exclue du plafond 39 C par le moteur.", None),
    ("Loi n° 2024-1039 du 19 novembre 2024 (dite « loi Le Meur »)",
     "Meublés de tourisme",
     "Seuils et abattements du micro-BIC pour les meublés de tourisme, "
     "classement, obligations locales. Concerne la location saisonnière.",
     None),
]

# Points d'attention connus au moment de la revue du corpus — à confirmer.
ACTUALITE_CONNUE = [
    "Loi de finances pour 2025 : réintégration des amortissements dans le "
    "calcul de la plus-value de cession (art. 150 VB du CGI).",
    "Loi de finances pour 2026 (promulguée le 19 février 2026) : "
    "l'amortissement reste déductible sans plafonnement ; hausse annoncée "
    "des prélèvements sociaux sur les revenus BIC (17,2 % → 18,6 %) ; "
    "création d'un statut de bailleur privé ; règles particulières pour les "
    "non-résidents. À VÉRIFIER et à préciser lors de votre veille.",
    "Loi Le Meur (2024) : abattements et seuils du micro-BIC des meublés de "
    "tourisme non classés.",
]


def _table_meta(conn: sqlite3.Connection) -> None:
    conn.execute("CREATE TABLE IF NOT EXISTS meta ("
                 "cle TEXT PRIMARY KEY, valeur TEXT NOT NULL)")


def derniere_veille(conn: sqlite3.Connection) -> str | None:
    """Date (AAAA-MM-JJ) de la dernière veille déclarée, ou None."""
    _table_meta(conn)
    row = conn.execute("SELECT valeur FROM meta WHERE cle='derniere_veille'"
                       ).fetchone()
    return row[0] if row else None


def enregistrer_veille(conn: sqlite3.Connection,
                       jour: str | None = None) -> str:
    """Mémorise qu'une veille vient d'être faite."""
    _table_meta(conn)
    jour = jour or datetime.date.today().isoformat()
    # Une veille se constate, elle ne se planifie pas : une date FUTURE
    # enregistrée par erreur — 2099 dans le cas reproduit — éteignait le
    # rappel pour des décennies, sans que rien ne signale l'incohérence.
    try:
        saisie = datetime.date.fromisoformat(jour)
    except ValueError:
        raise ValueError(f"Date de veille illisible : {jour!r} "
                         "(format attendu AAAA-MM-JJ).") from None
    if saisie > datetime.date.today():
        raise ValueError(
            f"Date de veille dans le futur : {jour}. Une veille s'enregistre "
            "le jour où elle est faite — une date future éteindrait le "
            "rappel jusque-là.")
    conn.execute("INSERT INTO meta (cle, valeur) VALUES ('derniere_veille', ?) "
                 "ON CONFLICT(cle) DO UPDATE SET valeur=excluded.valeur",
                 (jour,))
    conn.commit()
    return jour


def veille_a_refaire(conn: sqlite3.Connection,
                     aujourd_hui: datetime.date | None = None) -> bool:
    """Vrai si aucune veille n'a jamais été faite, ou si la dernière remonte
    à plus de 11 mois (une loi de finances par an, publiée fin décembre)."""
    auj = aujourd_hui or datetime.date.today()
    derniere = derniere_veille(conn)
    if not derniere:
        return True
    try:
        d = datetime.date.fromisoformat(derniere)
    except ValueError:
        return True
    # Une date postérieure à aujourd'hui ne prouve aucune veille faite :
    # l'écart en jours est alors négatif, et le test « plus de 334 jours »
    # concluait tranquillement que tout allait bien.
    if d > auj:
        return True
    return (auj - d).days > 334


def prompt_veille(annee_exercice: int, depuis: str | None = None) -> str:
    """
    Prompt prêt à coller dans une IA conversationnelle disposant d'une
    recherche web. Il est volontairement exigeant sur les SOURCES et sur la
    distinction adopté / en discussion : c'est là que les réponses d'IA
    dérapent le plus souvent en matière fiscale.
    """
    depuis = depuis or CORPUS_REVU_LE
    textes = "\n".join(f"- {ref} — {intitule}"
                       for ref, intitule, _effet, _regle in CORPUS)
    return f"""Tu es assisté d'une recherche web. Nous sommes le \
{datetime.date.today().isoformat()}.

CONTEXTE
Je tiens moi-même la comptabilité d'une activité de location meublée non
professionnelle (LMNP) au régime réel simplifié, en France. Je prépare
l'exercice {annee_exercice}. Je dois savoir ce qui a changé dans la
réglementation depuis le {depuis}.

TEXTES QUI RÉGISSENT MON RÉGIME (corpus de référence)
{textes}

CE QUE JE TE DEMANDE
1. Pour CHACUN de ces textes, indique s'il a été modifié, complété ou
   commenté depuis le {depuis} (loi de finances, loi de financement de la
   sécurité sociale, autre loi, décret, arrêté, mise à jour BOFiP,
   jurisprudence significative).
2. Signale aussi tout texte NOUVEAU qui concernerait la location meublée
   non professionnelle et qui ne figurerait pas dans ma liste.
3. Pour chaque évolution, précise :
   - la référence exacte (loi/décret/BOFiP + date + numéro d'article) ;
   - la date d'entrée en vigueur et les exercices concernés ;
   - en une phrase, ce qui change concrètement ;
   - l'impact sur : (a) le calcul des amortissements déductibles
     (art. 39 C), (b) le report et l'expiration des déficits, (c) les
     seuils (LMP, micro-BIC, immobilisation), (d) la plus-value de
     cession, (e) les obligations déclaratives (liasse, FEC).
4. Dis-moi où en est la réforme de la FACTURATION ÉLECTRONIQUE pour les
   loueurs meublés : calendrier effectif (obligation de réception, puis
   d'émission), report éventuel, et ce qui change pour un bailleur dont
   les loyers sont exonérés de TVA mais qui reste assujetti.
5. Dis-moi si les MODÈLES DÉCLARATIFS eux-mêmes ont changé : millésime en
   vigueur des formulaires 2031-SD, 2033-A à 2033-G et 2042-C-PRO,
   création ou suppression de cases, renumérotation, nouvelles rubriques
   obligatoires. Un logiciel qui produit une liasse sur un modèle périmé
   sort des chiffres justes dans des cases fausses : je dois le savoir
   même quand la règle de fond, elle, n'a pas bougé.
6. Distingue CLAIREMENT ce qui est DÉFINITIVEMENT ADOPTÉ et en vigueur de
   ce qui n'est qu'un projet, un amendement déposé ou une proposition en
   discussion. Ne présente jamais un projet comme du droit positif.
7. Termine par une liste des VALEURS CHIFFRÉES en vigueur pour
   {annee_exercice} : seuil LMP, seuils et abattements micro-BIC, durée de
   report des déficits, seuil d'immobilisation, taux des prélèvements
   sociaux sur les BIC.

EXIGENCES DE FIABILITÉ
- Cite tes sources avec des liens vers Légifrance, le BOFiP
  (bofip.impots.gouv.fr) ou impots.gouv.fr ; les articles de blogs ne font
  pas foi.
- Si tu n'es pas certain d'un point, dis-le explicitement plutôt que de
  formuler une réponse plausible.
- N'invente aucun numéro d'article ni aucune date.
- Termine par la liste des points qui, selon toi, méritent l'avis d'un
  expert-comptable."""


def resume(conn: sqlite3.Connection, annee: int) -> dict:
    """Tout ce dont la page de veille a besoin."""
    return {"corpus": CORPUS, "actualite": ACTUALITE_CONNUE,
            "corpus_revu_le": CORPUS_REVU_LE,
            "derniere_veille": derniere_veille(conn),
            "a_refaire": veille_a_refaire(conn),
            "prompt": prompt_veille(annee, derniere_veille(conn))}
````


## `compta_lmnp/modules/parametres.py`

````python
# Compta LMNP — Copyright © 2026 Sylvain FAURE et les contributeurs.
# SPDX-License-Identifier: AGPL-3.0-or-later

"""
Règles fiscales VERSIONNÉES — le point d'entrée des dispositions légales.

Principe : aucune valeur réglementaire (seuil, durée, taux, activation d'un
retraitement) n'est figée dans le code. Chaque règle vit dans la table
`regle_fiscale` avec une période de validité :

    cle | valeur | date_debut | date_fin (NULL = en vigueur) | reference | commentaire

Quand une loi de finances change un seuil, on n'édite PAS le code : on
enregistre une nouvelle valeur avec sa date d'effet (menu « Réglementation »
ou `definir()`). Le moteur sélectionne automatiquement la valeur en vigueur
pour l'exercice traité — les exercices passés restent calculés avec les
règles de leur époque (millésime), condition indispensable pour rejouer ou
justifier un exercice ancien.

Règles livrées (valeurs 2026, références légales en commentaire) :
    seuil_immobilisation        500 €   BOI-BIC-CHG-20-30-10 (tolérance)
    duree_report_deficit_lmnp   10 ans  art. 156, I-1° ter CGI
    seuil_lmp_recettes          23 000  art. 155, IV CGI
    seuil_micro_bic_meuble      77 700  art. 50-0 CGI
    retraitement_alur_auto      1       fonds travaux non déductible
                                        (BOI-BIC-CHG-40-20 ; provision, pas charge)
"""
from __future__ import annotations

import datetime
import math

import sqlite3

# (cle, valeur, date_debut, reference, commentaire, libelle humain)
REGLES_DEFAUT = [
    ("seuil_immobilisation", 500.0, "2000-01-01",
     "BOI-BIC-CHG-20-30-10",
     "Tolérance administrative : matériel/mobilier < 500 € HT passé en charge.",
     "Seuil d'immobilisation (€)"),
    ("duree_report_deficit_lmnp", 10, "2000-01-01",
     "Art. 156, I-1° ter CGI",
     "Déficit LMNP imputable sur revenus de même nature pendant N années.",
     "Report des déficits LMNP (années)"),
    ("seuil_lmp_recettes", 23000.0, "2000-01-01",
     "Art. 155, IV CGI",
     "Recettes annuelles au-delà desquelles le statut LMP peut s'appliquer.",
     "Seuil LMP — recettes (€)"),
    ("seuil_micro_bic_meuble", 77700.0, "2023-01-01",
     "Art. 50-0 CGI",
     "Plafond micro-BIC location meublée (cas général).",
     "Seuil micro-BIC meublé (€)"),
    ("retraitement_alur_auto", 1, "2000-01-01",
     "BOI-BIC-CHG-40-20",
     "Réintégration fiscale automatique du fonds travaux ALUR à la clôture "
     "(1 = active, 0 = inactive).",
     "Réintégration ALUR automatique (0/1)"),
]

LIBELLES = {cle: lib for cle, *_rest, lib in REGLES_DEFAUT}

# Où chaque règle agit RÉELLEMENT. Une règle versionnée n'a de valeur que si
# l'utilisateur sait ce qu'elle change : un seuil qui ne sert qu'à émettre un
# avertissement ne doit pas être confondu avec une règle qui modifie le
# résultat fiscal. Affiché en clair dans le menu « Réglementation ».
IMPACTS = {
    "seuil_immobilisation": (
        "Contrôle de saisie",
        "Avertissement avant clôture si une dépense au-delà du seuil est "
        "passée en charge (elle relèverait plutôt d'une immobilisation). "
        "N'change JAMAIS le compte utilisé ni le résultat : c'est à vous de "
        "requalifier la dépense si l'avertissement est justifié."),
    "duree_report_deficit_lmnp": (
        "Clôture fiscale",
        "Durée de vie des déficits LMNP : au-delà, un déficit non imputé "
        "expire et disparaît des reports."),
    "seuil_lmp_recettes": (
        "Pense-bête",
        "Au-delà de ce montant de recettes, un rappel signale le passage "
        "possible au statut LMP. Aucun effet sur les calculs."),
    "seuil_micro_bic_meuble": (
        "Information",
        "Plafond du régime micro-BIC, rappelé à titre indicatif : ce "
        "logiciel tient une comptabilité au réel."),
    "retraitement_alur_auto": (
        "Clôture fiscale",
        "À 1 (valeur livrée) : le fonds travaux ALUR saisi dans l'exercice "
        "est réintégré automatiquement au résultat fiscal, sans saisie "
        "manuelle. À 0 : la réintégration devient votre responsabilité."),
}


def impact(cle: str) -> tuple[str, str]:
    """(module concerné, effet concret) — « Non documenté » si règle ajoutée
    par l'utilisateur."""
    return IMPACTS.get(cle, ("Non documenté",
                             "Règle personnalisée : son effet dépend de "
                             "l'usage qui en est fait."))


# Domaine de validité de chaque règle livrée : (minimum, maximum, entier).
# Une règle fiscale est versionnable, pas arbitraire. Sans domaine, une
# durée de report saisie à ZÉRO faisait expirer un déficit l'année même de
# sa naissance — 1 200 € purgés par le moteur, et un bénéfice de 1 200 €
# laissé sans son imputation. Un seuil négatif, lui, déclenche une alerte
# sur toute dépense ; un seuil démesuré n'en déclenche plus aucune.
DOMAINES: dict[str, tuple] = {
    "seuil_immobilisation": (1.0, 100_000.0, False),
    "duree_report_deficit_lmnp": (1.0, 30.0, True),
    "seuil_lmp_recettes": (1.0, 10_000_000.0, False),
    "seuil_micro_bic_meuble": (1.0, 10_000_000.0, False),
    "retraitement_alur_auto": (0.0, 1.0, True),
}


# Marque apposée au commentaire d'une règle RECRÉÉE après coup, c'est-à-dire
# réapparue alors que d'autres règles existaient déjà — signature d'une
# configuration perdue, et non d'une première initialisation.
MARQUE_RETABLIE = " [rétablie à sa valeur livrée]"
# Clé de `meta` posée au premier ensemencement des règles.
MARQUE_SEMEES = "regles_fiscales_semees_le"


def regles_retablies(conn: sqlite3.Connection) -> list[str]:
    """Clés des règles recréées à leur valeur livrée après une disparition.

    Leur valeur d'origine n'est pas récupérable : la table d'historique ne
    conserve que ce qui s'y trouve. Le seul service honnête est de DIRE
    que la valeur affichée n'est peut-être pas celle qui s'appliquait.
    """
    assurer(conn)
    return [r[0] for r in conn.execute(
        "SELECT DISTINCT cle FROM regle_fiscale WHERE commentaire LIKE ?",
        ("%" + MARQUE_RETABLIE + "%",))]


def verifier_domaine(cle: str, valeur_numerique: float) -> None:
    """Lève ValueError si la valeur sort du domaine admis pour cette règle."""
    if not math.isfinite(valeur_numerique):
        raise ValueError(
            f"Valeur de règle invalide pour « {cle} » : un seuil doit être "
            "un nombre fini. Une valeur infinie rendrait définitivement "
            "muets les contrôles qui s'y comparent.")
    borne = DOMAINES.get(cle)
    if borne is None:
        return                     # règle personnalisée : domaine inconnu
    mini, maxi, entier = borne
    libelle = LIBELLES.get(cle, cle)
    if entier and abs(valeur_numerique - round(valeur_numerique)) > 1e-9:
        raise ValueError(f"« {libelle} » attend un nombre entier : "
                         f"{valeur_numerique} n'en est pas un.")
    if not (mini <= valeur_numerique <= maxi):
        raise ValueError(
            f"« {libelle} » : {valeur_numerique:g} est hors du domaine admis "
            f"({mini:g} à {maxi:g}). Une valeur hors de ces bornes ne "
            "traduit aucune disposition applicable — elle ne ferait que "
            "neutraliser les calculs qui s'y réfèrent.")


def assurer(conn: sqlite3.Connection) -> None:
    """Crée la table si besoin et insère les règles par défaut manquantes."""
    conn.execute(
        "CREATE TABLE IF NOT EXISTS regle_fiscale ("
        "  id          INTEGER PRIMARY KEY,"
        "  cle         TEXT NOT NULL,"
        "  valeur      REAL NOT NULL,"
        "  date_debut  TEXT NOT NULL,"           # AAAA-MM-JJ (date d'effet)
        "  date_fin    TEXT,"                    # NULL = toujours en vigueur
        "  reference   TEXT NOT NULL DEFAULT ''," # texte légal (CGI, BOFiP, LF)
        "  commentaire TEXT NOT NULL DEFAULT '')")
    # Une table VIDE ne dit pas si c'est la première ouverture du dossier
    # ou la disparition de sa configuration : les deux se présentent
    # exactement pareil. On pose donc une marque durable au premier
    # ensemencement, et c'est son absence — et non celle des règles — qui
    # signe une première fois.
    conn.execute("CREATE TABLE IF NOT EXISTS meta ("
                 "cle TEXT PRIMARY KEY, valeur TEXT NOT NULL)")
    deja_seme = conn.execute("SELECT 1 FROM meta WHERE cle=?",
                             (MARQUE_SEMEES,)).fetchone() is not None
    premiere_fois = not deja_seme
    for cle, valeur, debut, ref, com, _lib in REGLES_DEFAUT:
        n = conn.execute("SELECT COUNT(*) FROM regle_fiscale WHERE cle=?",
                         (cle,)).fetchone()[0]
        if n == 0:
            # Le commentaire porte la TRACE de cette réinsertion. Une règle
            # recréée en silence est indiscernable d'une règle jamais
            # touchée : un seuil abaissé à 300 €, puis perdu, revenait à
            # 500 € et l'avertissement disparaissait avec lui, sans que
            # rien ne distingue cette perte d'une première initialisation.
            # `regles_retablies()` permet de la signaler.
            conn.execute(
                "INSERT INTO regle_fiscale (cle, valeur, date_debut, reference, "
                "commentaire) VALUES (?,?,?,?,?)",
                (cle, valeur, debut, ref,
                 com if premiere_fois else com + MARQUE_RETABLIE))
    conn.execute("INSERT INTO meta (cle, valeur) VALUES (?, ?) "
                 "ON CONFLICT(cle) DO NOTHING",
                 (MARQUE_SEMEES, datetime.date.today().isoformat()))
    # Même précaution que `gabarits.assurer_table` : cette fonction sème la
    # table au premier accès, donc sur un chemin de LECTURE — `valeur()`
    # l'appelle. Committer inconditionnellement terminerait la transaction
    # d'un appelant travaillant en commit=False, sans qu'il le sache
    # (constat D2-08).
    if not conn.in_transaction:
        conn.commit()


def valeur(conn: sqlite3.Connection, cle: str, annee: int,
           defaut: float | None = None) -> float:
    """
    Valeur de la règle EN VIGUEUR pour l'exercice `annee` : la version dont la
    date d'effet est la plus récente parmi celles ≤ 31/12/annee et non closes
    avant le 01/01/annee. Les exercices passés gardent ainsi leurs règles.
    """
    assurer(conn)
    row = conn.execute(
        "SELECT valeur FROM regle_fiscale WHERE cle=? AND date_debut<=? "
        "AND (date_fin IS NULL OR date_fin>=?) "
        "ORDER BY date_debut DESC LIMIT 1",
        (cle, f"{annee}-12-31", f"{annee}-01-01")).fetchone()
    if row is not None:
        return row[0]
    if defaut is not None:
        return defaut
    raise ValueError(f"Règle fiscale inconnue pour {annee} : {cle!r}")


def definir(conn: sqlite3.Connection, cle: str, nouvelle_valeur: float,
            date_debut: str, reference: str = "", commentaire: str = "") -> None:
    """
    Enregistre une NOUVELLE version d'une règle (disposition légale future) :
    clôt la version précédente à la veille de la date d'effet, puis insère la
    nouvelle. L'historique complet est conservé.
    """
    assurer(conn)
    if len(date_debut) != 10:
        raise ValueError("date_debut attendue au format AAAA-MM-JJ.")
    # Clore la version couvrant la nouvelle date d'effet.
    an, mois, jour = date_debut.split("-")
    veille = _veille(date_debut)
    # Une version portant EXACTEMENT la même date d'effet remplace la
    # précédente au lieu de coexister avec elle : deux lignes à date égale
    # rendaient le « ORDER BY date_debut DESC LIMIT 1 » arbitraire — le
    # menu affichait la nouvelle règle pendant que le moteur appliquait
    # l'ancienne.
    conn.execute("DELETE FROM regle_fiscale WHERE cle=? AND date_debut=?",
                 (cle, date_debut))
    conn.execute(
        "UPDATE regle_fiscale SET date_fin=? WHERE cle=? AND date_debut<? "
        "AND (date_fin IS NULL OR date_fin>=?)",
        (veille, cle, date_debut, date_debut))
    # …et la nouvelle version reçoit sa propre fin lorsqu'une version
    # POSTÉRIEURE existe déjà. Seule la clôture de la version précédente
    # était faite : saisir une règle rétroactive laissait donc deux
    # périodes ouvertes en même temps, et l'historique se contredisait.
    # Le tri par date décroissante sauvait le calcul, mais il ne peut pas
    # servir de justification devant un vérificateur — et il suffisait de
    # clore la version la plus récente pour voir l'ancienne ressurgir.
    suivante = conn.execute(
        "SELECT MIN(date_debut) FROM regle_fiscale WHERE cle=? AND "
        "date_debut>?", (cle, date_debut)).fetchone()[0]
    fin = _veille(suivante) if suivante else None
    # Une règle fiscale est un NOMBRE FINI. `float()` accepte « inf » et
    # « 1e309 » : enregistrer un seuil infini rendait muets, pour toujours
    # et sans un mot, les contrôles qui s'y comparent — aucune dépense ne
    # dépasse l'infini. Un garde-fou qu'on peut désactiver par une saisie
    # est pire qu'un garde-fou absent : on croit encore l'avoir.
    try:
        valeur_numerique = float(nouvelle_valeur)
    except (TypeError, ValueError):
        raise ValueError(f"Valeur de règle invalide pour « {cle} » : "
                         f"{nouvelle_valeur!r} n'est pas un nombre.") from None
    verifier_domaine(cle, valeur_numerique)
    conn.execute(
        "INSERT INTO regle_fiscale (cle, valeur, date_debut, date_fin, "
        "reference, commentaire) VALUES (?,?,?,?,?,?)",
        (cle, valeur_numerique, date_debut, fin, reference, commentaire))
    conn.commit()


def historique(conn: sqlite3.Connection) -> list[dict]:
    """Toutes les versions de toutes les règles, pour le menu Réglementation."""
    assurer(conn)
    rows = conn.execute(
        "SELECT cle, valeur, date_debut, date_fin, reference, commentaire "
        "FROM regle_fiscale ORDER BY cle, date_debut").fetchall()
    return [{"cle": c, "libelle": LIBELLES.get(c, c), "valeur": v,
             "date_debut": d, "date_fin": f, "reference": r, "commentaire": com}
            for c, v, d, f, r, com in rows]


def _veille(date_iso: str) -> str:
    from datetime import date, timedelta
    a, m, j = (int(x) for x in date_iso.split("-"))
    return (date(a, m, j) - timedelta(days=1)).isoformat()
````


## `compta_lmnp/modules/gabarits.py`

````python
# Compta LMNP — Copyright © 2026 Sylvain FAURE et les contributeurs.
# SPDX-License-Identifier: AGPL-3.0-or-later

"""
Gabarits de saisie : chaque type d'opération sait quel compte de résultat il
mouvemente, dans quel sens, et ses attributs métier (périodicité attendue,
seuil d'immobilisation, retraitement fiscal…). La contrepartie est TOUJOURS
le compte courant de l'exploitant 108000 (compta de caisse, conventions des offres payantes).

Deux sources, fusionnées par `tous(conn)` :
  1. GABARITS (code) — inventaire des articles constatés dans les exercices
     2023-2025 (FEC + liasses de référence) et des charges officiellement déductibles
     en LMNP au réel ;
  2. table `gabarit_personnalise` — extensible SANS toucher au code, pour
     accueillir une catégorie créée par une disposition future (menu
     « Réglementation »).

Attributs :
  nature       : 'produit' (108000 débité) ou 'charge' (108000 crédité)
  periodicite  : 'mensuel' | 'annuel' | 'variable' (contrôle de complétude)
  groupe       : rubrique du menu déroulant de saisie
  seuil_immo   : drapeau — le contrôle propose l’immobilisation au-delà de
                 la règle versionnée « seuil_immobilisation »
  requalifier  : le contrôle demande une requalification (fourre-tout)
  retraitement : 'reintegration' → montant réintégré fiscalement à la clôture
                 (ex. fonds travaux ALUR : provision, non déductible)
"""
from __future__ import annotations

import sqlite3

COMPTE_CONTREPARTIE = "108000"   # Exploitant

GABARITS = {
    # ── Produits ─────────────────────────────────────────────────────────────
    "loyer":                 {"compte": "708810", "nature": "produit", "periodicite": "mensuel",
                              "groupe": "Produits", "libelle": "Loyer hors charges locatives"},
    "charges_locatives":     {"compte": "708810", "nature": "produit", "periodicite": "mensuel",
                              "groupe": "Produits", "libelle": "Provision pour charges"},
    "forfait_charges":       {"compte": "708810", "nature": "produit", "periodicite": "mensuel",
                              "groupe": "Produits", "libelle": "Forfait pour charges"},
    "regularisation_charges":{"compte": "708810", "nature": "produit", "periodicite": "variable",
                              "groupe": "Produits", "libelle": "Régularisation de charges locatives"},
    # Régularisation en faveur du LOCATAIRE. Elle DÉBITE le compte de
    # produit, ce qui en diminue le solde : nature « charge » pour que
    # l'écriture parte dans le bon sens, compte inchangé pour que les
    # agrégats — qui raisonnent par CLASSE de compte — nettent d'eux-mêmes.
    # Sans cette nature, une restitution était impossible à saisir : les
    # montants sont strictement positifs partout, et c'est cette règle qui
    # protège des saisies inversées (signalé en revue du catalogue).
    "restitution_charges":   {"compte": "708810", "nature": "charge", "periodicite": "variable",
                              "groupe": "Produits", "libelle": "Restitution de charges au locataire"},
    "indemnite_assurance":   {"compte": "758000", "nature": "produit", "periodicite": "variable",
                              "groupe": "Produits", "libelle": "Indemnité d'assurance / produit divers"},
    "autres_produits":       {"compte": "708810", "nature": "produit", "periodicite": "variable",
                              "groupe": "Produits", "libelle": "Autres produits de location"},

    # ── Dépôts & emprunts (mouvements de BILAN, hors résultat) ──────────────
    #    Ces gabarits mouvementent des comptes de classe 1 : fiscal.py agrège
    #    le résultat par CLASSE (6 et 7), ils en sont donc exclus d'office.
    #    C'est tout l'objet du constat E-10 — sans ces comptes, un dépôt de
    #    garantie devenait un loyer imposable et un remboursement de capital
    #    une charge déductible.
    "depot_garantie_recu":   {"compte": "165000", "nature": "produit", "periodicite": "variable",
                              "groupe": "Dépôts & emprunts",
                              "libelle": "Dépôt de garantie reçu (dette — non imposable)"},
    "depot_garantie_restitue": {"compte": "165000", "nature": "charge", "periodicite": "variable",
                              "groupe": "Dépôts & emprunts",
                              "libelle": "Dépôt de garantie restitué (extinction de dette)"},
    "emprunt_recu":          {"compte": "164000", "nature": "produit", "periodicite": "variable",
                              "groupe": "Dépôts & emprunts",
                              "libelle": "Déblocage d'emprunt reçu (dette — non imposable)"},
    "emprunt_capital_rembourse": {"compte": "164000", "nature": "charge", "periodicite": "variable",
                              "groupe": "Dépôts & emprunts",
                              "libelle": "Remboursement d'emprunt — CAPITAL (non déductible)"},

    # ── Copropriété ─────────────────────────────────────────────────────────
    "charge_copro":          {"compte": "614100", "nature": "charge", "periodicite": "variable",
                              "groupe": "Copropriété", "libelle": "Charges locatives et de copropriété"},
    "fonds_travaux_alur":    {"compte": "614100", "nature": "charge", "periodicite": "variable",
                              "groupe": "Copropriété", "libelle": "Fonds travaux ALUR",
                              "retraitement": "reintegration"},

    # ── Abonnements & énergie ───────────────────────────────────────────────
    "telecom":               {"compte": "626210", "nature": "charge", "periodicite": "variable",
                              "groupe": "Abonnements & énergie", "libelle": "Internet / Télécoms"},
    "energie":               {"compte": "606100", "nature": "charge", "periodicite": "variable",
                              "groupe": "Abonnements & énergie", "libelle": "Énergie (électricité, gaz)"},

    # ── Assurances ──────────────────────────────────────────────────────────
    "assurance":             {"compte": "616110", "nature": "charge", "periodicite": "variable",
                              "groupe": "Assurances", "libelle": "Assurance habitation PNO"},
    "assurance_emprunteur":  {"compte": "616110", "nature": "charge", "periodicite": "variable",
                              "groupe": "Assurances", "libelle": "Assurance emprunteur"},
    "assurance_gli":         {"compte": "616110", "nature": "charge", "periodicite": "variable",
                              "groupe": "Assurances", "libelle": "Garantie loyers impayés (GLI)"},

    # ── Entretien & équipement ──────────────────────────────────────────────
    "maintenance":           {"compte": "615200", "nature": "charge", "periodicite": "variable",
                              "groupe": "Entretien & équipement", "libelle": "Entretien et réparations"},
    "petit_equipement":      {"compte": "606320", "nature": "charge", "periodicite": "variable",
                              "groupe": "Entretien & équipement", "libelle": "Petit équipement",
                              "seuil_immo": True},  # → règle versionnée
    "electromenager":        {"compte": "606320", "nature": "charge", "periodicite": "variable",
                              "groupe": "Entretien & équipement", "libelle": "Électroménager",
                              "seuil_immo": True},  # → règle versionnée
    "autres_equipements":    {"compte": "606320", "nature": "charge", "periodicite": "variable",
                              "groupe": "Entretien & équipement", "libelle": "Autres équipements",
                              "seuil_immo": True},  # → règle versionnée
    "fournitures":           {"compte": "606400", "nature": "charge", "periodicite": "variable",
                              "groupe": "Entretien & équipement", "libelle": "Fournitures administratives"},

    # ── Emprunt & banque ────────────────────────────────────────────────────
    "interets_emprunt":      {"compte": "661100", "nature": "charge", "periodicite": "annuel",
                              "groupe": "Emprunt & banque", "libelle": "Intérêts d'emprunt"},
    "frais_dossier_emprunt": {"compte": "627810", "nature": "charge", "periodicite": "variable",
                              "groupe": "Emprunt & banque", "libelle": "Frais de dossier / garantie emprunt"},
    "frais_bancaires":       {"compte": "627810", "nature": "charge", "periodicite": "variable",
                              "groupe": "Emprunt & banque", "libelle": "Frais de tenue de compte"},

    # ── Honoraires & gestion ────────────────────────────────────────────────
    "honoraires":            {"compte": "622610", "nature": "charge", "periodicite": "variable",
                              "groupe": "Honoraires & gestion", "libelle": "Frais de comptabilité"},
    "gestion_locative":      {"compte": "622800", "nature": "charge", "periodicite": "variable",
                              "groupe": "Honoraires & gestion", "libelle": "Frais de gestion locative / agence"},
    "honoraires_juridiques": {"compte": "622700", "nature": "charge", "periodicite": "variable",
                              "groupe": "Honoraires & gestion", "libelle": "Honoraires juridiques / actes / contentieux"},
    "frais_acquisition":     {"compte": "622700", "nature": "charge", "periodicite": "variable",
                              "groupe": "Honoraires & gestion",
                              "libelle": "Frais d'acquisition (option charges : notaire, mutation)"},
    "publicite_annonces":    {"compte": "623100", "nature": "charge", "periodicite": "variable",
                              "groupe": "Honoraires & gestion", "libelle": "Annonces et publicité de location"},
    "cotisations_pro":       {"compte": "628100", "nature": "charge", "periodicite": "annuel",
                              "groupe": "Honoraires & gestion", "libelle": "Cotisations professionnelles"},
    "frais_postaux":         {"compte": "626100", "nature": "charge", "periodicite": "variable",
                              "groupe": "Honoraires & gestion", "libelle": "Frais postaux"},

    # ── Déplacements ────────────────────────────────────────────────────────
    "carburant":             {"compte": "606200", "nature": "charge", "periodicite": "variable",
                              "groupe": "Déplacements", "libelle": "Carburant (barème / réel)"},
    "peage_parking":         {"compte": "625100", "nature": "charge", "periodicite": "variable",
                              "groupe": "Déplacements", "libelle": "Péage / parking"},
    "deplacements":          {"compte": "625100", "nature": "charge", "periodicite": "variable",
                              "groupe": "Déplacements", "libelle": "Voyages et déplacements"},

    # ── Impôts & taxes ──────────────────────────────────────────────────────
    "cfe":                   {"compte": "635110", "nature": "charge", "periodicite": "annuel",
                              "groupe": "Impôts & taxes", "libelle": "Cotisation Foncière des Entreprises (CFE)"},
    "taxe_fonciere":         {"compte": "635130", "nature": "charge", "periodicite": "annuel",
                              "groupe": "Impôts & taxes", "libelle": "Taxe foncière (hors TEOM récupérable)"},
    "teom":                  {"compte": "635130", "nature": "charge", "periodicite": "annuel",
                              "groupe": "Impôts & taxes", "libelle": "Taxe d'enlèvement des ordures ménagères (TEOM)"},
    "impot_local":           {"compte": "635130", "nature": "charge", "periodicite": "annuel",
                              "groupe": "Impôts & taxes", "libelle": "Autres impôts locaux"},

    # ── Divers ──────────────────────────────────────────────────────────────
    "autres_charges":        {"compte": "628800", "nature": "charge", "periodicite": "variable",
                              "groupe": "Divers", "libelle": "Autres charges (à requalifier)",
                              "requalifier": True},

    # ── Attente ─────────────────────────────────────────────────────────────
    #    628800 est une charge IMMÉDIATEMENT DÉDUCTIBLE : y ranger une ligne
    #    non reconnue « signale » le doute sans rien empêcher. 472000 est un
    #    compte d'attente, et controles.py refuse BLOQUANTE une liasse dont
    #    le solde n'est pas apuré : le doute empêche alors de déclarer faux.
    "attente_encaissement":  {"compte": "472000", "nature": "produit", "periodicite": "variable",
                              "groupe": "Attente",
                              "libelle": "Encaissement à identifier (bloque la liasse)",
                              "requalifier": True},
    "attente_decaissement":  {"compte": "472000", "nature": "charge", "periodicite": "variable",
                              "groupe": "Attente",
                              "libelle": "Décaissement à identifier (bloque la liasse)",
                              "requalifier": True},
}

ORDRE_GROUPES = ["Produits", "Dépôts & emprunts", "Copropriété",
                 "Abonnements & énergie", "Assurances",
                 "Entretien & équipement", "Emprunt & banque", "Honoraires & gestion",
                 "Déplacements", "Impôts & taxes", "Divers", "Attente", "Personnalisé"]


# ── Gabarits personnalisés (table) ───────────────────────────────────────────

def assurer_table(conn: sqlite3.Connection) -> None:
    """Crée la table des gabarits personnalisés si elle manque.

    NE COMMITTE PAS quand une transaction est déjà ouverte. Elle committait
    inconditionnellement, et comme `gabarit()` — appelée à CHAQUE saisie —
    passe par `_personnalises()`, qui passe par ici, tout appelant travaillant
    en `commit=False` voyait sa transaction terminée en douce sous ses pieds.
    Observé sur la validation d'un import : la deuxième saisie committait la
    première, si bien qu'un `rollback` n'annulait plus que la dernière ligne
    — exactement l'inverse du tout-ou-rien recherché (constat D2-08).

    Le `CREATE TABLE IF NOT EXISTS` est transactionnel en SQLite : il peut
    voyager dans la transaction de l'appelant sans dommage.
    """
    conn.execute(
        "CREATE TABLE IF NOT EXISTS gabarit_personnalise ("
        "  cle          TEXT PRIMARY KEY,"
        "  libelle      TEXT NOT NULL,"
        "  compte_num   TEXT NOT NULL REFERENCES compte(numero),"
        "  nature       TEXT NOT NULL CHECK (nature IN ('produit','charge')),"
        "  periodicite  TEXT NOT NULL DEFAULT 'variable'"
        "               CHECK (periodicite IN ('mensuel','annuel','variable')),"
        "  retraitement TEXT,"
        "  actif        INTEGER NOT NULL DEFAULT 1)")
    if not conn.in_transaction:
        conn.commit()


def ajouter_personnalise(conn: sqlite3.Connection, *, cle: str, libelle: str,
                         compte_num: str, nature: str,
                         periodicite: str = "variable",
                         retraitement: str | None = None) -> None:
    """Nouvelle catégorie d'opération (disposition future) — sans toucher au code."""
    deja_en_transaction = conn.in_transaction
    assurer_table(conn)
    cle = cle.strip().lower().replace(" ", "_")
    if not cle:
        raise ValueError("Clé de gabarit vide.")
    if cle in GABARITS:
        raise ValueError(f"La clé {cle!r} existe déjà dans les gabarits standard.")
    ok = conn.execute("SELECT COUNT(*) FROM compte WHERE numero=?",
                      (compte_num,)).fetchone()[0]
    if not ok:
        raise ValueError(f"Compte {compte_num} absent du plan de comptes — "
                         "créez-le d'abord (menu Réglementation).")
    conn.execute(
        "INSERT INTO gabarit_personnalise (cle, libelle, compte_num, nature, "
        "periodicite, retraitement) VALUES (?,?,?,?,?,?)",
        (cle, libelle, compte_num, nature, periodicite, retraitement))
    # Ne committer QUE si l'appelant n'avait pas sa propre transaction —
    # même précaution que `assurer_table` et que les lecteurs de règles
    # (constat D2-08). Un `commit()` inconditionnel validait au passage tout
    # ce que l'appelant avait écrit sans le vouloir : un loyer de 800 €
    # saisi en `commit=False` survivait au rollback qui suivait, parce
    # qu'un gabarit avait été créé entre-temps sur la même connexion.
    if not deja_en_transaction:
        conn.commit()


def _personnalises(conn: sqlite3.Connection) -> dict:
    assurer_table(conn)
    rows = conn.execute(
        "SELECT cle, libelle, compte_num, nature, periodicite, retraitement "
        "FROM gabarit_personnalise WHERE actif=1").fetchall()
    out = {}
    for cle, lib, compte, nature, per, retr in rows:
        g = {"compte": compte, "nature": nature, "periodicite": per,
             "groupe": "Personnalisé", "libelle": lib}
        if retr:
            g["retraitement"] = retr
        out[cle] = g
    return out


# ── API ──────────────────────────────────────────────────────────────────────

def tous(conn: sqlite3.Connection | None = None) -> dict:
    """Gabarits standard + personnalisés actifs (si une connexion est fournie)."""
    fusion = dict(GABARITS)
    if conn is not None:
        fusion.update(_personnalises(conn))
    return fusion


def gabarit(type_op: str, conn: sqlite3.Connection | None = None) -> dict:
    g = tous(conn)
    if type_op not in g:
        raise ValueError(f"Type d'opération inconnu : {type_op!r}. "
                         f"Connus : {', '.join(sorted(g))}")
    return g[type_op]


def grouper(g: dict) -> list[tuple[str, list]]:
    """Regroupe un catalogue DÉJÀ CHARGÉ. Fonction pure, sans connexion.

    `par_groupe(conn)` relisait le catalogue pour son propre compte, alors
    que son appelant venait de le charger : une page de saisie lisait ainsi
    trois fois la même table (constat T-09). La lecture et le regroupement
    sont désormais deux gestes distincts, et l'appelant choisit.
    """
    groupes: dict[str, list] = {}
    for cle, gab in g.items():
        groupes.setdefault(gab.get("groupe", "Divers"), []).append((cle, gab))
    ordre = ORDRE_GROUPES + [x for x in groupes if x not in ORDRE_GROUPES]
    return [(grp, sorted(groupes[grp], key=lambda kv: kv[1]["libelle"]))
            for grp in ordre if grp in groupes]


def par_groupe(conn: sqlite3.Connection | None = None) -> list[tuple[str, list]]:
    """[(groupe, [(cle, gabarit), …]), …] dans l'ordre d'affichage."""
    return grouper(tous(conn))
````


## `compta_lmnp/modules/liasse_pdf.py`

````python
# Compta LMNP — Copyright © 2026 Sylvain FAURE et les contributeurs.
# SPDX-License-Identifier: AGPL-3.0-or-later

"""
Export PDF de la liasse fiscale — J7.

Prend le dictionnaire produit par `liasse.generer()` et le met en page dans
un PDF A4 : page de garde, 2031/2031 bis, 2033-A, 2033-B, 2033-C, suivi des
reports (39 C + déficits LMNP), aide 2042C-PRO et contrôles de cohérence.

Ce document est un ÉTAT DE TRAVAIL fidèle aux montants calculés — pas un
fac-similé des formulaires CERFA : les numéros de cases officiels y figurent
pour permettre le report champ à champ dans la télédéclaration (ou par
l'expert-comptable). Filigrane « PROVISOIRE » si l'exercice n'est pas clos.

Dépendance : reportlab (installée par les lanceurs au premier démarrage).
"""
from __future__ import annotations

import os
from datetime import datetime
from xml.sax.saxutils import escape as _xml

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle)

BLEU = colors.HexColor("#1e3a5f")
GRIS = colors.HexColor("#8a93a3")
FOND = colors.HexColor("#f7f8fa")
VERT = colors.HexColor("#1a7f37")
ROUGE = colors.HexColor("#b42318")


def _eur(x) -> str:
    """1234.5 → '1 234,50 €' (insécable fine espace non requise en PDF).

    Un résidu d'arrondi négatif — -0,004 — s'affichait « -0,00 € » : un
    montant nul affecté d'un signe moins, dans un document où le signe
    porte le sens. Le zéro est ramené au zéro positif AVANT formatage
    (constat E-18).
    """
    if x is None:
        return "—"
    if abs(x) < 0.005:                 # sous le demi-centime : zéro tout court
        x = 0.0
    s = f"{x:,.2f}".replace(",", " ").replace(".", ",")
    return f"{s} €"


def _styles():
    base = getSampleStyleSheet()
    return {
        "titre": ParagraphStyle("titre", parent=base["Title"],
                                textColor=BLEU, fontSize=20, spaceAfter=4),
        "sous": ParagraphStyle("sous", parent=base["Normal"],
                               textColor=GRIS, fontSize=10, spaceAfter=12),
        "h2": ParagraphStyle("h2", parent=base["Heading2"], textColor=BLEU,
                             fontSize=13, spaceBefore=14, spaceAfter=6),
        "normal": ParagraphStyle("normal", parent=base["Normal"], fontSize=9,
                                 leading=12),
        "note": ParagraphStyle("note", parent=base["Normal"], fontSize=8,
                               textColor=GRIS, leading=10, spaceBefore=4),
    }


def _table(lignes, largeurs=None, aligne_droite=(1,)):
    """Table 2 colonnes+ : entête grisée, montants alignés à droite."""
    t = Table(lignes, colWidths=largeurs, hAlign="LEFT")
    style = [
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("BACKGROUND", (0, 0), (-1, 0), FOND),
        ("TEXTCOLOR", (0, 0), (-1, 0), BLEU),
        ("LINEBELOW", (0, 0), (-1, 0), 0.75, BLEU),
        ("LINEBELOW", (0, 1), (-1, -2), 0.25, colors.HexColor("#e4e7ec")),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]
    for col in aligne_droite:
        style.append(("ALIGN", (col, 0), (col, -1), "RIGHT"))
    t.setStyle(TableStyle(style))
    return t


def _ligne_tot(t: Table, index: int) -> None:
    t.setStyle(TableStyle([
        ("FONTNAME", (0, index), (-1, index), "Helvetica-Bold"),
        ("LINEABOVE", (0, index), (-1, index), 1, BLEU),
    ]))


def _version() -> str:
    """Version du logiciel, lue dans le fichier VERSION livré à côté."""
    try:
        # VERSION vit à la RACINE du paquet, ce module dans modules/ :
        # deux dirname, pas un.
        racine = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(racine, "VERSION"), encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return "?"


def _pied_de_page(provisoire: bool):
    """Pied de page : avertissement, horodatage d'édition, version, page.

    Le document ne portait ni date, ni heure, ni version. Deux tirages d'un
    même exercice, entre lesquels une écriture a été corrigée, étaient
    visuellement indiscernables — sur une pièce destinée à un
    expert-comptable ou à un dossier de contrôle, c'est la première chose
    qui manque (constat E-15).
    """
    edite_le = datetime.now().strftime("%d/%m/%Y à %H:%M")
    signature = f"Compta LMNP v{_version()} — édité le {edite_le}"

    def dessiner(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(GRIS)
        canvas.drawString(15 * mm, 10 * mm,
                          "Compta LMNP — état de travail à faire valider par "
                          "un expert-comptable avant tout dépôt.")
        canvas.drawRightString(A4[0] - 15 * mm, 10 * mm,
                               f"Page {doc.page}")
        canvas.setFont("Helvetica", 6.5)
        canvas.drawString(15 * mm, 6.5 * mm, signature)
        if provisoire:
            canvas.setFont("Helvetica-Bold", 60)
            canvas.setFillColor(colors.Color(0.71, 0.13, 0.09, alpha=0.08))
            canvas.saveState()
            canvas.translate(A4[0] / 2, A4[1] / 2)
            canvas.rotate(45)
            canvas.drawCentredString(0, 0, "PROVISOIRE")
            canvas.restoreState()
        canvas.restoreState()
    return dessiner


def generer_pdf(L: dict, chemin_ou_buffer) -> None:
    """Écrit le PDF de la liasse `L` (= liasse.generer()) dans un chemin ou un buffer."""
    st = _styles()
    doc = SimpleDocTemplate(
        chemin_ou_buffer, pagesize=A4,
        leftMargin=15 * mm, rightMargin=15 * mm,
        topMargin=15 * mm, bottomMargin=18 * mm,
        title=f"Liasse fiscale LMNP {L['annee']}",
        author="Compta LMNP")
    E = []  # flowables

    # ── Page de garde ────────────────────────────────────────────────────
    exp = L.get("exploitant") or {}
    statut = ("exercice clos" if not L["provisoire"]
              else "exercice NON clôturé — chiffres provisoires")
    E.append(Paragraph(f"Liasse fiscale LMNP — exercice {L['annee']}",
                       st["titre"]))
    # _xml() : les textes des Paragraph sont interprétés comme du balisage
    # par ReportLab — toute donnée UTILISATEUR doit être échappée, sinon un
    # nom contenant « < » fait planter la génération (même famille de défaut
    # que la XSS corrigée en v7, appliquée à la frontière PDF).
    ident = " · ".join(x for x in (
        exp.get("nom"), exp.get("siret") and f"SIRET {exp['siret']}",
        exp.get("adresse")) if x)
    E.append(Paragraph(f"{_xml(ident) or 'Exploitant non renseigné'}"
                       f" &nbsp;—&nbsp; {statut}", st["sous"]))
    # L'avertissement vivait dans la docstring du module, donc nulle part
    # pour le lecteur — alors que la page de garde s'intitule « Liasse
    # fiscale LMNP », ce qu'on peut prendre pour un formulaire officiel.
    E.append(Paragraph(
        "Ce document est un <b>état de travail</b> fidèle aux montants "
        "calculés — <b>pas un fac-similé des formulaires CERFA</b>. Les "
        "numéros de cases officiels y figurent pour permettre le report "
        "champ à champ dans la télédéclaration, ou par l'expert-comptable.",
        st["note"]))
    # Un exercice de cession se lit tout entier de travers si l'on croit
    # que la neutralisation du BIC calcule la plus-value. Le pense-bête le
    # dit bien, mais le PDF est ce qui part chez le comptable ou reste au
    # dossier : il doit le dire aussi, et le dire LÀ, sur la page de garde.
    if L.get("cession_de_l_exercice"):
        E.append(Spacer(1, 4))
        E.append(Paragraph(
            "<b>Une cession a eu lieu sur cet exercice.</b> Le prix de vente "
            "et la valeur comptable du bien sont NEUTRALISÉS dans le "
            "résultat BIC ci-après : en location meublée non "
            "professionnelle, la plus-value relève du régime des "
            "PARTICULIERS (article 150 U du CGI). Ce document ne la calcule "
            "donc pas, et l'absence de plus-value dans le résultat LMNP ne "
            "signifie pas qu'il n'y a rien à déclarer : la plus-value "
            "immobilière est établie et déclarée séparément par le notaire "
            "(formulaire 2048-IMM), au moment de la vente. Vérifiez auprès "
            "de lui que cette formalité a bien été accomplie.",
            st["note"]))
    E.append(Spacer(1, 6))

    g = L["page_garde"]
    E.append(_table([
        ["Chiffres clés", "Montant"],
        ["Recettes de l'exercice (CA HT)", _eur(g["ca_ht"])],
        ["Résultat fiscal LMNP", _eur(g["resultat_fiscal"])],
        ["Déficit LMNP généré", _eur(g["deficit_lmnp"])],
        ["Revenu imposable (2042C-PRO)", _eur(g["revenu_imposable"])],
        ["Amortissements en report (art. 39 C)", _eur(g["restant_39c"])],
        ["Déficits LMNP en stock", _eur(g["restant_deficits"])],
        ["Total des reports disponibles", _eur(g["restant_total"])],
    ], largeurs=[110 * mm, 60 * mm]))

    # ── Projection de clôture (exercice ouvert uniquement) ───────────────
    # Les tableaux ci-dessous reflètent les ÉCRITURES. Or la dotation aux
    # amortissements n'est comptabilisée qu'à la clôture : sans ce bloc, le
    # déclarant lisait toute l'année un résultat fiscal qui l'ignorait.
    proj = L.get("projection_cloture")
    if proj and proj["dotation_previsionnelle"]:
        E.append(Paragraph("Projection — si l'exercice était clôturé "
                           "aujourd'hui", st["h2"]))
        E.append(Paragraph(
            "Les tableaux qui suivent ne portent que les écritures "
            "enregistrées. La dotation aux amortissements de l'exercice "
            "n'est comptabilisée qu'à la clôture : ces chiffres-là "
            "l'anticipent, d'après le plan d'amortissement.", st["sous"]))
        E.append(_table([
            ["Projection de clôture", "Montant"],
            ["Dotation aux amortissements de l'exercice",
             _eur(proj["dotation_previsionnelle"])],
            ["Résultat comptable projeté",
             _eur(proj["resultat_comptable_projete"])],
            ["Amortissements reportés (art. 39 C) projetés",
             _eur(proj["report_39c_projete"])],
            ["Résultat fiscal projeté",
             _eur(proj["resultat_fiscal_projete"])],
        ], largeurs=[110 * mm, 60 * mm]))

    # ── 2031 / 2031 bis ──────────────────────────────────────────────────
    r = L["f2031"]
    E.append(Paragraph("2031-SD — Récapitulation", st["h2"]))
    lignes = [["Rubrique", "Montant"],
              ["Résultat fiscal (ligne 1 — activité exclue, cf. 2031 bis)",
               _eur(r["resultat_fiscal_1"])]]
    if r["bic_non_pro_7a_benefice"] is not None:
        lignes.append(["BIC non professionnel — bénéfice (cadre 7a)",
                       _eur(r["bic_non_pro_7a_benefice"])])
    if r["bic_non_pro_7b_deficit"] is not None:
        lignes.append(["BIC non professionnel — déficit (cadre 7b)",
                       _eur(r["bic_non_pro_7b_deficit"])])
    E.append(_table(lignes, largeurs=[110 * mm, 60 * mm]))

    # ── 2033-A ───────────────────────────────────────────────────────────
    a = L["f2033a"]
    E.append(Paragraph("2033-A — Bilan simplifié", st["h2"]))
    ta = _table([
        ["Actif", "Montant"],
        ["Immobilisations corporelles — brut (case 028)",
         _eur(a["immo_corporelles_brut_028"])],
        ["Amortissements (case 030)", _eur(a["amortissements_030"])],
        ["Immobilisations corporelles — net", _eur(a["immo_corporelles_net"])],
        ["Total actif net (case 112)", _eur(a["total_actif_net_112"])],
    ], largeurs=[110 * mm, 60 * mm])
    _ligne_tot(ta, 4)
    E.append(ta)
    E.append(Spacer(1, 4))
    tp = _table([
        ["Passif", "Montant"],
        ["Capital individuel (case 120)", _eur(a["capital_individuel_120"])],
        ["Résultat de l'exercice (case 136)", _eur(a["resultat_exercice_136"])],
        ["Total capitaux propres (case 142)", _eur(a["total_capitaux_142"])],
        ["Total passif (case 180)", _eur(a["total_passif_180"])],
    ], largeurs=[110 * mm, 60 * mm])
    _ligne_tot(tp, 4)
    E.append(tp)

    # ── 2033-B ───────────────────────────────────────────────────────────
    b = L["f2033b"]
    E.append(Paragraph("2033-B — Compte de résultat simplifié", st["h2"]))
    tb = _table([
        ["Rubrique", "Montant"],
        ["Production vendue — services, loyers (case 218)",
         _eur(b["produits_218"])],
        ["Autres produits (case 230)", _eur(b["autres_produits_230"])],
        ["Total des produits d'exploitation (case 232)",
         _eur(b["total_produits_232"])],
        ["Autres charges externes (case 242)", _eur(b["charges_externes_242"])],
        ["Impôts et taxes (case 244) — dont CFE et CVAE "
         + _eur(b["dont_cfe_243"]), _eur(b["impots_244"])],
        # 250 et 262 : sans elles, un compte de charge hors des préfixes
        # nommés n'apparaissait dans AUCUNE case, tout en pesant sur le
        # résultat. 262 est le reste rendu visible.
        ["Rémunérations du personnel (case 250)", _eur(b["personnel_250"])],
        ["Autres charges (case 262)", _eur(b["autres_charges_262"])],
        ["Dotations aux amortissements (case 254)", _eur(b["dotations_254"])],
        ["Total des charges d'exploitation (case 264)",
         _eur(b["total_charges_264"])],
        ["Résultat d'exploitation (case 270)",
         _eur(b["resultat_exploitation_270"])],
        # Ordre et numéros repris du CERFA 2033-B-SD 2026 (n° 15948*08) :
        # 280 puis 294, puis 290 puis 300, avant la case 310. Le document
        # sert au report champ à champ — suivre l'ordre du formulaire est
        # sa raison d'être. La ligne des charges exceptionnelles était
        # CALCULÉE mais jamais rendue, le prix de cession apparaissant sans
        # sa contrepartie (constat E-20).
        ["Produits financiers (case 280)", _eur(b["produits_financiers_280"])],
        ["Charges financières — intérêts d'emprunt (case 294)",
         _eur(b["charges_financieres_294"])],
        ["Produits exceptionnels — dont cessions (case 290)",
         _eur(b["produits_exceptionnels_290"])],
        ["Charges exceptionnelles (case 300) — dont valeur comptable des "
         "éléments cédés", _eur(b["charges_exceptionnelles_300"])],
        ["Bénéfice ou perte (case 310)", _eur(b["benefice_ou_perte_310"])],
    ], largeurs=[110 * mm, 60 * mm])
    _ligne_tot(tb, 15)     # la ligne 310, décalée par les ajouts 230/232/250/262
    E.append(tb)

    lignes = [["Réintégrations / déductions", "Montant"],
              ["Réintégration — amortissements excédentaires art. 39 C (case 318)",
               _eur(b["reintegration_amort_318"])]]
    for lib, m in b["reintegrations_detail"]:
        lignes.append([f"Réintégration — {lib} (case 330)", _eur(m)])
    for lib, m in b["deductions_detail"]:
        lignes.append([f"Déduction — {lib} (case 350)", _eur(m)])
    lignes.append(["Résultat fiscal ligne 352 (doit valoir 0 — activité "
                   "déclarée en 2031 bis)", _eur(b["resultat_fiscal_352"])])
    tr = _table(lignes, largeurs=[110 * mm, 60 * mm])
    _ligne_tot(tr, len(lignes) - 1)
    E.append(Spacer(1, 4))
    E.append(tr)

    # ── 2033-C ───────────────────────────────────────────────────────────
    c = L["f2033c"]
    E.append(Paragraph("2033-C — Immobilisations et amortissements", st["h2"]))
    # Les numéros de case étaient CALCULÉS par liasse.py (case_immo,
    # case_amort) et jamais rendus : le 2033-C était le seul tableau du
    # document à ne pas porter les siens, alors que le report champ à champ
    # est la raison d'être de ce PDF. Cases relevées sur le CERFA
    # 2033-C-SD 2026 : 420/430/450/470 (brut), 510/520/540/560 (amort.).
    lignes = [["Rubrique", "Brut début", "Augment.", "Brut fin",
               "Diminutions", "Amort. début", "Dotation",
               "Amort. dimin.", "Amort. fin"]]
    for rub in c["rubriques"]:
        # Enveloppé comme partout ailleurs : une chaîne brute ne se coupe pas
        # dans une table reportlab, elle déborde sur les colonnes voisines.
        # Mesuré : « Installations generales, agencements et amenagements des
        # constructions » fait 279,2 pt dans une colonne qui en offre 118,4
        # — trois colonnes de montants recouvertes (constat E-16).
        lignes.append([Paragraph(
            _xml(f"{rub['libelle']} (cases {rub['case_immo']} / "
                 f"{rub['case_amort']})"), st["normal"]),
                       _eur(rub["brut_debut"]), _eur(rub["augmentations"]),
                       _eur(rub["diminutions"]), _eur(rub["brut_fin"]),
                       _eur(rub["amort_debut"]), _eur(rub["dotation"]),
                       _eur(rub["amort_diminutions"]), _eur(rub["amort_fin"])])
    tt = c["totaux"]
    lignes.append(["Totaux", _eur(tt["brut_debut"]), _eur(tt["augmentations"]),
                   _eur(tt["diminutions"]), _eur(tt["brut_fin"]),
                   _eur(tt["amort_debut"]), _eur(tt["dotation"]),
                   _eur(tt["amort_diminutions"]), _eur(tt["amort_fin"])])
    t = _table(lignes, largeurs=[38 * mm] + [16.5 * mm] * 8,
               aligne_droite=range(1, 9))
    _ligne_tot(t, len(lignes) - 1)
    E.append(t)

    E.append(Paragraph("Détail par composant", st["h2"]))
    lignes = [["Composant", "Valeur brute", "Durée", "Dotation",
               "Cumul fin", "VNC fin"]]
    for d in c["detail_composants"]:
        lignes.append([Paragraph(_xml(d["libelle"]), st["normal"]),
                       _eur(d["valeur_brute"]),
                       f"{d['duree']} ans" if d["duree"] else "—",
                       _eur(d["dotation"]), _eur(d["cumul_fin"]),
                       _eur(d["vnc_fin"])])
    E.append(_table(lignes, largeurs=[58 * mm, 24 * mm, 16 * mm,
                                      24 * mm, 24 * mm, 24 * mm],
                    aligne_droite=range(1, 6)))

    # ── Suivi des reports ────────────────────────────────────────────────
    rep = L["reports"]
    s39 = rep["suivi_39c"]
    E.append(Paragraph("Suivi des reports — article 39 C", st["h2"]))
    # La SORTIE de stock d'un bien cédé manquait à ce tableau : seul le
    # détail par bien la portait, et il n'est imprimé qu'à partir de deux
    # biens. Sur un dossier mono-bien, l'état archivable affichait donc
    # « ouverture 5 000 + reporté 1 200 − repris 0 = clôture 0 » — un
    # tableau qui ne se réconcilie pas, et 6 200 € de mouvement sans
    # explication. La ligne n'apparaît que lorsqu'il y a une sortie, pour
    # ne pas encombrer le cas ordinaire.
    sortie_39c = round(rep.get("sortie_39c") or 0.0, 2)
    lignes_39c = [
        ["Rubrique", "Montant"],
        ["Stock d'ouverture", _eur(s39.get("stock_ouverture"))],
        ["Amortissements reportés cette année", _eur(s39.get("report_annee"))],
        ["Amortissements repris cette année", _eur(s39.get("utilisation_annee"))],
    ]
    if sortie_39c:
        lignes_39c.append(
            ["Stock sorti avec un bien cédé (ligne G')", _eur(sortie_39c)])
    lignes_39c.append(["Stock à la clôture", _eur(s39.get("stock_cloture"))])
    E.append(_table(lignes_39c, largeurs=[110 * mm, 60 * mm]))

    # Ventilation logement par logement — affichée dès que la comptabilité
    # compte plusieurs biens, ou qu'une sortie doit être expliquée même sur
    # un bien unique.
    par_bien = rep.get("suivi_39c_par_bien") or []
    if len(par_bien) > 1 or (par_bien and sortie_39c):
        E.append(Paragraph("Suivi du stock 39 C, logement par logement",
                           st["h2"]))
        avec_sorties = any(v.get("sortie_bien") for v in par_bien)
        entetes = ["Bien", "Ouverture", "Reporté", "Repris"]
        if avec_sorties:
            entetes.append("Sorti (G')")
        entetes.append("Stock fin")
        lignes_b = [entetes]
        for v in par_bien:
            ligne = [Paragraph(_xml(v["libelle"]), st["normal"]),
                     _eur(v["stock_ouverture"]), _eur(v["report_bien"]),
                     _eur(v["utilisation_bien"])]
            if avec_sorties:
                ligne.append(_eur(v.get("sortie_bien", 0)))
            ligne.append(_eur(v["stock_cloture"]))
            lignes_b.append(ligne)
        larg = [60 * mm] + [22 * mm] * (len(entetes) - 1)
        # `aligne_droite` n'était pas passé : le défaut (1,) n'alignait que
        # « Ouverture », laissant « Reporté », « Repris », « Sorti » et
        # « Stock fin » à gauche — dans le seul tableau où l'on compare des
        # colonnes entre elles (constat E-17).
        E.append(_table(lignes_b, largeurs=larg,
                        aligne_droite=range(1, len(entetes))))

    E.append(Paragraph("Déficits LMNP par millésime", st["h2"]))
    if rep["deficits"]:
        lignes = [["Origine", "Montant initial", "Solde", "Expire fin"]]
        for d in rep["deficits"]:
            lignes.append([str(d["annee_origine"]), _eur(d["montant_initial"]),
                           _eur(d["solde"]), (str(d["annee_expiration"]) + (" — périmé" if d.get("perime") else ""))])
        lignes.append(["Total", "", _eur(rep["total_deficits"]), ""])
        t = _table(lignes, largeurs=[30 * mm, 45 * mm, 45 * mm, 30 * mm],
                   aligne_droite=(1, 2))
        _ligne_tot(t, len(lignes) - 1)
        E.append(t)
    else:
        E.append(Paragraph("Aucun déficit LMNP en stock.", st["normal"]))

    if rep.get("total_deficits_perimes", 0):
        E.append(Paragraph(
            "Déficits perdus par péremption : "
            + _eur(rep["total_deficits_perimes"]), st["normal"]))
        for d in rep["deficits"]:
            if d.get("perime") and (d.get("perte_peremption") or d["solde"]):
                E.append(Paragraph(
                    f"Millésime {d['annee_origine']} : "
                    + _eur(d.get("perte_peremption") or d["solde"])
                    + " perdus, exclus du stock disponible.", st["normal"]))

    # ── Aide 2042C-PRO ───────────────────────────────────────────────────
    aide = L["aide_2042c"]
    E.append(Paragraph("Aide au report — 2042C-PRO", st["h2"]))
    lignes = [["Case", "Montant"]]
    if aide["case_5NA"] is not None:
        lignes.append(["5NA — bénéfice location meublée non professionnelle",
                       _eur(aide["case_5NA"])])
    if aide["case_5NY"] is not None:
        lignes.append(["5NY — déficit location meublée non professionnelle",
                       _eur(aide["case_5NY"])])
    for cd in aide["cases_deficits_anterieurs"]:
        lignes.append([f"{cd['case']} — déficit {cd['annee_origine']} "
                       "non encore déduit", _eur(cd["montant"])])
    if len(lignes) == 1:
        lignes.append(["Aucune case à servir", "—"])
    E.append(_table(lignes, largeurs=[110 * mm, 60 * mm]))
    # Seule chaîne de données à échapper au traitement : l'exception n'était
    # pas motivée, et un « & » dans la note ferait échouer la génération.
    E.append(Paragraph(_xml(aide["note"]), st["note"]))

    # ── Contrôles de cohérence ───────────────────────────────────────────
    E.append(Paragraph("Contrôles de cohérence internes", st["h2"]))
    lignes = [["Contrôle", "Résultat", "Détail"]]
    for ctl in L["controles"]:
        lignes.append([Paragraph(_xml(ctl["nom"]), st["normal"]),
                       "conforme" if ctl["ok"] else "ANOMALIE",
                       Paragraph(_xml(ctl["detail"]), st["normal"])])
    t = _table(lignes, largeurs=[80 * mm, 22 * mm, 68 * mm],
               aligne_droite=())
    for i, ctl in enumerate(L["controles"], start=1):
        t.setStyle(TableStyle([
            ("TEXTCOLOR", (1, i), (1, i), VERT if ctl["ok"] else ROUGE),
            ("FONTNAME", (1, i), (1, i), "Helvetica-Bold")]))
    E.append(t)

    # Les anomalies du MOTEUR DE CONTRÔLES. Le tableau ci-dessus ne porte
    # que cinq vérifications internes de cohérence de la liasse : il
    # pouvait afficher cinq « conforme » en vert alors qu'une anomalie
    # bloquante attendait dans le moteur, et le document remis au comptable
    # ne la révélait pas. Les deux ensembles n'étaient tout simplement pas
    # reliés.
    anomalies = L.get("anomalies") or []
    bloquantes = [a for a in anomalies if a["niveau"] == "BLOQUANT"]
    E.append(Paragraph("Contrôles de cohérence du dossier", st["h2"]))
    if not anomalies:
        E.append(Paragraph("Aucune anomalie détectée par les contrôles de "
                           "cohérence.", st["normal"]))
    else:
        if bloquantes:
            E.append(Paragraph(
                f"<b>{len(bloquantes)} anomalie(s) BLOQUANTE(S)</b> : cet "
                "exercice ne devrait pas être clôturé en l'état, et les "
                "montants ci-dessus peuvent s'en trouver faussés.",
                st["note"]))
        lignes = [["Niveau", "Contrôle", "Constat"]]
        for a in anomalies:
            lignes.append([a["niveau"], a["code"],
                           Paragraph(_xml(a["message"]), st["normal"])])
        t = _table(lignes, largeurs=[24 * mm, 34 * mm, 112 * mm],
                   aligne_droite=())
        for i, a in enumerate(anomalies, start=1):
            if a["niveau"] == "BLOQUANT":
                t.setStyle(TableStyle([
                    ("TEXTCOLOR", (0, i), (0, i), ROUGE),
                    ("FONTNAME", (0, i), (0, i), "Helvetica-Bold")]))
        E.append(t)

    pied = _pied_de_page(L["provisoire"])
    doc.build(E, onFirstPage=pied, onLaterPages=pied)
````


## `compta_lmnp/modules/pages.py`

````python
# Compta LMNP — Copyright © 2026 Sylvain FAURE et les contributeurs.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Gabarits HTML de l'interface web — la PRÉSENTATION, rien qu'elle.

Extraits d'app.py, qui mélangeait 1 300 lignes de HTML à la logique des
routes (52 % du fichier). Séparation stricte :
  - ce module : chaînes Jinja (gabarits de pages) et feuille de style —
    AUCUN import applicatif, aucune logique, rien d'exécutable ;
  - app.py : les routes, qui rendent ces gabarits avec leurs données.

Un gabarit se repère par sa page : PAGE_SAISIE, PAGE_IMMO, PAGE_CLOTURE,
PAGE_EX_NOUVEAU, PAGE_LIASSE, PAGE_REGLEMENTATION, PAGE_SANDBOX,
PAGE_ARCHIVES, PAGE_SAUVEGARDES_SECTION, PAGE_DOSSIERS, PAGE_PENSE_BETE,
PAGE_VEILLE — plus CSS (style global inline, distribution mono-fichier
oblige : pas de dossier static/).

L'échappement des données utilisateur est assuré par Jinja (autoescape) au
rendu, dans app.py — ces chaînes n'insèrent jamais rien elles-mêmes.
"""

CSS = """
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: system-ui, sans-serif; font-size: 14px;
       background: #f0f2f5; color: #1a1a1a; }

/* ── Header / nav ── */
/* Bleu marine ASM, avec le jaune de l'onglet actif : le bandeau porte les
   couleurs du club, et le contraste jaune sur marine est plus franc que
   le blanc sur bleu moyen d'avant. */
/* Bandeau VERROUILLÉ en haut de la fenêtre. Les pages longues — grand
   livre, liasse, contrôles — faisaient disparaître la navigation et le
   sélecteur d'exercice : changer d'onglet demandait de remonter. `sticky`
   plutôt que `fixed` : l'élément garde sa place dans le flux, donc aucune
   marge de compensation à régler sur `main`, et rien ne se glisse dessous
   au chargement.

   z-index 30 : au-dessus du contenu, mais SOUS les infobulles (40) et leur
   flèche (41) — une infobulle déclenchée dans la première ligne d'un
   tableau doit passer par-dessus le bandeau, pas dessous. */
header { background: #002b5c; color: #fff;
         display: flex; align-items: center; gap: 0; flex-wrap: wrap;
         position: sticky; top: 0; z-index: 30;
         box-shadow: 0 2px 6px rgba(0,0,0,.18); }
.brand { font-size: 16px; font-weight: 700; padding: 0 24px;
         letter-spacing: .4px; white-space: nowrap; }
nav { display: flex; flex: 1; }
nav a { display: block; padding: 14px 20px; color: rgba(255,255,255,.75);
        text-decoration: none; font-size: 13px; font-weight: 500;
        border-bottom: 3px solid transparent; transition: color .15s, border-color .15s; }
nav a:hover { color: #fff; }
/* Onglet courant : jaune sur fond assombri. L'ancien réglage — blanc sur
   bleu, souligné de bleu clair — ne se distinguait pas des autres onglets
   (retour d'usage). Le jaune tranche franchement sur le bleu du bandeau. */
nav a.active { color: #ffd54f; font-weight: 700;
        background: rgba(0,0,0,.22); border-bottom-color: #ffd54f;
        border-bottom-width: 3px; }
.header-right { margin-left: auto; padding: 0 16px;
                display: flex; align-items: center; gap: 8px; }
.header-right label { color: rgba(255,255,255,.6); font-size: 12px; }
.header-right select { background: #2d5080; color: #fff;
                       border: 1px solid #4a7ab5; border-radius: 4px;
                       padding: 4px 8px; font-size: 13px; cursor: pointer; }

/* ── Layout ── */
main { max-width: 960px; margin: 24px auto; padding: 0 16px; }
.row2 { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }

/* ── Cards ── */
/* `overflow: hidden` a été RETIRÉ d'ici. Il servait à ce que le bandeau
   coloré respecte les coins arrondis — mais il rognait aussi toute
   infobulle dépassant de la carte, c'est-à-dire la plupart de celles
   posées près d'un bord. Les coins sont désormais arrondis sur le bandeau
   lui-même, ce qui règle l'arrondi sans rien rogner. */
.card { background: #fff; border-radius: 8px;
        box-shadow: 0 1px 4px rgba(0,0,0,.12); margin-bottom: 24px; }

/* Bleu marine, avec le jaune de l'onglet actif : le bandeau porte les
   couleurs du club, et le contraste jaune sur marine est plus franc que
   le blanc sur bleu moyen d'avant.

   ATTENTION — ce commentaire était collé AU MILIEU du sélecteur, entre
   « .card- » et « header », ce qui le coupait en deux : `.card-header`
   ne recevait donc JAMAIS son `color: #fff`. Seules les variantes de
   couleur s'appliquaient, en posant un fond sans toucher au texte, qui
   héritait du noir du corps de page — titres noirs sur vert, ambre ou
   rouge foncé, illisibles. Un commentaire ne se place pas dans un
   sélecteur. */
.card-header { background: #002b5c; color: #fff; padding: 10px 20px;
               font-weight: 600; font-size: 12px;
               text-transform: uppercase; letter-spacing: .8px;
               border-radius: 8px 8px 0 0; }
/* Les variantes ne changent QUE le fond : la couleur du texte vient de la
   règle de base, et doit y rester — la redéclarer ici la ferait diverger. */
.card-header.green  { background: #1a6b3a; }
.card-header.amber  { background: #7a5200; }
.card-header.red    { background: #7a1c1c; }
.card-body { padding: 20px; }

/* ── Flash ── */
.flash { border-radius: 6px; padding: 10px 16px; margin-bottom: 20px; font-size: 13px; }
.flash-ok  { background: #d4edda; color: #155724; border: 1px solid #c3e6cb; }
.flash-err { background: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; }
.flash-warn { background: #fff3cd; color: #856404; border: 1px solid #ffeeba; }

/* ── Formulaires ── */
.form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
.form-grid .full { grid-column: 1 / -1; }
.form-grid .w1   { grid-column: span 1; }
label.field { display: block; font-size: 12px; font-weight: 600;
              color: #555; margin-bottom: 4px; }
label.field .opt { font-weight: 400; color: #999; }
.rappel { border-left: 4px solid #ccc; border-radius: 6px; background: #fafbfc;
          padding: 12px 14px; margin: 10px 0; }
.rappel-important { border-left-color: #c0392b; background: #fdf3f2; }
.rappel-a_prevoir { border-left-color: #d68910; background: #fdf9f0; }
.rappel-info      { border-left-color: #2471a3; background: #f2f7fb; }
.rappel-titre  { font-weight: 600; margin-bottom: 4px; }
.rappel-detail { font-size: 13.5px; color: #444; line-height: 1.5; }

/* Infobulle d'aide au survol : petite pastille « ? » après le libellé, qui
   dévoile un exemple de format. Pur CSS, aucun JavaScript. */
.aide { position: relative; display: inline-flex; align-items: center;
        justify-content: center; width: 15px; height: 15px; margin-left: 5px;
        border-radius: 50%; background: #c7d0dd; color: #fff; font-size: 10px;
        font-weight: 700; cursor: help; vertical-align: middle; }
.aide::after {
        content: attr(data-aide); position: absolute; left: 50%; bottom: 150%;
        transform: translateX(-50%); min-width: 180px; max-width: 280px;
        background: #1e2b3d; color: #f3f5f8; font-size: 11.5px; font-weight: 400;
        line-height: 1.45; text-align: left; padding: 8px 10px; border-radius: 6px;
        box-shadow: 0 4px 14px rgba(0,0,0,.22); opacity: 0; visibility: hidden;
        transition: opacity .12s ease; z-index: 40; white-space: normal; }
.aide::before {
        content: ""; position: absolute; left: 50%; bottom: 150%;
        transform: translateX(-50%) translateY(6px); border: 5px solid transparent;
        border-top-color: #1e2b3d; opacity: 0; visibility: hidden;
        transition: opacity .12s ease; z-index: 41; }
.aide:hover::after, .aide:hover::before { opacity: 1; visibility: visible; }
/* Bords de fenêtre : l'infobulle est centrée sur sa pastille, donc coupée
   dès que celle-ci est à moins d'une demi-largeur du bord. Ces deux
   variantes l'ancrent du bon côté ; la classe est posée au survol par le
   script de mise en page. Sans JavaScript, rien ne les active et
   l'infobulle reste centrée — elle dépasse, elle ne disparaît pas. */
.aide.aide-gauche::after  { left: 0; transform: none; }
.aide.aide-droite::after  { left: auto; right: 0; transform: none; }
.flash-err { white-space: pre-line; }   /* messages multi-lignes lisibles */

/* ── L'assistante ─────────────────────────────────────────────────────
   Décorative et NON bloquante : les infobulles CSS fonctionnent sans
   elle (sans JavaScript, ou si elle est masquée). Elle ne s'invite
   jamais — elle paraît sur demande d'aide, ou pour commenter le message
   qui vient de s'afficher, puis s'efface. */
/* Les confirmations passent par data-confirmer plutôt que par un
   gestionnaire « onclick » écrit à la main. Deux d'entre elles — dont
   celle de la RESTAURATION, la plus destructrice — contenaient un saut de
   ligne réel et une apostrophe fermante : le gestionnaire ne compilait
   pas, valait donc null, et l'action s'exécutait SANS aucune boîte de
   dialogue. Les deux qui fonctionnaient étaient précisément celles
   écrites sans apostrophe. Avec un attribut, c'est Jinja qui échappe. */
#assistant { position: fixed; right: 18px; bottom: 18px; z-index: 60;
        display: none; align-items: flex-end; gap: 10px; pointer-events: none; }
#assistant.actif { display: flex; }
/* Pixel art : image-rendering: pixelated interdit au navigateur de lisser
   les bords à l'agrandissement — sans quoi le sprite devient flou et perd
   tout l'intérêt de la technique. */
#assistant .perso { width: 112px; height: 98px; flex: none;
        image-rendering: pixelated; image-rendering: crisp-edges;
        animation: flotte 3.4s steps(2, end) infinite; }
#assistant.salue .perso { animation: salue .5s steps(2, end) 3; }

/* — les trois états — */
#assistant .sur-info, #assistant .sur-valide,
#assistant .sur-anomalie { display: none; }
#assistant.info     .sur-info     { display: block; }
#assistant.valide   .sur-valide   { display: block; }
#assistant.anomalie .sur-anomalie { display: block;
        animation: alerte 1.1s steps(2, end) infinite; }
#assistant.anomalie .bulle { background: #5b1a13; }
#assistant.anomalie .bulle::after { border-left-color: #5b1a13; }
#assistant.valide .bulle { background: #123a25; }
#assistant.valide .bulle::after { border-left-color: #123a25; }

#assistant .bulle { pointer-events: auto; position: relative; max-width: 300px;
        background: #1e2b3d; color: #f3f5f8; font-size: 12px; line-height: 1.5;
        padding: 11px 30px 11px 13px; border-radius: 10px;
        box-shadow: 0 6px 20px rgba(0,0,0,.25); opacity: 0;
        transform: translateY(6px);
        transition: opacity .18s ease, transform .18s ease, background .2s ease; }
#assistant.parle .bulle { opacity: 1; transform: translateY(0); }
#assistant .bulle::after { content: ""; position: absolute; right: -6px;
        bottom: 16px; border: 6px solid transparent; border-left-color: #1e2b3d; }
#assistant .fermer { position: absolute; top: 4px; right: 6px; border: 0;
        background: none; color: #9fb0c7; font-size: 15px; line-height: 1;
        cursor: pointer; padding: 2px 4px; }
#assistant .fermer:hover { color: #fff; }
/* Animations par PALIERS (steps) et non en interpolation continue : un
   sprite qui glisse en sous-pixels trahit le pixel art. On le fait sauter
   d'un pixel entier, comme dans un jeu. */
@keyframes flotte { 0%,100% { transform: translateY(0); }
                    50% { transform: translateY(-4px); } }
@keyframes salue  { 0%,100% { transform: translateX(0); }
                    50% { transform: translateX(-3px); } }
@keyframes alerte { 0%,100% { opacity: 1; } 50% { opacity: .62; } }
/* Accessibilité : plus aucun mouvement si le système demande le calme. */
@media (prefers-reduced-motion: reduce) {
  #assistant .perso, #assistant.anomalie .sur-anomalie { animation: none; }
  #assistant .bulle { transition: none; }
}
@media (max-width: 700px) { #assistant { display: none !important; } }
input, select, textarea {
  width: 100%; border: 1px solid #d0d5dd; border-radius: 5px;
  padding: 7px 10px; font-size: 13px; color: #1a1a1a;
  background: #fff; transition: border-color .15s; }
input:focus, select:focus, textarea:focus {
  outline: none; border-color: #1e3a5f;
  box-shadow: 0 0 0 3px rgba(30,58,95,.1); }
textarea { resize: vertical; min-height: 52px; }
.hint { font-size: 11px; color: #888; margin-top: 3px; }

/* ── Buttons ── */
.btn { display: inline-block; border: none; border-radius: 6px;
       padding: 9px 22px; font-size: 13px; font-weight: 600;
       cursor: pointer; text-decoration: none; transition: background .15s; }
.btn-primary { background: #1e3a5f; color: #fff; }
.btn-primary:hover { background: #2d5080; }
.btn-danger  { background: #7a1c1c; color: #fff; }
.btn-danger:hover  { background: #a02020; }
.btn-success { background: #1a6b3a; color: #fff; }
.btn-success:hover { background: #228a4a; }
.btn-sm { padding: 5px 12px; font-size: 12px; }
.mt { margin-top: 16px; }

/* ── Tableaux ── */
table { width: 100%; border-collapse: collapse; font-size: 13px; }
thead th { background: #f0f2f5; padding: 8px 10px; text-align: left;
           font-size: 11px; font-weight: 700; color: #555;
           text-transform: uppercase; letter-spacing: .5px;
           border-bottom: 2px solid #d0d5dd; }
tbody tr:hover { background: #f7f8fa; }
td { padding: 8px 10px; border-bottom: 1px solid #eaecef; vertical-align: top; }
td.right { text-align: right; font-variant-numeric: tabular-nums;
           font-weight: 600; white-space: nowrap; }
td.green { color: #155724; }
td.red   { color: #721c24; }
td.muted { color: #999; font-size: 11px; }
.empty { color: #999; font-style: italic; padding: 20px; text-align: center; }

/* ── Badges ── */
.badge { display: inline-block; font-size: 10px; font-weight: 700;
         border-radius: 3px; padding: 2px 6px; vertical-align: middle; }
.badge-produit { background: #d4edda; color: #155724; }
.badge-charge  { background: #fff3cd; color: #856404; }
.badge-ok      { background: #d4edda; color: #155724; }
.badge-clos    { background: #d0d5dd; color: #444; }
.badge-warn    { background: #fff3cd; color: #856404; }
.badge-err     { background: #f8d7da; color: #721c24; }

/* ── Séparateur de section ── */
h2.section { font-size: 13px; font-weight: 700; color: #555;
             text-transform: uppercase; letter-spacing: .6px;
             margin: 24px 0 12px; border-bottom: 1px solid #d0d5dd;
             padding-bottom: 6px; }

/* ── Résumé fiscal ── */
.kpi-row { display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 16px; }
.kpi { flex: 1; min-width: 120px; background: #f7f8fa; border-radius: 6px;
       padding: 12px 16px; }
.kpi .kpi-label { font-size: 11px; color: #666; margin-bottom: 4px;
                  text-transform: uppercase; letter-spacing: .4px; }
.kpi .kpi-val   { font-size: 20px; font-weight: 700; }
.kpi .kpi-val.pos { color: #155724; }
.kpi .kpi-val.neg { color: #721c24; }
"""


ASSISTANT = """
<!-- ══════════════════════════════════════════════════════════════════════
     L'ASSISTANTE — un seul dessin, trois états.

     SVG EN LIGNE plutôt qu'une illustration : le logiciel se distribue en
     un dossier sans ressources externes, un dessin vectoriel reste net à
     toute taille, pèse quelques kilo-octets là où une image en pèse
     mille, et se recolorie par CSS — c'est ce qui permet trois états sans
     trois fichiers.

     ÉTATS (classe portée par #assistant) :
       .info      — elle explique ; tablette sombre, chiffres
       .valide    — sourire, pouce levé ; tablette verte, coche
       .anomalie  — sourcils froncés ; tablette rouge, triangle d'alerte
     ══════════════════════════════════════════════════════════════════ -->
<div id="assistant" class="info" aria-live="polite">
  <div class="bulle">
    <button class="fermer" type="button" title="Masquer l'assistante"
            aria-label="Masquer l'assistante">&times;</button>
    <span class="texte"></span>
  </div>
  <svg class="perso" viewBox="0 0 24 21" xmlns="http://www.w3.org/2000/svg" shape-rendering="crispEdges"
       role="img" aria-hidden="true">
    <g class="corps">
      <rect x="8" y="0" width="6" height="1" fill="#14121c"/>
      <rect x="6" y="1" width="2" height="1" fill="#14121c"/>
      <rect x="8" y="1" width="6" height="1" fill="#a8a6b8"/>
      <rect x="14" y="1" width="2" height="1" fill="#14121c"/>
      <rect x="4" y="2" width="2" height="1" fill="#14121c"/>
      <rect x="6" y="2" width="1" height="1" fill="#a8a6b8"/>
      <rect x="7" y="2" width="8" height="1" fill="#e8e6ef"/>
      <rect x="15" y="2" width="1" height="1" fill="#a8a6b8"/>
      <rect x="16" y="2" width="2" height="1" fill="#14121c"/>
      <rect x="2" y="3" width="2" height="1" fill="#14121c"/>
      <rect x="4" y="3" width="2" height="1" fill="#a8a6b8"/>
      <rect x="6" y="3" width="10" height="1" fill="#e8e6ef"/>
      <rect x="16" y="3" width="2" height="1" fill="#a8a6b8"/>
      <rect x="18" y="3" width="2" height="1" fill="#14121c"/>
      <rect x="2" y="4" width="1" height="3" fill="#14121c"/>
      <rect x="3" y="4" width="1" height="3" fill="#a8a6b8"/>
      <rect x="4" y="4" width="14" height="1" fill="#e8e6ef"/>
      <rect x="18" y="4" width="1" height="3" fill="#a8a6b8"/>
      <rect x="19" y="4" width="1" height="3" fill="#14121c"/>
      <rect x="4" y="5" width="1" height="2" fill="#e8e6ef"/>
      <rect x="5" y="5" width="12" height="1" fill="#2f8f5f"/>
      <rect x="17" y="5" width="1" height="2" fill="#e8e6ef"/>
      <rect x="5" y="6" width="12" height="1" fill="#57c98d"/>
      <rect x="2" y="7" width="2" height="1" fill="#14121c"/>
      <rect x="4" y="7" width="14" height="1" fill="#a8a6b8"/>
      <rect x="18" y="7" width="2" height="1" fill="#14121c"/>
      <rect x="4" y="8" width="1" height="2" fill="#14121c"/>
      <rect x="5" y="8" width="2" height="1" fill="#6e6c82"/>
      <rect x="7" y="8" width="2" height="1" fill="#8ad8ff"/>
      <rect x="9" y="8" width="4" height="1" fill="#6e6c82"/>
      <rect x="13" y="8" width="2" height="1" fill="#8ad8ff"/>
      <rect x="15" y="8" width="2" height="1" fill="#6e6c82"/>
      <rect x="17" y="8" width="1" height="2" fill="#14121c"/>
      <rect x="5" y="9" width="12" height="1" fill="#6e6c82"/>
      <rect x="21" y="9" width="3" height="1" fill="#14121c"/>
      <rect x="5" y="10" width="2" height="1" fill="#14121c"/>
      <rect x="7" y="10" width="8" height="1" fill="#6e6c82"/>
      <rect x="15" y="10" width="2" height="1" fill="#14121c"/>
      <rect x="20" y="10" width="1" height="3" fill="#14121c"/>
      <rect x="21" y="10" width="2" height="3" fill="#1e2b3d"/>
      <rect x="23" y="10" width="1" height="3" fill="#14121c"/>
      <rect x="7" y="11" width="2" height="1" fill="#14121c"/>
      <rect x="9" y="11" width="4" height="1" fill="#6e6c82"/>
      <rect x="13" y="11" width="2" height="1" fill="#14121c"/>
      <rect x="3" y="12" width="5" height="1" fill="#14121c"/>
      <rect x="8" y="12" width="6" height="1" fill="#f2c14e"/>
      <rect x="14" y="12" width="5" height="1" fill="#14121c"/>
      <rect x="2" y="13" width="1" height="3" fill="#14121c"/>
      <rect x="3" y="13" width="4" height="1" fill="#e8e6ef"/>
      <rect x="7" y="13" width="1" height="3" fill="#14121c"/>
      <rect x="8" y="13" width="6" height="1" fill="#3a6ea8"/>
      <rect x="14" y="13" width="1" height="3" fill="#14121c"/>
      <rect x="15" y="13" width="4" height="1" fill="#e8e6ef"/>
      <rect x="19" y="13" width="5" height="1" fill="#14121c"/>
      <rect x="3" y="14" width="1" height="2" fill="#e8e6ef"/>
      <rect x="4" y="14" width="2" height="2" fill="#a8a6b8"/>
      <rect x="6" y="14" width="1" height="2" fill="#e8e6ef"/>
      <rect x="8" y="14" width="2" height="2" fill="#3a6ea8"/>
      <rect x="10" y="14" width="2" height="2" fill="#f2c14e"/>
      <rect x="12" y="14" width="2" height="2" fill="#3a6ea8"/>
      <rect x="15" y="14" width="1" height="2" fill="#e8e6ef"/>
      <rect x="16" y="14" width="2" height="2" fill="#a8a6b8"/>
      <rect x="18" y="14" width="1" height="2" fill="#e8e6ef"/>
      <rect x="19" y="14" width="1" height="2" fill="#14121c"/>
      <rect x="2" y="16" width="6" height="1" fill="#14121c"/>
      <rect x="8" y="16" width="6" height="2" fill="#3a6ea8"/>
      <rect x="14" y="16" width="6" height="1" fill="#14121c"/>
      <rect x="6" y="17" width="1" height="2" fill="#14121c"/>
      <rect x="7" y="17" width="1" height="1" fill="#26507d"/>
      <rect x="14" y="17" width="1" height="1" fill="#26507d"/>
      <rect x="15" y="17" width="1" height="2" fill="#14121c"/>
      <rect x="7" y="18" width="2" height="1" fill="#26507d"/>
      <rect x="9" y="18" width="4" height="1" fill="#3a6ea8"/>
      <rect x="13" y="18" width="2" height="1" fill="#26507d"/>
      <rect x="6" y="19" width="2" height="1" fill="#14121c"/>
      <rect x="8" y="19" width="6" height="1" fill="#26507d"/>
      <rect x="14" y="19" width="2" height="1" fill="#14121c"/>
      <rect x="8" y="20" width="6" height="1" fill="#14121c"/>
    </g>
    <g class="sur-info">
      <rect x="21" y="10" width="2" height="1" fill="#8fb4e0"/>
      <rect x="21" y="11" width="1" height="1" fill="#f2c14e"/>
      <rect x="22" y="11" width="1" height="1" fill="#1e2b3d"/>
      <rect x="21" y="12" width="2" height="1" fill="#8fb4e0"/>
    </g>
    <g class="sur-valide">
      <rect x="7" y="8" width="2" height="1" fill="#57c98d"/>
      <rect x="13" y="8" width="2" height="1" fill="#57c98d"/>
      <rect x="21" y="10" width="1" height="1" fill="#0f3320"/>
      <rect x="22" y="10" width="1" height="1" fill="#57c98d"/>
      <rect x="21" y="11" width="1" height="2" fill="#57c98d"/>
      <rect x="22" y="11" width="1" height="2" fill="#0f3320"/>
    </g>
    <g class="sur-anomalie">
      <rect x="7" y="8" width="2" height="1" fill="#ff8a72"/>
      <rect x="13" y="8" width="2" height="1" fill="#ff8a72"/>
      <rect x="21" y="10" width="1" height="3" fill="#4a1410"/>
      <rect x="22" y="10" width="1" height="3" fill="#ff8a72"/>
    </g>
  </svg>
</div>
<script>
(function () {
  var boite = document.getElementById("assistant");
  if (!boite) return;
  if (document.cookie.indexOf("assistant=0") !== -1) return;
  var texte = boite.querySelector(".texte");
  var minuteur = null, premiere = true;

  function etat(nom) {
    boite.classList.remove("info", "valide", "anomalie");
    boite.classList.add(nom || "info");
  }
  function montrer(aide, nom) {
    clearTimeout(minuteur);
    etat(nom);
    texte.textContent = aide;
    boite.classList.add("actif");
    requestAnimationFrame(function () {
      boite.classList.add("parle");
      if (premiere) {
        premiere = false;
        boite.classList.add("salue");
        setTimeout(function () { boite.classList.remove("salue"); }, 1700);
      }
    });
  }
  function cacher(delai) {
    clearTimeout(minuteur);
    minuteur = setTimeout(function () {
      boite.classList.remove("parle");
      setTimeout(function () { boite.classList.remove("actif"); }, 250);
    }, delai === undefined ? 400 : delai);
  }

  // 1. Infobulles : elle EXPLIQUE. textContent, jamais innerHTML.
  document.querySelectorAll(".aide[data-aide]").forEach(function (a) {
    a.setAttribute("tabindex", "0");
    ["mouseenter", "focus"].forEach(function (ev) {
      a.addEventListener(ev, function () {
        montrer(a.dataset.aide, a.dataset.aideEtat || "info");
      });
    });
    ["mouseleave", "blur"].forEach(function (ev) {
      a.addEventListener(ev, function () { cacher(); });
    });
  });
  var bulle = boite.querySelector(".bulle");
  bulle.addEventListener("mouseenter", function () { clearTimeout(minuteur); });
  bulle.addEventListener("mouseleave", function () { cacher(); });
  boite.querySelector(".fermer").addEventListener("click", function () {
    boite.classList.remove("actif", "parle");
    document.cookie = "assistant=0; path=/; max-age=31536000";
  });

  // 2. Elle COMMENTE ce qui vient de se passer — c'est ce qui donne un
  //    sens aux trois visages. Le message existe déjà à l'écran : elle ne
  //    le remplace pas, elle l'incarne, puis s'efface d'elle-même.
  var err = document.querySelector(".flash-err");
  var avert = document.querySelector(".flash-warn");
  var ok = document.querySelector(".flash-ok");
  var reaction = err ? ["anomalie", err] : avert ? ["anomalie", avert]
               : ok ? ["valide", ok] : null;
  if (reaction) {
    var mot = (reaction[1].textContent || "").trim();
    if (mot.length > 240) { mot = mot.slice(0, 237) + "\u2026"; }
    setTimeout(function () { montrer(mot, reaction[0]); cacher(6500); }, 500);
  }
})();
</script>
"""

PAGE_DON_SECTION = """
<div class="card" style="border-left:4px solid #1a73e8;background:#f5f9ff">
  <div class="card-body" style="padding:12px 16px;display:flex;
       align-items:center;gap:14px;flex-wrap:wrap">
    <div style="flex:1;min-width:260px">
      <b>Ce logiciel est gratuit.</b>
      <span class="muted">S'il vous fait gagner du temps (ou des honoraires
      d'expert-comptable), vous pouvez soutenir son développement par un don
      — c'est entièrement facultatif et ça ne débloque rien : tout est déjà
      débloqué.</span>
    </div>
    <a href="https://www.paypal.me/sfaure01" target="_blank" rel="noopener"
       style="display:inline-block;background:#1a73e8;color:#fff;
       padding:8px 18px;border-radius:6px;text-decoration:none;
       font-weight:600">Faire un don (PayPal)</a>
    <span class="muted" style="font-size:.85em">Compte PayPal :
      sylvainfaure01@hotmail.fr</span>
  </div>
</div>
"""

PAGE_IMPORT_SECTION = """
<div class="card"><div class="card-body">
  <h2>Importer un relevé bancaire (CSV)
    <span style="background:#fff3cd;color:#7a5c00;border:1px solid #e6cf8b;
          border-radius:4px;padding:2px 8px;font-size:.7em;font-weight:600;
          vertical-align:middle">FONCTION EXPÉRIMENTALE</span></h2>
  <p style="background:#fff8e6;border-left:4px solid #e8b93e;padding:8px 12px">
  Cette fonction a été testée sur des relevés types, pas encore sur la
  diversité des exports réels des banques (chaque banque a son dialecte).
  <b>Vérifiez chaque proposition avant de valider</b> — rien n'est écrit
  sans votre accord, et une opération validée par erreur s'annule d'un clic
  (contre-passation). Vos retours sur des relevés réels sont bienvenus.</p>
  <p class="muted">Colonnes attendues : date ; libellé ; montant. Les exports
  des banques françaises sont acceptés tels quels (encodage Windows, montants
  « 1 234,56 »…). Chaque ligne devient une <b>proposition</b> que vous validez
  ou écartez — rien n'est écrit sans votre accord.</p>
  <form method="post" action="/import/proposer" enctype="multipart/form-data"
        style="display:flex;gap:10px;align-items:center">
    <input type="file" name="releve" accept=".csv,.txt" required>
    <button type="submit">Analyser le relevé</button>
  </form>
  {% if propositions %}
  <form method="post" action="/import/valider" style="margin-top:14px">
    <table>
      <thead><tr><th></th><th>Date</th><th>Libellé</th><th>Catégorie
        proposée</th><th style="text-align:right">Montant</th></tr></thead>
      <tbody>
      {% for p in propositions %}
        <tr>
          <td><input type="checkbox" name="ligne" value="{{ loop.index0 }}"
                     checked></td>
          <td>{{ p.date_operation }}</td>
          <td>{{ p.libelle }}</td>
          <td>{{ p.type }}</td>
          <td style="text-align:right">{{ '%.2f'|format(p.montant) }}</td>
        </tr>
      {% endfor %}
      </tbody>
    </table>
    <input type="hidden" name="jeton" value="{{ jeton }}">
    <p><button type="submit">Enregistrer les lignes cochées</button></p>
  </form>
  {% endif %}
</div></div>
"""

PAGE_SAISIE = """
<div class="card">
  <div class="card-header">Nouvelle saisie</div>
  <div class="card-body">
    <form method="post" action="/saisir">
      <input type="hidden" name="annee" value="{{ annee }}">
      <div class="form-grid">

        <div class="full">
          <label class="field" for="type">Que souhaitez-vous saisir ?<span
            class="aide" data-aide="Choisissez la nature de l'opération : un loyer encaissé, une charge (assurance, énergie…), une acquisition à immobiliser. Le bon compte comptable est appliqué automatiquement.">?</span></label>
          <select id="type" name="type" required onchange="majPeriode(this.value)">
            <option value="" disabled selected>— choisir —</option>
            {% for groupe, items in choix_groupes %}
            <optgroup label="{{ groupe }}">
              {% for key, g in items %}
              <option value="{{ key }}" data-perio="{{ g['periodicite'] }}">{{ g['libelle'] }}</option>
              {% endfor %}
            </optgroup>
            {% endfor %}
          </select>
        </div>

        {% if biens|length > 1 %}
        <div class="full">
          <label class="field" for="bien_id">Bien concerné</label>
          <select id="bien_id" name="bien_id">
            {% for b in biens %}<option value="{{ b['id'] }}">{{ b['libelle'] }}</option>{% endfor %}
          </select>
        </div>
        {% else %}
        <input type="hidden" name="bien_id" value="{{ biens[0]['id'] if biens else 1 }}">
        {% endif %}

        <div>
          <label class="field" for="date_operation">Date de l'opération<span
            class="aide" data-aide="Jour de l'opération, au format AAAA-MM-JJ (ex. 2026-03-15). Elle doit tomber dans l'exercice ouvert, sinon la saisie est refusée.">?</span></label>
          <input type="date" id="date_operation" name="date_operation"
                 value="{{ today }}" required>
        </div>

        <div id="bloc-periode">
          <label class="field" for="periode">Période
            <span class="opt">(AAAA-MM, si mensuel)</span><span
            class="aide" data-aide="Mois concerné pour une charge ou un loyer récurrent, au format AAAA-MM (ex. 2026-03 pour mars 2026). Sert à repérer un loyer manquant sur l'année.">?</span></label>
          <input type="month" id="periode" name="periode" value="{{ today[:7] }}">
        </div>

        <div>
          <label class="field" for="montant">Montant TTC (€)<span
            class="aide" data-aide="Montant positif, en euros. La virgule et le point sont acceptés (ex. 795,50 ou 795.50). Pas de séparateur de milliers.">?</span></label>
          <input type="number" id="montant" name="montant"
                 step="0.01" min="0.01" placeholder="0,00" required>
        </div>

        <div>
          <label class="field" for="piece_ref">Pièce de l'écriture
            <span class="opt">(réf. justificatif)</span><span
            class="aide" data-aide="Référence du justificatif classé : quittance, facture, relevé… (ex. QUITTANCE-2026-03, FAC-042). Obligatoire — c'est le lien vers la pièce en cas de contrôle.">?</span></label>
          <input type="text" id="piece_ref" name="piece_ref"
                 placeholder="ex. QUITTANCE-2026-03, FAC-042">
        </div>

        <div>
          <label class="field" for="tiers">Tiers
            <span class="opt">(optionnel)</span><span
            class="aide" data-aide="Nom de la personne ou de l'entreprise concernée (ex. Locataire Dupont, EDF, Syndic Foncia). Facultatif, mais utile pour retrouver une opération.">?</span></label>
          <input type="text" id="tiers" name="tiers"
                 placeholder="ex. Locataire, EDF, Syndic…">
        </div>

        <div>
          <label class="field" for="libelle">Commentaire
            <span class="opt">(optionnel)</span><span
            class="aide" data-aide="Libellé personnalisé de l'écriture. Laissé vide, le libellé standard du gabarit est utilisé. Évitez les tabulations et retours à la ligne (interdits dans un FEC).">?</span></label>
          <input type="text" id="libelle" name="libelle"
                 placeholder="Remplace le libellé standard du gabarit">
        </div>

      </div>
      <button type="submit" class="btn btn-primary mt">Enregistrer</button>
    </form>
  </div>
</div>

<div class="card">
  <div class="card-header green" id="carte-appel">Appel de charges de copropriété — ventilation (formulaire distinct, ci-dessous)</div>
  <div class="card-body">
    <p class="muted" style="margin-bottom:12px">
      <strong>C'est ICI que se saisit un appel de charges du syndic</strong> —
      pas dans le formulaire de saisie simple ci-dessus. Un appel mélange
      plusieurs composantes fiscales : ventilez-le en une fois, les écritures
      sont rattachées à la même pièce.
      <strong>Charges courantes</strong> : déductibles en totalité — y compris
      la quote-part récupérable sur le locataire, puisque les provisions
      encaissées sont imposées en produits (traitement BIC symétrique).
      <strong>Fonds travaux ALUR</strong> : comptabilisé en charge mais
      réintégré fiscalement à la clôture (contribution capitalisée, non
      déductible). <strong>Travaux hors budget</strong> : en entretien ; pour
      de gros travaux (ravalement, toiture…), préférez une immobilisation.
    </p>
    <form method="post" action="/saisir-appel"
          style="display:grid;grid-template-columns:1fr 1fr 1fr 1fr 1fr auto;gap:10px;align-items:end">
      <div><label class="field">Date de l'appel</label>
        <input type="date" name="date_operation" value="{{ today }}" required></div>
      <div><label class="field">Période</label>
        <input type="month" name="periode" value="{{ today[:7] }}"></div>
      <div><label class="field">Charges courantes (€)</label>
        <input type="number" step="0.01" min="0" name="charges_courantes"
               placeholder="déductibles"></div>
      <div><label class="field">Fonds travaux ALUR (€)</label>
        <input type="number" step="0.01" min="0" name="fonds_alur"
               placeholder="réintégré"></div>
      <div><label class="field">Travaux hors budget (€)</label>
        <input type="number" step="0.01" min="0" name="travaux"
               placeholder="entretien"></div>
      <button type="submit" class="btn btn-success">Ventiler l'appel</button>
    </form>
  </div>
</div>

<div class="card">
  <div class="card-header">Opérations {{ annee }}</div>
  <div class="card-body" style="padding:0">
    {% if ops %}
    <table>
      <thead>
        <tr>
          <th>N°</th><th>Date</th><th>Nature</th><th>Libellé</th>
          <th>Pièce</th><th>Tiers</th><th>Période</th>
          <th style="text-align:right">Montant TTC</th>
          <th style="text-align:center">Dupliquer</th>
          <th style="text-align:center">Annuler</th>
        </tr>
      </thead>
      <tbody>
        {% for op in ops %}
        {% set is_p = op['type'] in produit_types %}
        <tr>
          <td class="muted">BQ {{ op['ecriture_num'] }}</td>
          <td>{{ op['date_operation'][8:10] }}/{{ op['date_operation'][5:7] }}/{{ op['date_operation'][:4] }}</td>
          <td><span class="badge {{ 'badge-produit' if is_p else 'badge-charge' }}">
            {{ 'Recette' if is_p else 'Charge' }}</span></td>
          <td>{{ op['libelle'] or gabarits_lib.get(op['type'], op['type']) }}</td>
          <td>{{ op['piece_ref'] or '' }}</td>
          <td>{{ op['tiers'] or '' }}</td>
          <td>{{ op['periode'] or '' }}</td>
          <td class="right {{ 'green' if is_p else 'red' }}">
            {{ '%.2f'|format(op['montant'])|replace('.', ',') }} €</td>
          <td>
            {% if not op['annulee'] %}
            <form method="post" action="/operation/{{ op['id'] }}/dupliquer"
                  style="display:inline">
              <button type="submit" class="btn"
                      style="padding:2px 8px;font-size:12px"
                      title="Dupliquer cette opération au mois suivant
(même montant, même nature — date et période décalées d'un mois)">→ M+1</button>
            </form>
            {% endif %}
          </td>
          <td>
            {% if op['annulee'] %}
              <span class="badge badge-clos" title="Une écriture inverse a été passée : les montants se neutralisent. Rien n'a été supprimé.">annulée</span>
            {% else %}
            <form method="post" action="/operation/{{ op['id'] }}/annuler"
                  style="display:inline"
                  data-confirmer="Annuler cette opération ? Une écriture INVERSE sera passée à la même date (contre-passation). Rien n'est supprimé : la numérotation reste dense et la piste comptable complète.">
              <button type="submit" class="btn-secondaire"
                      style="padding:2px 8px;font-size:12px"
                      title="Annuler par contre-passation : une écriture inverse est passée à la même date. Rien n'est supprimé — c'est le geste comptable, pas une suppression.">Annuler</button>
            </form>
            {% endif %}
          </td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
    {% else %}
    <p class="empty">Aucune opération saisie pour {{ annee }}.</p>
    {% endif %}
  </div>
</div>

<script>
const perioMap = {{ perio | tojson }};
function majPeriode(type) {
  const bloc = document.getElementById('bloc-periode');
  bloc.style.display = (perioMap[type] === 'mensuel') ? '' : 'none';
}
majPeriode(document.getElementById('type').value);
</script>
"""


PAGE_IMMO = """
{% if not exploitant %}
<div class="card">
  <div class="card-header amber">Exploitant — configuration initiale</div>
  <div class="card-body">
    <p style="margin-bottom:16px;color:#555;font-size:13px">
      Aucun exploitant enregistré. Renseignez vos informations pour pouvoir créer un bien.
    </p>
    <form method="post" action="/immobilisations/exploitant">
      <input type="hidden" name="annee" value="{{ annee }}">
      <div class="form-grid">
        <div><label class="field">Nom / Raison sociale</label>
          <input name="nom" required placeholder="DUPONT JEAN"></div>
        <div><label class="field">SIREN</label>
          <input name="siren" required placeholder="123456789" maxlength="9"></div>
        <div class="full"><label class="field">Adresse</label>
          <input name="adresse" placeholder="1 rue de la Paix, 75001 Paris"></div>
      </div>
      <button type="submit" class="btn btn-primary mt">Enregistrer l'exploitant</button>
    </form>
  </div>
</div>
{% else %}

<!-- Biens & composants existants -->
{% if biens %}
{% for bien in biens %}
<div class="card">
  <div class="card-header">{{ bien['libelle'] }} — {{ bien['adresse'] or '' }}
    {% if bien['date_cession'] %}
      <span style="float:right;font-weight:400;color:#c0392b">Cédé le {{ bien['date_cession'] }}</span>
    {% else %}
      <details style="float:right;font-weight:400">
        <summary style="cursor:pointer">Céder ce bien…</summary>
        <form method="post" action="/immobilisations/bien/{{ bien['id'] }}/ceder"
              style="margin-top:8px;display:flex;gap:8px;align-items:center">
          <label class="field" style="margin:0">Date
            <span class="aide" data-aide="Date de l'acte de vente (AAAA-MM-JJ). Les composants sont amortis au prorata jusqu'à cette date, puis sortis du bilan.">?</span></label>
          <input type="date" name="date_cession" required>
          <label class="field" style="margin:0">Prix (€)
            <span class="aide" data-aide="Prix de cession de l'acte. La plus-value relève du régime des particuliers (déclarée par le notaire) : elle est neutralisée dans le résultat LMNP.">?</span></label>
          <input type="number" name="prix_cession" step="0.01" min="0" required style="width:120px">
          <!-- data-confirmer, pas un littéral JS : le texte y est un
               ATTRIBUT, donc apostrophes et sauts de ligne sans danger.
               C'est le mécanisme posé en passe D ; ces deux confirmations
               ne l'avaient pas reçu et contournaient le problème en
               RETIRANT les apostrophes du texte lu par l'utilisateur. -->
          <button type="submit" data-confirmer="Céder définitivement ce bien ? Les composants seront sortis du bilan.">Valider la cession</button>
        </form>
      </details>
    {% endif %}
  </div>
  <div class="card-body" style="padding:0">
    <table>
      <thead>
        <tr>
          <th>Réf.</th><th>Composant</th><th>Catégorie</th>
          <th style="text-align:right">Valeur brute</th>
          <th>Durée</th><th>Mise en service</th>
          <th>Compte</th><th>Amort.</th><th style="text-align:center">Durée</th>
        </tr>
      </thead>
      <tbody>
        {% for c in composants if c['bien_id'] == bien['id'] %}
        <tr>
          <td class="muted">{{ c['code_immo'] or '—' }}</td>
          <td>{{ c['libelle'] }}</td>
          <td>{{ c['categorie'] or '—' }}</td>
          <td class="right">{{ '%.2f'|format(c['valeur_brute'])|replace('.', ',') }} €</td>
          <td>{{ (c['duree_annees']|string + ' ans') if c['duree_annees'] else '∞ (terrain)' }}</td>
          <td>{{ c['date_mise_service'] or '—' }}</td>
          <td class="muted">{{ c['compte_immo'] }}</td>
          <td><span class="badge {{ 'badge-ok' if c['amortissable'] else 'badge-clos' }}">
            {{ 'Oui' if c['amortissable'] else 'Non' }}</span></td>
          <td style="text-align:center">
            <form method="post" action="/immobilisations/composant/{{ c['id'] }}/duree"
                  style="margin:0;display:flex;gap:4px;justify-content:center">
              <input type="number" name="duree_annees" min="0" max="100"
                     value="{{ c['duree_annees'] or 0 }}" style="width:60px"
                     title="0 = non amortissable">
              <button type="submit" class="btn-secondaire">Corriger</button>
            </form>
          </td>
        </tr>
        {% else %}
        <tr><td colspan="9" class="empty">Aucun composant pour ce bien.</td></tr>
        {% endfor %}
      </tbody>
    </table>
  </div>
</div>
{% endfor %}
{% endif %}

<div class="row2">

  <!-- Nouveau bien -->
  <div class="card">
    <div class="card-header green">Ajouter un bien immobilier</div>
    <div class="card-body">
      <form method="post" action="/immobilisations/bien">
        <input type="hidden" name="annee" value="{{ annee }}">
        <div style="display:grid;gap:12px">
          <div><label class="field">Libellé du bien</label>
            <input name="libelle" required placeholder="Appartement 2P — Rue Gergovia"></div>
          <div><label class="field">Adresse <span class="opt">(optionnel)</span></label>
            <input name="adresse" placeholder="12 Rue Gergovia, 63000 Clermont-Ferrand"></div>
          <div><label class="field">Date d'acquisition</label>
            <input type="date" name="date_acquisition"></div>
          <div><label class="field">Prix total d'acquisition (€) <span class="opt">(optionnel)</span></label>
            <input type="number" name="prix_total" step="0.01" min="0" placeholder="117 000,00"></div>
          <div><label class="field">Quote-part terrain <span class="opt">(ex. 0.09)</span></label>
            <input type="number" name="quote_part_terrain" step="0.000001" min="0" max="1" placeholder="0.09">
            <p class="hint">Rapport terrain / prix total — sert au calcul de la décomposition.</p></div>
        </div>
        <button type="submit" class="btn btn-primary mt">Créer le bien</button>
      </form>
    </div>
  </div>

  {% for bien in biens %}{% if ventilations.get(bien['id']) %}
  <div class="card" style="border-left:4px solid #1a73e8;background:#f5f9ff">
    <div class="card-body">
      <h2 style="margin-top:0">Ventilation initiale — {{ bien['libelle'] }}</h2>
      <p>Avant d'ajouter des composants un par un, <b>répartissez le prix
      d'acquisition</b> ({{ '%.2f'|format(bien['prix_total'] or 0) }} €).
      C'est cette décomposition qui fait tout l'intérêt du régime réel :
      un bien saisi en bloc s'amortit à la vitesse du gros œuvre, et le
      mobilier — qui devrait s'amortir en quelques années — s'étale alors
      sur des décennies.</p>
      <p class="muted">Les parts pré-remplies sont des <b>ordres de grandeur
      usuels</b>, à ajuster : la répartition doit refléter la réalité du bien
      et les pièces de l'acquisition. Les durées suivent les usages admis par
      l'administration (BOI-ANNX-000115) et restent elles aussi indicatives.</p>
      <form method="post" action="/immobilisations/ventiler"
            id="form-vent-{{ bien['id'] }}">
        <input type="hidden" name="bien_id" value="{{ bien['id'] }}">
        <table>
          <thead><tr><th>Poste</th><th style="text-align:right">Montant</th>
            <th style="text-align:right">Durée</th><th>À quoi ça correspond</th></tr></thead>
          <tbody>
          {% for l in ventilations[bien['id']] %}
            <tr>
              <td>{{ l.libelle }}</td>
              <td style="text-align:right">
                <input type="number" step="0.01" min="0" style="width:120px"
                       class="vent-{{ bien['id'] }}"
                       name="montant_{{ l.cle }}" value="{{ '%.2f'|format(l.montant) }}"></td>
              <td style="text-align:right">
                <input type="number" min="0" max="100" style="width:70px"
                       name="duree_{{ l.cle }}" value="{{ l.duree }}"></td>
              <td class="muted" style="font-size:.9em">{{ l.note }}</td>
            </tr>
          {% endfor %}
          </tbody>
        </table>
        <p style="margin:10px 0">Total ventilé :
          <b id="tot-{{ bien['id'] }}">—</b>
          <span class="muted">/ prix d'acquisition
          {{ '%.2f'|format(bien['prix_total'] or 0) }} €</span>
          <span id="ec-{{ bien['id'] }}"></span></p>
        <p class="muted" style="font-size:.9em"><b>Frais d'acquisition</b>
        (notaire, droits de mutation, commission d'agence) : ils ne figurent
        pas ci-dessus car ils relèvent d'un choix — se déduire en charge
        l'année de l'acquisition, ou s'incorporer au prix de revient pour
        être amortis. Décidez avant de ventiler : l'option se retient une
        fois pour toutes.</p>
        <label><input type="checkbox" name="sans_ecriture" value="1">
          Ne pas générer les écritures d'acquisition (bien déjà porté par
          les à-nouveaux d'un exercice antérieur)</label>
        <p><button type="submit">Créer ces composants</button></p>
      </form>
      <script>
      (function(){
        var id = "{{ bien['id'] }}", prix = {{ bien['prix_total'] or 0 }};
        function maj(){
          var t = 0;
          document.querySelectorAll(".vent-" + id).forEach(function(i){
            t += parseFloat(i.value || 0); });
          t = Math.round(t * 100) / 100;
          document.getElementById("tot-" + id).textContent =
            t.toFixed(2) + " \u20ac";
          var e = document.getElementById("ec-" + id);
          if (!prix) { e.textContent = ""; return; }
          var ec = t - prix, pct = Math.abs(ec) / prix * 100;
          e.textContent = pct < 0.01 ? "  \u2713 le compte est juste"
            : "  \u00e9cart " + (ec > 0 ? "+" : "") + ec.toFixed(2)
              + " \u20ac (" + pct.toFixed(1) + " %)";
          e.style.color = pct > 5 ? "#c5221f" : (pct < 0.01 ? "#188038" : "#e8710a");
        }
        document.querySelectorAll(".vent-" + id).forEach(function(i){
          i.addEventListener("input", maj); });
        maj();
      })();
      </script>
    </div>
  </div>
  {% endif %}{% endfor %}

  {% if amort_anterieurs %}
  <div class="card" style="border-left:4px solid #e8710a;background:#fff8f0">
    <div class="card-body">
      <h2 style="margin-top:0">Amortissements antérieurs non repris</h2>
      <p>Vos composants sont amortis depuis leur mise en service, mais
      <b>{{ '%.2f'|format(amort_anterieurs) }} €</b> d'amortissements déjà
      courus avant cet exercice ne figurent pas dans les comptes. C'est le
      cas habituel d'un bien acquis il y a plusieurs années et saisi ici
      pour la première fois : l'écriture d'entrée porte la valeur brute,
      sans le cumul déjà pratiqué.</p>
      <p class="muted">Tant que ce cumul n'est pas repris, le bilan présente
      le bien comme neuf alors que le tableau 2033-C déroule son plan depuis
      l'origine — l'écart réapparaîtra à chaque liasse, et la valeur nette
      comptable servant au calcul d'une future plus-value sera fausse.</p>
      <form method="post" action="/immobilisations/reprendre-amortissements"
            data-confirmer="Passer l'écriture de reprise ? Le résultat de l'exercice n'est pas modifié : seul le bilan est corrigé.">
        <input type="hidden" name="annee" value="{{ annee }}">
        <button type="submit">Reprendre les amortissements antérieurs</button>
      </form>
      <p class="hint">Écriture OD au 1er janvier, contrepartie compte de
      l'exploitant. Le résultat de l'exercice n'est pas affecté.</p>
    </div>
  </div>
  {% endif %}

  <!-- Nouveau composant -->
  <div class="card">
    <div class="card-header green">Ajouter un composant</div>
    <div class="card-body">
      {% if not biens %}
      <p class="empty">Créez d'abord un bien.</p>
      {% else %}
      <form method="post" action="/immobilisations/composant">
        <input type="hidden" name="annee" value="{{ annee }}">
        <div style="display:grid;gap:12px">
          <div><label class="field">Bien</label>
            <select name="bien_id">
              {% for b in biens %}<option value="{{ b['id'] }}">{{ b['libelle'] }}</option>{% endfor %}
            </select></div>
          <div><label class="field">Libellé du composant</label>
            <input name="libelle" required placeholder="Gros oeuvre, Cuisine équipée…"></div>
          <div><label class="field">Catégorie</label>
            <select name="categorie">
              <option>Terrain</option><option>Bâtiment</option>
              <option>Travaux</option><option>Mobilier</option><option>Autre</option>
            </select></div>
          <div><label class="field">Compte d'immobilisation</label>
            <select name="compte_immo" id="cpt_immo" onchange="majAmort(this.value)">
              {% for num, lib, amort in comptes_immo %}
              <option value="{{ num }}" data-amort="{{ amort or '' }}">{{ num }} — {{ lib }}</option>
              {% endfor %}
            </select></div>
          <div><label class="field">Valeur brute (€)</label>
            <input type="number" name="valeur_brute" step="0.01" min="0" required placeholder="58 500,00"></div>
          <div><label class="field">Durée d'amortissement (années)
            <span class="opt">(0 = non amortissable)</span>
            <span class="aide" data-aide="Durees usuelles admises par l'administration (BOI-ANNX-000115) : gros oeuvre / structure 40 a 60 ans ; facade et etancheite 20 a 30 ans ; installations generales et techniques (chauffage, electricite, plomberie) 15 a 25 ans ; agencements interieurs 10 a 15 ans ; mobilier 5 a 10 ans ; electromenager 5 a 7 ans ; terrain non amortissable. Ce tableau est indicatif : la duree doit refleter la duree reelle d'utilisation du composant.">?</span></label>
            <input type="number" name="duree_annees" min="0" max="99"
                   id="duree" placeholder="0" onchange="majAmortissable(this.value)"></div>
          <div><label class="field">Date de mise en service</label>
            <input type="date" name="date_mise_service"></div>
          <div><label class="field">Réf. pièce <span class="opt">(optionnel)</span></label>
            <input name="code_immo" placeholder="MODYDW"></div>
        </div>
        <div class="mt">
          <label style="display:flex;align-items:center;gap:8px;cursor:pointer">
            <input type="checkbox" name="sans_ecriture" value="1">
            <span>Ne pas générer l'écriture d'acquisition
              <span class="opt">(reprise d'un historique déjà porté par les
              à-nouveaux)</span></span>
          </label>
        </div>
        <button type="submit" class="btn btn-primary mt">Ajouter le composant</button>
      </form>
      {% endif %}
    </div>
  </div>

</div>
{% endif %}

<script>
const amortMap = {{ amort | tojson }};
function majAmort(num) {
  // pas de champ visible pour compte_amort : géré côté serveur
}
function majAmortissable(v) {
  // futur : masquer/afficher selon durée
}
</script>
"""


PAGE_CLOTURE = """
<div class="card" style="border-left:4px solid #2e7d32;background:#f4faf4">
  <div class="card-body" style="padding:12px 16px">
    <b>Clôturer n'est pas irréversible :</b> une sauvegarde de votre dossier
    est prise automatiquement juste avant, et se restaure en un clic depuis
    la page <a href="/dossiers">Dossiers</a> (section Sauvegardes).
  </div>
</div>
{% for ex in exercices %}
<div class="card">
  <div class="card-header {{ 'red' if ex['statut']=='ouvert' else '' }}">
    Exercice {{ ex['annee'] }} —
    <span class="badge {{ 'badge-ok' if ex['statut']=='ouvert' else 'badge-clos' }}">
      {{ ex['statut'] }}</span>
  </div>
  <div class="card-body">

    {% if ex['statut'] == 'ouvert' %}

    <!-- KPI avant clôture -->
    <div class="kpi-row">
      <div class="kpi">
        <div class="kpi-label">Produits</div>
        <div class="kpi-val pos">{{ '%.2f'|format(ag[ex['annee']]['produits'])|replace('.',',') }} €</div>
      </div>
      <div class="kpi">
        <div class="kpi-label">Charges (hors DAA)</div>
        <div class="kpi-val neg">{{ '%.2f'|format(ag[ex['annee']]['charges_hors_daa'])|replace('.',',') }} €</div>
      </div>
      <div class="kpi">
        <div class="kpi-label">Résultat comptable provisoire<br><small style="color:#999;font-weight:400">(hors dotation non encore générée)</small></div>
        {% set rc = ag[ex['annee']]['resultat_comptable'] %}
        <div class="kpi-val {{ 'pos' if rc >= 0 else 'neg' }}">{{ '%.2f'|format(rc)|replace('.',',') }} €</div>
      </div>
    </div>

    <!-- Anomalies -->
    {% if anos[ex['annee']] %}
    <h2 class="section">Observations avant clôture</h2>
    <table>
      <thead><tr><th>Niveau</th><th>Code</th><th>Message</th></tr></thead>
      <tbody>
        {% for a in anos[ex['annee']] %}
        <tr>
          <td><span class="badge {{ 'badge-err' if a.niveau=='BLOQUANT' else 'badge-warn' if a.niveau=='AVERTISSEMENT' else '' }}">{{ a.niveau }}</span></td>
          <td class="muted">{{ a.code }}</td>
          <td>{{ a.message }}</td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
    {% else %}
    <p style="color:#155724;font-size:13px;margin-bottom:16px">
      ✓ Aucune anomalie détectée — clôture possible.
    </p>
    {% endif %}

    {% set a_bloquantes = anos[ex['annee']] | selectattr('niveau','equalto','BLOQUANT') | list %}
    <form method="post" action="/cloturer" style="margin-top:16px">
      <input type="hidden" name="annee" value="{{ ex['annee'] }}">
      <label style="font-size:13px;display:flex;align-items:center;gap:8px;margin-bottom:12px">
        <input type="number" name="retraitements" step="0.01" value="0"
               style="width:120px"> €
        <span style="color:#555">Autres retraitements fiscaux
          <span style="color:#999;font-weight:400">— laissez 0 dans la
          quasi-totalité des cas</span>
          <span class="aide" data-aide="ATTENTION AU DOUBLE RETRAITEMENT. Le fonds de travaux ALUR est déjà réintégré AUTOMATIQUEMENT par le logiciel, à partir de vos écritures de ventilation d'appel de charges : le saisir ici le compterait DEUX FOIS et gonflerait votre résultat imposable. Cette case ne sert qu'à un retraitement que le logiciel ne connaît pas — un redressement demandé par votre comptable, par exemple. Un montant POSITIF augmente le résultat fiscal (réintégration), un montant négatif le diminue (déduction). En cas de doute, laissez 0 : la page Liasse vous montrera le détail des retraitements déjà appliqués.">?</span></span>
      </label>
      {% if a_bloquantes %}
      <label style="font-size:13px;display:flex;align-items:center;gap:8px;margin-bottom:12px">
        <input type="checkbox" name="forcer" value="1">
        Forcer la clôture malgré les anomalies bloquantes
      </label>
      {% endif %}
      <button type="submit" class="btn btn-danger">Clôturer l'exercice {{ ex['annee'] }}</button>
    </form>

    {% else %}
    <!-- Exercice déjà clos -->
    <div class="kpi-row">
      <div class="kpi">
        <div class="kpi-label">Résultat comptable</div>
        {% set rc = ex['resultat_comptable'] or 0 %}
        <div class="kpi-val {{ 'pos' if rc >= 0 else 'neg' }}">{{ '%.2f'|format(rc)|replace('.',',') }} €</div>
      </div>
      <div class="kpi">
        <div class="kpi-label">Résultat fiscal</div>
        {% set rf = ex['resultat_fiscal'] or 0 %}
        <div class="kpi-val {{ 'pos' if rf >= 0 else 'neg' }}">{{ '%.2f'|format(rf)|replace('.',',') }} €</div>
      </div>
    </div>
    <p style="color:#555;font-size:13px">Cet exercice est clôturé et ne peut plus être modifié.</p>
    {% endif %}

  </div>
</div>
{% endfor %}
"""


PAGE_EX_NOUVEAU = """
<div class="card"><div class="card-body">
  <h2>Reprendre PLUSIEURS exercices depuis leurs FEC</h2>
  <p>Sélectionnez tous les fichiers d'un coup — l'ordre n'a pas
  d'importance, il est déduit des dates contenues dans chaque fichier.
  <b>Trois exercices valent bien mieux qu'un</b> : ils permettent des
  contrôles qu'un fichier isolé rend impossibles.</p>
  <ul class="muted" style="margin:6px 0 12px 18px">
    <li><b>Jonction des bilans</b> — le solde de clôture de chaque année
      doit se retrouver à l'ouverture de la suivante. Un écart signale une
      écriture ajoutée après coup, ou un fichier qui n'est pas la version
      définitive : c'est le défaut de migration le plus fréquent, et le
      plus silencieux.</li>
    <li><b>Amortissements</b> — avec plusieurs années de dotations
      réelles, le logiciel confronte son propre plan à celui de votre
      ancien prestataire. Un écart durable fausserait toutes vos liasses
      à venir.</li>
    <li><b>Continuité</b> — année manquante, exercice en double.</li>
  </ul>
  <form method="post" action="/exercice/analyser-fec"
        enctype="multipart/form-data"
        style="display:flex;gap:10px;align-items:center;flex-wrap:wrap">
    <input type="file" name="fecs" accept=".txt,.tsv" multiple required>
    <button type="submit">Analyser avant de reprendre</button>
  </form>
  <p class="hint">Rien n'est écrit à cette étape : l'analyse vous montre ce
  qu'elle a compris et ce qu'elle a trouvé, et vous décidez ensuite.</p>
</div></div>

{% if analyse %}
<div class="card"><div class="card-body">
  <h2 style="margin-top:0">Analyse des fichiers</h2>
  <table>
    <thead><tr><th>Exercice</th><th>Fichier</th><th class="num">Dotations</th>
      <th>Observations</th></tr></thead>
    <tbody>
    {% for f in analyse.fichiers %}
      <tr><td><b>{{ f.annee or '?' }}</b></td>
        <td class="muted">{{ f.nom }}</td>
        <td class="num">{{ '%.2f'|format(f.dotations) }} €</td>
        <td>{% if f.erreurs %}<span style="color:#c5221f">{{ f.erreurs|join(' ') }}</span>
            {% else %}<span class="badge badge-ok">lisible</span>{% endif %}</td></tr>
    {% endfor %}
    </tbody>
  </table>

  {% for o in analyse.observations %}
  <p style="margin:8px 0;padding:8px 12px;border-left:4px solid
     {{ '#188038' if o.type == 'ok' else '#c5221f' if o.type == 'ecart' else '#e8710a' }};
     background:{{ '#f2faf5' if o.type == 'ok' else '#fdf3f2' if o.type == 'ecart' else '#fff8ee' }}">
     {{ o.message }}</p>
  {% endfor %}

  {% if analyse.reprenables %}
  <form method="post" action="/exercice/reprendre-fec-multi">
    <input type="hidden" name="jeton" value="{{ analyse.jeton }}">
    <p><button type="submit">Reprendre {{ analyse.reprenables }} exercice(s),
      du plus ancien au plus récent</button></p>
  </form>
  {% else %}
  <p class="muted">Aucun exercice reprenable : corrigez les fichiers
  signalés ci-dessus.</p>
  {% endif %}
</div></div>
{% endif %}

<div class="card"><div class="card-body">
  <h2>Reprendre un seul exercice</h2>
  <p class="muted">Vous arrivez d'un autre logiciel ou d'un prestataire
  (prestataire de comptabilité LMNP) ? Téléversez le FEC d'un exercice :
  il est rejoué écriture par
  écriture, à numérotation identique, dans un exercice créé pour l'occasion.
  Les journaux et comptes absents du plan sont créés depuis le fichier.</p>
  <form method="post" action="/exercice/reprendre-fec"
        enctype="multipart/form-data"
        style="display:flex;gap:10px;align-items:center">
    <label class="field" style="margin:0">Année</label>
    <input type="number" name="annee" min="2000" max="2099" required
           style="width:90px">
    <input type="file" name="fec" accept=".txt,.tsv" required>
    <button type="submit">Reprendre cet exercice</button>
  </form>
</div></div>

{% if veille_due %}
<div class="card" style="border-left:4px solid #d68910;background:#fdf9f0">
  <div class="card-body">
    <h2 style="margin-top:0">Avant d'ouvrir un exercice : votre veille fiscale</h2>
    <p>Ce logiciel applique les règles <b>telles qu'elles y sont enregistrées</b> :
    il ne se met pas à jour tout seul. Une loi de finances par an peut changer
    un seuil, une durée de report ou le traitement d'une cession.
    {% if derniere_veille %}Dernière veille déclarée : {{ derniere_veille }}.
    {% else %}Aucune veille n'a encore été déclarée.{% endif %}</p>
    <p><a href="/veille"><b>Ouvrir la page Veille fiscale</b></a> — corpus des
    textes qui régissent le LMNP et question type à poser à une IA.</p>
  </div>
</div>
{% endif %}
<!-- Liste des exercices existants -->
<div class="card">
  <div class="card-header">Exercices enregistrés</div>
  <div class="card-body" style="padding:0">
    {% if exercices %}
    <table>
      <thead>
        <tr><th>Année</th><th>Début</th><th>Fin</th><th>Statut</th>
            <th style="text-align:right">Résultat comptable</th>
            <th style="text-align:right">Résultat fiscal</th></tr>
      </thead>
      <tbody>
        {% for ex in exercices %}
        <tr>
          <td><strong>{{ ex['annee'] }}</strong></td>
          <td>{{ ex['date_debut'] }}</td>
          <td>{{ ex['date_fin'] }}</td>
          <td><span class="badge {{ 'badge-ok' if ex['statut']=='ouvert' else 'badge-clos' }}">
            {{ ex['statut'] }}</span></td>
          {% if ex['resultat_comptable'] is not none %}
            {% set rc = ex['resultat_comptable'] %}
            <td class="right {{ 'green' if rc >= 0 else 'red' }}">{{ '%.2f'|format(rc)|replace('.',',') }} €</td>
          {% else %}<td class="muted right">—</td>{% endif %}
          {% if ex['resultat_fiscal'] is not none %}
            {% set rf = ex['resultat_fiscal'] %}
            <td class="right {{ 'green' if rf >= 0 else 'red' }}">{{ '%.2f'|format(rf)|replace('.',',') }} €</td>
          {% else %}<td class="muted right">—</td>{% endif %}
        </tr>
        {% endfor %}
      </tbody>
    </table>
    {% else %}
    <p class="empty">Aucun exercice enregistré.</p>
    {% endif %}
  </div>
</div>

<!-- Formulaire -->
<div class="card" style="max-width:480px">
  <div class="card-header green">Ouvrir un nouvel exercice</div>
  <div class="card-body">
    {% if prev_ouvert %}
    <div class="flash flash-warn" style="margin-bottom:16px">
      L'exercice {{ prev_ouvert }} est encore ouvert. Pensez à le clôturer avant d'utiliser le nouvel exercice.
    </div>
    {% endif %}
    <form method="post" action="/exercice/ouvrir">
      <div style="display:grid;gap:14px">
        <div>
          <label class="field">Année</label>
          <input type="number" name="annee" value="{{ annee_suggere }}"
                 min="2000" max="2099" required>
        </div>
        <div>
          <label class="field">Date de début</label>
          <input type="date" name="date_debut" value="{{ annee_suggere }}-01-01" required>
        </div>
        <div>
          <label class="field">Date de fin</label>
          <input type="date" name="date_fin" value="{{ annee_suggere }}-12-31" required>
        </div>
        <div>
          <label style="display:flex;align-items:center;gap:8px;cursor:pointer">
            <input type="checkbox" name="reprise" value="1"
                   {{ 'checked' if reprise_possible else 'disabled' }}>
            <span>Reprendre les à-nouveaux de l'exercice précédent
              {% if reprise_possible %}
                <span class="muted">(bilan de clôture {{ annee_suggere - 1 }} +
                affectation du résultat, générés automatiquement)</span>
              {% else %}
                <span class="muted">(indisponible : l'exercice précédent est
                absent ou non clôturé)</span>
              {% endif %}
            </span>
          </label>
        </div>
      </div>
      <button type="submit" class="btn btn-success mt">Ouvrir l'exercice</button>
    </form>
  </div>
</div>
"""


PAGE_LIASSE = """
<style>
.liasse table { width:100%; border-collapse:collapse; font-size:13px }
.liasse th, .liasse td { padding:6px 10px; border-bottom:1px solid #e4e7ec }
.liasse th { text-align:left; background:#f7f8fa; font-weight:600 }
.liasse td.num, .liasse th.num { text-align:right; font-variant-numeric:tabular-nums }
.liasse .case { color:#8a93a3; font-size:11px; margin-left:6px }
.liasse .tot td { font-weight:700; border-top:2px solid #1e3a5f }
@media print {
  header, .no-print, .flash { display:none !important }
  body { background:#fff } main { max-width:none; padding:0 }
  .card { box-shadow:none; border:1px solid #ccc; page-break-inside:avoid }
}
</style>

<div class="liasse">
<div class="no-print" style="text-align:right;margin-bottom:12px">
  <a class="btn" href="/liasse.pdf?annee={{ L.annee }}"
     style="text-decoration:none">&#128196; Télécharger la liasse en PDF</a>
</div>
{% if L.provisoire %}
<div class="flash flash-warn">Exercice {{ L.annee }} non clôturé — chiffres
<strong>provisoires</strong> (la dotation aux amortissements et la mécanique
39 C / déficits ne sont figées qu'à la clôture).</div>
{% endif %}

<div class="card">
  <div class="card-header">Liasse fiscale — Année fiscale {{ L.annee }}
    <button class="btn no-print" style="float:right"
            onclick="window.print()">Imprimer / PDF</button>
  </div>
  <div class="card-body">
    {% if L.exploitant %}
    <p><strong>{{ L.exploitant.nom }}</strong>
       {% if L.exploitant.adresse %}— {{ L.exploitant.adresse }}{% endif %}
       {% if L.exploitant.siren %}— SIREN {{ L.exploitant.siren }}{% endif %}
       — Location Meublée (LMNP, réel simplifié)</p>
    {% endif %}
    <table style="margin-top:10px">
      <tr><th>Chiffre d'affaires HT</th><th>Résultat fiscal</th>
          <th>Déficit LMNP de l'exercice</th><th>Revenu imposable</th></tr>
      <tr><td class="num">{{ eur(L.page_garde.ca_ht) }}</td>
          <td class="num">{{ eur(L.page_garde.resultat_fiscal) }}</td>
          <td class="num">{{ eur(L.page_garde.deficit_lmnp) }}</td>
          <td class="num">{{ eur(L.page_garde.revenu_imposable) }}</td></tr>
    </table>
    <table style="margin-top:14px">
      <tr><th colspan="3">Restant à imputer sur les exercices suivants</th></tr>
      <tr><th>Amort. reportés art. 39 C</th><th>Déficits LMNP</th><th>Total</th></tr>
      <tr><td class="num">{{ eur(L.page_garde.restant_39c) }}</td>
          <td class="num">{{ eur(L.page_garde.restant_deficits) }}</td>
          <td class="num"><strong>{{ eur(L.page_garde.restant_total) }}</strong></td></tr>
    </table>
  </div>
</div>

<div class="card">
  <div class="card-header {{ 'green' if L.conforme else 'red' }}">
    Contrôles de cohérence de la liasse —
    {{ 'CONFORME ✓' if L.conforme else 'ANOMALIES ✗' }}</div>
  <div class="card-body" style="padding:0"><table>
    {% for c in L.controles %}
    <tr><td style="width:60px">{{ '✓' if c.ok else '✗' }}</td>
        <td>{{ c.nom }}</td><td class="num muted">{{ c.detail }}</td></tr>
    {% endfor %}
  </table></div>
</div>

<div class="card">
  <div class="card-header">N° 2031-SD — Récapitulation & BIC non professionnels</div>
  <div class="card-body" style="padding:0"><table>
    <tr><td>1. Résultat fiscal <span class="case">(liasse, hors LMNP non pro.)</span></td>
        <td class="num">{{ eur(L.f2031.resultat_fiscal_1) }}</td></tr>
    <tr><td>7a. BIC non professionnels — BÉNÉFICE
        <span class="case">2031 bis, cadre I « Autres locations meublées non prof. »</span></td>
        <td class="num">{{ eur(L.f2031.bic_non_pro_7a_benefice) if
            L.f2031.bic_non_pro_7a_benefice is not none else '—' }}</td></tr>
    <tr><td>7b. BIC non professionnels — DÉFICIT</td>
        <td class="num">{{ eur(L.f2031.bic_non_pro_7b_deficit) if
            L.f2031.bic_non_pro_7b_deficit is not none else '—' }}</td></tr>
  </table></div>
</div>

<div class="card">
  <div class="card-header">N° 2033-A — Bilan simplifié</div>
  <div class="card-body" style="padding:0"><table>
    <tr><th>ACTIF</th><th class="num">Brut</th>
        <th class="num">Amort.</th><th class="num">Net</th></tr>
    <tr><td>Immobilisations corporelles <span class="case">028 / 030</span></td>
        <td class="num">{{ eur(L.f2033a.immo_corporelles_brut_028) }}</td>
        <td class="num">{{ eur(L.f2033a.amortissements_030) }}</td>
        <td class="num">{{ eur(L.f2033a.immo_corporelles_net) }}</td></tr>
    <tr class="tot"><td>Total général <span class="case">110 / 112</span></td>
        <td class="num">{{ eur(L.f2033a.total_actif_110) }}</td>
        <td class="num">{{ eur(L.f2033a.amortissements_030) }}</td>
        <td class="num">{{ eur(L.f2033a.immo_corporelles_net) }}</td></tr>
    <tr><th colspan="3">PASSIF</th><th></th></tr>
    <tr><td colspan="3">Capital individuel <span class="case">120</span></td>
        <td class="num">{{ eur(L.f2033a.capital_individuel_120) }}</td></tr>
    <tr><td colspan="3">Résultat de l'exercice <span class="case">136</span></td>
        <td class="num">{{ eur(L.f2033a.resultat_exercice_136) }}</td></tr>
    <tr class="tot"><td colspan="3">Total général <span class="case">142 / 180</span></td>
        <td class="num">{{ eur(L.f2033a.total_passif_180) }}</td></tr>
  </table></div>
</div>

{% if L.projection_cloture and L.projection_cloture.dotation_previsionnelle %}
<div class="card" style="border-left:4px solid #1a73e8;background:#f5f9ff">
  <div class="card-body">
    <h2 style="margin-top:0">Projection — si l'exercice était clôturé aujourd'hui</h2>
    <p class="muted">Les tableaux ci-dessous ne portent que les écritures
    enregistrées. La dotation aux amortissements de l'exercice n'est
    comptabilisée qu'à la clôture : ces chiffres-là l'anticipent d'après le
    plan d'amortissement. C'est aussi pourquoi le tableau 2033-C peut
    afficher une dotation que la 2033-B ne voit pas encore.</p>
    <table>
      <tr><td>Dotation aux amortissements de l'exercice</td>
          <td class="num">{{ eur(L.projection_cloture.dotation_previsionnelle) }}</td></tr>
      <tr><td>Résultat comptable projeté</td>
          <td class="num">{{ eur(L.projection_cloture.resultat_comptable_projete) }}</td></tr>
      <tr><td>Amortissements reportés (art. 39 C) projetés</td>
          <td class="num">{{ eur(L.projection_cloture.report_39c_projete) }}</td></tr>
      <tr><td><b>Résultat fiscal projeté</b></td>
          <td class="num"><b>{{ eur(L.projection_cloture.resultat_fiscal_projete) }}</b></td></tr>
    </table>
  </div>
</div>
{% endif %}

<div class="card">
  <div class="card-header">N° 2033-B — Compte de résultat simplifié & résultat fiscal</div>
  <div class="card-body" style="padding:0"><table>
    <tr><td>Production vendue — services <span class="case">218</span></td>
        <td class="num">{{ eur(L.f2033b.produits_218) }}</td></tr>
    <tr><td>Total des produits d'exploitation <span class="case">232</span></td>
        <td class="num">{{ eur(L.f2033b.total_produits_232) }}</td></tr>
    <tr><td>Autres charges externes <span class="case">242</span></td>
        <td class="num">{{ eur(L.f2033b.charges_externes_242) }}</td></tr>
    <tr><td>Impôts, taxes et versements assimilés <span class="case">244
        (dont CFE {{ eur(L.f2033b.dont_cfe_243) }} — 243)</span></td>
        <td class="num">{{ eur(L.f2033b.impots_244) }}</td></tr>
    <tr><td>Dotations aux amortissements <span class="case">254</span></td>
        <td class="num">{{ eur(L.f2033b.dotations_254) }}</td></tr>
    <tr><td>Total des charges d'exploitation <span class="case">264</span></td>
        <td class="num">{{ eur(L.f2033b.total_charges_264) }}</td></tr>
    <tr><td>Charges financières (intérêts d'emprunt) <span class="case">294</span></td>
        <td class="num">{{ eur(L.f2033b.charges_financieres_294) }}</td></tr>
    <tr class="tot"><td>Bénéfice ou perte (résultat comptable)
        <span class="case">270 / 310 / 312-314</span></td>
        <td class="num">{{ eur(L.f2033b.benefice_ou_perte_310) }}</td></tr>
    <tr><td>Réintégrations — amortissements excédentaires (art. 39 C)
        <span class="case">318</span></td>
        <td class="num">{{ eur(L.f2033b.reintegration_amort_318) }}</td></tr>
    <tr><td>Réintégrations — divers <span class="case">330</span>
        {% for lib, m in L.f2033b.reintegrations_detail %}
          <div class="case">· {{ lib }} : {{ eur(m) }}</div>{% endfor %}</td>
        <td class="num">{{ eur(L.f2033b.reintegration_divers_330) }}</td></tr>
    <tr><td>Déductions <span class="case">350</span>
        {% for lib, m in L.f2033b.deductions_detail %}
          <div class="case">· {{ lib }} : {{ eur(m) }}</div>{% endfor %}</td>
        <td class="num">{{ eur(L.f2033b.deductions_350) }}</td></tr>
    <tr class="tot"><td>Résultat fiscal après imputation
        <span class="case">352 / 370 — le résultat LMNP non professionnel est
        déclaré au cadre I de la 2031 bis</span></td>
        <td class="num">{{ eur(L.f2033b.resultat_fiscal_370) }}</td></tr>
  </table></div>
</div>

<div class="card">
  <div class="card-header">N° 2033-C — Immobilisations & amortissements</div>
  <div class="card-body" style="padding:0"><table>
    <tr><th>Rubrique</th><th class="num">Brut début</th>
        <th class="num">Augment.</th><th class="num">Dimin.</th>
        <th class="num">Brut fin</th>
        <th class="num">Amort. début</th><th class="num">Dotation</th>
        <th class="num">Amort. dimin.</th>
        <th class="num">Amort. fin</th></tr>
    {% for r in L.f2033c.rubriques %}
    <tr><td>{{ r.libelle }} <span class="case">{{ r.case_immo }} /
        {{ r.case_amort }}</span></td>
        <td class="num">{{ eur(r.brut_debut) }}</td>
        <td class="num">{{ eur(r.augmentations) }}</td>
        <td class="num">{{ eur(r.diminutions) }}</td>
        <td class="num">{{ eur(r.brut_fin) }}</td>
        <td class="num">{{ eur(r.amort_debut) }}</td>
        <td class="num">{{ eur(r.dotation) }}</td>
        <td class="num">{{ eur(r.amort_diminutions) }}</td>
        <td class="num">{{ eur(r.amort_fin) }}</td></tr>
    {% endfor %}
    <tr class="tot"><td>TOTAL <span class="case">490-496 / 570-576</span></td>
        <td class="num">{{ eur(L.f2033c.totaux.brut_debut) }}</td>
        <td class="num">{{ eur(L.f2033c.totaux.augmentations) }}</td>
        <td class="num">{{ eur(L.f2033c.totaux.diminutions) }}</td>
        <td class="num">{{ eur(L.f2033c.totaux.brut_fin) }}</td>
        <td class="num">{{ eur(L.f2033c.totaux.amort_debut) }}</td>
        <td class="num">{{ eur(L.f2033c.totaux.dotation) }}</td>
        <td class="num">{{ eur(L.f2033c.totaux.amort_diminutions) }}</td>
        <td class="num">{{ eur(L.f2033c.totaux.amort_fin) }}</td></tr>
  </table>
  <table style="margin-top:6px">
    <tr><th>Détail par composant</th><th class="num">Valeur brute</th>
        <th class="num">Durée</th><th class="num">Dotation</th>
        <th class="num">Cumul fin</th><th class="num">VNC fin</th></tr>
    {% for d in L.f2033c.detail_composants %}
    <tr><td>{{ d.libelle }}</td>
        <td class="num">{{ eur(d.valeur_brute) }}</td>
        <td class="num">{{ d.duree or '—' }}</td>
        <td class="num">{{ eur(d.dotation) }}</td>
        <td class="num">{{ eur(d.cumul_fin) }}</td>
        <td class="num">{{ eur(d.vnc_fin) }}</td></tr>
    {% endfor %}
  </table></div>
</div>

<div class="card">
  <div class="card-header">Suivi des reports — art. 39 C (SUIV39C) & déficits LMNP</div>
  <div class="card-body" style="padding:0"><table>
    <tr><th>Article 39 C</th><th class="num">Stock ouverture</th>
        <th class="num">Report de l'année</th>
        <th class="num">Utilisation</th><th class="num">Stock clôture</th></tr>
    <tr><td>Amortissements dont la déduction est écartée</td>
        <td class="num">{{ eur(L.reports.suivi_39c.stock_ouverture) }}</td>
        <td class="num">{{ eur(L.reports.suivi_39c.report_annee) }}</td>
        <td class="num">{{ eur(L.reports.suivi_39c.utilisation_annee) }}</td>
        <td class="num">{{ eur(L.reports.suivi_39c.stock_cloture) }}</td></tr>
    {% if L.reports.sortie_39c %}
    <tr><td colspan="4" style="color:#c5221f">dont <b>perdu à la cession
      d'un bien</b>
      <span class="aide" data-aide-etat="anomalie" data-aide="Les amortissements reportés au titre de l'article 39 C restent rattachés au bien qui les a produits. Quand ce bien sort du patrimoine, le stock qui lui restait ne peut plus être imputé : il est définitivement perdu. Ce montant n'a donc PAS été déduit de votre résultat — c'est lui qui explique la baisse du stock.">?</span></td>
      <td class="num" style="color:#c5221f">−{{ eur(L.reports.sortie_39c) }}</td></tr>
    {% endif %}
  </table>
  <table style="margin-top:6px">
    <tr><th>Déficits LMNP — millésime</th><th class="num">Montant initial</th>
        <th class="num">Solde restant</th><th class="num">Péremption</th></tr>
    {% for d in L.reports.deficits %}
    <tr><td>{{ d.annee_origine }}</td>
        <td class="num">{{ eur(d.montant_initial) }}</td>
        <td class="num">{{ eur(d.solde) }}</td>
        <td class="num">{{ d.annee_expiration }}{% if d.perime %} <b style="color:#c5221f">— périmé</b>{% endif %}</td></tr>
    {% else %}
    <tr><td colspan="4" class="muted">Aucun déficit LMNP en report.</td></tr>
    {% endfor %}
    <tr class="tot"><td>Total déficits reportables</td><td></td>
        <td class="num">{{ eur(L.reports.total_deficits) }}</td><td></td></tr>
  </table></div>
</div>

<div class="card">
  <div class="card-header green">Aide au report — déclaration 2042C-PRO</div>
  <div class="card-body" style="padding:0"><table>
    <tr><th>Case</th><th>Intitulé</th><th class="num">Montant (arrondi €)</th></tr>
    {% if L.aide_2042c.case_5NA %}
    <tr><td><strong>5NA</strong></td><td>Revenus imposables — régime réel</td>
        <td class="num">{{ L.aide_2042c.case_5NA }}</td></tr>{% endif %}
    {% if L.aide_2042c.case_5NY %}
    <tr><td><strong>5NY</strong></td><td>Déficit de l'exercice — cas général</td>
        <td class="num">{{ L.aide_2042c.case_5NY }}</td></tr>{% endif %}
    {% for c in L.aide_2042c.cases_deficits_anterieurs %}
    <tr><td><strong>{{ c.case }}</strong></td>
        <td>Déficit antérieur non encore déduit — millésime {{ c.annee_origine }}</td>
        <td class="num">{{ c.montant }}</td></tr>
    {% endfor %}
  </table>
  <p class="muted" style="padding:10px 12px">{{ L.aide_2042c.note }}</p></div>
</div>

<div class="card no-print">
  <div class="card-header amber">Télétransmettre cette liasse (obligation légale)</div>
  <div class="card-body">
    <p style="margin-bottom:10px"><strong>Ce logiciel ne télétransmet pas
    (encore) lui-même</strong> : il produit la liasse complète, case par case,
    que vous transmettez ensuite par l'une des deux voies légales. Le dépôt
    papier n'est plus admis (art. 1649 quater B quater CGI — pénalité 0,2 %,
    minimum 60 €).</p>
    <p style="margin-bottom:10px"><strong>1. EFI — saisie en ligne, gratuit
    (recommandé au réel simplifié).</strong> Espace <em>professionnel</em> sur
    impots.gouv.fr → adhérer une fois au service « Déclarer › Résultats » →
    recopier les cases 2031 / 2033-A / B / C ci-dessus (formulaire
    pré-renseigné, totaux automatiques). Délai : 2ᵉ jour ouvré suivant le
    1ᵉʳ mai + 15 jours de tolérance télédéclaration.</p>
    <p style="margin-bottom:10px"><strong>2. EDI-TDFC — via un partenaire
    habilité DGFiP.</strong> La voie qu'empruntent les prestataires de
    comptabilité LMNP (le « N° Interchange » figure sur les liasses qu'ils
    produisent) : expert-comptable ou portail de saisie en ligne à bas coût
    (liste officielle sur impots.gouv.fr).</p>
    <p style="margin-bottom:6px"><strong>Sources officielles :</strong></p>
    <ul style="margin:0 0 10px 20px;line-height:1.7">
      <li><a href="https://bofip.impots.gouv.fr/bofip/7690-PGP.html/identifiant=BOI-BIC-DECLA-30-60-20-20190605"
        target="_blank">BOFiP BOI-BIC-DECLA-30-60-20</a> — présentation de
        l'EFI : déclaration de résultat BIC/RSI en ligne, gratuite, depuis
        l'espace professionnel ;</li>
      <li><a href="https://www.impots.gouv.fr/professionnel/teleprocedures-efi-ou-edi"
        target="_blank">impots.gouv.fr — Téléprocédures EFI ou EDI</a> —
        création de l'espace, adhésion au service « Déclarer le résultat »
        (2031 au RSI) ;</li>
      <li><a href="https://www.impots.gouv.fr/professionnel/obligations-de-teleprocedures-0"
        target="_blank">impots.gouv.fr — Obligations de téléprocédures</a> —
        tableau des obligations et solutions TDFC avec saisie en ligne ;</li>
      <li><a href="https://entreprendre.service-public.gouv.fr/vosdroits/F23543"
        target="_blank">Service-Public F23543</a> — les deux modes EFI/EDI ;</li>
      <li><a href="https://entreprendre.service-public.gouv.fr/vosdroits/R14668"
        target="_blank">Service-Public R14668</a> — liste des démarches EFI,
        dont la « déclaration de résultats des entrepreneurs individuels BIC
        au régime simplifié (formulaire 2031) ».</li>
    </ul>
    <p>N'oubliez pas ensuite le report sur la <strong>2042C-PRO</strong> du
    foyer — dans votre espace <em>particulier</em>, cases pré-calculées
    ci-dessus.</p>
  </div>
</div>

<p class="muted no-print" style="margin:8px 0 24px">
⚠️ Liasse générée automatiquement sur les modèles disponibles à la date de
version du logiciel — peut ne pas correspondre aux derniers modèles en date.
À faire valider par un expert-comptable avant tout dépôt (télétransmission
EDI-TDFC non incluse).</p>
</div>
"""


PAGE_REGLEMENTATION = """
<div class="card">
  <div class="card-header">⚖️ Règles fiscales versionnées</div>
  <div class="card-body">
    <p style="margin-bottom:12px">Aucun seuil ni durée n'est figé dans le code :
    chaque règle est <strong>datée</strong>. Quand une loi de finances change une
    valeur, enregistrez la nouvelle version avec sa <strong>date d'effet</strong> —
    les exercices passés restent calculés avec les règles de leur millésime.</p>
    <table style="width:100%;border-collapse:collapse;font-size:13px">
      <tr style="background:#f7f8fa"><th style="text-align:left;padding:6px 10px">Règle</th>
          <th style="text-align:right;padding:6px 10px">Valeur</th>
          <th style="padding:6px 10px">En vigueur</th>
          <th style="text-align:left;padding:6px 10px">Ce que la règle change</th>
          <th style="text-align:left;padding:6px 10px">Référence légale</th></tr>
      {% for r in regles %}
      <tr style="border-bottom:1px solid #e4e7ec{{ ';color:#8a93a3' if r.date_fin else '' }}">
        <td style="padding:6px 10px">{{ r.libelle }}
            <span class="opt">({{ r.cle }})</span></td>
        <td style="padding:6px 10px;text-align:right">{{ '%g'|format(r.valeur) }}</td>
        <td style="padding:6px 10px;white-space:nowrap">{{ r.date_debut }} →
            {{ r.date_fin or 'en vigueur' }}</td>
        <td style="padding:6px 10px"><strong>{{ r.impact_module }}</strong>
            <div class="opt">{{ r.impact_effet }}</div></td>
        <td style="padding:6px 10px">{{ r.reference }}
            {% if r.commentaire %}<div class="opt">{{ r.commentaire }}</div>{% endif %}</td>
      </tr>
      {% endfor %}
    </table>

    <form method="post" action="/reglementation/regle" class="mt"
          style="display:grid;grid-template-columns:2fr 1fr 1fr 2fr auto;gap:10px;align-items:end">
      <div><label class="field">Règle</label>
        <select name="cle" required>
          {% for cle, lib in libelles_regles %}
          <option value="{{ cle }}">{{ lib }}</option>{% endfor %}
        </select></div>
      <div><label class="field">Nouvelle valeur</label>
        <input type="number" step="any" name="valeur" required></div>
      <div><label class="field">Date d'effet</label>
        <input type="date" name="date_debut" required></div>
      <div><label class="field">Référence légale <span class="opt">(LF, art. CGI, BOFiP)</span></label>
        <input name="reference" placeholder="ex. LF 2027, art. 12"></div>
      <button class="btn btn-success">Enregistrer la version</button>
    </form>
  </div>
</div>

<div class="card">
  <div class="card-header">Catégories d'opérations personnalisées</div>
  <div class="card-body">
    <p style="margin-bottom:12px">Une disposition future crée une nouvelle
    charge ou un nouveau produit ? Ajoutez la catégorie ici : elle apparaît
    immédiatement dans la liste déroulante de saisie, avec son compte, sa
    périodicité, et si besoin une <strong>réintégration fiscale automatique</strong>
    à la clôture.</p>
    <table style="width:100%;border-collapse:collapse;font-size:13px">
      <tr style="background:#f7f8fa"><th style="text-align:left;padding:6px 10px">Libellé</th>
          <th style="padding:6px 10px">Clé</th><th style="padding:6px 10px">Compte</th>
          <th style="padding:6px 10px">Nature</th><th style="padding:6px 10px">Périodicité</th>
          <th style="padding:6px 10px">Retraitement</th></tr>
      {% for g in persos %}
      <tr style="border-bottom:1px solid #e4e7ec">
        <td style="padding:6px 10px">{{ g.libelle }}</td>
        <td style="padding:6px 10px">{{ g.cle }}</td>
        <td style="padding:6px 10px">{{ g.compte_num }}</td>
        <td style="padding:6px 10px">{{ g.nature }}</td>
        <td style="padding:6px 10px">{{ g.periodicite }}</td>
        <td style="padding:6px 10px">{{ 'réintégration' if g.retraitement else '—' }}</td>
      </tr>
      {% else %}
      <tr><td colspan="6" class="muted" style="padding:6px 10px">Aucune catégorie
          personnalisée — les 37 gabarits standard couvrent l'existant.</td></tr>
      {% endfor %}
    </table>

    <form method="post" action="/reglementation/gabarit" class="mt"
          style="display:grid;grid-template-columns:2fr 1.5fr 1fr 1fr auto auto;gap:10px;align-items:end">
      <div><label class="field">Libellé</label>
        <input name="libelle" required placeholder="ex. Éco-contribution meublés 2028"></div>
      <div><label class="field">Compte</label>
        <select name="compte_num" required>
          {% for num, lib in comptes %}
          <option value="{{ num }}">{{ num }} — {{ lib }}</option>{% endfor %}
        </select></div>
      <div><label class="field">Nature</label>
        <select name="nature"><option value="charge">Charge</option>
          <option value="produit">Produit</option></select></div>
      <div><label class="field">Périodicité</label>
        <select name="periodicite"><option value="variable">Variable</option>
          <option value="mensuel">Mensuelle</option>
          <option value="annuel">Annuelle</option></select></div>
      <label style="display:flex;align-items:center;gap:6px;white-space:nowrap">
        <input type="checkbox" name="reintegration" value="1"> Réintégration fiscale</label>
      <button class="btn btn-success">Ajouter</button>
    </form>
  </div>
</div>

<div class="card">
  <div class="card-header">Plan de comptes — ajouter un compte</div>
  <div class="card-body">
    <form method="post" action="/reglementation/compte"
          style="display:grid;grid-template-columns:1fr 2fr 1fr auto;gap:10px;align-items:end">
      <div><label class="field">Numéro (6 chiffres)</label>
        <input name="numero" required pattern="[1-7][0-9]{5}" placeholder="637800"></div>
      <div><label class="field">Libellé</label>
        <input name="libelle" required placeholder="Nouvelle taxe secteur locatif"></div>
      <div><label class="field">Type</label>
        <select name="type"><option value="charge">Charge</option>
          <option value="produit">Produit</option><option value="actif">Actif</option>
          <option value="passif">Passif</option>
          <option value="amortissement">Amortissement</option></select></div>
      <button class="btn">Créer le compte</button>
    </form>
    <p class="muted mt">Le compte devient utilisable par les gabarits
    personnalisés et l'export FEC. Les comptes existants ne sont jamais modifiés.</p>
  </div>
</div>
"""


PAGE_SANDBOX = """
<div class="card" style="max-width:760px">
  <div class="card-header">🧪 Bac à sable — dossier d'essai jetable</div>
  <div class="card-body">
    <p style="margin-bottom:14px">
      Le bac à sable est un <strong>dossier comptable séparé</strong>
      (<code>bac_a_sable.db</code>), totalement isolé de votre comptabilité
      réelle. Vous pouvez y dérouler <strong>tout le processus</strong> :
      ouvrir un exercice du 1<sup>er</sup> janvier au 31 décembre, saisir
      librement, créer des immobilisations, lancer les contrôles, clôturer,
      exporter le FEC — puis tout effacer d'un clic.
    </p>

    {% if actif %}
      <div class="flash flash-warn" style="margin-bottom:14px">
        Vous êtes actuellement <strong>dans le bac à sable</strong>. Tous les
        menus (Saisie, Immobilisations, Clôture, Nouvel exercice) opèrent sur
        le dossier d'essai.
      </div>
      <form method="post" action="/bac-a-sable/quitter" style="display:inline">
        <button class="btn">← Revenir au dossier réel</button>
      </form>
    {% else %}
      <form method="post" action="/bac-a-sable/activer" style="display:inline">
        <button class="btn btn-success">Entrer dans le bac à sable →</button>
      </form>
    {% endif %}
  </div>
</div>

<div class="card" style="max-width:760px">
  <div class="card-header">Réinitialiser le dossier d'essai</div>
  <div class="card-body">
    <p style="margin-bottom:14px" class="muted">
      La réinitialisation efface <em>uniquement</em> <code>bac_a_sable.db</code> ;
      la comptabilité réelle n'est jamais touchée.
    </p>
    <form method="post" action="/bac-a-sable/reset" style="display:inline">
      <input type="hidden" name="mode" value="blanc">
      <button class="btn">Réinitialiser — dossier vierge (mode blanc)</button>
    </form>
    <form method="post" action="/bac-a-sable/reset" style="display:inline;margin-left:8px">
      <input type="hidden" name="mode" value="demo">
      <button class="btn">Réinitialiser — dossier d'exemple (mode démo)</button>
    </form>
  </div>
</div>

<div class="card" style="max-width:760px">
  <div class="card-header green">Audit automatique du cycle complet</div>
  <div class="card-body">
    <p style="margin-bottom:14px">
      Rejoue l'intégralité du processus sur une base jetable et vérifie chaque
      étape : ouverture, saisie 12 mois, immobilisations, contrôles
      (y compris détection d'anomalies injectées), clôture, limitation 39 C,
      déficits LMNP pluri-exercices, export et validation FEC.
    </p>
    <form method="post" action="/bac-a-sable/audit">
      <button class="btn btn-success">Lancer l'audit complet</button>
    </form>
    {% if rapport %}
    <pre style="margin-top:16px;background:#1a1a1a;color:#d8e8d8;padding:16px;
                border-radius:6px;overflow-x:auto;font-size:12.5px;
                line-height:1.55">{{ rapport }}</pre>
    {% endif %}
  </div>
</div>
"""


PAGE_ARCHIVES = """
<div class="card"><div class="card-body">
  <h2>Fichiers des écritures comptables (FEC) archivés</h2>
  <p class="muted">Un FEC est produit et horodaté à <b>chaque clôture</b>, avec
  son empreinte SHA-256 au manifeste. C'est le fichier que l'administration
  demande en cas de contrôle (art. L. 47 A-I du LPF) : conservez-en une copie
  hors de cet ordinateur.</p>
  {% if not fichiers %}
    <p>Aucune archive pour l'instant : le premier FEC sera produit à votre
    prochaine clôture.</p>
  {% else %}
  <table>
    <thead><tr><th>Fichier</th><th>Taille</th><th>Empreinte SHA-256</th>
      <th></th></tr></thead>
    <tbody>
    {% for f in fichiers %}
      <tr><td>{{ f.nom }}</td><td class="muted">{{ f.ko }} Ko</td>
        <td class="muted" style="font-family:monospace">{{ f.sha }}…</td>
        <td style="text-align:right">
          <a href="/archives/{{ f.nom }}">Télécharger</a></td></tr>
    {% endfor %}
    </tbody>
  </table>
  {% endif %}
  <p class="opt">Dossier : {{ dossier }}</p>
</div></div>
"""


PAGE_SAUVEGARDES_SECTION = """
<div class="card"><div class="card-body">
  <h2>Sauvegardes du dossier actif</h2>
  <p class="muted">Une sauvegarde automatique est faite chaque jour au
  lancement, plus une avant chaque clôture. <b>Restaurer</b> remet le dossier
  dans l'état de la sauvegarde choisie — l'état actuel est lui-même
  sauvegardé d'abord (« avant-restauration ») : l'opération est réversible.
  C'est le geste à faire après une clôture lancée par erreur ou une série de
  saisies malheureuses.</p>
  {% if not sauvegardes %}
    <p>Aucune sauvegarde pour l'instant : elles apparaîtront au prochain
    lancement du logiciel.</p>
  {% else %}
  <table>
    <thead><tr><th>Sauvegarde</th><th>Taille</th><th></th></tr></thead>
    <tbody>
    {% for s in sauvegardes[:15] %}
      <tr>
        <td>{{ s['nom'] }}</td>
        <td class="muted">{{ s['taille_ko'] }} Ko</td>
        <td style="text-align:right">
          <form method="post" action="/sauvegardes/restaurer" style="margin:0">
            <input type="hidden" name="nom" value="{{ s['nom'] }}">
            <button type="submit" class="btn-secondaire"
              data-confirmer="Restaurer « {{ s['nom'] }} » ? Le dossier reviendra à cet état. L'état actuel sera d'abord mis de côté (avant-restauration).">Restaurer</button>
          </form>
        </td>
      </tr>
    {% endfor %}
    </tbody>
  </table>
  {% endif %}
</div></div>
"""


PAGE_VERSION_TROP_RECENTE = """
<div class="card"><div class="card-body">
  <h2>Dossier plus récent que le logiciel</h2>
  <p>{{ msg }}</p>
  <!-- Une issue est INDISPENSABLE ici : chaque lien de la barre de
       navigation repasse par le garde qui a produit cette page, et le
       cookie de dossier vaut 180 jours. Sans ce bouton, le logiciel
       devenait inutilisable — pour TOUS ses dossiers — jusqu'à ce que
       l'utilisateur sache supprimer un cookie dans son navigateur. -->
  <form method="post" action="/dossiers/retour-principal">
    <button type="submit">Revenir au dossier principal</button>
  </form>
  <p class="muted" style="margin-top:14px">Pour rouvrir ce dossier,
  installez la version du logiciel qui l'a produit.</p>
</div></div>
"""

PAGE_DOSSIER_ABSENT = """
<div class="card"><div class="card-body">
  <h2>Fichier du dossier introuvable</h2>
  <p>Le dossier « <b>{{ slug }}</b> » est enregistré, mais son fichier est
  introuvable :</p>
  <p><code>{{ chemin }}</code></p>
  <p><b>Rien n'a été créé ni modifié.</b> Cette situation est le plus
  souvent temporaire : disque externe débranché, dossier synchronisé pas
  encore redescendu, partage réseau non monté. Rebranchez le support, puis
  rechargez la page.</p>
  <p class="muted">Le logiciel créait auparavant une base vierge à cette
  place : la comptabilité paraissait perdue, et le vrai fichier se
  trouvait masqué.</p>
  <form method="post" action="/dossiers/retour-principal">
    <button type="submit">Revenir au dossier principal</button>
  </form>
</div></div>
"""

PAGE_QUITTANCES = """
<div class="card">
  <div class="card-header">Locataires</div>
  <div class="card-body">
    {% if locataires %}
    <table>
      <thead><tr><th>Nom</th><th>Logement</th><th>Entrée</th><th>Sortie</th>
        <th class="num">Loyer</th><th class="num">Charges</th></tr></thead>
      <tbody>
      {% for l in locataires %}
        <tr><td><b>{{ l.nom }}</b></td><td>{{ l.bien }}</td>
          <td>{{ l.date_entree }}</td>
          <td>{{ l.date_sortie or '—' }}
            {% if not l.date_sortie %}<span class="badge badge-ok">en cours</span>{% endif %}</td>
          <td class="num">{{ '%.2f'|format(l.loyer_mensuel or 0) }} €</td>
          <td class="num">{{ '%.2f'|format(l.charges_mensuelles or 0) }} €</td></tr>
      {% endfor %}
      </tbody>
    </table>
    {% else %}
    <p class="muted">Aucun locataire enregistré.</p>
    {% endif %}

    <h2 style="font-size:1em;margin:18px 0 8px">Ajouter un locataire</h2>
    <form method="post" action="/quittances/locataire">
      <div class="grid3">
        <div><label class="field">Nom et prénom</label>
          <input name="nom" required placeholder="DUPONT Jean"></div>
        <div><label class="field">Logement</label>
          <select name="bien_id" required>
            {% for b in biens %}<option value="{{ b['id'] }}">{{ b['libelle'] }}</option>{% endfor %}
          </select></div>
        <div><label class="field">Date d'entrée</label>
          <input type="date" name="date_entree" required></div>
        <div><label class="field">Date de sortie <span class="opt">(vide si en cours)</span></label>
          <input type="date" name="date_sortie"></div>
        <div><label class="field">Loyer mensuel hors charges (€)</label>
          <input type="number" step="0.01" name="loyer_mensuel"></div>
        <div><label class="field">Provision de charges (€)</label>
          <input type="number" step="0.01" name="charges_mensuelles" value="0"></div>
      </div>
      <p><button type="submit">Ajouter</button></p>
    </form>
  </div>
</div>

<div class="card">
  <div class="card-header">Émettre une quittance</div>
  <div class="card-body">
    <p class="muted">Les montants sont lus dans vos ÉCRITURES : la quittance
    reflète la comptabilité, elle ne la double pas. Laissez les champs vides
    pour reprendre le loyer encaissé sur la période ; renseignez-les pour
    forcer un montant.</p>
    {% if locataires %}
    <form method="post" action="/quittances/emettre">
      <div class="grid3">
        <div><label class="field">Locataire</label>
          <select name="locataire_id" required>
            {% for l in locataires %}<option value="{{ l.id }}">{{ l.nom }} — {{ l.bien }}</option>{% endfor %}
          </select></div>
        <div><label class="field">Période (mois)</label>
          <input type="month" name="periode" required></div>
        <div><label class="field">Date de paiement <span class="opt">(facultatif)</span></label>
          <input type="date" name="date_paiement"></div>
        <div><label class="field">Loyer (€) <span class="opt">(vide = depuis les écritures)</span></label>
          <input type="number" step="0.01" name="loyer"></div>
        <div><label class="field">Charges (€) <span class="opt">(vide = depuis les écritures)</span></label>
          <input type="number" step="0.01" name="charges"></div>
      </div>
      <p><button type="submit">Émettre la quittance</button></p>
    </form>
    {% else %}
    <p class="muted">Enregistrez d'abord un locataire.</p>
    {% endif %}
  </div>
</div>

<div class="card">
  <div class="card-header">Quittances émises</div>
  <div class="card-body">
    <form method="get" style="margin-bottom:12px">
      <label class="field" style="display:inline">Année</label>
      <select name="an" onchange="this.form.submit()">
        <option value="">toutes</option>
        {% for a in annees_quittances %}
        <option value="{{ a }}" {{ 'selected' if a|string == an_filtre else '' }}>{{ a }}</option>
        {% endfor %}
      </select>
      <span class="muted" style="margin-left:10px">Toutes les quittances
      restent consultables et réimprimables, sans limite d'ancienneté.</span>
    </form>
    {% if quittances %}
    <table>
      <thead><tr><th>N°</th><th>Locataire</th><th>Logement</th><th>Période</th>
        <th class="num">Loyer</th><th class="num">Charges</th>
        <th class="num">Total</th><th>Émise le</th><th></th></tr></thead>
      <tbody>
      {% for q in quittances %}
        <tr><td><b>{{ '%05d'|format(q.numero) }}</b></td>
          <td>{{ q.locataire }}</td><td class="muted">{{ q.bien }}</td>
          <td>{{ q.periode }}</td>
          <td class="num">{{ '%.2f'|format(q.loyer) }} €</td>
          <td class="num">{{ '%.2f'|format(q.charges) }} €</td>
          <td class="num"><b>{{ '%.2f'|format(q.loyer + q.charges) }} €</b></td>
          <td>{{ q.date_emission }}</td>
          <td><a class="btn" href="/quittance/{{ q.id }}" target="_blank">Imprimer</a></td>
        </tr>
      {% endfor %}
      </tbody>
    </table>
    <p class="muted" style="font-size:.88em">La numérotation est continue et
    sans trou, dans une série UNIQUE partagée par tous vos logements —
    c'est ce qui la rend vérifiable. Elle suit l'ordre d'ÉMISSION, comme
    une numérotation de factures : une quittance établie aujourd'hui pour
    un mois ancien reçoit donc le numéro suivant, et non un numéro
    intercalé.</p>
    {% else %}
    <p class="muted">Aucune quittance émise.</p>
    {% endif %}
  </div>
</div>

"""

PAGE_QUITTANCE_IMPRIMABLE = """<!DOCTYPE html>
<html lang="fr"><head><meta charset="utf-8">
<title>Quittance n° {{ '%05d'|format(q.numero) }}</title>
<style>
  body { font-family: Georgia, serif; max-width: 17cm; margin: 2cm auto;
         color: #1a1a1a; line-height: 1.55; }
  h1 { font-size: 1.35em; margin: 0 0 4px; }
  .num { color: #555; margin-bottom: 26px; }
  .parties { display: flex; justify-content: space-between; gap: 30px;
             margin-bottom: 26px; }
  .bloc { font-size: .95em; }
  .bloc b { display: block; margin-bottom: 3px; }
  table { width: 100%; border-collapse: collapse; margin: 18px 0; }
  td, th { padding: 7px 10px; border-bottom: 1px solid #ddd; }
  th { text-align: left; background: #f4f4f6; }
  .droite { text-align: right; }
  .total td { font-weight: bold; border-top: 2px solid #333; border-bottom: 0; }
  .mentions { font-size: .82em; color: #555; margin-top: 30px;
              border-top: 1px solid #ddd; padding-top: 12px; }
  @media print { body { margin: 1.2cm; } .noprint { display: none; } }
</style></head><body>
<p class="noprint" style="text-align:right">
  <button onclick="window.print()">Imprimer</button></p>

{% if q.ecart_ecritures %}
<p class="noprint" style="background:#fdf3f2;border-left:4px solid #c5221f;
   padding:10px 14px;font-size:.9em">
  <b>Cette quittance ne correspond plus à vos écritures.</b><br>
  {{ q.ecart_ecritures.message }}</p>
{% endif %}

<h1>{{ q.titre_document or 'Quittance de loyer' }}</h1>
<p class="num">N° {{ '%05d'|format(q.numero) }} — {{ q.periode_lettres }}</p>

{% if q.type_document == 'recu' %}
<p style="background:#fff8ee;border-left:4px solid #e8710a;padding:10px 14px">
  <b>Paiement partiel.</b> Ce document n'est pas une quittance : il atteste
  d'un versement reçu, sans solder la période.
  {% if q.reste_du and q.reste_du > 0 %}Reste dû au titre de
  {{ q.periode_lettres }} : <b>{{ '%.2f'|format(q.reste_du) }} €</b>.{% endif %}
  Une quittance sera établie lorsque la période sera intégralement réglée
  (article 21 de la loi du 6 juillet 1989).</p>
{% endif %}

{% if q.referentiel_modifie %}
<p class="noprint" style="background:#fff8ee;border-left:4px solid #e8710a;
   padding:10px 14px;font-size:.9em">
  Depuis l'émission de ce document, {{ q.referentiel_modifie|join(' et ') }}
  a changé dans le dossier. Ce qui est imprimé ci-dessous est l'identité
  <b>figée à l'émission</b> — celle du document réellement remis.</p>
{% endif %}

<div class="parties">
  <div class="bloc"><b>Bailleur</b>
    {{ q.bailleur.nom }}<br>{{ q.bailleur.adresse or '' }}</div>
  <div class="bloc"><b>Locataire</b>
    {{ q.locataire }}<br>{{ q.bien_adresse or q.bien }}</div>
</div>

<p>Je soussigné(e) <b>{{ q.bailleur.nom }}</b>, bailleur du logement situé
<b>{{ q.bien_adresse or q.bien }}</b>, déclare avoir reçu de
<b>{{ q.locataire }}</b> la somme de
<b>{{ '%.2f'|format(q.total) }} €</b>, au titre du loyer et des charges de
la période de <b>{{ q.periode_lettres }}</b>,
{% if q.type_document == 'recu' %}à valoir sur les sommes dues pour cette
période, sans que ce versement en constitue quittance.
{% else %}et lui en donne quittance,{% endif %}
sous réserve de tous mes droits.</p>

{% if not q.bien_adresse %}
<p class="noprint" style="background:#fff8ee;border-left:4px solid #e8710a;
   padding:10px 14px;font-size:.9em">
  <b>Adresse du logement absente.</b> Le libellé interne
  « {{ q.bien }} » est imprimé à sa place : renseignez l'adresse postale du
  bien dans la page Immobilisations avant de remettre ce document.</p>
{% endif %}

<table>
  <tr><th>Désignation</th><th class="droite">Montant</th></tr>
  <tr><td>Loyer hors charges</td>
      <td class="droite">{{ '%.2f'|format(q.loyer) }} €</td></tr>
  <tr><td>Provision pour charges</td>
      <td class="droite">{{ '%.2f'|format(q.charges) }} €</td></tr>
  <tr class="total"><td>Total réglé</td>
      <td class="droite">{{ '%.2f'|format(q.total) }} €</td></tr>
</table>

<p>{% if q.date_paiement %}Paiement reçu le {{ q.date_paiement }}.{% endif %}
Fait le {{ q.date_emission }}.</p>

<p style="margin-top:38px">Signature du bailleur :</p>

<p class="mentions">
  La présente quittance annule tous les reçus qui auraient pu être établis
  précédemment pour la même période. Elle distingue le loyer des charges,
  conformément à l'article 21 de la loi n° 89-462 du 6 juillet 1989, qui
  impose au bailleur de la transmettre gratuitement au locataire qui en
  fait la demande.
</p>
</body></html>
"""

PAGE_DEMARRAGE = """
<div class="card" style="border-left:5px solid #ffd54f;background:#fffdf3">
  <div class="card-body">
    <h2 style="margin-top:0">Bienvenue — configurons votre dossier</h2>
    <p>Ce dossier est vierge. Une seule chose est nécessaire pour commencer :
    l'identité sous laquelle vous déclarez.</p>

    <form method="post" action="/immobilisations/exploitant">
      <input type="hidden" name="retour" value="saisie">
      <div class="grid3">
        <div><label class="field">Nom de l'exploitant
          <span class="aide" data-aide="Le nom sous lequel l'activité est déclarée. Pour un particulier, vos nom et prénom ; pour une société, sa dénomination. Il apparaît sur la liasse fiscale.">?</span></label>
          <input name="nom" required placeholder="NOM Prénom"></div>
        <div><label class="field">SIREN
          <span class="aide" data-aide="Les 9 chiffres attribués lors de la déclaration d'activité auprès du guichet unique de l'INPI. Il figure sur votre avis de situation SIRENE et sur vos avis de CFE.">?</span></label>
          <input name="siren" required pattern="[0-9]{9}"
                 title="9 chiffres" placeholder="123456789"></div>
        <div><label class="field">Adresse d'activité
          <span class="aide" data-aide="L'adresse déclarée pour l'activité de location meublée. Souvent celle du bien loué, ou votre domicile selon ce que vous avez déclaré.">?</span></label>
          <input name="adresse" placeholder="12 rue Exemple, 63000 Clermont-Ferrand"></div>
      </div>
      <p><button type="submit">Enregistrer et commencer</button></p>
    </form>

    <div style="background:#f0f6fb;border-left:4px solid #1a73e8;
                padding:10px 14px;margin-top:6px">
      <b>L'exercice est déjà ouvert.</b> Vous n'avez rien à créer : un
      exercice a été ouvert automatiquement à la création du dossier, et
      vous pourrez saisir dès l'étape suivante. L'onglet
      <i>Nouvel exercice</i> ne sert qu'à l'ANNÉE SUIVANTE, une fois la
      précédente clôturée — ou à reprendre un historique depuis un FEC.
    </div>

    <p class="muted" style="margin-top:14px">Ensuite : créez votre bien dans
    <i>Immobilisations</i> et ventilez son prix d'acquisition, puis saisissez
    vos loyers et vos charges. Pour voir le logiciel à l'œuvre sans rien
    risquer, le <a href="/bac-a-sable">bac à sable</a> contient une année
    complète déjà tenue.</p>
  </div>
</div>

<div class="card">
  <div class="card-header">Reprendre un historique existant</div>
  <div class="card-body">
    <p class="muted">Vous venez d'un autre logiciel ou d'un prestataire ?
    Vous pouvez rejouer un ou plusieurs exercices depuis leurs fichiers
    FEC — écriture par écriture, à numérotation identique — depuis
    l'onglet <a href="/exercice/nouveau">Nouvel exercice</a>. Commencez par
    le plus ancien.</p>
  </div>
</div>

"""

PAGE_DOSSIERS = """
<div class="card">
  <div class="card-header">📁 Dossiers comptables</div>
  <div class="card-body">
    <p style="margin-bottom:12px">Chaque dossier est une <strong>comptabilité
    indépendante</strong> (sa base, ses sauvegardes, ses archives FEC). Le
    dossier actif est indiqué dans l'en-tête ; il reste actif jusqu'à ce que
    vous en ouvriez un autre.</p>
    <table>
      <thead><tr><th>Nom</th><th>Emplacement</th>
        <th style="text-align:right">Taille</th><th></th><th></th></tr></thead>
      <tbody>
      {% for d in liste %}
      <tr>
        <td><strong>{{ d.nom }}</strong>
          {% if d.slug == actif %}<span class="badge badge-ok">actif</span>{% endif %}
          {% if not d.existe %}<span class="badge badge-clos">base absente</span>{% endif %}
        </td>
        <td class="muted" style="font-size:12px">{{ d.chemin }}</td>
        <td style="text-align:right">{{ '%.1f'|format(d.taille / 1024) }} Ko</td>
        <td>
          {% if d.slug != actif %}
          <form method="post" action="/dossiers/ouvrir" style="display:inline">
            <input type="hidden" name="slug" value="{{ d.slug }}">
            <button type="submit" class="btn">Ouvrir</button>
          </form>
          {% endif %}
        </td>
        <td>
          {% if d.slug != 'principal' %}
          <form method="post" action="/dossiers/renommer"
                style="display:flex;gap:6px">
            <input type="hidden" name="slug" value="{{ d.slug }}">
            <input type="text" name="nom" value="{{ d.nom }}" style="width:160px">
            <button type="submit" class="btn">Renommer</button>
          </form>
          {% endif %}
        </td>
      </tr>
      {% endfor %}
      </tbody>
    </table>
  </div>
</div>

<div class="card" style="max-width:480px">
  <div class="card-header green">Créer un nouveau dossier</div>
  <div class="card-body">
    <form method="post" action="/dossiers/creer">
      <label class="field">Nom du dossier</label>
      <input type="text" name="nom" placeholder="ex. Studio Nancy" required
             maxlength="60">
      <p class="muted" style="font-size:12px;margin-top:6px">Le dossier est
      créé vierge (plan de comptes et journaux installés, aucune écriture).
      Pour repartir d'une clôture existante, utilisez ensuite « Nouvel
      exercice » avec reprise d'un FEC.</p>
      <button type="submit" class="btn btn-success mt">Créer le dossier</button>
    </form>
  </div>
</div>
"""


PAGE_PENSE_BETE = """
<div class="card"><div class="card-body">
  <h2>Pense-bête — à faire manuellement</h2>
  <p class="muted">Le logiciel tient la comptabilité ; déclarer, payer et
  informer les administrations restent des gestes manuels. Rappels croisant
  le calendrier et l'état de ce dossier — dates indicatives, à vérifier sur
  impots.gouv.fr.</p>
  {% if not rappels %}
    <p>✅ Rien de particulier à signaler en ce moment.</p>
  {% endif %}
  {% for r in rappels %}
    <div class="rappel rappel-{{ r['niveau'] }}">
      <div class="rappel-titre">{{ badge[r['niveau']] }} {{ r['titre'] }}</div>
      <div class="rappel-detail">{{ r['detail'] }}</div>
    </div>
  {% endfor %}
</div></div>

<div class="card">
  <div class="card-header">Actualités réglementaires</div>
  <div class="card-body">
    <p class="muted">Faits datés, vérifiés le {{ actualites.verifie_le }}.
    Contrairement à la relecture ci-dessous, ils périment : la page
    <a href="/veille">Veille fiscale</a> sert à les remettre en question.</p>

    {% for a in actualites.faits %}
    <div style="border-left:4px solid #1a73e8;background:#f5f9ff;
                padding:12px 16px;margin-bottom:14px">
      <h2 style="margin:0 0 6px;font-size:1.02em">{{ a.titre }}</h2>
      <p style="margin:0 0 8px"><b>{{ a.resume }}</b></p>
      <p class="muted" style="white-space:pre-line;margin:0">{{ a.detail }}</p>
      {% if a.sources %}
      <p class="muted" style="font-size:.86em;margin:10px 0 0">
        <b>Sources :</b> {{ a.sources|join(' · ') }}</p>
      {% endif %}
    </div>
    {% endfor %}

    <h2 style="font-size:1em;margin:18px 0 8px">Échéances à connaître</h2>
    <table>
      <thead><tr><th>Quand</th><th>Quoi</th><th>Où</th></tr></thead>
      <tbody>
      {% for e in actualites.echeances %}
        <tr><td>{{ e.quand }}</td><td>{{ e.quoi }}</td>
            <td class="muted">{{ e.ou }}</td></tr>
      {% endfor %}
      </tbody>
    </table>
    <p class="muted" style="font-size:.86em">Les dates de dépôt sont
    publiées chaque année par l'administration et varient selon le
    département : vérifiez le calendrier de l'année en cours.</p>
  </div>
</div>

<div class="card">
  <div class="card-header">Mes notes personnelles</div>
  <div class="card-body">
    <p class="muted">Cet espace est à vous : notez ici ce que votre veille
    vous apprend, les questions à poser, les points à vérifier l'an
    prochain. Le contenu est conservé dans votre dossier — il suit vos
    sauvegardes et vos restaurations, et ne quitte jamais votre
    ordinateur.</p>
    <form method="post" action="/pense-bete/notes">
      <textarea name="notes" rows="12" style="width:100%;font-family:inherit;
                font-size:.95em;line-height:1.5"
                placeholder="Ex. : 13/08 — vérifié la plateforme agréée pour la réception des factures, inscription faite.&#10;Question au comptable : les frais de notaire de 2021 sont-ils bien reportés ?">{{ notes }}</textarea>
      <p><button type="submit">Enregistrer mes notes</button>
         <span class="muted" style="margin-left:10px">Dernier
         enregistrement conservé dans le dossier courant.</span></p>
    </form>
  </div>
</div>

<div class="card">
  <div class="card-header">Les oublis les plus fréquents — relecture avant clôture</div>
  <div class="card-body">
    <p class="muted">Ces points ne dépendent pas de votre dossier : ce sont
    les fautes que commettent le plus souvent les loueurs meublés au réel.
    Ils servent de relecture, pas de conseil personnalisé — en cas de doute
    sur l'un d'eux, la question mérite d'être posée à un professionnel.</p>
    {% for groupe in oublis %}
    <h2 style="font-size:1em;margin:18px 0 8px">{{ groupe.moment }}</h2>
    {% for p in groupe.points %}
    <details style="margin-bottom:6px">
      <summary style="cursor:pointer;font-weight:600">{{ p.titre }}</summary>
      <p class="muted" style="margin:6px 0 0 16px">{{ p.detail }}</p>
      {% if p.sources %}
      <p class="muted" style="margin:6px 0 0 16px;font-size:.86em">
        <b>Sources :</b> {{ p.sources|join(' · ') }}</p>
      {% endif %}
    </details>
    {% endfor %}
    {% endfor %}
  </div>
</div>
"""


PAGE_VEILLE = """
<div class="card"><div class="card-body">
  <h2>Veille fiscale — ce logiciel ne se met pas à jour tout seul</h2>
  <p class="muted">Les règles de calcul sont <b>datées</b> : le moteur applique
  celle qui était en vigueur pour l'exercice traité. Mais personne ne prévient
  le logiciel qu'une loi de finances a changé un seuil — c'est à vous de le
  vérifier, idéalement à chaque ouverture d'exercice.</p>
  <p>
    {% if v.derniere_veille %}Dernière veille déclarée : <b>{{ v.derniere_veille }}</b>.
    {% else %}<b>Aucune veille déclarée à ce jour.</b>{% endif %}
    {% if v.a_refaire %}<span style="color:#c0392b"> — il est temps d'en refaire une.</span>{% endif %}
  </p>
  <form method="post" action="/veille/faite" style="margin:0">
    <button type="submit">J'ai fait ma veille aujourd'hui</button>
  </form>
</div></div>

<div class="card"><div class="card-body">
  <h2>Question type à poser à une IA</h2>
  <p class="muted">Copiez ce texte dans n'importe quelle IA conversationnelle
  disposant d'une recherche web. Il est volontairement exigeant sur les sources
  et sur la distinction entre ce qui est adopté et ce qui n'est qu'un projet.
  <b>Une réponse d'IA n'est pas une source</b> : vérifiez toujours sur
  Légifrance, le BOFiP ou impots.gouv.fr, et demandez l'avis d'un
  expert-comptable en cas de doute.</p>
  <textarea id="prompt" rows="16" style="width:100%;font-family:ui-monospace,
    Menlo,Consolas,monospace;font-size:12.5px">{{ v.prompt }}</textarea>
  <p><button type="button" onclick="copierPrompt()">Copier la question</button>
     <span id="copie_ok" class="muted"></span></p>
</div></div>

<div class="card"><div class="card-body">
  <h2>Points d'attention connus</h2>
  <p class="muted">Relevés lors de la revue du corpus ({{ v.corpus_revu_le }}) —
  à confirmer lors de votre veille.</p>
  <ul>{% for a in v.actualite %}<li>{{ a }}</li>{% endfor %}</ul>
</div></div>

<div class="card"><div class="card-body" style="padding:0">
  <div style="padding:16px 16px 0"><h2>Les textes qui régissent le LMNP</h2>
  <p class="muted">Chaque texte est rattaché à ce qu'il gouverne dans ce
  logiciel.</p></div>
  <table>
    <thead><tr><th>Référence</th><th>Objet</th>
      <th>Ce qu'il gouverne ici</th><th>Règle liée</th></tr></thead>
    <tbody>
    {% for ref, intitule, effet, regle in v.corpus %}
      <tr>
        <td style="white-space:nowrap"><b>{{ ref }}</b></td>
        <td>{{ intitule }}</td>
        <td class="opt">{{ effet }}</td>
        <td class="muted">{{ regle or '—' }}</td>
      </tr>
    {% endfor %}
    </tbody>
  </table>
</div></div>

<script>
function copierPrompt() {
  var z = document.getElementById('prompt');
  z.select(); z.setSelectionRange(0, 999999);
  var ok = function () {
    document.getElementById('copie_ok').textContent = ' ✓ copié';
  };
  if (navigator.clipboard) {
    navigator.clipboard.writeText(z.value).then(ok, function () {
      document.execCommand('copy'); ok();
    });
  } else { document.execCommand('copy'); ok(); }
}
</script>
"""
````
