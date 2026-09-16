# Audit — passe T : architecture, sécurité et fiabilité transversale

**Date : 16 septembre 2026. Version : 8.52.0. Commit : `e953974cd6b161a9d055120f6b1fe5331d64f964`.**

## 1. Synthèse exécutive

**Santé globale : satisfaisante sous réserves importantes pour un usage local mono-utilisateur. Progression : amélioration**, avec une dette de concurrence et de sécurité web encore active. Cette appréciation qualitative évite un score numérique sans référentiel. Elle ne constitue ni une certification de sécurité, ni une validation du domaine métier.

Le projet possède des protections substantielles : guichet central d'écriture, transactions SQLite, validations, sauvegardes vérifiées, tests de panne, migrations versionnées et contrôles de distribution. La réduction des défauts depuis G–R est tangible. Les six corrections documentaires R-02 à R-07 sont confirmées par les tests actuels. En revanche, deux garanties annoncées après Q demeurent incomplètes sous concurrence : isolation de la migration et unicité des sauvegardes. Il s'agit de **variantes résiduelles reproduites**, pas d'un retour en arrière démontré par comparaison de commits.

Les cinq interventions prioritaires sont :

1. **T-01 — filtrer les hôtes HTTP** : un nom arbitraire et une origine identique passent la garde et permettent une mutation réelle.
2. **T-02 — corriger l'insertion JSON dans HTML** : une catégorie personnalisée injecte une balise script persistante dans la page de saisie.
3. **T-03 — bloquer les accès pendant les migrations** : une seconde requête obtient HTTP 200 pendant qu'une première migration, ensuite en échec, est suspendue.
4. **T-04 — réserver atomiquement les noms de sauvegarde** : deux appels simultanés réussissent en renvoyant le même fichier.
5. **T-05 — sérialiser les modifications du registre** : deux renommages réussissent, mais l'un est perdu.

**Bilan des constats T : 4 élevés, 4 moyens, 1 faible ; aucun critique établi.** Les risques de compromission à distance et de perte de données sont distingués des effets effectivement reproduits.

### Périmètre et méthode

Lecture des rapports G à R, de leurs suivis, du changelog, des invariants, de la configuration CI et de l'architecture ; revue ciblée des points d'entrée, modules, transactions, fichiers et rendus. Aucun rapport S n'est présent ; `gemini-code-1789578450149.md` contient la demande d'audit, pas des résultats techniques.

Les anciens scénarios métier sont évalués par leurs tests de non-régression et leurs correctifs, **sans réexpertise fiscale**. Les preuves historiques, souvent conservées avant correction, ne sont pas prises pour des sorties actuelles. Les vérifications nouvelles utilisent exclusivement des bases blanches et des données fictives temporaires. Aucun correctif de production n'est appliqué dans cette passe.

Pièces : [script reproductible](preuves_t/reproduire.py), [résultats et métriques](preuves_t/resultats.json), [résumé des vérifications](preuves_t/VERIFICATIONS.md).

```bash
.venv/bin/python docs/preuves_t/reproduire.py
.venv/bin/python -m pytest -q compta_lmnp/tests
.venv/bin/python -m ruff check compta_lmnp
```

Environnement mesuré : Python 3.14.6, SQLite 3.51.2, Flask 3.1.3. Première suite : **1 161 passed, 2 skipped, 1 failed en 38,06 s**. Le seul échec, `test_app_port_configurable`, disparaît en réexécution avec autorisation réseau locale hors du bac à sable : **1 passed en 0,53 s**. Bilan après diagnostic : 1 162 tests distincts réussis, 2 ignorés ; ce n'est pas une seconde exécution intégrale. Ruff : aucune alerte dans le jeu de règles configuré. Les 12 tests R passent également en exécution ciblée.

## 2. Matrice de suivi des audits

« Résolu » signifie que le correctif et les scénarios de non-régression actuels tiennent dans le périmètre testé, pas que toutes leurs variantes imaginables sont exclues. Les familles sont regroupées pour conserver une matrice lisible. Aucun point n'est classé « Régressé » sans preuve d'un état intermédiaire correct ensuite cassé.

| Audit / points | État actuel | Éléments de confirmation ou réserve |
|---|---|---|
| G-01 à G-15 : validation, arrondis, import/export, valeurs non finies | Résolu | Correctifs 8.42.0, `test_passe_g.py` dans la suite réussie ; refus et conservation des informations testés |
| H-01 à H-12 : bornes, cohérence et stabilité des états | Résolu | Correctifs 8.43.0 et `test_passe_h.py` ; sans requalification des conventions métier |
| I-01 à I-07, I-09 à I-13 | Résolu dans les scénarios couverts | Suivi 8.44.0 et `test_passe_i.py`, y compris les points encore actifs dans le corps historique du rapport |
| I-08 : cohérence arithmétique / attribution historique | Résolu / En souffrance pour la reconstitution historique | Sommes cohérentes ; attribution historique restant un repli documenté, aucune nouvelle preuve métier ici |
| J-01 à J-05 : instantanés et restitutions historiques | Résolu | Correctifs 8.45.0, `test_passe_j.py` ; tests d'extraction PDF disponibles dans cet environnement |
| K-01 à K-03 : ordre des clôtures et reprises | Résolu | Correctifs 8.46.0, `test_passe_k.py` |
| L-01 à L-04 : cohérence des restitutions | Résolu | Correctifs 8.47.0, `test_passe_l.py` |
| M-01 à M-14 : contrôles permissifs, refus et erreurs | Résolu | 8.48.0, `test_passe_m.py` ; `controler()` convertit un contrôle en panne en anomalie bloquante |
| N-01 à N-08 : versions, validation, commits et veille | Résolu | 8.48.0, `test_passe_n.py` ; création de gabarit respectant la transaction appelante |
| O-01 à O-10 : copies, restauration, archives et registre illisible | Résolu dans les scénarios couverts | 8.48.0, `test_passe_o.py` ; T-05 concerne une autre cause de perte du registre, sa concurrence |
| P-01 à P-07 : validation, instantanés et anonymisation | Résolu | 8.49.0, `test_passe_p.py` ; pas d'export de données réelles pour cet audit |
| Q-01 à Q-04 | Résolu | `test_passe_q.py` ; lectures et verrouillage des mutations améliorés |
| Q-05 : collision des sauvegardes | **En souffrance — correctif partiel** | Suffixe efficace en séquentiel, réservation non atomique ; reproduction T-04 |
| Q-06 à Q-09 | Résolu | Composition transactionnelle et distinction commit/nettoyage éprouvées par la suite |
| Q-10 : garde de migration | **En souffrance — correctif partiel** | Échec connu bloqué ; requête concurrente avant publication de l'échec autorisée, T-03 |
| Q-11 et Q-12 | Résolu | Ouverture transactionnelle et journal persistant ; tests Q réussis |
| R-01 : accès public à la source | **En souffrance** | Limite explicitement documentée ; accessibilité externe non revérifiée dans T, aucune clôture sur la seule forme de l'URL |
| R-02 et R-03 : inventaire des dépendances | Résolu | Notices corrigées et tests R réussis ; ne constitue pas une analyse CVE exhaustive |
| R-04 : liens du paquet | Résolu | Tests de construction et liens R réussis |
| R-05 : en-têtes | Résolu | Vérification exacte des en-têtes réussie |
| R-06 : périmètre documentaire | Résolu techniquement | Tableau présent ; questions juridiques hors périmètre |
| R-07 : copie de licence | Résolu | Empreinte et copie livrée vérifiées par les tests R |

**Trajectoire de dette :** les défauts de calcul et de transaction isolés ont été remplacés par des invariants mieux centralisés. La fragilité se déplace vers les interactions : application threadée, fichiers JSON, caches globaux et HTML/JavaScript. L'accumulation des gardes n'assure pas à elle seule leur composition. La passe R est principalement documentaire : sa comparaison directe ne mesure pas une amélioration d'architecture. La découverte de failles supplémentaires dans T n'établit donc pas une dégradation entre R et T.

## 3. Constats et recommandations détaillés

Les chemins ci-dessous sont relatifs à la racine. Les lignes désignent la version auditée.

### T-01 — L'hôte fourni par le client devient la référence de confiance

**Catégorie : sécurité / surface HTTP. Sévérité : Élevé.**

**Localisation :** `compta_lmnp/app.py:88` (configuration Flask), `:179` (`_garde_origine`), `:1707` (`dossiers_creer`).

La garde compare `Origin` au domaine de `request.base_url`, lui-même construit à partir du `Host` accepté sans restriction. L'écoute sur 127.0.0.1 limite l'interface réseau, pas les noms d'hôte associés à cette adresse.

**Scénario exécuté :** GET `/dossiers` avec `base_url=http://audit.invalid:5000`, puis POST `/dossiers/creer` avec le même hôte et `Origin: http://audit.invalid:5000`. Attendu : refus avant traitement pour un hôte non autorisé. Produit : **GET 200, POST 302, dossier effectivement créé**. Le témoin avec origine différente reçoit bien 403.

**Impact :** absence de barrière applicative contre le DNS rebinding ; un navigateur qui autorise ce chemin peut effectuer lectures et mutations sous un domaine contrôlé. Le test prouve l'acceptation serveur, **pas une attaque complète dans un navigateur**, dont les protections réseau peuvent varier. L'absence d'authentification accroît l'impact si cette frontière tombe.

**Recommandation :** limiter `TRUSTED_HOSTS` à `localhost`, `127.0.0.1` et, si supporté, `[::1]`, et refuser l'hôte invalide avant tout effet de bord dans les hooks. Vérifier les GET et POST avec hôte hostile, ainsi que les ports de repli. Conserver la garde d'origine ; ajouter un jeton de démarrage/session pour renforcer le modèle local si nécessaire. Flask documente explicitement le filtrage et précise que les hooks `before_request` restent appelés lors d'un rejet de routage : tester leur innocuité est donc nécessaire. [Configuration Flask](https://flask.palletsprojects.com/en/stable/config/#TRUSTED_HOSTS).

### T-02 — Une catégorie personnalisée ferme le script de la page de saisie

**Catégorie : sécurité / XSS persistante. Sévérité : Moyen dans le modèle local actuel.**

**Localisation :** `compta_lmnp/app.py:1548` (`reglementation_gabarit`), `:694` (`saisie`, sérialisation), `compta_lmnp/modules/gabarits.py:212` (`ajouter_personnalise`), `compta_lmnp/modules/pages.py:724` (`perio_json | safe`).

**Scénario exécuté :** créer par la route POST une catégorie dont le libellé est `</script><script>alert(731)</script>`, compte `616110`, nature `charge`, puis demander `/saisie`. Attendu : donnée littérale inoffensive. Produit : **POST 302, balise brute présente dans le contexte script** de la réponse.

`json.dumps` produit du JSON valide, mais n'échappe pas le délimiteur HTML `</script>`. Le filtre `safe` supprime ensuite la protection HTML. La normalisation de la clé laisse les chevrons et barres obliques. L'échappement correct des autres champs de formulaire ne corrige pas ce contexte.

**Impact :** exécution de JavaScript dans l'origine locale, lecture des pages et émission de requêtes avec les droits de l'application. L'entrée est un formulaire local déjà accessible : aucune exploitation distante autonome n'est démontrée. L'essai constate le HTML injecté, pas l'exécution d'une alerte dans un navigateur instrumenté.

**Recommandation :** passer le dictionnaire Python au template et utiliser `{{ perio | tojson }}` ; appliquer la même discipline à `amort_json | safe` (`pages.py:1015`) même si sa source actuelle est moins exposée. Tester les délimiteurs HTML dans clés et valeurs et vérifier le DOM/script dans un navigateur. Une CSP adaptée constitue une défense complémentaire, après extraction ou usage de nonces pour les scripts inline.

### T-03 — Le cache de migration publie un succès avant la fin du travail

**Catégorie : fiabilité / concurrence. Sévérité : Élevé.**

**Localisation :** `compta_lmnp/app.py:130` (`_migrer_si_besoin`), en particulier `:141–152` ; `:227` (`_garde_version_schema`) ; `compta_lmnp/modules/init_db.py:344` (`verifier_version`).

L'ajout dans `_MIGRES` se fait sous verrou, mais la migration a lieu **après la libération du verrou**. Une deuxième requête voit le marqueur, saute la migration et ne trouve encore aucun échec. Le contrôle de version refuse seulement une version trop récente.

**Scénario exécuté :** base fictive marquée version 7, migration suspendue par événement dans un premier thread, seconde requête GET `/saisie`, puis injection d'une panne de migration. Attendu : seconde requête en attente ou refusée, aucune route métier pendant la migration. Produit : **seconde requête 200 ; première requête 409 après panne**.

**Impact :** consultation et potentiellement mutation d'un schéma en cours de transformation ; erreurs intermittentes ou invariants incohérents. Le scénario n'endommage pas de table et ne prétend pas mesurer une perte de données : il prouve l'ouverture de la garde pendant le travail. C'est une limite résiduelle de Q-10.

**Recommandation :** état par dossier « en cours / prêt / échec », verrou couvrant la migration complète, publication de « prêt » uniquement après succès. Attendre ou renvoyer une indisponibilité temporaire aux requêtes concurrentes. Pour plusieurs processus, prévoir un verrou interprocessus ; un `threading.Lock` ne suffit pas. Ajouter le scénario à barrières aux tests de migration et de restauration.

### T-04 — Le suffixe des sauvegardes ne réserve pas le nom

**Catégorie : intégrité / sauvegardes / concurrence. Sévérité : Élevé.**

**Localisation :** `compta_lmnp/modules/perennite.py:63` (`sauvegarder`), `:83–92` (test d'existence puis ouverture SQLite).

**Scénario exécuté :** deux threads appellent la fonction réelle, même base et motif, horloge fixée à la même seconde. Une barrière arrête l'ouverture de la source après le choix du chemin, avant la création de la destination. Attendu : deux fichiers distincts ou refus explicite d'une demande. Produit : **2 retours réussis, 1 chemin distinct, aucune exception**.

**Impact :** deux copies de sûreté annoncées sont en réalité le même objet. Si la source change entre les captures, la seconde peut remplacer la première ; la reproduction utilise volontairement la même source et ne démontre pas une perte chiffrée. Le correctif Q-05 empêche l'écrasement séquentiel mais laisse un « vérifier puis agir » concurrent.

**Recommandation :** réserver un fichier unique avec création exclusive (`tempfile.mkstemp` ou `O_CREAT | O_EXCL`), gérer l'échec sans effacer la copie d'un autre appelant, puis contrôler l'intégrité. Tester deux connexions et états source distincts. Ne pas se contenter d'ajouter des microsecondes : cela réduit les collisions sans garantir l'exclusivité.

### T-05 — Une écriture atomique du registre n'empêche pas les mises à jour perdues

**Catégorie : fiabilité / persistance. Sévérité : Élevé.**

**Localisation :** `compta_lmnp/modules/dossiers.py:86` (`_enregistrer`), `:169` (`creer`), `:199` (`renommer`).

**Scénario exécuté :** deux threads lisent le registre contenant Alpha et Beta ; le premier enregistre `alpha-modifie`, puis le second enregistre sa copie initiale avec `beta-modifie`. Attendu : les deux modifications conservées. Produit : **aucune exception, noms finaux `Alpha` et `beta-modifie`**. La modification Alpha disparaît.

**Impact :** perte silencieuse de renommage ; le même cycle lecture/modification/écriture est employé pour la création, exposant les inscriptions au registre. La preuve ne prétend pas supprimer les bases physiques. Le nom temporaire partagé `dossiers.json.tmp` introduit en outre un risque de collision supplémentaire, non nécessaire à la reproduction.

**Recommandation :** verrouiller l'ensemble lecture–modification–publication, utiliser un temporaire unique et définir le comportement multi-processus. Une petite table de registre SQLite transactionnelle constitue une alternative simple. Tester deux créations distinctes et deux modifications simultanées. `os.replace` rend une publication atomique, pas une transaction couvrant les deux lectures.

### T-06 — L'environnement livré n'est pas celui vérifié en CI

**Catégorie : dépendances / reproductibilité. Sévérité : Moyen.**

**Localisation :** `compta_lmnp/requirements-dev.txt:9–22`, lanceur Unix `:317–345`, lanceur Windows `:56–69`, `.github/workflows/controles.yml` (installation et tests).

**Preuve statique :** les dépendances directes de développement sont épinglées ; les lanceurs installent `flask`, `reportlab` et parfois `cryptography` sans version. Les transitives ne sont pas verrouillées avec leurs empreintes. Un import déjà réussi dispense le lanceur de remettre l'environnement au niveau attendu.

**Impact :** installations différentes pour une même version applicative, régressions difficiles à reproduire et conservation possible d'une ancienne dépendance vulnérable. **Aucune CVE applicable au venv mesuré n'est établie par cette revue partielle.** L'absence de verrou n'est pas en elle-même une CVE et installer une version récente n'est pas automatiquement dangereux.

**Recommandation :** manifeste runtime séparé et contraintes testées, verrouillage des transitives par plateforme/Python si nécessaire, vérification des versions au démarrage et procédure explicite de mise à jour. Ajouter un contrôle SCA périodique fondé sur les versions réellement résolues, avec politique de traitement des alertes. Un verrou doit être renouvelé, pas figé indéfiniment.

**Vérification externe ciblée du 16 septembre 2026 :**

| Composant installé | Avis primaire consulté | Conclusion bornée |
|---|---|---|
| Werkzeug 3.1.8 | [GHSA-29vq-49wr-vm6x](https://github.com/pallets/werkzeug/security/advisories/GHSA-29vq-49wr-vm6x), versions affectées `<3.1.6` | Hors plage de cet avis |
| Jinja2 3.1.6 | [CVE-2025-27516](https://github.com/pallets/jinja/security/advisories/GHSA-cpwx-vrp4-4pq7), versions affectées `<=3.1.5` | Hors plage de cet avis ; aucune exécution de templates utilisateur identifiée |
| Flask 3.1.3 | [GHSA-4grg-w6v8-c28g](https://github.com/pallets/flask/security/advisories/GHSA-4grg-w6v8-c28g), version affectée `3.1.0` | Hors plage de cet avis |

L'inventaire complet local figure dans `resultats.json`. La revue n'est pas un scan SCA exhaustif de Pillow, ReportLab, leurs transitives, des binaires système et de l'option HTTPS. Aucun verdict « toutes dépendances saines » n'est donné ; aucune obsolescence ou absence de maintenance n'est déduite du seul numéro de version.

### T-07 — La modularisation n'empêche pas les cycles et les grandes unités

**Catégorie : architecture / maintenabilité / testabilité. Sévérité : Moyen.**

**Localisation :** `compta_lmnp/app.py:504` (`_base`), `modules/fiscal.py:841`, `modules/controles.py:21`, `modules/init_db.py:92`, `modules/perennite.py:214`, `modules/liasse_pdf.py:145`, `modules/valider_fec.py:96`.

**Mesure AST exécutée :** `app.py` 2 276 lignes, `pages.py` 2 434, `controles.py` 1 360. `generer_pdf` : 379 lignes / 34 nœuds de branchement ; `valider` : 294 / 49 ; `rappels` : 207 / 26. Ces compteurs incluent les lignes documentaires et ne sont **pas** une mesure normalisée de complexité cyclomatique ou cognitive.

Le graphe d'imports révèle `fiscal ↔ controles` et `init_db ↔ perennite`. Les imports différés évitent ici un plantage au chargement, mais ne suppriment pas le couplage conceptuel. La configuration Flask, les chemins, le journal et les états de migration restent globaux. La coquille HTML persiste dans `_base`, malgré l'extraction positive des pages.

**Impact :** grande surface de changement, tests dépendant de substitutions globales, évolution des transactions difficile à raisonner, risque de déplacer une responsabilité sans casser le cycle. Cela ne justifie pas de qualifier tout le code de « spaghetti » : les modules d'écriture, fichiers et contrôles offrent des frontières utiles.

**Recommandation :** extraire les calculs purs partagés vers un module sans dépendance au service de clôture ; séparer lecture des métadonnées de schéma et orchestration de sauvegarde. Introduire progressivement `create_app(config)` et un contexte de dossier injecté. Décomposer le PDF par sections et le validateur par phases, avec mêmes tests de sortie. Préserver l'indépendance du validateur vis-à-vis de l'exportateur : mutualiser leurs décisions créerait un angle mort commun.

### T-08 — Les tests couvrent largement les scénarios, moins les frontières d'exécution

**Catégorie : qualité / testabilité. Sévérité : Moyen.**

**Localisation :** `.github/workflows/controles.yml:30–79`, `compta_lmnp/tests/conftest.py:48–96`, `compta_lmnp/pyproject.toml:16`, `compta_lmnp/tests/test_passe_q.py`.

**Constat :** CI sur Ubuntu/Python 3.13 seulement ; lanceurs distribués sur Windows et macOS ; environnement local testé ici en 3.14. Les tests Flask rendent les pages mais ne remplacent pas une exécution navigateur de JavaScript. Les défauts T-02 à T-05 subsistent malgré la suite passée. Les tests sur sources gardent leur utilité documentaire, mais ne démontrent pas une propriété d'exécution.

Le hook de collection sélectionne certains jeux par présence de `reference/` et substitue des constantes de modules. Cette technique garde le clone public testable, au prix de deux compositions de suite et de dépendances implicites. Aucun pourcentage de couverture lignes/branches n'a été mesuré ; 1 162 succès ne constitue pas un taux de couverture.

**Impact :** faux sentiment de fermeture d'un constat, notamment lorsqu'un test séquentiel vise une propriété concurrente ; défauts de lanceur et de rendu dépendant d'une plateforme non éprouvée.

**Recommandation :** ajouter des tests à barrières pour T-03/04/05, un test navigateur pour T-02, puis une petite matrice Python minimal supporté / version CI et des tests de démarrage Windows/macOS. Séparer explicitement fixtures publiques et privées ; publier les tests ignorés. Mesurer la couverture des branches critiques avant de fixer un objectif. Les règles Ruff actives (`E4/E7/E9/F/W`) ne constituent ni SAST sécurité complet ni contrôle de complexité.

### T-09 — Lectures répétées et documentation d'architecture décalée

**Catégorie : performance / documentation. Sévérité : Faible.**

**Localisation :** `compta_lmnp/app.py:420` (`_catalogue`), `:672` (`saisie`), `modules/gabarits.py:255–284`, `compta_lmnp/ARCHITECTURE.md` (sections « Dette technique » et « Suite de tests »).

**Mesure exécutée :** une demande `/saisie` sur base fictive produit **14 instructions SQL**, dont **3 lectures de `gabarit_personnalise`** : `_catalogue` recharge les gabarits via `tous` et `par_groupe`, puis la route les recharge pour les périodicités. Il s'agit d'une duplication constante, pas d'un N+1 démontré. Aucun ralentissement perceptible n'est chiffré.

L'architecture annonce encore environ 1 200 lignes de routes et 279 tests, alors que l'inventaire actuel et la suite donnent des dimensions très différentes. Elle présente aussi les migrations versionnées comme une étape future alors que `migrations.py` existe.

**Impact :** coût évitable et modèle mental périmé pour le mainteneur. **Recommandation :** construire un catalogue une fois par requête et dériver les vues de ce dictionnaire ; éviter un cache global dont l'invalidation serait plus risquée que ces trois lectures. Mettre à jour les décisions d'architecture et remplacer les compteurs périssables par des commandes d'inventaire.

## 4. Appréciation transversale complémentaire

### Architecture et passage à l'échelle

Le monolithe modulaire SQLite est proportionné au logiciel local. Aucun besoin démontré ne justifie des microservices, une file distribuée ou un ORM ajouté pour l'audit. Les contraintes actuelles sont un écrivain SQLite à la fois, des traitements synchrones PDF/import, des fichiers locaux et des verrous/cache par processus. Multiplier les workers ne rendrait pas ces garanties communes : cela exige d'abord de revoir le registre, les migrations et les fichiers de sauvegarde.

Pour une future offre multi-utilisateur, définir authentification, autorisations par dossier, isolation des locataires, stockage partagé et gestion de jobs avant de changer de serveur. Le cookie `dossier` sélectionne un contexte ; ce n'est pas une session d'authentification. Son caractère non signé n'est donc pas à lui seul une faille de session dans le modèle mono-utilisateur.

### Qualité, erreurs et ressources

Le français est cohérent dans les noms, les modules et les commentaires. Les nombreux commentaires historiques rendent les décisions compréhensibles, mais leur volume participe à la longueur des fonctions. La séparation des pages et le parseur commun `fec_io` réduisent une duplication réelle. L'orchestration web garde SQL, chemins et rendu : priorité aux services de cas d'usage et aux contrats transactionnels, pas à une réécriture générale.

`_conn` inscrit les connexions dans le contexte Flask et le teardown les ferme, y compris après exception. Le journal tourne sur fichiers bornés. Le moteur de contrôles isole les exceptions et refuse une conclusion positive si une vérification échoue. La page d'erreur globale assure néanmoins « Vos données ne sont pas affectées » (`app.py:349–355`) sans pouvoir connaître le point du commit : améliorer cette formulation plutôt que promettre une annulation universelle. Les échecs d'ouverture du journal peuvent également rendre son annonce trop affirmative.

Aucune fuite mémoire ou de descripteurs durable n'a été quantifiée. Le rendu PDF utilise un tampon mémoire et l'import charge des données : leur consommation doit être mesurée sur un corpus volumineux avant de conclure à un besoin de streaming. Le plafond HTTP de 2 Mio borne les uploads web, mais pas les imports CLI. Les fichiers de préparation gardés après échec Q-09 servent la reprise ; une purge explicite et bornée est préférable à leur suppression systématique.

### I/O, requêtes et sécurité des entrées

Des index explicites existent (`init_db.py:306–314`) sur exercice, lignes d'écriture, comptes, opérations et plan. La page de saisie limite l'affichage à 100 opérations. Aucun diagnostic d'« absence générale d'index » n'est justifié. Une mesure sur grands volumes, des plans `EXPLAIN QUERY PLAN` et le comptage des requêtes des contrôles restent nécessaires avant de proposer des index composites supplémentaires.

Les chemins d'archives et slugs ont des gardes, les requêtes examinées utilisent des paramètres pour les valeurs, les champs numériques rejettent les valeurs non finies, les rendus ordinaires bénéficient de l'échappement et le PDF dispose d'un échappement XML. Aucune injection SQL, exécution de commande ou secret d'authentification en clair exploitable n'a été établi dans les chemins examinés. Ce constat borné ne couvre pas tout l'historique Git. L'injection T-02 est un défaut de contexte HTML/JavaScript distinct d'une injection de template côté serveur.

## 5. Plan d'action priorisé

| Horizon | Actions | Critère de fin vérifiable |
|---|---|---|
| Court terme — avant prochaine diffusion | T-01 : filtrer les hôtes avant effets de bord ; T-02 : `tojson` pour le rendu JavaScript | Hôtes arbitraires refusés ; payload conservé comme donnée, aucun nouveau script dans le DOM |
| Court terme — intégrité | T-03 : protéger tout le cycle de migration ; T-04 : réserver les destinations de sauvegarde ; T-05 : verrouiller les modifications du registre | Tests concurrents déterministes ; aucun accès métier pendant migration ; copies distinctes ; toutes les mises à jour conservées |
| Court terme — publication | Fermer R-01 par vérification anonyme de la source correspondant à la version ; expliciter les limites de la page d'erreur | Source accessible et version identifiable ; aucune promesse générale d'absence d'effet après une erreur |
| Moyen terme — dépendances et tests | T-06 et T-08 : environnement runtime reproductible, SCA récurrent, matrice de démarrage, test navigateur et couverture des branches | Installation reproductible dans un répertoire neuf ; inventaire daté ; alertes traitées ; skips visibles |
| Moyen terme — structure | T-07 : services de cas d'usage, fabrique Flask, rupture des imports réciproques, fonctions de validation et PDF plus petites | Dépendances orientées ; tests inchangés sur les sorties ; transactions possédées par une couche identifiée |
| Moyen terme — performance | T-09 et profilage sur corpus synthétique volumineux | Catalogue lu une fois ; temps/mémoire et nombre de requêtes publiés avant/après |
| Long terme — selon usage réel | Maintenir le monolithe local ; envisager stockage transactionnel partagé, autorisations et jobs seulement si multi-utilisateur requis | Objectifs de charge et modèle de menace définis avant changement de technologie |

## 6. Ce qui a été vérifié et tenu

- Les tests de non-régression historiques passent dans l'environnement disponible ; l'échec réseau initial est expliqué par une réexécution réussie.
- Une origine HTTP distincte est refusée en 403 ; le défaut T-01 concerne la confiance dans l'hôte, pas l'absence totale de garde CSRF.
- Les correctifs documentaires R disposent de 12 tests passés, dont les liens et l'empreinte de licence.
- Les mécanismes de transaction, de refus explicite, d'indexation et de fermeture des connexions sont présents ; aucune absence générale de ces protections n'est signalée.
- Les nouveaux scénarios produisent des résultats indépendants du dossier réel et nettoient leurs bases temporaires.

## 7. Non vérifiable dans cette passe

- Quelles variantes de DNS rebinding les navigateurs réellement utilisés autorisent-ils ? Aucun navigateur n'a été instrumenté ici.
- Quelles sont la couverture de branches, la résistance aux mutations des tests et la consommation mémoire au volume maximal supporté ? Aucun chiffre n'est inventé.
- Les lanceurs fonctionnent-ils nativement sur toutes les versions Windows/macOS promises ? La CI actuelle et l'hôte d'audit ne suffisent pas à le certifier.
- Quelles vulnérabilités supplémentaires ressortiraient d'un SCA exhaustif daté incluant les transitives, Poppler et le chemin HTTPS ? La consultation ciblée d'avis ne remplace pas cette étape.
- La source offerte par R-01 est-elle désormais accessible anonymement ? Non revérifié ; le statut de correction reste ouvert.
- Les sauvegardes résistent-elles à une coupure électrique réelle, à un stockage réseau ou à deux processus indépendants ? Les essais de T imposent des entrelacements de threads, pas ces environnements.

## 8. Tableau récapitulatif

| N° | Catégorie | Sévérité | Nature de la preuve | Priorité |
|---|---|---|---|---|
| T-01 | Sécurité HTTP | Élevé | Requêtes réelles du client Flask et mutation constatée | Immédiate |
| T-02 | XSS persistante | Moyen | POST réel puis HTML contenant la balise brute | Immédiate |
| T-03 | Migration concurrente | Élevé | Deux threads, migration suspendue puis échec injecté | Immédiate |
| T-04 | Sauvegarde concurrente | Élevé | Deux sauvegardes réelles retournent la même destination | Immédiate |
| T-05 | Registre concurrent | Élevé | Deux renommages réels, une modification perdue | Immédiate |
| T-06 | Dépendances | Moyen | Configuration et inventaire local ; avis primaires ciblés | Prochaine diffusion |
| T-07 | Architecture | Moyen | Graphe d'imports et métriques AST | Moyen terme |
| T-08 | Testabilité | Moyen | Suite exécutée et revue CI/tests | Moyen terme |
| T-09 | Performance/documentation | Faible | Trace SQLite et comparaison documentaire | Moyen terme |

---

## 9. Suivi des correctifs

Traitement du 16 septembre 2026, version **8.53.0**. **Les neuf constats sont
confirmés** : le script `preuves_t/reproduire.py` a été rejoué tel quel avant
toute modification, et chaque mesure correspondait au rapport. Aucun constat
annulé.

| N° | Sév. | État | Correctif | Non-régression |
|---|---|---|---|---|
| T-01 | Élevé | **Corrigé** | `TRUSTED_HOSTS` + garde applicative enregistrée **avant toute autre** `before_request` ; hôte hors `localhost / 127.0.0.1 / [::1]` refusé en 403 avant tout effet de bord | `test_t01_*` (3 tests, dont la contre-épreuve des hôtes locaux) |
| T-02 | Moyen | **Corrigé** | Le dictionnaire est passé au gabarit et rendu par `\| tojson`, qui échappe `<`, `>` et `&` ; `\| safe` sur du JSON a disparu des deux emplacements | `test_t02_*` (2 tests) |
| T-03 | Élevé | **Corrigé** | Séparation de « quelqu'un s'en occupe » et « c'est fait » : `_MIGRATIONS_EN_COURS` distinct de `_MIGRES`, `threading.Condition`, publication du succès **après** la migration, et 503 borné pour la requête concurrente | `test_t03_*` (2 tests à barrière) |
| T-04 | Élevé | **Corrigé** | Le nom est réservé par `O_CREAT \| O_EXCL` — atomique au niveau du système de fichiers — au lieu d'un `os.path.exists` suivi d'une ouverture ; la coquille est retirée si la copie échoue | `test_t04_*` (2 tests) |
| T-05 | Élevé | **Corrigé** | Lecture, modification et publication du registre dans **une seule** section critique (`_registre_exclusif`) ; nom temporaire unique par processus et par fil | `test_t05_*` (3 tests) |
| T-06 | Moyen | **Corrigé** | `requirements.txt` séparé, versions **bornées** (pas épinglées, voir plus bas) ; les lanceurs l'installent au lieu d'écrire les noms en clair, et comparent son empreinte à celle de la dernière installation réussie | `test_t06_*` (4 tests) |
| T-07 | Moyen | **Partiellement traité — chantier déclaré** | Les gardes HTTP sortent de `app.py` vers `modules/gardes_http.py`. Les cycles d'imports et les grandes fonctions **ne sont pas traités** : voir ci-dessous | garde anti-monolithe existante (`test_refonte`) |
| T-08 | Moyen | **Partiellement traité** | Matrice CI 3.12 / 3.13 / 3.14 avec `fail-fast: false` ; tests à barrières ajoutés pour T-03, T-04 et T-05. Le test navigateur et la matrice de plateformes **ne sont pas faits** | `test_passe_t.py` |
| T-09 | Faible | **Corrigé** | Catalogue chargé **une fois** par requête (`grouper` séparé de `tous`) : 14 → 10 instructions SQL, 3 → 1 lecture de `gabarit_personnalise`. Compteurs périmés retirés de `ARCHITECTURE.md` | `test_t09_*` (3 tests) |

### Pourquoi les dépendances sont bornées et non épinglées

Le rapport recommande un verrouillage. Il est appliqué **là où il a un
sens** — `requirements-dev.txt` épingle au point, et c'est ce que la CI
éprouve — mais **pas** pour l'utilisateur.

Le logiciel s'installe chez un particulier, sur un Python que nous ne
choisissons pas, souvent plus récent que tout ce que nous avons éprouvé. Une
version exacte n'y aurait pas nécessairement de roue précompilée : pip
tenterait une compilation depuis les sources, et l'installation échouerait
pour une raison bien plus obscure que celle qu'on prétendait éviter. On borne
donc la **majeure**, qui est ce qui casse la compatibilité, et un test vérifie
que le plancher livré est exactement la version que la CI éprouve.

Le maillon qui manquait n'était d'ailleurs pas le verrou : c'est qu'un import
réussi dispensait le lanceur de toute vérification, et qu'un `.venv` vieilli
survivait à toutes les mises à jour. Les lanceurs comparent désormais
l'empreinte du manifeste à celle de la dernière installation réussie.

### Ce qui n'est PAS traité, et pourquoi

**T-07, les cycles d'imports et les grandes unités.** `fiscal ↔ controles` et
`init_db ↔ perennite` s'importent toujours mutuellement ; `generer_pdf` et
`valider` dépassent toujours 290 lignes. C'est un **chantier de refonte**, pas
un correctif : la direction est consignée dans `ARCHITECTURE.md` (points 5
et 6 de la dette technique), avec la contrainte à ne pas perdre —
l'indépendance du validateur vis-à-vis de l'exportateur, sans quoi les deux
partageraient un angle mort. Entreprendre cela sous couvert de traiter un
audit reviendrait à mêler une réécriture à des correctifs de sécurité, dans le
même lot, juste avant une publication.

**T-08, le test navigateur et la matrice de plateformes.** La matrice Python
est faite ; le reste ne l'est pas. Un test navigateur demande un pilote et une
infrastructure qui n'existent pas dans ce projet, et les lanceurs Windows et
macOS ne peuvent pas être éprouvés depuis Linux — c'est précisément ce qui
avait laissé passer un exécutable PyInstaller cassé pendant des mois. Ces deux
manques restent donc **ouverts et nommés**, plutôt que comblés par un test qui
prouverait moins qu'il n'en aurait l'air.

**La couverture de branches n'est pas mesurée.** Le rapport a raison de
rappeler que 1 184 succès ne sont pas un taux de couverture. Aucun objectif
chiffré n'est fixé ici : en poser un sans mesure préalable produirait des
tests écrits pour le compteur.

### Ce que les correctifs ont fait apparaître

- **La garde anti-monolithe s'est déclenchée** pendant le traitement :
  `app.py` dépassait 2 300 lignes. Le seuil n'a pas été relevé — c'est ce
  qu'il est censé empêcher. Les gardes d'entrée HTTP ont été extraites, et
  c'est ce qui a ramené le fichier sous la limite tout en répondant à une
  partie de T-07.
- **La garde du lanceur Windows s'est déclenchée** : une édition en Python
  avait converti ses fins de ligne CRLF en LF. Elle a fait exactement son
  travail.
- **Un test existant produisait un faux positif** : `hashlib.sha256`, écrit
  dans le lanceur Unix, était lu comme une citation du fichier « hashlib.sh ».
  Le code a été reformulé plutôt que la garde assouplie.
- **Le scénario T-05 du script de preuve ne peut plus s'exécuter** : sa
  barrière attend un entrelacement que le verrou rend impossible, et les deux
  fils sortent en `BrokenBarrierError`. Le correctif invalide la preuve qui le
  motivait — d'où les tests à barrière écrits pour cette passe, qui vérifient
  le résultat (les deux modifications conservées) et non l'entrelacement.
- **Un de mes propres tests ne prouvait rien.** La première version du test
  T-02 passait par la route complète : la normalisation de la clé masquait la
  charge, et le test restait vert avec `| safe` comme avec `| tojson`. Il rend
  désormais la ligne réelle du gabarit et distingue les deux états. Le
  constat T-08 a ainsi trouvé sa première application sur le traitement de
  T-08 lui-même.

### Vérification finale

`1 184 tests` passent (22 nouveaux), `ruff` est propre, le paquet client se
construit sans lien mort, et le script `preuves_t/reproduire.py` rejoué donne :
hôte hostile **403/403 sans création**, balise brute **absente**, requête
concurrente pendant migration **409**, sauvegardes **2 chemins distincts**,
page de saisie **10 requêtes SQL et 1 lecture du catalogue**. Les cycles
d'imports restent affichés par le script : c'est le chantier déclaré ouvert.
