# Passe H — Amortissements par composants

**Joindre `00-INVARIANTS.md` avant ce prompt.**

## Pièces à joindre

| Fichier | Lignes |
|---|---|
| `modules/amortissement.py` | 363 |
| `modules/plan_immo.py` | 89 |
| `schema.sql` (tables `composant`, `plan_amortissement`) | — |
| `modules/operations.py` | 399 |
| `seed_referentiel.sql` | — |

Utile : BOI-BIC-AMT (amortissements), et la notice 2033-C.

---

## Le prompt

Cette passe porte sur le cœur de l'intérêt du régime réel : l'amortissement du
bien par composants. Une erreur ici se répète **sur toute la durée du plan** et
ne se voit pas l'année où elle est commise.

### Ce que je te demande de chercher

**Le calcul lui-même.**

- `plan(valeur_brute, duree_annees, date_mise_service)` produit les annuités.
  La somme des annuités égale-t-elle **exactement** la valeur brute, au
  centime, pour toutes les durées et toutes les dates de mise en service ?
  Teste des cas qui tombent mal : 15 ans sur 1 299,87 €, une durée de 1 an, une
  mise en service le 31 décembre.
- `fraction_prorata` : le prorata de la première et de la **dernière** année.
  Leur somme fait-elle une année pleine ? Le logiciel utilise `Decimal` —
  vérifie que la conversion depuis et vers le flottant ne réintroduit pas
  l'erreur qu'il évite.
- Une durée nulle, négative, absente (`NULL` en base) : refusée ou silencieuse ?
- Un composant non amortissable (terrain) : `plan_immo` le déclare sans compte
  d'amortissement. Peut-il quand même recevoir une dotation ?

**La dotation de l'exercice.**

- `dotations_exercice` et `_cumul_comptabilise` : le cumul déjà comptabilisé est
  relu en base. Que se passe-t-il si l'exercice N-1 n'a jamais été clos, si une
  dotation a été saisie **à la main** en plus de celle générée, ou si une
  écriture de dotation a été annulée par contre-passation ?
- Un amortissement peut-il dépasser la valeur brute ? Dans quel cas — durée
  raccourcie en cours de route, valeur brute corrigée après coup, double
  clôture ?
- `generer_cloture` est appelée à la clôture. Peut-elle être appelée **deux
  fois** sur le même exercice, et que produit le second appel ?

**L'article 39 B — l'amortissement minimum.**

Le code documente ce point comme traité en v8.39.0. Vérifie-le :

- la somme des amortissements pratiqués doit être au moins égale à celle des
  amortissements **linéaires** cumulés depuis la mise en service ;
- que se passe-t-il quand un exercice a été clos **sans** dotation (oubli,
  exercice déficitaire, bien acquis en fin d'année) ? Le rattrapage est-il
  possible, et par quel geste ?
- le logiciel signale-t-il l'insuffisance, la corrige-t-il, ou l'ignore-t-il ?

**La ventilation du prix.**

- `ventilation_proposee` et `normaliser_quote_part` : la somme des composants
  égale-t-elle le prix total ? La quote-part de terrain est-elle exclue de
  l'amortissement ?
- Une quote-part saisie en pourcentage (7,35) ou en fraction (0,0735) :
  `normaliser_quote_part` tranche-t-elle sans ambiguïté ? Que fait-elle de 1,0 —
  1 % ou 100 % ?
- La ventilation peut-elle rester **incomplète** et l'utilisateur en être
  averti ? *(Un contrôle `VENTILATION_INCOMPLETE` existe : fait-il ce qu'il
  annonce ?)*

**Le plan des immobilisations.**

- `plan_immo.py` est la source unique depuis peu. Un compte d'immobilisation
  utilisé en base mais **absent** de cette table : que produit le 2033-C, que
  produit le menu de saisie ?
- Un FEC de cabinet apporte `2180000`, `2181000`, `2818000`, `2818100` — sept
  chiffres, hors de la table. Où atterrissent-ils dans le tableau des
  immobilisations et dans le bilan ?

### Points d'attention nommés

- L'amortissement est le poste le plus lourd du résultat LMNP. Toute erreur de
  centime se **cumule** et finit par faire diverger le 2033-C du bilan :
  cherche où cette divergence serait détectée, et si elle l'est **avant** la
  liasse ou seulement dedans.
- `_cumul_comptabilise` lit ce qui est **écrit en base**, pas ce que le plan
  théorique prévoit. Les deux peuvent-ils diverger sans que rien ne le dise ?
  C'est exactement le genre d'écart qu'un contrôle doit rendre visible.
- Le contrôle `DOTATION_PLAN` et le contrôle `AMORT_ANTERIEURS` existent dans
  `controles.py`. Sans ce fichier tu ne peux pas juger de leur portée : dis-le
  plutôt que de supposer.
