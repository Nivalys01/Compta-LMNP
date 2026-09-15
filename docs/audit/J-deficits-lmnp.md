# Passe J — Déficits LMNP : report, péremption, imputation

**Joindre `00-INVARIANTS.md` avant ce prompt.**

## Pièces à joindre

| Fichier | Lignes |
|---|---|
| `modules/fiscal.py` | 559 |
| `modules/liasse.py` | 647 |
| `modules/liasse_pdf.py` | 447 |
| `schema.sql` (table `deficit_lmnp`) | — |

Les deux formulaires sont à la racine du dépôt :

- **2033-SD 2026** (`2033-sd_5394.pdf`) ;
- **2042-C-PRO** (`2042_Cpro.pdf`) — section « REVENUS DES LOCATIONS MEUBLÉES
  NON PROFESSIONNELLES », page 5.

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
- Aide au report 2042-C-PRO. Les trois familles de cases émises par
  `liasse.aide_2042c` **existent bien** au formulaire, sous « Régime du
  bénéfice réel » de la section location meublée non professionnelle — relevé
  fait sur le PDF joint, pas de mémoire :

  | Code | Libellé au formulaire |
  |---|---|
  | `5NA` | Revenus imposables cas général |
  | `5NY` | Déficits cas général |
  | `5GA` … `5GJ` | Déficits des années antérieures non encore déduits (dix cases) |

  Ce qui reste à confronter, et c'est là que porte l'enjeu :

  - **L'appariement case ↔ millésime.** Le code pose `origine = annee - 10 + i`,
    soit `5GA` = N-10 … `5GJ` = N-1. Le formulaire imprime les années **en
    clair** sous les cases : confronte-les une à une pour l'exercice visé. Un
    décalage d'un rang fait déclarer un déficit sous le millésime du voisin, et
    la péremption est calculée sur ce millésime.
  - **Le déclarant.** Les colonnes `5Ox` et `5Px` visent le déclarant 2 et une
    personne à charge. Le logiciel n'émet que la première colonne : est-ce dit
    au déclarant, ou peut-il croire que le report est complet pour un couple ?
  - **Les cases voisines à ne pas confondre** : `5NM` (revenus soumis aux
    cotisations sociales par un organisme de sécurité sociale), `5WE` (déficits
    relevant de ces organismes), `5NG`/`5NH`/`5NI` (régime **micro**). Le
    logiciel peut-il produire un montant qui relèverait de l'une d'elles sans le
    signaler — meublé de tourisme classé, chambre d'hôtes, affiliation SSI ?
  - **La durée d'exercice** (`5CD`) et la **cession ou cessation** (`5CF`) :
    servies par le logiciel, ou laissées au déclarant sans un mot ? Un exercice
    de moins de douze mois change le calcul.

### Points d'attention nommés

- Le PDF affiche « — périmé » à côté de l'année d'expiration mais reprend
  `total_deficits` tel quel. Vérifie que ce total et cette mention disent la
  même chose.
- Un déficit **reporté en arrière** (case 356) n'a pas de sens en LMNP : la case
  existe au formulaire, le logiciel la sert-il par erreur ?
- Le formulaire distingue explicitement les revenus **professionnels** (page 4,
  cases `5KP` et suivantes) des **non professionnels** (page 5). Le seuil de
  passage en **LMP** change donc de page ET de régime : le déficit devient
  imputable sur le revenu global. Un contrôle
  `SEUIL_LMP` existe dans `controles.py` : sans ce fichier tu ne peux pas juger
  s'il protège réellement, mais signale si le moteur de déficits suppose le
  statut non professionnel **sans jamais le vérifier**.
