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
  -- Dettes financières et de garantie. Sans elles, une mensualité de prêt et
  -- un dépôt de garantie n'avaient AUCUNE destination correcte : le capital
  -- remboursé partait en charge (déduction indue, redressement classique en
  -- LMNP au réel) et le dépôt encaissé devenait un loyer imposable.
  ('164000', 'Emprunts auprès des établissements de crédit', 'passif',  1),
  ('165000', 'Dépôts et cautionnements reçus',        'passif',        1),
  ('211550', 'Terrain',                               'actif',         2),
  ('213150', 'Bâtiment',                              'actif',         2),
  ('218100', 'Installation et agencement',            'actif',         2),
  ('218400', 'Mobilier',                              'actif',         2),
  ('281315', 'Amort. Bâtiment',                       'amortissement', 2),
  ('281810', 'Amort. Installation et agencement',     'amortissement', 2),
  ('281840', 'Amort. Mobilier',                       'amortissement', 2),
  ('401000', 'Fournisseurs',                          'passif',        4),
  ('411000', 'Locataires',                            'actif',         4),
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
  -- 758 = produit COURANT de gestion (indemnité d'assurance, remboursement
  -- reçu). 778 est un compte EXCEPTIONNEL : y loger un produit courant est
  -- une erreur de nature, même si la liasse ne les distingue pas encore.
  ('758000', 'Produits divers de gestion courante',   'produit',       7),
  ('778800', 'Indemnités et produits divers',         'produit',       7);
