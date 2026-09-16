# Audit — passe H : amortissements par composants

**Date : 15 septembre 2026. Version examinée : 8.41.0.**

**12 constats reproduits : 2 critiques, 9 majeurs, 1 mineur.** Les principaux risques sont le dépassement de la valeur brute, le double amortissement d'un exercice et la réécriture des tableaux historiques après modification d'une durée.

## Périmètre et méthode

Les fichiers cités sont relatifs à `compta_lmnp/`. Les numéros de ligne désignent cette version ; les empreintes SHA-256 sont dans les preuves. Le code de production n'a pas été modifié.

Lecture préalable des invariants, notamment la règle 2, du CHANGELOG (dont v8.35.0, v8.36.0, v8.39.0 et v8.14.0), des récapitulatifs E/F disponibles dans Git, et des rapports G/Q présents. Les rapports E/F supprimés du répertoire de travail n'ont pas été restaurés. Les correctifs sont distingués de leurs limites : le plafonnement fonctionne pour un composant seul ; la centralisation dans `plan_immo.py` existe ; le refus du terrain sans compte fonctionne. Le contrôle corrigé des dotations absentes **dans un FEC de migration** se trouve dans `migration_fec.py` ; ce n'est pas le contrôle `DOTATION_PLAN` examiné ici.

Toutes les bases sont créées en mode blanc dans un répertoire temporaire. Identité : « Exploitant fictif », SIREN fictif `000000000`, adresse fictive. Aucun accès aux FEC réels, au seed d'identité, à la liste d'empreintes privées ou à la base comptable de l'auteur. Les essais web appellent les véritables fonctions de route dans un contexte Flask, avec uniquement le chemin de base remplacé ; ils ne simulent pas le calcul comptable et ne constituent pas des essais de navigateur.

Reproduction depuis la racine du dépôt :

```bash
compta_lmnp/.venv/bin/python docs/preuves_h/reproduire.py
```

- [Script autonome](preuves_h/reproduire.py).
- [Sorties réelles : 48 groupes de résultats](preuves_h/resultats.json), Python 3.14.6 / SQLite 3.51.2.
- [Matrice de couverture et vérification des preuves](preuves_h/COUVERTURE.md).

Les blocs « Produit » sont des extraits des valeurs effectivement retournées ou relues en base, présentés avec des intitulés courts ; la sortie JSON complète fait foi. Les écritures ordinaires passent par `ecritures.inserer`. Les créations de composants par SQL servent à construire les fixtures ; les injections volontairement incohérentes sont expressément identifiées. Elles ne prouvent pas l'existence d'un chemin web équivalent.

Les montants indiquent des différences comptables, de revenu imposable ou de stock reportable, **pas un montant d'impôt calculé**. Les conventions assumées de comptabilité de caisse et de contrepartie 108000 ne sont pas des constats.

## H-01 — Le partage d'un compte désactive le plafonnement : 19 600 € amortis pour 16 000 €

**Gravité : critique.**

**Fichiers et fonctions :** `modules/amortissement.py`, `_cumul_comptabilise`, ligne **150** (abandon si compte partagé, lignes 165–170), `dotations_exercice`, ligne **99** ; `modules/controles.py`, `c_duree_allongee`, ligne **185**.

**Scénario reproductible :** deux composants de **8 000 €**, mis en service le **1er janvier 2026**, chacun sur cinq ans, partageant `281840`. Comptabiliser leur acquisition de 16 000 €. Clôturer 2026, 2027 et 2028, avec reprise interne des à-nouveaux à chaque ouverture. Porter les deux durées à huit ans. Clôturer ensuite 2029 à 2033. Aucun montant du grand livre n'est retouché.

**Attendu :** une fois 15 600 € comptabilisés fin 2031, il reste **400 €** à amortir. Le partage du compte doit être traité ou déclaré comme une impossibilité de plafonner ; il ne doit pas autoriser un cumul supérieur au brut.

**Produit — `duree_allongee_partage_True` :**

```text
année   dotation générée   cumul créditeur 281840
2029       2 000,00             11 600,00
2030       2 000,00             13 600,00
2031       2 000,00             15 600,00
2032       2 000,00             17 600,00
2033       2 000,00             19 600,00
```

Le contrôle `DUREE_ALLONGEE` est absent. `DOTATION_PLAN` est absent : les dotations suivent précisément le plan recalculé, pourtant incompatible avec l'historique. `AMORT_ANTERIEURS` existe, mais porte un écart négatif présenté comme des amortissements manquants. La liasse détecte ensuite la divergence entre tableau et bilan : **le défaut n'est donc pas invisible partout**.

**Conséquence :** **3 600 €** de charges d'amortissement excédentaires sur la séquence, une VNC comptable de **−3 600 €** et, dans cette fixture sans loyers, un stock 39 C alimenté par des dotations excessives. La borne du cas à compte unique corrigée en v8.35.0 ne protège pas ce cas. Le partage de compte est également utilisé par les trois composants de bâtiment de la ventilation indicative.

## H-02 — Le plafonnement ignore les dotations et à-nouveaux de l'exercice courant

**Gravité : critique.**

**Fichiers et fonctions :** `modules/amortissement.py`, `_cumul_comptabilise`, ligne **150**, `dotations_exercice`, ligne **99**, `generer_cloture`, ligne **303** ; `modules/fiscal.py`, `cloturer`, ligne **471**.

**Scénario reproductible :** composant de **12 000 €** sur dix ans, mis en service le 1er janvier 2026. Acquisition comptabilisée. Saisir une OD manuelle de **1 200 €**, débit 681120 / crédit 281840, pièce `MANUEL`, puis **1 800 €** de loyers. Clôturer normalement.

**Attendu :** reconnaître les 1 200 € déjà pratiqués ou refuser explicitement de générer une seconde dotation. Sans autre charge ni report, le revenu imposable doit être **600 €** et le nouveau report 39 C nul.

**Produit — `manuel_resultat_fiscal` :**

```json
{
  "produits": 1800.0,
  "dotation": 2400.0,
  "resultat_comptable": -600.0,
  "resultat_fiscal": 0.0,
  "revenu_imposable": 0.0,
  "stock_cloture_39c": 600.0
}
```

Le contrôle avant clôture ne signale pas de divergence de dotation : les 1 200 € déjà saisis correspondent au plan. La génération cherche une pièce OD `DAA`, pas la dotation nette déjà présente.

Deux variantes exécutées confirment la portée du défaut :

- `manuel_False` : composant de 12 000 € sur **un an**, déjà doté manuellement de 12 000 €. Après clôture : **24 000 €** en 281840 pour 12 000 € de brut, VNC **−12 000 €**.
- `an_premier_exercice` : premier exercice du dossier, composant de 8 000 € sur huit ans, mis en service en 2025, et **8 000 €** d'amortissements déjà repris en AN de 2026. `_cumul_comptabilise` retourne **0**, faute d'exercice antérieur clos ; la clôture ajoute **1 000 €**, portant le cumul à **9 000 €**. Les paramètres et l'historique sont volontairement discordants : c'est précisément la situation que la borne sur le réel doit contenir.

**Conséquence :** sur le premier scénario, **600 € de revenu imposable omis** et **600 € de report 39 C indu**. Sur les variantes, dépassement effectif de la valeur brute. Après génération, des contrôles de liasse ou `DOTATION_PLAN` peuvent alerter ; ils interviennent sur un exercice déjà clos.

## H-03 — Une contre-passation est ignorée par `DOTATION_PLAN`

**Gravité : majeur.**

**Fichiers et fonctions :** `modules/controles.py`, `c_dotation_vs_plan`, ligne **524** (somme des seuls débits, ligne 532) ; `modules/amortissement.py`, `generer_cloture`, ligne **303** ; `modules/fiscal.py`, `simuler`, ligne **412**.

**Scénario reproductible :** composant de 12 000 € sur dix ans, acquisition en 2026. Générer la DAA de **1 200 €**, puis enregistrer son inverse de **1 200 €** par `ecritures.inserer` : débit 281840 / crédit 681120, pièce `INVERSE`. Il s'agit d'une véritable contre-écriture, pas d'une suppression SQL. Relancer les contrôles et la génération.

**Attendu :** constater une dotation nette nulle et signaler son annulation. La présence de la pièce d'origine doit être distinguée de son effet comptable encore actif.

**Produit — `daa_annulee` :**

```text
solde net 681120 = 0,00
solde net 281840 = 0,00
controles.controler = []
seconde génération = ValueError: Dotation aux amortissements déjà générée
                      pour 2026 (écriture OD n°2).
```

La projection fiscale n'annonce aucune dotation complémentaire, la pièce `DAA` existant toujours. La liasse signale bien un écart de **1 200 €**, mais l'attribue à une reprise historique manquante, alors que le composant a été acquis dans l'exercice.

Variante inverse, `manuel_True` : une dotation manuelle de 12 000 € et son inverse, puis une DAA correcte de 12 000 €, donnent un solde net correct de **12 000 €** ; `DOTATION_PLAN` annonce pourtant un écart, car il totalise **24 000 € de débits**.

**Conséquence :** le même contrôle manque une annulation de **1 200 €** et accuse un double amortissement inexistant dans l'autre scénario. La reprise de clôture reste bloquée par la pièce historique, sans diagnostic de sa neutralisation.

## H-04 — L'omission d'une dotation à la clôture n'est pas contrôlée au titre du minimum 39 B

**Gravité : majeur.**

**Fichiers et fonctions :** `modules/controles.py`, `c_dotation_vs_plan`, ligne **524**, `c_duree_allongee`, ligne **185**, `c_amortissements_anterieurs`, ligne **630** ; `modules/fiscal.py`, `cloturer`, ligne **471** ; `modules/operations.py`, `reprendre_amortissements_anterieurs`, ligne **236**.

**Scénario reproductible :** acquisition et composant de **12 000 €**, dix ans, mise en service le **1er janvier 2026**. Clôturer par l'option existante `fiscal.cloturer(conn, 2026, generer_dotation=False)`. Exécuter les contrôles sur 2026 clos ; ouvrir 2027 avec reprise interne, puis exécuter le geste de reprise proposé.

**Attendu :** après clôture sans amortissement, signaler les **1 200 €** de minimum non pratiqué. Distinguer une omission de dotation dans un exercice réellement tenu ici d'une reprise d'historique de cabinet. Le contrôle d'un exercice encore ouvert peut naturellement attendre la génération finale.

**Produit — `omission_2026-01-01` :**

```text
2026 clos : amortissements en compte = 0,00
2026 clos : controles.controler = []
2033-C 2026 : amortissements fin = 1 200,00 ; bilan = 0,00 ; concordance false
2027 : dotation proposée = 1 200,00 ; aucun rattrapage dans cette dotation
2027 : AMORT_ANTERIEURS = 1 200,00
reprise proposée : AN, débit 108000 / crédit 281840, 1 200,00
```

**Conséquence :** l'omission annuelle de **1 200 €** est découverte dans la liasse, pas dans les contrôles après clôture. Le geste suggéré ajuste le bilan sans déduction de charge ni création du report 39 C omis. Le contrôle v8.39.0 des allongements de durée ne constitue pas un contrôle général du minimum.

L'article 39 B sanctionne l'insuffisance du cumul linéaire par une perte du droit à déduction ; une écriture d'AN ne constitue pas, à elle seule, une réparation fiscale de cette omission. La durée normale et les possibilités de rectification d'une déclaration particulière nécessitent une analyse distincte. [CGI, article 39 B](https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000006302321), [BOFiP, minimum d'amortissement, § 70–90 et 140–160](https://bofip.impots.gouv.fr/bofip/4711-PGP.html/identifiant=BOI-BIC-AMT-10-50-30-20170802).

**Variante de fin d'année, exécutée :** mise en service au **31 décembre 2026**, annuité **3,29 €**. Après omission, contrôles vides et concordance de liasse **true** malgré `3.29 / 0.00`. En 2027, le bouton de reprise répond : « Aucun amortissement antérieur à reprendre : le bilan est déjà cohérent avec le plan. » Le seuil matériel de 5 € explique ce résultat ; il ne démontre pas l'égalité des chiffres ni le respect du minimum. Ce n'est pas une erreur de flottant.

**Limite du chemin testé :** l'option sans génération appartient à la fonction métier. La clôture web ordinaire appelle la génération ; ce rapport ne lui attribue pas une case permettant d'oublier la DAA.

## H-05 — Modifier une durée change le 2033-C d'un exercice déjà clos

**Gravité : majeur.**

**Fichiers et fonctions :** `app.py`, `composant_duree`, ligne **1008** ; `modules/liasse.py`, `immobilisations_2033c`, ligne **309**, recalcul par `etat`, ligne **352** ; `modules/amortissement.py`, `generer_cloture`, ligne **303**, enregistrement du plan aux lignes 354–357.

**Scénario reproductible :** composant de **12 000 €** sur dix ans, mis en service le 1er janvier 2026, acquisition et clôture normale de 2026. Appeler la route de changement de durée pour passer à **vingt ans**, puis régénérer les états de **2026 clos**.

**Attendu :** les tableaux historiques doivent conserver les amortissements effectivement arrêtés. Une modification pour l'avenir doit être distinguée d'une correction historique explicite et ne doit pas substituer un plan neuf à l'état clos.

**Produit — `web_modification_clos` :**

```text
réponse : « Composant « Composant fictif » : durée portée à 20 ans. »
2033-C 2026 avant : dotation = 1 200,00 ; amort_fin = 1 200,00
2033-C 2026 après : dotation =   600,00 ; amort_fin =   600,00
bilan 2026 après : amortissements_030 = 1 200,00
plan_amortissement 2026 après : dotation = 1 200,00 ; cumul_fin = 1 200,00
```

**Conséquence :** **600 €** de divergence sur un exercice clos. La trace enregistrée à la clôture existe toujours mais n'est pas utilisée pour produire ce tableau. Le FEC et le bilan ne sont pas réécrits par ce geste : c'est **le 2033-C régénéré** qui change. `DOTATION_PLAN` et la concordance de liasse signalent ensuite l'écart ; la route a néanmoins annoncé le succès.

Le cas à compte unique de H-01 révèle aussi cette séparation sur l'exercice courant : en 2032, la borne réelle réduit la dotation à **200 €**, alors que le 2033-C recalculé affiche encore **1 000 €**. Le total des annuités du plan neuf ne remplace donc pas le total effectivement comptabilisé.

## H-06 — Une durée raccourcie abandonne 3 000 € restant à amortir

**Gravité : majeur.**

**Fichiers et fonctions :** `modules/amortissement.py`, `etat`, ligne **86**, `dotations_exercice`, ligne **99** ; `modules/operations.py`, `amortissements_anterieurs_manquants`, ligne **172**, `reprendre_amortissements_anterieurs`, ligne **236**.

**Scénario reproductible :** composant de **8 000 €** sur huit ans, mis en service le 1er janvier 2026 ; acquisition, clôtures 2026–2028 et à-nouveaux internes. Les comptes portent **3 000 €** d'amortissements. Ramener la durée à **quatre ans** puis clôturer 2029, 2030 et 2031.

**Attendu :** un changement de durée doit traiter les **5 000 € de VNC réelle** restant au début de 2029, ou imposer une résolution explicite. Il ne doit pas afficher un plan épuisé alors que les comptes portent encore une VNC de 3 000 €.

**Produit — `raccourcie_fin_plan` :**

```text
2029 : dotation 2 000,00 ; cumul réel 5 000,00 ; cumul_fin de la trace 8 000,00
2030 : dotations []      ; cumul réel 5 000,00 ; 2033-C amort_fin 8 000,00
2031 : dotations []      ; cumul réel 5 000,00 ; 2033-C amort_fin 8 000,00
```

La borne ne fonctionne que dans un sens : réduire une dotation excessive. Elle ne reconstruit pas le calendrier à partir de la VNC lorsqu'un plan rétrospectif s'achève trop tôt.

**Conséquence :** **3 000 €** sortent du programme de dotations sans avoir été comptabilisés en charges. La liasse et `AMORT_ANTERIEURS` signalent une divergence, mais la qualifient de reprise historique manquante. La variante `raccourcie_reprise_suggeree` exécute cette suggestion : **3 000 €** passent de 108000 vers 281840, sans charge ni report 39 C. Ce geste n'est pas un recalcul prospectif de la durée.

Le rapport ne présume pas qu'un raccourcissement arbitraire serait fiscalement justifié : il constate le traitement produit **lorsque le logiciel l'accepte**.

## H-07 — Une durée négative est enregistrée ; les durées 0/NULL incohérentes échappent aux contrôles

**Gravité : majeur.**

**Fichiers et fonctions :** `app.py`, `creer_composant`, ligne **837**, lecture de durée aux lignes 844–846 ; `modules/amortissement.py`, `plan`, ligne **60**, `dotations_exercice`, ligne **99** ; `modules/controles.py`, `c_composant_non_amortissable`, ligne **703**.

**Scénario reproductible :** envoyer à la véritable route de création un composant `218400` de **12 000 €**, date **2026-01-01**, durée **−1**. Réouvrir la base, calculer les dotations et clôturer.

**Attendu :** refus avant la création du composant et de son acquisition. Une durée d'amortissement négative ne doit produire aucun plan exploitable.

**Produit — `web_creation_duree_-1` :**

```text
réponse : « Composant « Composant fictif » ajouté.
           Écriture d'acquisition n°1 générée sur 2026. »
base : duree_annees = -1 ; amortissable = 1 ; valeur_brute = 12 000,00
dotations_exercice = []
clôture : réussie, dotation = 0
2033-C : dotation = -12 000,00 ; amort_fin = -12 000,00
```

**Conséquence :** **12 000 €** d'actif sont enregistrés avec un plan invalide ; le tableau annonce un amortissement négatif, et aucune dotation n'est générée. La perte annuelle ne peut être chiffrée sans durée correcte, qui n'a pas été fournie.

**Variantes injectées en base, non attribuées à la route :** composant de 12 000 €, `amortissable=1`, compte 281840, durée **0**, puis **NULL**. `controles.controler` retourne **[]** dans les deux cas. Le calcul et la clôture lèvent respectivement `DivisionByZero` et `InvalidOperation`; aucune écriture DAA ne reste. Le défaut est ici un contrôle préalable muet, pas une clôture partiellement validée.

**Diagnostic amendé :** la saisie web de `0` ou d'un champ vide les convertit en `NULL` **et** `amortissable=0`. Elle ne produit donc pas elle-même les deux incohérences injectées. Le refus de −1 reste absent.

## H-08 — Aucun composant : le contrôle de ventilation ne dit rien

**Gravité : majeur.**

**Fichiers et fonctions :** `modules/controles.py`, `c_ventilation_incoherente`, ligne **662**, sortie sur total nul aux lignes 687–688 ; `modules/amortissement.py`, `dotations_exercice`, ligne **99** ; `modules/liasse.py`, `immobilisations_2033c`, ligne **309**.

**Scénario reproductible :** bien fictif de **12 000 €**, acquisition enregistrée en 218400 / 108000, **aucun composant**. Exécuter le contrôle de ventilation, tous les contrôles, les dotations et la liasse.

**Attendu :** signaler que les **12 000 €** présents en immobilisations n'ont aucun composant et ne peuvent donner lieu à un plan. Une liste vide est le cas le plus incomplet, pas une preuve de complétude.

**Produit — `ventilation_0` :**

```text
controles.controler = []
dotations_exercice = []
2033-C brut_fin = 0,00
bilan brut = 12 000,00
contrôle de concordance du brut dans la liasse = false
```

L'import réel du FEC fictif `fec_sans_composants` donne la même absence d'alerte pré-clôture pour **20 000 €** de brut et **2 000 €** d'amortissements importés. Ces montants sont bien au bilan ; aucun composant n'est créé, et le 2033-C est vide.

**Conséquence :** pas de dotation proposée pour l'actif omis ; **12 000 €**, ou **20 000 €** dans le FEC, manquent au tableau des immobilisations. L'écart est rendu visible **dans la liasse**, pas par `VENTILATION_INCOMPLETE`. Il ne s'agit pas d'exiger que le FEC fournisse une durée qu'il ne contient pas : l'information manquante doit être demandée ou signalée.

**Ce qui tient à côté :** avec 1 000 € de composants sur un prix de 12 000 €, le contrôle signale effectivement les **11 000 €** manquants. À 11 400 €, il se tait en application du seuil documenté de 5 % ; ce seuil n'est pas présenté comme une égalité au centime.

## H-09 — Les comptes à sept chiffres passent au bilan mais dans la mauvaise rubrique du 2033-C

**Gravité : majeur.**

**Fichiers et fonctions :** `modules/plan_immo.py`, `pour_la_saisie`, ligne **68**, `compte_amortissement`, ligne **87** ; `modules/liasse.py`, `immobilisations_2033c`, ligne **309**, repli sur `autres_immo`, ligne **339**, `bilan_2033a`, ligne **278** ; `modules/rejeu_fec.py`, `rejouer`, ligne **28**.

**Scénario reproductible :** importer un FEC fictif de 2026 portant un AN équilibré :

```text
2180000  débit   8 000,00
2181000  débit  12 000,00
2818000  crédit    800,00
2818100  crédit  1 200,00
108000   crédit 18 000,00
```

Ajouter les composants correspondant à ces comptes : 8 000 € et 12 000 €, dix ans, mise en service le 1er janvier 2025. Leur création est explicite dans la fixture, pas déduite du seul FEC. Clôturer 2026.

**Attendu :** le poste 2181000, subdivision de 2181, doit rejoindre les installations/agencements, comme 218100. Le rattachement à « autres » doit être réservé aux postes qui en relèvent, ou rendu indéterminé explicitement.

**Produit — `fec_avec_composants` :**

```text
installations : brut_fin =      0,00 ; amort_fin =     0,00
autres_immo   : brut_fin = 20 000,00 ; amort_fin = 4 000,00
bilan        : brut     = 20 000,00 ; amort     = 4 000,00
tous les contrôles de liasse = true
controles.controler = []
```

**Conséquence :** **12 000 € de brut** et **2 400 € d'amortissements cumulés** sont affectés à la mauvaise rubrique. Les totaux concordent : le contrôle global ne peut pas détecter cette erreur de classement. Aucun effet sur le résultat fiscal n'est démontré pour ce scénario. La nature du compte 2181 et la ventilation parallèle des comptes 281 figurent au [plan de comptes ANC 2026, pages 3 et 5](https://www.anc.gouv.fr/files/anc/files/1_Normes_fran%C3%A7aises/Plans%20comptables/2026/Plan-de-comptes-2026.pdf).

**Menu exécuté — `fec_sans_composants` :** seuls 211550, 213150, 218100 et 218400 sont proposés. Les comptes importés ne s'ajoutent pas au menu. La source unique existe bien ; elle ne couvre pas automatiquement les subdivisions externes. Le compte générique 2180000 ne suffit pas, à lui seul, à préciser la nature physique du composant : aucune affectation plus fine de ses 8 000 € n'est inventée ici.

## H-10 — Une quote-part explicite de terrain à zéro devient 15 %

**Gravité : majeur.**

**Fichiers et fonctions :** `modules/amortissement.py`, `normaliser_quote_part`, ligne **237**, `ventilation_proposee`, ligne **272**, condition de prise en compte, ligne **286**.

**Scénario reproductible :** appeler `normaliser_quote_part(0, 100000)` puis `ventilation_proposee(100000, 0)`.

**Attendu :** respecter la valeur explicite zéro, ou la refuser avec une explication si elle n'est pas admissible. Elle doit être distinguée de l'absence de renseignement.

**Produit — `quote_parts`, entrée `0` :**

```text
normalisation : (0.0, "quote-part lue comme 0 %, soit 0)")
part terrain de la proposition : 0.15
montant terrain : 15 000,00
somme proposée : 100 000,00
```

**Conséquence :** la proposition exclut **15 000 €** de la base amortissable alors que le paramètre explicitement reconnu était nul. Cette perte potentielle existe si la proposition est conservée. Le rapport ne valide pas fiscalement un terrain à zéro pour un bien réel : il constate que la saisie n'est ni suivie ni refusée.

**Bornes qui tiennent :** `7,35` et `0,0735` donnent tous deux **7 350 €** de terrain sur 100 000 € ; `1.0` signifie **100 %**, avec 100 000 € de terrain et zéro ailleurs. Ce choix est documenté ; il n'est pas signalé comme un défaut. Le déplacement d'arrondi de **13 €** déjà constaté en G-12 a été reproduit, et n'est pas renuméroté ici.

## H-11 — Une annuité arrondie à zéro abandonne la valeur ; un reliquat peut créer une année supplémentaire

**Gravité : mineur.**

**Fichier et fonction :** `modules/amortissement.py`, `plan`, ligne **60**, arrondi de l'annuité ligne **63**, sortie de garde ligne **81**.

**Scénarios reproductibles :** appeler le plan de **0,24 € sur cinquante ans**, mise en service le **1er janvier 2026**, puis celui de **100 000,01 €** aux mêmes durée et date.

**Attendu :** répartir la valeur au centime sur la durée du plan, avec ajustement final ; si cette granularité n'est pas prise en charge, refuser explicitement. Le garde-fou de boucle ne doit pas retourner un plan incomplet comme un résultat ordinaire.

**Produit — `plan_residuel_0.24` et `plan_residuel_100000.01` :**

```text
valeur       nombre d'annuités   dernière annuité       somme
0,24                53          2078 : 0,00              0,00
100 000,01          51          2076 : 0,01        100 000,01
```

**Conséquence :** **0,24 €** jamais amorti dans le premier cas ; **0,01 €** décalé après les cinquante années 2026–2075 dans le second. L'impact unitaire est faible, d'où la gravité mineure. Les 21 930 cas usuels de la matrice conservent leur valeur totale : le défaut n'est pas généralisé à tous les plans.

## H-12 — Le garde-fou du terrain vérifie seulement l'absence de compte d'amortissement

**Gravité : majeur.**

**Fichiers et fonctions :** `modules/controles.py`, `c_composant_non_amortissable`, ligne **703** ; `modules/amortissement.py`, `generer_cloture`, ligne **303**, vérification des orphelins ligne **326** ; `modules/plan_immo.py`, `compte_amortissement`, ligne **87**.

**Scénario reproductible — injection de référentiel incohérent :** créer en SQL un composant de **12 000 €**, compte d'immobilisation **211550**, durée dix ans, date 2026-01-01, `amortissable=1`, mais compte d'amortissement renseigné **281840**. Exécuter le contrôle et la génération. Cette fixture éprouve une base modifiée ou un référentiel mal repris ; **elle ne provient pas de la saisie web normale**, qui résout correctement le compte du terrain.

**Attendu :** le compte 211550 déclaré non amortissable dans la source unique doit entraîner un refus, même si un compte 28 a été renseigné à tort.

**Produit — `terrain_1_281840` :**

```text
c_composant_non_amortissable = []
generer_cloture = {ecriture_id: 1, ecriture_num: 1,
                  total: 1200.0, nb_composants: 1}
solde 681120 = débit 1 200,00
solde 281840 = crédit 1 200,00
```

**Conséquence :** **1 200 €** de dotation de terrain indue sont effectivement enregistrés. La présence d'un compte 28 est traitée comme suffisante ; la cohérence avec le compte d'immobilisation n'est pas contrôlée.

**Limite de portée :** le contre-test `terrain_saisie_refusee` passe par la véritable route avec 211550 et durée dix ans : refus explicite, **zéro composant et zéro écriture**. Le correctif v8.14.0 tient sur ce chemin ; ce constat vise la défense du référentiel en base.

## Ce qui a été vérifié et tenu

- **Conservation au centime sur 21 930 plans usuels :** les 731 dates de 2023 et 2024, dix durées (1, 2, 3, 8, 10, 15, 20, 25, 50, 100 ans) et trois valeurs (1 299,87 €, 12 000 €, 100 000,01 €). La somme, refaite en `Decimal` à partir des annuités retournées, est toujours égale à la valeur brute ; aucune annuité négative. Cette vérification du total ne garantit pas l'absence d'année supplémentaire, traitée en H-11.
- **Cas imposés :** 1 299,87 € sur quinze ans à partir du 17 juin 2026 : première annuité **47,01 €**, dernière **39,62 €**, total **1 299,87 €**. Au 31 décembre : première **0,24 €**, dernière **86,39 €**, même total. Sur un an au 31 décembre : **3,56 € + 1 296,31 €**.
- **Prorata et flottants :** `fraction_prorata` retourne bien un Decimal. Les fractions de début/fin ne sont pas systématiquement complémentaires lorsqu'un 29 février intervient : du 1er juillet 2023 au 31 décembre, puis du 1er janvier au 30 juin 2024, elles totalisent **366/365**. Sur le plan, la dernière annuité est plafonnée au reliquat : aucun euro supplémentaire n'en résulte dans les cas testés. Il n'est donc pas conclu à un sur-amortissement à partir de la seule addition des fractions. La convention fiscale 365 reste une question distincte ci-dessous.
- **Terrain normal :** composant non amortissable ignoré par la génération ; terrain à durée positive et compte d'amortissement absent signalé par `COMPOSANT_SANS_AMORT` et refusé nommément. La route de création refuse aussi cette combinaison avant insertion.
- **Deux générations successives :** la seconde DAA est refusée, et une seconde clôture fiscale est refusée. Ce résultat séquentiel ne constitue pas un essai de concurrence ; celle-ci relève de Q.
- **Atomique sur les chemins éprouvés :** `generer_cloture(commit=False)` garde la transaction ouverte. Après rollback, seule l'acquisition initiale reste, sans ligne de plan. Une interruption SQLite imposée par trigger lors de l'insertion dans `plan_amortissement`, donc **après l'écriture DAA**, puis rollback/fermeture/réouverture, laisse **une écriture, deux lignes d'acquisition, zéro plan**, sans DAA survivante.
- **Un seul commit de clôture**, compté par sous-classe de connexion, sur le cas acquisition + composant de 12 000 € : dotation 1 200 €, un appel à `commit`.
- **44 gabarits exécutés deux fois chacun, puis rollback**, dont un personnalisé et un paramètre ALUR versionné. Sans transaction préalable, un appel de préparation à `commit()` est observé **avec `in_transaction=False`** ; aucune opération ne survit. Avec une transaction déjà ouverte et un témoin de 800 €, **zéro commit**, zéro témoin, zéro opération et zéro écriture après rollback. Le compteur seul sans son contexte aurait ici donné un mauvais diagnostic.
- **N-1 ouvert :** le calcul isolé propose une dotation de 1 200 € pour 2027, mais `fiscal.cloturer` refuse effectivement de clore 2027 avant 2026. Aucune écriture n'est insérée sur 2027.
- **Borne à compte unique :** après trois années à 1 600 €, puis durée allongée de cinq à huit ans, dotations de 1 000 €, 1 000 €, 1 000 €, **200 €**, puis zéro. Le cumul s'arrête à **8 000 €**. `DUREE_ALLONGEE` signale le changement. C'est une confirmation du correctif, pas H-01.
- **Valeur brute corrigée à la baisse :** une fixture passe de 8 000 € à 2 000 € après 3 000 € déjà amortis. La dotation suivante est vide ; les contrôles et la liasse rendent les écarts visibles. Le moteur ne crée pas de dotation supplémentaire pour corriger un historique déjà excessif.
- **Import à sept chiffres :** les quatre comptes nommés par la demande sont créés, les cinq lignes du FEC sont conservées, et le bilan lit **20 000 € brut / 2 000 € amortissements** avant la nouvelle dotation. Pas de perte de zéros ni d'amortissements au bilan dans cet essai.
- **La liasse détecte les divergences importantes de total**, y compris l'absence de composants, le cumul réel inférieur au plan et le dépassement du brut. Elle ne les bloque pas en amont de la clôture. La tolérance de concordance des amortissements est **5 € et 1 % simultanément** ; elle ne vérifie pas l'égalité au centime. La notice fiscale distingue elle-même les comptes tenus au centime et les tableaux fiscaux arrondis à l'euro : aucune conséquence de télédéclaration d'un simple centime n'est présumée ici. [Notice officielle 2033, millésime 2026, page 6](https://www.impots.gouv.fr/sites/default/files/formulaires/2033-sd/2026/2033-sd_5395.pdf).
- **Lecture indisponible, diagnostic limité :** renommer volontairement la table `ecriture` fait retourner `None` à `_cumul_comptabilise`, un plan théorique à `dotations_exercice` et `[]` au contrôle isolé des amortissements antérieurs. Toutefois, **le contrôleur complet échoue explicitement** avec `OperationalError: no such table: ecriture`. Ce résultat ne justifie donc pas d'annoncer un contrôle global vert sur une table manquante.
- **Non-duplication :** le déplacement de 13 € vers le terrain de G-12 est reproduit à l'identique et reste référencé sous G-12. Les constats d'atomicité Q ne sont pas renommés H.

## Non vérifiable avec les pièces fournies

- Pour chaque composant réel, quelles pièces établissent la durée normale d'utilisation, la valeur brute et la date effective de mise en service, notamment après un changement de durée ?
- Quelle justification comptable et fiscale valide la convention de prorata **jours réels / 365, jour d'entrée inclus, plafond annuel à 1**, notamment sur les premières et dernières années bissextiles ? Les calculs ont été exécutés ; leur conformité ne peut pas être déduite de leur ressemblance avec un ancien cabinet.
- En présence d'une dotation omise dans un exercice déjà déclaré, quelle procédure de correction est applicable au dossier et quelles possibilités de rectification sont encore ouvertes, distinctement d'un simple AN dans le logiciel ?
- Après raccourcissement ou allongement justifié, quel traitement prospectif et quelle date d'effet doivent être retenus, et quelles informations historiques doivent être conservées pour l'établir ?
- Pour les comptes génériques d'un cabinet, notamment 2180000 et 2818000, quel état détaillé des immobilisations permet de retrouver les composants, durées et natures que les dix-huit colonnes du FEC ne contiennent pas ?
- Quel effet exact les écarts observés auraient-ils sur l'impôt personnel et sur une éventuelle plus-value de cession, compte tenu des loyers, charges, reports, déductions effectivement admises et de la situation fiscale du déclarant ?
- Quel mécanisme extérieur au code audité empêcherait la transmission d'une liasse dont les contrôles internes sont faux ou seulement avertissants ? Aucun dépôt auprès de l'administration ni essai EDI n'a été effectué.

## Tableau récapitulatif numéroté

| N° | Constat | Conséquence effectivement mesurée | Gravité |
|---|---|---|---|
| H-01 | Compte partagé : plafonnement désactivé | 19 600 € amortis pour 16 000 € ; excès 3 600 € | critique |
| H-02 | Historique de l'exercice courant ignoré | Revenu imposable 0 € au lieu de 600 € ; report indu 600 € | critique |
| H-03 | Contre-passation ignorée par `DOTATION_PLAN` | 1 200 € annulés sans alerte de ce contrôle ; faux positif inverse | majeur |
| H-04 | Minimum 39 B non contrôlé après omission | 1 200 € non pratiqués ; reprise de bilan sans rattrapage fiscal | majeur |
| H-05 | Durée modifiée, 2033-C clos recalculé | 600 € d'écart sur l'état historique | majeur |
| H-06 | Raccourcissement : plan fini, VNC restante | 3 000 € abandonnés par le programme de dotations | majeur |
| H-07 | Durée négative acceptée | Actif de 12 000 €, dotation réelle 0 €, tableau à −12 000 € | majeur |
| H-08 | Ventilation vide non signalée par le contrôle | 12 000 € absents du 2033-C ; variante FEC à 20 000 € | majeur |
| H-09 | Subdivision 2181000 classée dans « autres » | 12 000 € brut et 2 400 € amortis dans la mauvaise rubrique | majeur |
| H-10 | Terrain explicitement nul remplacé par 15 % | 15 000 € exclus du potentiel amortissable proposé | majeur |
| H-11 | Arrondi annuel nul / année supplémentaire | 0,24 € jamais amorti ; reliquat de 0,01 € décalé | mineur |
| H-12 | Terrain avec compte 28 erroné accepté en base | 1 200 € de dotation indue ; chemin SQL explicitement injecté | majeur |

**État du suivi :** les douze constats ont été corrigés en production le 15 septembre 2026 (version 8.43.0). Les résultats et empreintes de `preuves_h/` sont conservés **tels qu'observés avant correction** : ils restent la référence du défaut, pas de l'état actuel du code. La non-régression est figée par `tests/test_passe_h.py` (61 tests), dont 42 échouent si l'on retire les correctifs.

Deux choix méritent d'être signalés à qui relira ce rapport. D'abord, le moteur ne **rattrape jamais** de lui-même un cumul d'amortissement en retard : l'article 39 B tient l'insuffisance pour irrégulièrement différée, et la déduire l'année suivante serait fautif. H-04 et H-06 sont donc traités par un contrôle — avertissement tant que des annuités restent à venir, bloquant quand le plan est épuisé — et non par une dotation de rattrapage. Ensuite, l'écart entre plan et comptabilité n'est suivi qu'au-delà d'un seuil de matérialité (1 € ou 1 % de la valeur brute, celui déjà retenu ailleurs dans le logiciel) : en deçà, le plan fait foi, pour que la dotation d'un exercice n'absorbe pas les arrondis hérités d'un historique repris. Les écarts ainsi tolérés restent signalés par `AMORT_ANTERIEURS` et `DOTATION_PLAN`.
