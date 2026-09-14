# Passe P — Quittances et obligations envers le locataire

**Joindre `00-INVARIANTS.md` avant ce prompt.**

## Pièces à joindre

| Fichier | Lignes |
|---|---|
| `modules/quittances.py` | 336 |
| `modules/operations.py` | 399 |
| `modules/pages.py` (gabarit de quittance imprimable) | 2398 |
| `schema.sql` (tables `locataire`, `quittance`) | — |
| `app.py` (routes `/quittances`, `/quittance/<id>`) | 2154 |

---

## Le prompt

La quittance de loyer est le seul document que ce logiciel produit à
destination d'un **tiers** — le locataire. Elle a une valeur juridique : elle
atteste un paiement, et le bailleur ne peut pas la reprendre une fois remise.

Le schéma impose `quittance.numero` **UNIQUE** et `UNIQUE (locataire_id,
periode)`.

Une passe antérieure a traité trois défauts ici : des quittances de colocation
erronées, une quittance qui survivait à l'annulation de l'encaissement, et une
restauration qui réattribuait des numéros déjà remis. Confirme qu'ils tiennent.

### Ce que je te demande de chercher

**La numérotation, qui ne doit jamais se rejouer.**

- Comment le prochain numéro est-il calculé — `MAX(numero) + 1`, un compteur, la
  table `meta` ? Deux émissions **simultanées** peuvent-elles obtenir le même
  numéro, et que produit alors la contrainte d'unicité — une erreur propre ou une
  quittance perdue ?
- Une quittance supprimée libère-t-elle son numéro ? Elle ne doit pas : un
  numéro réutilisé désigne deux documents différents chez deux locataires.
- Après restauration d'une sauvegarde antérieure, le compteur repart en arrière.
  `perennite` avertit du nombre de quittances menacées : vérifie que
  l'avertissement est **bloquant** ou au moins impossible à manquer, et qu'il
  compte juste.

**Le lien avec la comptabilité.**

- Une quittance atteste un paiement. Peut-elle être émise **sans** écriture
  d'encaissement correspondante ? Et l'inverse — un encaissement sans quittance,
  est-ce signalé ?
- Le montant de la quittance et celui de l'opération : rapprochés, ou saisis
  deux fois indépendamment ? Deux saisies indépendantes finissent par diverger.
- L'annulation de l'encaissement par contre-passation : que devient la
  quittance déjà émise ? Elle ne peut pas être « annulée » chez le locataire —
  le logiciel gère-t-il ce cas autrement qu'en supprimant la ligne ?
- Une quittance sur un exercice **clos** : émise, refusée, ou émise en modifiant
  un exercice clos ?

**La colocation et les cas de bail.**

- Plusieurs locataires sur un même logement : chacun sa quittance pour sa part,
  ou une quittance globale ? La somme des parts fait-elle le loyer ?
- Un locataire qui entre ou sort **en cours de mois** : la quittance est-elle au
  prorata, et le prorata est-il calculé sur les jours réels ?
- Un changement de locataire sur la même période : la contrainte
  `UNIQUE (locataire_id, periode)` l'autorise, mais le logement reçoit alors
  deux quittances pour le même mois — cohérent ?
- Un loyer **impayé** : peut-on émettre une quittance, et si oui le logiciel
  distingue-t-il quittance (paiement reçu) et avis d'échéance (paiement dû) ?
  C'est une distinction juridique, pas cosmétique.

**Le contenu du document.**

- Les mentions obligatoires d'une quittance : identité du bailleur, du
  locataire, adresse du logement, période, montant du loyer **et des charges
  distinctement**, date et somme reçue. Lesquelles manquent ?
- Le document imprimé porte-t-il la **ventilation loyer / charges** ? La loi
  l'exige, et c'est aussi ce qui permet au locataire de vérifier sa
  régularisation.
- Les données du locataire passent dans un gabarit HTML : sont-elles
  **échappées** ? Un nom contenant `&` ou `<` casse la page ou l'injecte.
- Le document contient-il des données que le locataire n'a pas à connaître — le
  SIREN du bailleur, d'autres locataires, des montants d'un autre logement ?

**La protection des données du locataire.**

C'est un angle qu'aucune passe n'a encore couvert : le logiciel détient des
données personnelles **de tiers**.

- Ces données partent-elles quelque part — jeu de démonstration, export FEC,
  journal d'erreurs, sauvegarde, PDF de liasse ?
- Le jeu de démonstration **publié** : contient-il des noms de locataires
  réels ? L'anonymisation couvre les libellés d'écriture, mais la table
  `locataire` est-elle du voyage ?
- Une quittance générée reste-t-elle sur le disque après impression, et où ?

### Points d'attention nommés

- La question qui gouverne cette passe : **une quittance remise ne se reprend
  pas.** Tout mécanisme qui permet de la modifier, de la renuméroter ou de la
  faire disparaître après remise est un défaut, même si la base reste cohérente.
- Vérifie par exécution le scénario complet : émettre trois quittances,
  restaurer une sauvegarde prise avant la deuxième, puis émettre à nouveau.
  Combien de documents différents portent le numéro 2 ?
- `quittances.assurer_schema` crée ses tables à la volée. Comme ailleurs dans ce
  logiciel, vérifie qu'il ne committe pas la transaction de son appelant.
