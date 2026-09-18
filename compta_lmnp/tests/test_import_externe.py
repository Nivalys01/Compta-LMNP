# Compta LMNP — Copyright © 2026 Sylvain FAURE et les contributeurs.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Le parcours de REPRISE d'une comptabilité existante, de bout en bout.

Trois constats d'usage sur un dossier réel repris depuis un cabinet, tous
au même endroit — la page Immobilisations, la seule étape obligatoire entre
la création du dossier et l'import des FEC :

  A. la ventilation initiale n'offrait qu'UNE ligne par poste. Un meublé
     n'a pas une durée de mobilier : l'électroménager se renouvelle en
     5 ans, les lits en 10, une cuisine intégrée en 15. Il fallait choisir
     une moyenne, c'est-à-dire renoncer à ce que la décomposition apporte.

  B. un composant se créait et ne se défaisait plus. Seule la durée se
     corrigeait ; une valeur brute, un compte ou une date de mise en
     service erronés étaient définitifs, et la seule issue était de
     repartir d'un dossier vierge.

  C. « Reprendre les amortissements antérieurs » ne passait qu'une fois.
     Au deuxième appel — après une durée corrigée, ou sur des à-nouveaux
     venus d'un cabinet plus amorti que le plan — l'écart devenait négatif
     et partait tel quel au crédit : « CHECK constraint failed: debit >= 0
     AND credit >= 0 ». Un message de moteur, sur une opération légitime.

Lancer :  pytest -q tests/test_import_externe.py
"""
import os
import sys

import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

import amortissement
import ecritures
import fiscal
import init_db
import liasse
import operations


@pytest.fixture()
def dossier(tmp_path):
    """Un bien acquis en 2021, saisi ici pour la première fois en 2026."""
    c = init_db.init(str(tmp_path / "reprise.db"), "blanc", annee_cible=2026)
    c.execute("INSERT INTO exploitant (nom, siren, adresse) "
              "VALUES ('EXPLOITANT', '123456789', 'ORLEAT')")
    c.execute("INSERT INTO bien (exploitant_id, libelle, date_acquisition, "
              "prix_total, quote_part_terrain) "
              "VALUES (1, 'appartement 3p', '2021-10-13', 117000, 0)")
    c.commit()
    yield c
    c.close()


def _composant(conn, libelle, valeur, duree, compte_immo, compte_amort,
               dms="2021-10-13", ecriture=True):
    cur = conn.execute(
        "INSERT INTO composant (bien_id, libelle, valeur_brute, duree_annees, "
        "date_mise_service, compte_immo, compte_amort, amortissable) "
        "VALUES (1,?,?,?,?,?,?,?)",
        (libelle, valeur, duree, dms, compte_immo, compte_amort,
         1 if duree else 0))
    composant_id = cur.lastrowid
    conn.commit()
    if ecriture:
        operations.saisir_acquisition(
            conn, compte_immo=compte_immo, montant=valeur,
            date_operation="2026-01-01", libelle=libelle)
    return composant_id


def _solde(conn, compte):
    return conn.execute(
        "SELECT COALESCE(ROUND(SUM(debit - credit), 2), 0) FROM ligne "
        "WHERE compte_num = ?", (compte,)).fetchone()[0]


# ═══ A — plusieurs lignes pour un même poste ══════════════════════════════

class _Formulaire(dict):
    """Un formulaire web : plusieurs champs peuvent porter le même nom."""

    def __init__(self, simples, multiples=None):
        super().__init__(simples)
        self._multiples = multiples or {}

    def getlist(self, nom):
        return self._multiples.get(nom, [])


def test_a_un_poste_dedoublable_accepte_plusieurs_durees():
    """Le cœur du constat A : trois mobiliers, trois durées, un seul
    formulaire. Avant, le poste « Mobilier » était une ligne et une seule."""
    postes = amortissement.postes_ventilation(_Formulaire(
        {"montant_gros_oeuvre": "52000", "duree_gros_oeuvre": "50",
         "montant_mobilier": "9000", "duree_mobilier": "10"},
        {"sup_cle": ["mobilier", "mobilier", "agencements"],
         "sup_libelle": ["Électroménager", "Literie", "Cuisine intégrée"],
         "sup_montant": ["5400", "3000", "7000"],
         "sup_duree": ["5", "8", "15"]}))
    mobiliers = [p for p in postes if p["compte_immo"] == "218400"]
    assert [p["duree"] for p in mobiliers] == [10, 5, 8]
    assert sum(p["montant"] for p in mobiliers) == 17400
    # le poste dédoublé garde le compte et la catégorie de son modèle
    assert {p["categorie"] for p in mobiliers} == {"Mobilier"}
    cuisine = [p for p in postes if p["libelle"] == "Cuisine intégrée"][0]
    assert (cuisine["compte_immo"], cuisine["duree"]) == ("218100", 15)


def test_a_une_ligne_ajoutee_sans_montant_est_ignoree():
    """Ajouter une ligne puis se raviser ne doit pas créer un composant à
    0 € — que la clôture amortirait sur rien."""
    postes = amortissement.postes_ventilation(_Formulaire(
        {"montant_mobilier": "9000", "duree_mobilier": "10"},
        {"sup_cle": ["mobilier"], "sup_libelle": ["Literie"],
         "sup_montant": [""], "sup_duree": ["8"]}))
    assert len(postes) == 1


def test_a_un_libelle_vide_reprend_celui_du_modele():
    postes = amortissement.postes_ventilation(_Formulaire(
        {}, {"sup_cle": ["mobilier"], "sup_libelle": ["   "],
             "sup_montant": ["1200"], "sup_duree": ["5"]}))
    assert postes[0]["libelle"] == "Mobilier et électroménager"


def test_a_seuls_les_postes_prevus_se_dedoublent():
    """Le terrain ne se dédouble pas : il n'a pas de durée à différencier,
    et une deuxième ligne de terrain serait une erreur de saisie."""
    with pytest.raises(ValueError, match="Poste supplémentaire inconnu"):
        amortissement.postes_ventilation(_Formulaire(
            {}, {"sup_cle": ["terrain"], "sup_libelle": ["Jardin"],
                 "sup_montant": ["5000"], "sup_duree": ["0"]}))


def test_a_un_montant_illisible_reste_refuse_avec_le_poste_en_clair():
    with pytest.raises(ValueError, match="n'est pas un montant"):
        amortissement.postes_ventilation(_Formulaire(
            {"montant_facade": "PAS UN NOMBRE"}))


# ═══ B — défaire un composant mal saisi ═══════════════════════════════════

def test_b_la_suppression_contrepasse_l_acquisition(dossier):
    """Le composant (référentiel) disparaît ; son écriture (comptabilité)
    ne disparaît pas — elle est contre-passée. Le FEC garde sa numérotation
    dense et sa piste d'audit."""
    cid = _composant(dossier, "Mobilier", 1700, 8, "218400", "281840")
    assert _solde(dossier, "218400") == 1700
    r = operations.supprimer_composant(dossier, cid)
    assert r["ecriture_annulation"]
    assert _solde(dossier, "218400") == 0
    assert dossier.execute("SELECT COUNT(*) FROM composant").fetchone()[0] == 0
    # les DEUX écritures restent : rien n'est effacé
    assert dossier.execute("SELECT COUNT(*) FROM ecriture").fetchone()[0] == 2


def test_b_on_resaisit_avec_la_bonne_valeur(dossier):
    """La raison d'être de la suppression : corriger une valeur brute, que
    rien ne permettait de reprendre."""
    cid = _composant(dossier, "Mobilier", 1700, 8, "218400", "281840")
    operations.supprimer_composant(dossier, cid)
    _composant(dossier, "Mobilier", 17000, 8, "218400", "281840")
    assert _solde(dossier, "218400") == 17000


def test_b_un_composant_sans_ecriture_se_supprime_aussi(dossier):
    """Reprise d'historique déjà portée par les à-nouveaux : il n'y a rien
    à contre-passer, et ce n'est pas une erreur."""
    cid = _composant(dossier, "Terrain", 9000, None, "211550", None,
                     ecriture=False)
    assert operations.supprimer_composant(dossier, cid)["ecriture_annulation"] is None


def test_b_deux_composants_identiques_ont_chacun_leur_contrepassation(dossier):
    """Deux lignes de même libellé et même montant — cas banal d'une
    ventilation tâtonnante. La contre-passation ne doit pas viser deux fois
    la même écriture, ce qui viderait le compte de moitié en trop."""
    a = _composant(dossier, "Mobilier", 1700, 8, "218400", "281840")
    b = _composant(dossier, "Mobilier", 1700, 8, "218400", "281840")
    assert _solde(dossier, "218400") == 3400
    n_a = operations.supprimer_composant(dossier, a)["ecriture_annulation"]
    n_b = operations.supprimer_composant(dossier, b)["ecriture_annulation"]
    assert n_a != n_b
    assert _solde(dossier, "218400") == 0


def test_b_un_composant_deja_cloture_ne_se_supprime_pas(dossier):
    """Sa dotation est dans un résultat figé et une liasse déjà établie :
    le supprimer la rendrait irreproductible."""
    cid = _composant(dossier, "Mobilier", 17000, 8, "218400", "281840")
    fiscal.cloturer(dossier, 2026, forcer=True)
    with pytest.raises(ValueError, match="clos"):
        operations.supprimer_composant(dossier, cid)
    assert dossier.execute("SELECT COUNT(*) FROM composant").fetchone()[0] == 1


def test_b_un_bien_cede_ne_se_remanie_plus(dossier):
    cid = _composant(dossier, "Mobilier", 1700, 8, "218400", "281840")
    dossier.execute("ALTER TABLE bien ADD COLUMN date_cession TEXT")
    dossier.execute("UPDATE bien SET date_cession='2026-06-30'")
    dossier.commit()
    with pytest.raises(ValueError, match="cédé"):
        operations.supprimer_composant(dossier, cid)


def test_b_un_composant_inconnu_le_dit(dossier):
    with pytest.raises(ValueError, match="introuvable"):
        operations.supprimer_composant(dossier, 4242)


def test_b_la_liasse_reste_conforme_apres_correction(dossier):
    """Contre-épreuve d'ensemble : un montant corrigé en cours de route ne
    doit rien laisser derrière lui."""
    _composant(dossier, "Gros oeuvre", 90000, 50, "213150", "281315")
    faux = _composant(dossier, "Mobilier", 2700, 8, "218400", "281840")
    operations.supprimer_composant(dossier, faux)
    _composant(dossier, "Mobilier", 27000, 8, "218400", "281840")
    for mois in range(1, 13):
        operations.saisir(dossier, type="loyer", montant=700,
                          periode=f"2026-{mois:02d}",
                          date_operation=f"2026-{mois:02d}-05", bien_id=1)
    dossier.commit()
    operations.reprendre_amortissements_anterieurs(dossier, 2026)
    fiscal.cloturer(dossier, 2026, forcer=True)
    res = liasse.generer(dossier, 2026)
    assert res["conforme"], [c["nom"] for c in res["controles"] if not c["ok"]]
    assert res["f2033c"]["totaux"]["brut_fin"] == pytest.approx(117000)


# ═══ C — reprendre les amortissements antérieurs DEUX fois ════════════════

def test_c_une_duree_corrigee_puis_une_seconde_reprise(dossier):
    """LE constat : la durée est le seul champ qui se corrigeait, et la
    corriger après une première reprise rendait la seconde impossible —
    « CHECK constraint failed: debit >= 0 AND credit >= 0 ». L'excédent
    d'amortissement se reprend au DÉBIT du compte 28, c'est tout."""
    _composant(dossier, "Mobilier", 17000, 5, "218400", "281840")
    premiere = operations.reprendre_amortissements_anterieurs(dossier, 2026)
    assert premiere["total"] > 0
    dossier.execute("UPDATE composant SET duree_annees = 10")
    dossier.commit()
    seconde = operations.reprendre_amortissements_anterieurs(dossier, 2026)
    assert seconde["total"] < 0                   # un excédent, donc au débit
    # et les comptes 28 collent désormais au plan : plus rien à reprendre
    assert operations.amortissements_anterieurs_manquants(
        dossier, 2026)["par_compte"] == {}


def test_c_des_a_nouveaux_plus_amortis_que_le_plan(dossier):
    """Le cas du cabinet : il amortissait le mobilier en 5 ans, le plan
    saisi ici le déroule sur 8. L'écart est négatif sur un compte, positif
    sur l'autre — une écriture, deux sens."""
    _composant(dossier, "Gros oeuvre", 100000, 50, "213150", "281315")
    _composant(dossier, "Mobilier", 17000, 8, "218400", "281840")
    ecritures.inserer(dossier, journal="AN", annee=2026, date="2026-01-01",
                      libelle="A-nouveaux du cabinet", piece_ref="AN",
                      lignes=[("281840", 0.0, 14000.0),
                              ("108000", 14000.0, 0.0)])
    manquants = operations.amortissements_anterieurs_manquants(dossier, 2026)
    assert manquants["par_compte"]["281315"] > 0
    assert manquants["par_compte"]["281840"] < 0
    r = operations.reprendre_amortissements_anterieurs(dossier, 2026)
    num = r["ecriture_num"]
    sens = dict(dossier.execute(
        "SELECT l.compte_num, ROUND(l.credit - l.debit, 2) FROM ligne l "
        "JOIN ecriture e ON e.id = l.ecriture_id WHERE e.ecriture_num = ?",
        (num,)).fetchall())
    assert sens["281315"] > 0 and sens["281840"] < 0
    assert operations.amortissements_anterieurs_manquants(
        dossier, 2026)["par_compte"] == {}


def test_c_aucune_ligne_negative_n_atteint_la_base(dossier):
    """La garde de fond : quoi qu'il arrive, aucun débit ni crédit négatif
    ne part vers la base — c'était le message d'erreur brut du moteur."""
    _composant(dossier, "Mobilier", 17000, 5, "218400", "281840")
    operations.reprendre_amortissements_anterieurs(dossier, 2026)
    dossier.execute("UPDATE composant SET duree_annees = 10")
    dossier.commit()
    operations.reprendre_amortissements_anterieurs(dossier, 2026)
    assert dossier.execute(
        "SELECT COUNT(*) FROM ligne WHERE debit < 0 OR credit < 0"
    ).fetchone()[0] == 0


def test_c_pas_de_ligne_a_zero_quand_les_sens_s_annulent(dossier):
    """Deux écarts opposés qui se compensent exactement : la contrepartie
    exploitant serait une ligne à 0,00 €, que le FEC afficherait sans rien
    dire. L'écriture s'équilibre alors entre comptes 28."""
    _composant(dossier, "Mobilier A", 10000, 5, "218400", "281840")
    _composant(dossier, "Agencements", 10000, 5, "218100", "281810")
    operations.reprendre_amortissements_anterieurs(dossier, 2026)
    dossier.execute("UPDATE composant SET duree_annees = 10 "
                    "WHERE libelle = 'Mobilier A'")
    dossier.execute("UPDATE composant SET duree_annees = 3 "
                    "WHERE libelle = 'Agencements'")
    dossier.commit()
    r = operations.reprendre_amortissements_anterieurs(dossier, 2026)
    lignes = dossier.execute(
        "SELECT l.compte_num, l.debit, l.credit FROM ligne l "
        "JOIN ecriture e ON e.id = l.ecriture_id WHERE e.ecriture_num = ?",
        (r["ecriture_num"],)).fetchall()
    assert all(d > 0 or c > 0 for _cpt, d, c in lignes)
    assert round(sum(d for _c, d, _cr in lignes), 2) == \
           round(sum(c for _c, _d, c in lignes), 2)


def test_c_sans_a_nouveaux_la_reprise_ne_compte_pas_double(dossier):
    """Un dossier tenu ici depuis l'origine, sans à-nouveaux : la reprise
    complétait le cumul des exercices antérieurs, puis se prenait elle-même
    pour un à-nouveau de bilan au deuxième passage et redemandait la
    différence. Le compte 28 finissait au-dessus du plan, sans qu'aucun
    équilibre ne le trahisse."""
    import reprise
    _composant(dossier, "Gros oeuvre", 100000, 50, "213150", "281315")
    reprise.ouvrir_exercice(dossier, 2025)
    ecritures.inserer(dossier, journal="OD", annee=2025, date="2025-12-31",
                      libelle="DAA 2025", piece_ref="DAA",
                      lignes=[("681120", 2000.0, 0.0),
                              ("281315", 0.0, 2000.0)])
    operations.reprendre_amortissements_anterieurs(dossier, 2026)
    plan = operations.amortissements_anterieurs_manquants(dossier, 2026)
    assert plan["par_compte"] == {}, "le cumul est déjà complet"
    with pytest.raises(ValueError, match="Aucun amortissement"):
        operations.reprendre_amortissements_anterieurs(dossier, 2026)
    assert _solde(dossier, "281315") == pytest.approx(-8438.36, abs=0.5)


def test_c_le_resultat_de_l_exercice_reste_intact(dossier):
    """Contre-épreuve : une reprise, dans un sens comme dans l'autre, ne
    touche que le bilan. Ce n'est pas une dotation."""
    _composant(dossier, "Mobilier", 17000, 5, "218400", "281840")
    operations.saisir(dossier, type="loyer", montant=700, periode="2026-01",
                      date_operation="2026-01-05", bien_id=1)
    dossier.commit()
    avant = liasse.generer(dossier, 2026)["f2033b"]["benefice_ou_perte_310"]
    operations.reprendre_amortissements_anterieurs(dossier, 2026)
    dossier.execute("UPDATE composant SET duree_annees = 10")
    dossier.commit()
    operations.reprendre_amortissements_anterieurs(dossier, 2026)
    apres = liasse.generer(dossier, 2026)["f2033b"]["benefice_ou_perte_310"]
    assert apres == pytest.approx(avant)


# ═══ Le parcours est ANNONCÉ, pas seulement possible ══════════════════════

def test_la_page_d_accueil_donne_les_trois_etapes_dans_l_ordre():
    """Le constat d'origine : pour importer un FEC, il fallait deviner
    l'onglet « Nouvel exercice », et surtout deviner que les immobilisations
    devaient être saisies AVANT. Rien ne le disait."""
    import pages
    page = pages.PAGE_DEMARRAGE
    assert "/immobilisations" in page and "/exercice/nouveau" in page
    # la procédure NUMÉROTÉE, et dans cet ordre-là
    etapes = page.split("<ol")[1].split("</ol>")[0].split("<li>")[1:]
    assert len(etapes) == 3
    assert "identité" in etapes[0]
    assert "immobilisations" in etapes[1].lower()
    assert "ordre d'acquisition" in etapes[1]
    assert "FEC" in etapes[2] and "/exercice/nouveau" in etapes[2]
    assert "plus ancien au plus récent" in etapes[2]
    # et l'infobulle du titre porte la même consigne, pour qui ne lit pas
    assert "Immobilisations" in page.split('data-aide="')[1].split('"')[0]
