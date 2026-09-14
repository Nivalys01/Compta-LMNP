# Passe M — Le moteur de contrôles : auditer le garde-fou

**Joindre `00-INVARIANTS.md` avant ce prompt.**

## Pièces à joindre

| Fichier | Lignes |
|---|---|
| `modules/controles.py` | 814 — **27 contrôles** |
| `modules/audit_cycle.py` | 522 |
| `modules/gabarits.py` | 277 |
| `modules/fiscal.py` | 559 |
| `modules/parametres.py` | 191 |

---

## Le prompt

Cette passe est particulière : **la pièce auditée est elle-même un auditeur**.
`controles.py` porte 27 vérifications qui se déclenchent avant la clôture, et
c'est sur elles que l'utilisateur s'appuie pour croire sa comptabilité juste.

Un contrôle défaillant est plus dangereux qu'un contrôle absent, parce qu'on lui
fait confiance. C'est le registre attendu ici, et la règle 4 des invariants
s'applique à chaque ligne.

Les 27 codes sont : `EQUILIBRE`, `DOUBLON`, `REQUALIFIER`, `IMMOBILISABLE`,
`LOYER_MANQUANT`, `SENS`, `DATE_HORS_EXERCICE`, `COMPTE_ATTENTE`,
`MONTANT_INVALIDE`, `DUREE_ALLONGEE`, `AMORT_ANTERIEURS`, `DOTATION_PLAN`,
`COMPOSANT_SANS_AMORT`, `VENTILATION_INCOMPLETE`, `ALUR_ABSENT`,
`INTERETS_MAL_CLASSES`, `PERIODE_INCOHERENTE`, `ANNUEL_MULTIPLE`,
`CHARGE_ATTENDUE`, `POSTE_HABITUEL_ABSENT`, `TEOM_ABSENTE`, `LOYER_ATYPIQUE`,
`SEUIL_LMP`, `AN_ABSENTS`, `RETRAITEMENT_MANUEL_PLAFOND`, et les autres visibles
dans le fichier.

### Ce que je te demande de chercher

**Un contrôle qui ne peut pas se déclencher.**

Pour chacun des 27, établis par **exécution** qu'il se déclenche sur le cas
qu'il décrit. Cherche en particulier :

- un contrôle dont la condition est **inatteignable** — un `WHERE` sur un type
  d'opération qu'aucune règle ne produit, un compte absent du référentiel, un
  seuil jamais franchi ;
- un contrôle qui dépend d'une **table créée à la volée** : que renvoie-t-il si
  la table n'existe pas encore — rien, ou une erreur avalée ?
- un contrôle qui lit un **paramètre versionné** absent : la valeur par défaut
  est-elle sûre, ou rend-elle le contrôle muet ?
- un contrôle sur un **exercice vide** : silencieux à juste titre, ou silencieux
  par accident ?

**La gravité annoncée contre la gravité réelle.**

- `BLOQUANT` doit empêcher la clôture. Vérifie que `controler` + `bloquants`
  + la route de clôture forment bien une chaîne qui **refuse**, et que le
  `--forcer` / la case « Forcer » sont le seul contournement.
- Un contrôle classé `AVERTISSEMENT` alors que sa conséquence est un **chiffre
  faux sur la déclaration** est mal classé : signale-le. L'inverse aussi — un
  `BLOQUANT` sur un cas légitime rend le logiciel inutilisable et pousse à
  cocher « Forcer » par réflexe, ce qui désarme **tous** les autres.
- Combien de `BLOQUANT` un dossier ordinaire déclenche-t-il ? S'il y en a
  régulièrement, le blocage perd son sens.

**Les faux positifs et les faux négatifs.**

- `DOUBLON` : sur quels champs ? Deux loyers du même montant le même mois pour
  deux locataires différents sont légitimes.
- `LOYER_MANQUANT`, `CHARGE_ATTENDUE`, `POSTE_HABITUEL_ABSENT`, `TEOM_ABSENTE` :
  ces contrôles supposent un dossier « normal ». Que produisent-ils sur un
  premier exercice, un bien acquis en novembre, une maison sans copropriété, un
  logement vacant toute l'année ?
- `LOYER_ATYPIQUE` : par rapport à quoi — une moyenne, un historique ? Que
  produit-il quand il n'y a pas d'historique ?
- `SENS` compare le sens comptable à la nature. Depuis que l'import confronte
  déjà signe et nature, ce contrôle voit-il encore quelque chose, ou est-il
  devenu redondant — et si oui, dis-le, un contrôle mort entretient une fausse
  assurance.

**Le contrôle de l'équilibre.**

- `EQUILIBRE` est le plus fondamental. Sur quoi porte-t-il — chaque écriture, ou
  le total de l'exercice ? Un total équilibré peut masquer deux écritures
  déséquilibrées de sens opposé.
- Porte-t-il sur les à-nouveaux, sur les écritures d'un exercice clos, sur les
  écritures reprises d'un FEC externe ?

**L'audit de cycle.**

`audit_cycle.py` (522 lignes) exerce le cycle complet. Vérifie qu'il **échoue**
quand on casse quelque chose : introduis une erreur volontaire — une dotation
supprimée, un déficit périmé à tort, un plafond faussé — et regarde s'il le
voit. Un audit de cycle qui passe quoi qu'on fasse ne prouve rien.

### Points d'attention nommés

- `c_autres_a_requalifier` se fonde sur le drapeau `requalifier` des gabarits, et
  non sur un nom de type écrit en dur — c'est la bonne forme. Vérifie que les
  autres contrôles qui visent des types d'opération font de même, plutôt que
  d'énumérer des noms qui peuvent changer.
- `c_compte_attente` bloque sur un solde `472000` non apuré. Depuis que l'import
  y envoie tout ce qu'il ne reconnaît pas, ce contrôle est devenu le principal
  filet du logiciel : vérifie qu'il ne peut pas être **contourné** — solde à un
  centime près, compte d'attente à sept chiffres venu d'un FEC de cabinet,
  écriture d'attente dans un exercice antérieur.
- Le rapport de contrôles est imprimé dans le PDF de la liasse. Un contrôle qui
  s'exécute mais dont le résultat n'est **pas rendu** est un défaut déjà
  rencontré trois fois sur ce logiciel : cherche-le ici aussi.
