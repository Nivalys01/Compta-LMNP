# Passe I — Article 39 C : plafonnement de l'amortissement

**Joindre `00-INVARIANTS.md` avant ce prompt.**

## Pièces à joindre

| Fichier | Lignes |
|---|---|
| `modules/fiscal.py` | 559 |
| `modules/amortissement.py` | 363 |
| `modules/liasse.py` | 647 |
| `schema.sql` (tables `suivi_39c`, `suivi_39c_bien`) | — |
| `modules/parametres.py` | 191 |

Utile : l'article 39 C, II-2 du CGI et le BOFiP correspondant ; la notice 2033-C
pour le tableau de suivi.

---

## Le prompt

L'article 39 C plafonne l'amortissement déductible d'un bien loué : la fraction
excédentaire n'est pas perdue, elle est **reportée** sans limite de durée et
devient déductible les années où le plafond le permet. C'est un mécanisme à
mémoire — une erreur une année se propage à toutes les suivantes.

Le logiciel tient ce suivi, et le ventile **par bien** (multi-biens).

### Ce que je te demande de chercher

**Le plafond.**

- `agregats` calcule `plafond_39c`. La base retenue est-elle la bonne ? Le
  plafond est le loyer **acquis** diminué des charges **afférentes au bien** :
  les charges de structure (honoraires comptables, CFE) en sont exclues.
- `comptes_hors_plafond_39c` porte cette exclusion. La liste est-elle
  configurable, et que se passe-t-il si elle est **vide** — plafond trop bas,
  trop haut, ou calcul faux ?
- Un FEC de cabinet apporte des comptes de charges à sept chiffres inconnus de
  cette liste. Entrent-ils dans le plafond alors qu'ils devraient en sortir, ou
  l'inverse ?
- Le prix de cession (`775000`) doit-il être exclu du plafond ? Le code le
  soustrait — vérifie que c'est juste et que ça ne le soustrait pas deux fois.

**Le report et sa mémoire.**

- `calculer_39c(stock_ouverture, dotation, plafond)` : vérifie la fonction
  seule, par exécution, sur des cas limites — plafond nul, plafond négatif
  (charges supérieures aux loyers), dotation nulle, stock d'ouverture non nul
  avec dotation nulle.
- `_stock_39c_ouverture` relit le stock de l'exercice précédent. Que se
  passe-t-il quand l'exercice N-1 **n'existe pas**, n'est **pas clos**, ou a été
  clos puis restauré depuis une sauvegarde antérieure ?
- Le report 39 C est **sans péremption**, contrairement au déficit. Le code les
  distingue-t-il partout, ou un mécanisme de purge s'applique-t-il par erreur
  aux deux ?

**La ventilation par bien.**

- `_ventiler_39c_par_bien` et `_repartir` : la somme des parts égale-t-elle le
  total, au centime ? Quel poids sert de clé de répartition, et est-il le bon ?
- Un bien **cédé** en cours d'exercice : sa part de stock 39 C part-elle avec
  lui, reste-t-elle, ou disparaît-elle ? `suivi_39c_par_bien` expose une colonne
  de sortie — que devient le stock du bien cédé l'année suivante ?
- Un bien acquis en cours d'exercice, un bien sans aucun loyer, un bien dont le
  plafond est négatif : la répartition reste-t-elle cohérente ?
- La somme des suivis **par bien** égale-t-elle le suivi **global** ? Vérifie-le
  par exécution sur un dossier à deux biens, dont un cédé.

**Ce que la liasse en fait.**

- Le report de l'exercice va en **case 318** (amortissements excédentaires,
  art. 39-4). Vérifie que c'est bien la case du CERFA 2033-B en vigueur et que
  le signe est le bon — une réintégration, pas une déduction.
- L'utilisation du stock une année où le plafond le permet : par quelle ligne
  passe-t-elle, et cette ligne est-elle **imprimée** ?
- Le tableau de suivi du PDF : ses colonnes s'additionnent-elles ? Une colonne
  calculée puis jamais rendue est un défaut déjà rencontré deux fois sur ce
  logiciel.

### Points d'attention nommés

- Un constat d'une passe antérieure sur le plafond 39 C a été **refusé**,
  tranché par un test de calage sur trois exercices réels. Si tu rouvres ce
  sujet, dis explicitement contre quoi tu confrontes ton raisonnement — le test
  de calage fait foi sur les chiffres, pas l'intuition.
- `retraitement_automatique` applique des retraitements à la clôture. Le
  report 39 C en est-il, et peut-il se cumuler avec un retraitement **manuel**
  saisi par l'utilisateur, produisant un double comptage ? *(Un contrôle
  `RETRAITEMENT_MANUEL_PLAFOND` existe — sans `controles.py` tu ne peux pas
  juger de sa portée.)*
- `_table_39c_bien` crée sa table à la volée et `migrations.py` porte un palier
  pour elle. Un dossier ancien, migré, a-t-il un stock par bien **cohérent**
  avec son stock global, ou la migration laisse-t-elle les deux divergents ?
