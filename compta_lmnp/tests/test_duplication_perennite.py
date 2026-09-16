# Compta LMNP — Copyright © 2026 Sylvain FAURE et les contributeurs.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Duplication d'opérations (→ M+1) et pérennité pluri-annuelle : enchaînement
de 12 exercices en reprise interne, amortissements arrivant à terme,
péremption des déficits, liasse conforme chaque année.
"""
import os
import sys
from datetime import date

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

import pytest

import audit_cycle
import controles
import fiscal
import init_db
import liasse
import operations
import reprise

AN = date.today().year


@pytest.fixture()
def conn(tmp_path):
    c = init_db.init(str(tmp_path / "t.db"), "blanc", annee_cible=AN)
    audit_cycle._creer_dossier(c, AN)
    yield c
    c.close()


# ── Duplication → M+1 ────────────────────────────────────────────────────────

def test_duplication_mois_suivant(conn):
    src = operations.saisir(conn, type="loyer", montant=795.0,
                            date_operation=f"{AN}-03-05", periode=f"{AN}-03")
    r = operations.dupliquer(conn, src["operation_id"])
    op = conn.execute("SELECT date_operation, periode, montant, type, source "
                      "FROM operation WHERE id=?", (r["operation_id"],)).fetchone()
    assert op[0] == f"{AN}-04-05" and op[1] == f"{AN}-04"
    assert op[2] == 795.0 and op[3] == "loyer" and op[4] == "duplication"
    # L'écriture générée est équilibrée et sur le bon exercice.
    d, c = conn.execute(
        "SELECT ROUND(SUM(l.debit),2), ROUND(SUM(l.credit),2) FROM ligne l "
        "WHERE l.ecriture_id=?", (r["ecriture_id"],)).fetchone()
    assert d == c == 795.0


def test_duplication_borne_fin_de_mois(conn):
    src = operations.saisir(conn, type="loyer", montant=795.0,
                            date_operation=f"{AN}-01-31", periode=f"{AN}-01")
    r = operations.dupliquer(conn, src["operation_id"])
    d = conn.execute("SELECT date_operation FROM operation WHERE id=?",
                     (r["operation_id"],)).fetchone()[0]
    dernier_fev = 29 if AN % 4 == 0 and (AN % 100 != 0 or AN % 400 == 0) else 28
    assert d == f"{AN}-02-{dernier_fev}"


def test_duplication_conserve_libelle_personnalise(conn):
    src = operations.saisir(conn, type="loyer", montant=795.0,
                            date_operation=f"{AN}-03-05", periode=f"{AN}-03",
                            libelle="Loyer M. Martin")
    r = operations.dupliquer(conn, src["operation_id"])
    lib = conn.execute("SELECT libelle FROM operation WHERE id=?",
                       (r["operation_id"],)).fetchone()[0]
    assert lib == "Loyer M. Martin"


def test_duplication_ne_declenche_pas_le_controle_doublon(conn):
    src = operations.saisir(conn, type="loyer", montant=795.0,
                            date_operation=f"{AN}-03-05", periode=f"{AN}-03")
    operations.dupliquer(conn, src["operation_id"])
    assert not any(a.code == "DOUBLON" for a in controles.controler(conn, AN))


def test_duplication_refuse_exercice_absent_ou_clos(conn):
    src_dec = operations.saisir(conn, type="loyer", montant=795.0,
                                date_operation=f"{AN}-12-05", periode=f"{AN}-12")
    src_mars = operations.saisir(conn, type="loyer", montant=795.0,
                                 date_operation=f"{AN}-03-05", periode=f"{AN}-03")
    # Décembre → janvier N+1 : l'exercice cible n'existe pas encore.
    with pytest.raises(ValueError, match="n'existe pas encore"):
        operations.dupliquer(conn, src_dec["operation_id"])
    fiscal.cloturer(conn, AN)
    # Mars → avril, mais l'exercice AN est désormais clos : refus explicite.
    with pytest.raises(ValueError, match="clos"):
        operations.dupliquer(conn, src_mars["operation_id"])


def test_duplication_via_interface(tmp_path):
    import app as A
    A.DB = str(tmp_path / "c.db")
    A.BAC_A_SABLE_DB = str(tmp_path / "b.db")
    c0 = init_db.init(A.DB, "blanc", annee_cible=AN)
    audit_cycle._creer_dossier(c0, AN)
    src = operations.saisir(c0, type="loyer", montant=795.0,
                            date_operation=f"{AN}-03-05", periode=f"{AN}-03")
    c0.close()
    client = A.app.test_client()
    assert "→ M+1" in client.get("/saisie").get_data(as_text=True)
    r = client.post(f"/operation/{src['operation_id']}/dupliquer",
                    follow_redirects=True)
    assert "dupliquée au mois suivant" in r.get_data(as_text=True)


# ── Endurance : 12 exercices enchaînés en reprise interne ────────────────────

def test_douze_exercices_enchaines(conn):
    """Réponse à « puis-je ouvrir indéfiniment un exercice depuis la clôture
    précédente ? » : 12 ans de cycle complet, avec vérifications annuelles.

    Scénario : année 1 fortement déficitaire (retraitement négatif → millésime
    de déficit), années suivantes à loyers modestes. Le mobilier (5 ans)
    s'amortit totalement en cours de route, le déficit de l'année 1 doit
    périmer à N+11 sans avoir été imputé (règle des 10 ans)."""
    dot_totale_precedente = None
    for i in range(12):
        annee = AN + i
        if i > 0:
            reprise.ouvrir_exercice(conn, annee)           # reprise interne
            an_d, an_c = reprise.controle_equilibre(conn, annee)
            assert abs(an_d - an_c) < 0.005, f"AN déséquilibrés en {annee}"
            bal = reprise.lire_balance_interne(conn, annee)
            assert abs(bal.get("120000", 0.0)) < 0.005, f"120000 non soldé en {annee}"

        audit_cycle._saisir_annee(conn, annee, loyer_mensuel=450.0,
                                  charges=[("charge_copro", 300.0, "03")])
        retraitement = -900.0 if i == 0 else 0.0                # déficit an 1
        res = fiscal.cloturer(conn, annee,
                              autres_retraitements=retraitement)

        L = liasse.generer(conn, annee)
        assert L["conforme"], (annee, [c for c in L["controles"] if not c["ok"]])

        dot = res["agregats"]["dotation"]
        if i == 0:
            assert dot == pytest.approx(5000.0)                 # bâti + mobilier
            assert res["deficits"]["deficit_cree"] == pytest.approx(800.0)  # 5400-300-5000-900
        if i == 5:
            # Mobilier (5 ans) totalement amorti : seule la dotation bâti reste.
            assert dot == pytest.approx(4000.0), f"dotation an {annee} = {dot}"
        if dot_totale_precedente is not None:
            assert dot <= dot_totale_precedente + 0.01          # jamais croissante
        dot_totale_precedente = dot

    # Péremption : le déficit de l'année 1 (expiration AN+10) est purgé,
    # jamais imputé (aucun exercice bénéficiaire dans le scénario).
    solde = conn.execute("SELECT solde FROM deficit_lmnp WHERE annee_origine=?",
                         (AN,)).fetchone()[0]
    assert solde == 0.0, "le millésime périmé devrait être purgé"
    exp = conn.execute("SELECT annee_expiration FROM deficit_lmnp "
                       "WHERE annee_origine=?", (AN,)).fetchone()[0]
    assert exp == AN + 10

    # Bilan de fin de course : VNC = brut − amortissements théoriques cumulés,
    # équilibre parfait après 12 reprises successives.
    a = liasse.generer(conn, AN + 11)["f2033a"]
    assert a["equilibre"]
    assert a["immo_corporelles_brut_028"] == pytest.approx(115000.0)
    # Bâti 12×4000 = 48 000 ; mobilier plafonné à 5 000.
    assert a["amortissements_030"] == pytest.approx(53000.0)
