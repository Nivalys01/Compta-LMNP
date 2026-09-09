# Compta LMNP — Copyright © 2026 Sylvain FAURE. Tous droits réservés.
"""
Reprise interne des à-nouveaux (clôture N → ouverture N+1 sans FEC)
et liasse fiscale (2031 / 2033 A-B-C, suivi des reports, aide 2042C-PRO).
"""
import os
import sys
from datetime import date

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

import pytest

import audit_cycle
import fiscal
import init_db
import liasse
import reprise

ANNEE = date.today().year


@pytest.fixture()
def dossier_clos(tmp_path):
    """Dossier blanc + exercice complet (acquisitions, 12 loyers, charges) clôturé."""
    db = str(tmp_path / "t.db")
    conn = init_db.init(db, "blanc", annee_cible=ANNEE)
    audit_cycle._creer_dossier(conn, ANNEE)
    audit_cycle._saisir_annee(conn, ANNEE, 800.0,
                              [("charge_copro", 600.0, "03"),
                               ("assurance", 200.0, "01"),
                               ("cfe", 300.0, "11")])
    fiscal.cloturer(conn, ANNEE)
    yield conn
    conn.close()


# ── Reprise interne ──────────────────────────────────────────────────────────

def test_reprise_interne_equilibree_et_120000_solde(dossier_clos):
    conn = dossier_clos
    conn.execute("INSERT INTO exercice (annee,date_debut,date_fin,statut) "
                 "VALUES (?,?,?,'ouvert')",
                 (ANNEE + 1, f"{ANNEE+1}-01-01", f"{ANNEE+1}-12-31"))
    conn.commit()
    info = reprise.construire_an_interne(conn, ANNEE + 1)
    d, c = reprise.controle_equilibre(conn, ANNEE + 1)
    assert abs(d - c) < 0.005
    bal = reprise.lire_balance_interne(conn, ANNEE + 1)
    assert abs(bal.get("120000", 0.0)) < 0.005          # résultat affecté
    assert info["annee_source"] == ANNEE


def test_reprise_interne_conserve_la_vnc(dossier_clos):
    conn = dossier_clos
    vnc_cloture = liasse.generer(conn, ANNEE)["f2033a"]["immo_corporelles_net"]
    conn.execute("INSERT INTO exercice (annee,date_debut,date_fin,statut) "
                 "VALUES (?,?,?,'ouvert')",
                 (ANNEE + 1, f"{ANNEE+1}-01-01", f"{ANNEE+1}-12-31"))
    conn.commit()
    reprise.construire_an_interne(conn, ANNEE + 1)
    bal = reprise.lire_balance_interne(conn, ANNEE + 1)
    types = dict(conn.execute("SELECT numero, type FROM compte").fetchall())
    actif_net = round(sum(v for k, v in bal.items()
                          if types.get(k) in ("actif", "amortissement")), 2)
    assert abs(actif_net - vnc_cloture) < 0.01


def test_reprise_refuse_exercice_non_clos(tmp_path):
    db = str(tmp_path / "t.db")
    conn = init_db.init(db, "blanc", annee_cible=ANNEE)      # ouvert
    conn.execute("INSERT INTO exercice (annee,date_debut,date_fin,statut) "
                 "VALUES (?,?,?,'ouvert')",
                 (ANNEE + 1, f"{ANNEE+1}-01-01", f"{ANNEE+1}-12-31"))
    conn.commit()
    with pytest.raises(ValueError, match="pas clôturé"):
        reprise.construire_an_interne(conn, ANNEE + 1)
    conn.close()


def test_reprise_refuse_double_an(dossier_clos):
    conn = dossier_clos
    conn.execute("INSERT INTO exercice (annee,date_debut,date_fin,statut) "
                 "VALUES (?,?,?,'ouvert')",
                 (ANNEE + 1, f"{ANNEE+1}-01-01", f"{ANNEE+1}-12-31"))
    conn.commit()
    reprise.construire_an_interne(conn, ANNEE + 1)
    with pytest.raises(ValueError, match="déjà"):
        reprise.construire_an_interne(conn, ANNEE + 1)


def test_reprise_interne_equivalente_a_la_reprise_fec(tmp_path):
    """Balance d'ouverture identique au centime entre la voie FEC et la voie interne."""
    fec = os.path.join(HERE, "reference/FEC_REFERENCE_2025.txt")
    ref = init_db.init(str(tmp_path / "ref.db"), "demo", annee_cible=2026)
    bal_fec = {k: round(v, 2)
               for k, v in reprise.lire_balance_interne(ref, 2026).items()
               if abs(v) > 0.005}
    ref.close()

    conn = init_db.init(str(tmp_path / "int.db"), "blanc", annee_cible=2025)
    cur = conn.cursor()
    cur.execute("INSERT INTO ecriture (journal_code,ecriture_num,ecriture_date,"
                "exercice_annee,piece_ref,piece_date,libelle,valid_date) "
                "VALUES ('OD',1,'2025-06-30',2025,'NA','2025-06-30','hist','2025-06-30')")
    eid = cur.lastrowid
    for compte, net in reprise.lire_balance_fec(fec).items():
        if abs(net) < 0.005:
            continue
        cur.execute("INSERT INTO ligne (ecriture_id,compte_num,libelle,debit,credit) "
                    "VALUES (?,?,?,?,?)",
                    (eid, compte, "hist",
                     round(net, 2) if net > 0 else 0.0,
                     round(-net, 2) if net < 0 else 0.0))
    conn.execute("UPDATE exercice SET statut='clos' WHERE annee=2025")
    conn.execute("INSERT INTO exercice (annee,date_debut,date_fin,statut) "
                 "VALUES (2026,'2026-01-01','2026-12-31','ouvert')")
    conn.commit()
    reprise.construire_an_interne(conn, 2026)
    bal_int = {k: round(v, 2)
               for k, v in reprise.lire_balance_interne(conn, 2026).items()
               if abs(v) > 0.005}
    conn.close()
    assert bal_fec == bal_int


# ── Liasse fiscale ───────────────────────────────────────────────────────────

def test_liasse_conforme_et_coherente(dossier_clos):
    L = liasse.generer(dossier_clos, ANNEE)
    assert L["conforme"], [c for c in L["controles"] if not c["ok"]]
    a, b, c3 = L["f2033a"], L["f2033b"], L["f2033c"]
    assert abs(b["resultat_fiscal_352"]) < 0.005          # ligne 352 = 0
    assert a["equilibre"]                                  # actif = passif
    assert abs(c3["totaux"]["brut_fin"] - a["immo_corporelles_brut_028"]) < 0.005
    assert abs(c3["totaux"]["amort_fin"] - a["amortissements_030"]) < 0.005
    # Scénario nominal : 9 600 − 1 100 − 5 000 = bénéfice 3 500 € → 7a et 5NA
    assert L["f2031"]["bic_non_pro_7a_benefice"] == pytest.approx(3500.0)
    assert L["aide_2042c"]["case_5NA"] == 3500
    assert L["aide_2042c"]["case_5NY"] is None


def test_liasse_deficit_alimente_5ny_et_millesimes(tmp_path):
    """Exercice déficitaire (hors 39 C) → 7b, 5NY, puis millésime en 5Gx l'année suivante."""
    db = str(tmp_path / "t.db")
    conn = init_db.init(db, "blanc", annee_cible=ANNEE)
    audit_cycle._creer_dossier(conn, ANNEE)
    # Loyers 500×12 = 6 000 ; charges 400 → plafond 5 600 > dotation 5 000,
    # donc vrai déficit LMNP (pas un report 39 C) : 6 000 − 400 − 5 000 = 600…
    # non : résultat = +600. Il faut des charges plus lourdes :
    # charges 2 000 → plafond 4 000 < dotation 5 000 → report 1 000, fiscal 0.
    # Pour un déficit NET : charges déductibles élevées SANS toucher au plafond
    # est impossible (toutes les charges le réduisent). Le déficit LMNP naît
    # quand plafond ≥ dotation mais produits < charges + dotation :
    # loyers 5 200, charges 100 → plafond 5 100 ≥ 5 000, fiscal = 5 200-100-5 000 = 100 > 0…
    # loyers 4 000, charges 0 → plafond 4 000 < 5 000. Le déficit pur exige une
    # dotation faible : on retire le mobilier pour ne garder que le bâti (4 000).
    conn.execute("DELETE FROM composant WHERE code_immo='AUD-MOB'")
    conn.commit()
    audit_cycle._saisir_annee(conn, ANNEE, 300.0,     # 3 600 de loyers
                              [("charge_copro", 200.0, "03")])
    # plafond = 3 400 < dotation 4 000 → report 600 ; fiscal = -600+600 = 0.
    # Toujours pas de déficit : en LMNP mono-bien, le déficit net vient des
    # charges financières/exceptionnelles. On force via retraitement négatif.
    res = fiscal.cloturer(conn, ANNEE, autres_retraitements=-450.0)
    assert res["resultat_fiscal"] == pytest.approx(-450.0)

    L = liasse.generer(conn, ANNEE)
    assert L["f2031"]["bic_non_pro_7b_deficit"] == pytest.approx(450.0)
    assert L["aide_2042c"]["case_5NY"] == 450
    assert L["page_garde"]["deficit_lmnp"] == pytest.approx(450.0)

    # Exercice suivant : le millésime N doit sortir en case 5GJ (N-1).
    conn.execute("INSERT INTO exercice (annee,date_debut,date_fin,statut) "
                 "VALUES (?,?,?,'ouvert')",
                 (ANNEE + 1, f"{ANNEE+1}-01-01", f"{ANNEE+1}-12-31"))
    conn.commit()
    reprise.construire_an_interne(conn, ANNEE + 1)
    audit_cycle._saisir_annee(conn, ANNEE + 1, 300.0, [])
    fiscal.cloturer(conn, ANNEE + 1)
    aide = liasse.generer(conn, ANNEE + 1)["aide_2042c"]
    cases = {c["case"]: c for c in aide["cases_deficits_anterieurs"]}
    assert "5GJ" in cases and cases["5GJ"]["annee_origine"] == ANNEE
    assert cases["5GJ"]["montant"] == 450
    conn.close()


def test_liasse_demo_reconcilie_bilan_ouverture(tmp_path):
    """Dossier démo (reprise FEC 2025 réel) : la liasse provisoire 2026 doit
    réconcilier le bilan d'ouverture des logiciels du marché (brut 139 908,66 €, VNC 118 578,78 €)."""
    conn = init_db.init(str(tmp_path / "demo.db"), "demo", annee_cible=2026)
    L = liasse.generer(conn, 2026)
    conn.close()
    assert L["provisoire"]
    a = L["f2033a"]
    assert a["immo_corporelles_brut_028"] == pytest.approx(139908.66, abs=0.01)
    assert a["immo_corporelles_net"] == pytest.approx(118578.78, abs=0.01)
    assert a["equilibre"]
    # 2033-C fin d'exercice = mêmes valeurs brutes (aucune acquisition 2026)
    assert L["f2033c"]["totaux"]["brut_fin"] == pytest.approx(139908.66, abs=0.01)
