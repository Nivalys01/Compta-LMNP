# Compta LMNP

//Message de l'Auteur//
J'ai souhaité développer ce logiciel pour faire face aux augmentations de tarifs de la solution payante que j'utilisais jusqu'à récemment, sans que ces augmentations me paraissent justifiées avec l'apparition de solutions IA et de leurs coûts associés. 
Mon objectif est de développer une solution robuste et fiable, je ne suis pas ingénieur informaticien, mais j'ai un cursus comptable. 
Aussi je me suis appuyé sur plusieurs modèles d'IA pour le développement (dont Claude Opus 5, Fable 5.1, GPT 6-ASTRA). 
Il subsiste des imprécisions dans le texte qui sont sans importances sur le fonctionnement comptable ou la compréhension générale et je n'effectue pas de correction si la substance l'emporte sur la forme.
L'investissement en temps passé m'a donné envie de rendre cela disponible gratuitement. Il n'y a pas de raison de dépenser de l'argent, du temps et des ressources naturelles pour juste le garder pour soit.
Ce n'est peut être pas la solution la plus facile d'accès (installation de python pour l'OS windows), mais c'est gratuit. Le code étant open-source, vous êtes libre de vérifier l'absence de malveillance.
Je vous souhaite une bonne appropriation de l'outil ! 



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
