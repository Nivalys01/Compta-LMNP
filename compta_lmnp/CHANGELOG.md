# Journal des versions — Compta LMNP

## 8.51.1 — 2026-09-16 (Un outil externe absent doit se nommer lui-même)

**Cinq tests de la passe J tombaient en `FileNotFoundError: 'pdftotext'`.**
Quatre fichiers de tests relisent le texte des PDF produits ; trois s'étaient
protégés par un `@pytest.mark.skipif` recopié à la main, le quatrième n'avait
rien. Trois gardes écrites à la main et un oubli : le motif exact de
l'invariant n°5 — une liste tenue à la main ne peut pas signaler ce qu'on a
oublié d'y inscrire. La règle n'est donc plus écrite qu'à un seul endroit,
`conftest.exiger_pdftotext()`, et les trois décorateurs disparaissent.

**Mais « ignorer si absent » aurait été la mauvaise règle.** Sur un poste de
développement, poppler n'a pas à être un prérequis pour lancer la suite : le
test est ignoré, en le disant. Sur un runner d'intégration continue, le
workflow l'installe explicitement : son absence y est une panne
d'environnement, et l'ignorer reviendrait à conclure au vert sans avoir
vérifié — ce que la passe F reproche à tout garde-fou qui approuve faute de
pouvoir travailler. La garde échoue donc franchement quand `CI` est défini, en
nommant l'étape du workflow qui n'a pas produit son effet. Un test ignoré en
silence sur la CI, c'est une couverture qui disparaît sans que personne ne
l'apprenne.

**L'installation de poppler vérifie désormais son propre effet.** L'étape
posait `apt-get install -y poppler-utils` et passait à la suite sans regarder.
Une installation sans effet ne se voyait pas là où elle avait lieu : elle
ressortait quarante secondes plus tard, en cinq échecs au milieu de constats
fiscaux — à l'endroit qui désigne le mauvais coupable. Elle exige maintenant
`command -v pdftotext` et affiche la version obtenue.


## 8.51.0 — 2026-09-16 (Le logiciel devient libre : AGPL-3.0-or-later)

**Une licence qui interdit la revente n'est pas un logiciel libre, et le dire
autrement n'y change rien.** L'ancienne licence maison concédait un usage
gratuit en interdisant la vente, la modification diffusée et la réutilisation
du code. C'était cohérent et clairement écrit — mais c'était du
source-available, pas de l'open source : le premier critère de l'Open Source
Definition est la liberté de redistribution, vente comprise. Pire, cette
licence entrait en contradiction avec son propre hébergement : les conditions
d'utilisation de GitHub accordent à tout utilisateur le droit de forker un
dépôt public, c'est-à-dire d'en faire une copie modifiable, que l'article 3
prétendait interdire. Un texte qui se contredit avec la plateforme qui le
porte ne protège rien.

**Le logiciel passe donc sous AGPL-3.0-or-later.** Chacun peut l'utiliser, le
copier, le modifier, le forker, le redistribuer et le vendre ; toute version
diffusée doit l'être sous la même licence avec son code source — y compris
exposée comme service en ligne, ce que dit l'article 13 propre à l'AGPL et qui
n'a rien de théorique pour une application qui est un serveur web. La
contrepartie de la liberté n'est plus l'interdiction de vendre, c'est
l'obligation de rendre. Le texte intégral est à la racine du dépôt, dans
`LICENSE` ; les 84 fichiers qui portaient « Tous droits réservés » portent
désormais un identifiant `SPDX-License-Identifier`, lisible par un humain
comme par un outil d'analyse.

**Le dossier du logiciel ne porte plus de numéro de version.**
`compta_lmnp_v8.41.0/compta_lmnp/` devient `compta_lmnp/`. Ce chemin faux —
la version était 8.50.1 depuis longtemps — obligeait `build_client.py` à
trier des candidats sur les nombres du nom, parce que 8.9.0 passe après
8.41.0 en tri lexical, et la CI à chercher son arborescence au lieu de la
nommer. Les deux recherches disparaissent. Surtout, un chemin qui change à
chaque version est intenable dans un dépôt public : il casse les clones, les
liens permanents et les signets. La version vit dans le fichier `VERSION`, et
nulle part ailleurs.

**Trois affirmations fausses ont été corrigées, dont une dans la section
licence.** Le document d'accueil soutenait que le logiciel n'utilise « que la
bibliothèque standard de Python » alors que Flask est une dépendance
d'exécution obligatoire depuis l'introduction de la couche web, et reportlab
une dépendance facultative. Dans une section qui traite des licences, ce n'est
pas une coquille : c'est une déclaration de conformité fausse. Le nouveau
`NOTICES-TIERS.md` établit ce qui est utilisé, sous quelle licence, et surtout
la distinction qui commande les obligations — le paquet client ne redistribue
aucun composant tiers, les lanceurs les installent chez l'utilisateur. Deux
autres chiffres avaient dérivé sans que personne ne les relise : 416 tests
annoncés pour 1 152 réels, 19 contrôles pour 32.

**La construction d'exécutable Windows est retirée.** `construire_exe.py`
embarquait Flask et reportlab sans leurs notices BSD — une redistribution
binaire non conforme, la seule obligation réellement manquée de tout ce
travail. Il était de surcroît cassé sans que personne ne l'ait vu, puisqu'il
ne se construit que sur Windows, là où la suite de tests ne tourne pas : il
n'embarquait que `schema.sql`, ni `seed_referentiel.sql` ni `seed_demo.sql`,
et ne gérait pas `sys._MEIPASS` — l'exécutable produit ne pouvait pas
initialiser sa base. Le corriger sans pouvoir l'exécuter aurait été valider
par lecture ce que seule l'exécution établit, ce que ce projet s'interdit
partout ailleurs.

**Le contrôle de publication ne dépend plus de la mémoire de l'auteur.**
`verifier_depot.py` reste un geste local — il refuse de conclure sans les
empreintes du dossier privé, et c'est voulu — mais il est désormais joué par
un hook `.githooks/pre-push` qui refuse le push s'il signale quelque chose.
Le maillon humain qui restait (penser à le lancer) n'existe plus, et un dépôt
public ne pardonne pas un oubli : un fichier poussé reste dans l'historique
même supprimé ensuite.

**Ce que le dépôt expose désormais à sa racine** : `LICENSE` (AGPL intégrale),
`README.md` (page d'accueil, avertissement fiscal, régime RGPD, dons, marque,
limites connues), `NOTICES-TIERS.md` et `CONTRIBUTING.md` (DCO, aucune donnée
réelle, un test de non-régression par correctif). La note RGPD manquait
entièrement alors que le logiciel détient des données personnelles de **tiers**
— les locataires : elle nomme le responsable de traitement (l'utilisateur, pas
l'auteur), la base légale, les durées de conservation et l'absence de
sous-traitance.

Non-régression : six tests de propriété intellectuelle dans
`tests/test_audit_production.py`, dont trois gardes anti-retour — aucune
mention du modèle propriétaire dans le dépôt, un identifiant SPDX en tête de
chaque fichier Python, et l'interdiction que revienne l'affirmation « seulement
la bibliothèque standard ». `1 152 tests` passent, `ruff` est propre, et le
paquet client livre bien `LICENSE.txt` et `NOTICES-TIERS.md` — vérifié sur le
zip construit.


## 8.50.1 — 2026-09-16 (Le contrôle de publication sait lire un PDF)

**Un contrôle qui échoue toujours finit par ne plus être lu.** Les preuves
d'audit versionnées dans `docs/preuves_*` sont des PDF ; le contrôle avant
publication rangeait le PDF parmi les formats opaques — archives, images,
bureautique — et rendait un avertissement pour chacun. Quatorze
avertissements perpétuels, un test de publication rouge en permanence, et
l'habitude de passer outre qui s'installe.

**La facilité aurait rouvert le trou que ce contrôle documente.** Exempter
`docs/preuves_*` par son chemin aurait rendu le test vert en aveuglant le
contrôle à l'endroit exact où l'on dépose des sorties fraîchement produites
— alors que le cas qui a motivé cet avertissement est justement un bilan
comptable RÉEL déposé en PDF, que le contrôle traversait sans rien y voir.
Un chemin exempté ne dit pas « ce fichier est propre », il dit « je ne
regarde plus par ici ».

**Le PDF est donc lu pour de bon.** Son texte est extrait par `pdftotext`,
dont la suite de tests dépend déjà, et les empreintes du dossier réel y sont
cherchées comme dans n'importe quel fichier. Ce qui ne peut pas être lu est
DIT, jamais traversé : poppler absent de la machine, extraction en échec sur
un fichier chiffré ou abîmé, document scanné dont l'extraction ne rend aucun
caractère — chacun de ces cas redevient un avertissement nommé, qui dit ce
qui manque. Et l'ordre des deux verdicts compte : le peu de texte d'une page
scannée passe d'abord au tamis des empreintes, parce qu'un nom tient en
moins de vingt signes et qu'une fuite lisible ne doit pas être classée « à
vérifier à la main ».

Le contrôle du dépôt conclut désormais sur les 209 fichiers qui seraient
publiés, PDF compris.


## 8.50.0 — 2026-09-16 (Passe Q : le bon contrôle, au mauvais moment)

Douze constats, quatre critiques, sept majeurs et un mineur. Cette passe ne
reproche presque rien aux contrôles du logiciel : elle reproche l'INSTANT où
ils sont posés. Presque tous étaient justes ; ils regardaient seulement un
état qui n'était plus celui dans lequel on écrivait.

**Un contrôle pris avant le verrou ne décrit que le passé.** Entre le moment
où l'on constate qu'un loyer n'est pas encore annulé et celui où on l'annule,
une seconde demande passait : deux contre-passations pour une écriture, et
800 € de produits envolés. Entre le moment où l'on constate qu'un logement
n'est pas encore quittancé et celui où l'on émet, une seconde demande
passait : 1 600 € attestés à des tiers pour 800 € encaissés — la contrainte
d'unicité, qui porte sur (locataire, période), ne voit pas le logement.
Entre le moment où un exercice est déclaré ouvert et celui où l'on y écrit,
une clôture passait : l'écriture entrait dans un exercice dont le résultat
figé ne la comptait pas, sans qu'aucun équilibre ne soit rompu. Ces trois
contrôles sont désormais relus APRÈS `BEGIN IMMEDIATE`, et le refus relâche
lui-même le verrou qu'il vient de prendre — sans toucher à la transaction
d'un appelant qui composait déjà la sienne.

**Et de l'autre côté du commit, la symétrique.** Un import de dix loyers
était bel et bien enregistré, puis la suppression du fichier temporaire
échouait, et le logiciel annonçait « Import interrompu ». L'utilisateur
relançait — l'import ne porte aucune clé d'idempotence — et saisissait
8 000 € de recettes une seconde fois. Un échec de ménage n'annule pas ce qui
est validé : c'est maintenant un avertissement sur un import réussi, qui
nomme le fichier à supprimer à la main et interdit la relance.

**Lire ne doit jamais valider.** `assurer_schema` exécutait un
`executescript`, et SQLite valide implicitement la transaction en cours avant
d'en exécuter le script : consulter la liste des quittances au milieu d'une
saisie composée rendait définitifs 800 € que l'appelant s'apprêtait peut-être
à annuler. Le contrat `commit=False` était rompu pour tout appelant, sans
qu'aucun d'eux ne puisse le soupçonner. La fonction n'écrit plus rien quand
il n'y a rien à créer.

**Deux copies de sûreté dans la même seconde n'en font plus qu'une.** Le nom
d'une sauvegarde ne portait que la seconde : deux restaurations lancées
ensemble visaient le même fichier, et la seconde écrasait la première avec
l'état déjà restauré. Le loyer que la copie devait permettre de retrouver
disparaissait donc aussi d'elle. Les collisions reçoivent désormais un
suffixe, et l'intégrité SQLite — qui ne voyait rien à redire — n'est plus
seule à répondre de la perte.

**Ce qui se fait en deux écritures doit tenir ou tomber ensemble.** Un
composant à 12 000 € était validé, puis son écriture d'acquisition échouait
sur une date inexistante : le référentiel gardait l'immobilisation sans
l'écriture, et le message d'erreur n'en disait rien. Un appel de charges
gardait ses deux premières composantes quand la troisième était refusée. Une
reprise de deux FEC laissait durablement le premier exercice quand le second
échouait — tout en effaçant, par son `finally`, les fichiers téléversés avec
quoi recommencer. Un exercice 2027 était créé alors que la reprise des
à-nouveaux qu'on lui demandait venait d'être refusée, et le message invitait
à clôturer 2026 « puis recommencer » sur un exercice déjà là. Ces quatre
traitements sont maintenant d'un seul tenant.

**Une mise à niveau interrompue ferme la porte.** L'exception d'une migration
échouée était avalée : la requête continuait sur un schéma à moitié monté,
sans un mot. La garde de version refuse désormais de servir un dossier dans
cet état, en nommant la cause, en rappelant qu'une sauvegarde a été prise
avant la tentative, et en laissant ouverte la seule sortie utile — le retour
au dossier principal.

**Un incident géré se conserve comme les autres.** Le journal persistant
était branché par le gestionnaire d'exception global, c'est-à-dire par les
seules erreurs NON gérées : un import proprement annulé à la septième ligne
sur dix n'écrivait rien sur le disque, et sa trace disparaissait avec la
fenêtre du lanceur. Ce sont pourtant ces incidents-là qu'on veut relire à
froid.

Non-régression : `tests/test_passe_q.py` (32 tests), dont 18 échouent si l'on
retire les correctifs. L'enregistrement d'un import a quitté `app.py` pour
`import_bancaire.enregistrer`, avec son exception `ImportAnnule` qui porte le
rang et le total — la quatrième fois de ce programme d'audit que le garde-fou
anti-monolithe impose de déplacer une règle là où elle appartient.


## 8.49.0 — 2026-09-16 (Passe P : la quittance est un document remis à un tiers)
Sept constats, six majeurs et un mineur. Une quittance n'est pas un état
interne : c'est un document remis à un locataire, qui le fera valoir contre
le bailleur. Tout ce qui suit en découle.

**Un document remis ne s'invente pas.** L'avertissement de discordance
existait à la consultation, mais l'émission n'était pas bloquée : 880 €
pouvaient être attestés sans le moindre encaissement. Et seul le TOTAL
était comparé, si bien que 800 € de loyer plus 80 € de charges encaissés
pouvaient devenir 880 € de loyer et zéro charge — le total tombait juste,
la ventilation était fausse, et c'est précisément cette ventilation que
l'article 21 de la loi du 6 juillet 1989 impose et que le locataire fera
valoir. Le rapprochement se fait maintenant poste par poste, avant
l'émission, avec une dérogation explicite pour ce que le logiciel ne peut
pas voir.

**Le reçu d'un acompte n'est pas la quittance d'un mois.** Un versement de
400 € sur 800 € dus produisait une QUITTANCE DE LOYER — titre qui solde la
période — puis interdisait tout justificatif du solde une fois celui-ci
payé : 400 € supplémentaires restaient hors de toute preuve. Les deux
documents sont désormais distingués, conformément à l'article 21 : le reçu
porte le reste dû, et la quittance lui succède sans l'effacer, chacun avec
son numéro.

**La colocation était conseillée puis refusée.** Le message d'erreur
invitait à « indiquer le montant revenant à chacun », et le contrôle
refusait ensuite la seconde part : le parcours conseillé était interdit par
le contrôle qui le conseillait. En relocation, le premier occupant recevait
même les fonds versés par le second. Ce qui doit rester interdit n'est pas
d'émettre deux documents, c'est d'attester DEUX FOIS le même encaissement :
c'est donc le montant, et non le nombre de documents, qui borne désormais.

**Un numéro remis ne se réattribue jamais.** Un compteur de quittances
devenu illisible était assimilé à l'absence de toute quittance : la garde
ne voyait aucun recul de numérotation, et le n° 2 déjà remis pour février
était réattribué à mars. La restauration est refusée quand la numérotation
ne peut pas être lue — sauf si la base courante est elle-même hors
d'usage, puisque c'est alors le sinistre que la restauration vient réparer.

**Un document remis ne se recalcule pas.** Le justificatif était reconstruit
par jointure sur le référentiel COURANT : corriger le nom d'un locataire ou
l'adresse d'un logement réécrivait rétroactivement tous ses documents, sous
leurs numéros d'origine, sans qu'aucune trace ne subsiste de ce qui avait
réellement circulé. L'identité — locataire, adresse, bailleur, montant dû —
est désormais FIGÉE à l'émission, et l'écran signale quand le dossier a
changé depuis.

**Le justificatif situe et date ce qu'il atteste.** La date du paiement
était connue dans l'opération et le document ne la portait pas ; l'adresse
postale manquante était remplacée en silence par le libellé interne du bien
— « Logement Alpha Fictif » présenté comme une adresse. La date est reprise
de l'encaissement, et l'absence d'adresse est signalée plutôt que masquée.

**Enfin, une promesse d'anonymisation ne peut pas reposer sur un
inventaire.** Le générateur du jeu de démonstration remplaçait les termes
inscrits à la main dans une liste ; un locataire absent de cette liste
traversait intact jusque dans l'artefact distribué, sous un en-tête
promettant « AUCUNE donnée personnelle ». Le contrôle final ne pouvait pas
le rattraper, puisqu'il cherche exactement les mêmes termes. Les tables qui
portent des PERSONNES — `locataire`, `quittance` — sont maintenant retirées
du jeu de démonstration : leur contenu n'instruit rien, et le moindre oubli
y devenait une fuite.

Le schéma passe en version 8 : le type de document et l'identité figée sont
ajoutés à la table `quittance`, dont l'unicité porte désormais sur
(locataire, période, type). Les bases existantes sont migrées au premier
accès — la contrainte d'unicité d'un CREATE TABLE ne s'altérant pas, la
table est reconstruite.

- 30 tests ajoutés (1111 au total).

## 8.48.0 — 2026-09-16 (Passes M, N, O : ce qui garde, et ce qui garde la garde)
Trente-deux constats. Ces trois passes n'examinent pas la comptabilité :
elles examinent ce qui la surveille, ce qui la paramètre et ce qui la
protège. Une même question les traverse — **que vaut un verdict positif ?**

### Le moteur de contrôles (passe M, 14 constats)

**Un contrôle qui échouait rendait une liste vide.** « Je n'ai pas pu
vérifier » devenait « rien à signaler » : le déclarant recevait une
assurance positive sur un cumul d'amortissement de 12 000 € qui n'avait
jamais été contrôlé. Chaque contrôle est désormais ISOLÉ — un échec devient
une anomalie bloquante qui le nomme, et n'emporte plus les vingt-six
autres avec lui. Dans le même esprit, un rapport demandé pour un exercice
absent de la base concluait « aucune anomalie ✓ » : il prétendait avoir
vérifié ce qu'il n'avait pas pu lire.

**Le document remis ne portait pas les anomalies du moteur.** Le PDF
affichait cinq validations internes en vert pendant qu'une anomalie
BLOQUANTE — 800 € en compte d'attente — attendait ailleurs : les deux
ensembles de contrôles n'étaient tout simplement pas reliés. Ils le sont.

**Le refus de clôturer n'existait que dans les interfaces.** La route web
et la ligne de commande vérifiaient bien les anomalies bloquantes ; la
fonction qui FIGE l'exercice, non. Un appel métier ordinaire figeait donc
800 € non identifiés sans rien demander. Une garantie qui repose sur la
discipline de ses appelants tombe au premier appelant nouveau : elle vit
maintenant dans l'API, avec sa dérogation explicite.

**Le compte d'attente et ce qu'apurer veut dire.** Le compte était désigné
par égalité avec 472000 — un cabinet numérote en 4720000. Et le contrôle
sommait algébriquement : deux flux opposés encore « à identifier » donnent
un solde nul, que le contrôle prenait pour un apurement. Le signal n'est
pourtant pas le mouvement du compte — un compte régulièrement apuré porte
justement l'écriture d'origine et sa reclassification, et le dossier de
référence en compte 287 847,78 € — mais les OPÉRATIONS qui n'ont pas reçu
de décision.

**L'audit de cycle approuvait des régressions qu'il annonçait vérifier.**
Un de ses contrôles passait `True` en dur ; un autre cherchait un code
d'anomalie sans exiger son niveau ; et il effaçait ses propres injections
avant de tenter la clôture, si bien qu'il n'éprouvait jamais le refus qu'il
annonçait. Il l'éprouve, et le compte d'attente a désormais son témoin.

**Des erreurs déterminées passées de l'avertissement au blocage.** Clôturer
sans à-nouveaux, ou avec des amortissements antérieurs non repris, fige un
bilan dont on SAIT qu'il est faux — actif net de −1 200 € au lieu de
9 600 € dans un cas reproduit. Avec la nuance demandée : un exercice
antérieur dont tous les soldes sont nuls ne laisse rien à reprendre et ne
bloque rien.

**Enfin, des alertes qui criaient sur du travail correct.** Une opération
annulée continuait d'être signalée ; deux studios loués au même prix
passaient pour un doublon ; un exercice ouvert en novembre réclamait dix
loyers antérieurs à son ouverture ; un gabarit de loyer créé par
l'utilisateur sortait des contrôles sans que rien ne l'annonce ; et un
seuil enregistré à l'infini rendait deux contrôles définitivement muets.

### Les règles versionnées (passe N, 8 constats)

Le logiciel applique les règles « telles qu'elles sont enregistrées ».
C'est un choix juste, mais il déplace la question : que vaut une règle
enregistrée ?

**Une règle a un domaine.** Une durée de report saisie à ZÉRO faisait
expirer un déficit l'année même de sa naissance : 1 200 € purgés, et un
bénéfice de 1 200 € laissé sans son imputation. Chaque règle livrée a
désormais ses bornes.

**Une règle a une période.** Saisir une valeur rétroactive laissait deux
périodes ouvertes en même temps ; le tri par date sauvait le calcul, mais
un historique contradictoire ne justifie rien devant un vérificateur.

**Une règle a une histoire.** Le logiciel ressème ses règles dès qu'une clé
manque — bon comportement à la première ouverture, mauvais après une
perte : un seuil abaissé à 300 € revenait à 500 € et l'avertissement
disparaissait avec lui. Une marque durable distingue maintenant les deux
situations, et un contrôle le dit.

**Deux lecteurs d'une même règle doivent répondre la même chose.** Le
pense-bête comparait à une constante 23 000 et restait muet sur 20 000 € de
recettes face à un seuil configuré à 15 000 €, là où le contrôle métier
signalait le franchissement.

**Un garde-fou qui ne peut pas travailler ne laisse pas passer.** Un seuil
d'immobilisation devenu illisible faisait proposer en charge un achat de
400 € que la règle disponible excluait. La ligne part désormais en attente,
qui demande une décision — un repli silencieux vers la valeur la plus
permissive est la pire réponse à l'indisponibilité d'un garde-fou.

S'y ajoutent une création de gabarit qui validait la transaction de son
appelant — 800 € survivaient au rollback —, une date de veille future
acceptée qui éteignait le rappel pour des décennies, une consultation de
veille en panne indiscernable d'une veille à jour, et la règle ALUR absente
de la revue guidée alors qu'elle modifie le résultat fiscal.

### Les sauvegardes et la pérennité (passe O, 10 constats)

Le risque tient en une phrase : **confondre une copie créée avec une
sauvegarde utilisable.**

L'API SQLite garantit une copie FIDÈLE, pas la validité de ce qu'elle
copie : une base au schéma corrompu donnait une copie tout aussi
corrompue, retournée comme un succès — défaut découvert le jour où l'on a
besoin de la copie, c'est-à-dire trop tard. Chaque copie est maintenant
relue avant d'être annoncée. Un fichier de zéro octet portant le nom du
jour suffisait par ailleurs à dire « déjà fait aujourd'hui », et aucune
sauvegarde exploitable n'était plus créée de la journée.

**La rotation pouvait supprimer la source d'une restauration en cours.** La
copie de sûreté prise juste avant déclenche une rotation : elle emportait
parfois le fichier que l'on s'apprêtait justement à lire, et la base active
était remplacée par du vide, avec un retour annoncé réussi.

**Le répertoire ne prouve pas l'appartenance.** Tous les dossiers nomment
leur base « compta.db » : déposer la copie d'un autre dossier dans le bon
répertoire suffisait à la faire accepter, et une comptabilité en remplaçait
une autre. L'identité se lit maintenant DANS la base — exploitant, SIREN,
biens — et seule une contradiction constatée fait refuser.

**Une preuve qui ne prouve plus rien ne doit pas être remise comme si elle
prouvait encore.** Le contrôle d'intégrité des archives existait, mais le
téléchargement ne l'appelait pas : une archive modifiée était servie comme
n'importe quelle autre. Le manifeste, lui, perdait ses lignes tronquées en
silence, et son absence rendait une liste vide plutôt qu'une alerte.

**Une restauration coupe l'histoire comptable en deux.** Après elle, deux
FEC du même exercice coexistent, tous deux intègres au sens de leur
empreinte, sans que rien ne dise lequel fait foi : la coupure est
désormais inscrite dans le manifeste, à sa date. Une sauvegarde produite
par une version PLUS RÉCENTE du logiciel était par ailleurs installée avant
que le garde de version ne bloque le dossier — restauration annoncée
réussie, comptabilité inaccessible dans la foulée. Et un registre de
dossiers tronqué passait pour un registre vide, faisant disparaître les
dossiers secondaires de l'interface sans que rien ne dise où ils étaient
passés.

### Au passage

Le garde-fou anti-monolithe d'`app.py` s'est déclenché deux fois pendant
ces passes. Chaque fois que la règle pouvait vivre ailleurs, elle y a été
déplacée — la durée d'amortissement dans `amortissement`, l'intégrité
d'une archive dans `perennite`. Son seuil passe de 2 200 à 2 250 lignes,
relevé plutôt que supprimé, avec sa raison écrite.

Un constat de la passe M (M-09, recettes du seuil LMP) était déjà corrigé
par la passe J : il est vérifié et figé, non recorrigé.

- 95 tests ajoutés (1081 au total).

## 8.47.0 — 2026-09-16 (Passe L : la cession d'un bien)
Quatre constats, trois majeurs et un mineur. La neutralisation fiscale de la
plus-value, la ligne 352 et le traitement d'une cession à titre gratuit
tiennent. Ce qui ne tenait pas concerne le moment de la sortie — qui est
sans retour — et ce que le déclarant reçoit ensuite.

**La sortie soldait le cumul du PLAN, pas celui des comptes.** Solder, c'est
ramener un compte à zéro : le montant à solder est donc celui qui s'y
trouve. Or la sortie reprenait le cumul recalculé depuis la durée et la date
actuelles du composant, et rien ne garantit qu'il décrive ce qui a été
comptabilisé — un historique repris d'un cabinet, ou une durée corrigée
après coup, le démentent. Sur un composant de 12 000 € portant 3 000 €
d'amortissements repris là où le plan en prévoyait 1 200 €, la sortie
soldait 1 200 € : 1 800 € d'amortissements restaient en compte pour un actif
qui n'existait plus, et la valeur nette passée en charge de cession était
surévaluée d'autant. Le cumul se lit désormais dans les comptes. Quand le
compte d'amortissement sert aussi à des composants qui ne sont pas cédés et
que son solde ne concorde pas avec le plan, l'écart ne peut être attribué ni
aux uns ni aux autres : la cession est refusée, avec le rapprochement à
faire.

**Le tableau des immobilisations effaçait l'exercice de la vente.** Le bien
cédé en était exclu dès l'année de sa cession, ouverture et mouvements
compris : il ne restait que des zéros. Les soldes FINAUX étaient pourtant
justes — et comme les contrôles de concordance ne rapprochent que les soldes
finaux, ils approuvaient. 12 000 € de brut d'ouverture, 595,07 € de dotation
de sortie et 1 795,07 € de diminution d'amortissements n'étaient donc pas
fournis au déclarant. Le tableau distingue maintenant un bien cédé AVANT
l'exercice — qui n'y a plus rien à faire — d'un bien cédé PENDANT, dont les
mouvements sont ceux de l'exercice. Deux colonnes de diminution s'ajoutent,
au brut et aux amortissements, sur l'écran comme au PDF ; leurs montants
sont lus dans les écritures de cession, non recalculés.

**Une vente antérieure à l'acquisition était acceptée.** Seule la syntaxe de
la date était contrôlée : une cession datée de la veille de l'acquisition
sortait 12 000 € d'actif, enregistrait 15 000 € de produit sur une
chronologie impossible, et la liasse déclarait le tout conforme. Le logiciel
ne peut pas deviner laquelle des deux dates est fausse, mais il peut refuser
la combinaison — et nommer les deux dates pour que la correction soit
possible. Vendre le jour même de l'acquisition reste permis : c'est étrange,
ce n'est pas impossible.

**Le PDF ne rappelait pas la déclaration immobilière séparée.** Un exercice
de cession se lit tout entier de travers si l'on croit que la neutralisation
du BIC calcule la plus-value. En location meublée non professionnelle, elle
relève du régime des particuliers (article 150 U du CGI) et se déclare par
le notaire, sur la 2048-IMM, au moment de la vente. Le pense-bête le disait ;
le PDF, qui est ce qui part chez le comptable ou reste au dossier, ne le
disait pas. Sa page de garde le dit désormais dès qu'une cession figure dans
l'exercice — y compris à titre gratuit, où le prix est nul mais la valeur
comptable sort.

- 24 tests ajoutés (986 au total).

## 8.46.0 — 2026-09-16 (Passe K : clôture et continuité pluriannuelle)
Trois constats, deux majeurs et un mineur. La clôture tient par ailleurs son
contrat atomique : soixante-quatorze interruptions par SIGKILL réparties sur
tous ses points d'écriture n'ont laissé aucune clôture partielle, et un seul
commit est observé. Ce qui manquait était ailleurs — dans ce que le logiciel
considère comme IRRÉVERSIBLE.

**Un exercice ancien pouvait être clôturé après ses suivants.** La garde
chronologique ne cherchait que les exercices antérieurs encore OUVERTS.
Rien n'empêchait donc d'ajouter 2024 après coup et de le clore alors que
2025 était déjà scellé. Or la clôture de 2025 a figé des stocks
d'amortissements et de déficits calculés SANS 2024 : les 600 € de bénéfice
déjà déclarés imposables auraient dû être absorbés par le déficit que l'on
vient de créer, et le stock de déficits compte désormais 600 € de trop. Deux
représentations incompatibles de la même imputation coexistaient, et rien
ne les départageait. Le logiciel ne peut pas recalculer les exercices
postérieurs — leur FEC est archivé, leur liasse a pu être déclarée — il
refuse donc, en indiquant que le chemin passe par une sauvegarde antérieure
et une reprise des clôtures dans l'ordre.

**Supprimer la moitié d'une reprise permettait de la reconstruire, et de
compter le résultat deux fois.** Une reprise d'à-nouveaux est un LOT :
l'écriture AN et l'OD qui affecte le résultat. La garde ne regardait que le
journal AN — supprimer manuellement cette seule écriture, sur un exercice
ouvert, laissait l'OD d'affectation seule et rendait la reconstruction
possible. Les 600 € de bénéfice se retrouvaient alors deux fois au crédit
de 108000 et au débit de 120000. Chaque OD étant elle-même équilibrée, aucun
contrôle d'équilibre ne pouvait le voir : le défaut ne se manifestait que
bien plus tard, la reprise de l'année suivante butant sur un solde 120000
résiduel que les comptes de bilan n'expliquaient pas. La garde regarde
désormais les deux moitiés du lot, nomme celle qui subsiste, et vit au
point de passage commun aux deux chemins de reprise — interne et depuis un
FEC externe — plutôt que dans chacun de leurs appelants.

**Une jonction tolérée était annoncée comme exacte.** Le contrôle qui
vérifie que le bilan de clôture de N se retrouve à l'ouverture de N+1
admet un écart d'un centime. Il concluait « les bilans se raccordent au
centime » dès qu'aucun écart ne dépassait ce seuil — lequel vaut justement
un centime : un décalage d'exactement 0,01 € sur deux comptes était donc
approuvé sous un libellé qui prétendait le contraire. Une tolérance est un
choix de contrôle légitime ; la présenter comme une égalité ne l'est pas.
Trois verdicts sont maintenant distingués : raccord exact, écarts sous la
tolérance — signalés, chiffrés, sans être traités comme une rupture — et
rupture franche. Sur les fichiers de référence, les deux jonctions sont
exactes.

- 18 tests ajoutés (962 au total).

## 8.45.0 — 2026-09-15 (Passe J : la mémoire des déficits LMNP)
Cinq constats, dont un critique. Le moteur respectait l'année limite et
l'ordre FIFO ; ce qui manquait, c'était la MÉMOIRE — ce que le logiciel
remet au déclarant, et ce qu'il sait encore en redire l'année suivante.

**Un déficit entièrement consommé disparaissait de l'aide à la
déclaration.** Le stock d'ouverture d'un millésime n'était reconstitué qu'à
partir de son solde courant : lorsqu'un bénéfice l'absorbait en totalité,
la ligne tombait à zéro et l'aide cessait de la voir. Elle proposait alors
un bénéfice en 5NA sans la case de déficit antérieur qui l'accompagne —
7 000 € de base avec 6 000 € de déduction omis dans un cas reproduit. Or
l'imputation est une opération que l'administration refait : lui donner le
bénéfice sans le déficit qui le compense, c'est déclarer imposable ce qui
ne l'est pas. L'aide lit désormais les soldes réellement enregistrés à la
clôture, millésimes épuisés compris, et additionne les lignes de même
origine avant d'arrondir.

**Une clôture ultérieure réécrivait la déclaration d'un exercice déjà
clos.** La table des déficits ne conservait qu'un solde COURANT, pas les
soldes par exercice. Rééditer la liasse 2025 après avoir clôturé 2026
perdait donc les 3 000 € de déficit d'ouverture de 2025, et faisait
apparaître dans son suivi un millésime 2027 qui n'existait pas encore. Les
écritures closes n'étaient pas touchées — c'est le document reconstruit qui
changeait, ce qui est pire : rien ne le signalait. Un instantané annuel
conserve maintenant chaque millésime, son ouverture, son imputation, son
solde final et sa perte par péremption ; les rééditions s'appuient sur lui,
et ne voient plus l'avenir.

**La perte par péremption s'effaçait du document imprimé.** Un déficit
arrivé à expiration laissait sa ligne en base, mais le PDF ne disait plus
ce qui avait été perdu : 1 200 € sans explication dans l'état archivé. Le
montant initial ne suffit pas à le dire, puisqu'il ne distingue pas ce qui
a été consommé de ce qui a expiré. La perte effective est donc enregistrée
à part, et le PDF en donne le total et le détail par origine.

**Le contrôle du seuil LMP ne voyait pas les recettes d'un FEC rejoué.** Il
additionnait les opérations de SAISIE : un dossier repris depuis un fichier
de cabinet franchissait le seuil sans l'avertissement prévu. Il lit
maintenant les loyers acquis issus des écritures, via `fiscal.agregats`,
sans cumuler les deux sources. Le franchissement reste un avertissement
invitant à vérifier le second critère, que le logiciel ne connaît pas.

**Enfin, les demi-euros s'arrondissaient dans le mauvais sens.** Python
arrondit au pair : 100,50 € donnait 100 en case, et un déficit antérieur de
0,50 € était purement éliminé par un filtre strict. Les cases emploient
désormais `Decimal` et `ROUND_HALF_UP`, après regroupement par millésime.

Une table `suivi_deficits` porte ces instantanés. Elle est créée à la
première clôture d'un dossier ancien, sans commit intermédiaire : la
clôture reste atomique. Aucun historique n'est INVENTÉ pour les exercices
clos avant ce correctif — une réédition qui n'a pas d'instantané est
refusée avec un message explicite renvoyant aux archives de déclaration ou
à une sauvegarde antérieure, plutôt que de reconstruire un document
plausible et faux.

- 35 tests ajoutés (944 au total).

## 8.44.0 — 2026-09-15 (Passe I : l'article 39 C, son plafond et sa mémoire)
Onze constats, dont deux critiques. Deux fils rouges, et ils se
ressemblent : le logiciel identifiait des choses par une CHAÎNE au lieu de
les identifier par ce qu'elles sont.

**Les comptes, par égalité stricte.** Le plan livré tient sur six chiffres ;
un cabinet en utilise sept, et la reprise d'un FEC les crée tels quels.
Chaque égalité devenait alors une qualification fiscale manquée — sans
qu'un seul total ne bouge, ce qui rendait le défaut parfaitement
invisible. Une dotation arrivée en 6811200 n'était plus une dotation :
elle tombait dans les charges ordinaires, et son excédent devenait un
DÉFICIT LMNP, imputable sur les seuls bénéfices de même nature et périmé à
dix ans, au lieu d'un report 39 C qui ne se périme jamais. Des honoraires
comptables en 6226100 n'étaient plus exclus du plafond. Un produit de
cession en 7750000 n'était plus neutralisé : il gonflait le plafond comme
s'il s'agissait d'un loyer, et 4 000 € de revenu imposable apparaissaient
là où il n'y en avait pas. Un compte se reconnaît désormais à sa RACINE
PCG, dont les subdivisions héritent par construction.

**Les biens, par le libellé de leurs composants.** Pour attribuer à un bien
cédé sa part du report, le suivi retrouvait sa dotation de cession en
comparant le libellé des lignes au libellé de ses composants. Deux
logements meublés dont un composant s'appelle pareil — le cas le plus
ordinaire qui soit — et chacun se voyait attribuer la dotation de l'autre :
1 000 € de stock conservé disparaissaient pour un simple choix de mots. La
référence de pièce porte maintenant l'identifiant du bien.

**Le plafond se calcule sur les LOYERS acquis.** Tous les produits de
classe 7 y entraient. Un produit financier de 1 000 € absorbait donc
immédiatement 1 000 € d'amortissement au lieu de les faire reporter — et
une déduction perdue ne revient jamais, là où un report attend
indéfiniment. Les produits financiers, exceptionnels, les reprises et les
transferts de charges sont écartés de cette base ; ils restent bien
entendu des produits du résultat.

**À qui appartient le report ?** La question n'est pas théorique : le
report part DÉFINITIVEMENT avec le bien le jour où celui-ci est vendu. Il
était réparti au prorata des dotations, si bien qu'un logement dont les
loyers couvraient largement sa dotation en recevait quand même une part —
laquelle disparaissait ensuite avec lui, au détriment du logement qui
l'avait réellement produite. Le report se répartit désormais selon
l'INSUFFISANCE de chaque bien : ce que sa dotation dépasse de sa marge
locative. Faute d'opérations rattachées aux biens — un historique repris
d'un FEC n'en a pas —, la répartition par dotations reste le repli.

**Un stock sans propriétaire se dit, au lieu de partir au hasard.** Deux
situations le produisaient en silence. Un dossier migré depuis une version
qui ne ventilait pas : le stock global existait, le détail non, et tout
était porté sur « le bien le plus ancien » — fût-il déjà CÉDÉ, auquel cas
6 000 € sortaient du suivi dès la clôture suivante, dont 1 000 € produits
par le seul bien encore actif. Un historique incomplet, ensuite : le détail
le plus récent datait de 2024 quand le stock global venait de 2025, et
3 000 € n'avaient tout simplement personne à qui appartenir. Le détail suit
maintenant le millésime du stock global, ce qui manque est rattaché à un
bien NON cédé pour que les deux suivis concordent toujours, et un contrôle
annonce que cette affectation est un pis-aller à vérifier.

**Une répartition ne rend plus de part négative.** L'ajustement du dernier
centime portait sur la dernière part, à qui l'on donnait le reste : quand
les arrondis précédents dépassaient déjà le total, ce reste était négatif —
un mouvement de reprise de −0,01 € enregistré en base. La répartition se
fait au plus fort reste, et l'écrêtage d'une utilisation au stock
réellement détenu redistribue ce qu'il retire, au lieu de le perdre.

**L'avertissement sur un retraitement manuel agit enfin avant la clôture.**
Il ne lisait que les retraitements DÉJÀ enregistrés : il ne pouvait donc
parler qu'une fois l'exercice figé, quand l'effet était produit. Or
1 000 € saisis à la main majorent le plafond d'autant et font disparaître
le report — sans que le résultat fiscal immédiat ne bouge, donc sans que
rien ne se voie. La clôture consulte désormais ce contrôle avec la valeur
soumise, et demande confirmation. Le retraitement manuel légitime — le
fonds ALUR du calage — reste praticable.

**Enfin, l'état archivable se réconcilie.** Sur un dossier mono-bien, le
tableau imprimé du suivi 39 C affichait « ouverture 5 000 + reporté 1 200 −
repris 0 = clôture 0 » : la ligne de SORTIE n'existait que dans le détail
par bien, lequel n'est imprimé qu'à partir de deux logements. 6 200 € de
mouvement sans explication dans un document destiné à être conservé.

- 39 tests ajoutés (909 au total).

## 8.43.0 — 2026-09-15 (Passe H : les amortissements par composants)
Douze constats, dont deux critiques. Tous tiennent à la même confusion : le
plan d'amortissement, recalculé à neuf depuis la durée ACTUELLE du
composant, était appliqué comme s'il décrivait ce qui avait été
comptabilisé. Une durée modifiée, une dotation saisie à la main ou un
historique repris en à-nouveaux le démentent — et c'est de là que venaient
le dépassement de la valeur brute, le double amortissement d'un exercice et
la réécriture des tableaux d'un exercice déjà clos.

Le principe est désormais écrit : **le plan est une cible, la comptabilité
en est la mesure.** La dotation d'un exercice est ce qu'il faut écrire pour
rejoindre le plan — jamais davantage que l'annuité qu'il prévoit, jamais
au-delà de ce que le bien a coûté.

**Un compte d'amortissement partagé désactivait tout plafonnement.** Le
moteur raisonnait par composant, et renonçait dès qu'un compte servait à
plusieurs — le cas, précisément, des trois postes de bâtiment de la
ventilation indicative, tous sur le même 281315. Deux composants de 8 000 €
dont la durée passait de cinq à huit ans recevaient ainsi 19 600 €
d'amortissements pour 16 000 € de valeur brute, soit 3 600 € de charges
excédentaires et une valeur nette comptable négative. Le raisonnement se
tient maintenant par COMPTE, qui est ce que l'on peut observer, et le
cumul d'un compte ne peut plus dépasser la somme des valeurs brutes qu'il
amortit.

**Une dotation déjà passée n'empêchait pas d'en générer une seconde.** La
génération cherchait une pièce OD nommée « DAA » ; elle ne voyait ni une
OD saisie à la main, ni des amortissements repris en à-nouveaux. Sur un
exercice où 1 200 € avaient déjà été dotés, la clôture en ajoutait 1 200
autres : le revenu imposable tombait à zéro au lieu de 600 €, avec 600 €
de report 39 C indu. Sur un composant d'un an déjà doté de 12 000 €, le
compte d'amortissement finissait à 24 000 € pour 12 000 € de brut. Le
moteur lit désormais deux choses distinctes — ce que le plan prévoit pour
l'exercice, et ce qu'il RESTE à y écrire — et ne confond plus les deux.

**Un retard de cumul ne se rattrape pas tout seul, mais il se voit.** Le
moteur ne majore jamais une annuité pour combler un retard : l'article
39 B du CGI tient l'amortissement insuffisant pour irrégulièrement
différé, donc définitivement perdu, et le déduire l'année suivante serait
faux. En revanche l'écart ne pouvait pas rester muet. Un nouveau contrôle
compare le cumul réellement comptabilisé à celui du plan : avertissement
tant que des annuités restent à venir, BLOQUANT quand le plan est épuisé —
ce qui arrivait après un raccourcissement de durée, 3 000 € de valeur
nette sortant alors de tout programme de dotations sans un mot.

**Une contre-passation était invisible, et son inverse était accusé à
tort.** Le contrôle ne totalisait que les DÉBITS du compte de dotation :
une DAA annulée par une écriture inverse passait pour intacte, tandis
qu'une dotation erronée proprement annulée puis refaite était dénoncée
comme un double amortissement. Le compte de charge se lit maintenant par
son solde. Et le verrou anti-doublon regarde l'EFFET comptable plutôt que
la seule présence de la pièce : une dotation contre-passée peut de nouveau
être reprise, au lieu de bloquer l'exercice définitivement.

**Modifier une durée réécrivait un exercice clos.** Le tableau 2033-C était
reconstruit depuis la durée actuelle : passer de dix à vingt ans faisait
tomber la dotation de 2026 — exercice CLOS — de 1 200 € à 600 €, cependant
que le bilan et le FEC, eux, ne bougeaient pas. La trace écrite à la
clôture existait ; elle n'était pas lue. Elle fait désormais foi.

**Quatre gardes qui ne gardaient rien.** Une durée de −1 an était acceptée
par la page Immobilisations : l'acquisition de 12 000 € était
comptabilisée, aucune dotation n'était jamais générée, et le tableau
affichait un amortissement négatif. Un bien sans AUCUN composant ne
déclenchait aucune alerte — une liste vide ne pouvant pas être
« incohérente » — alors que c'est le cas le plus incomplet qui soit. Un
terrain portant par erreur un compte d'amortissement de mobilier recevait
une dotation en bonne et due forme, la seule présence d'un compte 28 étant
tenue pour suffisante. Et une quote-part de terrain saisie à ZÉRO était
traitée comme une absence de saisie, la proposition retombant sur sa part
indicative de 15 % — 15 000 € sortis de la base amortissable sur un prix
de 100 000 €.

**Les subdivisions d'un cabinet trouvent leur rubrique.** Les comptes du
plan livré tiennent sur six chiffres, ceux d'un cabinet en ont souvent
sept. La correspondance était établie par égalité stricte : 2181000, qui
est une subdivision de 2181, tombait dans le repli « autres
immobilisations » du 2033-C — 12 000 € de brut et 2 400 € d'amortissements
dans la mauvaise rubrique, sans que le total général ne bouge d'un
centime, donc sans qu'aucun contrôle de concordance puisse le voir. Le
plan reconnaît maintenant les subdivisions par leur préfixe. Ce qu'il ne
reconnaît pas — 2180000, compte générique qui ne dit pas la nature du
composant — n'est pas deviné : c'est annoncé, et cela ne bloque pas la
clôture d'un dossier repris.

**Enfin, le plan d'amortissement vaut exactement la valeur brute.** Une
annuité inférieure à un demi-centime — 0,24 € sur cinquante ans —
s'arrondissait à zéro, la boucle n'avançait plus, le garde-fou anti-boucle
la coupait, et la valeur n'était jamais amortie. À l'autre bout, le
reliquat d'arrondi de 100 000,01 € créait une cinquante-et-unième annuité
de 0,01 €. Le plan descend désormais au centime et sa dernière annuité
solde le reste, sans qu'aucune des annuités calées sur les liasses réelles
ne bouge.

- 61 tests ajoutés (870 au total).

## 8.42.0 — 2026-09-15 (Passe G : la régularité comptable et le FEC)
Quinze constats, dont deux critiques. Leur fil rouge n'est pas qu'ils
existaient, c'est qu'aucun ne produisait d'erreur : chacun rendait un
verdict rassurant sur un travail qu'il n'avait pas fait. Tous sont traités.

**Une reprise perdait des écritures en annonçant un succès.** Une ligne de
FEC qui n'atteignait pas le nombre de colonnes attendu était écartée en
silence par le lecteur, et l'import affichait ensuite « n écritures
rejouées » comme un résultat normal. Un fichier dont on avait retiré deux
colonnes VIDES en fin de ligne — ses montants tous présents — perdait ainsi
des recettes entières, de façon parfaitement ÉQUILIBRÉE : aucun contrôle
d'équilibre en aval ne pouvait les rattraper. La lecture nommée refuse
maintenant le fichier en nommant les lignes en cause, et la balance de
reprise fait de même. Perdre des données sans le dire n'est pas une
tolérance.

**Une cession s'enregistrait pour un prix qui n'était pas un nombre.**
`nan < 0` est faux, comme toute comparaison avec nan : le prix passait le
contrôle de négativité, puis `nan > 0` était faux à son tour et aucune
écriture de produit n'était générée. La sortie d'actif, elle, se faisait
quand même — composants sortis, date de cession posée, douze mille euros
disparus de l'actif pour une demande qui aurait dû être rejetée. Le prix
doit désormais être un montant fini, et le champ de formulaire ne livre
plus « nan », « inf » ni « 1e400 » à la couche métier.

**Le validateur approuvait des fichiers qu'il n'avait pas pu vérifier.**
Quatre défauts se cumulaient. Il convertissait les montants avec un
`float()` direct, qui accepte « NaN », « inf » et « 1e309 » — des valeurs
qui neutralisent ensuite toute comparaison d'équilibre (nan ≠ nan,
inf − inf = nan). Il agrégeait les écritures sur le seul numéro, si bien
qu'un débit isolé dans un journal et un crédit isolé dans un autre se
compensaient. Il bornait le jour des dates à 31 sans regarder le
calendrier, et ne contrôlait du numéro de compte que la longueur. Le
parseur de montants est désormais commun au lecteur et au validateur, et
fermé : un montant est un nombre fini écrit en chiffres. L'agrégation
porte sur le couple (journal, numéro). Les dates passent par le
calendrier, jusque dans le nom de remise du fichier.

**Et il rejetait des fichiers parfaitement conformes.** La barre verticale
est un séparateur admis : elle était lue comme du texte, et le fichier
tokenisé en une seule colonne. Le signe suffixé (« 800,00- ») était un
« montant illisible ». Les dix-huit colonnes de l'arrêté sont les
PREMIÈRES, pas un maximum : une dix-neuvième faisait rejeter le fichier
dès l'en-tête, sans lire une ligne. EcritureNum est alphanumérique :
« BQ0001 » rendait tout un FEC de cabinet non migrable. Les quatre formes
sont maintenant lues. Quant aux ruptures de numérotation, elles passent en
OBSERVATION — la notice DGFiP admet celles qu'explique la validation d'un
brouillard — tandis que la numérotation que le logiciel PRODUIT, elle,
reste contrôlée strictement, là où sa provenance est connue.

**Un export taisait ce qu'il ne savait pas restituer.** Ses jointures
internes faisaient disparaître du fichier toute ligne dont le compte ou le
journal manquait au plan : l'export se terminait normalement, le validateur
trouvait le fichier conforme, et huit cents euros présents en base
n'étaient nulle part. L'export refuse désormais d'écrire un fichier qui ne
rendrait pas l'intégralité de l'exercice, et un nouveau contrôle bloquant
signale l'anomalie avant la clôture. Au passage, le fichier sort dans
l'ordre chronologique : la numérotation suit l'ordre de saisie, et un loyer
de mars saisi avant celui de janvier faisait reculer les dates du fichier.

**Un rejeu ne rendait pas le fichier qu'on lui avait donné.**
Identification auxiliaire, lettrage et devise revenaient vides au
ré-export ; les dates de PREUVE — celle de la pièce, celle de la
validation — étaient réécrites avec la date d'écriture. Ces champs sont
maintenant conservés. Deux lignes datées de deux années différentes dans
une même écriture étaient par ailleurs reprises sous l'année de la
première, sans un mot : c'est refusé. Et lorsqu'un libellé de journal du
plan livré l'emporte sur celui du fichier, la reprise le dit au lieu de le
laisser tacite.

**Trois défauts de moindre portée.** L'équilibre d'une écriture était
vérifié sur la somme des montants bruts alors que l'insertion arrondit
chaque ligne : un centime de déséquilibre durable pouvait s'inscrire, et
aucun compte ne l'absorbait. La quote-part de terrain lue dans un acte
était déplacée de treize euros par une absorption d'arrondi qui visait la
plus grosse ligne — le terrain non amortissable, justement. Un FEC en
ISO-8859-15, encodage que l'arrêté admet, voyait ses euros devenir des
« ¤ » parce que l'ordre d'essai des jeux latins décidait seul.

**Le code de retour du validateur autonome vaut désormais le verdict.** Il
valait 0 quoi qu'il arrive : une automatisation pouvait archiver puis
remettre un FEC déséquilibré au motif que le contrôle « s'était bien
passé ». Le message affiché, lui, était explicite — c'est le contrat de
commande qui manquait. 0 conforme, 1 erreur bloquante, 2 illisible.

**Et les comptes de tiers d'exception sont typés correctement.** 409
(fournisseurs débiteurs), 419 (clients créditeurs) et 425 (avances au
personnel) portent le solde INVERSE de leur tranche : un avoir fournisseur
était rangé avec les dettes, un trop-perçu de locataire avec les créances.

- 65 tests ajoutés (809 au total).

## 8.41.0 — 2026-09-07 (Passe D : les trois derniers constats critiques)
Les neuf constats critiques de la revue de la couche web sont désormais
traités. Ces trois-là touchent tous à la DISPONIBILITÉ d'un dossier.

**Une base en retard de schéma n'était jamais migrée hors du démarrage.**
La migration ne tournait qu'au lancement du serveur, sur les dossiers
alors connus — alors que le registre prévoit explicitement d'ADOPTER une
base préexistante trouvée sur le disque, laquelle conserve son schéma
d'origine. Copier un dossier d'une ancienne installation et l'ouvrir en
cours de session faisait donc écrire dans un schéma périmé, sans la copie
de sûreté que la migration produit. Le garde de version ne voyait rien : il
ne refuse qu'une base plus RÉCENTE. La migration s'exécute maintenant à
l'ouverture, une fois par dossier et par session.

**Ouvrir un dossier plus récent verrouillait tout le logiciel.** La page
d'erreur ne comportait ni lien ni formulaire, et chaque lien de la barre de
navigation repassait par le garde qui l'avait produite. Le cookie valant
180 jours, le logiciel devenait inutilisable — pour TOUS ses dossiers —
jusqu'à ce que l'utilisateur sache supprimer un cookie dans son
navigateur. Une impasse, pour un logiciel destiné à des non-informaticiens.
La page offre désormais un retour au dossier principal, et cette sortie
reste joignable malgré le garde.

**Un dossier momentanément absent était remplacé par une base vierge.**
Sans un mot. Or l'absence est le plus souvent temporaire — disque externe
débranché, dossier synchronisé pas encore redescendu, partage réseau non
monté — et créer une base à la place masquait le vrai fichier tout en
faisant croire à une perte de données. Le logiciel l'annonce maintenant,
explique la cause probable, et ne crée rien.

Au passage : le HTML de ces deux pages de secours est parti dans le module
de présentation, où il appartient. Le garde-fou anti-monolithe passe de
2 000 à 2 200 lignes — relevé plutôt que supprimé, avec sa raison écrite.

- 3 tests ajoutés (537 au total).


## 8.40.0 — 2026-09-07 (revue Passe D : la couche jamais auditée)
Première revue de la couche web et de la ligne de commande. 29 constats,
dont 9 critiques. Les six premiers sont corrigés ici ; les trois autres et
les constats majeurs suivront.

**Les deux confirmations les plus importantes ne s'affichaient jamais.**
Leur littéral JavaScript contenait un saut de ligne réel et une apostrophe
fermante — interprétés par Python avant d'atteindre le navigateur. Le
gestionnaire ne compilait pas, valait donc `null`, et le formulaire partait
sans la moindre boîte de dialogue. Cela touchait la RESTAURATION d'une
sauvegarde et l'annulation d'une opération. Preuve par contraste, dans le
même fichier : les deux confirmations qui fonctionnaient étaient
précisément celles écrites sans apostrophe — quelqu'un avait rencontré le
problème et l'avait contourné sur deux gabarits sans remonter aux autres.
Elles passent désormais par un attribut que Jinja échappe, et un
gestionnaire unique les lit.

**Le bac à sable partageait ses annexes avec la comptabilité réelle.**
Sauvegardes, archives et fichiers d'import dérivaient du RÉPERTOIRE de la
base — le même pour les deux. Trois conséquences : la page Archives du bac
à sable proposait au téléchargement les FEC de la comptabilité réelle,
sous un bandeau affirmant que celle-ci n'était pas touchée ; chaque
réinitialisation y déposait une copie que la protection des motifs de
sûreté empêchait ensuite d'effacer ; et un import préparé en bac à sable,
validé après une bascule, écrivait ses opérations dans le dossier réel.
Chaque base a maintenant ses répertoires propres.

**Le bac à sable expirait au bout de 8 heures, vers le dossier principal.**
Là où les autres dossiers durent 180 jours. Le cookie expirait souvent d'un
jour à l'autre : une page de propositions d'import laissée ouverte la
veille écrivait alors dans la comptabilité réelle. Durée alignée.

**La ligne de commande ne connaissait qu'un dossier.** Elle codait en dur
le dossier principal, alors que l'interface résout le dossier courant par
son registre : quelqu'un travaillant depuis des semaines dans un dossier
secondaire voyait ses commandes agir ailleurs — une clôture dans un
dossier qu'il ne regardait plus, et celui qu'il voulait clore resté
ouvert. Le chemin de la base n'apparaissait nulle part. Chaque commande
l'annonce désormais, et `--dossier` vise le registre.

**La clôture en ligne de commande ne sauvegardait rien.** Même opération
irréversible que la clôture web, qui elle prend une sauvegarde et archive
le FEC. Sauvegarde préalable ajoutée, et son échec interdit la clôture.

- 6 tests ajoutés (534 au total).


## 8.39.0 — 2026-09-06 (amortissement minimum : article 39 B)
Signalé par l'auteur : on ne prolonge pas librement la durée de vie d'une
immobilisation. L'article 39 B du CGI impose un amortissement MINIMUM —
à la clôture de chaque exercice, le cumul pratiqué ne peut être inférieur
au cumul linéaire calculé sur la durée retenue à l'ORIGINE. Allonger la
durée réduit l'annuité, fait décrocher le cumul de ce minimum, et l'écart
constitue un amortissement irrégulièrement différé : définitivement perdu,
à la différence du report de l'article 39 C qui, lui, se rattrape.

Le logiciel acceptait l'allongement en silence — dotation ramenée de
1 600 à 1 000 € sur un cas éprouvé, sans le moindre message. Un contrôle
le signale désormais, en citant la règle et en rappelant l'exception :
revenir à la durée normale après une réduction motivée (obsolescence
prévue, sinistre) qui n'a plus lieu d'être reste légitime. Le logiciel ne
conservant pas la durée d'origine, l'allongement se déduit de sa
signature — le cumul en compte dépasse ce que le plan actuel prévoyait.

- 1 test ajouté (528 au total).


## 8.38.0 — 2026-09-06 (revue Passe C : la liasse d'un exercice de cession)
Le réexamen des points écartés a produit deux constats NOUVEAUX, tous deux
sur la liasse d'un exercice de cession, et l'un d'eux touche la case que
le déclarant recopie.

**La liasse provisoire majorait la base imposable de toute la
plus-value.** La 2033-B recalculait le résultat fiscal à la main —
résultat comptable, report, reprise, retraitements — en omettant la
neutralisation de la cession que `_calcul_fiscal` applique pourtant, et
que son propre commentaire présente comme la « source unique » de la
règle. Sur un cas éprouvé : case 5NA à 30 000 € au lieu de 18 016 €, avec
deux résultats fiscaux contradictoires dans le même document, le bloc de
projection donnant le bon.

**Toute liasse d'exercice de cession sortait auto-déclarée non
conforme.** Même racine : la ligne 352, qui doit valoir zéro par
convention, valait exactement la plus-value comptable. Le contrôle
s'allumait, le PDF imprimait « ANOMALIE » — sur un montage parfaitement
tenu.

**Correction de mon propre correctif de la v8.35.0.** La requête qui
récupérait la dotation d'un bien cédé ne filtrait pas sur le bien : chaque
cédé recevait la SOMME des dotations de tous les cédés de l'exercice, et
pesait donc beaucoup trop dans la répartition du report — au détriment des
biens conservés, dont la part partait avec les sortants.

**Un avertissement alarmant et faux à chaque cession.** Le contrôle qui
compare la dotation comptabilisée au plan théorique comptait la dotation
de cession, absente de ce plan puisqu'il exclut les composants sortis :
l'écart était garanti, égal à cette dotation.

**Le contrôle du déficit menacé ne parlait qu'après la clôture.** Il lit
une table écrite par la seule clôture, donc se taisait jusqu'au moment où
il n'est plus temps d'agir — alors que le rapport se lit AVANT de figer la
liasse, et que la simulation connaît déjà la reprise. Il interroge
désormais la projection quand la table est muette. Sa première requête
n'était par ailleurs pas protégée alors que la seconde l'était : sur une
base sans la table, c'est tout le rapport qui tombait.

**Un constat REFUSÉ, et c'est le test en or qui a tranché.** La revue
proposait de n'admettre au plafond 39 C que le retraitement automatique,
un retraitement manuel portant sur une charge non afférente au bien le
majorant à tort. Le raisonnement est juste, mais la restriction aurait
décalé les trois exercices de référence de 26, 57 et 61 € : le dossier
réel passe précisément l'ALUR en retraitement manuel, et les liasses du
cabinet montrent le plafond majoré d'autant. Le comportement est conservé,
la raison écrite dans le code, et un contrôle avertit désormais quand un
retraitement manuel majore le plafond — le logiciel ne pouvant pas savoir
si la charge retraitée est afférente au bien.

Également corrigé : la cession réécrivait la date de sortie de TOUS les
composants du bien, y compris ceux sortis lors d'un exercice antérieur,
modifiant rétroactivement le périmètre d'exercices clos.

- 7 tests ajoutés (527 au total).


## 8.37.0 — 2026-09-06 (revue Passe B : trois chemins de perte de données)
19 points signalés, 13 retenus. Trois d'entre eux menaient à une perte de
données irréversible.

**`init()` détruisait une base tenue, sans un mot.** Le fichier était
supprimé sans test de contenu ni sauvegarde — et `main()` visait par
défaut la base du dossier principal, avec la commande donnée en tête du
mode d'emploi. Une année de saisie disparaissait sur un « python
init_db.py » lancé par curiosité, et la base neuve étant cohérente, rien
ne distinguait la destruction d'un bug d'affichage. Reproduit : 12
écritures effacées. La fonction refuse désormais, et `--ecraser` prend une
sauvegarde avant de détruire. Les fichiers annexes du moteur partent avec
la base : un journal résiduel se serait rattaché à la base neuve.

**Une restauration réattribuait des numéros de quittance déjà remis.** Le
compteur se calcule dans la base ; une restauration le remettait en
arrière, et les numéros déjà portés par des documents chez des locataires
étaient réattribués. La contrainte d'unicité n'y voyait rien : les deux
documents existaient dans deux états différents de la base. La
restauration est refusée avec le nombre de quittances menacées.

**Rien ne rattachait une sauvegarde à son dossier.** Tous les dossiers
nomment leur base « compta.db », donc leurs sauvegardes sont strictement
homonymes ; restaurer celle d'un autre dossier remplaçait une
comptabilité par une autre, les deux contrôles d'intégrité passant sans
broncher. La sauvegarde doit désormais appartenir au dossier restauré.

**En colocation, chaque occupant recevait la totalité du loyer.** Le
montant est lu par LOGEMENT, l'unicité ne portait que sur le locataire :
1 600 € attestés pour 800 € encaissés, chaque quittance étant
individuellement « conforme aux écritures ». Le second appel est refusé,
avec la marche à suivre pour ventiler.

**Une quittance survivait à l'annulation de son encaissement.** Les
montants sont figés à l'émission ; après une contre-passation, le document
attestait une somme jamais perçue et restait imprimable à l'identique. La
quittance est désormais confrontée aux écritures à chaque lecture, et
l'écart s'affiche en rouge à l'écran comme avant impression.

**Autres corrections** : les sauvegardes de sûreté (avant-migration,
avant-restauration, avant-réinitialisation) sortent de la rotation — elles
disparaissaient précisément dans le scénario où elles servent ; un palier
de migration manquant était sauté en silence puis la base marquée à jour,
une assertion le rend désormais impossible ; les deux branches de
sélection des gabarits appliquaient des règles opposées, l'une inerte et
l'autre absente ; la liste des quittances utilisait des jointures internes
et masquait celles dont le bien avait été supprimé, alors que leurs
numéros restaient consommés ; l'année par défaut suit l'horloge ; le mode
démo valide son année AVANT toute destruction ; le repli sur le jeu de
démonstration anonymisé était mort-né, le chemin par défaut n'étant jamais
testé pour son existence ; périodes impossibles (mois 00 ou 13), montants
négatifs et dates de paiement invalides sont refusés.

- 11 tests ajoutés (520 au total).


## 8.36.0 — 2026-09-06 (revue Passe A : lecture, validation, migration FEC)
14 points signalés, 11 retenus — et 2 défauts supplémentaires découverts
en vérifiant, que la revue n'avait pas vus parce qu'un défaut antérieur
les masquait. **Aucun dossier de cabinet ordinaire n'était migrable.**

**Les à-nouveaux ignoraient la trésorerie.** Le bilan d'ouverture ne
retenait que les classes 1, 2 et 4 : la classe 5 — la BANQUE — était
omise. Tout dossier tenu avec un compte bancaire dédié, c'est-à-dire le
cas ordinaire, produisait une écriture d'à-nouveaux déséquilibrée du
montant exact du solde, et la reprise s'arrêtait sur « Écriture
déséquilibrée » en accusant une écriture que l'utilisateur n'avait jamais
saisie. Deux modules ne s'accordaient pas sur ce qu'est un compte de
bilan : `migration_fec` retenait déjà les classes 1 à 5.

**Un guillemet faisait disparaître des lignes.** Le format FEC ne donne
aucun rôle au guillemet, mais le lecteur CSV de Python le traite comme un
délimiteur de champ : un seul guillemet non refermé dans un libellé
fusionnait toutes les lignes jusqu'au suivant, qui s'évanouissaient de la
balance sans un mot. Reproduit : 6 lignes lues comme 4.

**Le rejeu fusionnait des écritures sans rapport.** Beaucoup de logiciels
de cabinet numérotent PAR JOURNAL — AC 1..n, BQ 1..n. Grouper sur le seul
numéro transformait une facture d'achat et son règlement bancaire en une
écriture unique, portant le journal et la date de la première. Les
balances restaient exactes au centime, si bien que rien ne se voyait —
mais l'exercice rejoué n'était plus le FEC source.

**Deux encodages pourtant conformes étaient illisibles.** L'ISO-8859-15
est explicitement autorisé par l'arrêté et courant chez les éditeurs ;
il provoquait une erreur brute, y compris dans le validateur dont c'était
le rôle de la diagnostiquer. Et la marque d'ordre des octets ajoutée par
Excel rendait la première colonne méconnaissable.

**Découverts en vérifiant** : le rejeu créait les comptes manquants sans
renseigner leur `type`, colonne NOT NULL — et la reprise ne les créait pas
du tout, échouant sur une contrainte de clé étrangère qui ne nommait même
pas le compte fautif. Le typage est désormais déduit du numéro selon le
PCG, les comptes d'amortissement recevant leur type propre.

**Autres corrections** : une seconde reprise depuis un FEC externe
doublait le bilan d'ouverture en silence — refusée ; un rejeu interrompu
laissait une transaction ouverte que le premier commit venu d'ailleurs
figeait — annulation explicite ; le contrôle des amortissements se taisait
justement quand le FEC ne portait aucune dotation, et avalait toute
exception ; la borne du plan se lisait sur un exercice non clos ; deux
versions de règle à date d'effet identique rendaient le choix arbitraire.

- 8 tests ajoutés (509 au total).


## 8.35.0 — 2026-08-15 (revue adversariale n° 3 : 8 défauts sur 8 confirmés)
Première revue externe dont **tous** les constats tiennent. Elle avait
rejoué les scénarios contre une base réelle et donnait les montants
exacts — retrouvés au centime lors de la vérification.

**Le résultat comptable ignorait les charges exceptionnelles.** Les
produits étaient captés par le préfixe « 7 », donc le prix de cession y
entrait ; mais aucune charge de classe 67 ne l'était, si bien que la
valeur comptable du bien cédé (675000) manquait. La ligne 310 comptait la
recette de la vente sans sa contrepartie. Sur une cession à titre gratuit,
le résultat était majoré de toute la valeur nette du bien — 3 753,42 € sur
le cas éprouvé — sans qu'aucun contrôle ne bronche.

**Le tableau des immobilisations gardait les biens cédés.** Sortis du
bilan mais toujours en 2033-C : les deux divergeaient définitivement.

**Le report d'amortissement disparaissait quand un exercice manquait.**
Le stock d'ouverture se lisait strictement en N-1 ; sur une série non
contiguë — reprise depuis des FEC incomplets, année sans activité — il
retombait à ZÉRO. Un report qui ne se périme jamais s'évaporait, et le
bénéfice suivant était déclaré en trop (3 000 € au lieu de 0). C'était
aussi une incohérence interne : la ventilation par bien lisait déjà le
dernier exercice connu, si bien que la somme par bien cessait d'égaler le
global — l'invariant que le projet revendique.

**Un changement de durée pouvait sur-amortir.** Le plan se recalculait à
neuf depuis la mise en service, sans borne sur ce qui avait déjà été
comptabilisé. La dotation est désormais plafonnée au reste à amortir, lu
sur le dernier exercice clos — et non sur la somme de tous, qui aurait
doublé le cumul par les à-nouveaux.

**La dotation de cession était proratisée DEUX FOIS.** L'annuité du plan
l'est déjà ; la multiplier encore par la fraction 1er janvier → cession se
trompait dans les deux sens : 627,05 € au lieu de 586,30 € pour une mise
en service en cours d'année, 245,91 € au lieu de 495,89 € pour une
dernière annuité tronquée. Le calcul part maintenant de l'annuité pleine,
proratisée sur la seule période de détention de l'exercice.

**La docstring encourageait le double retraitement** en donnant le fonds
ALUR comme exemple de saisie manuelle — alors qu'il est réintégré
automatiquement et que les deux montants s'additionnent.

**Un bien cédé ne perdait pas sa part de report.** Les poids de
ventilation venaient du plan d'amortissement, qui ignore les biens cédés :
leur part restait attachée aux autres au lieu de sortir avec eux.

**Les cases de la 2042-C-PRO n'étaient pas sur la même base** : 5NA donnait
le bénéfice AVANT imputation, 5GA→5GJ les déficits APRÈS. L'administration
imputait donc une seconde fois un déficit déjà consommé — impôt sur un
bénéfice qui ne l'était pas, et reliquat perdu. Les déficits sont
désormais déclarés tels qu'ils étaient à l'ouverture, reconstitués en
rembobinant l'imputation FIFO.

Point commun des huit : aucun ne provoquait d'erreur, aucun n'était
visible, et chacun faussait un montant déclaré.
- 8 tests ajoutés (501 au total).


## 8.34.0 — 2026-08-14 (revue du catalogue de saisie : 4 constats retenus)
Revue étroite des 36 gabarits — d'un tout autre calibre que les deux
précédentes : verdicts nuancés, sources vérifiables, incertitude assumée
là où elle existait. Quatre constats retenus, quatre réfutés.

**RETENU — la caution mutuelle d'un prêt n'est pas une charge.** Les frais
de garantie se partagent en deux : la commission est acquise à
l'organisme, mais la part versée au fonds mutuel de garantie est
RESTITUABLE en fin de prêt. C'est une créance, pas une dépense — la
déduire revient à déduire une somme qui sera rendue. Le libellé du gabarit
le dit désormais, et le pense-bête explique comment lire son offre de prêt.

**RETENU — deux conditions sur les frais d'acquisition.** L'option pour la
déduction immédiate est GLOBALE et irrévocable : elle vaut pour toutes les
immobilisations, pas bien par bien. Et surtout — le point le moins connu —
un logement acquis AVANT d'être affecté à la location meublée, cas le plus
fréquent en LMNP, entre au bilan pour sa valeur à la date d'affectation :
les frais payés à l'achat d'origine ne sont alors pas déductibles.

**RETENU — une régularisation en faveur du LOCATAIRE était impossible à
saisir.** Les montants sont strictement positifs partout, et la contrainte
de schéma le fait respecter. La réponse n'était pas d'affaiblir cette
garde — c'est elle qui protège des saisies inversées — mais d'ajouter la
nature manquante : « Restitution de charges au locataire » débite le
compte de produit, ce qui en diminue le solde. Aucune valeur négative dans
le FEC, qui n'en admet pas, et les agrégats nettent d'eux-mêmes puisqu'ils
raisonnent par classe de compte.

**RETENUS — deux pièges de classement** ajoutés au pense-bête : la taxe
d'habitation due parce que le propriétaire garde la jouissance du logement
n'est pas une charge de l'exploitation ; et une indemnité d'assurance
versée pour la DESTRUCTION d'un bien immobilisé relève du régime des
plus-values, non d'un produit ordinaire.

**RÉFUTÉS — quatre « comptes à revoir », par la pratique professionnelle.**
La revue proposait de corriger quatre comptes au nom du PCG strict :
essence en 6068 plutôt que 606200, assurances emprunteur et GLI éclatées
sur 616800 et 616500, taxe foncière en 635120. Vérification faite sur les
trois FEC réels qui servent d'étalon au projet : le cabinet emploie
exactement nos comptes — 606200 pour l'essence, 616110 pour toutes les
primes, 635130 pour les impôts locaux. Un plan comptable est un cadre que
les cabinets adaptent ; nous en éloigner nous couperait de la seule
référence vérifiée dont dispose le projet. Réfutation figée par test.

- 4 tests ajoutés (493 au total). La checklist du pense-bête passe à 19
  points, dont 8 sourcés.


## 8.33.0 — 2026-08-14 (revue adversariale externe n° 2 : 1 défaut sur 11)
Onze défauts annoncés, chacun tranché empiriquement contre le code. **Dix
réfutés, un réel** — et celui-là valait la revue à lui seul.

**LE DÉFAUT RÉEL — un déficit peut se perdre à cause du report d'amortissement.**
Les deux reports n'ont pas la même durée de vie : les amortissements
reportés au titre de l'article 39 C s'imputent sans limite de temps, un
déficit LMNP se périme à dix ans. Or le 39 C s'impute EN PREMIER par
construction — sa reprise entre dans le calcul du résultat fiscal, sur
lequel les déficits s'imputent ensuite. Quand le bénéfice ne suffit pas à
absorber les deux, c'est donc le déficit, le seul périssable, qui se perd.
Reproduit : bénéfice 5 000 €, stock 39 C 5 000 €, déficit 5 000 € — le
39 C absorbe tout, le déficit reste entier et périmera.

Le logiciel ne CHANGE PAS cet ordre de lui-même. Savoir si la reprise du
39 C peut être différée à volonté est une question qui se discute, et la
trancher en silence dans le sens favorable serait exactement le genre de
décision qu'un logiciel ne doit pas prendre à la place de son utilisateur.
Un contrôle la signale, chiffrée, avec les millésimes et les dates de
péremption, et invite à la porter à un professionnel.

**Les dix réfutations, mesurées.** Trois des quatre fonctions citées par
la revue n'existent pas dans le code (`ventiler_charges_communes`,
`calculer_plafond_39c`, `generer_ecritures_amortissement`) : la revue a
raisonné sur un logiciel imaginé. Vérifié par mesure directe :
- le prorata est en JOURS RÉELS (0,547945 pour 15/06→31/12, soit 200/365
  et non 6,5/12) — c'est l'invariant n° 5, prouvé contre trois liasses ;
- le stock 39 C EST neutralisé à la cession, la sortie est tracée par bien
  et affichée à l'écran depuis la v8.23.0 ;
- le plafond 39 C dérive des produits RÉELLEMENT saisis : sur un exercice
  de neuf mois il vaut 9 000 € et non 12 000 € — il n'y a aucun montant
  annuel à proratiser ;
- la reclôture après réouverture est REFUSÉE en nommant l'écriture déjà
  passée : aucun double compte de dotation possible ;
- un composant ajouté à un bien déjà amorti suit son propre plan, exact au
  centime ; l'écart 2033-C évoqué a une autre cause, connue et corrigée en
  v8.11.0, signalée par son propre contrôle ;
- aucune ventilation automatique des charges communes n'existe : chaque
  opération porte le bien choisi à la saisie ;
- la cession porte sur un bien entier — fonctionnalité absente, pas calcul
  faux ;
- le contrôle « le stock 39 C doit être nul » n'existe nulle part.

Chaque réfutation est désormais FIGÉE par un test : si l'un de ces
comportements changeait vraiment un jour, il faudrait le savoir.
- 7 tests ajoutés (489 au total).


## 8.32.0 — 2026-08-14 (reprise de PLUSIEURS FEC, avec autocontrôles)
La reprise n'acceptait qu'un fichier, et l'année devait être saisie à la
main. Un FEC isolé est une photographie ; plusieurs FEC consécutifs sont
un film, et le film se vérifie tout seul.

**Trois contrôles qu'un fichier unique rend impossibles :**
- **Jonction des bilans** — le solde de clôture de chaque compte en année
  N doit se retrouver à l'ouverture de N+1. C'est le défaut de migration
  le plus fréquent et le plus silencieux : une écriture ajoutée après coup
  dans l'exercice précédent, ou un fichier qui n'est pas la version
  définitive. Deux pièges rencontrés en le construisant : comparer deux
  CLÔTURES successives n'a aucun sens (leur écart est l'activité de
  l'année — il faut comparer la clôture de N à l'OUVERTURE de N+1, soit
  au seul journal d'à-nouveaux), et le compte de résultat (classe 12) doit
  être exclu, car il naît aux à-nouveaux puis se solde par affectation :
  sans cette exclusion, chaque jonction affichait un faux écart.
- **Amortissements** — avec plusieurs années de dotations réelles, le plan
  recalculé par le logiciel est confronté à celui du prestataire
  précédent. C'est le « test en or » du projet, appliqué au dossier de
  celui qui migre. Un écart durable fausserait toutes ses liasses à venir.
- **Continuité** — année manquante dans la série, exercice en double,
  exercice déjà présent dans le dossier.

**L'ordre est déduit du CONTENU**, pas du nom de fichier ni de l'ordre de
sélection : les dates d'écriture sont dans le fichier, le nom est une
convention que rien ne garantit. Rejouer 2025 avant 2023 produirait des
à-nouveaux absurdes, et l'utilisateur n'a aucune raison de connaître cette
contrainte.

**Deux temps séparés.** L'analyse n'écrit RIEN : elle montre ce qu'elle a
compris — l'ordre, les jonctions, les dotations — et l'utilisateur décide
ensuite. On ne défait pas trois exercices d'un clic.

Vérifié sur trois exercices réels envoyés dans le désordre : classement
correct, jonctions raccordées au centime, reprise du plus ancien au plus
récent.
- 6 tests ajoutés (482 au total).


## 8.31.0 — 2026-08-14 (quittances durcies, bandeau ASM)

**Date et lieu de naissance : champs SUPPRIMÉS.** Ils étaient facultatifs
et jamais imprimés — cela ne suffisait pas. Un champ qui existe finit par
être rempli, et une donnée qu'on ne détient pas est une donnée qu'on n'a
ni à protéger, ni à justifier, ni à effacer sur demande. Retirés du
schéma, du module, de la page et de la route ; un test vérifie qu'ils ne
peuvent pas revenir.

**Numérotation vérifiée sur plusieurs biens.** Éprouvée avec 3 logements,
4 locataires (dont un sortant et son remplaçant) et 3 années : la série
est UNIQUE, continue et sans doublon à travers tous les logements — et
non une série par bien, qui rendrait la suite invérifiable. Elle suit
l'ordre d'ÉMISSION, comme une numérotation de factures : une quittance
établie aujourd'hui pour un mois ancien reçoit le numéro suivant, et non
un numéro intercalé. C'est désormais écrit dans la page.

**Quittances anciennes.** Elles l'étaient déjà, sans limite d'ancienneté ;
elles sont maintenant plus faciles à retrouver — filtre par année, colonne
du logement, et une phrase qui le dit.

**Audit de non-régression du module** (huit points vérifiés) : émettre des
quittances ne crée ni écriture, ni ligne, ni opération ; la clôture, la
liasse et les contrôles sont inchangés ; le FEC exporté reste conforme et
ne contient aucune trace de locataire ; les quittances survivent à une
sauvegarde-restauration ; une base antérieure migre correctement (schéma
v6, palier de migration 6) et la page ne tombe pas même sans migration ;
les douze pages répondent ; le bac à sable reste cloisonné du dossier
réel. Les tables sont désormais déclarées dans `schema.sql`, tout en
restant créées à la volée pour les installations existantes.

**Bandeau aux couleurs du club** : fond bleu marine, onglet actif en jaune.
Le contraste jaune sur marine est nettement plus franc que le blanc sur
bleu moyen d'avant.
- 7 tests ajoutés (476 au total).


## 8.30.0 — 2026-08-14 (retours d'une utilisatrice profane + module quittances)

**Une régression rattrapée au passage, et elle était grave.** Le bouton
d'annulation par contre-passation avait DISPARU de la liste des
opérations — perdu lors d'une restauration de fichier — alors que la route
existait toujours. Le premier bloquant trouvé par le panel bêta était donc
revenu en silence. Il est de nouveau là, dans sa propre colonne à côté de
la duplication, et une opération déjà annulée n'offre plus ni l'un ni
l'autre.

**Lisibilité.** Le nom du dossier, dans le bandeau, était un lien SANS
couleur explicite : bleu par défaut sur fond bleu, illisible. L'onglet
courant ne se distinguait pas davantage — blanc sur bleu, souligné de bleu
clair. Les deux passent au jaune, avec un fond assombri pour l'onglet actif.

**Premier lancement guidé.** Sur un dossier vierge, l'onglet « Démarrer »
passe en tête et la configuration initiale — nom, SIREN, adresse —
s'affiche directement, au lieu d'être cachée dans la page Immobilisations.
Un encadré répond à la question qui revenait : **l'exercice est déjà
ouvert**, il n'y a rien à créer avant de saisir ; l'onglet « Nouvel
exercice » ne sert qu'à l'année suivante ou à reprendre un historique
depuis des FEC.

**Avertissements dès le premier exercice.** Le contrôle de plausibilité
compare à l'an dernier : sur un dossier neuf il n'avait rien à comparer et
se taisait, laissant sans filet celui qui en a le plus besoin. Un nouveau
contrôle signale les postes quasi certains qui manquent — intérêts
d'emprunt, assurance, taxe foncière, CFE, charges de copropriété — en
INFO, jamais bloquant : un achat comptant ou une maison hors copropriété
sont parfaitement légitimes.

**Risque de double retraitement écarté.** Le champ « autres retraitements
fiscaux » donnait le fonds ALUR en EXEMPLE, alors qu'il est déjà réintégré
AUTOMATIQUEMENT depuis les écritures de ventilation : le saisir là le
comptait deux fois. Le libellé indique désormais de laisser 0 dans la
quasi-totalité des cas, avec une infobulle qui explique le piège.

**Documents.** `INSTALLATION.md` devient `LISEZ-MOI.md`. Les deux commandes
Linux et macOS sont données DANS L'ORDRE, avec le `cd` — indispensable et
souvent oublié, il explique la plupart des « Aucun fichier ou dossier de
ce nom » — et l'astuce du clic droit « Ouvrir un terminal ici ».

**NOUVEAU — module Quittances.** Locataires (logement, dates de présence,
loyer et charges), émission de quittances et impression.
- Les montants sont **lus dans les écritures** : la quittance reflète la
  comptabilité au lieu de la doubler. Deux jeux de chiffres finiraient par
  diverger — et c'est la quittance, remise à un tiers, qui ferait foi
  contre le bailleur.
- **Numérotation incrémentale et sans trou**, comme celle des écritures :
  c'est ce qui la rend vérifiable.
- Trois refus : deux quittances pour le même mois (deux preuves du même
  paiement), une quittance sans encaissement (elle atteste d'un paiement
  REÇU), une période hors présence du locataire.
- Document conforme à l'article 21 de la loi n° 89-462 du 6 juillet 1989,
  qui impose la distinction du loyer et des charges et la remise gratuite
  au locataire qui la demande. Imprimable depuis le navigateur — donc
  enregistrable en PDF — sans dépendre de reportlab.
- Date et lieu de naissance sont proposés en OPTION et **jamais imprimés** :
  une quittance n'en a pas besoin. Moins on conserve de données sur un
  tiers, moins on a d'obligations à son égard.
- 13 tests ajoutés (469 au total).


## 8.29.0 — 2026-08-13 (Linux Mint : « ./.venv/bin/pip : aucun fichier »)
Signalé sur Linux Mint XFCE, avec un message d'erreur suivi de rien.
Trois défauts, tous dans la création de l'environnement local.

**1. Le lanceur appelait le SCRIPT pip, pas le module.** Sur Debian et ses
dérivés — donc Mint — `./.venv/bin/pip` peut manquer alors que le module
pip est parfaitement présent : le paquet système fournit l'un sans
l'autre. `python -m pip` fonctionne dans les deux cas. Tous les appels
sont convertis, et un test interdit désormais d'appeler le script.

**2. Le test « le dossier .venv existe-t-il ? » était trompeur.** Une
création interrompue laisse un environnement incomplet ; le lancement
suivant le croyait prêt et mourait sans un mot. Le lanceur vérifie
maintenant que l'environnement FONCTIONNE (`python -m pip --version`), et
reconstruit s'il est abîmé.

**3. Une création réussie ne garantit pas la présence de pip.** Le cas
exact rencontré. `ensurepip` permet de le rattraper sans rien réinstaller ;
à défaut seulement, le message indique le bon paquet — `sudo apt install
python3-venv python3-pip` — au lieu du `python3-venv` seul, insuffisant ici.

Vérifié en reproduisant les deux situations : un `.venv` créé sans pip et
un `.venv` incomplet laissé par un échec. Les deux se rattrapent
maintenant tout seuls, sans intervention.

Au passage : l'échec de `python3 -m venv` affiche désormais SA propre
sortie d'erreur (elle disait précisément quoi installer, et elle était
avalée) ; l'échec d'installation de Flask distingue le défaut de connexion
du proxy d'entreprise ; et reportlab, qui ne sert qu'à l'export PDF, ne
peut plus bloquer le lancement.

**Le lanceur Windows souffrait du même piège n° 2** — il testait la
présence de `python.exe` et non le fonctionnement de pip. Aligné, avec
reconstruction automatique et amorçage par `ensurepip`.
- 5 tests ajoutés (457 au total).


## 8.28.0 — 2026-08-13 (pense-bête : actualités, notes, et deux erreurs corrigées)

**Deux erreurs fiscales signalées par l'auteur, vérifiées et corrigées.**
Elles décrédibilisaient tout le reste ; leur correction est la partie la
plus importante de cette version.
- **Frais de déplacement — confusion entre deux barèmes.** Le texte
  affirmait qu'« on ne cumule pas barème kilométrique et frais réels ».
  C'était faux deux fois. D'abord, le barème KILOMÉTRIQUE ne s'applique
  pas aux BIC : il vise les traitements et salaires et les BNC. En BIC,
  c'est le barème CARBURANT (BOI-BAREME-000003), ouvert aux exploitants
  individuels au réel simplifié ayant opté pour la comptabilité
  super-simplifiée. Ensuite, ce barème ne couvre QUE le carburant : péages,
  stationnement, assurance et entretien se déduisent EN PLUS, au réel et
  au prorata professionnel.
- **Rattachement — le LMNP n'est pas en engagement pur.** Le texte posait
  « c'est l'engagement qui compte, pas le décaissement ». En réalité, la
  quasi-totalité des LMNP relèvent du réel simplifié et peuvent opter pour
  la comptabilité super-simplifiée (case en tête de la 2031-SD) : trésorerie
  en cours d'année, constatation des créances et dettes à la CLÔTURE, avec
  une exception pour les frais généraux à échéances régulières. C'est
  d'ailleurs le modèle du logiciel — le pense-bête le contredisait.

**Précisions chiffrées et sources.** Les durées de conservation sont
désormais données : droit de reprise de 3 ans (LPF art. L. 169),
conservation de 6 ans (LPF art. L. 102 B), 10 ans pour les livres et
pièces comptables (Code de commerce art. L. 123-22). Les dépôts indiquent
les DEUX espaces distincts d'impots.gouv.fr et le chemin pour y accéder :
espace professionnel pour la liasse 2031/2033, espace particulier pour la
2042-C-PRO. Chaque point corrigé cite ses sources, affichées sous le texte.

**Nouvelle rubrique « Actualités réglementaires ».** Faits DATÉS et
sourcés, distincts de la checklist intemporelle. Premier sujet : la
facturation électronique, avec le point contre-intuitif que la fiche
officielle de la DGFiP établit — l'exonération de TVA des loyers ne
dispense PAS de l'obligation de RÉCEPTION au 1er septembre 2026, car
c'est l'assujettissement qui compte, pas l'exonération. L'émission, elle,
ne concerne que les redevables (para-hôtellerie, résidences de services)
au 1er septembre 2027. Un tableau récapitule les échéances de l'année et
indique OÙ faire chaque démarche. Aucune plateforme n'est recommandée :
le choix appartient à l'utilisateur, et un test interdit de nommer un
prestataire dans cette rubrique.

**Bloc-notes personnel.** Un espace libre où consigner ce que la veille
apprend, les questions à poser, les points à vérifier l'an prochain.
Conservé dans la table `meta` du dossier : il suit les sauvegardes, les
restaurations et les changements de dossier, et ne quitte jamais la
machine.

**Veille fiscale** : le prompt interroge désormais aussi l'état de la
réforme de la facturation électronique.
- 6 tests ajoutés (451 au total).


## 8.27.0 — 2026-07-30 (l'assistante, refonte complète du sprite)
Le personnage précédent, dessiné en courbes, ne convenait pas. Refonte
totale en pixel art « chunky » : heaume à couronne étagée, visière verte
(la signature comptable), regard dans l'ombre du casque, pauldrons larges,
tabard bleu à emblème doré, cape effilée, et une tablette qui flotte à
côté de lui.

**Création ORIGINALE, et c'est un choix, pas une approximation.**
L'illustration de référence apportée était un personnage de jeu vidéo
appartenant à un éditeur. Le reproduire dans un logiciel diffusé sous le
copyright de l'auteur aurait annulé le travail des versions 8.16 à 8.20 —
établir sa propriété, retirer le nom d'un cabinet pour ne pas s'exposer,
écrire un contrôle qui refuse de publier le moindre terme sensible. Seul
le REGISTRE VISUEL a donc été repris : gros pixels francs, contour noir
épais, palette contrastée. Un style ne se protège pas ; un personnage si.
Un test verrouille l'absence de toute marque tierce dans le sprite.

- Sprite 24 × 21, 92 rectangles après fusion des pixels voisins.
- Trois états ne repeignent que ce qui change : l'écran de la tablette et
  la lueur du regard (verte quand tout est validé, rouge à l'alerte).
- 2 tests ajoutés (446 au total), dont un qui vérifie que la carte du
  sprite reste rectangulaire et n'utilise aucune couleur non définie.


## 8.26.0 — 2026-07-30 (documents dédoublonnés, assistante en pixel art)

**README et INSTALLATION se recopiaient — et avaient divergé.**
Cinq sections d'installation figuraient dans les deux fichiers. Pire que
la redondance : la copie du README annonçait encore un démarrage en HTTPS
sur `https://localhost:5000`, abandonné depuis la v8.15.0. Une consigne
recopiée à deux endroits ne gaspille pas de la place, elle finit par
mentir. Le README (467 → 408 lignes) décrit ce que fait le logiciel et
comment il est construit, et renvoie à LISEZ-MOI.md pour tout le reste.

**LISEZ-MOI.md enrichi pour aller plus vite** : liens de téléchargement
directs de Python par système (dont Windows, avec le rappel de cocher
« Add python.exe to PATH » — sans quoi le lanceur ne le trouve pas), la
commande exacte pour chaque distribution Linux, tableau de lancement par
système, options du lanceur, et un renvoi vers le bac à sable pour
découvrir le logiciel sans rien saisir.

**Les chiffres personnels de l'auteur ont quitté le README.** Un débutant
qui lit « valeur brute totale 139 908,66 € » se demande d'où sort ce
montant au lieu de retenir ce que la ligne démontre. Les grandeurs sont
désormais décrites, pas chiffrées — et les références de pièce réelles
ont disparu.

**Terminologie** : « prestataire de référence » devient « les acteurs
payants actuels ». Le remplacement automatique de la v8.20.0 avait laissé
des accords cassés (« de le prestataire », « façon le prestataire ») :
28 fichiers relus et corrigés.

**L'assistante est refaite en PIXEL ART.** La version dessinée en courbes
était laide, et à juste titre : dessiner une illustration au trait demande
un métier que ce projet n'a pas. Le pixel art contourne le problème — il
est honnête sur sa définition, lisible à petite taille, et se dessine sur
une grille. Le sprite (26 × 28) est décrit par une CARTE en caractères
dans `outils_sprite.py`, qui fusionne les pixels voisins de même couleur :
310 pixels deviennent 125 rectangles. Les trois états ne repeignent que ce
qui change — écran de la tablette, bouche, sourcils — au lieu de trois
sprites entiers. `image-rendering: pixelated` interdit au navigateur de
lisser les bords, et les animations avancent par PALIERS (`steps`) : un
sprite qui glisse en sous-pixels trahirait la technique.
- 444 tests (inchangé), tests de l'assistante réécrits pour le sprite.


## 8.25.0 — 2026-07-23 (portabilité : Linux couvert, macOS enfin traité)

**Linux — 28 bureaux passés en revue, 27 étaient déjà couverts.**
Seul elementary OS manquait (`io.elementary.terminal`), désormais ajouté.
Sont reconnus les terminaux par défaut d'Ubuntu et toutes ses variantes,
Debian, Fedora (Workstation et KDE), Bazzite et Silverblue, Linux Mint
dans ses trois éditions, Pop!_OS, Zorin, elementary, Manjaro, Arch,
openSUSE, SteamOS, Raspberry Pi OS, Deepin, Solus, ainsi que les
environnements minimalistes (kitty, foot, alacritty, wezterm).

**macOS — le fichier s'appelait « Linux-macOS » et ne l'était pas.**
Aucune des différences entre les deux systèmes n'était traitée. Le plus
grave : `readlink -f` est une extension GNU, absente de BSD avant macOS
12.3 — et c'était la TOUTE PREMIÈRE instruction du script. Avec
`set -e`, il s'arrêtait donc là, avant le moindre message. Le nom du
fichier promettait un support qui n'existait pas. Corrigé :
- résolution de chemin en POSIX pur, sans `readlink -f` ;
- détection du système (`uname -s`), dont tout le reste dépend ;
- terminal : Terminal.app et iTerm sont des APPLICATIONS, jamais trouvées
  par `command -v` — on passe par `open -a`, et sans `exec` aveugle (si
  l'ouverture échoue, `exec` aurait déjà remplacé le processus et le
  script mourrait sans un mot) ;
- navigateur : `open`, l'ouvreur du système, `xdg-open` n'existant pas ;
- notification : `osascript` au lieu de `notify-send` ;
- diagnostic de port : `lsof` au lieu de `ss` et de `/proc`, absents ;
- raccourci : un fichier `.command` sur le Bureau — l'équivalent natif du
  `.desktop`, double-cliquable depuis le Finder ;
- messages d'installation de Python adaptés (Xcode CLT ou python.org sur
  macOS ; apt, dnf, pacman ou zypper selon la distribution Linux, là où
  « sudo apt install » était faux partout sauf sur Debian et dérivés).

**Deux défauts trouvés en éprouvant ces branches.** `--raccourci` était
relancé dans une fenêtre de terminal alors qu'il ne fait qu'écrire un
fichier — son message de confirmation s'en trouvait caché. Et l'ouverture
du terminal macOS était un `exec` aveugle, qui tuait le script au lieu de
basculer sur le repli.

RÉSERVE : ces branches ont été éprouvées en SIMULANT macOS (interception
de `uname`, `open`, `osascript`), faute de machine Apple. La logique est
vérifiée, le comportement réel reste à confirmer sur un Mac.
- 7 tests ajoutés (444 au total).


## 8.24.0 — 2026-07-23 (Linux : « rien ne se lance », les vraies causes)
Deuxième signalement du même symptôme. Le code du lanceur, relu ligne à
ligne, en a révélé **quatre** — dont la plus embarrassante.

**1. Le lanceur donnait lui-même le mauvais nom.** Son en-tête indiquait
encore `./Lancer-Compta-LMNP.sh`, nom abandonné à la v8.15.0 : qui suivait
cette instruction obtenait « fichier introuvable ». Pire, l'option
`--raccourci` installait dans le menu d'applications une entrée pointant
vers ce fichier inexistant. Le renommage avait été propagé partout SAUF
dans le fichier renommé. Le script déduit désormais son propre nom de son
chemin — il ne peut plus se périmer.

**2. La liste des terminaux ignorait ceux des distributions récentes.**
`ptyxis` est le terminal par défaut de Fedora 40+ et de Bazzite ; `kgx` /
`gnome-console` celui de GNOME. Aucun des deux n'était cherché : sur ces
systèmes, AUCUN terminal n'était trouvé. Dix-huit terminaux sont désormais
reconnus, les défauts actuels en premier.

**3. Le relancement utilisait un chemin relatif.** `gnome-terminal` et
`ptyxis` sont activés par D-Bus et ne transmettent pas le répertoire
courant : `bash ./script` échouait sans un mot. Chemin absolu résolu avant
tout changement de répertoire.

**4. À défaut de terminal, le script continuait EN SILENCE.** Le pire des
cas : l'application démarrait et l'utilisateur ne voyait rien du tout. Il
écrit maintenant `logs/demarrage.log` avec la commande exacte à taper,
envoie une notification de bureau si le système en propose une, et
rappelle l'adresse — l'application démarre quand même, et on le dit.

Le fichier `Compta-LMNP.desktop` livré était cassé lui aussi : `Path=.`
est invalide (la spécification exige un chemin absolu) et `%k` peut valoir
une URI `file://` que `cd` ne comprend pas. Corrigé.

**Au passage — le linter n'était pas épinglé.** Une réinstallation de
l'environnement a suffi pour faire passer le projet de « propre » à 234
erreurs sans qu'une ligne de code ait bougé : le jeu de règles par défaut
de ruff s'était élargi entre deux versions. Le jeu est désormais DÉCLARÉ
dans `pyproject.toml`, et `requirements-dev.txt` épingle les versions. Sur
un dépôt public, c'est la différence entre une CI stable et une CI rouge
un matin, sur une release qu'on n'a pas demandée.
- 7 tests ajoutés (444 au total).


## 8.23.0 — 2026-07-23 (double audit, et l'assistante prend visage)

**Audit comptable — ce qui a tenu.** Un composant totalement amorti cesse
bien de produire des dotations (aucun sur-amortissement, VNC plancher à
zéro). Un exercice COURT (création au 1er juillet) est correctement
proratisé en jours réels. Les montants négatifs sont refusés à la saisie.
La cession neutralise bien la plus-value au titre du régime des
particuliers. Trois clôtures simultanées du même exercice : une seule
aboutit, une seule dotation est écrite.

**Défaut trouvé — le stock 39 C perdu à la cession était invisible.**
Les amortissements reportés restent rattachés au bien qui les a produits :
quand ce bien sort du patrimoine, le stock restant est définitivement
perdu. Le logiciel l'enregistrait bien (ventilation par bien) et le PDF le
montrait — mais à l'écran, le stock passait de 8 000 € à zéro **sans un
mot**, et le « total des reports disponibles » chutait comme s'il avait
été utilisé. Une ligne explicite le dit désormais, en rouge, avec son
infobulle. Même famille que les déficits périmés corrigés en v8.19.0 : un
montant qui disparaît doit s'expliquer.

**Bug trouvé — la ventilation d'un bien n'était pas ATOMIQUE.**
Un montant illisible sur la 3ᵉ ligne laissait les deux premières écrites,
composants ET écritures d'acquisition. L'utilisateur voyait un message
d'erreur, en concluait que rien n'avait eu lieu, recommençait — et
doublait tout. Cause : l'écriture d'acquisition validait sa propre
transaction, si bien que le `rollback` de l'appelant ne pouvait plus rien
défaire. La ventilation est désormais tout-ou-nien, vérifié par test. Au
passage, `could not convert string to float: 'abc'` est remplacé par un
message qui nomme le poste fautif et rappelle le format attendu, et un
montant hors de proportion est refusé.

**L'assistante prend visage.** Redessinée d'après trois illustrations de
référence : une comptable ailée à visière verte et lunettes, armure or et
rouge, qui présente une tablette. Trois états, un seul dessin :
- **informatif** — tablette sombre et chiffres, elle explique ;
- **valide** — sourire, pouce levé, tablette verte à coche ;
- **anomalie** — sourcils froncés, tablette rouge à triangle d'alerte.

Toujours en SVG en ligne : net à toute taille, quelques kilo-octets là où
une illustration en pèse mille, et recoloriable par CSS — c'est ce qui
permet trois états sans trois fichiers. Nouvelles animations : battement
d'ailes et balancement de la queue-de-cheval, pouce levé, pulsation de
l'alerte. Elle ne s'invite toujours pas : elle paraît sur demande d'aide,
ou pour **incarner le message qui vient de s'afficher** (une erreur la
fait froncer les sourcils, une confirmation lui fait lever le pouce), puis
s'efface d'elle-même. Toujours masquable définitivement, toujours muette,
et les animations s'arrêtent si le système demande un mouvement réduit.
- 7 tests ajoutés (437 au total).


## 8.22.0 — 2026-07-22 (Linux : « rien ne se lance » — deux causes)
Signalé en usage : rien ne démarre au lancement du `.sh` sous Linux, et le
code du script s'affiche à l'écran. Deux causes, aucune n'était un bug du
logiciel — ce qui ne les rend pas moins bloquantes.

**1. Le paquet contenait DEUX fichiers `.sh`.** Le lanceur, et un
générateur de certificat devenu inutile depuis que HTTP est le mode par
défaut (v8.15.0) — affichés côte à côte dans le dossier. Ouvrir l'un pour
l'autre ne produit aucun message d'erreur : juste du code à l'écran et
rien qui démarre. Un seul `.sh` est désormais livré, celui qui porte le
nom du logiciel ; le générateur Python, multiplateforme, fait le même
travail sans ressembler à un lanceur. Un test refuse tout paquet qui en
contiendrait plusieurs.

**2. Sur un bureau Linux, double-cliquer un `.sh` l'OUVRE dans un
éditeur** au lieu de l'exécuter — choix de sécurité du système, pas un
défaut du logiciel. La notice l'explique désormais et donne trois voies,
la plus robuste en premier : `bash Compta-LMNP-Linux-macOS.sh`, qui
fonctionne même quand le droit d'exécution a été perdu à la
décompression. Un fichier `Compta-LMNP.desktop` est ajouté pour les
bureaux qui savent lancer une application graphique.

- Vérifié : le lanceur conserve bien son droit d'exécution dans l'archive.
- 2 tests ajoutés (430 au total).


## 8.21.0 — 2026-07-22 (un assistant qui lit les infobulles)
Un petit personnage apparaît en bas à droite pour dire à voix… écrite le
contenu de l'infobulle survolée. Trois animations : flottement au repos,
clignement des yeux, salut de la main à la première apparition. Aucun son.
- **Rien à réécrire** : les 11 infobulles existantes portent déjà leur
  texte dans un attribut `data-aide` — l'assistant s'y branche.
- **SVG en ligne**, aucune ressource externe : le logiciel se distribue en
  un dossier sans `static/`, et un fichier image de plus serait un fichier
  de plus à perdre.
- **Il ne s'invite pas.** Le précédent le plus célèbre du genre a été
  détesté pour cette raison précise. Celui-ci n'apparaît QUE sur demande
  d'aide, rien de périodique ne le déclenche, et un clic sur la croix le
  masque définitivement (préférence conservée d'une page à l'autre).
- **Il n'est qu'un confort** : l'infobulle CSS reste autonome et continue
  de fonctionner sans lui — sans JavaScript, ou pour qui l'a masqué.
- Accessibilité : les infobulles deviennent atteignables au clavier, et
  toutes les animations s'arrêtent si le système demande un mouvement
  réduit (`prefers-reduced-motion`). Masqué sous 700 px de large.
- 4 tests ajoutés (428 au total), dont un qui vérifie qu'il ne peut pas
  devenir intrusif.


## 8.20.0 — 2026-07-22 (aucun tiers nommé dans le dépôt)
Préalable à la publication : le nom du prestataire comptable historique
apparaissait **63 fois** dans le projet — commentaires, docstrings,
documentation, journal des versions, noms de tests, et jusque dans les
libellés d'écriture du jeu de démonstration PUBLIÉ. Le nommer dans un
dépôt public n'apporte rien et l'expose autant que nous.
- Toutes les mentions remplacées par une formulation neutre qui conserve
  le SENS (« un prestataire externe », « les liasses de référence », « le
  cabinet ») sans le nom.
- Le fichier du test en or, qui portait ce nom, est renommé
  `tests/test_or_liasses_reelles.py` — ainsi que les tests qui le
  citaient nommément.
- Le jeu de démonstration est régénéré sans la mention : l'outil
  d'anonymisation lit désormais les termes à proscrire dans un fichier du
  dossier PRIVÉ (`reference/termes_a_anonymiser.txt`) plutôt que de les
  contenir — sans quoi il publierait ce qu'il sert à masquer, exactement le
  défaut corrigé pour l'adresse en v8.18.0.
- `verifier_depot.py` cherche ces termes dans tout ce qui serait publié, et
  un test les traque dans les sources.


## 8.19.0 — 2026-07-22 (double audit : ingénierie et régularité comptable)

**Audit comptable — ce qui a tenu.** Intangibilité des exercices clos,
numérotation continue et sans trou, équilibre de chaque écriture, mentions
obligatoires présentes, dates dans les bornes, aucun compte hors plan, FEC
exporté conforme et équilibré. Côté règles LMNP : le plafond 39 C empêche
bien l'amortissement de créer un déficit, un déficit d'EXPLOITATION reste
lui déductible, le stock reporté est repris dès qu'il y a du bénéfice, les
comptes de gestion ne sont pas repris dans les à-nouveaux, et les déficits
s'imputent du plus ancien au plus récent.

**Défaut 1 — les déficits PÉRIMÉS étaient comptés comme disponibles.**
Un déficit LMNP s'impute dix ans, puis il est perdu. La clôture le purgeait
correctement, mais le suivi des reports les additionnait tous : le « total
des reports disponibles » surestimait ce qui reste réellement imputable, et
le déclarant pouvait bâtir un plan dessus. Les millésimes périmés sont
désormais exclus du total — et restent AFFICHÉS, marqués « périmé » :
disparaître sans explication serait pire que de trop compter.

**Défaut 2 — la quote-part de terrain était ignorée en silence.**
Le champ attend une fraction (0,09). Trois saisies plausibles — un
pourcentage (7,35), un montant en euros (8 600), ou la valeur 1 pour un
terrain nu — étaient rejetées SANS UN MOT, et la ventilation retombait sur
sa part indicative de 15 %. Conséquence directe : une part de terrain
fausse, donc un amortissement faux, le terrain n'étant pas amortissable.
Ces saisies sont désormais reconnues et converties.

- 3 tests ajoutés (423 au total).


## 8.17.0 — 2026-07-22 (le bac à sable montre une année de location vécue)
Le dossier de démonstration créait un exercice précédent « clos » mais
**vide** : le débutant qui basculait dessus ne voyait rien. Le bac à sable
ne montrait donc jamais à quoi ressemble une année tenue de bout en bout —
il fallait tout imaginer.
- L'exercice précédent est désormais **rejoué depuis le FEC anonymisé** :
  loyers mois par mois, appels de charges ventilés, taxe foncière, CFE,
  assurance, télécom, maintenance, dotation aux amortissements, clôture.
  Un exercice PASSÉ à inspecter (page Saisie, grand livre, liasse, export
  FEC) et un exercice OUVERT laissé libre pour s'exercer.
- **Opérations reconstituées depuis les écritures** : rejouer un FEC
  produit des écritures comptables, pas des opérations de saisie — la page
  Saisie, premier écran du débutant, serait restée vide. Le rapprochement
  se fait d'abord par le LIBELLÉ (qui reprend celui du gabarit d'origine),
  puis par le compte, en retenant le premier gabarit du catalogue et non
  le dernier : sans quoi un loyer devenait un « autre produit ». Les
  écritures non saisies par l'utilisateur (à-nouveaux, dotation) n'en
  reçoivent aucune, ce qui est exact.
- **Piège évité** : l'exercice précédent complet ET les à-nouveaux de
  l'exercice courant coexistent. Les compter tous les deux doublait le
  cumul d'amortissement et déclenchait une fausse alerte. La règle est
  désormais explicite — s'il y a des à-nouveaux, ils portent à eux seuls
  la situation d'ouverture ; sinon on cumule les exercices antérieurs.
- **Contrôle de plausibilité N-1 assagi** : il se taisait faute de
  comparaison possible, il se serait mis à hurler. Au 2 janvier, toutes
  les charges de l'an dernier sont « manquantes » — comparer un exercice
  à peine ouvert n'a pas de sens et noierait l'utilisateur d'alertes
  chaque début d'année.
- Vérifié : les chiffres de l'exercice courant sont INCHANGÉS (le bilan
  d'ouverture réconcilie toujours celui du prestataire précédent, au
  centime), et la réinitialisation du bac à sable en mode démo fonctionne
  de bout en bout.
- 5 tests ajoutés (416 au total).


## 8.16.1 — 2026-07-22 (orthographe du titulaire)
- Le nom du titulaire des droits s'écrit **Sylvain FAURE**, sans accent :
  corrigé dans les 68 fichiers concernés (en-têtes de sources, licence,
  README, pied de page de l'application). Une mention de copyright ne vaut
  que si elle désigne exactement la bonne personne — autant le régler
  avant publication qu'après.
- Vérifié au passage : le dossier de démonstration reste totalement
  anonyme (ni le seed ni le FEC de démo ne contiennent ce nom).


## 8.16.0 — 2026-07-22 (propriété identifiée, licence freeware, import marqué expérimental)
Préalable à la publication (jalon 9) : la propriété du logiciel est
désormais clairement identifiée, PARTOUT.
- **Titulaire réel dans 67 fichiers** : chaque en-tête de source, le
  README, les seeds et la licence portaient encore un simple gabarit à la
  place du nom — une mention de copyright sans titulaire ne protège
  personne. Tous portent désormais « Copyright © 2026 Sylvain FAURE ».
- **LICENSE.txt réécrite pour le modèle GRATUIT** : l'ancienne, rédigée
  pour la vente (« l'acquéreur d'une licence »), était périmée depuis
  l'abandon de la commercialisation (v8.8.0). La nouvelle : résumé en
  langage clair, usage gratuit illimité, partage du paquet officiel INTACT
  autorisé (ça sert la diffusion), interdictions ciblées (vente,
  modification diffusée, réutilisation du code, retrait des mentions),
  clause DONS (une libéralité, aucun droit supplémentaire, non
  remboursable), ABSENCE DE GARANTIE renforcée pour un logiciel comptable
  (les états produits sont des aides à la préparation, à faire valider
  avant dépôt), clause données (tout reste sur la machine de
  l'utilisateur), composants tiers listés (Python PSF, Flask/BSD,
  reportlab/BSD — aucune licence contaminante), droit français.
- La propriété est VISIBLE : pied de page de l'application (« © 2026
  Sylvain FAURE, tous droits réservés — logiciel gratuit, fourni sans
  garantie ») et en tête du README. LICENSE.txt livrée en PREMIER fichier
  du paquet.
- **Import CSV marqué « FONCTION EXPÉRIMENTALE »** : badge et encadré
  d'avertissement — testé sur des relevés types, pas encore sur la
  diversité des exports bancaires réels ; chaque proposition est à
  vérifier, rien ne s'écrit sans validation, et une erreur s'annule par
  contre-passation. Les retours sur relevés réels sont sollicités.
- 4 tests ajoutés (411 au total) : aucun placeholder restant, licence
  cohérente avec le modèle gratuit, licence livrée + propriété visible,
  badge expérimental présent.


## 8.15.0 — 2026-07-22 (HTTP local par défaut, lanceurs distinguables)

**Le cadenas barré n'était pas un défaut à corriger, mais un choix à
revoir.** Signalé en usage Windows : « le navigateur indique toujours que
la connexion localhost:5000 est non sécurisée, avec le https barré ». Rien
d'anormal : un certificat AUTO-SIGNÉ ne peut être validé par personne, par
construction. Le logiciel affichait donc un avertissement plein écran au
premier accès, puis un cadenas barré à chaque lancement, définitivement.
Or ce HTTPS ne protégeait RIEN : l'application n'écoute que sur 127.0.0.1,
les données ne quittent jamais la machine et ne traversent aucun réseau.
Son seul effet réel était d'habituer l'utilisateur à passer outre les
avertissements de sécurité de son navigateur — précisément le réflexe
qu'un logiciel ne doit pas installer.
- **HTTP est désormais le mode par défaut.** Les navigateurs traitent
  `http://localhost` comme un CONTEXTE SÉCURISÉ, au même titre que HTTPS :
  aucune fonctionnalité n'est perdue, et l'avertissement disparaît.
- Le démarrage explique l'absence de cadenas plutôt que de la subir.
- HTTPS reste disponible sur demande explicite : `COMPTA_HTTPS=1`, ou
  `--https` pour le lanceur Linux/macOS.
- Effet de bord bienvenu : plus de génération de certificat au premier
  lancement, ni de dépendance `cryptography` à installer — la première
  mise en route est plus courte et a une raison de moins d'échouer.

**Deux lanceurs qui portaient le même nom.**
Windows masque les extensions par défaut : `Lancer-Compta-LMNP.bat` et
`Lancer-Compta-LMNP.sh` s'affichaient tous deux comme
« Lancer-Compta-LMNP », côte à côte dans le dossier. Deux fichiers
jumeaux, un seul qui fonctionne.
- Renommés **`Compta-LMNP-Windows.bat`** et
  **`Compta-LMNP-Linux-macOS.sh`** : la plateforme est dans le nom, donc
  visible même sans extension. Un test vérifie qu'aucun couple de lanceurs
  ne redevient homonyme une fois l'extension masquée.
- **Raccourci « Compta LMNP » créé sur le Bureau au premier lancement**
  sous Windows (le lanceur Linux le proposait déjà via `--raccourci`).
  Marqueur d'idempotence : il n'est pas recréé si l'utilisateur le
  supprime volontairement.
- 4 tests ajoutés (407 au total).


## 8.14.0 — 2026-07-22 (clôture débloquée, ventilation guidée des biens)

**Bug bloquant : « NOT NULL constraint failed: ligne.compte_num ».**
Signalé en usage sur un exercice minimal. Cause reproduite : un composant
portant une durée d'amortissement sur un compte qui ne s'amortit PAS
(le terrain). La saisie était acceptée, puis la génération de la dotation
construisait une ligne à compte nul et toute clôture échouait — sur un
message d'erreur SQLite incompréhensible. Pire : **rien dans l'interface
ne permettait de corriger**, les composants étant créables mais jamais
modifiables. Traité aux quatre niveaux :
- création REFUSÉE avec un message qui explique pourquoi (le terrain ne se
  déprécie pas — raison même pour laquelle sa quote-part doit être isolée) ;
- clôture qui NOMME le composant fautif et le geste, au lieu de l'erreur
  SQLite ;
- contrôle pré-clôture BLOQUANT, pour l'apprendre avant d'être coincé ;
- **correction de la durée depuis la page Immobilisations** — un logiciel
  qui laisse commettre une erreur doit laisser la défaire.

**Ventilation guidée du prix d'acquisition.**
On pouvait empiler des composants sans qu'aucun lien ne soit fait avec le
prix payé. Or c'est la ventilation qui donne au réel tout son intérêt : un
bien saisi en bloc s'amortit à la vitesse du gros œuvre, et le mobilier —
qui devrait s'amortir en quelques années — s'étale sur des décennies.
- Tant qu'un bien n'a aucun composant, la page Immobilisations propose une
  ventilation en six postes (terrain, gros œuvre, façade/étanchéité,
  installations techniques, agencements, mobilier), pré-remplie depuis le
  prix payé et, si elle est connue, depuis la quote-part de terrain réelle
  — une donnée vaut mieux qu'une moyenne. Total vivant et écart affichés
  en temps réel ; durées issues des usages admis (BOI-ANNX-000115),
  rappelées comme indicatives.
- Les frais d'acquisition sont expliqués mais laissés hors ventilation :
  ils relèvent d'un choix (déduction immédiate ou incorporation au prix de
  revient) qui se retient une fois pour toutes.
- **Alerte à l'ajout** d'un composant faisant dépasser le prix
  d'acquisition de plus de 5 %, avec la nuance qui évite le faux positif :
  normal si des travaux postérieurs sont immobilisés.
- Contrôle permanent limité à la SOUS-ventilation : une part du prix jamais
  amortie est un avantage perdu silencieusement, alors qu'un dépassement
  devient légitime dès les premiers travaux — et le reste. Crier dessus à
  chaque contrôle reviendrait à crier sur tout dossier vivant.
- Le garde-fou d'app.py vise désormais le VRAI invariant (aucun HTML de
  page dans les routes, coque du document exceptée) plutôt qu'un simple
  seuil de lignes qu'il fallait relever à chaque ajout légitime.
- 9 tests ajoutés (403 au total).


## 8.13.0 — 2026-07-22 (dossier de démonstration anonymisé, pense-bête étoffé)

**Le bac à sable en mode démo échouait — et cachait plus grave.**
Signalé en usage : la réinitialisation sur un dossier de démonstration
plantait, le logiciel cherchant un FEC personnel. Cause immédiate : le
seed livré (`seed_exemple.sql`) réclamait un fichier volontairement exclu
du paquet. Cause découverte en corrigeant : **ce seed portait une identité
réelle — nom, SIREN, adresse — et partait dans chaque paquet client**,
alors qu'il porte lui-même la mention « NE JAMAIS LIVRER ». Le garde
anti-fuite bloquait le dossier `reference/` mais pas ce fichier-là.
- Nouveau dossier de démonstration **fictif**, dérivé du réel par
  `outils_demo.py` : montants × 0,78, identité et libellés remplacés,
  codes de pièce renumérotés. Un débutant dispose d'un dossier complet et
  cohérent — 14 composants, un exercice clos, des à-nouveaux — sans
  qu'aucune donnée personnelle ne quitte le poste de développement.
- L'anonymisation préserve ce qui doit l'être : équilibre de CHAQUE
  écriture au centime (l'arrondi après multiplication le cassait), solde
  nul du compte d'attente (un centime résiduel y était écarté de
  l'à-nouveau et déclenchait un contrôle BLOQUANT sur un dossier neuf), et
  accord exact entre les composants du seed et les soldes du FEC.
- `seed_exemple.sql` est désormais **interdit de paquet** (motif ajouté au
  garde anti-fuite) ; le mode démo bascule automatiquement sur le dossier
  anonymisé quand le dossier de référence est absent.
- Contrôle 2033-C assoupli à bon escient : sur un exercice OUVERT, l'écart
  entre le plan d'amortissement et le bilan vaut la dotation à venir — ce
  n'est pas une anomalie mais la définition d'un exercice en cours. Seul
  le reliquat, lui, est signalé. Et les deux contrôles qui portent sur cet
  écart (liasse et pré-clôture) partagent enfin le MÊME seuil de
  matérialité : ils ne peuvent plus être en désaccord.

**Pense-bête : les oublis récurrents des loueurs meublés.**
- Checklist de 15 points groupés par moment de la vie du dossier
  (démarrage, charges oubliées, erreurs de classement, avant de
  déclarer) : frais d'acquisition traités comme un coût perdu, CFE
  découverte trop tard, terrain amorti par erreur, entretien confondu avec
  amélioration, mobilier passé en charge d'un bloc, exercice de
  rattachement, symétrie des charges récupérables, justificatifs,
  déclaration d'une année sans loyer, dates de dépôt, effet des
  amortissements à la revente. Formulée en points de VIGILANCE, pas en
  affirmations fiscales.
- Deux rappels regardent réellement le dossier : aucun composant de frais
  d'acquisition enregistré, aucun mobilier immobilisé.
- 6 tests ajoutés (394 au total).


## 8.12.0 — 2026-07-22 (la liasse provisoire cesse de se contredire)
Suite de l'analyse du dossier réel : la liasse provisoire annonçait un
« Résultat fiscal LMNP » de 395 € là où la clôture donne **−380 €**. Deux
causes distinctes, traitées différemment selon leur nature.

**1. Le fonds ALUR était ignoré (fait, pas estimation).**
La réintégration du fonds de travaux ALUR n'était appliquée qu'à la
clôture : sur un exercice ouvert, la table de clôture n'existe pas, donc
le retraitement valait zéro. Or la charge EST comptabilisée et sa
non-déductibilité est une règle de droit, pas une prévision : elle a sa
place dans les tableaux. La règle est désormais portée par une fonction
unique, `fiscal.retraitement_automatique()`, appelée par la clôture ET
par la liasse provisoire — au lieu d'être recopiée.

**2. La dotation aux amortissements manquait (estimation, donc séparée).**
La dotation n'est écrite qu'à la clôture : la liasse provisoire se
CONTREDISAIT — la 2033-C affichait la dotation de l'exercice quand la
2033-B affichait zéro. Correction volontairement conservatrice : les
tableaux 2033-A / 2033-B restent STRICTEMENT factuels (ils reflètent les
écritures, et le bilan d'ouverture d'un dossier repris doit rester
réconciliable avec celui du prestataire précédent — un test de calage le
garantit). La projection vit dans un bloc distinct et clairement nommé,
« Projection — si l'exercice était clôturé aujourd'hui », affiché à
l'écran et dans le PDF : dotation de l'exercice, résultat comptable
projeté, report 39 C projeté, résultat fiscal projeté.
- `fiscal.simuler()` : ce que donnerait la clôture, sans rien écrire.
- `fiscal._calcul_fiscal()` : chaîne fiscale pure (agrégats → plafond
  39 C → résultat), extraite de `cloturer` et partagée avec `simuler`.
  Un test interdit désormais que `cloturer` recalcule la chaîne 39 C
  lui-même : une seule règle, deux moments.
- Vérifié : la projection annonce le résultat de clôture au centime, et
  le test en or (3 exercices réels) reste inchangé.
- 5 tests ajoutés (388 au total).


## 8.11.0 — 2026-07-22 (premier dossier réel tenu de bout en bout)
Retours d'un exercice complet saisi sous Windows, FEC de clôture contrôlé
(conforme, équilibré) et liasse provisoire analysée.

**Le constat majeur — l'anomalie de la liasse était juste.**
« 2033-C : amortissements fin = case 030 du bilan → ANOMALIE 12 219,29 /
0,00 » ne signalait pas un défaut de calcul mais une COMPTABILITÉ
INCOMPLÈTE : le bien, acquis en 2021, avait été saisi à sa seule valeur
brute (117 000 €) ; les ~9 879 € d'amortissements déjà courus n'avaient
jamais été comptabilisés. Le bilan présentait un bien neuf pendant que le
tableau 2033-C déroulait son plan depuis l'origine — écart permanent, et
valeur nette comptable fausse pour une future plus-value. Or le logiciel
n'offrait AUCUN moyen de reprendre ce cumul, alors que c'est le cas le
plus fréquent en LMNP (on achète des années avant d'ouvrir une compta).
- `operations.reprendre_amortissements_anterieurs()` : écriture d'à-nouveau
  au journal AN, 1er janvier, comptes 28 au crédit par le compte de
  l'exploitant. **Le résultat de l'exercice n'est pas touché** : ce n'est
  pas une dotation, c'est la reconstitution d'une situation antérieure.
- Bouton « Reprendre les amortissements antérieurs » sur la page
  Immobilisations, affiché seulement quand l'écart existe.
- Contrôle pré-clôture AMORT_ANTERIEURS + message de la liasse devenu
  explicatif (il dit la cause et le geste, au lieu d'aligner deux nombres).
- Seuil de matérialité (5 € ET 1 %) : un bilan repris d'un ancien
  prestataire diffère toujours du plan de quelques euros d'arrondi — ce
  bruit ne déclenche rien, un oubli total (≈100 %) déclenche toujours.

**Ergonomie — retours d'usage.**
- Page Saisie : la carte d'appel de charges dit désormais explicitement
  que c'est LÀ que se saisit un appel du syndic (et pas dans le formulaire
  de saisie simple au-dessus), qui prêtait à confusion.
- Colonne « Actions » nommée dans le tableau des opérations (les boutons
  Annuler / Dupliquer n'avaient pas d'en-tête).
- Duplication : la pièce devient « Relevé bancaire MM » au lieu d'une
  période nue (« 2026-08ches ») qui ne disait pas d'où venait l'écriture.
- Taxe foncière : libellé « Taxe foncière (hors TEOM récupérable) » et
  nouveau contrôle TEOM_ABSENTE — l'avis porte les deux, l'oubli de la
  TEOM est l'erreur la plus courante du dépouillement.
- Formulaire d'ajout de bien : les exemples ne reprennent plus une adresse
  réelle ; quote-part terrain suggérée à 0.09 (ordre de grandeur usuel).
- Composants : infobulle des durées usuelles admises par l'administration
  (BOI-ANNX-000115), du gros œuvre au mobilier.
- Gabarit « Adhésion OGA / CGA » retiré : la majoration pour non-adhésion
  est supprimée à compter de 2025.
- Toutes les mentions du prestataire historique remplacées par « les
  prestataires de comptabilité LMNP » dans l'interface et la liasse.
- Avertissement de la liasse reformulé : « générée sur les modèles
  disponibles à la date de version du logiciel — peut ne pas correspondre
  aux derniers modèles en date ».
- Veille fiscale : le prompt demande désormais si les MODÈLES DÉCLARATIFS
  eux-mêmes ont changé (millésime des 2031/2033/2042-C-PRO, cases créées,
  renumérotées). Un logiciel qui produit des chiffres justes dans des
  cases périmées est faux sans que la règle de fond ait bougé.
- 10 tests ajoutés (383 au total).


## 8.10.0 — 2026-07-22 (premier test Windows réel : le lanceur était illisible)
Test sur un vrai Windows 10 : l'installation échouait entièrement, avec des
messages incompréhensibles (« 'ho' n'est pas reconnu », « '\python.exe" -m
pip' n'est pas reconnu »). Diagnostic : le fichier **Lancer-Compta-LMNP.bat
était écrit en UTF-8 avec des fins de ligne Unix** (97 lignes LF, 995 octets
non-ASCII dans les commentaires décoratifs). cmd.exe lit un fichier de
commandes octet par octet : ce décalage lui faisait avaler le début des
lignes — « echo » devenait « ho » puis « o », les variables n'étaient jamais
affectées. Le lanceur n'a donc JAMAIS fonctionné sous Windows ; aucun test
automatisé ne pouvait le voir, seul un essai réel le pouvait.
- Lanceur réécrit en **ASCII pur + CRLF**, garanti par deux verrous : la
  construction du paquet REFUSE désormais de livrer un .bat non conforme
  (vérifié en cassant volontairement le fichier), et un test le contrôle.
- Détection de Python durcie : la commande est EXÉCUTÉE (`py -3 --version`)
  au lieu d'être seulement cherchée dans le PATH — Windows 10 fournit un
  faux `python.exe` qui ouvre le Microsoft Store et trompait l'ancien test.
- **reportlab n'est plus bloquant** : Flask et cryptography d'abord, PDF
  ensuite et son échec est toléré (message clair). Utile sur les versions
  très récentes de Python, où certaines dépendances n'ont pas encore de
  roue prête — l'application sait déjà fonctionner sans PDF.
- Messages d'échec enrichis : dossier en lecture seule / OneDrive,
  suggestion de Python 3.12-3.13 si l'installation des dépendances échoue.
- **Compatibilité exécutable autonome** : les données de l'utilisateur
  (base, sauvegardes, certificat, journal) se placent à côté de
  l'exécutable et non dans le bundle temporaire (`sys.frozen`).
  `construire_exe.py` fabrique l'exécutable — À LANCER SUR WINDOWS,
  PyInstaller ne faisant pas de compilation croisée. Choix `--onedir` et
  non `--onefile` (démarrage lent et antivirus soupçonneux sur machine
  ancienne). Réserve documentée : un exécutable non signé aggrave
  SmartScreen plutôt qu'il ne le résout.
- 4 tests ajoutés (373 au total).


## 8.9.0 — 2026-07-21 (audit « mise en production », au tamis de l'autoporté)
Grille externe de 5 axes (secrets, observabilité, données, exploitation,
résilience), chaque point tranché empiriquement contre le code.
APPLIQUÉ :
- **Journal d'erreurs persistant et rotatif** (logs/erreurs.log, 512 Ko × 3,
  branché paresseusement au premier incident) : la console du lanceur est
  invisible (double-clic) ou perdue au redémarrage — sans fichier, un
  plantage chez un utilisateur distant était indiagnosticable. La page 500
  masque toujours toute trace technique mais oriente désormais vers le
  fichier à joindre au message de support. Le journal reste sur la machine
  de l'utilisateur (aucun envoi réseau).
- Repli minimal de la page d'erreur corrigé au passage : l'appel _base sans
  ses arguments requis faisait toujours tomber sur « Erreur interne. » nu.
DÉJÀ EN PLACE (désormais verrouillé par tests pour le rester) :
- écoute strictement locale (127.0.0.1), debug opt-in (COMPTA_DEBUG=1),
  jamais par défaut ; sauvegarde automatique AVANT toute migration de
  schéma (le « rollback » de facto) ; export PDF en dépendance optionnelle
  (ImportError → message, pas de crash) ; paquet client sans base de
  données, sans référence, sans journaux, sans certificats ; aucun secret
  en dur (pas de session Flask, pas de secret_key nécessaire) ; SQL
  paramétré (le seul f-string itère des tuples constants internes).
RÉFUTÉ (sans objet en autoporté, documenté) : healthcheck, alerting,
centralisation de logs, process manager, limites CPU/RAM, timeouts d'API
tierces (zéro appel sortant), sessions/JWT/politiques de mots de passe
(pas d'authentification par conception, liée à l'écoute locale exclusive).
- 6 tests ajoutés (369 au total).


## 8.8.0 — 2026-07-21 (changement de modèle : gratuit, soutenu par dons)
- Le logiciel n'est plus destiné à la vente : il est distribué GRATUITEMENT
  et son développement peut être soutenu par un don volontaire.
- Encart de soutien sur la page d'accueil (lien PayPal + courriel du
  compte). Ton assumé : « entièrement facultatif, ça ne débloque rien :
  tout est déjà débloqué ». L'encart ne s'affiche QUE sur l'accueil — pas
  sur les pages de travail (vérifié par test).
- README mis en cohérence (mention « revendable » remplacée par le modèle
  gratuit + dons).
- 1 test ajouté (363 au total).


## 8.7.0 — 2026-07-21 (panel de bêta-testeurs simulé : 3 bloquants, 2 frictions)
Cinq personas rejoués sur le paquet client, sans connaissance préalable du
logiciel. Trois BLOQUANTS découverts et corrigés :
- **Aucune correction d'opération possible** (Michel, novice : « je me suis
  trompé de montant, comment je corrige ? ») → bouton **Annuler** sur
  chaque opération : CONTRE-PASSATION comptable (écriture inverse à la même
  date, pièce ANNUL-n), jamais de suppression — la numérotation du FEC
  reste dense et la piste d'audit complète. Les montants se neutralisent
  d'eux-mêmes dans tous les calculs fondés sur les écritures ; les usages
  fondés sur les opérations (réintégration ALUR automatique, contrôles de
  complétude et de doublons, pense-bête) excluent les opérations annulées.
  Refus motivés : opération déjà annulée, exercice clos (orientation vers
  la régularisation ou la restauration). Colonne operation.annulee,
  schéma v5, palier de migration 5.
- **Import bancaire FANTÔME** (Sandrine, pressée) : le module existait
  depuis la v7.4 — durci, testé — mais n'était câblé dans AUCUNE page.
  Section « Importer un relevé bancaire » sur la page Saisie, en DEUX
  temps : analyse → propositions cochables → validation explicite. Rien
  n'est écrit sans accord ; jeton de session vérifié.
- **Reprise d'un exercice inaccessible** (Nadia, migrante depuis un logiciel du marché) :
  rejeu_fec.py n'était joignable qu'en code — l'argument « migrez
  facilement » était inutilisable par un client. Formulaire « Reprendre un
  exercice complet depuis son FEC » sur la page Nouvel exercice : exercice
  créé, fichier rejoué écriture par écriture. Vérifié sur le FEC réel
  2025 : 34 écritures, balance strictement identique compte par compte.
Deux FRICTIONS corrigées :
- Saisie sans bien : « FOREIGN KEY constraint failed » remplacé par un
  message d'orientation (« créez d'abord votre logement dans la page
  Immobilisations »).
- La page Clôture dit désormais que clôturer N'est PAS irréversible
  (sauvegarde automatique juste avant + restauration en un clic).
Constats POSITIFS du panel (vérifiés, inchangés) : montants à la virgule
française acceptés, messages de format clairs (date 05/03/2026 refusée en
expliquant le format attendu), bouton Dupliquer, doublon d'un double-clic
rattrapé par le contrôle pré-clôture, restauration trouvable, 7 infobulles
d'aide sur la saisie.
- 13 tests ajoutés (362 au total).


## 8.6.0 — 2026-07-21 (refonte : app.py scindé, lecteur FEC unifié)
Les deux dettes documentées d'ARCHITECTURE.md sont soldées — refonte pure,
zéro changement fonctionnel (349 tests, dont le test en or, inchangés).
- **app.py : 2 571 → 1 217 lignes (−53 %)**. Les 13 gabarits HTML et la
  feuille de style (1 342 lignes, 52 % du fichier) vivent désormais dans
  pages.py, module de PRÉSENTATION PURE : aucun import, aucune fonction,
  rien d'exécutable — pureté verrouillée par test (l'AST du module est
  inspecté), tout comme l'interdiction de réintroduire un gabarit dans
  app.py. Chaque page de l'interface re-testée après extraction.
- **Un seul lecteur de FEC (fec_io.py)** au lieu de trois : le validateur,
  la balance de reprise et le rejeu d'exercice ré-implémentaient chacun
  l'ouverture du fichier, le découpage tabulaire et la conversion des
  montants à virgule — trois endroits où un même bug pouvait diverger.
  fec_io fournit les 18 colonnes A-47 A-1 (source unique, réexportée par
  valider_fec pour compatibilité), la tokenisation brute (AUCUN filtre :
  le validateur garde tout son pouvoir de détection) et les lignes
  nommées pour le rejeu. Les RÈGLES restent chez chaque consommateur —
  sémantiques historiques préservées à l'identique (la balance tolère les
  fichiers partiels, le rejeu exige les 18 colonnes) — et l'ÉCRITURE
  (export_fec) reste volontairement séparée : le validateur doit pouvoir
  contredire l'export, pas hériter de ses défauts. Un test verrouille
  l'accord des trois consommateurs sur le même FEC réel.
- 7 tests ajoutés (349 au total).


## 8.5.0 — 2026-07-21 (audit interne : fonctionnement simulé + revue de code)
Parcours utilisateur complet rejoué sur le PAQUET CLIENT (installation
neuve), puis revue systématique du code. Quatre défauts réels corrigés :
- **Base neuve annoncée « schéma 0 → 4 »** : une installation toute fraîche
  déclenchait une migration et une copie « avant-migration » inutiles. La
  version est désormais marquée à la création de la base.
- **Écriture en base à chaque affichage de page** : la garde de version
  appelait marquer_version() sur CHAQUE requête (transaction d'écriture
  inutile, contention possible avec une clôture en cours) et pouvait
  déclarer un dossier à jour sans qu'aucun palier de migration n'ait
  tourné. La garde est maintenant en LECTURE SEULE ; le marquage appartient
  à la création et à la migration.
- **FEC archivé introuvable depuis l'interface** : un FEC est produit à
  chaque clôture (avec empreinte SHA-256), mais rien ne permettait de le
  retrouver — or c'est LE fichier réclamé lors d'un contrôle
  (art. L. 47 A-I du LPF). Nouvelle page « Archives FEC » : liste,
  empreinte, téléchargement, remontée de chemin bloquée.
- **Noms réservés Windows** : un dossier nommé CON, AUX, PRN, NUL, COM1-9
  ou LPT1-9 produisait un slug impossible à créer sous Windows (erreur
  système incompréhensible). Refus explicite et pédagogique, sur toutes les
  plateformes, pour qu'un dossier créé sous Linux reste transférable.
- **Filet de sécurité sur les connexions** : 21 routes fermaient leur
  connexion hors de tout finally (un rendu qui échoue laissait la connexion
  ouverte). Toute connexion ouverte pendant une requête est désormais
  fermée en fin de contexte, sans modifier les routes.

Vérifié sans défaut : robustesse de saisie (type inconnu, montant négatif
ou non numérique, date inexistante, date hors exercice, exercice clos —
message clair à chaque fois), échappement des données utilisateur (aucune
injection HTML possible), équilibre en partie double et chaîne fiscale
recalculée à la main, FEC conforme (CRLF, sans BOM), chemins avec espaces
et accents, certificat sans dépendance à openssl, aucune fonction morte
(0 sur 211), aucun os.rename, tous les open() texte avec encodage explicite.
- 13 tests ajoutés (342 au total).


## 8.4.0 — 2026-07-21 (veille fiscale : le logiciel ne se met pas à jour seul)
Les règles de calcul sont datées et versionnées, mais RIEN n'avertissait
l'utilisateur qu'une loi de finances avait changé un seuil. Nouveau module
veille_fiscale.py + page « Veille fiscale » :
- **Corpus des textes qui régissent le LMNP** (15 références), chacun
  rattaché à ce qu'il gouverne DANS le logiciel et, le cas échéant, à la
  règle versionnée correspondante : art. 155 IV (LMP/LMNP), 156 I-1° ter
  (déficits 10 ans), 50-0 (micro-BIC), 39 C II-2 (limitation des
  amortissements — le calcul central), 39-1 et PCG/ANC 2014-03
  (composants), 150 U et 150 VB (plus-value, réintégration des
  amortissements depuis la LF 2025), 53 A et 302 septies A bis (liasse),
  L. 47 A-I LPF et arrêté A-47 A-1 (FEC), 261 D 4° (TVA), 1447 (CFE),
  loi Le Meur, doctrine BOFiP correspondante.
- **Question type prête à coller dans une IA** : demande ce qui a changé
  depuis la dernière veille, texte par texte, avec impact ventilé
  (amortissements, déficits, seuils, plus-value, obligations
  déclaratives) et récapitulatif des valeurs chiffrées de l'exercice.
  Garde-fous explicites : sources officielles exigées (Légifrance, BOFiP,
  impots.gouv.fr), distinction ADOPTÉ / en discussion, interdiction
  d'inventer articles et dates, aveu d'incertitude demandé. Bouton
  « Copier ».
- **Rappel au bon moment** : bandeau sur la page « Nouvel exercice » et
  mention dans le message d'ouverture si la veille date de plus de 11 mois
  (une loi de finances par an) ; rappel dans le Pense-bête ; bouton
  « J'ai fait ma veille » qui horodate (table meta).
- Avertissement affiché sans détour : une réponse d'IA n'est pas une
  source, et ce module ne donne aucun conseil fiscal.
- 7 tests ajoutés (329 au total).


## 8.3.0 — 2026-07-20 (second audit externe, points 3 à 5)
Retenus :
- **Impact des règles versionnées affiché** (point 4a) : le menu
  « Réglementation » montre désormais, pour chaque règle, le module
  concerné et son effet concret — distinguer une règle qui n'émet qu'un
  AVERTISSEMENT (seuil d'immobilisation : il ne requalifie jamais la
  dépense) d'une règle qui modifie le résultat fiscal (réintégration ALUR,
  durée de report des déficits). Table parametres.IMPACTS, complétude
  vérifiée par test pour toute règle livrée.
- **Comparaisons de dates simplifiées** (point 3) : les
  CAST(substr(date,1,4) AS INTEGER) sont remplacés par des comparaisons
  lexicographiques sur les dates ISO (AAAA-MM-JJ se trient comme du texte)
  dans amortissement, fiscal et pense_bete — sémantique identique (testée),
  sans extraction, et utilisable par un index.

Réfutés après vérification :
- « retraitement_alur_auto est à 0 par défaut » (point 4b) : la règle est
  livrée à **1** (REGLES_DEFAUT) et le repli de fiscal.py est également 1.
  L'audit a néanmoins révélé un TROU DE COUVERTURE réel : le test en or
  passe les retraitements à la main, le chemin AUTOMATIQUE n'était vérifié
  nulle part. Deux tests ajoutés (réintégration automatique effective, et
  désactivation par règle datée).
- Prorata temporis « au mois » (point 5) : la ligne citée
  (mois_actifs = 12 - mois0 + …) **n'existe plus depuis la v8.1.0** — le
  calcul se fait en jours réels (base 365), convention prouvée contre les
  13 composants de la liasse 2025 et verrouillée par 12 tests. La
  recommandation de documenter la convention est déjà satisfaite
  (docstring de fraction_prorata + invariant 3 bis d'ARCHITECTURE.md).
- Couplage clôture/dotation (point 3) : l'audit confirme lui-même
  l'atomicité ; aucun changement nécessaire.
- 5 tests ajoutés (322 au total).


## 8.2.0 — 2026-07-20 (second audit externe : points 1 et 2)
- **Alias supprimé (point 1, adopté)** : `_ouvrir_exercice = reprise.
  ouvrir_exercice` dans audit_cycle.py (outillage) laissait croire à une
  variante propre aux tests alors qu'il n'existe qu'une seule fonction, de
  PRODUCTION. Alias retiré, les 15 appelants (module + 6 fichiers de tests)
  pointent désormais sur reprise.ouvrir_exercice. Test de garde interdisant
  toute réapparition. NB : la recommandation de renommer une fonction
  « pour_cycle » dans audit_cycle n'a pas été suivie — elle aurait recréé
  la duplication que le point dénonce.
- **Montants négatifs dans un FEC (point 2, résolu autrement)** : ni rejet,
  ni silence. Vérification faite : le FEC n'est pas télétransmis (il est
  remis lors d'un contrôle, art. L.47 A-I du LPF), les champs de montants
  sont déclarés `numeric NOT NULL` dans le code source de Test Compta Demat
  (aucune contrainte de signe), et l'outil DGFiP gradue lui-même ses
  constats (anomalies bloquantes vs points à documenter). Le validateur
  adopte le même modèle : nouveau canal d'OBSERVATIONS non bloquantes.
  Un montant négatif est désormais signalé, avec ses numéros de ligne et la
  conduite à tenir, sans rejeter un fichier réel conforme par ailleurs.
  `valider()` ne renvoie toujours que les anomalies bloquantes (invariant
  « accepté ⇒ FEC conforme » préservé) ; `valider(..., comme_dict=True)` et
  `observations()` exposent les observations ; la CLI les affiche.
  Rappel : nos propres exports ne peuvent PAS contenir de négatif — la base
  l'interdit structurellement (CHECK debit >= 0 AND credit >= 0), désormais
  couvert par test.
- 4 tests ajoutés (317 au total).


## 8.1.0 — 2026-07-20 (suites d'un audit externe : 4 correctifs, 2 réfutations)
Chaque point a été tranché EMPIRIQUEMENT contre les liasses réelles, pas par
argument d'autorité.

Corrigés (l'audit avait raison) :
- **Prorata temporis (correctif fiscal majeur)** : l'amortissement de
  l'année d'entrée se calculait au MOIS. Vérification contre les
  13 composants de la liasse 2025 réellement déclarée : la convention
  effective est le prorata en JOURS RÉELS (base 365, jour de mise en
  service inclus) — elle reproduit 12/12 des cumuls déclarés, là où le
  calcul au mois se trompait de 2 à 6 € sur les acquisitions en cours de
  mois (Huisseries 11/03 et 25/05/2022, Porte d'entrée 26/10/2022). Un
  prorata au mois SURÉVALUE l'amortissement d'une entrée de fin de mois :
  c'est un risque de redressement. Corrigé aussi pour la CESSION (même
  défaut sur la dotation de sortie). Convention verrouillée par 12 tests
  contre la liasse réelle.
- **Aucun index en base** : 5 index ajoutés (écritures par exercice, lignes
  par écriture et par compte, opérations par exercice/type, plan
  d'amortissement). Gain MESURÉ sur 3 000 opérations : contrôles
  pré-clôture 1 416 ms → 46 ms (×31). Palier de migration 4 pour les bases
  existantes.
- **Registre dossiers.json** : réécriture en place remplacée par une
  écriture ATOMIQUE (fichier temporaire + os.replace + fsync) — une coupure
  en pleine écriture ne peut plus tronquer le registre, donc plus faire
  « disparaître » les dossiers secondaires.
- **FEC importé avec compte alphanumérique** (« CLIENTS ») : plantage brut
  sur int() remplacé par un refus explicite et pédagogique.

Réfutés après vérification (le code était déjà correct) :
- « inserer() peut annuler la transaction de l'appelant » : le rollback de
  rejeu est gardé par debutee_ici — il n'a lieu que si inserer() a
  lui-même ouvert la transaction. Prouvé par test.
- « la complétude des loyers rate un mois manquant en présence d'un
  doublon » : le contrôle compare des ENSEMBLES de mois ; janvier manquant
  est signalé même avec deux loyers en mars. Prouvé par test.

Non retenus (choix assumés, documentés dans ARCHITECTURE.md) : lecture du
FEC en mémoire (quelques milliers de lignes en LMNP), Decimal→float en
sortie (équilibre vérifié au centime par la suite), affectation du résultat
au compte 108000 (conventions des offres payantes validée par le test en or), tolérance des
montants négatifs (présents dans les FEC réels acceptés).
- 20 tests ajoutés (313 au total).


## 8.0.1 — 2026-07-20 (correctifs de lancement, trouvés au test réel Linux)
Le serveur démarrait correctement, mais aucune page ne s'ouvrait.
- **Ouverture du navigateur (Linux)** : le lanceur ne tentait que xdg-open.
  Diagnostic : xdg-open EXISTE souvent et renvoie « succès » sans rien
  ouvrir (comme python -m webbrowser) — aucun code de retour n'est fiable.
  Correctifs : (a) l'adresse est DÉSORMAIS TOUJOURS affichée en clair,
  avant le démarrage et après, l'ouverture automatique n'étant qu'un bonus ;
  (b) essais en cascade — $BROWSER, xdg-open/gio/kde-open, module Python
  webbrowser, navigateurs installés, applications Flatpak (Fedora
  Silverblue, Bazzite…) ; (c) astuce affichée pour forcer le navigateur
  (BROWSER=firefox ./Lancer-Compta-LMNP.sh).
- **Ouverture du navigateur (Windows)** : `start "" "%URL%"` s'exécutait
  AVANT app.py — la page s'ouvrait sur un port encore muet (« site
  inaccessible »). Nouvel assistant commun ouvrir_navigateur.py, lancé en
  arrière-plan, qui attend que le serveur réponde avant d'ouvrir, et rend
  la main proprement s'il reste muet.
- **Paquet client incomplet (défaut v8.0.0)** : generer_certificat.sh et
  generer_certificat.py n'étaient PAS embarqués — HTTPS serait tombé en
  panne sur une installation neuve. Corrigé, et surtout garde systémique :
  la construction du paquet ÉCHOUE si un fichier local invoqué par un
  lanceur n'y figure pas.
- 5 tests ajoutés (293 au total).


## 8.0.0 — 2026-07-17 (J9 : cycle de release — prêt à diffuser)
- **Migrations versionnées** (migrations.py) : au démarrage, chaque dossier
  du registre est mis au niveau du logiciel — copie de sûreté
  « avant-migration » D'ABORD, paliers idempotents (2 : multi-biens,
  3 : cession) réutilisant l'infrastructure existante, version marquée,
  jamais abaissée. Mise à jour = remplacer les fichiers, les données
  restent (testé : zéro écriture perdue, idempotent).
- **Paquet de distribution** (construire_distribution.py →
  dist/compta_lmnp_client_vX.zip) : code de production, lanceurs et docs
  UNIQUEMENT. Garde anti-fuite BLOQUANTE : jamais de tests, de FEC réels
  (reference/ = SIREN et adresse de l'exploitant), de bases .db, de
  sauvegardes ou d'archives dans le paquet — la construction échoue si un
  fichier interdit s'y glisse (testé).
- **LISEZ-MOI.md** : première installation (Python, lanceurs, messages
  Windows normaux — SmartScreen, pare-feu, certificat local, reliquat de
  la revue R5), procédure de mise à jour par-dessus l'existant,
  localisation des données, mise en garde cloud sync.
- 5 tests ajoutés (288 au total).


## 7.9.0 — 2026-07-17 (irritants du marché adressés avant J9)
Revue web des bugs et irritants documentés des logiciels de comptabilité
(EBP/Ciel : forums Compta Online, centres d'aide ; SaaS LMNP : avis
utilisateurs, comparatifs 2026). Deux manques réels corrigés :
- **« Clôturé par erreur »** (détresse récurrente des forums, la réponse
  étant toujours « restaurez la sauvegarde avant clôture ») : la sauvegarde
  automatique existait (J6), le moteur de restauration aussi (v7.4), mais
  AUCUNE interface. Nouvelle section « Sauvegardes du dossier actif » dans
  la page Dossiers : restauration en UN CLIC, réversible (l'état courant
  est d'abord mis de côté), interdite en bac à sable, noms de fichiers
  hostiles rejetés.
- **« Base plus récente que l'application »** (message EBP incompréhensible,
  rétrogradations impossibles) : table meta + version de schéma, marquée à
  chaque ouverture, jamais abaissée ; ouvrir un dossier créé par une
  version plus récente affiche un message pédagogique (HTTP 409) sans
  toucher aux données.
Déjà couverts par conception (constat de la revue) : base autonome SQLite
sans serveur (corruptions SQL Server), chemins relatifs (dossiers
déplacés), verrous (BEGIN IMMEDIATE v7.5), à-nouveaux testés, vocabulaire
métier sans jargon + infobulles (v7.3.1), multi-biens sans surcoût,
reprise d'historique gratuite (rejeu_fec). Hors périmètre assumé :
télétransmission EDI (documenté au pense-bête).
- 4 tests ajoutés (283 au total).


## 7.8.0 — 2026-07-17 (cession d'un bien + revue d'architecture)
Cession d'un bien (module cession.py, bouton « Céder ce bien… » sur la
fiche du bien) :
- dotation complémentaire prorata temporis jusqu'à la date de cession ;
- sortie des composants (28x + 675000 contre 2x), prix en 775000, colonnes
  bien.date_cession / composant.date_sortie créées à la volée ;
- traitement fiscal LMNP : plus-value NEUTRALISÉE dans le BIC (régime des
  particuliers, déclarée par le notaire — le produit 775 est déduit, la VNC
  675 réintégrée) ; 675/775 exclus du plafond 39 C (le prix de cession
  n'est pas un loyer acquis) ;
- ligne G' de l'état SUIV39C : le stock 39 C du bien cédé, tracé par la
  ventilation par bien, est définitivement sorti (global réduit d'autant,
  colonne « Sorti (G') » dans le PDF) ;
- la clôture ne redote jamais un composant sorti ; FEC conforme après
  cession (testé) ; rappel Pense-bête (2048-IMM chez le notaire,
  réintégration des amortissements dans la PV depuis 2025, cessation INPI
  si dernier bien).
Revue d'architecture pour repreneur expert :
- ARCHITECTURE.md : carte du code selon le cycle comptable de la
  profession, invariants à ne jamais casser (test en or, conformité par
  construction, Σ ventilation = global), choix assumés (pas de 512,
  migrations à la volée), dette priorisée (app.py 2 240 l. → blueprints au
  J9, lecteur FEC commun, page d'admin des gabarits).
- Simplification appliquée : ouvrir_exercice déménagée d'audit_cycle
  (outillage) vers reprise (production), nom public, alias conservé.
- 5 tests ajoutés (279 au total).


## 7.7.0 — 2026-07-17 (pense-bête des démarches manuelles)
Nouvelle page « Pense-bête » (module pense_bete.py) : rappels contextuels de
ce que le logiciel ne fait PAS à la place de l'exploitant, croisant le
calendrier et l'état du dossier. Trois niveaux (🔴 important, 🟠 à prévoir,
🔵 info) :
- cycle déclaratif : exercice N-1 à clôturer (dès février, pressant dès
  mai), liasse clôturée à TÉLÉDÉCLARER en période déclarative (février-juin)
  avec report 2042C-PRO — dates indicatives, renvoi vers impots.gouv.fr ;
- échéances : taxe foncière (octobre), avis puis paiement CFE au
  15 décembre (espace professionnel en ligne, aucun avis papier) ;
- événements : bien acquis dans l'année → formalités INPI (début/extension
  d'activité) et déclaration initiale de CFE 1447-C avant le 31/12, mise à
  jour de l'adresse d'activité ; CA > 23 000 € → alerte seuil LMP et
  affiliation sociale ; charges de copropriété sans fonds travaux ALUR
  saisi → rappel du gabarit dédié (réintégration automatique) ; aucune
  sauvegarde récente → rappel de lancer le logiciel et d'externaliser.
- 6 tests ajoutés (274 au total).


## 7.6.0 — 2026-07-17 (multi-biens : suivi 39 C logement par logement)
Conformité multi-biens de l'art. 39 C (règle rappelée par les liasses de référence,
§ 4.1.2) : la LIMITATION reste déterminée globalement pour l'exploitant
(comportement validé par le test en or, inchangé) ; la TENUE DU STOCK
d'amortissements reportables est désormais ventilée logement par logement.

- Nouvelle table suivi_39c_bien, alimentée à chaque clôture : report de
  l'année réparti au prorata des dotations de chaque bien, utilisation
  répartie au prorata des stocks, arrondis ajustés pour que la somme des
  stocks par bien égale TOUJOURS le stock global au centime (invariant
  testé). Préalable indispensable à la vente d'un bien (ligne G' de l'état
  SUIV39C : amortissements liés aux immobilisations sorties).
- Activation au démarrage OU en cours de vie : table créée à la volée, sans
  migration ; un stock historique jamais ventilé est hérité par le bien le
  plus ancien (exact pour toute comptabilité restée mono-bien jusque-là),
  le bien ajouté part de zéro.
- Liasse : reports.suivi_39c_par_bien exposé ; le PDF affiche le tableau
  « logement par logement » dès qu'il y a plusieurs biens.
- Rappel structure déjà en place : biens illimités (fiche adresse/prix/
  quote-part terrain), composants et opérations rattachés à leur bien,
  sélecteur de bien automatique dans la saisie ; identité de l'exploitant
  (nom, SIREN, adresse d'activité) dans la page Immobilisations.
- 4 tests ajoutés (268 au total) : mono-bien ≡ global, prorata deux biens,
  activation en cours de vie, utilisation ventilée.


## 7.5.0 — 2026-07-16 (TEST EN OR : liasses réelles reproduites à l'euro)
Les trois exercices réels 2023-2025 sont rejoués en chaîne depuis leurs FEC
et reproduisent, à l'euro près, CHAQUE grandeur des liasses de référence réellement
télétransmises et acceptées : résultat comptable, mouvements 39 C, résultat
fiscal, revenu imposable, année par année, imputation FIFO du bénéfice 2023
sur le déficit 2021, et l'état final des reports (556 + 13 020 = 13 575).

- **Correctif fiscal majeur (plafond 39 C)** : l'art. 39 C, II-2 limite la
  déduction aux loyers diminués des charges AFFÉRENTES AU BIEN. L'ancienne
  formule retenait toutes les charges : plafond trop bas, report gonflé,
  résultat fiscal faussé (0 au lieu de -630 en 2025) et déficits jamais
  créés. Les honoraires comptables (622610) et la CFE (635110) sont
  désormais exclus du plafond (table compte_hors_plafond_39c, extensible),
  et les réintégrations de charges non déductibles afférentes au bien
  (fonds travaux ALUR) majorent le plafond. Vérifié case par case contre
  les liasses réelles ; les déductions extra-comptables (retraitements
  négatifs) ne touchent que le résultat fiscal.
- **Nouveau module rejeu_fec.py** : import intégral d'un exercice depuis son
  FEC (journaux/comptes créés à la volée, montants négatifs des à-nouveaux
  normalisés par équivalence débit/crédit) — socle du test en or et d'une
  future migration depuis un autre outil (logiciels du marché…).
- **Concurrence (BEGIN IMMEDIATE)** : une transaction qui lisait puis
  écrivait partait en « database is locked » immédiat si un écrivain s'était
  intercalé (l'upgrade de verrou SQLite n'attend jamais) ; et le rejeu de
  collision relisait le même numéro dans son propre instantané. Les
  écritures ouvrent désormais la transaction en IMMEDIATE et rafraîchissent
  l'instantané entre deux tentatives : 12/12 stables sous 4 fils simultanés.
- Test en or permanent (tests/test_or_liasses_reelles.py) : toute modification du
  moteur qui ferait dévier un seul montant déclaré fait échouer la suite.


## 7.4.0 — 2026-07-16 (revue de fiabilité : campagnes R1-R6)
- **R1 — Restauration** : il n'existait AUCUNE fonction de restauration.
  Ajout de perennite.restaurer() : intégrité de la sauvegarde vérifiée AVANT
  d'écraser quoi que ce soit, copie de sûreté « avant-restauration » (la
  restauration est réversible), l'état corrompu est mis de côté, jamais perdu.
- **R2 — Crash en plein vol (correctif majeur)** : régression introduite en
  v7.2.2 — en SQLite, le RELEASE d'un savepoint le plus externe vaut COMMIT ;
  inserer(commit=False) commitait donc en douce et une coupure de courant en
  pleine clôture laissait une dotation fantôme en base. Transaction désormais
  ouverte explicitement avant le savepoint : kill -9 au milieu d'une clôture
  ne laisse plus AUCUNE trace partielle (vérifié par test).
- **R3 — Concurrence** : collision de numéro d'écriture entre deux saisies
  simultanées (deux onglets/instances) → rejeu borné quand le numéro est
  auto-attribué. 100 saisies sur 4 fils : 100 enregistrées, numérotation
  dense. Double-clic sur Clôturer : une dotation, un refus propre.
- **R4 — Import bancaire durci** : les CSV en encodage Windows (cp1252)
  faisaient crasher l'import ; les montants à espace insécable (1 234,56)
  étaient perdus EN SILENCE ; un fichier binaire renommé .csv crashait ;
  un libellé bancaire à tabulation aurait fait échouer l'import au guichet.
  Encodage UTF-8/BOM puis repli cp1252, nettoyage des séparateurs Unicode,
  refus propre du binaire, libellés assainis.
- **R5 — Revue Windows** : code vérifié sans open() texte non encodé (les
  accents survivent au cp1252 par défaut de Windows) ; lanceur .bat audité
  (chcp 65001, chemins entre guillemets, replis py/python). Restent à tester
  sur machine réelle : pare-feu et SmartScreen (documentation J9).
- **R6 — Longévité** : 30 exercices clôturés (2026-2055) — bilan équilibré
  chaque année, extinction progressive des amortissements sans jamais de
  sur-amortissement (VNC jamais négative), FEC 2055 conforme, 29 février
  bissextile accepté / inexistant rejeté.
- 11 tests permanents ajoutés (259 au total).


## 7.3.2 — 2026-07-16 (revue finale de conformité FEC)
Revue exhaustive A47 A-1 sur les trois FEC réels et un FEC généré : zéro
anomalie. Points formellement vérifiés pour la première fois : UTF-8 sans
BOM, fins de ligne CRLF homogènes (convention des fichiers réellement
acceptés par l'administration), appariement CompAuxNum/CompAuxLib et
Montantdevise/Idevise, ValidDate/PieceDate/JournalLib/CompteLib remplis,
18 champs par ligne, aucun espace parasite, montants extrêmes (10 milliards)
sérialisés en clair, accents intacts.

Validateur durci en conséquence : champs obligatoires par ligne (JournalLib,
CompteLib, PieceDate, ValidDate) et colonnes appariées (compte auxiliaire,
devise) désormais contrôlés — les FEC réels 2023-2025 restent conformes
(zéro faux positif). 5 tests ajoutés (248 au total).


## 7.3.1 — 2026-07-16 (ergonomie de saisie)
- Infobulles d'aide au survol (pastille « ? ») sur chaque champ du
  formulaire de saisie, avec un exemple du format attendu (date, montant,
  période, pièce, tiers, libellé). Pur CSS, aucun JavaScript.
- Les messages de rejet de saisie sont préfixés « Saisie refusée — » et
  s'affichent en clair à l'écran (ils étaient déjà explicites depuis 7.3.0 :
  motif précis + comment corriger). Bannière d'erreur multi-lignes lisible.


## 7.3.0 — 2026-07-16 (conformité FEC par construction)
Audit de rapprochement entre le guichet unique (ecritures.inserer) et le
validateur FEC : 11 brèches trouvées où une écriture ACCEPTÉE produisait
pourtant un FEC non conforme. Toutes fermées à la source — le guichet
garantit désormais qu'une écriture enregistrée produit un FEC conforme
(conformité par construction, non plus par vérification a posteriori).

Contrôles ajoutés au guichet (fonction _verifier_conformite_fec, miroir des
règles de valider_fec.py) :
- libellé d'écriture obligatoire (EcritureLib non vide, espaces compris) ;
- référence de pièce et code journal obligatoires ;
- date d'écriture réelle (AAAA-MM-JJ) ET dans l'exercice déclaré ;
- au moins deux lignes par écriture (partie double) ;
- interdiction des tabulations, sauts de ligne et retours chariot dans tous
  les champs texte (un copier-coller depuis un tableur ou un e-mail cassait
  la structure tabulée du FEC — brèche la plus sournoise).
Désactivable via verifier_conformite=False pour les seules injections
d'anomalies volontaires des tests d'audit.

Validateur FEC (symétrie) :
- ajout du contrôle de cohérence date/exercice (une écriture datée hors de
  l'exercice majoritaire est signalée) ; vérifié contre les FEC réels
  2023-2025 qui restent conformes.

Tests : 18 ajoutés (243 au total), dont un test « propriété » et un fuzz
ciblé qui vérifient l'invariant « accepté au guichet ⇒ FEC conforme ».


## 7.2.3 — 2026-07-16 (stress test couche web + validateur FEC)
Couche web :
- **Correctif — erreurs serveur 500** : une année ou un montant non
  numérique (« xxxx », « abc ») dans un formulaire déclenchait une erreur
  serveur avec fuite de traceback. Helpers de parsing tolérants
  (_form_int/_form_float) + gestionnaire d'erreurs global : toute exception
  devient une page sobre, jamais un traceback.
- **Plafond de requête** : corps > 2 Mo refusé (HTTP 413) avant chargement.
- Bonus : les montants à virgule française (« 795,50 ») sont désormais
  acceptés à la saisie web.

Validateur FEC (contrôles DGFiP Test Compta Demat) :
- Ajout : CompteNum d'au moins 3 caractères (norme PCG) ; lettrage cohérent
  (DateLet sans EcritureLet rejeté) ; validateur de nomenclature de fichier
  SirenFECAAAAMMJJ.txt.
- **Piège évité** : le rejet des montants négatifs, envisagé, aurait rejeté
  les FEC réels 2023-2025 (leurs à-nouveaux contiennent des négatifs
  légitimes). Écarté après test contre les fichiers de référence — désormais
  verrouillé par un test anti-régression.


## 7.2.2 — 2026-07-16 (stress test du moteur comptable)
- **Correctif — exercice clos scellé** : la saisie (métier ou directe) dans
  un exercice clos était acceptée alors que rien ne pouvait plus la détecter
  (contrôles exécutés avant clôture, FEC déjà archivé). Rejet dur au guichet
  unique, sans contournement possible.
- **Correctif — ordre chronologique des clôtures** : on pouvait clôturer
  N+1 avant N, faussant les stocks d'ouverture des reports (39 C, déficits).
  Les clôtures s'enchaînent désormais obligatoirement dans l'ordre.
- **Correctif — écritures orphelines** : un échec en cours d'insertion
  (compte inconnu, montant rejeté par la base…) laissait l'en-tête déjà
  inséré dans la transaction ; un commit ultérieur sans rapport figeait une
  écriture SANS LIGNE — trou dans la numérotation séquentielle du FEC.
  L'insertion est désormais protégée par un SAVEPOINT (tout ou rien).
- Campagne validée : 16 attaques au guichet contenues, marathon de
  10 exercices avec hostilités (bilan équilibré et FEC conforme chaque
  année), volume de 3 000 opérations (FEC de 6 037 lignes conforme,
  équilibre exact à 0,0000 €). 7 tests permanents ajoutés (199 au total).


## 7.2.1 — 2026-07-16 (audit pré-diffusion v7.2)
- **Correctif critique — perte de données** : recréer un dossier dont le
  répertoire existait déjà (registre `dossiers.json` perdu ou copie
  partielle) réinitialisait la base à blanc. Désormais la base existante est
  RATTACHÉE au registre, jamais réinitialisée.
- **Correctif — génération PDF** : un nom d'exploitant ou un libellé de
  composant contenant « < » ou « & » faisait planter l'export PDF de la
  liasse (interprétation balisage ReportLab). Toutes les données utilisateur
  sont désormais échappées à la frontière PDF ; les libellés longs passent à
  la ligne au lieu de déborder du tableau 2033-C.
- **Correctif — couverture des sauvegardes** : la sauvegarde quotidienne de
  démarrage ne couvrait que le dossier principal ; elle couvre maintenant
  tous les dossiers du registre.
- Ouvrir ou créer un dossier purge le mémo de retour du bac à sable
  (cookie devenu caduc) ; créer un dossier depuis le bac à sable en sort
  explicitement.
- 8 tests d'audit ajoutés (192 au total), dont : FEC archivé validé par le
  validateur indépendant, isolation des archives par dossier.


## 7.2.0 — 2026-07-16 (J8 multi-dossiers)
- **Plusieurs comptabilités indépendantes** : menu « Dossiers » — création
  d'un dossier vierge, ouverture (cookie), renommage. Chaque dossier vit dans
  `dossiers/<slug>/` avec sa base, ses sauvegardes et ses archives FEC.
- Le `compta.db` historique reste le « Dossier principal » : aucune migration.
- L'en-tête affiche en permanence le dossier actif.
- Quitter le bac à sable ramène au dossier de travail d'origine (et non plus
  systématiquement au principal).
- Sécurité : le cookie de sélection n'est jamais utilisé comme chemin — il
  est confronté au registre `dossiers.json`, tout slug inconnu ou forgé
  retombe sur le dossier principal.


## 7.1.0 — 2026-07-15 (J6 pérennité + J7 liasse PDF)
- **Sauvegardes automatiques** de la base (`sauvegardes/`) : copie cohérente
  via l'API backup SQLite, au démarrage (1×/jour) et avant chaque clôture ;
  rotation (30 copies conservées).
- **Archivage FEC** (`archives/`) : à chaque clôture, le FEC de l'exercice est
  figé avec son empreinte SHA-256 dans `manifeste.csv` (piste d'audit,
  contrôle d'intégrité par `perennite.verifier_archives()`).
- **Liasse fiscale en PDF** : bouton « Télécharger la liasse en PDF » sur la
  page Liasse (2031, 2033-A/B/C, reports 39 C et déficits, aide 2042C-PRO,
  contrôles). Filigrane PROVISOIRE si l'exercice n'est pas clos.
  Nouvelle dépendance : reportlab (installée par les lanceurs).
- Numéro de version affiché dans le pied de page (fichier `VERSION`).

## 7.0.0 — audit v7
- Correction : mélange d'exercices dans l'export FEC (filtre par exercice).
- Correction : double clôture possible (idempotence) ; clôture rendue
  atomique (une seule transaction).
- Correction : XSS réfléchie sur les messages flash (échappement systématique).
- Correction : montants NaN acceptés par les contrôles d'équilibre.
- Tests rendus hermétiques (COMPTA_DB) ; `certs/` exclu du versionnement.
