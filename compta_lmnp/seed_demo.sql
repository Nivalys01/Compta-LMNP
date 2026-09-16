-- ====================================================================
-- Seed DÉMONSTRATION — dossier FICTIF, généré par outils_demo.py.
--
-- Dérivé d'un dossier réel : montants x 0.78, identité et
-- libellés remplacés. AUCUNE donnée personnelle. C'est CE fichier qui
-- est livré au client (seed_exemple.sql, lui, ne quitte jamais le
-- poste de développement).
--
-- Ne pas modifier à la main : régénérer avec `python outils_demo.py`.
-- ====================================================================

-- --- Exploitant & bien -----------------------------------------------------
INSERT INTO exploitant (id, nom, siren, adresse) VALUES
  (1, 'MARTIN CAMILLE', '000000000', '14 Rue Gergovia, 63000 Clermont-Ferrand');

INSERT INTO bien (id, exploitant_id, libelle, adresse, date_acquisition, prix_total, quote_part_terrain) VALUES
  (1, 1, 'Appartement de demonstration', '14 Rue Gergovia, 63000 Clermont-Ferrand',
   '2021-06-17', 91260.0, 0.073504);

-- --- Composants (code_immo = réf. pièce prestataire ; valeurs brutes EXACTES) ------
INSERT INTO composant
  (bien_id, code_immo, libelle, categorie, valeur_brute, duree_annees, date_mise_service, compte_immo, compte_amort, amortissable) VALUES
  (1, 'DEMO01', 'Terrain',                          'Terrain',     6707.61, NULL, '2021-11-01', '211550', NULL,     0),
  (1, 'DEMO02', 'Gros oeuvre',                      'Bâtiment',   45629.97,   55, '2021-11-01', '213150', '281315', 1),
  (1, 'DEMO03', 'Aménagements intérieurs',          'Bâtiment',   23326.06,   25, '2021-11-01', '213150', '281315', 1),
  (1, 'DEMO04', 'Etanchéité',                       'Bâtiment',   15596.33,   25, '2021-11-01', '213150', '281315', 1),
  (1, 'DEMO05', 'Installation électrique',          'Bâtiment',    1299.87,   20, '2021-11-01', '213150', '281315', 1),
  (1, 'DEMO06', 'Aménagements intérieurs - Aménagement', 'Bâtiment', 0.10,   15, '2022-01-01', '213150', '281315', 1),
  (1, 'DEMO07', 'Travaux - Carrelage',              'Travaux',     1143.88,   20, '2021-11-01', '218100', '281810', 1),
  (1, 'DEMO08', 'Travaux - Huisseries coté Est',    'Travaux',     1564.13,   25, '2022-03-11', '218100', '281810', 1),
  (1, 'DEMO09', 'Travaux - Huisseries Coté OUEST',  'Travaux',     5137.03,   25, '2022-05-25', '218100', '281810', 1),
  (1, 'DEMO10', 'Travaux - Porte d''entrée',        'Travaux',     1470.59,   20, '2022-10-26', '218100', '281810', 1),
  (1, 'DEMO11', 'Cuisine équipée - Cuisine IKEA',   'Mobilier',    2574.55,   10, '2021-11-01', '218400', '281840', 1),
  (1, 'DEMO12', 'Electroménager - MDA',             'Mobilier',    1215.05,    5, '2021-11-01', '218400', '281840', 1),
  (1, 'DEMO13', 'Mobilier - Mobilier Salon',        'Mobilier',    1499.86,    5, '2021-11-01', '218400', '281840', 1),
  (1, 'DEMO14', 'Mobilier - Mobiliers chambres',    'Mobilier',    1963.72,    5, '2021-11-01', '218400', '281840', 1);

-- --- Stocks fiscaux d'ENTRÉE (clôture 2025, source prestataire) --------------------
INSERT INTO suivi_39c
  (exercice_annee, plafond_deductible, dotation_exercice, stock_ouverture, report_annee, utilisation_annee, stock_cloture)
VALUES
  (2025, 3842.28, 4043.5, 231.66, 201.24, 0.0, 433.68);

INSERT INTO deficit_lmnp (annee_origine, montant_initial, solde, annee_expiration) VALUES
  (2021, 9554.22, 8985.6, 2031),
  (2022,   194.22,   194.22, 2032),
  (2024,   484.38,   484.38, 2034),
  (2025,   491.4,   491.4, 2035);