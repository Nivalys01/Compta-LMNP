# Audit — passe M : le moteur de contrôles et son propre auditeur

Date : **15 septembre 2026**. Version examinée : `compta_lmnp/`.

**27 contrôles sur 27 déclenchés par exécution ; 14 constats, dont 7 majeurs et 7 mineurs.** Aucun contrôle entièrement inatteignable n'a été trouvé. En revanche, un contrôle atteignable peut manquer le cas qui importe : compte d'attente importé, flux qui se compensent, échec de calcul caché. Le PDF ne transporte pas les anomalies du moteur. L'audit de cycle détecte les mutations de dotation et de plafond, mais approuve une péremption des déficits volontairement cassée.

## Périmètre et méthode

Les cinq pièces demandées ont été examinées : `modules/controles.py`, `audit_cycle.py`, `gabarits.py`, `fiscal.py`, `parametres.py`. Les dépendances et les consommateurs sont également présents dans le dépôt : notamment `operations.py`, `amortissement.py`, `ecritures.py`, `reprise.py`, `rejeu_fec.py`, `export_fec.py`, `liasse.py`, `liasse_pdf.py`, `app.py` et `cli.py`. Les chemins de source cités ci-dessous sont relatifs au répertoire de version indiqué en tête. Les numéros sont ceux des fichiers exécutés.

Lecture préalable des invariants, du programme M, du CHANGELOG, de la synthèse E/F et du suivi D2, ainsi que des récapitulatifs G à L et Q. Les anciens documents supprimés dans l'arbre de travail ont été consultés dans Git, sans restaurer ces suppressions. Les correctifs E/F/D2 ne sont pas redéclarés défectueux. Les recoupements avec H, I et J sont indiqués à la fin.

Les bases sont **blanches, temporaires, intégralement fictives**. Aucun fichier de référence privé, seed d'identité ou base réelle n'a été utilisé. Les valeurs de scénario ne proviennent pas de ces pièces privées. Le code de production n'a pas été modifié.

Pièces de preuve :

- [Script reproductible](preuves_m/reproduire.py), comprenant les 27 témoins, les cas limites, les mutations et les appels web/CLI.
- [Sorties d'exécution](preuves_m/resultats.json), indexées par les clés citées dans les constats.
- [Vérification des résultats](preuves_m/verifier.py), par assertions sur les sorties exécutées.
- [PDF effectivement généré](preuves_m/attente.pdf) et [texte extrait par `pdftotext`](preuves_m/attente.txt).

Commande depuis la racine :

```bash
compta_lmnp/.venv/bin/python docs/preuves_m/reproduire.py
```

Environnement exécuté : **Python 3.14.6, SQLite 3.51.2**, avec Flask et ReportLab de l’environnement local.

Les sorties « Produit » sont des extraits des retours réels, des lectures de base après exécution ou du texte extrait du PDF. Le script échoue si un des 27 témoins ne se déclenche pas. Les mutations remplacent temporairement une fonction en mémoire et sont retirées après chaque essai. Elles éprouvent **la capacité de l'auditeur à détecter une régression**, et ne prétendent pas que la fonction de production a déjà cette régression.

Les tests web exécutent la véritable fonction de route dans un contexte Flask de requête ; seules la connexion et la sélection du bac à sable sont isolées. Ils ne constituent pas une interaction de navigateur. La CLI est lancée dans de vrais sous-processus, avec `COMPTA_DB` pointant explicitement sur les bases fictives. Les montants d'écart sont comptables ou déclaratifs, **pas des calculs d'impôt personnel**. Les conventions comptables exclues par la demande ne sont pas des constats.

## Constats

### M-01 — Le compte d'attente à sept chiffres traverse le contrôle et la clôture

**Gravité : majeur.**

**Fichier et fonction :** `modules/controles.py`, `c_compte_attente`, **158**, filtre exact à **165**. Consommateur exécuté : `app.py`, `cloturer`, **1219**.

**Scénario :** créer un FEC fictif avec débit `4720000` **800 €**, crédit `108000` **800 €**. L'exporter, le rejouer dans une autre base blanche, exécuter les contrôles puis la route de clôture sans `forcer`.

**Attendu :** import conservant la subdivision et blocage du solde d'attente non apuré, comme pour `472000`.

**Produit — `attente_sept_chiffres`, `web_attentes_non_detectees.sept_chiffres` :**

```text
rejeu : ecritures=1 ; comptes_crees=["4720000"]
solde=800.0 ; anomalies=[]
route sans Forcer : statut=clos ; Résultat fiscal : 0.00 €
```

**Conséquence :** **800 € non classés** peuvent être figés sans aucun signal du moteur. Leur traitement fiscal final reste inconnu tant qu'ils ne sont pas identifiés : il serait incorrect de transformer automatiquement ces 800 € en une déduction manquante. Le défaut est le passage de cette incertitude malgré le contrat de blocage. L'import lui-même conserve bien le montant.

### M-02 — Deux flux d'attente se compensent sans avoir été reclassés

**Gravité : majeur.**

**Fichiers et fonctions :** `modules/controles.py`, `c_compte_attente`, **158**, somme algébrique à **162** ; `c_autres_a_requalifier`, **68** ; `app.py`, `cloturer`, **1219**.

**Scénario :** un loyer fictif de **800 €** et un remboursement de capital de **800 €** sont encore saisis sous `attente_encaissement` et `attente_decaissement`. Exécuter les contrôles puis la route sans Forcer. Exécuter séparément le même dossier avec les deux gabarits corrects.

**Attendu :** les deux opérations non identifiées demandent une décision avant clôture. Après identification, le loyer produit **800 €** de résultat ; le remboursement de capital ne le réduit pas.

**Produit — `attente_compensee`, `attente_compensee_reference`, `web_attentes_non_detectees.compensee` :**

```text
attente : 2 REQUALIFIER de niveau AVERTISSEMENT ; aucun BLOQUANT
route sans Forcer : statut=clos ; résultat fiscal=0.0
référence identifiée : résultat fiscal=800.0 ; revenu_imposable=800.0
```

**Conséquence :** **800 € de revenu imposable omis dans ce scénario**, parce qu'un solde nul est assimilé à une attente apurée. Ce n'est pas le défaut E-06 corrigé : les flux vont bien en attente, mais le contrôle ne protège pas leur compensation accidentelle. Un apurement par reclassement doit être distingué de deux opérations encore typées « à identifier ».

### M-03 — Le PDF imprime cinq validations internes et omet le BLOQUANT du moteur

**Gravité : majeur.**

**Fichiers et fonctions :** `modules/liasse.py`, `generer`, **588**, liste distincte à **600** ; `modules/liasse_pdf.py`, `generer_pdf`, **146**, rendu de cette seule liste à **431–448** ; `modules/controles.py`, `controler`, **785**.

**Scénario :** saisir un décaissement à identifier de **800 €** sur `472000`, générer la liasse provisoire et son PDF, puis extraire le texte.

**Attendu :** le destinataire du document retrouve l'anomalie bloquante et sa conséquence pour la préparation de la déclaration.

**Produit — `pdf_attente` et PDF joint :**

```text
moteur : COMPTE_ATTENTE=BLOQUANT ; REQUALIFIER=AVERTISSEMENT
liasse : conforme=true ; cinq contrôles internes à ok=true
PDF : COMPTE_ATTENTE_imprime=false ; non_solde_imprime=false
```

**Conséquence :** le document transmis ne révèle pas les **800 € en attente**. Il conserve bien son caractère provisoire ; ce filigrane ne restitue cependant ni l'anomalie ni son montant. Le problème n'est pas une ligne coupée à l'impression : **les deux ensembles de contrôles ne sont pas reliés**. L'affirmation initiale selon laquelle le rapport des 27 contrôles serait déjà imprimé est donc contredite par l'exécution.

### M-04 — Les avertissements de reprise permettent de figer un bilan effectivement faux

**Gravité : majeur.**

**Fichier et fonctions :** `modules/controles.py`, `c_an_absents`, **508**, niveau à **518** ; `c_amortissements_anterieurs`, **630**, niveau à **651** ; `bloquants`, **813**. Clôture exécutée : `modules/fiscal.py`, `cloturer`, **471**.

**Scénario A :** mobilier de **12 000 €** acquis au 1er janvier 2025, amorti sur dix ans, recettes **2 400 €** par an. Clôturer 2025, ouvrir 2026 sans reprise, puis contrôler et clôturer. Comparer à un second cycle avec reprise.

**Attendu :** blocage de la reprise manquante avant que le bilan de 2026 soit figé ; actif net **9 600 €** après reprise et dotation correcte.

**Produit — `an_absents_bilan` :**

```text
sans AN : AN_ABSENTS=AVERTISSEMENT ; clôture réussie
          brut=0.0 ; amortissements=1200.0 ; actif net=-1200.0
avec AN : brut=12000.0 ; amortissements=2400.0 ; actif net=9600.0
```

**Scénario B :** reprendre en 2026 ce mobilier mis en service en 2025, avec son acquisition brute mais sans les **1 200 €** d'amortissements antérieurs. Saisir 2 400 € de recettes puis clôturer.

**Produit — `amort_anterieurs_cloture` :**

```text
AMORT_ANTERIEURS=AVERTISSEMENT ; montant signalé=1200.00 €
clôture réussie ; actif net=10800.0
```

**Conséquence :** dans A, actif net minoré de **10 800 €** ; dans B, surévalué de **1 200 €** par rapport aux **9 600 €** attendus. Le bénéfice courant reste **1 200 €** dans ces essais : aucun écart d'impôt n'est imputé à ces erreurs de bilan. La liasse de A porte ensuite `conforme=false` : cette détection existe, mais intervient après une clôture autorisée. Le classement en simple avertissement ne correspond pas à ces erreurs déterminées. Cela n'impose pas de bloquer aveuglément un exercice antérieur dont tous les soldes à reprendre seraient nuls.

### M-05 — Une impossibilité de calcul peut devenir « aucune anomalie »

**Gravité : majeur.**

**Fichier et fonctions :** `modules/controles.py`, `c_amortissements_anterieurs`, **630**, exception avalée à **644–647** ; `c_duree_allongee`, **185**, abandon sur erreur de plan à **231–234** ; `c_deficit_menace_par_le_39c`, **299**, repli à zéro à **337–342** ; `rapport`, **796**.

**Scénario A :** composant fictif de **12 000 €**, dix ans, mise en service en 2025, contrôlé en 2026. Avec une date correcte, le moteur signale **1 200 €** de cumul absent. Injecter une erreur de lecture dans le lecteur de cumul : exécuter à nouveau tout le moteur.

**Scénario B :** dans une autre base, créer par SQL ce composant avec la date impossible `2025-02-30`, puis appeler le rapport normal. C'est une injection de donnée incohérente, pas une preuve que le formulaire courant accepte cette date.

**Attendu :** annoncer qu'un contrôle n'a pas pu être effectué, au lieu de valider implicitement son objet.

**Produit — `amort_avant_panne`, `amort_panne`, `rapport_date_composant_invalide` :**

```text
avant panne : AMORT_ANTERIEURS ; 1200.00 €
après panne injectée : anomalies=[]
avec date impossible : Contrôles 2026 : aucune anomalie. ✓
```

**Autre exécution — `deficit_avant_panne`, `deficit_panne` :** stock 39 C de **1 000 €**, déficit de **1 200 €** expirant en 2028, recettes 2026 de **2 400 €**. Le contrôle émet l'alerte de concurrence des reports. Faire échouer sa simulation produit `[]`, sans diagnostic d'indisponibilité.

**Conséquence :** le déclarant reçoit une assurance positive alors que le cumul d'un actif de **12 000 €**, ou la concurrence de reports de **1 000/1 200 €**, n'a pas été contrôlé. Aucun calcul de déclaration réussi avec la date impossible n'est allégué. Une autre panne, injectée dans le plan lorsque `DOTATION_PLAN` doit le lire, **remonte effectivement** : le silence n'est pas universel, il dépend du contrôle.

### M-06 — L'audit de cycle approuve des régressions qu'il annonce vérifier

**Gravité : majeur.**

**Fichier et fonctions :** `modules/audit_cycle.py`, `phase_3_fiscal`, **318**, contrôle à condition constante `True` à **343–344** ; `phase_2_detection`, **228**, vérification du code de date à **296–297**, nettoyage avant clôture à **309–315** ; `executer`, **474**.

**Scénario A :** remplacer temporairement le traitement des déficits par une variante qui met tous les soldes à zéro avant le traitement normal, quelle que soit leur expiration. Lancer le cycle complet. Éprouver ensuite cette même variante sur un déficit fictif de **1 200 €**, né en 2018, expiration 2028, avec résultat 2026 nul.

**Attendu :** le cycle échoue sur une péremption prématurée ; le témoin conserve **1 200 €**.

**Produit — `audit_peremption_fausse`, `temoin_peremption` :**

```text
audit muté : succes=true ; nombre=41 ; echecs=[]
stocks de déficits positifs rencontrés pendant le cycle=0
témoin : solde avant=1200 ; solde après=0.0
```

Le cycle annoncé comme exerçant les déficits et leur FIFO n'offre aucun stock positif à cette mutation. Son contrôle « Files 39 C et déficits LMNP jamais cumulées » réussit en outre inconditionnellement ; ce libellé n'est pas repris ici comme une règle fiscale.

**Scénario B :** remplacer seulement le niveau de `DATE_HORS_EXERCICE` par `AVERTISSEMENT`, puis relancer. Autre essai : retirer seulement le contrôle du compte d'attente de `CONTROLES`.

**Produit — `audit_date_degradee`, `audit_sans_compte_attente` :** dans les deux cas, **41/41, `succes=true`**. Le cycle recherche le code de date sans exiger son niveau. Il efface ses anomalies avant de tenter la clôture : il ne prouve pas le refus annoncé. Le compte d'attente n'a pas de témoin dans ce cycle.

**Conséquence :** une régression capable de détruire **1 200 € de report** ou de retirer un verrou de clôture peut être couverte par un verdict « conforme ». Cela ne signifie pas que l'audit passe quoi qu'on fasse : suppression des dotations **détectée, 7 échecs** ; plafond augmenté de **1 000 € détecté, 3 échecs**. La couverture est réelle, mais plus étroite que son annonce.

### M-07 — L'API fiscale clôture avec un BLOQUANT sans option de forçage

**Gravité : majeur.**

**Fichier et fonction :** `modules/fiscal.py`, `cloturer`, **471**, puis génération et calcul à **515–523**. Contrôle de référence : `modules/controles.py`, `bloquants`, **813**.

**Scénario :** saisir **800 €** en `attente_decaissement`, constater le BLOQUANT puis appeler directement `fiscal.cloturer(conn, 2026)`, sans argument de dérogation.

**Attendu :** si le blocage est une garantie de clôture du logiciel, le point d'entrée métier refuse ou exige une dérogation explicite.

**Produit — `api_sans_forcer` :**

```text
avant : COMPTE_ATTENTE=BLOQUANT
appel sans option de forçage : résultat fiscal=0.0 ; statut=clos
```

**Conséquence :** **800 € non identifiés sont figés** par un appel métier ordinaire. Le forçage n'est donc pas l'unique contournement à l'échelle du code distribué. **Limite du constat :** les interfaces web et CLI vérifient bien ce BLOQUANT avant cet appel ; cet essai ne démontre pas un contournement HTTP caché. La protection repose sur la discipline de chaque appelant, et non sur l'API qui réalise la mutation irréversible.

### M-08 — La CLI annonce un refus de clôture mais retourne un succès système

**Gravité : mineur.**

**Fichier et fonction :** `cli.py`, `cmd_cloturer`, **132**, refus suivi d'un `return` à **148–152**.

**Scénario :** base fictive contenant **800 €** en attente ; lancer dans un sous-processus `cloturer --annee 2026` sans `--forcer`, puis consulter le statut et le code retour.

**Attendu :** exercice ouvert et code de sortie non nul pour une commande de clôture refusée.

**Produit — `cli.False` :**

```text
sortie : Clôture refusée (anomalies bloquantes).
statut=ouvert ; code_retour=0
```

**Conséquence :** un script appelant peut poursuivre comme si la clôture avait réussi. **Pas de clôture erronée ni de perte comptable dans cet essai** ; le texte destiné à l'humain est correct. Ce constat vise la commande de clôture, distincte du validateur autonome déjà examiné en G-14.

### M-09 — Le contrôle de seuil assimile un emprunt reçu et un loyer annulé à des recettes

**Gravité : mineur.**

**Fichier et fonction :** `modules/controles.py`, `c_seuil_lmp`, **549**, sélection par nature à **554**, somme sans exclusion des annulations à **557–559**. Catalogue concerné : `modules/gabarits.py`, consommé par `tous`, **253**.

**Scénario A :** enregistrer uniquement `emprunt_recu=100000`. **Scénario B indépendant :** enregistrer un loyer de **24 000 €**, puis l'annuler par l'API prévue. Seuil configuré : **23 000 €**.

**Attendu :** zéro recette locative conservée dans ces deux scénarios, donc pas d'alerte de dépassement fondée sur ces mouvements.

**Produit — `seuil_emprunt`, `seuil_annule` :**

```text
A : agrégats.produits=0 ; SEUIL_LMP : Recettes 100000.00 € > seuil LMP 23000 €
B : agrégats.produits=0 ; SEUIL_LMP : Recettes 24000.00 € > seuil LMP 23000 €
```

**Conséquence :** alerte de statut sur **100 000 €** ou **24 000 € de recettes fictives**. Les agrégats restent corrects et le contrôle ne change pas automatiquement le régime : aucun supplément d'impôt n'est démontré. `nature='produit'` décrit ici aussi le sens d'un flux de bilan, pas seulement un produit comptable. Le faux négatif sur FEC sans opérations est déjà J-04 ; il n'est pas renuméroté.

### M-10 — Des alertes continuent de viser des opérations correctement annulées

**Gravité : mineur.**

**Fichier et fonctions :** `modules/controles.py`, `c_depense_immobilisable`, **85** ; `c_annuel_multiple`, **478** ; `c_loyer_atypique`, **458**, deuxième requête à **469**.

**Scénario :** annuler par l'API un petit équipement de **780 €**, annuler puis ressaisir une CFE de **300 €**, enfin annuler un loyer saisi à **80 €** et le remplacer par **800 €**. Trois autres loyers de 800 € établissent la référence annuelle.

**Attendu :** aucune alerte de dépense immobilisable sur l'équipement annulé, pas de double CFE active, pas d'erreur de montant sur le loyer corrigé.

**Produit — `annulations` :**

```text
IMMOBILISABLE : 780.00 € > seuil 500 €
ANNUEL_MULTIPLE : 'cfe' saisi 2 fois
LOYER_ATYPIQUE : 80.00 € vs médiane annuelle 800.00 €
agrégats : produits=3200.0 ; charges_hors_daa=300.0
```

**Conséquence :** les alertes ne disparaissent pas après correction, ce qui encourage à ignorer les suivantes. **Les montants comptables sont justes** dans l'essai. Pour les loyers, la médiane exclut les annulations, mais la requête qui cherche les écarts les réintroduit. Il ne suffit donc pas de vérifier la première requête.

### M-11 — Les contrôles de loyers confondent calendrier complet et activité réelle

**Gravité : mineur.**

**Fichier et fonctions :** `modules/controles.py`, `c_doublons`, **56** ; `c_completude_loyers`, **107** ; `c_loyer_atypique`, **458**.

**Scénario A :** deux biens et deux locataires fictifs distincts, chacun un loyer de **800 €** en janvier 2026. **Scénario B indépendant :** bien acquis le **1er novembre 2026**, exercice ouvert du 1er novembre au 31 décembre, loyers de **800 €** en novembre et décembre.

**Attendu :** pas de soupçon de doublon fondé uniquement sur le montant de deux locations distinctes ; pas de mois manquants antérieurs aux bornes de l'exercice.

**Produit — `deux_locataires`, `acquisition_novembre` :**

```text
A : DOUBLON — 2× 'loyer' pour 2026-01 à 800.00 €
B : LOYER_MANQUANT — 10 mois : 2026-01 à 2026-10
```

`DOUBLON` groupe type, période et montant arrondi, sans bien ni tiers. `LOYER_MANQUANT` attend toujours les douze mois.

**Autre limite exécutée — `loyers_deux_tarifs` :** trois loyers de **800 €** puis trois de **1 600 €** donnent une référence de **1 600 €** et trois alertes sur les 800 €. Il s'agit de l'élément central supérieur de la liste triée, pas de la médiane arithmétique des deux valeurs centrales pour un effectif pair, ni d'un historique par logement. Un changement de prix documenté reste une explication légitime, comme le message le reconnaît.

**Conséquence :** bruit de contrôle sur des recettes correctes ; aucun loyer supprimé automatiquement. Le montant de **800 €** ne serait perdu qu'en annulant à tort une opération légitime : cette annulation n'a pas été faite dans l'essai.

### M-12 — Un gabarit personnalisé de loyer sort des contrôles de complétude et d'écart

**Gravité : mineur.**

**Fichiers et fonctions :** `modules/gabarits.py`, `ajouter_personnalise`, **213** ; `modules/controles.py`, `c_completude_loyers`, **107**, filtre à **110** ; `c_loyer_atypique`, **458**, filtres à **461 et 471**.

**Scénario :** créer par l'API le gabarit `loyer_fictif`, compte `708810`, nature `produit`, périodicité `mensuel`. Saisir **800, 800 et 80 €** en janvier, février et mars 2026. Le comparer au témoin utilisant le gabarit standard `loyer`.

**Attendu :** mêmes contrôles pour ces loyers, ou une indication explicite que le nouveau gabarit n'entre pas dans leur couverture.

**Produit — `loyer_personnalise` et témoins `couverture` :**

```text
gabarit personnalisé : produits=1680.0 ; manquants=[] ; atypique=[]
gabarit standard : LOYER_MANQUANT et LOYER_ATYPIQUE se déclenchent
```

**Conséquence :** l'erreur de **720 €** sur le troisième loyer n'est plus signalée par le contrôle dédié, alors que les recettes sont bien comptabilisées. Le nom écrit en dur réduit la couverture sans l'annoncer. La périodicité seule ne suffit pas à distinguer loyer et provision pour charges : une qualification explicite est nécessaire. À l'inverse, la taxe personnalisée annuelle est bien contrôlée, et un nouveau gabarit du catalogue portant `requalifier=True` est détecté ; toutes les extensions ne sont pas aveugles.

### M-13 — Un seuil non fini accepté rend deux contrôles muets

**Gravité : mineur.**

**Fichiers et fonctions :** `modules/parametres.py`, `definir`, **146**, conversion et enregistrement à **173** ; `valeur`, **126** ; `modules/controles.py`, `c_depense_immobilisable`, **85** ; `c_seuil_lmp`, **549**.

**Scénario :** équipement de **780 €**, loyer de **24 000 €**. Vérifier les alertes avec les seuils livrés. Enregistrer ensuite par `definir` la valeur `float('inf')` pour les deux seuils à effet du 1er janvier 2026. C'est aussi la valeur obtenue par `float('1e309')` ; le formulaire de réglementation n'est pas invoqué dans ce scénario.

**Attendu :** rejet d'un seuil non fini, ou diagnostic de paramétrage invalide.

**Produit — `regles_supprimees`, `seuils_infinis`, `seuil_conversion_1e309` :**

```text
avec valeurs livrées : IMMOBILISABLE et SEUIL_LMP
conversion 1e309 : inf
après définition : immo=[] ; lmp=[]
```

**Conséquence :** les deux alertes deviennent impossibles à déclencher pour un montant fini. Aucun changement automatique de calcul fiscal n'est attribué à ces seuils ; la perte mesurée est celle des alertes sur **780/24 000 €**. Ce défaut ne doit pas être confondu avec une règle absente : les valeurs de repli **500/23 000** fonctionnent dans les essais de table vide et de millésime non couvert.

### M-14 — Un exercice inexistant reçoit un rapport positif

**Gravité : mineur.**

**Fichier et fonctions :** `modules/controles.py`, `controler`, **785** ; `rapport`, **796**, verdict positif à **800** ; `c_dates_hors_exercice`, **143**, retour vide à **149**.

**Scénario :** base blanche avec le seul exercice 2026 ; demander `rapport(conn, 2099)`.

**Attendu :** « exercice inexistant » ou contrôle non effectué.

**Produit — `exercice_inexistant` :**

```text
Contrôles 2099 : aucune anomalie. ✓
```

**Conséquence :** le rapport prétend avoir contrôlé un exercice absent. Aucune perte en euros mesurée. Le refus d'un exercice inexistant par la clôture fiscale ne transforme pas ce verdict de contrôle en résultat valide.

## Ce qui a été vérifié et tenu

### Les 27 déclenchements, chacun par exécution

Chaque ligne ci-dessous provient d'une base indépendante passée par `controler`, et non d'un appel factice retournant une anomalie préparée. Les composants des témoins valent **12 000 €**, sur dix ans à partir du 1er janvier 2026, sauf indication contraire. Les scénarios incohérents utilisent explicitement une injection SQL ou une option de test ; ils n'impliquent pas que la saisie normale accepte l'incohérence. Les messages complets sont dans `resultats.json`, clé `couverture`.

Tous les fichiers de cette table sont `modules/controles.py`.

| Code déclenché | Fonction : ligne | Témoin concret | Sortie observée |
|---|---|---|---|
| EQUILIBRE | `c_equilibre_ecritures` : 41 | Débit 100 €, crédit 99 €, injection autorisée | BLOQUANT, 100 ≠ 99 |
| DATE_HORS_EXERCICE | `c_dates_hors_exercice` : 143 | Écriture 2026 datée du 01/01/2027, injection | BLOQUANT |
| COMPTE_ATTENTE | `c_compte_attente` : 158 | Décaissement non identifié 0,01 € | BLOQUANT, 0,01 € |
| MONTANT_INVALIDE | `c_montants_invalides` : 173 | Opération SQL à 0 € | BLOQUANT |
| DOUBLON | `c_doublons` : 56 | Deux loyers de 800 €, même janvier | AVERTISSEMENT, 2×800 € |
| REQUALIFIER | `c_autres_a_requalifier` : 68 | Autres charges 120 € | AVERTISSEMENT |
| IMMOBILISABLE | `c_depense_immobilisable` : 85 | Petit équipement 780 €, seuil 500 € | AVERTISSEMENT |
| LOYER_MANQUANT | `c_completude_loyers` : 107 | Seul janvier saisi, 800 € | AVERTISSEMENT, 11 mois |
| SENS | `c_sens_comptable` : 122 | Charge 614100 créditée de 50 € en BQ | AVERTISSEMENT |
| ANNUEL_MULTIPLE | `c_annuel_multiple` : 478 | CFE 300 € puis 301 € | AVERTISSEMENT |
| PERIODE_INCOHERENTE | `c_periode_incoherente` : 496 | Date janvier 2026, période décembre 2025 | AVERTISSEMENT |
| INTERETS_MAL_CLASSES | `c_interets_mal_classes` : 568 | Frais bancaires 100 €, libellé « Intérêts emprunt fictif » | AVERTISSEMENT |
| PLAUSIBILITE_N1 | `c_plausibilite_n1` : 419 | 2025 clos : 800 € ; 2026 : trois loyers de 800 € | AVERTISSEMENT, 2 400 contre 800 € |
| POSTE_HABITUEL_ABSENT | `c_postes_habituels_absents` : 367 | Trois loyers de 800 €, aucune charge | INFO, cinq postes |
| DEFICIT_MENACE_PAR_39C | `c_deficit_menace_par_le_39c` : 299 | Stock 39 C 1 000 €, déficit 1 200 € expirant en 2028, loyer 2 400 €, dotation prévue 1 200 € | AVERTISSEMENT avant clôture |
| RETRAITEMENT_MANUEL_PLAFOND | `c_retraitement_manuel_majore_le_plafond` : 254 | Clôture avec retraitement manuel de 1 000 € | AVERTISSEMENT, 1 000 € |
| DUREE_ALLONGEE | `c_duree_allongee` : 185 | Mise en service 2025, cumul clos 2 400 €, plan actuel 1 200 €/an | AVERTISSEMENT, écart +1 200 € |
| LOYER_ATYPIQUE | `c_loyer_atypique` : 458 | Loyers 800, 800, 80 € | AVERTISSEMENT, 80 contre 800 € |
| AN_ABSENTS | `c_an_absents` : 508 | 2025 clos, aucun AN en 2026 | AVERTISSEMENT |
| DOTATION_PLAN | `c_dotation_vs_plan` : 524 | Dotation comptabilisée 1 500 €, plan 1 200 € | AVERTISSEMENT |
| AMORT_ANTERIEURS | `c_amortissements_anterieurs` : 630 | Mise en service 2025, aucun cumul repris en 2026 | AVERTISSEMENT, 1 200 € |
| COMPOSANT_SANS_AMORT | `c_composant_non_amortissable` : 703 | Amortissable=1, compte d'amortissement NULL | BLOQUANT |
| VENTILATION_INCOMPLETE | `c_ventilation_incoherente` : 662 | Prix 12 000 €, composant 6 000 € | AVERTISSEMENT, manque 6 000 € |
| TEOM_ABSENTE | `c_teom_oubliee` : 725 | Taxe foncière 900 €, aucune TEOM | INFO |
| SEUIL_LMP | `c_seuil_lmp` : 549 | Loyer 24 000 €, seuil 23 000 € | AVERTISSEMENT |
| CHARGE_ATTENDUE | `c_charges_attendues` : 589 | Six loyers de 800 €, aucune charge | INFO, trois rappels |
| ALUR_ABSENT | `c_alur_absent` : 613 | ALUR 2025 : 100 € ; copropriété 2026 : 600 €, aucun ALUR | INFO |

L'inventaire des fonctions `c_*` est comparé à `CONTROLES` : **aucune fonction existante oubliée dans la liste**. Cette vérification externe couvre l'état présent ; elle ne fait pas de la liste manuelle une protection automatique contre un futur oubli.

### Équilibre, attente et chaîne de clôture

- **Équilibre par écriture :** deux écarts opposés de **1 €**, dont l'un en journal AN, total global **0 €** : **deux BLOQUANT**. Les mêmes alertes restent présentes après passage de l'exercice au statut clos. Le groupement par numéro est cohérent avec l'unicité du numéro par exercice imposée dans cette base ; le regroupement de journaux du validateur externe décrit en G-03 n'est pas imputé à ce contrôle.
- **Écriture effectivement rejouée :** après export/rejeu fictif, altération SQL du débit de 800 à **799 €** : `EQUILIBRE` trouve **799 ≠ 800**. Le contrôle ne se limite pas aux opérations natives.
- **Centime d'attente :** **0,01 €** est bien bloquant. Aucun seuil d'un euro caché.
- **Attente historique :** après clôture 2025 contenant 800 € d'attente, ouvrir 2026 avec reprise réactive `COMPTE_ATTENTE`. Sans AN, il reste seulement `AN_ABSENTS=AVERTISSEMENT` : cette limite est rattachée à M-04, et non comptée deux fois.
- **Les cinq BLOQUANT** ont chacun été soumis séparément à la route web sans Forcer : HTTP 302 avec avertissement de refus, **exercice toujours ouvert**. Pour le témoin d'attente de 800 €, web et CLI laissent l'exercice ouvert sans forçage et le clôturent avec forçage. Les deux faux négatifs d'attente M-01/M-02 ont aussi été clôturés par cette route sans Forcer.
- **Dossier ordinaire fictif :** trois acquisitions de 115 000 € au total, 12 loyers de 800 € et cinq charges totalisant 1 500 € : **0 BLOQUANT, 0 AVERTISSEMENT, 3 INFO**. Les rappels concernent intérêts et taxe foncière. Il n'est pas démontré qu'un dossier ordinaire provoque régulièrement un blocage abusif.

### Dossier neuf, vacance et contrôles heuristiques

- **Exercice existant entièrement vide :** les **27 fonctions** renvoient chacune une liste vide, et le moteur aussi. C'est approprié pour l'absence de mouvements ; cela ne prouve pas qu'une activité réelle n'aurait rien omis.
- **Maison vacante toute l'année, achat comptant :** trois primes fictives de 100 €, aucun loyer : **aucun BLOQUANT, aucun LOYER_MANQUANT, aucun CHARGE_ATTENDUE**. Quatre INFO de postes habituels subsistent. Le rappel de copropriété est conditionnel ; celui des intérêts invite à ignorer un achat comptant. Ils ne sont donc pas qualifiés à tort de blocages.
- **Acquisition en novembre :** pas de rappel `CHARGE_ATTENDUE` avec seulement deux loyers ; pas de `POSTE_HABITUEL_ABSENT` sous trois opérations. L'alerte erronée sur janvier à octobre est M-11.
- **Premier exercice :** `PLAUSIBILITE_N1` reste muet sans précédent clos. `TEOM_ABSENTE` ne part que si une taxe foncière est saisie ; elle reste un rappel de vérification, pas une création de charge.
- **Absence d'historique de loyers :** un seul loyer ne déclenche pas `LOYER_ATYPIQUE`. Trois loyers dans l'année courante suffisent : aucune année antérieure n'est nécessaire.
- **SENS n'est pas mort :** la charge créditrice de 50 € en BQ est détectée indépendamment de l'import bancaire. La restitution native de charges de **100 €** émet aussi « produit 708810 au débit — annulation ? ». Ce mouvement est légitime ; le message appelle une justification, et ne bloque pas. Ce contrôle ne doit pas être présenté comme une preuve automatique de mauvaise nature. Sa couverture est limitée au journal BQ.

### Tables, paramètres et extensions

- Sur une base blanche, les absences initiales des tables paresseuses ne font pas tomber le moteur. Les tables de gabarits et de règles sont créées ; aucune clôture fiscale préalable n'est nécessaire pour les contrôles ordinaires.
- **Déficit menacé sur exercice ouvert :** le témoin déclenche l'alerte à partir de la simulation et du stock antérieur ; il ne requiert pas une ligne de suivi courant déjà clôturée. Le correctif de ce chemin tient.
- **Règles supprimées :** après suppression des lignes de `regle_fiscale`, les seuils livrés sont recréés. **Versions hors millésime :** les replis 500 et 23 000 conservent les deux alertes sur 780/24 000 €. Pas de silence constaté pour ces absences-là. Cela ne certifie pas la pertinence réglementaire de valeurs de repli pour tous les millésimes possibles.
- **Drapeaux et périodicité :** une catégorie de catalogue fictive portant `requalifier=True` déclenche `REQUALIFIER` sans ajout de nom dans le contrôle. Une taxe personnalisée annuelle de 100 puis 101 € déclenche `ANNUEL_MULTIPLE`. Les comptes utilisés par les 27 témoins existent bien ou ont été explicitement créés par le rejeu.

### Diagnostics déjà couverts, non renumérotés

- **H-01** couvre l'abandon du cumul lorsque plusieurs composants partagent un compte ; **H-03** couvre le débit brut de `DOTATION_PLAN` ignorant la contre-passation ; **H-04** couvre l'omission totale de dotation ; **H-08** couvre la ventilation entièrement absente. Ces limites ne deviennent pas quatre nouveaux constats M.
- **I-10** couvre l'avertissement de retraitement manuel disponible seulement après clôture : le témoin des 27 confirme son déclenchement **après** la clôture, sans prétendre le rendre préventif.
- **J-04** couvre le silence du seuil LMP sur un FEC rejoué sans table d'opérations alimentée. M-09 vise ses faux positifs différents, sur des saisies natives.
- Les exclusions voulues du modèle comptable et la ligne 352 à zéro restent hors constats. M-03 examine la transmission des anomalies, pas ces conventions.

## Non vérifiable avec les pièces fournies

- Quelle fréquence ces alertes ont-elles dans les dossiers réels des utilisateurs, notamment ceux comportant plusieurs biens, locations saisonnières ou changements d'occupant ? Les données privées n'ont pas été consultées ; le décompte « dossier ordinaire » porte sur le scénario fictif exécuté.
- Quels anciens imports ou anciennes interfaces peuvent produire la date de composant incohérente injectée dans M-05 ? La réaction du moteur est établie, pas chacun des chemins historiques d'introduction de cette donnée.
- Quelle qualification métier explicite doit distinguer un loyer personnalisé, une provision et un autre produit mensuel, pour étendre les contrôles sans créer de faux positifs ? La périodicité du catalogue ne résout pas seule cette question.
- Quelles règles de justification doivent autoriser une dérogation sur une reprise réellement non nécessaire, un cumul antérieur différent du plan ou une dotation importée particulière ? Les témoins chiffrés établissent les erreurs de bilan ; ils ne suffisent pas à imposer un blocage universel de toute divergence théorique.
- Les autres versions de Python, SQLite et les parcours complets dans un navigateur reproduisent-ils exactement les résultats obtenus ici dans les contextes Flask et sous-processus locaux ?
- Les constats D-10 à D-29, signalés comme perdus dans les récapitulatifs antérieurs, comportaient-ils déjà certains de ces cas ? Aucun contenu manquant n'a été reconstitué par supposition.

## Tableau récapitulatif numéroté

| N° | Constat | Conséquence établie | Gravité |
|---|---|---|---|
| M-01 | Attente à sept chiffres ignorée | 800 € non classés, clôture web sans Forcer | majeur |
| M-02 | Compensation de deux flux non identifiés | Revenu imposable 0 € au lieu de 800 € | majeur |
| M-03 | Anomalies du moteur absentes du PDF | BLOQUANT de 800 € omis ; cinq validations internes positives | majeur |
| M-04 | Reprises manquantes seulement averties | Actif net erroné de −10 800 € ou +1 200 € | majeur |
| M-05 | Échec de calcul changé en silence | Rapport positif sur un contrôle impossible | majeur |
| M-06 | Régressions non détectées par l'audit de cycle | Mutation détruisant 1 200 € de déficit ; audit 41/41 | majeur |
| M-07 | API fiscale sans garde BLOQUANT | 800 € d'attente clôturés sans dérogation explicite | majeur |
| M-08 | Refus CLI avec code retour zéro | Succès apparent pour le script appelant | mineur |
| M-09 | Seuil calculé sur dette et opération annulée | Alertes sur 100 000/24 000 € de recettes inexistantes | mineur |
| M-10 | Alertes visant des opérations annulées | Corrections sans disparition des avertissements | mineur |
| M-11 | Loyers sans contexte de bien ni bornes d'exercice | Faux doublon et dix mois manquants avant acquisition | mineur |
| M-12 | Loyers personnalisés hors couverture | Erreur de 720 € non signalée par LOYER_ATYPIQUE | mineur |
| M-13 | Seuils infinis acceptés | Deux contrôles désactivés sans diagnostic | mineur |
| M-14 | Rapport positif sur exercice inexistant | Assurance de contrôle sans exercice à examiner | mineur |

Aucun correctif de production appliqué. Les preuves constituent l'état observé avant correction.

**État du suivi :** les constats de cette passe ont été corrigés en production le 16 septembre 2026 (version 8.48.0). Les preuves de `preuves_m/` sont conservées **telles qu'observées avant correction** : elles restent la référence du défaut, pas de l'état actuel du code. La non-régression est figée par `tests/test_passe_m.py`.

Trois précisions. **M-09 était déjà corrigé** par la passe J, qui a fait porter le contrôle du seuil LMP sur les loyers acquis des écritures : il a été vérifié puis figé par deux tests, non recorrigé. **M-02 a été traité autrement que ne le suggérait une première lecture** : le mouvement du compte d'attente ne peut pas servir de signal, puisqu'un compte régulièrement apuré porte par construction l'écriture d'origine et sa reclassification — le dossier de référence en compte 287 847,78 €, tous légitimes. Le signal retenu est donc l'existence d'opérations encore typées « à identifier ». Enfin, **M-07 a un rayon d'action large** : le refus de clôturer déplacé dans l'API a obligé 59 appels de tests à déclarer `forcer=True`, ces fixtures clôturant sciemment des dossiers partiels ; c'est la contrepartie assumée d'une garantie qui ne dépend plus de la discipline de ses appelants.

Au passage, `c_ventilation_incoherente` (constat H-08) a été resserré : il ne se déclenche plus sur un `prix_total` renseigné, mais sur un actif effectivement INSCRIT AUX COMPTES qu'aucun composant n'explique. Renseigner le prix d'un bien avant d'en comptabiliser l'acquisition ne bloque donc plus la clôture.
