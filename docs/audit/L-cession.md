# Passe L — Cession d'un bien et plus-values

**Joindre `00-INVARIANTS.md` avant ce prompt.**

## Pièces à joindre

| Fichier | Lignes |
|---|---|
| `modules/cession.py` | 172 |
| `modules/fiscal.py` | 559 |
| `modules/liasse.py` | 647 |
| `modules/amortissement.py` | 363 |
| `schema.sql` (colonnes `bien.date_cession`, `composant.date_sortie`) | — |

Utile : l'article 150 U du CGI (plus-values des particuliers) et le BOFiP sur le
régime des plus-values en location meublée non professionnelle.

---

## Le prompt

La cession est le point où le régime LMNP **non professionnel** diverge le plus
de la comptabilité d'entreprise : la plus-value relève du régime des
plus-values **des particuliers** (article 150 U), pas du résultat BIC. Elle doit
donc être **neutralisée** dans le résultat fiscal, alors qu'elle est bien
comptabilisée.

Le logiciel passe trois écritures : sortie de l'actif par la VNC en `675000`,
encaissement du prix en `775000`, et une neutralisation au calcul fiscal.

Une passe antérieure a déjà corrigé deux défauts graves ici — le résultat fiscal
recalculé **sans** la neutralisation (case 5NA à 30 000 € au lieu de 18 016 €) et
la ligne 352 qui valait la plus-value au lieu de zéro. Ne les resignale pas :
confirme qu'ils tiennent, et cherche ailleurs.

### Ce que je te demande de chercher

**Les écritures de cession.**

- `ceder_bien` : l'écriture est-elle équilibrée, datée dans le bon exercice, et
  refusée si l'exercice est **clos** ?
- `_dotation_prorata` calcule la dotation de l'année de cession au prorata.
  Jusqu'à quelle date — celle de la cession ou la fin d'exercice ? Un mois de
  trop, et la VNC est fausse.
- La VNC portée en `675000` est-elle bien **valeur brute moins cumul
  d'amortissement à la date de cession**, prorata inclus ?
- Une cession **à titre gratuit** (prix nul) : le code le supporte-t-il, ou
  divise-t-il par zéro quelque part ? Une passe antérieure signale que le
  résultat comptable s'en trouvait majoré de toute la VNC — vérifie que c'est
  réglé.
- Une cession **partielle** — un seul composant sorti, les autres conservés :
  possible, cohérente ?

**La neutralisation fiscale.**

- `agregats` expose `produits_cession` et `vnc_cession`, et la neutralisation
  vaut `vnc_cession - produits_cession`. Vérifie le **signe** sur les deux cas :
  plus-value (prix > VNC) et moins-value (prix < VNC). Une moins-value doit-elle
  être neutralisée symétriquement, ou reste-t-elle déductible ?
- La neutralisation est-elle appliquée **une seule fois** ? Elle apparaît à deux
  endroits de `liasse.py` selon que l'exercice est clos ou ouvert : les deux
  chemins donnent-ils le même chiffre ?
- Un exercice clos relit `cloture_fiscale`. La neutralisation y est-elle figée,
  ou recalculée — et si elle est recalculée après qu'une écriture a bougé, le
  résultat de la liasse s'écarte-t-il de celui de la clôture ?

**Le bien cédé dans les tableaux.**

- Les composants d'un bien cédé sont exclus du 2033-C. Le sont-ils aussi du
  **bilan** ? Si l'un des deux les garde, les deux divergent.
- Le suivi 39 C du bien cédé : son stock part-il, reste-t-il, ou disparaît-il ?
  *(Voir aussi la passe I.)*
- Un bien cédé **au 31 décembre** : dans l'exercice de cession ou le suivant ?
  Et au 1ᵉʳ janvier ?
- L'année **suivant** la cession, le bien ne doit plus produire ni dotation ni
  ligne de tableau. Vérifie-le par exécution sur deux exercices consécutifs.

**Ce que la liasse imprime.**

- Le prix de cession va en case **290** (produits exceptionnels), la VNC en case
  **300** (charges exceptionnelles) — vérifie contre le CERFA 2033-B-SD 2026
  joint au dépôt.
- Le cadre III du 2033-C (plus-values, moins-values) : servi ou laissé vide ?
  S'il est laissé vide alors qu'une cession a eu lieu, le déclarant n'a rien à
  recopier là où le formulaire l'attend.
- Le résultat comptable (310) inclut la plus-value, le résultat fiscal ne
  l'inclut pas. L'écart entre les deux est-il **lisible** dans le document, ou
  le déclarant doit-il le deviner ?

### Points d'attention nommés

- `cession.assurer_schema` crée `675000` et `775000` **à la volée**, hors du
  référentiel livré et hors migration. Un dossier qui n'a jamais eu de cession
  ne les a donc pas. Que produisent alors les calculs qui les cherchent —
  `agregats` fait `SELECT … WHERE compte_num='775000'` sur un compte absent ?
- Un constat d'une passe antérieure portait sur une dotation de cession **non
  filtrée par bien** : c'était une régression introduite par une passe
  précédente. Cherche si le filtrage par bien est appliqué partout où il doit
  l'être, ou seulement à l'endroit qui avait été corrigé.
- Le régime des plus-values est **hors** du périmètre du logiciel (il ne
  calcule pas la plus-value imposable, il neutralise). Vérifie que le document
  le **dit** au déclarant, plutôt que de le laisser croire que la cession est
  traitée de bout en bout.
