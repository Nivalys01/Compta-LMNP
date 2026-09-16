# Compta LMNP — Copyright © 2026 Sylvain FAURE et les contributeurs.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Passe J : non-régression sur bases blanches et flux fictifs uniquement."""
import subprocess
from unittest.mock import patch

import pytest

import controles
import ecritures
import export_fec
import fiscal
import init_db
import liasse
import liasse_pdf
import operations
import rejeu_fec
import reprise


@pytest.fixture
def base(tmp_path):
    c = init_db.init_blanc(str(tmp_path / 'fictif.db'), 2025)
    c.execute("INSERT INTO exploitant VALUES(1,'Fictif','000000000','Fictif')")
    c.execute("INSERT INTO bien(id,exploitant_id,libelle,prix_total) VALUES(1,1,'Fictif',12000)")
    c.commit()
    yield c
    c.close()


def stock(c, origine, initial, solde=None):
    c.execute("INSERT INTO deficit_lmnp(annee_origine,montant_initial,solde,annee_expiration) "
              "VALUES(?,?,?,?)", (origine, initial, initial if solde is None else solde,
                                    origine + 10))
    c.commit()


def flux(c, montant, annee=2025):
    lignes = [('108000', montant, 0), ('708810', 0, montant)] if montant > 0 else [
        ('614100', -montant, 0), ('108000', 0, -montant)]
    ecritures.inserer(c, journal='OD', date=f'{annee}-12-31', annee=annee,
                     piece_ref='FICTIF', libelle='Fictif', lignes=lignes)


def cloture(c, annee=2025):
    return fiscal.cloturer(c, annee, generer_dotation=False)


def cases(c, annee=2025):
    return {d['case']: d['montant'] for d in liasse.aide_2042c(c, annee)[
        'cases_deficits_anterieurs']}


def pdf(c, tmp_path, annee=2025):
    p = tmp_path / f'liasse-{annee}.pdf'
    liasse_pdf.generer_pdf(liasse.generer(c, annee), str(p))
    return subprocess.check_output(['pdftotext', '-layout', str(p), '-'], text=True)


@pytest.mark.parametrize('benefice', [500, 1000, 1500])
def test_j01_epuise(base, benefice, tmp_path):
    stock(base, 2024, 1000)
    flux(base, benefice)
    cloture(base)
    assert cases(base) == {'5GJ': 1000}
    assert liasse.suivi_reports(base, 2025)['total_deficits'] == max(0, 1000-benefice)
    assert '5GJ' in pdf(base, tmp_path)


def test_j01_millesime_partiellement_consomme_et_doublons(base):
    stock(base, 2020, 1000, 500)
    stock(base, 2024, 2000, 750)
    stock(base, 2024, 250)
    flux(base, 500)
    cloture(base)
    assert cases(base) == {'5GF': 500, '5GJ': 1000}


def test_j02_historique_et_futur(base, tmp_path):
    flux(base, -3000)
    cloture(base)
    reprise.ouvrir_exercice(base, 2026)
    flux(base, 1000, 2026)
    cloture(base, 2026)
    avant = liasse.suivi_reports(base, 2026)
    texte = pdf(base, tmp_path, 2026)
    reprise.ouvrir_exercice(base, 2027)
    flux(base, 2000, 2027)
    cloture(base, 2027)
    reprise.ouvrir_exercice(base, 2028)
    flux(base, -700, 2028)
    cloture(base, 2028)
    assert liasse.suivi_reports(base, 2026) == avant
    assert cases(base, 2026) == {'5GJ': 3000}
    assert pdf(base, tmp_path, 2026) == texte


def test_j03_peremption_partielle(base, tmp_path):
    stock(base, 2014, 2000, 1200)
    stock(base, 2024, 800)
    assert liasse.suivi_reports(base, 2025)['total_deficits_perimes'] == 1200
    cloture(base)
    rep = liasse.suivi_reports(base, 2025)
    assert rep['total_deficits_perimes'] == 1200
    assert rep['total_deficits'] == 800
    assert cases(base) == {'5GJ': 800}
    texte = pdf(base, tmp_path)
    assert '2014' in texte and '1 200,00' in texte and 'perdus' in texte


@pytest.mark.parametrize('annee, attendu', [(2025, 500), (2026, 0)])
def test_pivot_dix_ans(base, annee, attendu):
    stock(base, 2015, 800)
    if annee == 2026:
        cloture(base)
        # Exercice précédent sans écriture : aucun à-nouveau à construire.
        base.execute("INSERT INTO exercice(annee,date_debut,date_fin,statut) "
                     "VALUES(?,?,?,'ouvert')", (annee, f"{annee}-01-01", f"{annee}-12-31"))
        base.commit()
    flux(base, 300, annee)
    cloture(base, annee)
    assert liasse.suivi_reports(base, annee)['total_deficits'] == attendu


def test_j04_fec(base, tmp_path):
    operations.saisir(base, type='loyer', montant=30000, date_operation='2025-02-01')
    flux(base, -35000)
    assert controles.c_seuil_lmp(base, 2025)[0].code == 'SEUIL_LMP'
    p = tmp_path / 'fictif.txt'
    export_fec.exporter(base, 2025, str(p))
    c = init_db.init_blanc(str(tmp_path / 'rejeu.db'), 2025)
    try:
        rejeu_fec.rejouer(c, str(p), 2025)
        assert c.execute('SELECT COUNT(*) FROM operation').fetchone()[0] == 0
        assert controles.c_seuil_lmp(c, 2025) == controles.c_seuil_lmp(base, 2025)
    finally:
        c.close()


@pytest.mark.parametrize('montant,attendu', [(100.49,100), (100.50,101), (100.51,101),
                                           (101.50,102), (.50,1), (.49,0)])
@pytest.mark.parametrize('sens', ['benefice', 'deficit', 'anterieur'])
def test_j05_arrondis(base, montant, attendu, sens):
    if sens == 'anterieur':
        stock(base, 2024, montant)
    else:
        flux(base, montant if sens == 'benefice' else -montant)
    cloture(base)
    aide = liasse.aide_2042c(base, 2025)
    if sens == 'anterieur':
        assert cases(base) == ({'5GJ': attendu} if attendu else {})
    else:
        assert aide['case_5NA' if sens == 'benefice' else 'case_5NY'] == attendu


def test_migration_et_rollback(base):
    base.execute('DROP TABLE suivi_deficits')  # schéma antérieur au correctif
    stock(base, 2024, 1000)
    flux(base, 600)
    original = fiscal.traiter_deficit

    def interrompre(*args, **kwargs):
        original(*args, **kwargs)
        raise RuntimeError('interruption après imputation')

    with patch.object(fiscal, 'traiter_deficit', interrompre), pytest.raises(RuntimeError):
        cloture(base)
    base.rollback()
    assert base.execute('SELECT solde FROM deficit_lmnp').fetchone()[0] == 1000
    cloture(base)
    assert cases(base) == {'5GJ': 1000}


def test_ancienne_cloture_sans_trace_refusee(base):
    stock(base, 2024, 1000)
    flux(base, 1000)
    cloture(base)
    base.execute('DROP TABLE suivi_deficits')
    with pytest.raises(ValueError, match='Historique des déficits indisponible'):
        liasse.aide_2042c(base, 2025)


def test_commit_false(base):
    stock(base, 2024, 1000)
    base.execute('BEGIN')
    fiscal.traiter_deficit(base, 2025, 600, commit=False)
    base.rollback()
    assert base.execute('SELECT COUNT(*) FROM suivi_deficits').fetchone()[0] == 0
    assert base.execute('SELECT solde FROM deficit_lmnp').fetchone()[0] == 1000


def test_fifo_epuisement(base):
    for origine, montant in [(2017, 1000), (2019, 2000), (2024, 3000)]:
        stock(base, origine, montant)
    flux(base, 7000)
    cloture(base)
    assert cases(base) == {'5GC': 1000, '5GE': 2000, '5GJ': 3000}
    assert liasse.suivi_reports(base, 2025)['total_deficits'] == 0


def test_snapshot_vide_reste_vide(base):
    flux(base, 1000)
    cloture(base)
    reprise.ouvrir_exercice(base, 2026)
    flux(base, -700, 2026)
    cloture(base, 2026)
    assert liasse.suivi_reports(base, 2025)['deficits'] == []


def test_double_appel_refuse_sans_mutation(base):
    stock(base, 2024, 1000)
    fiscal.traiter_deficit(base, 2025, 300)
    with pytest.raises(ValueError, match='déjà été traités'):
        fiscal.traiter_deficit(base, 2025, 300)
    assert base.execute('SELECT solde FROM deficit_lmnp').fetchone()[0] == 700
    assert cases(base) == {'5GJ': 1000}


@pytest.mark.parametrize('recette,alerte', [(23000, False), (23000.01, True)])
def test_seuil_sans_double_comptage(base, recette, alerte):
    operations.saisir(base, type='loyer', montant=recette, date_operation='2025-02-01')
    assert bool(controles.c_seuil_lmp(base, 2025)) is alerte
