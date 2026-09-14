# Programme d'audit — mode d'emploi

Un fichier par passe, à copier tel quel dans une IA. **Toujours joindre
`00-INVARIANTS.md` avant le prompt de la passe** : il porte le contexte, le
format imposé, les six règles apprises en se trompant, et la consigne de
sécurité sur les données réelles.

## Les passes

| Fichier | Domaine | Pièces principales |
|---|---|---|
| `G-regularite-comptable.md` | Équilibre, numérotation, immuabilité, conformité FEC | `ecritures`, `export_fec`, `valider_fec`, `fec_io` |
| `H-amortissements.md` | Plan par composants, prorata, article 39 B | `amortissement`, `plan_immo` |
| `I-article-39C.md` | Plafonnement, report sans péremption, suivi par bien | `fiscal`, `liasse` |
| `J-deficits-lmnp.md` | Report, **péremption 10 ans**, ordre d'imputation | `fiscal`, `liasse`, `liasse_pdf` |
| `K-cloture-pluriannuel.md` | Clôture, à-nouveaux, cohérence N → N+1 | `fiscal`, `reprise`, `migration_fec` |
| `L-cession.md` | Sortie d'actif, neutralisation, plus-values | `cession`, `fiscal`, `liasse` |
| `M-moteur-de-controles.md` | **Auditer le garde-fou** — 27 contrôles | `controles`, `audit_cycle` |
| `N-regles-versionnees.md` | Règles datées, effet rétroactif, veille | `parametres`, `veille_fiscale` |
| `O-perennite.md` | Sauvegardes, restauration, piste d'audit | `perennite`, `dossiers`, `migrations` |
| `P-quittances.md` | Documents remis à un tiers, données du locataire | `quittances` |
| `Q-atomicite.md` | **Transverse** : transactions, concurrence | tous les modules qui écrivent |

## Ordre conseillé

Il n'est pas arbitraire — chaque passe s'appuie sur ce que la précédente a
établi.

1. **Q** d'abord, même si elle n'est pas métier. C'est elle qui a produit les
   deux pires défauts déjà trouvés, et une écriture non atomique invalide les
   constats de toutes les autres passes.
2. **G**, puis **H** : l'intégrité comptable et l'amortissement sont le socle
   des chiffres que les passes fiscales examinent.
3. **I**, **J**, **L** : les trois mécaniques fiscales à mémoire. **J** est
   celle où une erreur coûte le plus longtemps — dix ans.
4. **K** : le cycle, qui ne peut être jugé qu'une fois I, J et L établies.
5. **M** : auditer les contrôles en dernier a un sens, on sait alors ce qu'ils
   auraient dû voir.
6. **N**, **O**, **P** : indépendantes, dans n'importe quel ordre.

## Ce qui manque pour aller au bout

- **Le CERFA 2042-C-PRO** — absent du dépôt. Sans lui, les cases `5NA` / `5NY`
  de l'aide au report ne peuvent pas être vérifiées (passe J). Le
  **2033-SD 2026** est à la racine du dépôt et suffit pour G, I, L et K.
- **Une table de correspondance de plans comptables** : la case 243 « dont CFE
  et CVAE » reste vide sur un plan de cabinet, et aucun préfixe ne distingue la
  CET des autres impôts directs. C'est une limite connue, figée par un test.

## Ce qui est déjà couvert — ne pas resignaler

Six passes faites, consignées dans `CHANGELOG.md` et `docs/AUDIT_PASSE_*.md` :

| Passe | Domaine | Où |
|---|---|---|
| A | Lecture, validation, migration FEC | `CHANGELOG.md` v8.36.0 |
| B | Cycle de vie du dossier | v8.37.0 |
| C | Liasse d'un exercice de cession | v8.38.0 |
| D | Couche web et ligne de commande (9 critiques) | v8.40.0 / v8.41.0 |
| D2 | Reprise de la couche web (9 constats) | `docs/AUDIT_PASSE_D2.md` |
| E | Import bancaire, liasse PDF, plan de comptes (22 constats) | `docs/AUDIT_PASSE_E.md` |
| F | Chaîne de distribution (12 constats) | `docs/AUDIT_PASSE_F.md` |

Synthèse transversale des passes E et F : `docs/SYNTHESE_PASSES_E_F.md`.

**Les 20 constats majeurs de la passe D (D-10 à D-29) sont perdus** — aucune
trace, ni liste ni test. La passe D2 a repris la couche web à neuf plutôt que
de tenter de les reconstituer.

## Après une passe

1. Déposer le rapport en `docs/AUDIT_PASSE_<lettre>.md`.
2. Traiter les constats **par gravité**, en vérifiant chacun par exécution avant
   et après correction.
3. Figer chaque correctif par un test de non-régression nommé d'après le
   constat, dans `tests/test_passe_<lettre>.py`.
4. Ajouter au rapport une section « Suivi des correctifs » — y compris les
   constats **annulés** parce que faux. Une revue qui efface ses erreurs ne se
   relit pas.
