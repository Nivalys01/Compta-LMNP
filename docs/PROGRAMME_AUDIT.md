# Programme d'audit — prompts prêts à l'emploi

Ce document contient les prompts à donner à une IA pour auditer le logiciel,
domaine par domaine. Il est écrit à partir de ce qui a **effectivement
fonctionné** sur les passes A à F, et de ce qui leur a échappé.

## Comment s'en servir

1. Coller le **préambule** (section 1) en tête de chaque prompt.
2. Coller la section **1 bis** (interdiction de lecture) — toujours.
3. Coller ensuite **une seule** passe (sections 3 à 15). Une passe par
   conversation : mélanger les domaines dilue la revue.
4. Indiquer les fichiers listés sous « Pièces à joindre » — **tous**, et rien
   de plus. Une passe qui reçoit trop de code survole ; une passe à qui il
   manque une pièce invente.
5. Mettre à jour la section 2 (« déjà trouvé ») avant chaque nouvelle passe,
   sinon la revue resignale ce qui est corrigé et on perd sa confiance.

**L'IA a accès au dossier de projet entier, données réelles comprises.** Le
préambule lui interdit donc de LIRE certains fichiers — ce n'est plus une
question de ce qu'on transmet, mais de ce qu'on demande de ne pas ouvrir.
Cette interdiction est la section 1 bis : ne pas la retirer du prompt.

---

## 1. Préambule commun

> Tu es auditeur logiciel. Je te confie un module d'un logiciel de
> comptabilité LMNP au réel, développé par un particulier, distribué
> gratuitement, dont les états produits (liasse fiscale, FEC) servent à
> préparer une déclaration réelle.
>
> **Si un fichier te manque, dis-le — ne déduis rien.** Un constat fondé sur
> une fonction supposée est pire qu'un constat manquant : il coûte du temps à
> réfuter et fait douter du reste.
>
> ### Ce que je cherche
>
> Des défauts qui **produisent un résultat faux sans produire d'erreur**.
> C'est le registre de tout ce qui a été trouvé jusqu'ici : un import réussi
> qui a perdu la moitié des lignes, un contrôle qui affirme « aucune donnée
> personnelle » sans avoir rien cherché, une case de liasse servie à zéro
> alors que le montant existe. Un plantage se voit ; un chiffre faux qui
> ressemble à un chiffre juste se recopie sur une déclaration.
>
> Cherche en particulier :
>
> - un calcul juste sur le cas nominal et faux sur un cas limite — montant
>   nul, exercice incomplet, premier ou dernier exercice, valeur à la
>   frontière exacte d'un seuil, arrondi à un centime près ;
> - une donnée qui traverse sans être vue parce qu'elle arrive sous une forme
>   non prévue : casse différente, accents, espaces multiples, signe suffixe,
>   numéro de compte à sept chiffres là où le code en attend six ;
> - un `except` qui avale, un `continue` sur un cas non prévu, un `if` sans
>   `else` qui laisse passer l'entrée intacte ;
> - une valeur énumérée là où elle devrait être déduite — une liste de
>   préfixes, de comptes ou de fichiers écrite à la main ne peut pas signaler
>   ce qu'on a oublié d'y mettre ;
> - deux modules qui calculent la même grandeur de deux façons.
>
> ### Comment je veux que tu procèdes
>
> **Reproduis par EXÉCUTION, pas par lecture.** Un test qui relit le code
> conclut au succès là où l'exécution échoue : c'est arrivé sur un correctif
> de transaction apparemment correct — `commit=False` passé, `rollback`
> appelé — que seul un comptage des lignes en base après échec a démenti.
>
> **Sors du cadre au moins une fois par passe.** Les deux défauts les plus
> graves de la dernière revue n'ont pas été trouvés par la suite de tests
> mais par deux gestes latéraux : compter ce qui reste en base après un
> échec, et décompresser le paquet ailleurs pour le démarrer. Les tests
> passaient dans les deux cas.
>
> **Si le code contredit mon énoncé, corrige mon énoncé.** Cinq constats sur
> vingt-deux ont été amendés ainsi à la dernière passe : une conséquence
> annoncée qui n'existait pas, une cause supplémentaire non vue, un constat
> déjà réglé, un diagnostic faux. Une revue qui se contente de confirmer ne
> sert à rien.
>
> **Distingue un défaut d'un choix assumé.** Ce logiciel tient la
> comptabilité SANS comptes de tiers ni trésorerie, contrepartie unique
> 108000. Les cases « fournisseurs », « clients » et « disponibilités » du
> bilan restent donc vides : c'est décidé, documenté, et ce n'est pas un
> constat. Si tu penses qu'un choix est mauvais, dis-le comme un choix à
> rediscuter, pas comme un bug.
>
> ### Format imposé
>
> Pour chaque constat :
>
> - un identifiant (`X-01`, `X-02`… avec la lettre de la passe) ;
> - le **fichier et la fonction réels** — ne cite que ce qui existe dans les
>   pièces jointes ;
> - un **scénario reproductible**, avec les valeurs d'entrée ;
> - **attendu** contre **produit**, le produit étant une sortie réelle
>   d'exécution et non une lecture ;
> - la **conséquence pour le déclarant**, chiffrée quand c'est possible ;
> - une **gravité** : critique / majeur / mineur, et pourquoi.
>
> Puis :
>
> - une section **« Ce qui a été vérifié et tenu »** — ce qui est sain mérite
>   d'être écrit, sinon la prochaine revue le recontrôlera ;
> - une section **« Non vérifiable avec les pièces fournies »**, où va tout
>   ce que tu n'as pas pu établir, formulé en questions ;
> - un **tableau récapitulatif** : identifiant, constat, fichier, gravité.
>
> **N'écris aucune donnée personnelle dans ton rapport**, même pour
> illustrer. Si un libellé réel sert ton propos, remplace-le par un
> équivalent fictif. Ce piège s'est refermé deux fois à la dernière passe :
> un nom réel recopié depuis un rapport dans un test, puis une adresse réelle
> écrite dans le rapport qui décrivait précisément cette faute.
>
> La manière la plus sûre de tenir cette règle est de ne pas ouvrir les
> fichiers qui en contiennent : voir l'interdiction de lecture ci-dessous,
> qui fait partie du prompt.

---

## 1 bis. Fichiers à NE PAS LIRE — à coller avec le préambule

> ### Interdiction de lecture
>
> Tu as accès au dossier de projet entier, **données réelles comprises**. Tu
> ne dois **pas ouvrir** les fichiers suivants, ni en citer le contenu, ni
> t'en servir pour construire un scénario :
>
> | Chemin | Ce qu'il contient |
> |---|---|
> | `reference/` (tout le répertoire) | trois FEC RÉELS — identité, SIREN, adresse, comptabilité complète — et la liste des tiers à ne jamais publier |
> | `seed_exemple.sql` | la même identité, en jeu de données |
> | `*.db`, `*.sqlite`, `*.sqlite3` | la comptabilité tenue |
> | `sauvegardes/` | copies de cette base |
> | `archives/` | FEC exportés réels, et leur manifeste d'empreintes |
> | `logs/`, `imports_tmp/`, `dossiers.json` | journaux, relevés déposés, registre des dossiers |
> | tout `.pdf`, `.docx`, `.xlsx` à la racine du dépôt | documents de travail, dont un bilan établi par un cabinet |
>
> **Ce que tu peux lire sans réserve** : tout le code, `schema.sql`,
> `seed_referentiel.sql` (le plan de comptes générique), et le jeu de
> démonstration **anonymisé** — `seed_demo.sql` et `demo/FEC_DEMO_2025.txt`.
> Ce dernier a la même structure que le FEC réel, avec des valeurs fictives :
> il suffit à tout ce qu'un audit demande.
>
> ### Pourquoi
>
> Trois raisons, dont une qui n'est pas de principe.
>
> 1. **Un audit n'a pas besoin de données réelles.** Trente-quatre constats
>    ont été trouvés sur les passes précédentes, aucun ne l'a exigé : les
>    scénarios se construisent, et un cas limite construit exprès est plus
>    probant qu'un cas trouvé par hasard dans un vrai dossier.
> 2. **Ton rapport sera versionné dans le dépôt**, qui part sur un hébergeur
>    distant. Ce que tu y écris est publié. Le piège s'est refermé deux fois :
>    un nom réel recopié depuis un rapport dans un fichier de test, puis une
>    adresse réelle écrite dans le rapport qui décrivait précisément cette
>    faute. Les deux fois, c'est un contrôle automatique qui a bloqué avant la
>    publication — ne compte pas sur lui.
> 3. **Lire ces fichiers t'induirait en erreur sur ce que voit un
>    utilisateur.** Le dossier réel est le cas particulier de l'auteur, tenu
>    depuis 2023, sans anomalie. Les défauts qui comptent sont ceux d'un
>    dossier neuf, d'un premier exercice, d'un FEC de cabinet tiers — c'est-à-dire
>    de ce que tu construis, pas de ce que tu trouves.
>
> ### Une exception, et une seule
>
> Plusieurs modules **prennent ces fichiers pour entrée** :
> `outils_demo.py` les anonymise, `verifier_depot.py` en dérive les empreintes
> qu'il traque, `init_db.py` bascule dessus en mode démonstration quand ils
> sont là. Les auditer suppose de comprendre ce qu'ils en font.
>
> Tu peux donc **lire le code qui les touche**, et **la structure** de ces
> fichiers — noms de colonnes, forme d'un `INSERT`, nombre de lignes — mais
> **jamais les valeurs**. Si tu as besoin d'un échantillon, prends
> `seed_demo.sql` : il a la même forme et des valeurs fictives.
>
> Si tu penses qu'un constat ne peut pas être établi sans lire une valeur
> réelle, **dis-le dans la section « Non vérifiable »** plutôt que de la lire.
> C'est exactement à cela que cette section sert.

---

## 2. Déjà trouvé et corrigé — ne pas resignaler

*(à mettre à jour avant chaque passe ; état au 15/09/2026)*

> Les défauts suivants sont **corrigés**, inutile de les relever :
>
> **Lecture et migration de FEC** — à-nouveaux ignorant la classe 5 (banque) ;
> guillemet non refermé fusionnant des lignes ; rejeu groupé sur le seul
> numéro d'écriture au lieu du couple (journal, numéro) ; ISO-8859-15 et BOM
> illisibles ; comptes créés sans `type` ; seconde reprise non refusée.
>
> **Cycle de vie du dossier** — `init()` détruisant une base tenue sans
> sauvegarde ; restauration réattribuant des numéros de quittance déjà émis ;
> sauvegarde non rattachée à son dossier.
>
> **Liasse d'un exercice de cession** — résultat fiscal recalculé sans la
> neutralisation de cession ; ligne 352 valant la plus-value au lieu de zéro ;
> produits exceptionnels (77x) confondus avec le chiffre d'affaires en case
> 218 ; charges exceptionnelles calculées mais jamais imprimées ; numéros de
> rubrique du 2033-C calculés puis jamais rendus ; charges de classe 6 hors
> des préfixes 60/61/62/63/66/67 n'atterrissant dans aucune case, si bien
> qu'une dotation portée en 6811000 par un cabinet disparaissait de la liasse
> tout en pesant sur le résultat.
>
> **Couche web et ligne de commande** — confirmations JavaScript cassées par
> une apostrophe ; bac à sable partageant ses répertoires avec le dossier
> réel ; cookie de dossier expirant en 8 h ; migration de schéma ne tournant
> qu'au démarrage ; dossier absent remplacé par une base vierge ; aucune
> protection contre une écriture d'origine étrangère ; validation d'import non
> transactionnelle ; clôture en ligne de commande n'archivant pas le FEC ;
> échec d'archivage présenté comme un échec de clôture.
>
> **Import bancaire** — tout encaissement inconnu classé en loyer imposable ;
> export à quatre colonnes lu à l'envers ; formats de montant ignorés en
> silence ; mots-clés matchés en sous-chaîne (« mobilier » dans
> « IMMOBILIER ») ; nature jamais confrontée au signe ; fourre-tout en charge
> déductible au lieu d'un compte d'attente ; accents absents des mots-clés ;
> seuil d'immobilisation jamais testé ; dates non validées.
>
> **Chaîne de distribution** — garde de publication concluant au vert sans
> avoir chargé d'empreinte ; garde du paquet ne contrôlant que des noms tirés
> d'une liste écrite à la main ; anonymisation du jeu de démonstration sans
> vérification après génération ; recherche d'empreintes sensible à la casse
> et aux accents.
>
> **Transactions** — une fonction de lecture (`gabarits.assurer_table`,
> `parametres.assurer`) committait inconditionnellement et terminait la
> transaction de son appelant, rompant en silence le contrat `commit=False`.
>
> Ces défauts ont un point commun qui te donne le registre attendu : **aucun
> ne produisait d'erreur**. Chacun ressemblait au succès.

---

## 3. Passe G — Régularité comptable et intégrité du FEC

**Pièces à joindre** : `modules/ecritures.py`, `modules/operations.py`,
`modules/export_fec.py`, `modules/valider_fec.py`, `modules/fec_io.py`,
`schema.sql`, `seed_referentiel.sql`, et le CERFA/arrêté si tu veux un
contrôle de conformité littéral.

> Périmètre : la tenue de la comptabilité elle-même, avant toute
> considération fiscale.
>
> Ce que je veux savoir :
>
> - **L'équilibre est-il garanti par construction ou par convention ?** Une
>   écriture déséquilibrée peut-elle entrer en base par un chemin qui ne
>   passe pas par le contrôle — un `INSERT` direct, une contre-passation, une
>   reprise, un rejeu ?
> - **La numérotation des écritures** est-elle continue et unique par
>   exercice ? Que se passe-t-il sur deux saisies simultanées, sur un rejeu
>   interrompu, sur un FEC source numéroté par journal ?
> - **Les montants** : un arrondi peut-il déséquilibrer une écriture d'un
>   centime ? Où l'arrondi est-il fait — une fois, ou à chaque étape ? Un
>   montant négatif, nul, ou non fini (`inf`, `nan`) peut-il entrer ?
> - **Le FEC exporté est-il conforme** à l'arrêté A47 A-1 : 18 colonnes,
>   ordre, séparateur, encodage, format des montants et des dates, colonnes
>   obligatoires ? Le validateur du logiciel accepte-t-il son propre export ?
>   Et refuse-t-il ce qu'il doit refuser ?
> - **L'immutabilité** : une écriture d'un exercice clos peut-elle être
>   modifiée ou supprimée ? Par quel chemin ?
> - **La contre-passation** est-elle une vraie contre-passation — écriture
>   inverse, même date, rien de supprimé — ou une suppression déguisée ?
>
> Vérifie en particulier ce qui se passe **à la frontière d'exercice** : une
> opération datée du 31/12 ou du 01/01, un exercice de moins de douze mois,
> deux exercices ouverts.

---

## 4. Passe H — Amortissements

**Pièces à joindre** : `modules/amortissement.py`, `modules/plan_immo.py`,
`schema.sql` (tables `composant`, `plan_amortissement`),
`modules/controles.py`.

> Périmètre : le plan d'amortissement des composants, sa génération et sa
> reprise.
>
> Ce que je veux savoir :
>
> - **La règle du prorata temporis** est-elle juste ? Un composant mis en
>   service le 15 d'un mois, le 31 décembre, le 1er janvier : combien de
>   jours ou de mois la première annuité compte-t-elle, et sur quelle
>   convention — jours réels, mois entiers, trentièmes ?
> - **La dernière annuité** solde-t-elle exactement la valeur brute, au
>   centime, ou laisse-t-elle un résidu ? Que se passe-t-il si la durée est
>   modifiée en cours de vie ?
> - **L'amortissement minimum de l'article 39 B** : le logiciel garantit-il
>   que le cumul pratiqué n'est jamais inférieur à l'amortissement linéaire ?
>   Comment se comporte-t-il après un exercice où la dotation a été bridée
>   par l'article 39 C ?
> - **Le terrain** : jamais amortissable. Est-ce garanti, ou seulement
>   respecté par les données livrées ?
> - **La ventilation par composants** : la somme des composants égale-t-elle
>   le prix d'acquisition ? Qu'advient-il du résidu d'arrondi ? Une
>   ventilation incomplète ou excédentaire est-elle refusée ou acceptée ?
> - **La reprise d'amortissements antérieurs** (dossier repris en cours de
>   vie) : le cumul saisi est-il confronté à ce que le plan aurait produit ?
>   Un cumul supérieur à la valeur brute est-il possible ?
>
> Recalcule au moins un plan complet à la main, sur toute sa durée, et
> compare-le au plan produit — annuité par annuité, pas seulement le total.

---

## 5. Passe I — Article 39 C : plafonnement de la dotation

**Pièces à joindre** : `modules/fiscal.py`, `modules/amortissement.py`,
`modules/liasse.py`, `modules/parametres.py`, `modules/controles.py`.

> Périmètre : le plafonnement de l'amortissement déductible en location
> meublée non professionnelle (art. 39 C, II-2 du CGI) et le suivi du stock
> reporté.
>
> Ce que je veux savoir :
>
> - **L'assiette du plafond** : « loyers acquis diminués des charges
>   afférentes au bien ». Quelles charges le logiciel retient-il, et
>   lesquelles exclut-il ? Une charge de structure — honoraires comptables,
>   CFE, frais bancaires — doit-elle entrer ? Le choix est-il explicite et
>   justifié, ou implicite ?
> - **Le report** : la fraction non déduite est-elle reportée sans limite de
>   durée, et imputable sur les exercices où le plafond le permet ? L'ordre
>   d'imputation est-il le bon — report le plus ancien d'abord ?
> - **Le suivi par bien** : sur plusieurs logements, le plafond se calcule-t-il
>   bien **par bien** et non globalement ? Que devient le stock d'un bien
>   cédé ?
> - **Les cas limites** : loyers nuls, charges supérieures aux loyers
>   (plafond négatif), premier exercice partiel, exercice sans aucune
>   opération.
> - **La cohérence avec la liasse** : le stock imprimé dans le suivi 39 C
>   correspond-il à ce que le moteur a calculé, et à ce que la clôture a figé ?
>
> Construis un scénario sur **trois exercices consécutifs** : un où le plafond
> bride, un où il permet de reprendre, un où le bien est cédé. Vérifie que le
> stock se boucle à zéro et que rien n'est perdu ni compté deux fois.

---

## 6. Passe J — Déficits LMNP : report et péremption

**Pièces à joindre** : `modules/fiscal.py`, `modules/liasse.py`,
`schema.sql` (table `deficit_lmnp`), `modules/controles.py`,
`modules/liasse_pdf.py`.

> Périmètre : les déficits de location meublée non professionnelle — leur
> création, leur report, leur imputation et leur péremption. C'est la
> mécanique la plus spécifique du régime, et la plus coûteuse en cas
> d'erreur : un déficit perdu ne se récupère pas.
>
> Rappel du régime, à vérifier dans le code et non à supposer : le déficit
> d'une activité de location meublée **non professionnelle** n'est imputable
> que sur les **bénéfices de même nature** — pas sur le revenu global — et il
> est reportable **dix ans**.
>
> Ce que je veux savoir :
>
> - **La péremption** : le compte à rebours part-il de l'exercice de
>   création, et expire-t-il à la fin du dixième exercice suivant, ou du
>   dixième exercice tout court ? Vérifie la borne exacte — un exercice
>   d'écart, c'est un déficit perdu ou indûment imputé.
> - **Un déficit périmé est-il exclu du stock imputable** — et l'est-il
>   partout : dans le calcul, dans la liasse imprimée, dans l'aide au report
>   2042C-PRO ? Le total affiché peut-il être supérieur à la somme
>   réellement imputable ?
> - **L'ordre d'imputation** : le plus ancien d'abord, sans quoi on laisse
>   périmer ce qu'on aurait pu utiliser. Est-ce garanti ?
> - **L'imputation partielle** : un bénéfice inférieur au stock laisse-t-il
>   le reliquat correctement réparti entre millésimes, chacun gardant sa
>   propre date de péremption ?
> - **Le passage professionnel / non professionnel** : si le statut change,
>   les déficits antérieurs suivent-ils la bonne règle ? Le logiciel
>   prétend-il traiter ce cas, et si oui le fait-il ?
> - **La clôture** : un exercice clos fige-t-il le stock ? Une reclôture, une
>   restauration de sauvegarde, une réouverture peuvent-elles dupliquer ou
>   effacer un millésime ?
> - **La cohérence des trois représentations** : la table `deficit_lmnp`, le
>   tableau de suivi de la liasse, et les cases de l'aide 2042C-PRO
>   racontent-elles la même chose ?
>
> Construis un scénario sur **douze exercices** : un déficit créé au premier,
> aucun bénéfice avant le onzième. Le déficit doit être périmé et
> **explicitement signalé comme tel**, pas silencieusement absent.

---

## 7. Passe K — Clôture et cycle pluriannuel

**Pièces à joindre** : `modules/fiscal.py` (`cloturer`), `modules/reprise.py`,
`modules/migration_fec.py`, `modules/rejeu_fec.py`,
`schema.sql` (table `cloture_fiscale`), `modules/perennite.py`.

> Périmètre : la clôture d'un exercice et l'enchaînement d'un exercice au
> suivant.
>
> Ce que je veux savoir :
>
> - **L'atomicité** : la clôture écrit la dotation, fige le résultat fiscal,
>   met à jour les déficits et le stock 39 C, archive le FEC. Une coupure au
>   milieu laisse-t-elle un exercice à moitié clos ? Reproduis-la — un `kill`
>   au bon endroit, pas une lecture du code.
> - **L'idempotence** : clôturer deux fois le même exercice, ou clôturer un
>   exercice déjà clos, produit quoi ?
> - **Le bilan d'ouverture** : les à-nouveaux de N+1 reprennent-ils
>   exactement le bilan de clôture de N, au centime ? Quel compte reçoit le
>   résultat, et le report à nouveau est-il correctement cumulé ?
> - **L'ordre des exercices** : peut-on clôturer N+1 avant N ? Ouvrir un
>   exercice antérieur à un exercice clos ? Saisir dans un exercice clos par
>   un chemin détourné ?
> - **La reprise depuis un FEC externe** : un dossier repris en cours de vie
>   part-il d'un bilan juste ? Les amortissements antérieurs, le stock 39 C et
>   les déficits sont-ils repris, ou repartent-ils de zéro en silence ?
>
> Construis un cycle de **quatre exercices** en partant d'un dossier vierge,
> et compare le bilan de clôture du quatrième à ce qu'un calcul indépendant
> donne. Puis recommence en reprenant le troisième depuis un FEC.

---

## 8. Passe L — Cession d'un bien

**Pièces à joindre** : `modules/cession.py`, `modules/fiscal.py`,
`modules/liasse.py`, `modules/amortissement.py`, `modules/controles.py`.

> Périmètre : la sortie d'un bien de l'actif et son traitement fiscal.
>
> En LMNP **non professionnel**, la plus-value relève du régime des
> plus-values des **particuliers** (art. 150 U et suivants), non du résultat
> BIC : le produit de cession et la valeur comptable des éléments cédés
> doivent donc être **neutralisés** dans le résultat fiscal. Vérifie que
> c'est bien ce que fait le code, et que la neutralisation est complète.
>
> Ce que je veux savoir :
>
> - **La valeur nette comptable** à la date de cession : l'amortissement de
>   l'exercice de cession est-il calculé au prorata jusqu'à la date de sortie,
>   ou sur l'année entière, ou pas du tout ?
> - **Les composants** : tous sortent-ils, y compris ceux déjà sortis
>   auparavant ? Un composant oublié laisse un actif fantôme au bilan.
> - **Le stock 39 C** du bien cédé : que devient-il ? Est-il perdu, transféré,
>   ou reste-t-il à tort dans le stock global ?
> - **Une cession partielle** ou à titre gratuit, un prix nul, un prix
>   inférieur à la VNC : la neutralisation tient-elle dans les deux sens ?
> - **La liasse** : les cases exceptionnelles sont-elles servies, la
>   ventilation imprimée est-elle cohérente, et le résultat fiscal
>   correctement neutralisé ?
> - **Le multi-biens** : céder un bien sur trois affecte-t-il les deux
>   autres — dotation, plafond, stock ?

---

## 9. Passe M — Le moteur de contrôles lui-même

**Pièces à joindre** : `modules/controles.py`, `modules/audit_cycle.py`,
et les modules que les contrôles interrogent.

> Périmètre : les vingt-sept contrôles du logiciel. **C'est le garde-fou
> qu'on audite**, pas ce qu'il garde — et l'expérience des passes
> précédentes montre que le garde-fou est souvent plus faible que le code
> qu'il protège.
>
> Ce que je veux savoir, pour chaque contrôle :
>
> - **Peut-il échouer à détecter ce qu'il annonce ?** Construis un dossier
>   qui porte exactement le défaut visé, et vérifie que le contrôle le
>   signale. Un contrôle qui ne se déclenche jamais est pire qu'absent.
> - **Peut-il se déclencher à tort** sur un dossier sain ? Un faux positif
>   récurrent apprend à ignorer les alertes.
> - **Sa gravité est-elle juste ?** Un « avertissement » sur un défaut qui
>   rend la déclaration fausse est une gravité mal placée : il devrait
>   bloquer. Inversement, un bloquant sur un cas légitime rend le logiciel
>   inutilisable.
> - **Se tait-il quand il ne peut pas travailler ?** Un contrôle qui rend
>   « conforme » parce que la table est vide, l'exercice absent ou la donnée
>   illisible donne une fausse assurance. C'est le défaut le plus grave
>   trouvé jusqu'ici, deux fois.
> - **Le contrôle d'équilibre du bilan** compare-t-il deux grandeurs
>   calculées indépendamment, ou une grandeur à elle-même ? (Regarde-le de
>   près : c'est un piège connu de ce logiciel.)
>
> Rends un tableau : contrôle, ce qu'il prétend détecter, se déclenche-t-il
> réellement, faux positif possible, gravité juste.

---

## 10. Passe N — Règles fiscales versionnées et veille

**Pièces à joindre** : `modules/parametres.py`, `modules/veille_fiscale.py`,
`modules/gabarits.py`, `modules/pense_bete.py`.

> Périmètre : les règles fiscales paramétrables (seuils, taux, durées) et
> leur versionnement dans le temps.
>
> Ce que je veux savoir :
>
> - **Une règle est-elle bien lue au millésime de l'exercice** et non à la
>   date du jour ? Un exercice 2024 recalculé en 2027 doit retrouver la règle
>   de 2024. Vérifie-le sur un exercice antérieur à un changement de règle.
> - **Le chevauchement** : deux versions d'une même règle couvrant la même
>   date, ou un trou entre deux versions, sont-ils possibles ? Que rend la
>   lecture dans ce cas ?
> - **Les valeurs par défaut** : quand une règle manque, le repli est-il
>   explicite et signalé, ou silencieux ? Un repli muet sur une valeur
>   obsolète produit un calcul faux sans alerte.
> - **Les seuils à la frontière exacte** : 500 € pile, dernier jour de
>   validité, exercice à cheval sur un changement.
> - **Le catalogue de gabarits** : un gabarit personnalisé peut-il viser un
>   compte de classe incohérente avec sa nature ? Peut-il écraser un gabarit
>   standard ?

---

## 11. Passe O — Pérennité : sauvegarde, restauration, incident

**Pièces à joindre** : `modules/perennite.py`, `modules/dossiers.py`,
`modules/migrations.py`, `modules/init_db.py`.

> Périmètre : ce qui protège les données de l'utilisateur, et ce qui se passe
> quand quelque chose se casse.
>
> Ce que je veux savoir :
>
> - **La sauvegarde est-elle vérifiée avant d'être considérée comme faite ?**
>   Une copie tronquée, un disque plein, un fichier verrouillé : la fonction
>   rend-elle un succès ?
> - **La restauration** vérifie-t-elle l'intégrité de la sauvegarde **avant**
>   d'écraser la base courante, et garde-t-elle une copie de sûreté du
>   remplacé ?
> - **La rotation** ne peut-elle pas supprimer la dernière sauvegarde
>   valable ? Une sauvegarde « de sûreté » est-elle bien hors rotation ?
> - **La migration de schéma** : reprise après échec au milieu d'un palier ?
>   Deux migrations concurrentes sur le même fichier ? Une base marquée à
>   jour sans que les paliers aient tourné ?
> - **Un dossier dont le fichier a disparu** — disque débranché, synchro en
>   retard : que fait le logiciel ? Créer une base vierge à sa place serait
>   une perte silencieuse.
>
> Provoque au moins **trois incidents réels** : coupure pendant une écriture
> (`kill -9`), fichier de sauvegarde tronqué, disque en lecture seule.

---

## 12. Passe P — Quittances et obligations locatives

**Pièces à joindre** : `modules/quittances.py`, `schema.sql` (tables
`locataire`, `quittance`), `modules/perennite.py`, `modules/pages.py`.

> Périmètre : les quittances de loyer — documents remis à un tiers, donc
> irréversibles une fois sortis.
>
> Ce que je veux savoir :
>
> - **La numérotation** est-elle continue, unique, et sans réutilisation
>   possible ? Une quittance déjà remise dont le numéro serait réattribué à
>   un autre document est un faux en écriture.
> - **La colocation** : un loyer partagé produit-il des quittances cohérentes
>   entre elles et avec le loyer encaissé ?
> - **Une quittance survit-elle à l'annulation de l'encaissement** qu'elle
>   atteste ? Elle ne devrait pas — ou l'annulation doit produire une
>   rectification explicite.
> - **Les mentions obligatoires** : période, montants loyer et charges
>   séparés, identité du bailleur et du locataire, date de paiement.
> - **La cohérence avec la comptabilité** : le montant quittancé correspond-il
>   à l'opération enregistrée, et la période à l'exercice ?

---

## 13. Passe Q — Concurrence et intégrité transactionnelle

**Pièces à joindre** : `modules/ecritures.py`, `modules/operations.py`,
`modules/fiscal.py`, `modules/gabarits.py`, `modules/parametres.py`,
`app.py`.

> Périmètre : transverse. Cette passe ne cherche pas un domaine mais une
> propriété — **une opération se termine entièrement ou pas du tout**.
>
> Contexte : le logiciel est mono-utilisateur, mais le serveur est threadé et
> un navigateur ouvre plusieurs requêtes en parallèle. Un défaut de cette
> famille a déjà été trouvé : une fonction de lecture qui committait, et
> terminait la transaction de son appelant.
>
> Ce que je veux savoir :
>
> - **Quelles fonctions committent ?** Dresse-en la liste. Pour chacune :
>   est-ce une écriture délibérée, ou un effet de bord sur un chemin de
>   lecture ? Une fonction qui sème une table au premier accès ne doit pas
>   valider le travail de son appelant.
> - **Le contrat `commit=False`** est-il tenu de bout en bout, sur toute la
>   chaîne d'appels ? Vérifie-le en comptant les lignes en base après un
>   `rollback`, jamais en relisant le code.
> - **Les opérations composites** — clôture, import validé, reprise, cession,
>   ventilation d'un appel de charges — sont-elles atomiques ? Fais échouer
>   chacune **au milieu** et compte ce qui reste.
> - **Les savepoints** : un `RELEASE` de savepoint le plus externe vaut
>   `COMMIT` en SQLite. Ce piège est connu du code ; est-il évité partout ?
> - **La concurrence** : deux requêtes simultanées sur le même dossier —
>   deux saisies, une saisie pendant une clôture, deux migrations.

---

## 14. Passe R — Sécurité de l'interface locale

**Pièces à joindre** : `app.py`, `modules/pages.py`, `modules/dossiers.py`,
`cli.py`.

> Périmètre : la surface d'attaque d'une application web servie sur
> `127.0.0.1`.
>
> Le modèle de menace du logiciel repose sur « l'application n'écoute que sur
> la machine locale ». C'est exact pour le réseau et **sans effet pour le
> navigateur** : toute page ouverte dans le même navigateur peut poster sur
> `localhost`. Une garde d'origine a été ajoutée depuis ; vérifie qu'elle
> couvre tout ce qu'elle doit couvrir.
>
> Ce que je veux savoir :
>
> - **Toutes les routes qui changent l'état** sont-elles protégées, ou une
>   seule famille ? Y a-t-il une méthode d'écriture non couverte ?
> - **L'échappement** : une donnée utilisateur — nom d'exploitant, libellé de
>   composant, nom de dossier — peut-elle casser le HTML, le JavaScript, le
>   PDF, ou le FEC exporté ? Essaie `<script>`, une apostrophe, un
>   saut de ligne, un séparateur de colonne FEC, un `&`.
> - **Les chemins de fichier** construits depuis une entrée utilisateur :
>   nom d'archive, slug de dossier, jeton d'import. Une traversée est-elle
>   possible ?
> - **Le bac à sable** peut-il écrire dans le dossier réel, ou l'inverse ?
>   Par quel chemin — cookie forgé, session expirée en cours d'opération,
>   répertoire partagé ?
> - **Ce qui sort de la machine** : le logiciel fait-il une requête réseau
>   quelque part ? Un journal, une télémétrie, une vérification de version ?
>
> Ne cherche pas à durcir au-delà de l'usage : c'est un outil local
> mono-utilisateur, pas un service exposé. Une recommandation
> disproportionnée sera écartée, et celles qui comptent avec elle.

---

## 15. Passe S — Résultat fiscal, retraitements et articulation déclarative

**Pièces à joindre** : `modules/liasse.py`, `modules/fiscal.py`,
`modules/liasse_pdf.py`, `modules/gabarits.py`, et le CERFA 2033 de l'année
concernée (le formulaire officiel, pas un exemple).

> Périmètre : le passage du résultat COMPTABLE au résultat FISCAL, et le
> report de ce résultat sur les déclarations. C'est le dernier maillon : une
> erreur ici se recopie telle quelle sur une déclaration réelle.
>
> Ce que je veux savoir :
>
> - **Chaque retraitement est-il justifié et complet ?** Le fonds travaux
>   ALUR est comptabilisé en charge puis réintégré (provision non
>   déductible) : la réintégration porte-t-elle sur le bon montant, le bon
>   exercice, et une seule fois ? Y a-t-il d'autres charges non déductibles
>   que le logiciel laisse passer — amendes, quote-part personnelle d'un bien
>   à usage mixte, dépense immobilisable passée en charge ?
> - **L'articulation des lignes de la liasse** : la case de résultat fiscal
>   est ramenée à zéro parce que le résultat LMNP est déclaré ailleurs
>   (2031 bis). Cette convention est-elle appliquée de façon cohérente, et le
>   document dit-il clairement au déclarant ce qu'il doit reporter et où ?
> - **La cohérence des trois tableaux** : le bilan, le compte de résultat et
>   le tableau des immobilisations racontent-ils la même chose ? Recoupe le
>   total des amortissements du 2033-C avec la ligne correspondante du bilan,
>   et le résultat du 2033-B avec celui du bilan. Un écart d'un centime est
>   un défaut, pas un arrondi.
> - **Deux chemins, un résultat** : le logiciel calcule le résultat à plus
>   d'un endroit. Recoupe-les systématiquement sur un même dossier. Un écart
>   entre deux calculs de la même grandeur a déjà été trouvé, valant le
>   montant entier d'une dotation.
> - **Chaque case imprimée porte-t-elle le bon numéro ?** Vérifie-les **une
>   par une** contre le CERFA de l'année, sans exception — libellé officiel
>   compris. Et signale toute case que le logiciel CALCULE sans l'imprimer :
>   ce cas s'est produit deux fois.
> - **L'aide au report** vers la déclaration de revenus : les cases citées
>   existent-elles, et correspondent-elles au régime — location meublée non
>   professionnelle, déficits antérieurs, revenus non soumis aux
>   prélèvements sociaux ?
> - **Les cas limites** : résultat nul, déficit, exercice sans recette,
>   exercice de cession, premier exercice.
>
> Pour cette passe, **ne fais confiance à aucun numéro de case que tu ne peux
> pas lire sur le formulaire joint**. Si une case n'est pas vérifiable, dis-le
> plutôt que de la valider : c'est le seul domaine où une erreur se transmet
> directement à l'administration.

---

## 16. Après la passe : ce qu'il faut en faire

Ce que les passes E et F ont appris sur le traitement d'un rapport, et qui
vaut consigne :

1. **Reproduire chaque constat avant de corriger.** Sur vingt-deux constats,
   trois étaient déjà réglés, mal diagnostiqués ou sans la conséquence
   annoncée. Corriger sur la foi du rapport, c'est modifier du code sain.
2. **Un test de non-régression par constat**, dans un fichier dédié à la
   passe, citant le scénario du rapport. C'est ce qui empêche le défaut de
   revenir à la refonte suivante.
3. **Vérifier par exécution ce qui peut l'être.** Un test qui relit le code
   confirme l'intention, pas le résultat.
4. **Sortir du cadre une fois.** Compter les lignes en base après un échec.
   Décompresser le paquet ailleurs et le démarrer. Cloner le dépôt et lancer
   la suite sans le dossier privé.
5. **Consigner ce qu'on ne corrige pas**, et pourquoi : choix assumé, limite
   non déterminable, décision reportée. Un constat clos sans explication
   revient à la passe suivante.
6. **Ne jamais laisser un correctif sans son commentaire du pourquoi.** Les
   correctifs les mieux tenus de ce logiciel sont ceux qui portent, en
   commentaire, le défaut qu'ils empêchent — c'est ce qui a évité plusieurs
   régressions.
