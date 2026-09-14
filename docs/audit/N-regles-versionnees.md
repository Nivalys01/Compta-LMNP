# Passe N — Règles fiscales versionnées et veille

**Joindre `00-INVARIANTS.md` avant ce prompt.**

## Pièces à joindre

| Fichier | Lignes |
|---|---|
| `modules/parametres.py` | 191 |
| `modules/veille_fiscale.py` | 246 |
| `modules/gabarits.py` | 277 |
| `modules/pense_bete.py` | 550 |
| `schema.sql` (tables `regle_fiscale`, `meta`, `gabarit_personnalise`) | — |

---

## Le prompt

Un logiciel fiscal a une particularité : **le droit change et le logiciel
reste**. Un utilisateur qui clôture 2026 en 2029 doit obtenir les règles de
2026, pas celles de 2029.

Le logiciel porte ce mécanisme dans `parametres.py` : une table `regle_fiscale`
où chaque règle a une **date d'effet**, et `valeur(conn, cle, annee, defaut)`
qui rend la version en vigueur pour l'exercice visé. `veille_fiscale.py` invite
l'utilisateur à vérifier périodiquement.

### Ce que je te demande de chercher

**La bonne version pour le bon exercice.**

- `valeur(conn, cle, annee, defaut)` : quelle version rend-elle exactement ? La
  règle « en vigueur à la clôture de l'exercice », « au 1ᵉʳ janvier », « à la
  date de l'opération » ? Les trois donnent des résultats différents l'année
  d'un changement — établis lequel le code applique, par exécution, sur une
  règle qui change au 1ᵉʳ juillet.
- Deux versions d'une même règle dont les intervalles **se chevauchent** ou
  laissent un **trou** : que rend `valeur` ? `definir` clôt la version
  précédente « à la veille de la date d'effet » — vérifie qu'un chevauchement
  est impossible, y compris si l'utilisateur saisit deux versions dans le
  désordre chronologique.
- Une règle **absente** : le `defaut` du code s'applique. Est-il annoncé à
  l'utilisateur, ou le calcul se fait-il silencieusement sur une valeur que
  personne n'a validée ? Le `seuil_immobilisation` vaut 500 € par défaut — si la
  table est vide, le déclarant le sait-il ?
- Une valeur **aberrante** saisie par l'utilisateur — seuil négatif, nul,
   10 000 000 — est-elle refusée ?

**L'effet rétroactif involontaire.**

C'est le risque principal de ce mécanisme.

- Modifier une règle **après** avoir clos un exercice : la liasse de cet
  exercice change-t-elle ? Elle ne doit pas — `cloture_fiscale` fige les
  retraitements. Vérifie-le par exécution : clos 2026, modifie le seuil, rouvre
  la liasse 2026 et compare.
- Les contrôles d'un exercice clos utilisent-ils la règle du millésime, ou la
  règle courante ?
- L'import bancaire lit le seuil au **millésime de l'opération** — vérifie que
  les autres consommateurs de règles font de même, et pas tous la même chose.

**Les gabarits personnalisés.**

- `ajouter_personnalise` permet de créer une catégorie sans toucher au code.
  Le compte visé doit exister au plan : vérifié ? Et si le compte est **supprimé**
  ensuite ?
- Une clé qui collisionne avec un gabarit standard est refusée. Et une clé qui
  collisionne avec un gabarit **désactivé** (`actif=0`) ?
- La `nature` est contrainte à `produit`/`charge`. Un gabarit personnalisé
  pointant un compte de **classe 1 ou 4** est-il cohérent — et que produit-il
  dans le résultat, sachant que l'agrégation se fait par classe ?
- `assurer_table` ne committe plus si une transaction est ouverte. Vérifie que
  `ajouter_personnalise` et `_personnalises` respectent le même contrat, et
  qu'aucun autre chemin de **lecture** ne committe. *(C'est un défaut qui a déjà
  rompu l'atomicité d'un import — voir règle 2 des invariants.)*

**La veille.**

- `veille_fiscale.py` s'appuie sur la table `meta`. Que se passe-t-il si la date
  de dernière veille est absente, dans le futur, ou illisible ?
- La veille **rappelle** de vérifier. Est-ce qu'elle vérifie quoi que ce soit
  elle-même, ou est-ce un pense-bête ? Si c'est un pense-bête, le document le
  dit-il clairement — un utilisateur pourrait croire que le logiciel se met à
  jour seul.
- Y a-t-il une liste des règles **à surveiller** ? Est-elle complète au regard
  de ce que le logiciel calcule — seuil d'immobilisation, durées
  d'amortissement, seuil LMP, plafond 39 C, taux de prélèvements sociaux ?
  Signale les paramètres **codés en dur** qui devraient être versionnés.

### Points d'attention nommés

- Cherche les **constantes fiscales en dur** dans tout le code joint : un taux,
  un seuil, une durée, un nombre d'années de report. Chacune est une bombe à
  retardement le jour où le droit change. La péremption des déficits à **dix
  ans** en est un cas : versionnée ou en dur ?
- `pense_bete.py` (550 lignes) porte des rappels métier. Les échéances y
  sont-elles calculées, ou écrites en dur pour une année donnée ? Un rappel daté
  de 2026 dans un logiciel utilisé en 2029 est pire qu'aucun rappel.
- Une règle versionnée dont la date d'effet est **antérieure** au premier
  exercice du dossier : prise en compte ou ignorée ?
