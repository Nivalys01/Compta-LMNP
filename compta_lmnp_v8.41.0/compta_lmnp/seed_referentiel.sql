-- ============================================================================
-- Seed RÉFÉRENTIEL — générique, livré avec le produit.
-- Ne contient AUCUNE donnée personnelle : journaux + plan de comptes LMNP type.
-- Chargé dans tous les modes (blanc comme exemple).
-- ============================================================================

-- --- Journaux --------------------------------------------------------------
INSERT INTO journal (code, libelle) VALUES
  ('AN', 'A Nouveaux'),
  ('AC', 'A Nouveaux callage'),
  ('BQ', 'Banque'),
  ('OD', 'Opérations diverses');

-- --- Plan de comptes (LMNP au réel, contrepartie trésorerie = 108000) ------
INSERT INTO compte (numero, libelle, type, classe) VALUES
  ('108000', 'Exploitant',                            'passif',        1),
  ('120000', 'Résultat de l''exercice',               'passif',        1),
  ('211550', 'Terrain',                               'actif',         2),
  ('213150', 'Bâtiment',                              'actif',         2),
  ('218100', 'Installation et agencement',            'actif',         2),
  ('218400', 'Mobilier',                              'actif',         2),
  ('281315', 'Amort. Bâtiment',                       'amortissement', 2),
  ('281810', 'Amort. Installation et agencement',     'amortissement', 2),
  ('281840', 'Amort. Mobilier',                       'amortissement', 2),
  ('472000', 'A nouveaux en attente',                 'attente',       4),
  ('606320', 'Petit équipement',                      'charge',        6),
  ('614100', 'Charges locatives et de copropriété',   'charge',        6),
  ('615200', 'Maintenance sur immobilier',            'charge',        6),
  ('616110', 'Primes assurances',                     'charge',        6),
  ('622610', 'Honoraires comptables',                 'charge',        6),
  ('626210', 'Télécoms',                              'charge',        6),
  ('627810', 'Frais bancaires courants',              'charge',        6),
  ('628800', 'Autres charges',                        'charge',        6),
  ('635110', 'Contribution Economique Territoriale',  'charge',        6),
  ('635130', 'Autres impots locaux',                  'charge',        6),
  ('681120', 'Dotation Amort. Corpo.',                'charge',        6),
  ('606100', 'Énergie (électricité, gaz)',            'charge',        6),
  ('606200', 'Carburant',                             'charge',        6),
  ('606400', 'Fournitures administratives',           'charge',        6),
  ('622700', 'Honoraires juridiques et actes',        'charge',        6),
  ('622800', 'Frais de gestion locative',             'charge',        6),
  ('623100', 'Annonces et insertions',                'charge',        6),
  ('625100', 'Voyages et déplacements',               'charge',        6),
  ('626100', 'Frais postaux',                         'charge',        6),
  ('628100', 'Cotisations professionnelles',          'charge',        6),
  ('661100', 'Intérêts des emprunts',                 'charge',        6),
  ('708810', 'Loyers et autres produits',             'produit',       7),
  ('778800', 'Indemnités et produits divers',         'produit',       7);
