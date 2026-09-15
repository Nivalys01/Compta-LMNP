# Couverture de la passe Q

Cette annexe distingue le recensement par analyse du code des scénarios exécutés. Une mention structurelle ne constitue ni un constat supplémentaire ni une certification d’atomicité. Les résultats d’exécution sont dans `resultats.json`.

## Chaque commit et chaque executescript

| Fichier | Fonction | Ligne | Appel | Atteignabilité et examen |
|---|---|---:|---|---|
| app.py | `immobilisations` | 754 | `conn.commit` | Lecture HTTP ; connexion créée dans la vue, commit de préparation du schéma de cession. Pas une connexion empruntée à une autre requête. |
| app.py | `creer_exploitant` | 796 | `conn.commit` | Écriture unitaire ; lecture des exercices après commit. Pas de boucle. |
| app.py | `creer_bien` | 827 | `conn.commit` | Écriture unitaire ; pas de boucle ni appel de lecture externe. |
| app.py | `creer_composant` | 875 | `conn.commit` | Action composée composant puis acquisition ; commit intermédiaire exécuté : Q-07. |
| app.py | `immo_ventiler` | 990 | `conn.commit` | Fin de boucle de composants/acquisitions avec commit=False ; rollback dans except. Pas appelé en lecture. |
| app.py | `composant_duree` | 1037 | `conn.commit` | Écriture unitaire de durée ; pas appelé en lecture. |
| app.py | `exercice_ouvrir` | 1335 | `conn.commit` | Action composée ouverture puis reprise : commit intermédiaire exécuté, Q-11. |
| app.py | `reglementation_compte` | 1492 | `conn.commit` | Création unitaire ; pas de boucle. |
| app.py | `import_valider` | 1921 | `conn.commit` | Fin de boucle de saisies commit=False ; puis suppression faillible : Q-08. Interruption au rang 7 éprouvée. |
| app.py | `exercice_reprendre_fec_multi` | 2022 | `conn.commit` | Fin de boucle ; les rejeux ont déjà validé chaque exercice : Q-09. |
| app.py | `exercice_reprendre_fec` | 2065 | `conn.commit` | Après le rejeu, qui a déjà committé. Écriture de reprise, pas une lecture. |
| modules/amortissement.py | `generer_cloture` | 361 | `conn.commit` | Génération groupée ; commit conditionnel, désactivé par fiscal.cloturer. Éprouvé dans la clôture. |
| modules/audit_cycle.py | `_creer_dossier` | 124 | `conn.commit` | Construction du dossier synthétique de l’audit ; écritures de préparation, pas lecture métier. |
| modules/audit_cycle.py | `phase_2_detection` | 312 | `conn.commit` | Injections d’anomalies de l’audit ; écritures groupées de diagnostic, pas lecteur métier. |
| modules/audit_cycle.py | `phase_4_reprise_et_liasse` | 417 | `conn.commit` | Préparation de la phase de reprise de l’audit ; écritures de diagnostic, pas lecteur métier. |
| modules/cession.py | `ceder_bien` | 168 | `conn.commit` | Fin de plusieurs écritures commit=False ; commit conditionnel. Interruption avant deuxième écriture éprouvée. |
| modules/ecritures.py | `inserer` | 209 | `conn.commit` | Point commun des écritures ; commit conditionnel. Désactivé dans les boucles atomiques ; activé dans l’appel de charges Q-06. |
| modules/fiscal.py | `traiter_deficit` | 199 | `conn.commit` | Écrit plusieurs mouvements de déficits ; commit conditionnel, désactivé pendant la clôture éprouvée. |
| modules/fiscal.py | `cloturer` | 555 | `conn.commit` | Commit final d’une action composée ; un seul appel observé. Pas lecture. |
| modules/gabarits.py | `assurer_table` | 210 | `conn.commit` | Atteint par les lectures de gabarits et chaque saisie ; garde in_transaction éprouvée, ne valide pas le témoin. |
| modules/gabarits.py | `ajouter_personnalise` | 233 | `conn.commit` | Écriture d’une catégorie personnalisée ; pas appelé par le lecteur tous. |
| modules/init_db.py | `_exec` | 54 | `conn.executescript` | executescript d’initialisation (schema et seeds) ; peut valider implicitement. Pas appelé par une lecture courante. |
| modules/init_db.py | `init` | 121 | `conn.commit` | Étapes de création d’une base, mode blanc ou démonstration. Plusieurs commits d’initialisation ; pas fonction de lecture. |
| modules/init_db.py | `init` | 138 | `conn.commit` | Étapes de création d’une base, mode blanc ou démonstration. Plusieurs commits d’initialisation ; pas fonction de lecture. |
| modules/init_db.py | `init` | 141 | `conn.commit` | Étapes de création d’une base, mode blanc ou démonstration. Plusieurs commits d’initialisation ; pas fonction de lecture. |
| modules/init_db.py | `init` | 163 | `conn.commit` | Étapes de création d’une base, mode blanc ou démonstration. Plusieurs commits d’initialisation ; pas fonction de lecture. |
| modules/init_db.py | `_reconstituer_operations` | 245 | `conn.commit` | Fin de boucle de reconstruction depuis les écritures, appelée à l’initialisation démo. Pas lecteur. |
| modules/init_db.py | `creer_index` | 320 | `conn.commit` | Infrastructure appelée pendant init et la boucle de migrations ; commit intermédiaire confirmé par témoin et Q-10. |
| modules/init_db.py | `marquer_version` | 332 | `conn.commit` | Écriture de version appelée après init/migration ; commit non conditionnel. Pas appelée dans la garde de simple lecture. |
| modules/migrations.py | `migrer` | 115 | `conn.commit` | Fin de boucle des paliers ; plusieurs sous-appels ont leur commit. Q-10. |
| modules/operations.py | `saisir` | 95 | `conn.commit` | Commit conditionnel ; boucles import atomique (False) et appel de charges (True). Tous les types testés. |
| modules/operations.py | `annuler` | 397 | `conn.commit` | Fin d’une contre-passation et d’un UPDATE, commit conditionnel ; course Q-02. |
| modules/parametres.py | `assurer` | 123 | `conn.commit` | Atteint par les lecteurs de règles et les calculs groupés ; garde in_transaction éprouvée. |
| modules/parametres.py | `definir` | 174 | `conn.commit` | Mutation versionnée DELETE/UPDATE/INSERT ; pas une lecture. |
| modules/pense_bete.py | `ecrire_notes` | 344 | `conn.commit` | Écriture explicite du bloc-notes ; lire_notes ne l’appelle pas. |
| modules/quittances.py | `assurer_schema` | 55 | `conn.executescript` | Atteint depuis les lecteurs et migrations. executescript puis commit ; Q-01 et Q-10. |
| modules/quittances.py | `assurer_schema` | 56 | `conn.commit` | Atteint depuis les lecteurs et migrations. executescript puis commit ; Q-01 et Q-10. |
| modules/quittances.py | `ajouter_locataire` | 99 | `conn.commit` | Écriture unitaire, précédée de assurer_schema. Pas appelée par le lecteur locataires. |
| modules/quittances.py | `emettre` | 263 | `conn.commit` | Émission du document, précédée de lectures qui committent ; course Q-04. |
| modules/rejeu_fec.py | `rejouer` | 110 | `conn.commit` | Fin de boucle d’écritures ; lui-même dans la boucle multi-exercices, Q-09. |
| modules/reprise.py | `_construire_an_depuis_balance` | 162 | `conn.commit` | Fin du groupe AN et affectation ; interruption éprouvée. Appelé après une ouverture qui a déjà committé. |
| modules/reprise.py | `ouvrir_exercice` | 184 | `conn.commit` | Commit de création avant reprise facultative ; chemin API analogue à Q-11, sortie web utilisée dans le constat. |
| modules/veille_fiscale.py | `enregistrer_veille` | 155 | `conn.commit` | Écriture explicite de la date de veille ; les lecteurs de veille ne l’appellent pas. |

Total : 43 sites, dont 41 appels explicites à commit et 2 appels à executescript. Le classement couvre chaque site de l’inventaire, sans écarter les appels d’infrastructure.

## Chaque except Exception de app.py

« Structure » signifie que le bloc a été inspecté mais que chaque panne possible n’a pas été injectée. Les fermetures normales sont éprouvées par les scénarios ; une panne de close/rollback elle-même n’est pas simulée. Les traitements qui relèvent du bac à sable n’ont jamais été exécutés sur son chemin réel.

| Fonction | Ligne except | État / preuve ou limite |
|---|---:|---|
| `_migrer_si_besoin` | 142 | Exécuté : exception avalée, marqueur retiré, garde autorisant la suite ; Q-10. Le discard ne valide ni ne répare la base. |
| `_garde_version_schema` | 248 | Structure : repli de présentation après fermeture de la connexion de version ; pas de DML dans ce repli. |
| `_erreur_globale` | 302 | Structure : initialisation de journal et rendu de secours ; ne reconstitue pas les transactions déjà validées. Contenu du journal testé séparément. |
| `_fermer_connexions` | 402 | Structure : close best effort ; erreur ignorée. Les fermetures ordinaires et le retour à zéro des écritures non committées ont été exécutés. |
| `operation_dupliquer` | 655 | Structure : duplication durable avant SELECT de confirmation ; aucune panne injectée dans cette lecture. Pas de verdict de sûreté de ce second stade. |
| `immo_reprendre_amortissements` | 675 | Structure : écriture puis message ; fermeture finally. Panne de présentation après commit non injectée. |
| `saisir_appel` | 703 | Fonction métier exécutée : deux composantes persistantes à l’échec de la troisième, Q-06. La fermeture ne peut pas annuler ces commits. |
| `saisir_op` | 738 | Structure : saisie durable puis lecture du catalogue ; panne à ce second stade non injectée. Le commit=False métier est éprouvé séparément. |
| `creer_exploitant` | 802 | Structure : INSERT durable puis lecture des exercices ; panne à ce second stade non injectée. |
| `creer_bien` | 829 | Structure : INSERT puis commit, erreur convertie en message et fermeture. Échec artificiel de commit non injecté. |
| `creer_composant` | 912 | Exécuté : composant durable, acquisition refusée, Q-07. |
| `immo_ventiler` | 999 | Structure : rollback du groupe et fermeture finally ; pas de commit demandé aux acquisitions de la boucle. Panne spécifique de cette vue non injectée. |
| `composant_duree` | 1043 | Structure : UPDATE unique et commit, fermeture finally. Panne de rendu non injectée. |
| `pense_bete_notes` | 1062 | Structure : UPSERT des notes et commit métier, fermeture finally. Panne de rendu non injectée. |
| `_dossier_absent` | 1096 | Structure : repli de présentation pour base absente ; aucun état comptable créé par ce bloc. |
| `quittances_locataire` | 1139 | Structure : ajout explicite et commit ; ne dispose pas d’un rollback après succès. Lectures de schema testées en Q-01. |
| `quittances_emettre` | 1158 | Émission métier exécutée en concurrence : double attestation ou collision, Q-04. Fermeture de connexion dans finally. |
| `cloture` | 1201 | Structure : simulations de présentation avec repli ; pas d’appel à fiscal.cloturer dans cette vue GET. |
| `cloture` | 1206 | Structure : simulations de présentation avec repli ; pas d’appel à fiscal.cloturer dans cette vue GET. |
| `cloturer` | 1254 | Métier exécuté : arrêt intermédiaire annulé par fermeture ; une clôture simultanée refusée. Bloc archivage isolé conforme au correctif D2 ; panne d’archive non rejouée ici. |
| `cloturer` | 1271 | Métier exécuté : arrêt intermédiaire annulé par fermeture ; une clôture simultanée refusée. Bloc archivage isolé conforme au correctif D2 ; panne d’archive non rejouée ici. |
| `exercice_ouvrir` | 1351 | Exécuté : création durable avant reprise refusée, Q-11. |
| `liasse_page` | 1378 | Structure : lecture/calcul puis rendu ; pas de clôture appelée. Exceptions de rendu non injectées. |
| `liasse_pdf_route` | 1409 | Structure : lecture/calcul puis création de PDF en mémoire ; pas de DML métier explicite. Exceptions PDF non injectées. |
| `reglementation_regle` | 1456 | Structure : changement versionné puis commit ; panne intermédiaire de cette vue non injectée. Lecture versionnée sans commit éprouvée. |
| `reglementation_gabarit` | 1476 | Structure : ajout de catégorie puis commit, fermeture ; création du gabarit exercée dans les tests métier. |
| `reglementation_compte` | 1496 | Structure : INSERT unitaire puis commit, fermeture ; pas de groupe métier apparent. |
| `sauvegardes_restaurer` | 1580 | Métier exécuté : deux appels retournent le même chemin de sûreté et perdent l’état antérieur, Q-05. La vue annonce normalement son succès. |
| `bac_a_sable_reset` | 1705 | Structure seulement : restauration de sauvegarde après panne d’initialisation non éprouvée ; aucun accès au bac à sable réel. |
| `bien_ceder` | 1763 | Métier exécuté : après échec avant deuxième écriture, fermeture laisse zéro écriture ; finally présent dans la vue. |
| `operation_annuler` | 1815 | Métier exécuté : deux succès concurrents, produits -800 ; Q-02. |
| `import_valider` | 1922 | Exécuté : rollback rang 7 laisse zéro ; après commit, échec de suppression laisse dix opérations et relance vingt ; Q-08/Q-12. |
| `import_valider` | 1935 | Exécuté : rollback rang 7 laisse zéro ; après commit, échec de suppression laisse dix opérations et relance vingt ; Q-08/Q-12. |
| `exercice_analyser_fec` | 1983 | Structure : fichiers de préparation et analyse ; pas de reprise comptable. Panne de nettoyage non injectée. |
| `exercice_reprendre_fec_multi` | 2033 | Exécuté : rollback n’annule pas l’exercice précédent committé ; répertoire supprimé ; Q-09. |
| `exercice_reprendre_fec` | 2073 | Rejeu métier interrompu exécuté : zéro écriture. Structure web : rollback et close puis os.remove dans finally ; panne de ce dernier non injectée. |

Total : 36 blocs except Exception recensés.

## Motifs de concurrence recensés

| Fichier / fonction | Tester puis agir | Résultat |
|---|---|---|
| ecritures.prochain_num / inserer | MAX puis INSERT | 20 saisies parallèles réussies ; borne de cinq collisions forcées exécutée. |
| ecritures.inserer | Statut ouvert puis acquisition du verrou | Q-03, ajout après clôture exécuté. |
| fiscal.cloturer | Statut ouvert puis clôture | BEGIN IMMEDIATE avant lecture : un succès et un refus exécutés. |
| quittances.emettre / prochain_numero | Absence par logement puis MAX puis INSERT | Q-04, deux entrelacements exécutés. |
| operations.annuler | Marqueur annulee puis écriture et UPDATE | Q-02 exécuté. |
| cession.ceder_bien | Absence de date de cession puis écritures | Interruption éprouvée ; double cession concurrente non exécutée. assurer_schema écrit aussi sur la connexion. |
| reprise.construire_an_interne / _construire_an_depuis_balance | Absence d’AN puis génération | Interruption éprouvée ; double reprise concurrente non exécutée. |
| app._migrer_si_besoin | Présence dans _MIGRES puis add | Test et add sous verrou conformément à D2 ; exception silencieuse exécutée. Fin de migration hors de cette section, entrelacements métier non éprouvés. |
| app.exercice_ouvrir | Absence d’année puis INSERT | Contrainte primaire en base ; échec de reprise après création exécuté, pas double ouverture. |
| app.exercice_reprendre_fec_multi | Année absente du set local puis insertion et add | Q-09 ; le set est local à la requête, pas un verrou interrequêtes. |
| rejeu_fec.rejouer / fec_io.assurer_comptes | Absence du compte puis INSERT | Même transaction que les écritures ; rollback de rejeu éprouvé. Course sur création de compte non injectée. |
| gabarits.ajouter_personnalise | Validation clé / compte puis INSERT | Création exercée ; collision entre créations non injectée. |
| perennite.sauvegarder / restaurer | État / quittances contrôlés puis sauvegarde et restauration | Q-05 ; noms limités à la seconde. Émission de quittance pendant restauration non injectée. |
| perennite.sauvegarde_quotidienne | Recherche de sauvegarde du jour puis création | Structure seulement ; pas de preuve de perte spécifique. |
| dossiers.creer / renommer / _enregistrer | Chargement du registre puis remplacement du JSON | Structure seulement ; atomicité du remplacement ne prouve pas la sérialisation de deux mises à jour. Aucun constat sans exécution. |
| app._db_path / bac_a_sable_activer | Absence de base puis initialisation | Structure seulement ; aucune opération sur la vraie base de bac à sable. |
| app.import_valider | Existence du jeton puis traitement et suppression | Relance après erreur exécutée Q-08 ; deux validations simultanées du même jeton non injectées. |
| init_db.init | Existence / sauvegarde puis suppression et création | Hors scénario de destruction concurrente ; mode blanc isolé seulement. |

Les autres MAX de fiscal._ventiler_39c_par_bien, amortissement._cumul_comptabilise et perennite._max_quittance sélectionnent une année/un état ; ce ne sont pas des allocateurs de numéros. Seul ecritures.inserer émet des instructions SAVEPOINT/RELEASE dans le code métier recensé.

## Exceptions pendant le traitement d’une exception

- `app.import_valider` appelle rollback avant journalisation ; `immo_ventiler` et les reprises appellent aussi rollback sans protection secondaire. Une panne de rollback n’a pas été injectée : aucune affirmation de récupération universelle.
- `app._fermer_connexions` avale l’erreur de close. Les autres close placés dans except/finally peuvent remplacer l’erreur initiale ; cette éventualité reste une question d’injection, pas un constat établi.
- `app.exercice_reprendre_fec` supprime le fichier dans finally ; `exercice_reprendre_fec_multi` utilise rmtree(ignore_errors=True). Le premier échec de suppression testé est celui de l’import bancaire après commit (Q-08) ; le second efface effectivement la préparation après échec métier (Q-09).
- `_MIGRES.discard` opère sur un set de chaînes sans I/O ; aucune panne propre de discard reproduite. L’exception de migration est, elle, effectivement absorbée (Q-10).
