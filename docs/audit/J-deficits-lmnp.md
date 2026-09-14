# Passe J — Déficits LMNP : report, péremption, imputation

**Joindre `00-INVARIANTS.md` avant ce prompt.**

## Pièces à joindre

| Fichier | Lignes |
|---|---|
| `modules/fiscal.py` | 559 |
| `modules/liasse.py` | 647 |
| `modules/liasse_pdf.py` | 447 |
| `schema.sql` (table `deficit_lmnp`) | — |

Utile, et **le second manque aujourd'hui sur disque** :

- le CERFA **2033-B-SD 2026** (présent à la racine du dépôt) ;
- le CERFA **2042-C-PRO** — absent : les cases `5NA` / `5NY` n'ont jamais pu
  être vérifiées. Joins-le si tu veux que la passe aille jusqu'au report en
  déclaration.

---

## Le prompt

C'est la mécanique la plus particulière du régime, et celle où une erreur coûte
le plus longtemps : un déficit LMNP n'est **pas** imputable sur le revenu
global. Il ne s'impute que sur des **bénéfices de même nature** — des bénéfices
de location meublée non professionnelle — et il **périme au bout de dix ans**.

Un déficit mal suivi, c'est soit de l'impôt payé en trop pendant dix ans, soit
une déduction indue qui se voit au contrôle.

La table est `deficit_lmnp (annee_origine, montant_initial, solde,
annee_expiration)`, et le moteur est `traiter_deficit`, documenté « FIFO,
péremption 10 ans ».

### Ce que je te demande de chercher

**La péremption.**

- `annee_expiration` vaut `annee_origine + 10`. Est-ce le bon calcul ? Un
  déficit né en N est imputable sur les bénéfices des années N+1 à N+10 : la
  **dernière année utile** est-elle incluse ou exclue par la comparaison du
  code ?
- La purge : `WHERE annee_expiration < ?`. Un déficit dont l'expiration tombe
  **l'année en cours** est-il purgé avant ou après avoir eu sa chance d'être
  imputé ? Teste l'année pivot par exécution — c'est là que l'erreur d'un an se
  cache.
- Un déficit périmé est-il **supprimé** ou son solde mis à zéro ? S'il est
  supprimé, la trace de ce qui a été perdu disparaît-elle du suivi imprimé ?
- Le total des déficits affiché dans le PDF inclut-il les déficits **périmés** ?
  C'est une question ouverte laissée par une passe antérieure : si le total les
  inclut, le déclarant lit un stock imputable supérieur à la réalité.

**L'ordre d'imputation.**

- FIFO annoncé : le plus ancien d'abord. Vérifie-le par exécution sur trois
  déficits d'années différentes et un bénéfice qui n'en couvre qu'un et demi.
- Est-ce le bon ordre au regard du droit ? Imputer le plus ancien d'abord est
  favorable au contribuable puisque c'est celui qui périme le plus tôt —
  confirme que le code fait bien cela, et pas l'inverse.
- Un bénéfice **supérieur** au stock total : le reliquat de bénéfice est-il bien
  imposé ? Un bénéfice **inférieur** : les soldes sont-ils décrémentés
  exactement, sans reste d'arrondi ?

**La création du déficit.**

- `traiter_deficit(conn, annee, resultat_fiscal, …)` : un résultat fiscal
  **négatif** crée un déficit. De quel montant exactement — avant ou après
  réintégration des amortissements excédentaires, avant ou après le
  retraitement du fonds ALUR ?
- Un déficit peut-il être créé **deux fois** pour le même exercice — double
  clôture, clôture puis restauration puis re-clôture ? La table n'a pas de
  contrainte d'unicité sur `annee_origine` : vérifie ce qui l'empêche, et par
  exécution.
- Un exercice **bénéficiaire** peut-il créer un déficit par erreur de signe ?

**Le lien avec l'amortissement — le point le plus délicat.**

En LMNP, la fraction du déficit qui provient des **amortissements** ne suit pas
le même régime que celle qui provient des autres charges : l'amortissement
excédentaire est reporté sans limite de durée (article 39 C), le déficit
ordinaire périme à dix ans.

- Le logiciel distingue-t-il les deux, ou verse-t-il l'amortissement
  excédentaire dans le stock de déficits — où il périmerait à tort au bout de
  dix ans ?
- Inversement : un déficit ordinaire peut-il se retrouver dans le suivi 39 C, où
  il ne périmerait jamais — déduction indue ?
- C'est **le** constat à chercher en priorité dans cette passe. Décris le
  chemin exact, et chiffre la conséquence sur dix ans.

**Ce que la liasse et la déclaration en font.**

- Ligne **360** du 2033-B, « déficits antérieurs reportables, dont imputés sur
  le résultat » : servie ? Cohérente avec le stock ?
- Lignes **352** puis **370** : résultat fiscal avant puis après imputation des
  déficits. La 352 doit valoir **zéro** (choix assumé : le résultat LMNP est
  déclaré en 2031 bis). Que devient alors l'imputation des déficits — est-elle
  encore visible quelque part, ou disparaît-elle avec la mise à zéro ?
- Aide au report 2042-C-PRO : cases `5NA` (bénéfice) et `5NY` (déficit), plus
  les cases de déficits antérieurs. **Ces numéros n'ont jamais été vérifiés
  contre le formulaire.** Si je te joins le 2042-C-PRO, confronte-les un par un
  et dis lesquels sont faux. Sinon, signale-le en « non vérifiable » — ne les
  valide pas de mémoire.

### Points d'attention nommés

- Le PDF affiche « — périmé » à côté de l'année d'expiration mais reprend
  `total_deficits` tel quel. Vérifie que ce total et cette mention disent la
  même chose.
- Un déficit **reporté en arrière** (case 356) n'a pas de sens en LMNP : la case
  existe au formulaire, le logiciel la sert-il par erreur ?
- Le seuil de passage en **LMP** (loueur professionnel) change le régime du
  déficit, qui devient imputable sur le revenu global. Un contrôle
  `SEUIL_LMP` existe dans `controles.py` : sans ce fichier tu ne peux pas juger
  s'il protège réellement, mais signale si le moteur de déficits suppose le
  statut non professionnel **sans jamais le vérifier**.
