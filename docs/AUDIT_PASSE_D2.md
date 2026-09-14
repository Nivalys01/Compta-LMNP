# Revue passe D2 — couche web et ligne de commande

Périmètre : `app.py` (2 015 lignes, 50 routes), `cli.py` (221 lignes), et
`pages.py` là où il porte du comportement.

## Ce que cette revue est, et ce qu'elle n'est pas

La passe D (v8.40.0 / v8.41.0) avait relevé **29 constats, dont 9 critiques**.
Les neuf critiques ont été traités ; **les 20 autres n'ont laissé aucune
trace** — ni liste, ni numérotation, ni test. Ils sont perdus.

Cette revue ne les reconstitue pas : c'est impossible. Elle repart des deux
fichiers tels qu'ils sont aujourd'hui. Le recouvrement avec D-10…D-29 est donc
**partiel et inconnaissable** — trois constats ci-dessous correspondent aux
trois exemples dont l'auteur se souvenait, le reste est à prendre pour ce qu'il
est : un état des lieux daté, pas un solde de comptes.

Les constats sont numérotés **D2-xx** pour ne pas se confondre avec ceux de la
passe D.

## Vérification préalable : les 9 critiques de la passe D tiennent

| # | Correctif annoncé | Localisation |
|---|---|---|
| D-01 | confirmations JS cassées | `app.py:480,487` — gestionnaire délégué sur `data-confirmer`, le texte ne passe plus par un littéral JS |
| D-02 | bac à sable partageant les répertoires | `app.py:1452` `perennite.dossier_sauvegardes(_db_path())` ; `imports_tmp` indexé sur le `stem` |
| D-03 | cookie du bac à 8 h | trois `set_cookie("dossier", …)`, tous en `max_age=180*24*3600` |
| D-04 | `cli.py` sans dossier configurable | `cli.py:170` `--dossier SLUG`, `COMPTA_DB`, et `_annoncer_base()` |
| D-05 | `cloturer` sans sauvegarde | `cmd_cloturer` sauvegarde — **mais pas entièrement, voir D2-02** |
| D-07 | migration hors démarrage | `app.py:103` `_migrer_si_besoin()` |
| D-08 | dossier récent verrouillant tout | `app.py:135-137`, exemption de `/dossiers/retour-principal` |
| D-09 | dossier absent → base vierge | `FichierDossierAbsent` : classe 252, levée 278, `errorhandler` 981 |

---

## 1. Critique

### D2-01 — Aucune protection CSRF, et l'absence de cookie vise le dossier RÉEL

**Fichier / fonction** : `app.py`, les 30 routes `POST` ; `_dossier_actif()`
lignes 237-250.

**Scénario** — l'utilisateur a le logiciel ouvert et visite, dans le même
navigateur, une page quelconque qui contient :

```html
<form action="http://localhost:5000/cloturer" method="POST">
  <input type="hidden" name="annee" value="2026">
  <input type="hidden" name="forcer" value="1">
</form><script>document.forms[0].submit()</script>
```

**Attendu** : la requête est refusée — jeton absent, ou `Origin` étranger.

**Produit** (sortie réelle, client de test sans cookie, sans `Referer`, sans
jeton) :

```
dossier visé sans cookie : principal
POST /saisir            -> 302
opérations en base      -> 1   (écriture acceptée sans contrôle d'origine)
POST /cloturer          -> 302 | exercice 2026 : ('clos',)
```

**L'exercice a été clôturé par une requête d'origine inconnue.** Il n'y a
aucun jeton de formulaire, aucun contrôle de `Origin` ni de `Referer` : la
recherche de `csrf`, `Origin`, `Referer` dans `app.py` rend **0**.

Deux aggravations propres à ce logiciel :

1. **`samesite="Lax"` n'aide pas, il nuit.** Lax empêche l'envoi du cookie
   `dossier` sur un POST inter-site — donc `_dossier_actif()` ne trouve rien
   et **retombe sur `PRINCIPAL`**. Une requête forgée ne peut pas viser le bac
   à sable : elle vise toujours la comptabilité réelle.
2. **Les routes concernées sont destructrices** :
   `/sauvegardes/restaurer` (remplace la base), `/cloturer` (irréversible),
   `/operation/<id>/annuler`, `/immobilisations/bien/<id>/ceder`,
   `/bac-a-sable/reset`, `/exercice/reprendre-fec`. Aucune ne demande de
   connaître les données de l'utilisateur : un formulaire caché suffit.

**Conséquence** : le modèle de menace du logiciel repose sur
« `host="127.0.0.1"`, l'application n'est jamais exposée au réseau local »
(commentaire ligne 2014). C'est exact pour le réseau, **et sans effet pour le
navigateur** : toute page ouverte dans le même navigateur peut poster sur
localhost. La liaison locale protège des autres machines, pas des autres
onglets.

**Gravité : critique.** C'est le seul constat de cette revue qui ouvre une
porte depuis l'extérieur.

**CORRIGÉ** — `_garde_origine()`, un `before_request` qui refuse en **403**
toute méthode d'écriture dont l'origine annoncée diffère de celle du
logiciel. Reproduit après correctif : `POST /cloturer` depuis
`http://evil.example` rend 403, l'exercice reste ouvert, et le refus est
journalisé.

Règle retenue, et son revers assumé : une origine **présente et différente**
est refusée ; une origine **absente** est acceptée. Ce second point est
délibéré — curl, la ligne de commande et le client de test n'envoient ni
`Origin` ni `Referer`, et les exiger ferait du contrôle un obstacle sans rien
gagner : un navigateur envoie **toujours** `Origin` sur un POST inter-site
(« null » si la politique de référent le masque, ce qui est refusé aussi).
Un jeton par formulaire serait plus orthodoxe, mais toucherait les 30 routes
et tous les gabarits pour couvrir le même scénario.

Sept tests figent le comportement, dont celui qui fige le choix ci-dessus
pour qu'il ne passe pas pour un oubli.

---

## 2. Majeur

### D2-02 — La clôture en ligne de commande n'archive pas le FEC, et son commentaire affirme le contraire

**Fichier / fonction** : `cli.py::cmd_cloturer`, lignes 122-131.

Le commentaire, en tête de la fonction :

> *« La clôture web prend une sauvegarde et archive le FEC ; la version en
> ligne de commande ne faisait ni l'un ni l'autre. Même opération, même
> irréversibilité, même piste d'audit à conserver. »*

**Produit** : `perennite.sauvegarder()` est bien appelé. `archiver_fec`
**n'apparaît pas une seule fois dans `cli.py`** — 0 occurrence, contre 1 dans
`app.py`.

Le correctif de D-05 a donc été appliqué **à moitié**, et le commentaire
décrit l'intention comme si elle était tenue. Une clôture faite en ligne de
commande ne laisse aucune trace dans `archives/` ni aucune ligne dans
`manifeste.csv` : **la piste d'audit — FEC figé et son empreinte SHA-256 —
est absente pour tout exercice clos hors de l'interface web.**

*Rapprochement proposé, à confirmer* : l'auteur se souvient d'un constat D
formulé « colonne d'empreintes SHA-256 toujours vide ». Aucune colonne de ce
genre n'existe au schéma (15 tables, 105 colonnes vérifiées, zéro orpheline).
Il est possible que le constat visait ceci : l'empreinte n'est jamais
enregistrée pour une clôture CLI.

**Gravité : majeur.** Un commentaire qui affirme un correctif absent est pire
qu'un correctif manquant : il empêche de le retrouver.

---

### D2-03 — La clôture web est validée en base avant l'archivage, et un échec d'archivage se présente comme un échec de clôture

**Fichier / fonction** : `app.py::cloturer`, lignes 1136-1152.

L'ordre est : sauvegarde → `fiscal.cloturer(conn, annee)` → `archiver_fec()`.
Or `fiscal.cloturer` **committe** (`fiscal.py:555`).

**Scénario** : le disque est plein, ou `archives/` n'est pas accessible en
écriture, au moment de l'archivage.

**Attendu** : ou bien la clôture est annulée, ou bien l'utilisateur apprend
que l'exercice EST clos mais que l'archive manque.

**Produit** : `except Exception as exc` rend
`redirect(url_for("cloture", err=str(exc)))`. L'utilisateur lit un message
d'erreur — et l'exercice est clos. Il relancera la clôture, qui échouera pour
une autre raison (exercice déjà clos), sans jamais comprendre.

**Gravité : majeur** (probabilité faible, confusion totale).

---

### D2-04 — La validation d'un import n'est pas transactionnelle

**Fichier / fonction** : `app.py::import_valider`, boucle ligne 1783.

C'est l'un des trois constats dont l'auteur se souvenait. Confirmé :

```
BEGIN/savepoint/rollback dans import_valider : False
operations.saisir committe à chaque appel     : True
```

`operations.saisir` fait un `conn.commit()` par opération (`operations.py:81`).
Un échec à la 7ᵉ ligne sur 10 laisse **les six premières en base**, sans
retour arrière. L'`except Exception` rend « Import interrompu : … » alors que
l'import est partiellement fait — et rien ne dit où il s'est arrêté.

**Conséquence** : l'utilisateur relance l'import, et les six premières lignes
sont saisies **deux fois**. Aucune clé d'idempotence n'existe côté import
(constat déjà relevé au §5 de la passe E).

**Gravité : majeur.**

---

### D2-05 — Le plan des comptes d'immobilisation vit dans la couche web, et la connaissance est dispersée

**Fichier / fonction** : `app.py:293` — `COMPTES_IMMO`.

```python
COMPTES_IMMO = [
    ("211550", "Terrain",                   None),
    ("213150", "Bâtiment",                  "281315"),
    ("218100", "Installation / agencement", "281810"),
    ("218400", "Mobilier",                  "281840"),
]
```

Troisième constat dont l'auteur se souvenait — confirmé, et **plus large que
« dupliqué quatre fois »**. Le couple immobilisation → amortissement est
exprimé dans **dix fichiers** : `app.py`, `liasse.py` (`RUBRIQUES_2033C`),
`pages.py`, `amortissement.py`, `operations.py`, `controles.py`, `cession.py`,
`schema.sql`, `seed_referentiel.sql`, `audit_cycle.py`.

**Conséquence** : ajouter un compte d'immobilisation — un agencement sur un
compte 2181 distinct, un véhicule — demande de penser à dix endroits, dont
aucun ne référence les autres. Le risque n'est pas l'oubli d'un seul : c'est
qu'un oubli reste invisible, chaque module continuant de fonctionner avec sa
propre vue partielle.

**Gravité : majeur** (dette, pas défaut : rien n'est faux aujourd'hui).

---

### D2-06 — La garde de migration n'est pas atomique sur un serveur threadé

**Fichier / fonction** : `app.py::_migrer_si_besoin`, lignes 112-114.

```python
if chemin in _MIGRES:
    return
_MIGRES.add(chemin)
```

Le test et l'ajout sont deux opérations. Le serveur de développement Flask est
**threadé par défaut**, et un navigateur ouvre plusieurs requêtes en parallèle
sur la première page : deux threads peuvent évaluer le test à faux avant que
l'un n'ajoute, et **lancer deux migrations concurrentes** sur la même base —
chacune prenant sa propre sauvegarde, chacune appliquant ses paliers.

Les paliers sont idempotents, ce qui limite les dégâts ; mais deux sauvegardes
« avant-migration » horodatées à la seconde peuvent se recouvrir, et deux
écritures concurrentes sur SQLite donnent un `database is locked` au premier
chargement de page — sur le chemin le plus sensible du logiciel.

**Attendu** : un verrou, ou `_MIGRES` alimenté avant tout travail sous un
`threading.Lock`.

**Gravité : majeur** par l'emplacement, faible par la probabilité.

---

## 3. Mineur

### D2-07 — Les apostrophes sont retirées du texte utilisateur pour contourner un littéral JS

**Fichier** : `pages.py:906`.

```html
onsubmit="return confirm('Passer l écriture de reprise ? Le résultat de
l exercice n est pas modifié : seul le bilan est corrigé.')"
```

Trois apostrophes manquantes dans une phrase que l'utilisateur lit. Le
correctif de fond existe depuis D-01 — le gestionnaire délégué sur
`data-confirmer` — mais n'a pas été appliqué ici : c'est un contournement du
symptôme, et il subsiste. `pages.py:739` est dans le même cas, sans apostrophe
à supprimer.

**Gravité : mineur**, correctif trivial et à fort rendement : ces deux
confirmations restent les seules à pouvoir se casser à la prochaine
reformulation.

---

### D2-08 — RETIRÉ : le constat était faux

**Énoncé initial** : « cinq colonnes du FEC ne sont jamais renseignées, dont
`valid_date` sur un exercice clos ».

**Il est faux, et la partie qui portait un enjeu fiscal l'était entièrement.**
`valid_date` **est** écrite — `ecritures.py:183`, dans la liste de colonnes de
l'`INSERT` — et l'export la restitue (`export_fec.py:55`). Vérifié de bout en
bout : un FEC exporté par le logiciel porte bien sa `ValidDate`
(`20260305`) et **passe son propre validateur sans une anomalie.**

L'erreur venait de ma méthode : j'avais cherché `INSERT|UPDATE|SET` et le nom
de colonne **sur la même ligne**, alors que l'`INSERT` d'`ecritures.py` s'étale
sur plusieurs. Le contrôle refait correctement donne :

| Colonne | Écrite par un INSERT |
|---|---|
| `valid_date` | **oui** |
| `ecriture_let`, `date_let` | non |
| `montant_devise`, `idevise` | non |

Restent donc quatre colonnes vides — le **lettrage** et la **devise**. Toutes
quatre sont facultatives au FEC quand l'usage ne s'y prête pas : une
comptabilité LMNP en euros, sans lettrage, les laisse légitimement vides. Ce
n'est pas un défaut.

**Constat annulé.** Il est conservé ici, et non supprimé, pour que le
récapitulatif reste honnête : une revue qui efface ses erreurs ne se relit pas.

## 4. Ce qui a été vérifié et tenu

1. **Liaison strictement locale.** `app.run(host="127.0.0.1")`, commenté. Le
   `debug` n'est pas activé par défaut.
2. **`/archives/<nom>` ne permet pas de traversée.** Le nom est réduit à son
   `basename` et l'extension est contrôlée (`.txt`) avant `send_file`.
3. **Le cookie de dossier n'est jamais utilisé comme chemin.**
   `_dossier_actif()` le valide contre le registre et retombe sur le principal
   pour tout slug inconnu — le commentaire le dit explicitement. C'est propre ;
   c'est le repli lui-même qui devient un problème avec D2-01.
4. **Le jeton d'import est contrôlé.** `re.fullmatch(r"[0-9a-f]{32}")` plus
   `os.path.basename` : le chemin du fichier temporaire n'est pas forgeable.
5. **Le journal d'erreurs est rotatif et local** (512 Ko × 3), sans aucun
   envoi réseau.
6. **`cli.py init` ne peut pas écraser une base tenue** : `init_db.init` est
   appelé sans `ecraser`, donc le refus de la passe B s'applique.
7. **Le FEC de référence passé par `cli.py` retombe sur le jeu anonymisé**
   quand le dossier privé est absent (`init_db` teste l'existence du fichier,
   pas seulement la présence d'une chaîne).

---

## 5. Non vérifiable avec les pièces fournies

- **Le recouvrement avec D-10…D-29.** Trois des huit constats ci-dessous
  correspondent aux exemples mémorisés (D2-04, D2-05, et peut-être D2-02). Des
  cinq autres, impossible de dire s'ils étaient déjà dans la passe D.
- **`pages.py` n'a été lu que partiellement** (2 357 lignes) : seuls les
  endroits portant du comportement — confirmations, formulaires — ont été
  examinés. Les gabarits eux-mêmes n'ont pas été revus.
- **Le comportement réel sous charge** (D2-06) n'a pas été provoqué : la
  course est établie par lecture, pas par exécution.
- **Les colonnes de lettrage et de devise** : leur caractère facultatif au
  regard de l'arrêté A47 A-1 relève d'un avis, pas d'une lecture de code — mais
  la conformité du FEC produit, elle, est établie : le validateur du projet
  l'accepte sans anomalie.

---

## Récapitulatif

| # | Constat | Fichier | Gravité |
|---|---|---|---|
| D2-01 | Aucune protection CSRF ; sans cookie, la requête vise le dossier réel | app.py | Critique — **corrigé** |
| D2-02 | Clôture CLI sans archivage FEC | cli.py | Majeur — **corrigé** |
| D2-03 | Un échec d'archivage passait pour un échec de clôture | app.py | Majeur — **corrigé** |
| D2-04 | Validation d'import non transactionnelle | app.py | Majeur — **corrigé** |
| D2-05 | Plan immo/amort dans la couche web, dupliqué | app.py | Majeur — **corrigé** |
| D2-06 | Garde de migration non atomique | app.py | Majeur — **corrigé** |
| D2-07 | Apostrophes retirées du texte utilisateur | pages.py | Mineur — **corrigé** |
| D2-08 | Une lecture terminait la transaction de l'appelant | gabarits, parametres | Majeur — **corrigé** |
| D2-09 | Le paquet n'embarquait pas un module nouveau | construire_distribution | Critique — **corrigé** |
| ~~D2-08~~ | ~~Colonnes du FEC jamais renseignées~~ — **constat annulé, il était faux** | — | — |

**Lecture d'ensemble.** La couche web est nettement plus soignée que ne le
laissait craindre l'absence de trace : les gardes sont documentées, le cookie
est validé, le chemin d'archive est assaini, et les neuf critiques de la
passe D tiennent tous. Les défauts qui restent sont d'une autre nature que
ceux des passes E et F : non plus des chiffres faux ou des fuites, mais des
**opérations qui s'arrêtent au milieu** — un import à moitié inséré, une
clôture faite mais annoncée en échec, une piste d'audit absente d'un chemin
sur deux.

Une exception, et c'est le seul constat critique : **D2-01 est la première
faille de cette revue qui vienne de l'extérieur.** Le raisonnement
« `127.0.0.1`, donc pas exposé » est juste pour le réseau et faux pour le
navigateur. Il tient par la liaison locale, alors que ce qui le menace est
dans le même navigateur que l'utilisateur.

---

## Complément — import d'un FEC de cabinet (classes 1 à 7)

Ajouté après coup, sur demande : le bilan sans comptes de tiers est un choix
assumé, mais un FEC remis par un cabinet en contient toujours. Le plan de test
est calqué sur un bilan LMNP **réellement établi par un cabinet** : numéros à
**sept chiffres** (`5120100` banque, `6811000` dotation, `1640000` emprunt,
`4110100` locataire), là où le plan livré en compte six. Montants et identité
fictifs.

### D2-09 — Un compte de charge hors des préfixes énumérés disparaît de la liasse

**Fichier / fonction** : `liasse.resultat_2033b`.

`liasse` **énumérait** des préfixes de classe 6 — `60/61/62` → 242, `63` → 244,
`66` → 294, `67` → 300 — plus le **seul compte** `681120` pour la case 254. Or
`fiscal.agregats` prend **toute la classe 6**. Les préfixes `64`, `65`, `68`
hors `681120` et `69` n'atterrissaient donc dans **aucune case**.

**Scénario** : un cabinet porte sa dotation en `6811000`.

**Produit** (sorties réelles, avant correctif) :

```
dotation du cabinet (6811000)      : 12000.00
case 254 rend                      :     0.00
fiscal.agregats resultat_comptable : -14767.99
liasse case 310                    :  -2767.99
écart                              :  12000.00
```

**Les 12 000 € ne figuraient nulle part au 2033-B** — ni en 254, ni en 242, ni
en 244 — tout en pesant sur le résultat. Les deux modules qui calculent le
résultat divergeaient d'exactement le montant ignoré, et rien ne le signalait :
le contrôle d'équilibre du bilan compare `immo_net` à lui-même, il ne peut pas
le voir.

C'est le raisonnement du constat E-20 — *« les trois blocs sont soustraits du
total plutôt qu'énumérés par préfixe : un compte oublié dans l'énumération
sortirait du résultat en silence »* — appliqué aux produits et **jamais porté
sur les charges**.

**Corrigé** : `total_charges_264` vaut désormais la classe 6 entière moins le
financier et l'exceptionnel ; les cases 250 (personnel) et 262 (autres charges)
sont servies et imprimées, 262 recueillant le reste. Ce qui n'est pas reconnu
**retombe dans une case visible** au lieu de s'évaporer. Après correctif :
case 254 = 12 000 €, écart entre les deux modules = **0,00 €**.

**Gravité : critique** — c'était le seul défaut de cette série à falsifier un
chiffre reporté par le déclarant.

### D2-10 — Le type de la classe 4 contredisait le plan livré

Traité dans le même lot : `fec_io.type_du_compte` rangeait **toute** la classe 4
au passif, si bien qu'un compte auxiliaire de locataire (`4110100`) était créé
comme une **dette** alors que le plan livré déclare `411000` à l'**actif**. Les
tranches sans ambiguïté sont désormais tranchées — 40, 42, 43 au passif, 41 à
l'actif. Les tranches mixtes par construction (44 État, 45 associés, 46 divers,
48 régularisation) restent au repli : c'est le sens du solde qui décide, pas le
numéro.

### D2-11 — Un PDF comptable réel pouvait être publié sans un mot

Trouvé en cherchant le document de référence : un bilan établi par un cabinet
séjournait **à la racine du dépôt**, ni suivi ni ignoré. Un `git add -A`
l'aurait publié, et le contrôle **n'aurait rien dit** : le texte d'un PDF est
compressé, la recherche d'empreintes n'y trouve rien — elle ne échoue pas, elle
ne trouve rien, ce qui est pire.

**Corrigé** en deux temps : les documents déposés à la racine (`/*.pdf`,
`/*.docx`, `/*.xlsx`, `/*.odt`) sont exclus par principe ; et
`verifier_depot` signale désormais en **AVERTISSEMENT** tout format dont il ne
peut pas inspecter le contenu, au lieu de le traverser en silence. Même famille
que F-01 : un contrôle qui ne peut pas travailler doit le dire.

### Ce qui tient, et ce qui reste

**Tient.** L'import lui-même est solide : les 19 comptes du plan de cabinet
sont créés avec le bon type et la bonne classe, l'équilibre est préservé au
centime, le FEC à sept chiffres passe le validateur, et un produit de classe 79
(transferts de charges) retombe bien en exploitation.

**Limite assumée, figée par un test.** La case 243 « dont CFE et CVAE » est lue
sur le compte du plan livré (`635110`). Un cabinet numérote autrement —
`6351200` relevé sur le bilan réel — et **aucun préfixe ne distingue la CET des
autres impôts directs**. La case reste donc vide alors que la CET a été payée.
Ce n'est pas corrigeable sans une correspondance de plans ; le test
`test_la_case_243_reste_a_zero_sur_un_plan_de_cabinet` fige la limite pour
qu'elle ne passe pas pour un succès.

**Toujours ouvert — E-22.** L'emprunt de 96 000 €, la banque et les tiers du
FEC de cabinet sont bien en base, et n'apparaissent dans aucune case du bilan :
le 2033-A ne retient que les immobilisations. C'est le choix de modèle assumé,
et le test le dit explicitement.

Non-régression : `tests/test_import_cabinet.py`, 22 tests.

---

## Suivi des correctifs — D2-02 à D2-07 traités, deux constats nouveaux

### Les six constats sans échéance

**D2-02 — la clôture en ligne de commande archive le FEC.** Elle prenait la
sauvegarde et n'archivait rien, alors que son propre commentaire affirmait le
contraire. Vérifié par exécution : la clôture CLI rend désormais le chemin de
l'archive **et l'empreinte SHA-256 consignée au manifeste**.

**D2-03 — un échec d'archivage n'est plus un échec de clôture.** `fiscal.cloturer`
committe : l'archivage qui suit a son propre `try`, et son échec produit un
**avertissement sur une clôture réussie**, nommant l'archive manquante et la
marche à suivre. Auparavant, l'utilisateur lisait « erreur », relançait, et se
heurtait à « exercice déjà clos » sans comprendre.

**D2-04 — la validation d'import est tout ou rien.** `operations.saisir` accepte
`commit=False` ; la boucle valide une fois, et `rollback` en cas d'échec. Le
message dit **où** l'import s'est arrêté et que **rien** n'a été écrit.

**D2-05 — le plan des immobilisations a une source unique.** `modules/plan_immo.py`
remplace la table qui vivait en dur dans `app.py` — couche web — ET dans
`liasse.py`, sans que l'une référence l'autre. Un test vérifie qu'ajouter un
compte n'exige qu'un seul endroit.

**D2-06 — la garde de migration est atomique.** `threading.Lock` autour du test
et de l'ajout.

**D2-07 — les confirmations ne mutilent plus le texte.** Les deux dernières
passent par `data-confirmer` : « Passer l'écriture de reprise ? » a retrouvé
ses apostrophes.

### D2-08 — Une fonction de lecture terminait la transaction de l'appelant

**Trouvé en vérifiant D2-04, et plus profond que lui.**

`gabarits.assurer_table` committait inconditionnellement. Or `gabarit()` — appelée
à **chaque** saisie — y passe. Tout appelant travaillant en `commit=False` voyait
donc sa transaction terminée sous ses pieds : à la deuxième saisie la première
était committée, et un `rollback` n'annulait plus que la dernière ligne.

```
après saisie 1   in_transaction=True   opérations=1
après saisie 2   in_transaction=True   opérations=2
après rollback   in_transaction=False  opérations=1   ← une survit
```

**Le tout-ou-rien de D2-04 était donc faux malgré le correctif**, et seule la
vérification par EXÉCUTION l'a montré : un test qui relit le code aurait conclu
au succès. `parametres.assurer` portait le même défaut, sur le même chemin de
lecture. Les deux ne committent plus si une transaction est déjà ouverte — le
`CREATE TABLE IF NOT EXISTS` est transactionnel en SQLite, il peut voyager dans
celle de l'appelant.

**Gravité : majeur.** Le contrat `commit=False` existait depuis la passe B, où il
avait été introduit pour rendre la clôture atomique face à une coupure de
courant. Il était silencieusement rompu.

### D2-09 — Le paquet n'embarquait pas un module nouveau

**Trouvé en décompressant le paquet ailleurs, pas par la suite de tests.**

`MODULES_PROD` était une liste écrite à la main. Le jour où `plan_immo.py` a été
créé, le paquet s'est construit **sans une erreur** et l'application a échoué à
l'import **chez le client** :

```
ModuleNotFoundError: No module named 'plan_immo'
```

La garde « PAQUET INCOMPLET » ne couvre pas ce cas : elle ne vérifie que les
fichiers cités par les **lanceurs**. C'est le défaut de principe de F-03,
resurgi ailleurs — *une liste rédigée à la main ne peut pas signaler ce qu'on a
oublié d'y mettre.*

Le répertoire `modules/` est désormais **lu**, pas énuméré, et un test compare
le contenu du zip au contenu du disque.

**Gravité : critique** — le paquet livré ne démarrait pas.

### Vérifications

- **730 tests** sur ce poste, **584 passés / 148 ignorés** sur un clone sans
  dossier privé, `ruff` propre.
- Paquet construit (45 fichiers, 27 modules), **décompressé ailleurs et
  démarré** : c'est l'installation du client qui est éprouvée.
- Clôture en ligne de commande exécutée sur cette copie : sauvegarde, FEC
  archivé, empreinte au manifeste.
