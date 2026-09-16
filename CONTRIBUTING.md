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
