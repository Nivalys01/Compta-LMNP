# Passe Q — Atomicité, concurrence, intégrité transactionnelle

**Joindre `00-INVARIANTS.md` avant ce prompt.**

## Pièces à joindre

Cette passe est **transverse** : elle ne porte pas sur un domaine métier mais
sur une propriété que tout le code doit respecter. Joindre l'ensemble des
modules qui écrivent en base :

| Fichier | Lignes |
|---|---|
| `modules/ecritures.py` | 210 |
| `modules/operations.py` | 399 |
| `modules/fiscal.py` | 559 |
| `modules/gabarits.py` | 277 |
| `modules/parametres.py` | 191 |
| `modules/quittances.py` | 336 |
| `modules/cession.py` | 172 |
| `modules/reprise.py` | 189 |
| `modules/rejeu_fec.py` | 115 |
| `modules/migrations.py` | 133 |
| `modules/perennite.py` | 344 |
| `app.py` | 2154 |

---

## Le prompt

C'est la passe qui a produit les deux pires défauts déjà trouvés sur ce
logiciel, et **aucun des deux n'était visible à la lecture du code**. Lis la
règle 2 des invariants avant de commencer : ici, un constat établi par lecture
ne vaut rien.

Le logiciel est mono-utilisateur mais **pas mono-thread** : le serveur de
développement Flask est threadé par défaut, et un navigateur ouvre plusieurs
requêtes en parallèle sur une même page.

### Ce que je te demande de chercher

**Une fonction de lecture qui committe.**

C'est le défaut à chercher en premier, parce qu'il en existait deux exemplaires
et qu'il rompt silencieusement tous les contrats d'atomicité du logiciel.

Le motif : une fonction qui **sème** sa table au premier accès
(`CREATE TABLE IF NOT EXISTS …` suivi d'un `conn.commit()`), appelée depuis un
chemin de lecture. L'appelant qui travaillait en transaction ouverte voit son
travail validé sous ses pieds.

- Recense **tous** les `conn.commit()` du code joint, et pour chacun établis s'il
  peut être atteint depuis une fonction de lecture ou depuis une boucle
  d'écriture groupée.
- Deux ont été corrigés (`gabarits.assurer_table`, `parametres.assurer`) en ne
  committant plus si `conn.in_transaction`. Cherche les autres :
  `quittances.assurer_schema`, `cession.assurer_schema`,
  `fiscal._table_39c_bien`, `operations.assurer_colonne_annulee`,
  `init_db.creer_index`, `veille_fiscale`.
- **Méthode imposée** : pour chaque candidat, ouvre une transaction, insère un
  témoin, appelle la fonction, `rollback`, et **compte le témoin en base**. Ne
  conclus pas autrement.

**Les opérations groupées.**

- `operations.saisir(commit=False)` doit laisser la transaction ouverte. Le
  contrat tient-il sur **tous** les types de gabarit, y compris ceux qui
  déclenchent un paramètre versionné ou un gabarit personnalisé ?
- La clôture compte sur un commit **unique** final pour être atomique face à une
  coupure de courant. Compte les commits réellement produits par
  `fiscal.cloturer`, par exécution, en instrumentant `conn.commit`.
- L'import bancaire, la reprise d'à-nouveaux, le rejeu d'un FEC, la cession, la
  migration : chacun écrit plusieurs lignes. Pour chacun, interromps au milieu et
  **compte ce qui reste**.

**La concurrence.**

- Le motif « tester puis agir » sans verrou : un `if x in ensemble` suivi d'un
  `ensemble.add(x)`, un `SELECT MAX(...)` suivi d'un `INSERT`. Recense-les.
  `ecritures.prochain_num` et la numérotation des quittances sont les deux
  candidats évidents.
- `ecritures.inserer` utilise `BEGIN IMMEDIATE` et un rejeu borné sur collision
  de numéro. Le rejeu est-il suffisant, et que se passe-t-il **après** la
  cinquième tentative ?
- Deux requêtes parallèles qui clôturent le même exercice, qui restaurent la
  même base, qui émettent une quittance au même moment : que produit chacune ?
- `busy_timeout` est-il réglé ? Sans lui, un « database is locked » remonte
  brutalement à l'utilisateur au lieu d'attendre.

**Les exceptions avalées.**

- `app.py` porte une trentaine d'`except Exception as exc` qui transforment
  l'erreur en message. Pour chacun, la question : **l'état de la base au moment
  de l'exception est-il cohérent ?** Un message d'erreur sur une base à moitié
  modifiée est le pire des deux mondes — l'utilisateur croit que rien n'a eu
  lieu.
- Cherche les endroits où une opération **durable** est suivie d'une opération
  **faillible** dans le même bloc : l'échec de la seconde fait passer la
  première pour annulée. Un cas a été corrigé (clôture puis archivage) —
  cherche les autres.
- Un `except` qui remet un état en place (`discard`, `rollback`, suppression d'un
  fichier) peut-il lui-même échouer ?

**Le journal.**

- Les refus et les annulations sont-ils **journalisés** ? Un import annulé, une
  clôture interrompue, une migration échouée : l'utilisateur peut-il, trois mois
  plus tard, savoir ce qui s'est passé ?
- Le journal contient-il des données comptables réelles ? Il reste sur la
  machine, mais c'est un fichier de plus à protéger.

### Points d'attention nommés

- **Le piège SQLite documenté dans le code** : le `RELEASE` d'un savepoint le
  plus externe vaut `COMMIT` s'il n'existe pas de transaction englobante.
  `ecritures.inserer` s'en protège en ouvrant explicitement la transaction.
  Vérifie que **tout** code qui utilise un savepoint fait de même.
- **Ce que Python ignore** : `conn.rollback()` ne défait que ce qui n'a pas été
  committé. Si une fonction intermédiaire a committé, le rollback réussit sans
  rien défaire et **ne lève aucune erreur**. C'est exactement ce qui s'est
  produit. Instrumente `conn.commit` pour compter les appels plutôt que de te
  fier au succès du rollback.
- **Formule le constat en euros** quand c'est possible : « un import de dix
  lignes interrompu à la septième laisse six loyers en base, et une relance les
  saisit deux fois » est plus utile que « absence de transaction ».
