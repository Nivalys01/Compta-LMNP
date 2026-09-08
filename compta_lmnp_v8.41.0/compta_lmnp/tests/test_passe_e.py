# Compta LMNP — Copyright © 2026 Sylvain FAURE. Tous droits réservés.
"""
Non-régression des constats de la passe E (import bancaire, liasse PDF, plan).

Chaque test reproduit le SCÉNARIO du rapport d'audit (docs/AUDIT_PASSE_E.md)
et fige le comportement corrigé. Un test qui casse ici signifie qu'un défaut
d'audit est revenu, pas qu'une convention a changé.

Lot traité : E-02 (export à colonnes débit/crédit accepté et inversé) et
E-03 (lignes de montant ignorées en silence).

Lancer :  pytest -q tests/test_passe_e.py
"""
import os
import sys

import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

import import_bancaire


def _releve(tmp_path, contenu, nom="releve.csv"):
    p = tmp_path / nom
    p.write_text(contenu, encoding="utf-8")
    return str(p)


# ═══ E-02 — un export à 4 colonnes ne doit plus être lu à l'envers ═══════

def test_e02_export_quatre_colonnes_refuse(tmp_path):
    """Le scénario exact du rapport.

    Avant : la colonne DÉBIT (non signée) était prise pour un montant, la
    charge de copropriété devenait une recette de loyer avec une période
    servie, et l'import « réussissait » sans un mot. Sur un relevé annuel,
    la totalité des charges basculait en produits.
    """
    p = _releve(tmp_path, "05/01/2026;PRLV SYNDIC;120,50;\n")
    with pytest.raises(ValueError, match="colonnes"):
        import_bancaire.analyser(p)


def test_e02_message_explique_quoi_faire(tmp_path):
    """Un refus qui n'explique pas est un mur : le message doit nommer le
    format attendu et la manœuvre de sortie."""
    p = _releve(tmp_path, "05/01/2026;PRLV SYNDIC;120,50;\n")
    with pytest.raises(ValueError) as exc:
        import_bancaire.analyser(p)
    texte = str(exc.value)
    assert "Ligne 1" in texte                       # où
    assert "4 colonnes au lieu de 3" in texte       # quoi
    assert "date;libelle;montant" in texte          # attendu
    assert "Réexportez" in texte                    # que faire


@pytest.mark.parametrize("ligne", [
    "05/01/2026;PRLV SYNDIC\n",                                  # 2 colonnes
    "05/01/2026;PRLV SYNDIC;120,50;;\n",                         # 5 colonnes
    "05/01/2026;PRLV SYNDIC;;120,50\n",                          # débit/crédit
])
def test_e02_tout_ce_qui_n_est_pas_trois_colonnes_est_refuse(tmp_path, ligne):
    """`len(r) < 3` acceptait 4, 5 ou 12 colonnes. Le compte est désormais
    exact, dans les deux sens."""
    with pytest.raises(ValueError, match="colonnes"):
        import_bancaire.analyser(_releve(tmp_path, ligne))


def test_e02_trois_colonnes_reste_accepte(tmp_path):
    """Le format documenté ne doit pas être emporté par le durcissement."""
    p = _releve(tmp_path, "date;libelle;montant\n"
                          "05/01/2026;PRLV SYNDIC;-120,50\n")
    r = import_bancaire.analyser(p)
    assert len(r["propositions"]) == 1
    assert r["propositions"][0]["montant"] == 120.50
    assert r["rejets"] == []


def test_e02_ligne_vide_finale_ne_fait_pas_echouer(tmp_path):
    """Un CSV se termine par un saut de ligne : la ligne vide qui en résulte
    n'a pas 3 colonnes, mais elle ne porte aucune donnée."""
    p = _releve(tmp_path, "05/01/2026;PRLV SYNDIC;-120,50\n\n")
    assert len(import_bancaire.analyser(p)["propositions"]) == 1


# ═══ E-03 — plus aucune ligne ignorée en silence ════════════════════════

@pytest.mark.parametrize("brut,attendu", [
    ("-120,50",       -120.50),   # forme documentée
    ("120,50-",       -120.50),   # signe suffixe (mainframes)
    ("(120,50)",      -120.50),   # convention anglo-saxonne
    ("-120,50 EUR",   -120.50),   # devise en toutes lettres
    ("-1 234,50 €",  -1234.50),   # milliers + symbole
    ("-1 234,50", -1234.50),  # espace insécable (acquis R6, non régressé)
    ("-1 234,50", -1234.50),  # fine insécable   (idem)
    ("795",            795.0),    # entier sans décimale
    ("+795,50",        795.50),   # signe explicite
])
def test_e03_formats_de_montant_lus(brut, attendu):
    """Les cinq formes du rapport, plus les acquis de la campagne R6."""
    assert import_bancaire._montant(brut) == pytest.approx(attendu)


@pytest.mark.parametrize("contenu,montant", [
    ("05/01/2026;PRLV SYNDIC;120,50-\n",      120.50),
    ("05/01/2026;PRLV SYNDIC;(120,50)\n",     120.50),
    ("05/01/2026;PRLV SYNDIC;-120,50 EUR\n",  120.50),
    ("05/01/2026;PRLV SYNDIC;-1 234,50 €\n", 1234.50),
    ("05/01/2026\tPRLV SYNDIC\t-120,50\n",   120.50),
])
def test_e03_les_cinq_scenarios_ne_renvoient_plus_vide(tmp_path, contenu, montant):
    """Le tableau du rapport : cinq relevés, cinq fois `[]`. Un relevé
    entièrement au format « signe suffixe » produisait ZÉRO proposition et
    l'utilisateur concluait que son relevé ne contenait rien."""
    r = import_bancaire.analyser(_releve(tmp_path, contenu))
    assert len(r["propositions"]) == 1, r
    assert r["propositions"][0]["montant"] == pytest.approx(montant)
    assert r["rejets"] == []


def test_e03_tabulation_reconnue_comme_separateur(tmp_path):
    """Un export tabulé tombait dans une colonne unique, donc rejeté en
    bloc par le test de longueur."""
    p = _releve(tmp_path, "05/01/2026\tPRLV SYNDIC\t-120,50\n")
    props = import_bancaire.analyser(p)["propositions"]
    assert props[0]["libelle"] == "PRLV SYNDIC"
    assert props[0]["montant"] == 120.50


def test_e03_point_virgule_gagne_sur_la_virgule_decimale(tmp_path):
    """La virgule est d'abord un séparateur DÉCIMAL en France : elle ne doit
    pas emporter la détection sur un fichier à point-virgule."""
    p = _releve(tmp_path, "05/01/2026;VIR LOYER;795,50\n"
                          "06/01/2026;PRLV GMF PNO;-138,49\n")
    assert len(import_bancaire.analyser(p)["propositions"]) == 2


def test_e03_ligne_illisible_comptee_et_restituee(tmp_path):
    """Le cœur du constat : ce qui n'est pas lu doit être RENDU, avec son
    numéro de ligne. Le `continue` muet faisait passer un import partiel
    pour un import complet."""
    p = _releve(tmp_path, "date;libelle;montant\n"
                          "05/01/2026;VIR LOYER;795,50\n"
                          "06/01/2026;LIGNE CASSEE;non-un-montant\n"
                          "07/01/2026;PRLV SYNDIC;-120,50\n")
    r = import_bancaire.analyser(p)
    assert len(r["propositions"]) == 2
    assert len(r["rejets"]) == 1
    rejet = r["rejets"][0]
    assert rejet["ligne"] == 3                       # en-tête comprise
    assert "LIGNE CASSEE" in rejet["contenu"]
    assert "non-un-montant" in rejet["raison"]


def test_e03_montant_vide_est_un_rejet_pas_un_zero(tmp_path):
    """Une cellule vide ne vaut pas 0 € : inventer un montant nul serait
    une écriture fausse de plus."""
    r = import_bancaire.analyser(_releve(tmp_path, "05/01/2026;SOLDE;\n"))
    assert r["propositions"] == []
    assert len(r["rejets"]) == 1


def test_e03_proposer_reste_une_liste(tmp_path):
    """`proposer()` garde sa signature : app.py, cli.py et les tests
    existants la consomment comme une liste."""
    p = _releve(tmp_path, "05/01/2026;VIR LOYER;795,50\n")
    props = import_bancaire.proposer(p)
    assert isinstance(props, list) and props[0]["type"] == "loyer"
