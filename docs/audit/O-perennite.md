# Passe O — Pérennité : sauvegardes, restauration, piste d'audit

**Joindre `00-INVARIANTS.md` avant ce prompt.**

## Pièces à joindre

| Fichier | Lignes |
|---|---|
| `modules/perennite.py` | 344 |
| `modules/dossiers.py` | 188 |
| `modules/migrations.py` | 133 |
| `modules/init_db.py` | 354 |
| `app.py` (routes `/sauvegardes/restaurer`, `/archives`, `/dossiers`) | 2154 |

---

## Le prompt

Une comptabilité doit être **conservée six ans**. Ce logiciel est un fichier
SQLite sur le disque d'un particulier : les sauvegardes, la rotation, la
restauration et l'archivage des FEC sont ce qui tient lieu de pérennité.

Une passe antérieure a déjà traité trois chemins de perte irréversible —
`init()` qui détruisait une base tenue, une restauration qui réattribuait des
numéros de quittance déjà remis, et l'absence de rattachement d'une sauvegarde à
son dossier. Confirme qu'ils tiennent, et cherche ailleurs.

### Ce que je te demande de chercher

**La sauvegarde.**

- `sauvegarder` copie la base. Une copie prise **pendant** une écriture
  concurrente est-elle cohérente ? SQLite écrit dans un journal ou un WAL : la
  copie emporte-t-elle ce journal, ou produit-elle une base tronquée qui se
  restaure sans erreur mais avec des écritures manquantes ?
- La sauvegarde est-elle **vérifiée** après écriture — `PRAGMA integrity_check`,
  taille non nulle, lisibilité ? Une sauvegarde corrompue qui passe pour valide
  est le pire cas de cette passe.
- `sauvegardes_quotidiennes` au démarrage : que se passe-t-il si le disque est
  plein, le répertoire non accessible en écriture, ou le dossier ouvert depuis
  un montage réseau déconnecté ? Le logiciel démarre-t-il quand même, et le
  dit-il ?
- La **rotation** : combien de sauvegardes conservées, et sur quel critère ? Une
  sauvegarde « de sûreté » est annoncée hors rotation — vérifie qu'elle l'est
  vraiment et qu'elle ne peut pas être emportée par la purge.

**La restauration.**

- `restaurer` remplace la base courante. Une **copie de sûreté réversible** est
  prise avant : vérifie-le par exécution, et vérifie qu'on peut effectivement
  revenir en arrière après une restauration regrettée.
- L'intégrité de la sauvegarde est contrôlée **avant** l'écrasement : le
  contrôle porte-t-il sur la structure seulement, ou aussi sur le contenu — une
  base valide mais **vide** passerait-elle ?
- Restaurer une sauvegarde d'un **autre dossier** est refusé. Comment le
  logiciel établit-il l'appartenance, et cette marque survit-elle à une
  restauration, à un renommage de dossier, à une migration de schéma ?
- Restaurer une sauvegarde d'un schéma **plus ancien** : migrée ensuite, ou
  ouverte telle quelle ? Et d'un schéma plus **récent** ?
- Restaurer une sauvegarde prise **avant** une clôture, alors que l'exercice
  suivant a déjà des écritures : que devient la chaîne des à-nouveaux ?

**La piste d'audit — l'archivage des FEC.**

- `archiver_fec` fige le FEC et consigne son empreinte SHA-256 dans
  `manifeste.csv`. Le manifeste est-il en **append** seul, ou peut-il être
  réécrit ? Peut-on y ajouter deux lignes pour le même exercice, et laquelle
  fait foi ?
- La vérification d'intégrité relit chaque FEC archivé contre son empreinte.
  Que produit-elle si le fichier a disparu, si le manifeste a disparu, si une
  ligne est illisible ? Un écart est-il **BLOQUANT** ou informatif ?
- Un même exercice clôturé deux fois — après restauration — produit deux
  archives : laquelle est la bonne, et le manifeste permet-il de le savoir ?
- L'archive et le manifeste vivent dans le répertoire du dossier. Une
  restauration les emporte-t-elle, ou la base revient-elle en arrière en
  laissant des archives d'un futur qui n'existe plus ?

**Le registre des dossiers.**

- `dossiers.py` tient un registre (`dossiers.json`). Un registre corrompu,
  absent, ou pointant un fichier disparu : le logiciel démarre-t-il ? *(Une
  passe antérieure a traité le dossier absent remplacé par une base vierge —
  confirme que ça tient.)*
- Deux dossiers peuvent-ils pointer le **même** fichier ? Un slug peut-il
  collisionner, ou contenir un séparateur de chemin ?
- Le registre est-il sauvegardé avec les bases, ou perdu en cas de sinistre —
  auquel cas les bases subsistent mais ne sont plus retrouvables par
  l'interface ?

**La migration de schéma.**

- `migrations.migrer` prend une sauvegarde avant d'appliquer les paliers.
  Un palier qui **échoue au milieu** laisse-t-il la base dans un état
  intermédiaire, et la version est-elle malgré tout marquée ? L'assertion de
  garde vérifie que les paliers sont complets — vérifie qu'elle ne peut pas être
  contournée.
- Une base **plus récente** que le logiciel est refusée sans être touchée :
  confirme-le, y compris sur les chemins qui écrivent avant le garde.

### Points d'attention nommés

- La question à garder en tête pour toute cette passe : **« après quel geste
  l'utilisateur ne peut-il plus revenir en arrière, et le sait-il à ce
  moment-là ? »** Liste ces gestes, et pour chacun dis si un retour est possible.
- Les sauvegardes conservent la comptabilité **réelle**. Vérifie que rien dans
  le logiciel ne les envoie ailleurs — pas d'envoi réseau, pas de copie dans un
  répertoire synchronisé par défaut, pas de trace dans un journal.
- Une passe antérieure a relevé que la **suite de tests** déposait des copies
  réelles dans `/tmp`, hors de toute protection. Cherche les autres chemins par
  lesquels une copie de la base sort du répertoire du dossier : export, PDF,
  journal d'erreurs, répertoire temporaire d'import.
