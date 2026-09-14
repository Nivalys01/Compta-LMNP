# Passe G — Régularité comptable et intégrité du FEC

**Joindre `00-INVARIANTS.md` avant ce prompt.**

## Pièces à joindre

| Fichier | Lignes |
|---|---|
| `modules/ecritures.py` | 210 |
| `modules/export_fec.py` | 93 |
| `modules/valider_fec.py` | 255 |
| `modules/fec_io.py` | 170 |
| `schema.sql` | — |
| `modules/operations.py` | 399 |

Joindre aussi, si tu veux que la conformité soit vérifiée et pas supposée :
l'arrêté A47 A-1 (ou la notice DGFiP du FEC).

---

## Le prompt

Cette passe porte sur ce qui fait qu'une comptabilité **est** une comptabilité :
l'équilibre, la continuité, l'immuabilité, et la conformité du fichier remis à
l'administration.

Le logiciel produit un FEC à 18 colonnes qui doit être accepté par
l'administration, et reconstitue ses écritures depuis un FEC externe. Les deux
sens comptent.

### Ce que je te demande de chercher

**L'équilibre et son contrôle.**

- Une écriture peut-elle être enregistrée débit ≠ crédit ? Par quel chemin —
  `ecritures.inserer`, un import, une reprise d'à-nouveaux, une cession ?
- L'écart d'arrondi : où est-il absorbé, et cette absorption peut-elle déplacer
  un centime vers un compte qui n'a rien à voir ?
- Un montant négatif, nul, `NaN`, `inf` : où sont-ils refusés, et ce refus
  est-il **avant** toute écriture ou après une insertion partielle ?

**La continuité de la numérotation.**

- `ecritures.inserer` attribue un numéro. Deux écritures peuvent-elles porter
  le même ? Un numéro peut-il manquer — une écriture annulée, un rejeu
  interrompu, un `rollback` partiel ?
- `valider_fec` signale une numérotation non continue. Cette règle est-elle
  juste ? Beaucoup de cabinets numérotent **par journal** (AC 1..n, BQ 1..n) —
  ce que le logiciel reconnaît par ailleurs au rejeu. Le contrôle de continuité
  et le rejeu se contredisent-ils ?
- Une écriture sans aucune ligne peut-elle subsister ?

**L'immuabilité.**

- Une écriture d'un exercice **clos** peut-elle être modifiée, supprimée,
  renumérotée ? Par quel chemin — SQL direct, annulation, restauration,
  migration de schéma ?
- L'annulation se fait par contre-passation : l'écriture inverse porte-t-elle la
  bonne date, le bon exercice, la bonne référence de pièce ? Une
  contre-passation dans un exercice clos est-elle refusée ?

**Le FEC produit.**

- Les 18 colonnes sont-elles dans l'ordre, nommées exactement comme l'exige
  l'arrêté, séparées correctement, terminées correctement (CRLF) ?
- Le format des montants, des dates, du séparateur décimal.
- Les colonnes facultatives laissées vides : lettrage, devise. Leur vacuité est
  licite quand l'usage ne s'y prête pas — mais `ValidDate` sur un exercice
  **clos** l'est-elle ?
- **Le FEC produit passe-t-il le validateur du logiciel lui-même ?** Vérifie-le
  par exécution. Et le validateur accepte-t-il des fichiers qu'il devrait
  refuser ?

**Le FEC lu.**

- Un FEC de cabinet à **sept chiffres** de numéro de compte : lu correctement ?
  Le type et la classe déduits du numéro sont-ils justes pour chaque tranche,
  en particulier la classe 4 — 401 fournisseurs au passif, 411 clients à
  l'actif, 44/45/46/48 mixtes par construction ?
- Un guillemet, une tabulation, un saut de ligne dans un libellé.
- Une ligne trop courte, une colonne manquante, un en-tête absent : signalés ou
  **écartés en silence** ?
- Un FEC de plusieurs exercices, ou daté d'une autre année que celle visée.

### Points d'attention nommés

- `ecritures.inserer` ouvre une transaction et un savepoint, avec un
  commentaire expliquant que le `RELEASE` du savepoint le plus externe vaut
  `COMMIT` en SQLite. Le raisonnement tient-il pour **tous** les chemins
  d'appel, y compris quand une fonction appelée entre-temps committe de son
  côté ?
- `operations.saisir` accepte `commit=False` pour grouper. Ce contrat est-il
  respecté de bout en bout ? *(Vérifie-le en comptant les lignes en base après
  un échec volontaire, pas en relisant le code.)*
- `fec_io.lire_brut` ne filtre volontairement aucune ligne, pour que le
  validateur puisse les signaler. Une ligne écartée plus loin l'est-elle
  **avec un compte rendu** ?
- `export_fec` reconstitue les 18 colonnes par une vue SQL. Une écriture sans
  ligne, un compte absent du plan, un libellé `NULL` : que produit la vue ?

### Question ouverte à trancher

Le logiciel tient une comptabilité de caisse sans compte de trésorerie. Un FEC
**produit** dans ces conditions est-il régulier au sens de l'arrêté, ou
l'absence de compte 512 est-elle un motif de rejet ? Ce n'est pas une question
de code : dis-le en section « non vérifiable » si tu n'as pas de quoi trancher.
