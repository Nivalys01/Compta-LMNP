# Passe K — Clôture et cycle pluriannuel

**Joindre `00-INVARIANTS.md` avant ce prompt.**

## Pièces à joindre

| Fichier | Lignes |
|---|---|
| `modules/fiscal.py` | 559 |
| `modules/reprise.py` | 189 |
| `modules/migration_fec.py` | 288 |
| `modules/rejeu_fec.py` | 115 |
| `modules/ecritures.py` | 210 |
| `schema.sql` (tables `exercice`, `cloture_fiscale`) | — |
| `app.py` (route `/cloturer`) et `cli.py` (`cmd_cloturer`) | 2154 / 249 |

---

## Le prompt

La clôture est l'opération la plus lourde de conséquences du logiciel :
irréversible en pratique, elle fige un résultat, génère la dotation, crée ou
impute un déficit, et conditionne l'exercice suivant par ses à-nouveaux.

Le logiciel doit tenir un cycle **pluriannuel autonome** : clore N, ouvrir N+1
avec les bons à-nouveaux, et retrouver les mêmes chiffres qu'un cabinet.

### Ce que je te demande de chercher

**L'atomicité de la clôture.**

- `fiscal.cloturer` enchaîne dotation, calcul fiscal, traitement du déficit,
  écriture de résultat, marquage de l'exercice. Un `kill -9` au milieu laisse-t-il
  un état cohérent ? *(Un test existe pour ce scénario — vérifie qu'il couvre
  tous les points d'interruption, pas un seul.)*
- Combien de `commit` la clôture produit-elle ? Un seul commit final est la
  seule forme atomique face à une coupure de courant. Une fonction appelée en
  chemin peut-elle committer de son côté et rompre ce contrat ? **Vérifie-le par
  exécution**, en observant `conn.in_transaction` à chaque étape.
- Une clôture **interrompue** peut-elle être relancée ? Que produit le second
  passage — doublon de dotation, second déficit, résultat doublé ?

**La double clôture.**

- Clore un exercice **déjà clos** : refusé ? Par quel mécanisme, et ce
  mécanisme survit-il à une restauration depuis une sauvegarde prise avant la
  clôture ?
- Clore un exercice **antérieur** à un exercice déjà clos — clore 2024 alors que
  2025 l'est : que devient la chaîne des à-nouveaux ?
- Clore un exercice **futur**, ou un exercice sans aucune écriture.

**Les à-nouveaux et la continuité N → N+1.**

- `reprise.construire_an_interne` reporte le bilan de clôture en ouverture. Les
  classes retenues sont 1 à 5 : le compte de résultat (6 et 7) est-il bien
  **exclu**, et le résultat de l'exercice bien viré en `120000` puis en report à
  nouveau ?
- L'écriture d'à-nouveaux est-elle équilibrée **au centime** ? `controle_equilibre`
  existe : est-il appelé systématiquement, ou seulement sur demande ?
- Les soldes **négligeables** sont écartés (« ≤ 1 ct »). Cette troncature peut-elle
  déséquilibrer l'écriture, et où l'écart va-t-il ?
- Une seconde reprise est refusée (« déjà ses à-nouveaux »). Que se passe-t-il
  si l'utilisateur supprime l'écriture d'à-nouveaux à la main puis recommence ?
- `ouvrir_exercice` : un exercice peut-il être ouvert **sans** à-nouveaux, et
  l'utilisateur en être averti ? *(Un contrôle `AN_ABSENTS` existe.)*

**La cohérence entre les deux moteurs.**

- `fiscal.agregats` agrège par **classe** de compte ; `liasse.resultat_2033b`
  construit ses cases autrement. Les deux doivent donner le **même** résultat
  comptable. Vérifie-le par exécution sur un FEC de cabinet à sept chiffres
  portant des comptes hors des préfixes usuels — c'est exactement là qu'ils
  ont déjà divergé de 12 000 €.
- `cloture_fiscale` fige les retraitements. La liasse d'un exercice **clos**
  doit-elle relire cette table plutôt que recalculer ? Le fait-elle ? Que se
  passe-t-il si une écriture est ajoutée après la clôture ?

**La reprise depuis un FEC externe.**

- `migration_fec` et `rejeu_fec` reconstituent un historique. Trois exercices
  repris d'affilée donnent-ils les mêmes soldes que trois clôtures internes ?
- Un FEC de cabinet dont les à-nouveaux sont datés du 1ᵉʳ janvier, ou du
  31 décembre de l'année précédente : rattachés au bon exercice ?
- Un rejeu **interrompu** laisse-t-il l'exercice à moitié rempli ?

### Points d'attention nommés

- La clôture web prend une sauvegarde **avant**, archive le FEC **après**.
  L'archivage est désormais hors du `try` de la clôture, pour qu'un échec
  d'archivage ne passe pas pour un échec de clôture. Vérifie qu'aucune autre
  étape ne souffre du même mélange — une opération durable suivie d'une
  opération faillible dans le même bloc.
- La clôture CLI et la clôture web doivent produire **exactement** le même
  état. Compare-les par exécution sur le même dossier dupliqué : mêmes
  écritures, même déficit, même archive, même empreinte.
- Un exercice clos doit interdire toute écriture. Cherche les chemins qui
  contournent ce refus : contre-passation, restauration, migration de schéma,
  reprise d'à-nouveaux, cession datée dans l'exercice clos.
