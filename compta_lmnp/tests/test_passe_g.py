# Compta LMNP — Copyright © 2026 Sylvain FAURE et les contributeurs.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Non-régression des constats de la passe G (régularité comptable, FEC).

Le fil rouge de cette passe est une famille de défauts qui ne produisaient
aucune erreur : une reprise qui perdait des écritures en annonçant un
succès, un validateur qui déclarait conformes des fichiers dont il n'avait
pas pu calculer l'équilibre, un export qui taisait ce qu'il ne savait pas
restituer, une cession enregistrée pour un prix qui n'était pas un nombre.
Chacun rendait un verdict rassurant sur un travail qu'il n'avait pas fait.

Ces tests figent l'exigence inverse, dans les deux sens :
  - **rien ne disparaît en silence** — toute ligne, tout montant, tout
    champ qui ne peut pas être traité fait ÉCHOUER l'opération en se
    nommant, au lieu d'être écarté ;
  - **rien n'est rejeté à tort** — les formes que l'arrêté A47 A-1 admet
    (barre verticale, signe suffixé, numéro alphanumérique, colonnes
    supplémentaires, ISO-8859-15) sont lues, et une rupture de numérotation
    qu'un mode brouillard explique reste une observation.

Aucune donnée réelle : exploitant fictif, base blanche, FEC construits ici.

Lancer :  pytest -q tests/test_passe_g.py
"""
import os
import subprocess
import sys
import tempfile

import pytest

import conftest  # noqa: F401  (insère la racine et modules/ dans sys.path)

import amortissement
import cession
import controles
import ecritures
import export_fec
import fec_io
import fiscal
import init_db
import operations
import rejeu_fec
import reprise
import valider_fec

COLS = fec_io.COLONNES


# ── Fabriques de pièces fictives ──────────────────────────────────────────

@pytest.fixture
def base(tmp_path):
    """Base BLANCHE, exercice 2026 ouvert, un exploitant et un bien fictifs."""
    chemin = str(tmp_path / "fictif.db")
    conn = init_db.init_blanc(chemin, 2026)
    conn.execute("INSERT INTO exploitant VALUES "
                 "(1,'Exploitant fictif','000000000','Adresse fictive')")
    conn.execute("INSERT INTO bien(id,exploitant_id,libelle,prix_total) "
                 "VALUES (1,1,'Bien fictif',12000)")
    conn.commit()
    yield conn
    conn.close()


def ligne(**kw):
    """Une ligne de FEC fictive, tous champs nommés."""
    r = dict.fromkeys(COLS, "")
    r.update(JournalCode="BQ", JournalLib="Journal fictif", EcritureNum="1",
             EcritureDate="20260110", CompteNum="108000",
             CompteLib="Compte fictif", PieceRef="P-1", PieceDate="20260110",
             EcritureLib="Loyer fictif", Debit="800", Credit="",
             ValidDate="20260110")
    r.update(kw)
    return r


def ecriture(num="1", journal="BQ", montant="800", date="20260110"):
    """Une écriture fictive ÉQUILIBRÉE de deux lignes."""
    return [ligne(EcritureNum=str(num), JournalCode=journal, Debit=montant,
                  EcritureDate=date, PieceDate=date, ValidDate=date),
            ligne(EcritureNum=str(num), JournalCode=journal, Debit="",
                  Credit=montant, CompteNum="708810", EcritureDate=date,
                  PieceDate=date, ValidDate=date)]


def ecrire_fec(tmp_path, nom, lignes, entete=None, sep="\t",
               encodage="utf-8", fin="\r\n"):
    """Écrit un FEC fictif. `lignes` : des dicts, ou des listes déjà
    tronquées pour les essais de structure."""
    entete = entete or COLS
    p = tmp_path / nom
    texte = [sep.join(entete)]
    for r in lignes:
        texte.append(sep.join(r.get(k, "") for k in entete)
                     if isinstance(r, dict) else sep.join(r))
    p.write_bytes((fin.join(texte) + fin).encode(encodage))
    return str(p)


def loyer(conn, montant=800, date="2026-01-10"):
    return operations.saisir(conn, type="loyer", montant=montant,
                             date_operation=date, periode=date[:7])


def compter(conn):
    return {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            for t in ("ecriture", "ligne")}


# ═══ G-01 — l'équilibre porte sur les montants réellement inscrits ═══════

def test_g01_equilibre_verifie_apres_arrondi(base):
    """Le contrôle sommait les montants BRUTS et n'arrondissait qu'à la fin,
    alors que l'insertion arrondit CHAQUE ligne : deux débits de 100,004 €
    contre un crédit de 200,008 € passaient (200,01 = 200,01) et
    s'inscrivaient en 100,00 + 100,00 contre 200,01. Un centime de
    déséquilibre durable, qu'aucun compte n'absorbait."""
    with pytest.raises(ValueError, match="arrondis au centime"):
        ecritures.inserer(base, journal="BQ", date="2026-01-10", annee=2026,
                          libelle="Fait fictif", piece_ref="P-1",
                          lignes=[("108000", 100.004, 0.0),
                                  ("108000", 100.004, 0.0),
                                  ("708810", 0.0, 200.008)])
    base.commit()
    assert compter(base) == {"ecriture": 0, "ligne": 0}


def test_g01_les_montants_arrondis_restent_acceptes(base):
    """Contre-épreuve : l'arrondi ne doit rien casser d'ordinaire."""
    ecritures.inserer(base, journal="BQ", date="2026-01-10", annee=2026,
                      libelle="Fait fictif", piece_ref="P-1",
                      lignes=[("108000", 800.25, 0.0), ("708810", 0.0, 800.25)])
    totaux = base.execute("SELECT SUM(debit), SUM(credit) FROM ligne").fetchone()
    assert totaux == (800.25, 800.25)


# ═══ G-02 — aucune ligne ne disparaît d'une reprise ═════════════════════

def _fec_a_lignes_courtes(tmp_path):
    """Second loyer amputé de ses DEUX DERNIÈRES COLONNES VIDES : seize
    champs, tous les montants présents. Il disparaissait entièrement."""
    courtes = [[r[k] for k in COLS[:-2]] for r in ecriture(num=2)]
    return ecrire_fec(tmp_path, "courtes.txt", ecriture(num=1) + courtes)


def test_g02_lecture_nommee_refuse_au_lieu_d_ecarter(tmp_path):
    f = _fec_a_lignes_courtes(tmp_path)
    assert len(fec_io.lire_brut(f)[1]) == 4          # le lecteur brut voit tout
    with pytest.raises(ValueError) as exc:
        fec_io.lignes_nommees(f)
    assert "L.4 (16 champs)" in str(exc.value)
    assert "L.5 (16 champs)" in str(exc.value)


def test_g02_le_rejeu_ne_peut_plus_annoncer_un_succes_partiel(base, tmp_path):
    """800 € de recettes disparaissaient de façon ÉQUILIBRÉE : aucun
    contrôle d'équilibre en aval ne pouvait les rattraper."""
    with pytest.raises(ValueError, match="colonnes annoncées"):
        rejeu_fec.rejouer(base, _fec_a_lignes_courtes(tmp_path), 2026)
    base.commit()
    assert compter(base) == {"ecriture": 0, "ligne": 0}


def test_g02_la_balance_de_reprise_refuse_aussi(tmp_path):
    """Même défaut sur l'autre consommateur : un bilan d'ouverture faux ne
    se voit plus ensuite."""
    courtes = [[r[k] for k in COLS[:11]] for r in ecriture(num=2)]
    f = ecrire_fec(tmp_path, "balance-courte.txt", ecriture(num=1) + courtes)
    with pytest.raises(ValueError, match="avant la colonne Credit"):
        reprise.lire_balance_fec(f)


def test_g02_entete_incomplet_refuse(base, tmp_path):
    """Un fichier à dix-sept colonnes était « repris » avec un retour
    réussi de zéro écriture."""
    f = ecrire_fec(tmp_path, "17-colonnes.txt", ecriture(), entete=COLS[:-1])
    with pytest.raises(ValueError, match="Idevise"):
        rejeu_fec.rejouer(base, f, 2026)


def test_g02_vue_web_annonce_le_refus(tmp_path, monkeypatch):
    """La vue d'import affichait « 1 écritures rejouées » — un succès — sur
    un fichier dont la moitié des lignes venait d'être écartée."""
    import io
    from urllib.parse import urlparse, parse_qs
    import app as web

    chemin_db = str(tmp_path / "web.db")
    init_db.init_blanc(chemin_db, 2026).close()
    octets = open(_fec_a_lignes_courtes(tmp_path), "rb").read()
    imports = tmp_path / "imports"
    imports.mkdir()
    monkeypatch.setattr(web, "_db_path", lambda *a, **k: chemin_db)
    monkeypatch.setattr(web, "_dossier_imports", lambda *a, **k: str(imports))
    with web.app.test_request_context(
            "/", method="POST",
            data={"annee": "2025", "fec": (io.BytesIO(octets), "fictif.txt")}):
        reponse = web.exercice_reprendre_fec()
    query = parse_qs(urlparse(reponse.location).query)
    assert "ok" not in query
    assert "colonnes annoncées" in query["err"][0]


# ═══ G-03 — le validateur ne compense plus entre journaux ═══════════════

def test_g03_desequilibres_opposes_dans_deux_journaux(tmp_path):
    """AC/1 ne portait qu'un débit de 800 €, BQ/1 qu'un crédit de 800 € :
    agrégées sur le seul numéro, les deux écritures se compensaient et le
    fichier était déclaré conforme, sans erreur."""
    f = ecrire_fec(tmp_path, "journaux.txt",
                   [ligne(JournalCode="AC"),
                    ligne(JournalCode="BQ", CompteNum="708810",
                          Debit="", Credit="800")])
    erreurs = valider_fec.valider(f)
    assert any("AC/1 déséquilibrée" in e for e in erreurs)
    assert any("BQ/1 déséquilibrée" in e for e in erreurs)
    assert sum("une seule ligne" in e for e in erreurs) == 2


def test_g03_sequences_par_journal_ne_sont_plus_des_trous(tmp_path):
    """AC 10-11 et BQ 20-21 : deux séquences par journal, parfaitement
    continues, à qui le validateur réclamait les numéros 12 à 19."""
    f = ecrire_fec(tmp_path, "sequences.txt",
                   ecriture(10, "AC") + ecriture(11, "AC")
                   + ecriture(20, "BQ") + ecriture(21, "BQ"))
    rapport = valider_fec.valider(f, comme_dict=True)
    assert rapport["conforme"]
    assert rapport["observations"] == []


def test_g03_un_trou_par_journal_n_est_plus_masque(tmp_path):
    """AC 1 puis 3, BQ 1 puis 2 : le numéro 2 de BQ comblait, aux yeux du
    contrôle, le trou d'AC. Le numéro 1 présent dans DEUX journaux établit
    que la numérotation est par journal — c'est par journal qu'on juge."""
    f = ecrire_fec(tmp_path, "trou-journal.txt",
                   ecriture(1, "AC") + ecriture(3, "AC")
                   + ecriture(1, "BQ") + ecriture(2, "BQ"))
    rapport = valider_fec.valider(f, comme_dict=True)
    assert rapport["erreurs"] == []          # une rupture peut s'expliquer…
    assert any("AC : [2]" in o for o in rapport["observations"])  # …mais se dit


def test_g03_un_trou_reste_une_observation(tmp_path):
    """La notice DGFiP (question 14) admet les ruptures issues de la
    validation d'un brouillard : un trou dans un fichier EXTERNE n'est pas
    une non-conformité certaine."""
    f = ecrire_fec(tmp_path, "trou.txt", ecriture(1) + ecriture(3))
    rapport = valider_fec.valider(f, comme_dict=True)
    assert rapport["erreurs"] == []
    assert any("non continue" in o for o in rapport["observations"])


def test_g03_la_numerotation_du_logiciel_reste_stricte(base):
    """Ce que le logiciel PRODUIT, en revanche, lui appartient : un trou y
    est bloquant, là où sa provenance est connue."""
    ecritures.inserer(base, journal="BQ", date="2026-01-10", annee=2026,
                      libelle="Fait fictif", piece_ref="P-1", num=1,
                      lignes=[("108000", 800, 0.0), ("708810", 0.0, 800)])
    ecritures.inserer(base, journal="BQ", date="2026-01-11", annee=2026,
                      libelle="Fait fictif", piece_ref="P-2", num=3,
                      lignes=[("108000", 800, 0.0), ("708810", 0.0, 800)])
    anomalies = controles.c_numerotation_fec(base, 2026)
    assert [a.niveau for a in anomalies] == [controles.BLOQUANT]
    assert "n° 2" in anomalies[0].message


# ═══ G-04 — EcritureNum est un champ alphanumérique ════════════════════

def test_g04_numeros_alphanumeriques_lus_et_rejoues(base, tmp_path):
    """« BQ0001 » est un numéro légal (A47 A-1, VII-1). Le validateur le
    refusait en bloc et le rejeu s'arrêtait sur un `invalid literal for
    int()` : tout un FEC de cabinet devenait non migrable."""
    f = ecrire_fec(tmp_path, "alpha.txt",
                   ecriture("BQ0001") + ecriture("BQ0002"))
    assert valider_fec.valider(f) == []
    res = rejeu_fec.rejouer(base, f, 2026)
    assert res["ecritures"] == 2
    assert res["renumerotees"] is True       # la base numérote en entiers…
    assert compter(base) == {"ecriture": 2, "ligne": 4}   # …et rien n'est perdu


# ═══ G-05 — les variantes admises du format sont lues ══════════════════

def test_g05_barre_verticale(base, tmp_path):
    """Séparateur admis par l'arrêté. Le fichier était tokenisé en UNE
    colonne : en-tête « reçu 1 », et zéro écriture reprise en guise de
    succès."""
    f = ecrire_fec(tmp_path, "pipe.txt", ecriture(), sep="|")
    assert valider_fec.valider(f) == []
    assert rejeu_fec.rejouer(base, f, 2026)["ecritures"] == 1


def test_g05_signe_suffixe():
    """« 800,00- » : forme admise, produite par plusieurs logiciels."""
    assert fec_io.nombre("800,00-") == -800.0
    assert fec_io.nombre("-800,00") == -800.0
    with pytest.raises(ValueError, match="deux signes"):
        fec_io.nombre("-800,00-")


def test_g05_colonne_supplementaire(base, tmp_path):
    """Les dix-huit informations sont les PREMIÈRES, pas un maximum : la
    notice DGFiP admet des colonnes à la suite. L'égalité stricte rejetait
    le fichier dès l'en-tête, sans lire une ligne."""
    f = ecrire_fec(tmp_path, "col19.txt", ecriture(), entete=COLS + ["Info"])
    rapport = valider_fec.valider(f, comme_dict=True)
    assert rapport["conforme"]
    assert any("au-delà des dix-huit" in o for o in rapport["observations"])
    assert rejeu_fec.rejouer(base, f, 2026)["ecritures"] == 1


def test_g05_colonnes_permutees_restent_refusees(tmp_path):
    """L'ordre des dix-huit premières, lui, est imposé."""
    f = ecrire_fec(tmp_path, "permutees.txt", ecriture(),
                   entete=list(reversed(COLS)))
    assert any("En-tête" in e for e in valider_fec.valider(f))


# ═══ G-06 — un montant est un nombre fini écrit en chiffres ════════════

@pytest.mark.parametrize("valeur", ["NaN", "nan", "inf", "-inf", "1e309",
                                    "1e3", "800€", ""])
def test_g06_le_parseur_refuse_ce_qui_n_est_pas_un_montant(valeur):
    if valeur == "":
        assert fec_io.analyser_montant(valeur) == (0.0, None)   # vide = 0
        return
    valeur_lue, erreur = fec_io.analyser_montant(valeur)
    assert valeur_lue is None and erreur


@pytest.mark.parametrize("gauche,droite", [("NaN", "999"), ("inf", "inf"),
                                           ("1e309", "1e309"), ("1e3", "1e3")])
def test_g06_aucun_verdict_positif_sans_equilibre_calculable(tmp_path, gauche,
                                                             droite):
    """nan ≠ nan et inf − inf = nan : ces valeurs traversaient toutes les
    comparaisons d'équilibre. Le validateur rendait « conforme, 0 erreur »
    sur un fichier dont il n'avait pas pu calculer la somme — le pire
    verdict possible, puisqu'il rassure."""
    rs = ecriture()
    rs[0]["Debit"] = gauche
    rs[1]["Credit"] = droite
    erreurs = valider_fec.valider(ecrire_fec(tmp_path, "non-fini.txt", rs))
    assert any("montant illisible" in e or "représentables" in e
               for e in erreurs)


def test_g06_montant_en_devise_non_numerique(tmp_path):
    """Seule la présence CONJOINTE de Montantdevise et Idevise était
    vérifiée : n'importe quel texte y passait pour une contrevaleur."""
    rs = ecriture()
    rs[0].update(Montantdevise="BOGUS", Idevise="USD")
    assert any("Montantdevise" in e
               for e in valider_fec.valider(ecrire_fec(tmp_path, "dev.txt", rs)))


# ═══ G-07 — dates réelles et préfixe de compte ═════════════════════════

def test_g07_le_30_fevrier_n_existe_pas(tmp_path):
    """Le jour était borné à 31 sans regarder le calendrier."""
    f = ecrire_fec(tmp_path, "30fev.txt", ecriture(date="20260230"))
    assert any("EcritureDate '20260230' invalide" in e
               for e in valider_fec.valider(f))
    assert valider_fec.valider_nom_fichier("000000000FEC20260230.txt")
    assert valider_fec.valider_nom_fichier("000000000FEC20261231.txt") is None


def test_g07_prefixe_de_compte_numerique(tmp_path):
    """Le compte n'était contrôlé qu'en LONGUEUR : « 4AB » passait pour un
    compte de tiers valide. Au-delà du troisième caractère, les auxiliaires
    alphanumériques restent admis."""
    rs = ecriture()
    rs[0]["CompteNum"] = "4AB"
    assert any("trois premiers caractères" in e
               for e in valider_fec.valider(ecrire_fec(tmp_path, "4ab.txt", rs)))
    rs[0]["CompteNum"] = "411DUPONT"
    assert valider_fec.valider(ecrire_fec(tmp_path, "aux.txt", rs)) == []


# ═══ G-08 — le rejeu conserve ce que le FEC source porte ═══════════════

def test_g08_les_champs_du_fec_source_survivent_au_reexport(base, tmp_path):
    """Identification auxiliaire, lettrage, devise et dates de PREUVE
    étaient effacés ou réécrits : un fichier censé être repris à
    l'identique ne l'était plus."""
    rs = ecriture()
    rs[0].update(CompteNum="4110000", CompteLib="Locataires")
    rs[1].update(CompteNum="7088100", CompteLib="Loyers")
    for r in rs:
        r.update(CompAuxNum="AUX-FICTIF", CompAuxLib="Tiers fictif",
                 PieceDate="20260102", ValidDate="20260120",
                 EcritureLet="LET-1", DateLet="20260125")
    rs[0].update(Montantdevise="900", Idevise="USD")
    rs[1].update(Montantdevise="900", Idevise="USD")
    source = ecrire_fec(tmp_path, "metadonnees.txt", rs)
    rejeu_fec.rejouer(base, source, 2026)
    sortie = str(tmp_path / "reexport.txt")
    export_fec.exporter(base, 2026, sortie)
    rendu = fec_io.lignes_nommees(sortie)[0]
    for champ in ("CompAuxNum", "CompAuxLib", "PieceDate", "EcritureLet",
                  "DateLet", "ValidDate", "Montantdevise", "Idevise"):
        assert rendu[champ] == rs[0][champ], champ


def test_g08_un_libelle_de_journal_ecrase_est_annonce(base, tmp_path):
    """Le plan livré reste la référence pour un journal déjà connu — mais
    le ré-export ne rend alors pas le libellé du FEC source, et cela ne
    peut pas rester tacite."""
    res = rejeu_fec.rejouer(base, ecrire_fec(tmp_path, "j.txt", ecriture()),
                            2026)
    assert any("Journal fictif" in j for j in res["journaux_renommes"])


def test_g08_deux_dates_dans_une_meme_ecriture(base, tmp_path):
    """Seule la date de la PREMIÈRE ligne du groupe était lue, et les
    autres réécrites avec : deux lignes datées de deux ANNÉES différentes
    entraient dans l'exercice de la première, sans un mot. La garde du
    guichet ne pouvait rien voir, la date lui arrivant uniformisée."""
    rs = ecriture()
    rs[1]["EcritureDate"] = "20250110"
    f = ecrire_fec(tmp_path, "deux-annees.txt", rs)
    with pytest.raises(ValueError, match="dates différentes"):
        rejeu_fec.rejouer(base, f, 2026)
    base.commit()
    assert compter(base) == {"ecriture": 0, "ligne": 0}


# ═══ G-09 — le fichier produit se lit dans l'ordre chronologique ═══════

def test_g09_export_chronologique(base, tmp_path):
    """La numérotation suit l'ordre de SAISIE : le loyer de mars, saisi en
    premier, sortait en tête du fichier, dont les dates reculaient ensuite
    d'un bloc à l'autre."""
    loyer(base, 800, "2026-03-10")
    loyer(base, 800, "2026-01-10")
    fiscal.cloturer(base, 2026, generer_dotation=False)
    f = str(tmp_path / "chrono.txt")
    export_fec.exporter(base, 2026, f)
    lignes = fec_io.lignes_nommees(f)
    dates = [r["ValidDate"] for r in lignes]
    assert dates == sorted(dates)
    assert valider_fec.valider(f, comme_dict=True)["observations"] == []


def test_g09_un_recul_de_chronologie_est_observe(tmp_path):
    """Sur un fichier EXTERNE, le recul se signale sans rejeter."""
    f = ecrire_fec(tmp_path, "recul.txt",
                   ecriture(1, date="20260310") + ecriture(2, date="20260110"))
    rapport = valider_fec.valider(f, comme_dict=True)
    assert rapport["erreurs"] == []
    assert any("recule" in o for o in rapport["observations"])


# ═══ G-10 — un export ne tait pas ce qu'il ne peut pas restituer ═══════

def test_g10_ligne_dont_le_compte_a_disparu(base, tmp_path):
    """Les jointures INTERNES faisaient disparaître la ligne du fichier :
    l'export se terminait normalement, le validateur trouvait le fichier
    conforme, et 800 € présents en base n'étaient nulle part."""
    loyer(base)
    fiscal.cloturer(base, 2026, generer_dotation=False)
    base.execute("PRAGMA foreign_keys=OFF")
    base.execute("DELETE FROM compte WHERE numero IN ('108000','708810')")
    base.commit()
    with pytest.raises(ValueError, match="comptes absents"):
        export_fec.exporter(base, 2026, str(tmp_path / "ampute.txt"))
    assert not os.path.exists(str(tmp_path / "ampute.txt"))


def test_g10_entete_sans_ligne(base, tmp_path):
    """Une écriture sans ligne occupe un numéro et ne produit rien : c'est
    un trou dans la numérotation du fichier remis."""
    loyer(base)
    fiscal.cloturer(base, 2026, generer_dotation=False)
    base.execute("DELETE FROM ligne")
    base.commit()
    with pytest.raises(ValueError, match="sans aucune ligne"):
        export_fec.exporter(base, 2026, str(tmp_path / "vide.txt"))


def test_g10_un_fichier_sans_ecriture_ne_passe_plus_pour_verifie(tmp_path):
    """« Conforme, 0 erreur » sur un en-tête seul : verdict exact sur la
    forme, et parfaitement trompeur — c'est ce que produit un export qui a
    perdu toutes ses lignes."""
    rapport = valider_fec.valider(ecrire_fec(tmp_path, "entete.txt", []),
                                  comme_dict=True)
    assert any("aucune écriture" in o for o in rapport["observations"])


def test_g10_un_export_ordinaire_reste_possible(base, tmp_path):
    """Contre-épreuve : la vérification d'exhaustivité ne gêne pas."""
    loyer(base)
    fiscal.cloturer(base, 2026, generer_dotation=False)
    f = str(tmp_path / "normal.txt")
    export_fec.exporter(base, 2026, f)
    assert valider_fec.valider(f) == []


# ═══ G-11 — un prix de cession est un montant chiffré ══════════════════

def test_g11_prix_nan_refuse_et_rien_ne_sort_de_l_actif(base):
    """`nan < 0` est FAUX, comme toute comparaison avec nan : le prix
    passait le contrôle, puis `nan > 0` était faux à son tour et aucune
    écriture de produit n'était générée — mais les 12 000 € d'actif
    sortaient quand même, date de cession posée."""
    base.execute("INSERT INTO composant(bien_id,libelle,valeur_brute,"
                 "duree_annees,date_mise_service,compte_immo,compte_amort) "
                 "VALUES (1,'Mobilier fictif',12000,10,'2026-01-01',"
                 "'218400','281840')")
    base.commit()
    with pytest.raises(ValueError, match="montant chiffré"):
        cession.ceder_bien(base, 1, "2026-06-30", float("nan"))
    base.commit()
    assert compter(base) == {"ecriture": 0, "ligne": 0}
    assert base.execute("SELECT date_cession FROM bien").fetchone()[0] is None


def test_g11_le_formulaire_web_ne_livre_pas_nan_au_metier():
    """`float()` accepte « nan », « inf » et « 1e400 » : trois mots que
    n'importe qui peut taper dans un champ de montant."""
    import app as web
    with web.app.test_request_context("/", method="POST",
                                      data={"m": "nan", "n": "inf",
                                            "o": "1e400", "p": "795,50"}):
        assert web._form_float("m") is None
        assert web._form_float("n") is None
        assert web._form_float("o") is None
        assert web._form_float("p") == 795.50


def test_g11_cession_ordinaire_inchangee(base):
    """Contre-épreuve : prix 15 000 €, la cession normale passe."""
    base.execute("INSERT INTO composant(bien_id,libelle,valeur_brute,"
                 "duree_annees,date_mise_service,compte_immo,compte_amort) "
                 "VALUES (1,'Mobilier fictif',12000,10,'2026-01-01',"
                 "'218400','281840')")
    base.commit()
    r = cession.ceder_bien(base, 1, "2026-06-30", 15000)
    assert r["prix_cession"] == 15000
    assert r["vnc_sortie"] == 11404.93


# ═══ G-12 — la quote-part fournie n'est pas déplacée par un arrondi ════

def test_g12_la_quote_part_de_terrain_fournie_est_respectee():
    """Les proportions des AUTRES postes étaient arrondies à quatre
    décimales avant d'être appliquées au prix — sur 100 000 €, cela suffit
    à créer un écart de 13 € — puis cet écart était absorbé par la ligne au
    plus gros montant : le terrain, justement. Treize euros ajoutés au
    terrain NON AMORTISSABLE, contre la quote-part lue dans l'acte."""
    lignes = amortissement.ventilation_proposee(100000.01, 0.73117)
    terrain = next(x for x in lignes if x["cle"] == "terrain")
    assert terrain["montant"] == 73117.01        # 100000,01 × 0,73117
    assert round(sum(x["montant"] for x in lignes), 2) == 100000.01


def test_g12_le_centime_residuel_reste_absorbe():
    """Sans quote-part fournie, rien ne change : l'arrondi ne doit toujours
    ni perdre ni inventer d'euros."""
    lignes = amortissement.ventilation_proposee(100000.01)
    assert round(sum(x["montant"] for x in lignes), 2) == 100000.01


# ═══ G-13 — l'euro d'un fichier ISO-8859-15 reste un euro ══════════════

@pytest.mark.parametrize("encodage", ["iso-8859-15", "cp1252", "utf-8",
                                      "utf-8-sig"])
def test_g13_le_symbole_euro_traverse_la_lecture(tmp_path, encodage):
    """L'octet 0xA4 vaut « € » en ISO-8859-15 et « ¤ » en CP1252 : l'ordre
    d'essai décidait seul, et tout FEC de cabinet en ISO-8859-15 voyait ses
    euros remplacés par le symbole monétaire générique, sans signal."""
    rs = [dict(r, EcritureLib="Loyer fictif 800 €") for r in ecriture()]
    f = ecrire_fec(tmp_path, f"{encodage}.txt", rs, encodage=encodage)
    assert all(r["EcritureLib"] == "Loyer fictif 800 €"
               for r in fec_io.lignes_nommees(f))


# ═══ G-14 — le code de retour EST le verdict ══════════════════════════

def _lancer_validateur(*chemins):
    return subprocess.run([sys.executable, conftest.source("valider_fec.py"),
                           *chemins], capture_output=True, text=True,
                          timeout=30)


def test_g14_code_retour_non_nul_sur_erreur_bloquante(tmp_path):
    """Le code valait 0 quoi qu'il arrive : une automatisation pouvait
    archiver puis remettre un FEC déséquilibré au motif que le contrôle
    « s'était bien passé ». Le message, lui, était explicite : c'est le
    contrat de commande qui manquait."""
    rs = ecriture()
    rs[1]["Credit"] = "799"
    r = _lancer_validateur(ecrire_fec(tmp_path, "invalide.txt", rs))
    assert r.returncode == 1
    assert "déséquilibrée" in r.stdout


def test_g14_code_retour_nul_sur_fichier_conforme(tmp_path):
    r = _lancer_validateur(ecrire_fec(tmp_path, "conforme.txt", ecriture()))
    assert r.returncode == 0
    assert "conforme" in r.stdout


def test_g14_fichier_illisible_distingue_de_l_erreur_comptable(tmp_path):
    r = _lancer_validateur(str(tmp_path / "inexistant.txt"))
    assert r.returncode == 2
    assert "illisible" in r.stdout


# ═══ G-15 — les exceptions de typage des comptes de tiers ═════════════

@pytest.mark.parametrize("numero,attendu", [
    ("4090000", "actif"),    # fournisseurs DÉBITEURS
    ("4190000", "passif"),   # clients CRÉDITEURS
    ("4250000", "actif"),    # personnel : avances et acomptes
    ("4010000", "passif"),   # la tranche, elle, ne change pas
    ("4110000", "actif"),
    ("2818400", "amortissement"),
])
def test_g15_exceptions_de_tranche(numero, attendu):
    """Les tranches 40, 41 et 42 ont leurs exceptions, que le plan de
    comptes nomme une par une : ce sont les comptes qui portent le solde
    INVERSE de leur tranche, créés exprès pour ne pas compenser une créance
    avec une dette. Un avoir fournisseur était rangé avec les dettes, un
    trop-perçu de locataire avec les créances."""
    assert fec_io.type_du_compte(numero) == attendu


def test_g15_le_typage_survit_a_une_reprise(base, tmp_path):
    rs = []
    for i, numero in enumerate(("4090000", "4190000", "4250000"), start=1):
        rs += [ligne(EcritureNum=str(i), CompteNum=numero,
                     CompteLib="Tiers fictif"),
               ligne(EcritureNum=str(i), CompteNum="1080000",
                     CompteLib="Exploitant", Debit="", Credit="800")]
    rejeu_fec.rejouer(base, ecrire_fec(tmp_path, "tiers.txt", rs), 2026)
    types = dict(base.execute("SELECT numero, type FROM compte "
                              "WHERE numero LIKE '4%0000'"))
    assert types["4090000"] == "actif"
    assert types["4190000"] == "passif"
    assert types["4250000"] == "actif"


# ═══ Ce qui tenait doit continuer de tenir ════════════════════════════

def test_le_fec_natif_reste_conforme_de_bout_en_bout(base, tmp_path):
    """Garde générale : une comptabilité ordinaire, close, exportée, doit
    traverser toutes ces nouvelles exigences sans une observation."""
    loyer(base, 800.25)
    loyer(base, 100, "2026-02-10")
    fiscal.cloturer(base, 2026, generer_dotation=False)
    f = str(tmp_path / "natif.txt")
    export_fec.exporter(base, 2026, f)
    octets = open(f, "rb").read()
    assert not octets.startswith(b"\xef\xbb\xbf")        # UTF-8 sans BOM
    assert octets.replace(b"\r\n", b"").count(b"\n") == 0   # aucun LF isolé
    assert valider_fec.valider(f, comme_dict=True) == {
        "conforme": True, "nb_erreurs": 0, "erreurs": [], "observations": []}
    assert controles.c_numerotation_fec(base, 2026) == []


def test_le_rejeu_d_un_fec_natif_le_reproduit(base, tmp_path):
    """Boucle complète : exporter, rejouer ailleurs, ré-exporter — les
    deux fichiers doivent être identiques OCTET POUR OCTET."""
    loyer(base, 800.25)
    loyer(base, 100, "2026-02-10")
    fiscal.cloturer(base, 2026, generer_dotation=False)
    source = str(tmp_path / "source.txt")
    export_fec.exporter(base, 2026, source)

    cible = init_db.init_blanc(str(tmp_path / "cible.db"), 2026)
    try:
        rejeu_fec.rejouer(cible, source, 2026)
        refait = str(tmp_path / "refait.txt")
        export_fec.exporter(cible, 2026, refait)
        assert open(refait, "rb").read() == open(source, "rb").read()
    finally:
        cible.close()


def test_aucune_regression_sur_les_montants_du_lecteur():
    assert fec_io.nombre("1234,56") == 1234.56
    assert fec_io.nombre("") == 0.0
    assert fec_io.nombre("-12,50") == -12.5
    with pytest.raises(ValueError):
        fec_io.nombre("abc")


def test_le_separateur_est_detecte_sans_ambiguite():
    assert fec_io.separateur("a\tb\tc") == "\t"
    assert fec_io.separateur("a|b|c") == "|"
    # Une barre verticale DANS un libellé ne change pas un fichier tabulé.
    assert fec_io.separateur("a\tb|c\td") == "\t"


def test_dossier_temporaire_nettoye():
    """Garde-fou de la suite elle-même : ces tests n'écrivent que dans le
    tmp_path de pytest, jamais à côté des fichiers du projet."""
    assert not os.path.exists(os.path.join(tempfile.gettempdir(),
                                           "fictif.db"))
