# Audit — passe R : licences, provenance et promesses du dépôt

Audit du 16 septembre 2026, sur **8.51.1**, commit `82ba5d04aa668b73858cd21e8cbba290680ea3a3`. La migration AGPL est celle de 8.51.0. **Sept constats : deux majeurs, cinq mineurs ; aucun critique.** Les deux majeurs concernent une source promise mais inaccessible anonymement, et une déclaration générale d'absence de composants à réciprocité contredite par l'outillage réellement utilisé. Aucune violation d'une obligation de redistribution d'une bibliothèque tierce n'est établie sur le ZIP examiné.

Ce rapport est un audit technique et documentaire, pas un avis juridique. « Majeur » qualifie ici une promesse substantielle non tenue, pas une qualification juridique de contrefaçon. Aucun montant de préjudice ni de redressement fiscal n'est établi. Les questions de titularité, de réutilisation administrative et de marques sont séparées des constats.

## Périmètre, pièces et méthode

Les seize fichiers demandés sont présents. Ont aussi été examinés `build_client.py`, `app.py`, `verifier_depot.py`, le générateur de certificat, les seeds génériques, le hook, la CI, les tests de propriété intellectuelle, les fichiers suivis par Git, les paquets installés et leurs licences. Lecture préalable des invariants, de l'entrée 8.51.0 du changelog, des corrections de distribution et du suivi de la passe N. Ni l'ancien exécutable retiré, ni les défauts déjà corrigés des passes précédentes ne sont signalés comme défauts actuels.

L'inventaire des imports, installations et métadonnées a précédé la lecture de `NOTICES-TIERS.md`. Le ZIP a été **construit**, décompressé dans un répertoire temporaire, puis l'application a été appelée avec le client Flask sur une base **blanche créée pour l'audit**. Aucune base réelle n'a servi aux scénarios. La construction a utilisé le garde-fou local existant, sans recopier ses empreintes.

Preuves reproductibles : [script](preuves_r/reproduire.py), [résultats](preuves_r/resultats.json), [vérifications externes et système](preuves_r/verifications_externes.json), [contenu du ZIP](preuves_r/zip.txt), [métadonnées et empreintes des licences installées](preuves_r/paquets.json), [recensement des indications de licence](preuves_r/indications_licence.json), [historique pseudonymisé](preuves_r/historique_pseudonymise.json). Ces pièces conservent les chemins, versions et résultats utiles, sans noms ou adresses des auteurs Git. Les identités pseudonymisées ne prouvent pas l'existence de personnes distinctes.

Reproduction depuis la racine :

```sh
python build_client.py
.venv/bin/python docs/preuves_r/reproduire.py
.venv/bin/python -m pip freeze
.venv/bin/python -m pip show -f Flask reportlab
.venv/bin/python -m pytest -q compta_lmnp/tests/test_audit_production.py -k 'modele_proprietaire or licence_livree or notices_tierces or entetes_portent'
```

Sorties observées : ZIP **45 fichiers**, licence racine identique à `LICENSE.txt`, interface **HTTP 200**, sprite identique, extraction du PDF fictif réussie ; les quatre tests sélectionnés **passent**. Ce dernier résultat ne valide pas les promesses externes : ces tests cherchent surtout des mots dans les sources.

Le dépôt local comprend 46 commits accessibles et aucun tag. Il ne permet pas de reconstituer à lui seul deux années de développement, les décisions de revue privées ou les anciennes distributions effectivement remises. L'audit ne certifie pas l'absence de données privées dans tout l'historique Git.

## Constats vérifiables

### R-01 — Le lien « code source » livré répond 404 sans authentification

**TYPE : OBLIGATION_NON_REMPLIE** — engagement documentaire d'accès à la source, sans conclusion autonome de violation de l'article 13.

**GRAVITÉ : majeur.**

**PROMESSE / OBLIGATION TESTÉE :** le pied de page offre le « code source » de l'application affichée. L'utilisateur doit pouvoir obtenir la source annoncée. Le commentaire du test de licence présente ce lien comme une offre de source.

**SCÉNARIO REPRODUCTIBLE :** construire 8.51.1, extraire le ZIP dans un répertoire vide, initialiser une base blanche, demander `/` avec suivi des redirections. Extraire le `href` du lien dont le texte est `code source`, puis effectuer une requête HTTPS anonyme, avec suivi des redirections. L'URL n'est pas recopiée ici pour éviter de republier l'identifiant de compte ; elle est extraite directement du livrable :

```python
import re, subprocess, zipfile
with zipfile.ZipFile('compta_lmnp/dist/compta_lmnp_client_v8.51.1.zip') as z:
    s = z.read('compta_lmnp/app.py').decode()
u = re.search(r'href="([^"]+)"[^>]*>code source</a>', s).group(1)
subprocess.run(['curl', '-L', '-sS', '--max-time', '25',
                '-o', '/dev/null', '-w', '%{http_code}\n', u], check=True)
```

**ATTENDU :** source accessible sans compte autorisé, correspondant à 8.51.1, ou indication honnête que la publication n'est pas encore disponible.

**PRODUIT :** interface `http=200`, `source_lien_present=true`, `version_visible=true` ; requête anonyme **`404`** le jour de l'audit. Le lien vise la racine du dépôt, sans tag ou commit ; `git tag` ne retourne rien. Un 404 ne permet pas de distinguer dépôt privé, inexistant ou renommé : le fait établi est l'inaccessibilité anonyme.

**PREUVE :** `preuves_r/resultats.json`, rubrique `interface`, et commande HTTP ci-dessus exécutée. Le test `test_licence_livree_avec_le_paquet_et_source_offerte` passe malgré cette réponse : il vérifie la présence du mot `github.com`, pas l'accès.

**FICHIER / LIGNE :** `compta_lmnp/app.py:505`, fonction `_base`, lien aux lignes 605–606 ; `compta_lmnp/tests/test_audit_production.py:319`, fonction `test_licence_livree_avec_le_paquet_et_source_offerte`.

**CONSÉQUENCE :** l'utilisateur du serveur web ne reçoit pas la source par le moyen annoncé. Le ZIP contient toutefois les sources de production : il serait faux de conclure à une distribution exclusivement binaire ou à une absence totale de source. Le dépôt étant encore privé selon le contexte, c'est un point à résoudre **avant** d'annoncer la disponibilité publique. Aucun dommage en euros établi.

**CORRECTION MINIMALE :** rendre accessible une source correspondant à la version, puis tester anonymement le lien depuis le livrable. Un tag, un commit accessible ou une archive immuable permettrait de rattacher l'offre à 8.51.1 ; aucun mécanisme particulier n'est imposé par ce constat. Le lien est une chaîne ordinaire modifiable par un forkeur : pas de verrouillage technique ni d'obligation d'héberger les futurs forks imputée au projet initial.

### R-02 — L'affirmation « aucun composant GPL ou assimilé utilisé » est fausse pour l'outillage du dépôt

**TYPE : CONTROLE_NON_DEMONTRE.**

**GRAVITÉ : majeur.**

**PROMESSE / OBLIGATION TESTÉE :** `NOTICES-TIERS.md:21` exclut tout composant à réciprocité, sans limiter cette affirmation au serveur comptable. La notice est aussi livrée au client.

**SCÉNARIO REPRODUCTIBLE :** produire un PDF contenant seulement `Document fictif audit R sans aucune donnee personnelle.` ; appeler la fonction réelle `verifier_depot.texte_du_pdf` ; identifier le programme système utilisé avec `pdftotext -v`, `rpm -qi poppler-utils` et lire `/usr/share/licenses/poppler/COPYING`.

**ATTENDU :** soit aucun outil à réciprocité utilisé dans le périmètre affirmé, soit une déclaration qui distingue explicitement application, outils de contrôle, paquets installés et composants redistribués.

**PRODUIT :** `texte="Document fictif audit R sans aucune donnee personnelle."`, `reserve=""`. Le programme exécuté est `pdftotext` **26.01.0** ; le paquet système déclare notamment `GPL-2.0-only OR GPL-3.0-only`, ainsi que des termes GPL/LGPL et MIT. Son fichier `COPYING` contient la GPL version 2. La CI installe expressément `poppler-utils`.

**PREUVE :** `preuves_r/resultats.json`, rubrique `poppler_execution` ; métadonnées RPM et licence système lues. Le [site du projet Poppler](https://poppler.freedesktop.org/) identifie également `pdftotext` dans ses outils ; la licence précise retenue ici provient du **paquet installé**, pas d'une supposition de mémoire.

Autre limite indépendante : ReportLab 5.0.1 installé contient `fonts/DarkGardenMK.pfb`, son source `.sfd`, `DarkGarden-copying.txt` et `DarkGarden-copying-gpl.txt`. Le premier texte accorde **GPL-2.0-or-later avec exception pour l'incorporation de la police dans un document**. Sa seule présence ne prouve pas son usage par la liasse. Les 14 PDF suivis par Git emploient Helvetica et Helvetica-Bold **non incorporées** ; aucune incorporation de DarkGarden n'a été établie. Il serait donc erroné d'en déduire que les PDF de l'utilisateur doivent être publiés sous GPL.

**FICHIER / LIGNE :** `NOTICES-TIERS.md:21`, déclaration documentaire ; `compta_lmnp/verifier_depot.py:130`, fonction `texte_du_pdf`, exécution à la ligne 154 ; `.github/workflows/controles.yml:65`, étape d'installation de Poppler.

**CONSÉQUENCE :** un lecteur reçoit une assurance générale contredite par une utilisation réelle. Cela ne démontre **ni** redistribution de Poppler par le projet, **ni** incompatibilité de l'application AGPL avec un programme GPL appelé en sous-processus. Aucun manquement d'attribution de Poppler dans le ZIP n'est retenu.

**CORRECTION MINIMALE :** remplacer la négation absolue par un inventaire borné et daté ; nommer Poppler et les ressources à régime distinct des paquets installés. Séparer « installé », « exécuté » et « redistribué ».

### R-03 — La notice omet des dépendances d'exécution installées ou demandées

**TYPE : NOTICE_TIERS_INCOMPLETE.**

**GRAVITÉ : mineur.**

**PROMESSE / OBLIGATION TESTÉE :** la liste des composants et de leurs licences est présentée comme le détail des dépendances du logiciel.

**SCÉNARIO REPRODUCTIBLE :** interroger `importlib.metadata.distribution('reportlab').requires` dans le venv fourni ; comparer les noms aux lignes 9–19 de la notice extraite du ZIP. Lire aussi le chemin HTTPS du lanceur Unix et les imports du générateur de certificat.

**ATTENDU :** Pillow et charset-normalizer figurent parmi les dépendances transitives de l'export PDF ; cryptography figure comme dépendance directe conditionnelle du HTTPS. Leur statut de redistribution reste explicite.

**PRODUIT :** ReportLab **5.0.1** déclare `pillow>=9.0.0` et `charset-normalizer` sans condition d'extra ; sont installés **Pillow 12.3.0** et **charset-normalizer 3.5.1**. Aucun des deux n'apparaît dans la notice. Le lanceur demande `pip install --quiet cryptography` lorsque `--https` est demandé et que le certificat manque ; ce composant est aussi absent de la notice. Cryptography n'est pas installé dans le venv audité : sa licence effective et ses transitives ne sont pas déclarées vérifiées.

**PREUVE :** sorties réelles `pip freeze`, `pip show reportlab`, fichiers `METADATA` et `LICENSE`, recensés dans `preuves_r/paquets.json`. Le texte de Pillow vérifie **MIT-CMU**, celui de charset-normalizer **MIT**. Le test `test_notices_tierces_disent_les_vraies_dependances` passe : il ne réclame que quatre chaînes fixes.

**FICHIER / LIGNE :** `NOTICES-TIERS.md:9` ; `compta_lmnp/Compta-LMNP-Linux-macOS.sh:345`, corps du lanceur ; `compta_lmnp/generer_certificat.py:21`, fonction `generer` ; `compta_lmnp/tests/test_audit_production.py:333`, fonction `test_notices_tierces_disent_les_vraies_dependances`.

**CONSÉQUENCE :** inventaire incomplet pour le mainteneur et pour un futur redistributeur. **Aucune obligation de joindre ces licences au ZIP courant n'est démontrée**, puisque les paquets concernés n'y sont pas présents. C'est une inexactitude documentaire, pas une contrefaçon prouvée.

**CORRECTION MINIMALE :** ajouter les dépendances manquantes avec leur mode d'installation et leurs versions vérifiées ; produire l'inventaire à partir des métadonnées, complété par les chemins optionnels et outils système. Les composants de développement peuvent former une rubrique distincte plutôt qu'être présentés comme nécessaires au client.

### R-04 — Les liens de licence et de contribution ne fonctionnent pas dans le ZIP

**TYPE : AMELIORATION_DOCUMENTAIRE.**

**GRAVITÉ : mineur.**

**PROMESSE / OBLIGATION TESTÉE :** le document d'accueil livré renvoie au texte intégral, aux notices et aux conditions de contribution.

**SCÉNARIO REPRODUCTIBLE :** construire 8.51.1, ouvrir `compta_lmnp/LISEZ-MOI.md` dans l'archive et résoudre les liens relativement à ce document, sans utiliser le dépôt de développement.

**ATTENDU :** chaque lien local annoncé atteint le document correspondant dans la distribution, ou un lien distant explicitement accessible.

**PRODUIT :** cinq occurrences non résolues : `../LICENSE` **deux fois**, `../README.md`, `../NOTICES-TIERS.md`, `../CONTRIBUTING.md`. Le ZIP contient `compta_lmnp/LICENSE.txt` et `compta_lmnp/NOTICES-TIERS.md`, mais ni le README racine ni CONTRIBUTING.

**PREUVE :** `preuves_r/resultats.json`, rubrique `liens_locaux_absents`, calculée sur les noms **réels** du ZIP après normalisation des chemins, et `preuves_r/zip.txt`.

**FICHIER / LIGNE :** `compta_lmnp/LISEZ-MOI.md:4`, `:590`, `:591`, `:607`, `:615`, document ; `compta_lmnp/construire_distribution.py:55`, constante `DOCS`, consommée par la fonction `construire` à la ligne 89.

**CONSÉQUENCE :** le lecteur du paquet autonome ne suit pas les renvois promis, notamment vers la procédure DCO. **La licence n'est pas absente** : sa copie complète existe à côté. Pas de non-conformité à l'obligation de remise du texte démontrée par ces liens cassés.

**CORRECTION MINIMALE :** adapter les liens lors de la construction ou livrer une documentation portable avec des cibles effectivement présentes ; vérifier tous les liens locaux du ZIP, sans liste limitée à ceux déjà connus.

### R-05 — Vingt sources distribuées gardent une fin de phrase de l'ancienne restriction

**TYPE : AMELIORATION_DOCUMENTAIRE.**

**GRAVITÉ : mineur.**

**PROMESSE / OBLIGATION TESTÉE :** le changement de licence et la garde anti-retour annoncent des en-têtes cohérents avec le modèle libre.

**SCÉNARIO REPRODUCTIBLE :** lire les premières lignes de tous les fichiers Python du ZIP construit ; rechercher `sans autorisation`.

**ATTENDU :** en-tête AGPL sans fragment inexpliqué d'une condition d'autorisation individuelle.

**PRODUIT :** **20 fichiers de production**, dont `app.py`, `cli.py`, `modules/liasse_pdf.py`, `modules/gabarits.py` et `modules/parametres.py`, portent après l'identifiant SPDX la ligne `# sans autorisation écrite de l'auteur.`. La liste complète est dans la preuve. Cinq fichiers de tests suivis présentent aussi ce reste. Le test `test_aucun_reste_du_modele_proprietaire` passe.

**PREUVE :** `preuves_r/resultats.json`, `zip.restes_autorisation`, obtenu en lisant le contenu de chaque entrée Python, et exécution du test.

**FICHIER / LIGNE :** `compta_lmnp/modules/liasse_pdf.py:3`, `compta_lmnp/modules/gabarits.py:3`, `compta_lmnp/modules/parametres.py:3`, en-têtes sans fonction ; `compta_lmnp/tests/test_audit_production.py:276`, fonction `test_aucun_reste_du_modele_proprietaire`.

**CONSÉQUENCE :** une réserve orpheline est diffusée à côté d'une licence qui autorise les modifications. **Diagnostic limité :** cette proposition sans verbe ni objet ne constitue pas à elle seule une interdiction effective de modifier ou revendre. Le classement n'est donc pas `CONTRADICTION_DE_LICENCE` et ne prétend pas invalider la concession AGPL.

**CORRECTION MINIMALE :** supprimer ces lignes résiduelles ; compléter la revue des en-têtes, sans assimiler une courte liste de motifs à une preuve d'absence de toute restriction.

### R-06 — Le régime des données et documents n'est pas explicité par catégorie

**TYPE : PERIMETRE_DE_LICENCE_AMBIGU.**

**GRAVITÉ : mineur.**

**PROMESSE / OBLIGATION TESTÉE :** le dépôt annonce AGPL pour le logiciel ; le README parle aussi de licence portant sur le « code ». Les destinataires reçoivent également des données de démonstration, un référentiel et de la documentation.

**SCÉNARIO REPRODUCTIBLE :** inventorier les 215 fichiers suivis à HEAD, puis lire les déclarations de licence et les en-têtes des trois SQL, du FEC de démonstration, des documents d'accueil et des rapports. L'inventaire parcourt les fichiers Git, pas une liste choisie de fichiers censés avoir une licence.

**ATTENDU :** un lecteur sait si la déclaration globale couvre également documentation, rapports, données et référentiels, sous réserve des éléments tiers et des droits éventuellement distincts. Une déclaration centrale suffit ; un SPDX sur chaque fichier n'est pas exigé.

**PRODUIT :** déclaration générale AGPL, mais aucune ventilation explicite pour les données de démonstration, la sélection du plan de comptes et les rapports/preuves de `docs/`. `seed_referentiel.sql` se présente comme générique et distribué, sans indication de régime propre. Le recensement retourne **127 fichiers sans SPDX**, dont **104 fichiers textuels sans même occurrence d'une mention de licence** ; ces comptes sont des indices de traçabilité, **pas 127 infractions**. Les 14 PDF sont classés séparément du texte par le script.

**PREUVE :** `preuves_r/indications_licence.json` contient une entrée par fichier ; la matrice de périmètre ci-dessous distingue les indications présentes et les questions restantes. Une occurrence du mot « licence » n'est pas une concession effective : cet indicateur ne suffit jamais à conclure juridiquement.

**FICHIER / LIGNE :** `README.md:33` et `:103`, déclarations ; `compta_lmnp/seed_referentiel.sql:1`, `compta_lmnp/schema.sql:1`, `compta_lmnp/seed_demo.sql:1`, en-têtes ; `docs/audit/00-INVARIANTS.md:1`, document. Pas de fonction concernée par ces déclarations.

**CONSÉQUENCE :** un réutilisateur ne peut pas lire une réponse explicite sur les catégories non-code ou sur d'éventuels droits de base de données. **L'AGPL racine n'est ni présumée exclure ces fichiers ni présumée suffire à régler tous les droits tiers.** Aucun droit de propriété sur les données personnelles saisies par l'utilisateur n'est déduit de cette ambiguïté.

**CORRECTION MINIMALE :** ajouter un paragraphe central définissant ce que couvre la licence du dépôt, les données d'exemple, la documentation et les exceptions tierces ; documenter séparément les origines incertaines. Les identifiants SPDX seraient un complément de traçabilité, pas une obligation juridique inventée.

### R-07 — Trois liens du texte de licence diffèrent du canonique FSF actuel

**TYPE : AMELIORATION_DOCUMENTAIRE.**

**GRAVITÉ : mineur.**

**PROMESSE / OBLIGATION TESTÉE :** `LICENSE` est annoncé comme texte intégral de référence et le ZIP doit en livrer une copie fidèle.

**SCÉNARIO REPRODUCTIBLE :** télécharger le [texte canonique FSF](https://www.gnu.org/licenses/agpl-3.0.txt), puis comparer les octets au fichier racine et au `LICENSE.txt` du ZIP :

```sh
curl -fsSL https://www.gnu.org/licenses/agpl-3.0.txt -o /tmp/audit_r_agpl.txt
.venv/bin/python docs/preuves_r/reproduire.py
```

**ATTENDU :** égalité avec le canonique courant, ou provenance documentée d'une édition antérieure identique sur le fond.

**PRODUIT :** dépôt **34 520 octets**, canonique **34 523** ; égalité brute `false`, égalité après remplacement de `http://` par `https://` **`true`**. Les trois seuls écarts sont à la ligne 4 (`fsf.org`) et aux lignes 646 et 661 (`gnu.org/licenses`). Le ZIP est strictement identique à la racine.

**PREUVE :** `preuves_r/resultats.json`, rubrique `licence`, avec SHA-256 des deux fichiers. L'intégralité des clauses, dont l'article 13, est présente ; aucune substitution par un résumé, suppression de clause ou modification des permissions n'est constatée.

**FICHIER / LIGNE :** `LICENSE:4`, `:646`, `:661`, texte documentaire ; `compta_lmnp/construire_distribution.py:89`, fonction `construire`, copie livrée.

**CONSÉQUENCE :** une comparaison exacte au fichier FSF courant échoue. L'écart est compatible avec une ancienne édition des URL ; l'audit ne prouve pas une altération volontaire et ne conclut **ni à une licence tronquée ni à l'invalidité de la concession**.

**CORRECTION MINIMALE :** reprendre le canonique actuel ou documenter la provenance exacte de la copie, puis conserver la comparaison de l'artefact complet plutôt que quelques titres de sections.

## Régime annoncé et traçabilité par catégorie

| Catégorie | Ce que le dépôt affirme réellement | Lecture de l'audit |
|---|---|---|
| Code Python de production | SPDX AGPL-3.0-or-later, LICENSE racine | Régime expressément déclaré ; fragments orphelins R-05 |
| CSS, JavaScript, HTML et SVG dans `pages.py` | Dans un module portant SPDX AGPL | Déclaration du fichier englobant ; provenance externe exhaustive non établie |
| Lanceurs `.sh`, `.bat`, `.desktop` | Livrés avec le logiciel AGPL, sans en-tête individuel | Traçabilité à améliorer ; absence de SPDX seule sans contradiction |
| SQL de schéma et scripts de seed | Scripts livrés ; pas de notice individuelle | Rattachement global plausible ; distinguer code SQL et contenu des données, R-06 |
| Plan de comptes et référentiel | Référentiel générique ; comptes LMNP | Pas de source détaillée ou de régime distinct déclaré ; question de provenance |
| Gabarits d'écritures | SPDX du module ; commentaire expliquant une sélection issue d'exercices de référence et de charges déductibles | Licence du code déclarée ; origine de la sélection et des libellés à préciser |
| Données de démonstration/FEC | Exemples distribuables ; pas de régime spécifique | R-06 ; ne pas confondre exemple publié et données réelles exclues |
| Documentation d'accueil et architecture | AGPL annoncée pour le logiciel | Portée documentaire non explicitée ; pas d'exclusion démontrée |
| Rapports, prompts et preuves `docs/` | Publications du projet ; pas de politique de licence par catégorie | R-06 ; assistance générative et productions externes à documenter |
| États produits pour un utilisateur | Aides à la préparation, non certifiées | Aucune affirmation que la licence du programme impose de publier la comptabilité de l'utilisateur |

Recensement sans SPDX à HEAD : 38 `.md`, 23 `.py` (preuves dans `docs/`), 19 `.json`, 16 `.txt`, 14 `.pdf`, 4 fichiers sans extension, 4 `.html`, 3 `.sql`, 2 `.sh`, 1 `.yml`, 1 `.bat`, 1 `.desktop`, 1 `.toml`. Le fichier de licence lui-même figure parmi ceux sans SPDX : illustration de la raison pour laquelle ce compteur **n'est pas** un test juridique. Le détail exhaustif est dans l'annexe JSON, pas dans une énumération manuelle prétendument complète.

## Ce qui a été vérifié et tenu

- **Texte et livraison :** une seule source de licence au sommet du dépôt ; 661 lignes ; toutes les clauses sont présentes et le ZIP en reçoit une copie identique. Les notices sont également présentes. Le défaut R-07 ne touche que trois protocoles d'URL.
- **Distribution réelle :** les 45 entrées sont 32 `.py`, 3 `.sql`, 2 `.txt`, 1 `.sh`, 1 `.bat`, 1 `.desktop`, 4 `.md` et `VERSION`. Aucun wheel, bibliothèque native, exécutable, police, dossier `site-packages`, fichier CSS/JS minifié ou PDF n'est dans le ZIP. Aucun composant Python installé n'y a été retrouvé. L'absence de copie des licences Flask/ReportLab dans ce ZIP n'est donc pas signalée comme un manquement.
- **Licences principales vérifiées :** Flask 3.1.3 déclare BSD-3-Clause ; son `LICENSE.txt` contient les trois conditions. ReportLab 5.0.1 annonce BSD dans ses métadonnées ; son fichier `LICENSE` confirme les trois conditions. Leurs exigences de conservation de notices concernent aussi la redistribution **source**, pas seulement les binaires. La phrase de la notice centrée sur le binaire doit être lue avec cette réserve ; aucune bibliothèque vendorisée en source n'a été trouvée ici.
- **Ressources locales :** `outils_sprite.svg_complet` régénère exactement le SVG inclus dans `pages.ASSISTANT`. Cela établit la chaîne de fabrication dans le dépôt, pas une preuve absolue de création indépendante. CSS, JavaScript et SVG sont des chaînes lisibles, sans import de CDN, police web ou feuille distante trouvé dans `pages.py`. L'icône du `.desktop` est un nom d'icône système, pas une image copiée.
- **PDF de preuves :** `pdffonts` sur les 14 PDF suivis par Git retourne Helvetica et Helvetica-Bold, avec incorporation `no`. Pas de redistribution constatée de DarkGarden ou Vera dans ces PDF. La mise en page de `liasse_pdf.generer_pdf` est un état de travail en tableaux ReportLab, annoncé comme tel ; le ZIP n'embarque aucun CERFA graphique.
- **Permissions et forks :** README autorise copie, modification et vente, et demande de conserver les mentions et de signaler les modifications. Aucun workflow supprimant les mentions n'a été trouvé. Le changement de nom d'un fork est présenté comme un usage destiné à éviter la confusion, pas comme une preuve de marque déposée. Le lien source peut être remplacé simplement dans `_base`.
- **Ancien modèle :** les passages historiques du changelog expliquent l'ancienne licence ; ce ne sont pas des restrictions actuelles. Les mentions du modèle antérieur dans les audits et tests ne sont pas traitées comme concessions contradictoires. La formule « tous droits réservés » des licences tierces ne suffit pas non plus à établir une contradiction.

### DCO : procédure disponible, acceptation extérieure non démontrée

`CONTRIBUTING.md:49` nomme le DCO **1.1**, donne `git commit -s`, décrit `Signed-off-by` et renvoie au [texte DCO accessible](https://developercertificate.org/). Le DCO est une certification d'origine, pas une cession. L'historique donne matière à vérifier les trailers : **46 commits, 6 couples nom/adresse distincts pseudonymisés, zéro Signed-off-by**. Il serait faux d'en déduire six contributeurs extérieurs ou 46 infractions.

La règle apparaît au commit `a14f99cd898e94e7cfc551ee57bf09c279d3536b`. Les deux commits postérieurs, `9a6ea443c114130d0a2d0eb21a0a28005a5d670d` et HEAD, ont la même identité Git que celui qui introduit la règle et aucun trailer. Aucune contribution extérieure acceptée après l'introduction n'est établie. Le défaut demandé « contribution extérieure acceptée sans DCO » **n'est pas retenu**. Si le mainteneur veut appliquer la formulation « chacun de vos commits » à ses propres commits, il doit clarifier cette portée et appliquer sa convention.

La CI et le hook fournis ne contrôlent pas les trailers ; la documentation décrit comment signer, mais ne décrit pas qui vérifie les signatures avant acceptation. Un contrôle manuel reste possible et n'est pas réfuté par l'absence d'automatisation. État exact : **procédure de signature prête, contrôle d'acceptation non documenté dans les pièces, pratique extérieure non éprouvée par cet historique**. La formule anticipant « les contributeurs » est une question de formulation, pas une violation établie.

### Actifs fiscaux et références examinés

`liasse_pdf.py:146` (`generer_pdf`) réutilise des identifiants de formulaires, numéros de cases et libellés : 2031/2031 bis, 2033-A/B/C, aides 2042-C-PRO. Les nombres de cases sont des références factuelles ; les libellés sont du texte ; le regroupement des tableaux est une sélection/organisation. La présentation observée est propre à l'état de travail, sans image du formulaire officiel. La [page officielle 2031](https://www.impots.gouv.fr/formulaire/2031-sd/impot-sur-le-revenu) permet d'identifier les millésimes, mais ne prouve pas la provenance de chaque chaîne de caractères du dépôt.

`fec_io.py:33` et `export_fec.py:16` reprennent la nomenclature des 18 colonnes du FEC, avec référence à l'arrêté A-47 A-1. Cela identifie une source normative ; cela ne constitue pas une preuve de copie d'un logiciel tiers.

`veille_fiscale.py:34` (`CORPUS`) fournit des références et des résumés reliés aux modules, datés par `CORPUS_REVU_LE`. `parametres.py:37` (`REGLES_DEFAUT`) associe valeurs, références et commentaires synthétiques. `pense_bete.py` contient des conseils rédigés, des paraphrases et de courtes désignations normatives — par exemple le libellé du compte 275 — avec certaines sources dans `OUBLIS_FREQUENTS`. Les sources citées ne sont pas toutes des permaliens vers une version archivée. Aucun corpus intégral permettant d'attribuer chaque formulation, phrase par phrase, n'est fourni.

La [notice officielle 2031 de 2026](https://www.impots.gouv.fr/sites/default/files/formulaires/2031-sd/2026/2031-sd_5396.pdf) confirme notamment le principe de report vers la déclaration complémentaire et donne des seuils pour **2025** ; elle ne valide pas à elle seule les seuils de toute année future. Le [BOFiP sur les actifs](https://bofip.impots.gouv.fr/export/pdf/2801) documente une tolérance de faible valeur sous conditions. Ces recoupements ne sont pas une validation exhaustive des résumés fiscaux. Aucune nouvelle divergence matérielle avec conséquence exécutée n'est retenue dans cette passe ; les questions de périmètre, de formulation et de provenance restent ci-dessous.

Le commentaire de `gabarits.py:11` nomme comme source de sélection les exercices 2023–2025 et des charges déductibles ; il ne dit pas qui a conçu tous les libellés et comptes détaillés. `seed_referentiel.sql:14` livre une sélection LMNP, pas un PCG intégral identifié par édition. Ce sont des questions d'origine à documenter, **pas des indices suffisants de copie illicite**. Aucune attribution à Stack Overflow ou à un dépôt externe n'a été démontrée par une correspondance vérifiée. Un style idiomatique ou différent n'est pas une telle preuve.

Les références Windows, macOS et Linux désignent des plateformes ; PayPal désigne le moyen de don. Aucune affiliation ou certification par ces tiers n'a été constatée dans les documents examinés. « Remplacer les logiciels du marché », dans `LISEZ-MOI.md:11`, exprime une ambition générale sans concurrent nommé ni comparaison chiffrée à cet endroit. Le README exclut explicitement la certification des états. Aucune allégation de marque déposée n'est formulée : `README.md:103` affirme le contraire.

## Non vérifiable avec les pièces fournies

### QJ-1 — Contributions assistées par IA

**TYPE : QUESTION_JURIDIQUE.**

**FAITS ÉTABLIS :** le dépôt contient des rapports et prompts d'audit faisant intervenir l'assistance générative ; le logiciel revendique une titularité et une licence générale. L'historique fourni n'attribue pas chaque fragment à une origine humaine ou générative.

**POINT NON TRANCHABLE DANS LE DÉPÔT :** quelles créations sont protégeables, et quels droits sont effectivement détenus sur chacune ?

**QUESTION À SOUMETTRE AU CONSEIL :** quelles contributions ont été produites avec assistance générative, quelle part des choix créatifs, de l'architecture, de la sélection, de l'adaptation et de la rédaction finale peut être documentée comme humaine, et cette provenance affecte-t-elle la titularité revendiquée ou la capacité à concéder l'AGPL sur tout ou partie du dépôt ?

**PIÈCES UTILES À FOURNIR :** historique de travail pertinent expurgé, versions intermédiaires, outils et conditions applicables, traces de sélection et de réécriture humaine. Pas de gravité de non-conformité attribuée.

### QJ-2 — Référentiels, textes et formulaires

**TYPE : QUESTION_JURIDIQUE.**

**FAITS ÉTABLIS :** nombres et intitulés de cases, structure FEC, sélection de comptes, résumés fiscaux et gabarits sont incorporés ; la mise en page PDF n'est pas un fac-similé CERFA. Certaines références sont identifiées, sans dossier de provenance par élément.

**POINT NON TRANCHABLE DANS LE DÉPÔT :** quels droits et conditions de réutilisation s'appliquent à chaque reprise, en distinguant faits, texte, sélection d'une base et présentation ?

**QUESTION À SOUMETTRE AU CONSEIL :** quelles sources exactes ont servi aux libellés et à la sélection des comptes/gabarits, quelles conditions de réutilisation sont applicables aux documents administratifs effectivement employés, et faut-il distinguer des droits de base de données de la licence du code ?

**PIÈCES UTILES À FOURNIR :** éditions des textes et formulaires sources, conditions de réutilisation associées, note sur les adaptations, autorisations éventuelles du producteur d'un référentiel externe. Aucune condition juridique n'est déduite par analogie avec un autre site administratif.

### QJ-3 — Nom, marque et gouvernance

**TYPE : QUESTION_JURIDIQUE.**

**FAITS ÉTABLIS :** nom déclaré non déposé ; invitation à renommer un fork substantiel ; anticipation des contributeurs dans la mention de copyright ; absence de contribution extérieure postérieure au DCO démontrée.

**POINT NON TRANCHABLE DANS LE DÉPÔT :** quels droits sur le nom existent indépendamment d'un dépôt, et quelle portée donner aux formulations de gouvernance ?

**QUESTION À SOUMETTRE AU CONSEIL :** la formulation actuelle distingue-t-elle assez clairement licence, prévention de la confusion et éventuels droits sur le nom, sans créer une restriction supplémentaire involontaire ?

**PIÈCES UTILES À FOURNIR :** politique de nommage souhaitée, éventuelles recherches d'antériorité, règles d'acceptation des contributions. Aucune conclusion sur la distinctivité ou le dénigrement n'est prononcée.

Autres questions techniques non résolues :

- Quelle source publiquement accessible correspondra exactement à 8.51.1, et quel contrôle constatera son accessibilité après ouverture du dépôt ?
- Les six identités Git sont-elles des alias du mainteneur, des importations ou des contributions extérieures ? Existe-t-il des revues DCO privées ou des certificats d'origine non présents dans les commits ?
- Quelles versions de cryptography et de ses dépendances sont réellement installées par le parcours HTTPS, sur chaque plateforme ? Quelles versions conditionnelles, notamment colorama sous Windows, sont résolues ?
- Quelles sont les origines des polices supplémentaires de ReportLab et de chaque composant natif des wheels effectivement installés ? Les fichiers de licence agrégés permettent-ils une correspondance exhaustive composant/version/conditions ?
- Quelle revue de l'historique complet précédera sa publication, notamment pour les fichiers supprimés, anciens livrables et messages de commit ? Le contrôle local du contenu courant ne constitue pas cette preuve historique.
- Quelles pièces permettent d'établir l'origine indépendante des fragments HTML/CSS/JavaScript et des libellés au-delà de la déclaration de l'auteur et de la chaîne de génération du sprite ?

## Matrice des promesses du dépôt

| Promesse / déclaration | Où est-elle formulée ? | Comment a-t-elle été testée ? | Résultat | Constat associé |
|---|---|---|---|---|
| Texte intégral AGPL faisant foi | README:35, LICENSE | Comparaison FSF complète + ZIP | Clauses intégrales ; trois URL anciennes | R-07 |
| Licence et notices livrées | Construire_distribution:55 | Construction et lecture de 45 entrées | Présentes, licence identique | Tenu |
| Liens documentaires utilisables | LISEZ-MOI:4, 590, 607, 615 | Résolution dans le ZIP extrait | Cinq occurrences cassées | R-04 |
| Accès au code source | App `_base`:605 | Rendu HTTP 200 puis requête anonyme au lien | Lien présent, destination 404 | R-01 |
| Liberté de modifier et vendre | README:40 ; LISEZ-MOI:592 | Lecture des déclarations et de tous les en-têtes distribués | Permission annoncée ; fragments orphelins | R-05 |
| Inventaire des dépendances | NOTICES:9 ; README:110 | Imports, scripts, METADATA et licences installées | Trois dépendances d'exécution manquent | R-03 |
| Aucun composant à réciprocité utilisé | NOTICES:21 | Exécution du lecteur PDF et licence système | Contredit par Poppler ; ressources de paquets à distinguer | R-02 |
| Aucun paquet tiers dans le ZIP | NOTICES:28 | Inventaire réel, sources lisibles et extensions | Aucun paquet tiers trouvé ; provenance exhaustive des fragments non certifiée | Tenu dans cette limite |
| DCO 1.1 et signature de chaque contribution | CONTRIBUTING:49 | Lien DCO, historique pseudonymisé, CI/hook | Procédure accessible ; acceptation extérieure non démontrée | Question, pas infraction |
| Conserver mentions et signaler modifications | README:48 | Instructions et construction | Aucun effacement/instruction contraire trouvé | Tenu dans le périmètre |
| Logiciel sous AGPL | README:33 ; NOTICES:3 | Recensement de tous les fichiers suivis | Code explicite ; catégories non-code à préciser | R-06 |
| Nom non déposé, états non certifiés | README:22, 103 | Lecture contextualisée et ressources rendues | Aucune prétention contraire constatée | QJ-3, sans non-conformité |

## Matrice des composants tiers

**Légende :** D = direct ; T = transitif ; « installé » signifie fourni par un index ou le système, **pas redistribué par ce projet**. « Notice nécessaire » décrit une éventuelle redistribution du composant ; aucune obligation de copie dans le ZIP n'est déduite de sa simple installation. « Notice présente » distingue notice du projet et texte du paquet installé. Les versions sont celles observées, non une garantie des résolutions futures des lanceurs non épinglés.

| Composant | D / T | Nécessaire à l'exécution / installé par le client | Installé / redistribué, vendorisé | ZIP | Licence déclarée par le projet | Licence vérifiée / source | Notice nécessaire | Notice présente |
|---|---|---|---|---|---|---|---|---|
| Python 3.14.6 | D | Oui / prérequis utilisateur | Système / non | Non | PSF | Licence de cette construction non auditée intégralement | Selon distribution de l'interpréteur | Projet : oui ; pile système non certifiée |
| Flask 3.1.3 | D | Oui / lanceurs | Installé / non | Non | BSD-3 | BSD-3 ; METADATA + `flask-*.dist-info/licenses/LICENSE.txt` | Si redistribution | Projet + paquet |
| Werkzeug 3.1.8 | D et T Flask | Oui / résolution pip | Installé / non | Non | BSD-3 | BSD-3 ; METADATA + LICENSE.txt | Si redistribution | Projet + paquet |
| Jinja2 3.1.6 | T Flask | Oui / résolution pip | Installé / non | Non | BSD-3 | BSD-3 ; fichier LICENSE.txt à trois conditions | Si redistribution | Projet + paquet |
| MarkupSafe 3.0.3 | D et T | Oui / résolution pip | Installé / non | Non | BSD-3 | BSD-3 ; METADATA + LICENSE.txt | Si redistribution | Projet + paquet |
| itsdangerous 2.2.0 | T Flask | Oui / résolution pip | Installé / non | Non | BSD-3 | BSD-3 ; fichier LICENSE.txt | Si redistribution | Projet + paquet |
| click 8.4.2 | T Flask | Oui / résolution pip | Installé / non | Non | BSD-3 | BSD-3 ; METADATA + LICENSE.txt | Si redistribution | Projet + paquet |
| blinker 1.9.0 | T Flask | Oui / résolution pip | Installé / non | Non | MIT | MIT ; fichier LICENSE.txt | Si redistribution | Projet + paquet |
| ReportLab 5.0.1 | D | PDF facultatif / lanceurs | Installé / non | Non | BSD-3 | BSD-3 pour le code principal ; METADATA + LICENSE | Si redistribution ; ressources séparées | Projet + paquet |
| Pillow 12.3.0 | T ReportLab | Dépendance PDF / pip | Installé avec bibliothèques natives / non | Non | Absente | MIT-CMU principal ; METADATA + LICENSE composite | Si redistribution, y compris bibliothèques incorporées | Projet : non ; paquet : oui |
| charset-normalizer 3.5.1 | T ReportLab | Dépendance PDF / pip | Installé / non | Non | Absente | MIT ; METADATA + LICENSE | Si redistribution | Projet : non ; paquet : oui |
| cryptography | D conditionnel | Génération HTTPS / Unix `--https` | Installation demandée, absent du venv / non | Non | Absente | Non vérifiée pour un paquet effectif | À déterminer sur l'artefact résolu | Projet : non |
| colorama | T conditionnel click/pytest | Windows / résolution conditionnelle | Absent de l'environnement Linux / non | Non | Absente | Non vérifiée localement | À déterminer | Non vérifiée |
| pytest 9.1.1 | D développement | Non serveur / non client | Venv développement / non | Non | Absente | MIT ; METADATA + LICENSE | Si redistribution | Paquet seulement |
| ruff 0.16.0 | D développement | Non serveur / non client | Venv développement, binaire / non | Non | Absente | MIT principal ; fichier composite LICENSE | Si redistribution avec ses composants | Paquet seulement |
| iniconfig 2.3.0 | T pytest | Non serveur / non client | Venv développement / non | Non | Absente | MIT ; METADATA + LICENSE | Si redistribution | Paquet seulement |
| packaging 26.2 | T pytest | Non serveur / non client | Venv développement / non | Non | Absente | Apache-2.0 OU BSD-2 ; METADATA + textes des deux licences | Si redistribution, selon option | Paquet seulement |
| pluggy 1.6.0 | T pytest | Non serveur / non client | Venv développement / non | Non | Absente | MIT ; fichier LICENSE | Si redistribution | Paquet seulement |
| Pygments 2.20.0 | T pytest | Non serveur / non client | Venv développement / non | Non | Absente | BSD-2 ; METADATA + LICENSE | Si redistribution | Paquet seulement |
| pip et composants vendorisés | D installation | Installation / venv et mise à jour lanceurs | Installé, vendors dans pip / non | Non | Absente | Inventaire ci-dessous ; analyse juridique exhaustive non effectuée | Par composant si redistribué | Textes dans pip ; pas dans notice projet |
| Poppler / pdftotext 26.01.0 | D contrôle/tests | Non serveur ; contrôle PDF / CI, outil local | Système / non | Non | Absente, déclaration générale contraire | GPL et autres termes ; RPM + `/usr/share/licenses/poppler/COPYING` | Si redistribution | Système seulement |
| OpenSSL 3.5.7, SQLite 3.51.2 | T environnement Python | TLS / stockage ; préexistants | Système / non | Non | Pas d'inventaire séparé | Versions exécutées ; licences de la construction système non auditées | Selon artefacts effectivement redistribués | Non vérifiée intégralement |
| Actions checkout@v7, setup-python@v6 | D CI externe | Non / runner seulement | Résolution GitHub Actions / non | Non | Absente | Sources résolues non fournies localement | Selon usage/redistribution à examiner | Non vérifiée |

Les dépendances d'extras non demandés de ReportLab (`rl_accel`, `rlPyCairo`, `freetype-py`, `rlbidi`, `uharfbuzz`) figurent dans les métadonnées, mais ne sont pas installées dans ce venv ni demandées par les lanceurs : elles ne sont pas qualifiées de composants effectivement utilisés. Même distinction pour les dépendances conditionnelles des anciennes versions de Python.

**Composants incorporés dans les paquets installés, absents du ZIP :**

| Composant | Direct / transitif | Nécessaire / installé client | Redistribué par le projet / vendorisé ailleurs | Licence vérifiée / source | Notice présente |
|---|---|---|---|---|---|
| DarkGarden | T, ressource ReportLab | Usage non établi / installé avec ReportLab | Non / oui dans ReportLab | GPL-2.0-or-later avec exception documentaire ; `DarkGarden-copying.txt` | Texte et GPL dans le paquet ; absent de la notice projet |
| Bitstream Vera, quatre TTF | T, ressources ReportLab | Usage non établi / installé avec ReportLab | Non / oui dans ReportLab | Licence Bitstream Vera, attribution et conditions spécifiques de nommage/vente isolée ; `bitstream-vera-license.txt` | Paquet seulement |
| Autres Type 1/AFM et `hb-test.ttf` de ReportLab | T, ressources | Usage précis non établi / installés | Non / oui dans ReportLab | Pas de correspondance exhaustive fichier/origine/licence établie | À compléter avant redistribution de ces ressources |
| Icônes Silk de Werkzeug debug | T, ressources | Débogueur seulement / installées avec Werkzeug | Non / oui dans Werkzeug | CC-BY-2.5 OU CC-BY-3.0 ; `werkzeug/debug/shared/ICON_LICENSE.md` | Paquet seulement |
| Bibliothèques natives du wheel Pillow | T, code incorporé | Selon fonctionnalités / installées avec Pillow | Non / oui dans wheel | LICENSE composite lu ; attribution exacte de chaque binaire non certifiée | Textes composites du wheel |

Les 18 bibliothèques natives recensées dans `pillow.libs` sont : libXau, libavif, libbrotlicommon, libbrotlidec, libfreetype, libharfbuzz, libjpeg, liblcms2, liblzma, libopenjp2, libpng16, libsharpyuv, libtiff, libwebp, libwebpdemux, libwebpmux, libxcb et libzstd. Leur seule présence n'est pas assimilée à de la redistribution par Compta LMNP. **Contre-exemple utile :** la licence composite de Pillow mentionne la GPL à propos d'outils et fichiers de construction XZ, mais précise qu'ils n'entrent pas dans les binaires ; cela n'établit pas que liblzma installé est GPL.

`pip/_vendor/vendor.txt` recense CacheControl, distlib, distro, msgpack, packaging, platformdirs, pyproject-hooks, requests, certifi, idna, urllib3, rich, pygments, resolvelib, setuptools, tomli, tomli-w, truststore et dependency-groups. Cet inventaire montre pourquoi `pip freeze` seul n'est pas exhaustif. L'audit ne transforme pas leur présence dans l'installateur externe en obligation de les joindre au ZIP, et ne certifie pas toutes leurs licences incorporées.

## Matrice des actifs non-code

| Actif | Origine connue ? | Régime déclaré ? | Redistribué ? | Risque / question | Constat associé |
|---|---|---|---|---|---|
| Sprite SVG de l'assistante | Générateur local reproduit à l'identique | AGPL du module | Oui, dans `pages.py` | Création initiale indépendante non prouvée par le seul générateur | QJ-1 |
| CSS / JS / gabarits HTML | Sources locales lisibles ; pas de CDN identifié | AGPL du module | Oui | Provenance externe exhaustive non attestée | Question technique |
| Icône du lanceur desktop | Nom d'icône système | Pas de fichier image livré | Non pour l'icône | Pas d'obligation de notice d'image copiée démontrée | Aucun |
| Cases 2031/2033/2042 et libellés | Références administratives identifiées | Pas de régime distinct de reprise | Oui, chaînes et sorties | Distinguer faits, texte et sélection | QJ-2 |
| Présentation PDF | Tableaux et styles locaux ReportLab | Module AGPL | Code livré ; états générés | Aucun fac-similé CERFA incorporé constaté | QJ-2 |
| Colonnes FEC | Arrêté A-47 A-1 cité | Module AGPL | Oui | Nomenclature normative, pas preuve de code copié | QJ-2 |
| Textes pense-bête / veille / paramètres | Références CGI/BOFiP/PCG ; sources pas toutes versionnées | Modules AGPL | Oui | Distinguer résumés, libellés et citations exactes | QJ-2 |
| Plan de comptes / seed référentiel | Sélection LMNP ; origine détaillée incomplète | Déclaration générale du logiciel | Oui | Régime et provenance de la sélection | R-06, QJ-2 |
| Gabarits d'écritures | Sources de sélection décrites dans le module | AGPL du module | Oui | Provenance de tous les libellés non établie | QJ-2 |
| Démonstration SQL/FEC | Exemple destiné à distribution | Régime des données non explicité | Oui | Couverture des données distincte du code SQL | R-06 |
| Rapports, prompts, JSON, HTML et PDF de `docs/` | Chaîne de preuves locale, assistance générative mentionnée | Pas de portée documentaire explicite | Dépôt, pas ZIP client | Titularité et régime des rapports ; PDF sans police incorporée vérifiés | R-06, QJ-1 |
| DarkGarden, Vera, autres polices | Origines partielles via licences des paquets | Régimes distincts de BSD ReportLab | Installées, pas redistribuées ici | Usage/incorporation à vérifier si évolution du PDF | R-02, questions |
| Icônes Silk | Attribution dans Werkzeug | CC-BY-2.5 OU CC-BY-3.0 | Installées, pas ZIP | Attribution si redistribution future | Questions |
| PDF administratif présent hors fichiers suivis | Pas traité comme contenu publié | Non établi | Absent du ZIP et de `git ls-files` | Quel statut et quelle destination prévus ? | Non vérifiable |

## Matrice des zones non vérifiables

Chaque ligne formule une question restant ouverte ; aucune ne constitue un verdict de conformité par défaut.

| Sujet | Pourquoi non vérifiable ? | Pièce manquante | Peut bloquer la publication ? | Action recommandée |
|---|---|---|---|---|
| Quelle part des créations est humaine et quels droits en découlent ? | Historique Git insuffisant pour la titularité | Dossier de création expurgé, conditions des outils | À apprécier par le conseil | Préparer QJ-1 |
| D'où viennent chaque libellé, compte et sélection de gabarits ? | Commentaires généraux, pas d'attribution élémentaire | Sources et note d'adaptation | Potentiellement si origine incompatible établie ; pas établi ici | Cartographier les sources |
| Quel régime appliquer aux reprises administratives ? | Conditions exactes de chaque source non réunies | Éditions et conditions de réutilisation | À déterminer juridiquement | Préparer QJ-2 sans analogie automatique |
| Les identités Git représentent-elles des contributions extérieures ? | Six identités ne prouvent pas six personnes | Correspondance d'alias, revues, attestations | Si droits d'une contribution nécessaires non établis | Faire une revue confidentielle, ne publier aucune adresse |
| Un contrôle DCO manuel fonctionne-t-il ? | Aucun journal de revue fourni | Procédure et acceptations documentées | À mettre en place avant contributions extérieures | Nommer le vérificateur et le geste attendu |
| Quels paquets sont résolus sous Windows et en HTTPS ? | Venv Linux sans cryptography/colorama | Inventaires d'installations isolées par plateforme | Pas un blocage juridique démontré du ZIP sans dépendances | Compléter la matrice sur installations réelles |
| Quelles licences couvrent tous les binaires/ressources des wheels ? | Textes composites, cartographie incomplète | Inventaire des builds natifs et des polices | Oui avant redistribution de ces wheels ; pas démontré pour le ZIP actuel | Analyser les artefacts si le périmètre change |
| Les sources promises resteront-elles celles de la version distribuée ? | Lien racine actuellement 404, aucun tag local | Source publique correspondante et contrôle d'accès | Oui pour annoncer l'offre de source comme opérationnelle | Résoudre R-01 puis vérifier anonymement |
| L'historique entier peut-il être rendu public sans fuite ni ancien actif problématique ? | Cette passe n'a pas certifié chaque ancien blob/message | Revue historique expurgée et périmètre à publier | Oui pour une publication irréversible | Contrôler les objets effectivement poussés, pas seulement l'arbre courant |
| Quelles licences précises pour la pile système et les actions CI résolues ? | Non incorporées au ZIP, builds externes non analysés intégralement | Sources et métadonnées des constructions concernées | Selon redistribution future ; non établi ici | Borner honnêtement les déclarations générales |

## Tableau récapitulatif numéroté

| N° | Type | Gravité | Écart prouvé | Correction minimale |
|---|---|---|---|---|
| R-01 | OBLIGATION_NON_REMPLIE | Majeur | Lien source rendu, destination anonyme 404 | Rendre la source correspondante accessible et tester le lien |
| R-02 | CONTROLE_NON_DEMONTRE | Majeur | Assurance sans GPL contredite par Poppler exécuté | Inventaire borné distinguant outils, installation et redistribution |
| R-03 | NOTICE_TIERS_INCOMPLETE | Mineur | Pillow, charset-normalizer et chemin cryptography omis | Compléter depuis les métadonnées et parcours optionnels |
| R-04 | AMELIORATION_DOCUMENTAIRE | Mineur | Cinq liens de l'accueil cassés dans le ZIP | Adapter les cibles au livrable autonome |
| R-05 | AMELIORATION_DOCUMENTAIRE | Mineur | Vingt en-têtes distribués gardent une réserve orpheline | Supprimer les fragments ; relire les en-têtes |
| R-06 | PERIMETRE_DE_LICENCE_AMBIGU | Mineur | Couverture documentaire des catégories non-code non explicitée | Déclaration centrale de périmètre et exceptions |
| R-07 | AMELIORATION_DOCUMENTAIRE | Mineur | Trois URL HTTP différentes du canonique FSF actuel | Actualiser ou tracer l'édition du texte |

Les trois questions juridiques ne reçoivent aucune gravité de non-conformité et ne sont pas comptées comme anomalies. Les affirmations non vérifiables ne sont pas assimilées à des faits de copie illicite ou à des obligations déjà violées.

---

## Suivi des correctifs

Traitement du 16 septembre 2026, version **8.52.0**. **Les sept constats sont
confirmés** — aucun n'a été annulé après vérification par exécution. Chacun a
été reproduit avant correction, puis re-vérifié après.

| N° | État | Correctif | Test de non-régression |
|---|---|---|---|
| R-01 | **Partiellement corrigé** — le reste n'est pas du ressort du code | Le README porte une liste de contrôle avant ouverture du dépôt, et dit explicitement le 404 actuel. Le test de l'offre de source vérifie désormais la FORME de l'URL et déclare ne pas prouver son accessibilité | `test_r01_le_pied_de_page_offre_une_url_de_source_bien_formee`, `test_r01_la_liste_de_controle_avant_publication_est_ecrite` |
| R-02 | **Corrigé** | La négation absolue disparaît. `NOTICES-TIERS.md` distingue **redistribué / installé / exécuté**, nomme Poppler et sa GPL, et explique pourquoi un appel en sous-processus n'affecte pas la licence de l'application. La police DarkGarden de reportlab est documentée comme non utilisée | `test_r02_aucune_affirmation_absolue_d_absence_de_reciprocite`, `test_r02_poppler_est_nomme_avec_son_regime` |
| R-03 | **Corrigé** | Pillow 12.3.0 (MIT-CMU), charset-normalizer 3.5.1 (MIT) et cryptography (conditionnel HTTPS) ajoutés, avec versions vérifiées et mode d'installation | `test_r03_les_dependances_declarees_figurent_toutes_dans_les_notices`, `test_r03_la_dependance_conditionnelle_du_https_est_declaree` |
| R-04 | **Corrigé** | Les liens sont réécrits à la construction ; le paquet livre en outre `README.md` et `CONTRIBUTING.md`. Une garde résout **tous** les liens locaux du zip et détruit le paquet s'il en pend un | `test_r04_aucun_lien_local_mort_dans_le_paquet`, `test_r04_le_paquet_livre_la_licence_et_les_conditions` |
| R-05 | **Corrigé** | Les 25 lignes orphelines supprimées, et surtout la garde remplacée | `test_r05_chaque_source_porte_exactement_len_tete_attendue` |
| R-06 | **Corrigé** | Le README porte un tableau de périmètre par catégorie, et deux réserves nommées : nomenclature du PCG et cases des formulaires administratifs | `test_r06_le_perimetre_de_la_licence_couvre_chaque_categorie` |
| R-07 | **Corrigé** | `LICENSE` remplacé par le canonique FSF, SHA-256 `0d96a4ff68ad6d4b6f1f30f713b18d5184912ba8dd389f86aa7710db079abcb0` | `test_r07_la_licence_est_le_canonique_fsf_a_l_octet_pres`, `test_r07_la_copie_livree_est_identique_a_la_racine` |

### Ce que R-05 condamne, et qui dépasse R-05

L'ancien en-tête propriétaire tenait sur **trois** lignes. La migration AGPL
en a supprimé deux par correspondance exacte, et la troisième — `# sans
autorisation écrite de l'auteur.` — est restée dans 25 fichiers, juste sous
l'identifiant SPDX qui autorise la modification.

La garde écrite en même temps que la migration cherchait une **liste de motifs
interdits**, où ce fragment ne figurait pas : elle passait au vert. C'est
l'invariant n°5 appliqué à celui qui croyait s'en prémunir — et la leçon ne
porte pas sur la liste, mais sur la méthode. La garde vérifie désormais que le
bloc de commentaires de tête vaut **exactement** les deux lignes attendues, et
signale tout le reste quel qu'en soit le texte : « le total moins ce qui est
identifié », plutôt qu'une énumération de ce qu'on a su imaginer.

Deux autres listes écrites à la main ont été supprimées dans la foulée, toutes
deux découvertes **parce qu'un correctif les a cassées** : la table de
réécriture des liens est doublée d'une garde qui relit l'archive entière, et
la copie jetable de `tests/test_passe_f.py` déduit désormais les documents de
racine de `construire_distribution.DOCS` au lieu de les nommer.

### Défauts trouvés par les correctifs, absents du rapport

La garde anti-lien mort, dès sa première exécution, a signalé **huit liens
morts de plus** que les cinq du constat R-04 — ceux de `README.md` et
`CONTRIBUTING.md`, qui n'étaient pas encore livrés dans le paquet au moment de
l'audit et le sont devenus par le correctif. Trois d'entre eux visaient des
répertoires absents du paquet (`docs/`, `.githooks/`) et sont désormais des
liens vers le dépôt : un renvoi honnête vaut mieux qu'un chemin qui pend.

### Les trois questions juridiques

`QJ-1` (contributions assistées par IA), `QJ-2` (référentiels, textes et
formulaires) et `QJ-3` (nom, marque et gouvernance) **ne sont pas traitées
ici**, et c'est délibéré : ce sont des questions d'appréciation juridique, pas
des défauts vérifiables dans le dépôt. Deux d'entre elles reçoivent toutefois
un début de réponse documentaire, sans prétendre trancher :

- le tableau de périmètre du README nomme la nomenclature du PCG et les cases
  des formulaires administratifs comme des réserves explicites (QJ-2) ;
- le README indique que le nom n'est pas déposé et invite les forks
  substantiels à en changer (QJ-3).

`QJ-1` reste entière et appelle un conseil en propriété intellectuelle.

### Vérification finale

`1 162 tests` passent (12 nouveaux pour cette passe), `ruff` est propre, le
paquet client se construit et ne porte aucun lien mort, et le contrôle de
publication conclut au vert.
