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
