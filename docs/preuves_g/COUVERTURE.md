# Couverture d'exécution — passe G

Les identifiants ci-dessous correspondent aux clés du fichier `resultats.json`. Le script `reproduire.py` exécute le code applicatif ; il ne valide pas les contrats en relisant leurs commentaires. Les tables et FEC sont créés exclusivement à partir de données fictives. Les bases temporaires ne sont pas conservées.

## Correspondance entre constats et preuves

| Constat | Clés des sorties exécutées | Point éprouvé |
|---|---|---|
| G-01 | `guichet_valeurs.arrondi` | Totaux enregistrés 200 / 200,01 et rejet de l'export par le validateur |
| G-02 | `lignes_courtes`, `balance_filtre_court`, `colonne_absente`, `rejeu_web_lignes_courtes` | Lignes conservées par le lecteur brut, filtrées par les consommateurs ; succès de la vue web |
| G-03 | `equilibre_par_journal`, `trou_par_journal`, `sequences_distinctes` | Équilibre et séquences calculés sur la mauvaise clé |
| G-04 | `numeros_alphanumeriques` | Refus par les deux consommateurs des numéros BQ0001/BQ0002 |
| G-05 | `variantes_format` : `pipe`, `signe_suffixe`, `colonne_supplementaire` | Trois variantes de format, fichier réel dans chaque essai |
| G-06 | `validateur_mutations` : `montant_NaN`, `deux_montants_inf`, `deux_montants_1e309`, `devise_non_numerique` | Faux verdict positif sur valeurs monétaires impropres |
| G-07 | `validateur_mutations.date_impossible`, `validateur_mutations.compte_non_pcg`, `nom_date_impossible` | Calendrier réel et trois premiers chiffres du compte |
| G-08 | `metadonnees_rejeu`, `annee_interne_ecriture` | Aller-retour des champs et date différente au sein d'une écriture |
| G-09 | `ordre_validation` | Deux saisies rétrospectives, clôture, export et validation |
| G-10 | `sql_clos_export.compte_absent`, `sql_clos_export.sans_ligne` | État orphelin injecté, volume en base contre volume exporté |
| G-11 | `cession_valeurs.nan`, `cession_web_nan` | Cession durable et message de succès avec prix NaN |
| G-12 | `absorption_arrondis` | Répartition calculée et compte recevant l'ajustement |
| G-13 | `variantes_format.latin15` | Texte encodé ISO-8859-15 puis libellé réellement conservé |
| G-14 | `validateur_cli` | Sous-processus réel, sortie humaine et code système |
| G-15 | `comptes_sept_chiffres` | Types effectivement inscrits pour 409/419/425 |

## Matrice des exigences demandées

| Domaine | Essai / sortie | Conclusion limitée à l'exécution |
|---|---|---|
| Équilibre au guichet | `guichet_valeurs` | 800/799 refusé ; trois décimales ou plus peuvent créer G-01 |
| Négatif au guichet | `guichet_valeurs.negatif` | INSERT tenté, contrainte SQL, savepoint : aucun en-tête ni ligne après commit volontaire |
| Compte inexistant | `guichet_valeurs.compte_inconnu` | INSERT tenté, clé étrangère, aucun en-tête ni ligne après commit volontaire |
| NaN/inf au guichet | `guichet_valeurs.nan`, `.inf` | Refus avant INSERT |
| Zéro au guichet et à la saisie | `guichet_valeurs.nul`, `operations_valeurs.zero` | Le guichet général accepte deux lignes nulles ; l'opération métier les refuse |
| Opérations négatives/non finies | `operations_valeurs` | Refus, puis zéro donnée après commit volontaire |
| Arrondis de répartition | `absorption_arrondis` | Total conservé ; 13 € déplacés vers un terrain à quote-part fixée |
| Cession | `cession_valeurs` | Cas normal équilibré ; négatif refusé ; inf provisoire annulé à la fermeture ; NaN committé |
| À-nouveaux | `an_banque`, `an_desequilibre` | Classe 5 conservée ; déséquilibre rejeté, zéro écriture durable |
| Import FEC négatif | `variantes_format.negatifs_normalises` | Deux lignes normalisées, une écriture conservée, compteur explicite |
| Unicité de numéro | `num_impose` | Numéro 1 dupliqué : erreur UNIQUE ; numéro 3 imposé accepté, trou signalé |
| Réutilisation après rollback | `groupe_rollback` | Zéro écriture, prochain numéro 1 |
| Annulation normale | `annulation` | Écriture originale 1 conservée, inverse 2 en OD, dates et référence ANNUL-1 vérifiées |
| Annulation close | `annulation_close` | Refus ; écriture originale conservée |
| SQL direct sur clos | `sql_clos_export` | Modification, renumérotation et suppression possibles : frontière applicative, pas scellement SQL |
| Restauration | `restauration_cloture` | Retour à ouvert ; état clos présent dans la copie de sûreté |
| Migration de schéma | `migration_fec_inchange` | Version 2 simulée vers 7 ; export identique octet pour octet |
| Dix-huit colonnes natives | `export_normal` | Liste attendue, ordre et longueurs vérifiés contre une liste indépendante dans le dispositif |
| Encodage / délimiteurs natifs | `export_normal` | UTF-8, sans BOM, tabulations, CRLF final, aucun LF isolé |
| Formats montants / dates | `export_normal` | Virgule, zéro vide, dates sur huit chiffres, pas de séparateur de milliers |
| Champs non utilisés | `export_normal` | Auxiliaires, lettrage et devise vides sur les écritures natives |
| Date de validation close | `export_normal`, `validateur_mutations.valid_date_vide` | Date remplie ; champ vidé refusé |
| Export contre validateur propre | `export_normal`, `guichet_valeurs.arrondi`, `ordre_validation` | Cas normal accepté ; arrondi déséquilibré détecté ; ordre inversé non détecté |
| FEC sans en-tête | `entete_absente` | Signal de validation ; KeyError au rejeu, zéro écriture |
| Colonne manquante | `colonne_absente` | Signal de validation ; zéro écriture avec retour réussi au rejeu |
| Ligne trop courte | `lignes_courtes` | Le lecteur brut garde tout ; le rejeu perd des lignes équilibrées |
| Tabulation dans libellé importé | `tabulation_import` | Dix-neuf champs signalés ; montant décalé illisible, rejeu annulé |
| Saut de ligne dans libellé importé | `saut_ligne_import` | Fragments de 11 et 8 champs visibles ; erreurs de structure et équilibre |
| Guillemets importés | `variantes_format.guillemets` | Guillemets non fermés conservés sans fusion des lignes |
| UTF-8 avec BOM | `variantes_format.utf8_bom` | Lecture et rejeu réussis |
| CP1252 / ISO-8859-15 | `variantes_format.cp1252`, `.latin15` | CP1252 conserve € ; ISO-8859-15 produit ¤ |
| Fins de lignes LF | `variantes_format.lf` | Lecture et validation réussies ; variante admise par le texte |
| Colonnes permutées | `variantes_format.colonnes_permutees` | Rejeu par nom fonctionnel ; validateur refuse l'ordre, ce qui est attendu pour la remise |
| Numéros par journal | `rejeu_journaux_correct`, autres essais de journaux | Correction A du rejeu tenue ; divergence du validateur en G-03 |
| Numéros alphanumériques | `numeros_alphanumeriques` | Refus explicite du validateur, exception int au rejeu |
| Autre année cible | `autre_annee` | FEC 2025 cohérent isolément ; rejet du rejeu vers 2026 |
| Plusieurs exercices | `plusieurs_exercices`, `annee_interne_ecriture` | Rejet entre groupes distincts ; date de seconde ligne écrasée dans un groupe unique |
| Export d'orphelins | `sql_clos_export` | En-tête sans ligne / comptes absents masqués par jointures |
| Libellé NULL | `sql_clos_export.libelle_null` | Lignes exportées ; champ vide signalé par le validateur |
| Fin de savepoint | `tous_gabarits_rollback`, `groupe_rollback` | RELEASE ne rend pas durables les opérations testées en commit=False |
| Lecture qui committe entre deux gestes | `recoupement_Q01` | Une opération survit au rollback après lecture des quittances ; défaut Q-01 non renuméroté |
| 512 | `an_banque`, `comptes_sept_chiffres`, `export_normal` | Import supporté ; export natif sans 512 accepté localement ; régularité de fond non certifiée |

## Types des comptes importés

Tous les montants et numéros sont conservés dans cet essai ; le classement stocké ci-dessous est une observation, pas une validation globale du bilan.

| Compte à sept chiffres | Type produit | Classe | Qualification |
|---|---|---:|---|
| 1640000 | passif | 1 | Emprunt |
| 2110000 | actif | 2 | Immobilisation |
| 2818400 | amortissement | 2 | Actif soustractif |
| 3010000 | actif | 3 | Stock |
| 3910000 | amortissement | 3 | Type générique soustractif utilisé par le logiciel |
| 4010000 | passif | 4 | Fournisseur : correctif D2 tenu |
| 4090000 | passif | 4 | G-15 : débiteur mal classé |
| 4110000 | actif | 4 | Client : correctif D2 tenu |
| 4190000 | actif | 4 | G-15 : créditeur mal classé |
| 4210000 | passif | 4 | Rémunération due |
| 4250000 | passif | 4 | G-15 : avance débitrice mal classée |
| 4310000 | passif | 4 | Organisme social |
| 4410000, 4510000, 4610000, 4810000 | passif | 4 | Repli par numéro ; ne signifie pas qu'un solde débiteur a été analysé |
| 4710000 | attente | 4 | Compte d'attente |
| 4910000 | amortissement | 4 | Type générique soustractif |
| 5120000 | actif | 5 | Banque correctement conservée |
| 5910000 | amortissement | 5 | Type générique soustractif |
| 6152000, 6811000 | charge | 6 | Comptes de charges |
| 7088100, 7910000 | produit | 7 | Comptes de produits |

Le test emploie 1080000 comme contrepartie synthétique. Il ne reproduit pas un bilan réel et n'attribue aucune identité à un compte de tiers.

## Limites d'exécution

- Aucune soumission à l'administration ni exécution de Test Compta Demat.
- Aucun dossier réel, aucune vérification de cohérence avec ses justificatifs.
- Pas de répétition des courses Q-02/Q-03/Q-05 : elles restent documentées dans la passe Q. L'unicité et le rollback sont réexécutés ici.
- Les suppressions/renumérotations SQL servent à tester les frontières et l'exhaustivité de l'export ; elles ne sont pas présentées comme une fonctionnalité disponible dans une vue web.
- Les flags d'injection `verifier_equilibre=False` / `verifier_conformite=False` n'ont pas été utilisés pour G-01 : ses contrôles sont ceux par défaut. Leur existence pour les audits n'est pas un défaut en soi.
- Le contrôle du seul nom est distinct de celui du contenu. Le test `nom_date_impossible` établit une date impossible acceptée ; il ne vérifie pas le SIREN fictif contre un registre d'identités.
