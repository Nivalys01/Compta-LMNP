# Journal des versions — Compta LMNP

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
- **Reprise d'un exercice inaccessible** (Nadia, migrante les acteurs payants actuels) :
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
  future migration depuis un autre outil (les acteurs payants actuels…).
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
