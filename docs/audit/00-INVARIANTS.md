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
