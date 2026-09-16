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
