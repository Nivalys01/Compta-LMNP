# Compta LMNP — Copyright © 2026 Sylvain FAURE. Tous droits réservés.
# Logiciel propriétaire — voir LICENSE.txt. Reproduction et revente interdites
# sans autorisation écrite de l'auteur.

"""
Export PDF de la liasse fiscale — J7.

Prend le dictionnaire produit par `liasse.generer()` et le met en page dans
un PDF A4 : page de garde, 2031/2031 bis, 2033-A, 2033-B, 2033-C, suivi des
reports (39 C + déficits LMNP), aide 2042C-PRO et contrôles de cohérence.

Ce document est un ÉTAT DE TRAVAIL fidèle aux montants calculés — pas un
fac-similé des formulaires CERFA : les numéros de cases officiels y figurent
pour permettre le report champ à champ dans la télédéclaration (ou par
l'expert-comptable). Filigrane « PROVISOIRE » si l'exercice n'est pas clos.

Dépendance : reportlab (installée par les lanceurs au premier démarrage).
"""
from __future__ import annotations

import os
from datetime import datetime
from xml.sax.saxutils import escape as _xml

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle)

BLEU = colors.HexColor("#1e3a5f")
GRIS = colors.HexColor("#8a93a3")
FOND = colors.HexColor("#f7f8fa")
VERT = colors.HexColor("#1a7f37")
ROUGE = colors.HexColor("#b42318")


def _eur(x) -> str:
    """1234.5 → '1 234,50 €' (insécable fine espace non requise en PDF).

    Un résidu d'arrondi négatif — -0,004 — s'affichait « -0,00 € » : un
    montant nul affecté d'un signe moins, dans un document où le signe
    porte le sens. Le zéro est ramené au zéro positif AVANT formatage
    (constat E-18).
    """
    if x is None:
        return "—"
    if abs(x) < 0.005:                 # sous le demi-centime : zéro tout court
        x = 0.0
    s = f"{x:,.2f}".replace(",", " ").replace(".", ",")
    return f"{s} €"


def _styles():
    base = getSampleStyleSheet()
    return {
        "titre": ParagraphStyle("titre", parent=base["Title"],
                                textColor=BLEU, fontSize=20, spaceAfter=4),
        "sous": ParagraphStyle("sous", parent=base["Normal"],
                               textColor=GRIS, fontSize=10, spaceAfter=12),
        "h2": ParagraphStyle("h2", parent=base["Heading2"], textColor=BLEU,
                             fontSize=13, spaceBefore=14, spaceAfter=6),
        "normal": ParagraphStyle("normal", parent=base["Normal"], fontSize=9,
                                 leading=12),
        "note": ParagraphStyle("note", parent=base["Normal"], fontSize=8,
                               textColor=GRIS, leading=10, spaceBefore=4),
    }


def _table(lignes, largeurs=None, aligne_droite=(1,)):
    """Table 2 colonnes+ : entête grisée, montants alignés à droite."""
    t = Table(lignes, colWidths=largeurs, hAlign="LEFT")
    style = [
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("BACKGROUND", (0, 0), (-1, 0), FOND),
        ("TEXTCOLOR", (0, 0), (-1, 0), BLEU),
        ("LINEBELOW", (0, 0), (-1, 0), 0.75, BLEU),
        ("LINEBELOW", (0, 1), (-1, -2), 0.25, colors.HexColor("#e4e7ec")),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]
    for col in aligne_droite:
        style.append(("ALIGN", (col, 0), (col, -1), "RIGHT"))
    t.setStyle(TableStyle(style))
    return t


def _ligne_tot(t: Table, index: int) -> None:
    t.setStyle(TableStyle([
        ("FONTNAME", (0, index), (-1, index), "Helvetica-Bold"),
        ("LINEABOVE", (0, index), (-1, index), 1, BLEU),
    ]))


def _version() -> str:
    """Version du logiciel, lue dans le fichier VERSION livré à côté."""
    try:
        # VERSION vit à la RACINE du paquet, ce module dans modules/ :
        # deux dirname, pas un.
        racine = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(racine, "VERSION"), encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return "?"


def _pied_de_page(provisoire: bool):
    """Pied de page : avertissement, horodatage d'édition, version, page.

    Le document ne portait ni date, ni heure, ni version. Deux tirages d'un
    même exercice, entre lesquels une écriture a été corrigée, étaient
    visuellement indiscernables — sur une pièce destinée à un
    expert-comptable ou à un dossier de contrôle, c'est la première chose
    qui manque (constat E-15).
    """
    edite_le = datetime.now().strftime("%d/%m/%Y à %H:%M")
    signature = f"Compta LMNP v{_version()} — édité le {edite_le}"

    def dessiner(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(GRIS)
        canvas.drawString(15 * mm, 10 * mm,
                          "Compta LMNP — état de travail à faire valider par "
                          "un expert-comptable avant tout dépôt.")
        canvas.drawRightString(A4[0] - 15 * mm, 10 * mm,
                               f"Page {doc.page}")
        canvas.setFont("Helvetica", 6.5)
        canvas.drawString(15 * mm, 6.5 * mm, signature)
        if provisoire:
            canvas.setFont("Helvetica-Bold", 60)
            canvas.setFillColor(colors.Color(0.71, 0.13, 0.09, alpha=0.08))
            canvas.saveState()
            canvas.translate(A4[0] / 2, A4[1] / 2)
            canvas.rotate(45)
            canvas.drawCentredString(0, 0, "PROVISOIRE")
            canvas.restoreState()
        canvas.restoreState()
    return dessiner


def generer_pdf(L: dict, chemin_ou_buffer) -> None:
    """Écrit le PDF de la liasse `L` (= liasse.generer()) dans un chemin ou un buffer."""
    st = _styles()
    doc = SimpleDocTemplate(
        chemin_ou_buffer, pagesize=A4,
        leftMargin=15 * mm, rightMargin=15 * mm,
        topMargin=15 * mm, bottomMargin=18 * mm,
        title=f"Liasse fiscale LMNP {L['annee']}",
        author="Compta LMNP")
    E = []  # flowables

    # ── Page de garde ────────────────────────────────────────────────────
    exp = L.get("exploitant") or {}
    statut = ("exercice clos" if not L["provisoire"]
              else "exercice NON clôturé — chiffres provisoires")
    E.append(Paragraph(f"Liasse fiscale LMNP — exercice {L['annee']}",
                       st["titre"]))
    # _xml() : les textes des Paragraph sont interprétés comme du balisage
    # par ReportLab — toute donnée UTILISATEUR doit être échappée, sinon un
    # nom contenant « < » fait planter la génération (même famille de défaut
    # que la XSS corrigée en v7, appliquée à la frontière PDF).
    ident = " · ".join(x for x in (
        exp.get("nom"), exp.get("siret") and f"SIRET {exp['siret']}",
        exp.get("adresse")) if x)
    E.append(Paragraph(f"{_xml(ident) or 'Exploitant non renseigné'}"
                       f" &nbsp;—&nbsp; {statut}", st["sous"]))
    # L'avertissement vivait dans la docstring du module, donc nulle part
    # pour le lecteur — alors que la page de garde s'intitule « Liasse
    # fiscale LMNP », ce qu'on peut prendre pour un formulaire officiel.
    E.append(Paragraph(
        "Ce document est un <b>état de travail</b> fidèle aux montants "
        "calculés — <b>pas un fac-similé des formulaires CERFA</b>. Les "
        "numéros de cases officiels y figurent pour permettre le report "
        "champ à champ dans la télédéclaration, ou par l'expert-comptable.",
        st["note"]))
    # Un exercice de cession se lit tout entier de travers si l'on croit
    # que la neutralisation du BIC calcule la plus-value. Le pense-bête le
    # dit bien, mais le PDF est ce qui part chez le comptable ou reste au
    # dossier : il doit le dire aussi, et le dire LÀ, sur la page de garde.
    if L.get("cession_de_l_exercice"):
        E.append(Spacer(1, 4))
        E.append(Paragraph(
            "<b>Une cession a eu lieu sur cet exercice.</b> Le prix de vente "
            "et la valeur comptable du bien sont NEUTRALISÉS dans le "
            "résultat BIC ci-après : en location meublée non "
            "professionnelle, la plus-value relève du régime des "
            "PARTICULIERS (article 150 U du CGI). Ce document ne la calcule "
            "donc pas, et l'absence de plus-value dans le résultat LMNP ne "
            "signifie pas qu'il n'y a rien à déclarer : la plus-value "
            "immobilière est établie et déclarée séparément par le notaire "
            "(formulaire 2048-IMM), au moment de la vente. Vérifiez auprès "
            "de lui que cette formalité a bien été accomplie.",
            st["note"]))
    E.append(Spacer(1, 6))

    g = L["page_garde"]
    E.append(_table([
        ["Chiffres clés", "Montant"],
        ["Recettes de l'exercice (CA HT)", _eur(g["ca_ht"])],
        ["Résultat fiscal LMNP", _eur(g["resultat_fiscal"])],
        ["Déficit LMNP généré", _eur(g["deficit_lmnp"])],
        ["Revenu imposable (2042C-PRO)", _eur(g["revenu_imposable"])],
        ["Amortissements en report (art. 39 C)", _eur(g["restant_39c"])],
        ["Déficits LMNP en stock", _eur(g["restant_deficits"])],
        ["Total des reports disponibles", _eur(g["restant_total"])],
    ], largeurs=[110 * mm, 60 * mm]))

    # ── Projection de clôture (exercice ouvert uniquement) ───────────────
    # Les tableaux ci-dessous reflètent les ÉCRITURES. Or la dotation aux
    # amortissements n'est comptabilisée qu'à la clôture : sans ce bloc, le
    # déclarant lisait toute l'année un résultat fiscal qui l'ignorait.
    proj = L.get("projection_cloture")
    if proj and proj["dotation_previsionnelle"]:
        E.append(Paragraph("Projection — si l'exercice était clôturé "
                           "aujourd'hui", st["h2"]))
        E.append(Paragraph(
            "Les tableaux qui suivent ne portent que les écritures "
            "enregistrées. La dotation aux amortissements de l'exercice "
            "n'est comptabilisée qu'à la clôture : ces chiffres-là "
            "l'anticipent, d'après le plan d'amortissement.", st["sous"]))
        E.append(_table([
            ["Projection de clôture", "Montant"],
            ["Dotation aux amortissements de l'exercice",
             _eur(proj["dotation_previsionnelle"])],
            ["Résultat comptable projeté",
             _eur(proj["resultat_comptable_projete"])],
            ["Amortissements reportés (art. 39 C) projetés",
             _eur(proj["report_39c_projete"])],
            ["Résultat fiscal projeté",
             _eur(proj["resultat_fiscal_projete"])],
        ], largeurs=[110 * mm, 60 * mm]))

    # ── 2031 / 2031 bis ──────────────────────────────────────────────────
    r = L["f2031"]
    E.append(Paragraph("2031-SD — Récapitulation", st["h2"]))
    lignes = [["Rubrique", "Montant"],
              ["Résultat fiscal (ligne 1 — activité exclue, cf. 2031 bis)",
               _eur(r["resultat_fiscal_1"])]]
    if r["bic_non_pro_7a_benefice"] is not None:
        lignes.append(["BIC non professionnel — bénéfice (cadre 7a)",
                       _eur(r["bic_non_pro_7a_benefice"])])
    if r["bic_non_pro_7b_deficit"] is not None:
        lignes.append(["BIC non professionnel — déficit (cadre 7b)",
                       _eur(r["bic_non_pro_7b_deficit"])])
    E.append(_table(lignes, largeurs=[110 * mm, 60 * mm]))

    # ── 2033-A ───────────────────────────────────────────────────────────
    a = L["f2033a"]
    E.append(Paragraph("2033-A — Bilan simplifié", st["h2"]))
    ta = _table([
        ["Actif", "Montant"],
        ["Immobilisations corporelles — brut (case 028)",
         _eur(a["immo_corporelles_brut_028"])],
        ["Amortissements (case 030)", _eur(a["amortissements_030"])],
        ["Immobilisations corporelles — net", _eur(a["immo_corporelles_net"])],
        ["Total actif net (case 112)", _eur(a["total_actif_net_112"])],
    ], largeurs=[110 * mm, 60 * mm])
    _ligne_tot(ta, 4)
    E.append(ta)
    E.append(Spacer(1, 4))
    tp = _table([
        ["Passif", "Montant"],
        ["Capital individuel (case 120)", _eur(a["capital_individuel_120"])],
        ["Résultat de l'exercice (case 136)", _eur(a["resultat_exercice_136"])],
        ["Total capitaux propres (case 142)", _eur(a["total_capitaux_142"])],
        ["Total passif (case 180)", _eur(a["total_passif_180"])],
    ], largeurs=[110 * mm, 60 * mm])
    _ligne_tot(tp, 4)
    E.append(tp)

    # ── 2033-B ───────────────────────────────────────────────────────────
    b = L["f2033b"]
    E.append(Paragraph("2033-B — Compte de résultat simplifié", st["h2"]))
    tb = _table([
        ["Rubrique", "Montant"],
        ["Production vendue — services, loyers (case 218)",
         _eur(b["produits_218"])],
        ["Autres produits (case 230)", _eur(b["autres_produits_230"])],
        ["Total des produits d'exploitation (case 232)",
         _eur(b["total_produits_232"])],
        ["Autres charges externes (case 242)", _eur(b["charges_externes_242"])],
        ["Impôts et taxes (case 244) — dont CFE et CVAE "
         + _eur(b["dont_cfe_243"]), _eur(b["impots_244"])],
        # 250 et 262 : sans elles, un compte de charge hors des préfixes
        # nommés n'apparaissait dans AUCUNE case, tout en pesant sur le
        # résultat. 262 est le reste rendu visible.
        ["Rémunérations du personnel (case 250)", _eur(b["personnel_250"])],
        ["Autres charges (case 262)", _eur(b["autres_charges_262"])],
        ["Dotations aux amortissements (case 254)", _eur(b["dotations_254"])],
        ["Total des charges d'exploitation (case 264)",
         _eur(b["total_charges_264"])],
        ["Résultat d'exploitation (case 270)",
         _eur(b["resultat_exploitation_270"])],
        # Ordre et numéros repris du CERFA 2033-B-SD 2026 (n° 15948*08) :
        # 280 puis 294, puis 290 puis 300, avant la case 310. Le document
        # sert au report champ à champ — suivre l'ordre du formulaire est
        # sa raison d'être. La ligne des charges exceptionnelles était
        # CALCULÉE mais jamais rendue, le prix de cession apparaissant sans
        # sa contrepartie (constat E-20).
        ["Produits financiers (case 280)", _eur(b["produits_financiers_280"])],
        ["Charges financières — intérêts d'emprunt (case 294)",
         _eur(b["charges_financieres_294"])],
        ["Produits exceptionnels — dont cessions (case 290)",
         _eur(b["produits_exceptionnels_290"])],
        ["Charges exceptionnelles (case 300) — dont valeur comptable des "
         "éléments cédés", _eur(b["charges_exceptionnelles_300"])],
        ["Bénéfice ou perte (case 310)", _eur(b["benefice_ou_perte_310"])],
    ], largeurs=[110 * mm, 60 * mm])
    _ligne_tot(tb, 15)     # la ligne 310, décalée par les ajouts 230/232/250/262
    E.append(tb)

    lignes = [["Réintégrations / déductions", "Montant"],
              ["Réintégration — amortissements excédentaires art. 39 C (case 318)",
               _eur(b["reintegration_amort_318"])]]
    for lib, m in b["reintegrations_detail"]:
        lignes.append([f"Réintégration — {lib} (case 330)", _eur(m)])
    for lib, m in b["deductions_detail"]:
        lignes.append([f"Déduction — {lib} (case 350)", _eur(m)])
    lignes.append(["Résultat fiscal ligne 352 (doit valoir 0 — activité "
                   "déclarée en 2031 bis)", _eur(b["resultat_fiscal_352"])])
    tr = _table(lignes, largeurs=[110 * mm, 60 * mm])
    _ligne_tot(tr, len(lignes) - 1)
    E.append(Spacer(1, 4))
    E.append(tr)

    # ── 2033-C ───────────────────────────────────────────────────────────
    c = L["f2033c"]
    E.append(Paragraph("2033-C — Immobilisations et amortissements", st["h2"]))
    # Les numéros de case étaient CALCULÉS par liasse.py (case_immo,
    # case_amort) et jamais rendus : le 2033-C était le seul tableau du
    # document à ne pas porter les siens, alors que le report champ à champ
    # est la raison d'être de ce PDF. Cases relevées sur le CERFA
    # 2033-C-SD 2026 : 420/430/450/470 (brut), 510/520/540/560 (amort.).
    lignes = [["Rubrique", "Brut début", "Augment.", "Brut fin",
               "Diminutions", "Amort. début", "Dotation",
               "Amort. dimin.", "Amort. fin"]]
    for rub in c["rubriques"]:
        # Enveloppé comme partout ailleurs : une chaîne brute ne se coupe pas
        # dans une table reportlab, elle déborde sur les colonnes voisines.
        # Mesuré : « Installations generales, agencements et amenagements des
        # constructions » fait 279,2 pt dans une colonne qui en offre 118,4
        # — trois colonnes de montants recouvertes (constat E-16).
        lignes.append([Paragraph(
            _xml(f"{rub['libelle']} (cases {rub['case_immo']} / "
                 f"{rub['case_amort']})"), st["normal"]),
                       _eur(rub["brut_debut"]), _eur(rub["augmentations"]),
                       _eur(rub["diminutions"]), _eur(rub["brut_fin"]),
                       _eur(rub["amort_debut"]), _eur(rub["dotation"]),
                       _eur(rub["amort_diminutions"]), _eur(rub["amort_fin"])])
    tt = c["totaux"]
    lignes.append(["Totaux", _eur(tt["brut_debut"]), _eur(tt["augmentations"]),
                   _eur(tt["diminutions"]), _eur(tt["brut_fin"]),
                   _eur(tt["amort_debut"]), _eur(tt["dotation"]),
                   _eur(tt["amort_diminutions"]), _eur(tt["amort_fin"])])
    t = _table(lignes, largeurs=[38 * mm] + [16.5 * mm] * 8,
               aligne_droite=range(1, 9))
    _ligne_tot(t, len(lignes) - 1)
    E.append(t)

    E.append(Paragraph("Détail par composant", st["h2"]))
    lignes = [["Composant", "Valeur brute", "Durée", "Dotation",
               "Cumul fin", "VNC fin"]]
    for d in c["detail_composants"]:
        lignes.append([Paragraph(_xml(d["libelle"]), st["normal"]),
                       _eur(d["valeur_brute"]),
                       f"{d['duree']} ans" if d["duree"] else "—",
                       _eur(d["dotation"]), _eur(d["cumul_fin"]),
                       _eur(d["vnc_fin"])])
    E.append(_table(lignes, largeurs=[58 * mm, 24 * mm, 16 * mm,
                                      24 * mm, 24 * mm, 24 * mm],
                    aligne_droite=range(1, 6)))

    # ── Suivi des reports ────────────────────────────────────────────────
    rep = L["reports"]
    s39 = rep["suivi_39c"]
    E.append(Paragraph("Suivi des reports — article 39 C", st["h2"]))
    # La SORTIE de stock d'un bien cédé manquait à ce tableau : seul le
    # détail par bien la portait, et il n'est imprimé qu'à partir de deux
    # biens. Sur un dossier mono-bien, l'état archivable affichait donc
    # « ouverture 5 000 + reporté 1 200 − repris 0 = clôture 0 » — un
    # tableau qui ne se réconcilie pas, et 6 200 € de mouvement sans
    # explication. La ligne n'apparaît que lorsqu'il y a une sortie, pour
    # ne pas encombrer le cas ordinaire.
    sortie_39c = round(rep.get("sortie_39c") or 0.0, 2)
    lignes_39c = [
        ["Rubrique", "Montant"],
        ["Stock d'ouverture", _eur(s39.get("stock_ouverture"))],
        ["Amortissements reportés cette année", _eur(s39.get("report_annee"))],
        ["Amortissements repris cette année", _eur(s39.get("utilisation_annee"))],
    ]
    if sortie_39c:
        lignes_39c.append(
            ["Stock sorti avec un bien cédé (ligne G')", _eur(sortie_39c)])
    lignes_39c.append(["Stock à la clôture", _eur(s39.get("stock_cloture"))])
    E.append(_table(lignes_39c, largeurs=[110 * mm, 60 * mm]))

    # Ventilation logement par logement — affichée dès que la comptabilité
    # compte plusieurs biens, ou qu'une sortie doit être expliquée même sur
    # un bien unique.
    par_bien = rep.get("suivi_39c_par_bien") or []
    if len(par_bien) > 1 or (par_bien and sortie_39c):
        E.append(Paragraph("Suivi du stock 39 C, logement par logement",
                           st["h2"]))
        avec_sorties = any(v.get("sortie_bien") for v in par_bien)
        entetes = ["Bien", "Ouverture", "Reporté", "Repris"]
        if avec_sorties:
            entetes.append("Sorti (G')")
        entetes.append("Stock fin")
        lignes_b = [entetes]
        for v in par_bien:
            ligne = [Paragraph(_xml(v["libelle"]), st["normal"]),
                     _eur(v["stock_ouverture"]), _eur(v["report_bien"]),
                     _eur(v["utilisation_bien"])]
            if avec_sorties:
                ligne.append(_eur(v.get("sortie_bien", 0)))
            ligne.append(_eur(v["stock_cloture"]))
            lignes_b.append(ligne)
        larg = [60 * mm] + [22 * mm] * (len(entetes) - 1)
        # `aligne_droite` n'était pas passé : le défaut (1,) n'alignait que
        # « Ouverture », laissant « Reporté », « Repris », « Sorti » et
        # « Stock fin » à gauche — dans le seul tableau où l'on compare des
        # colonnes entre elles (constat E-17).
        E.append(_table(lignes_b, largeurs=larg,
                        aligne_droite=range(1, len(entetes))))

    E.append(Paragraph("Déficits LMNP par millésime", st["h2"]))
    if rep["deficits"]:
        lignes = [["Origine", "Montant initial", "Solde", "Expire fin"]]
        for d in rep["deficits"]:
            lignes.append([str(d["annee_origine"]), _eur(d["montant_initial"]),
                           _eur(d["solde"]), (str(d["annee_expiration"]) + (" — périmé" if d.get("perime") else ""))])
        lignes.append(["Total", "", _eur(rep["total_deficits"]), ""])
        t = _table(lignes, largeurs=[30 * mm, 45 * mm, 45 * mm, 30 * mm],
                   aligne_droite=(1, 2))
        _ligne_tot(t, len(lignes) - 1)
        E.append(t)
    else:
        E.append(Paragraph("Aucun déficit LMNP en stock.", st["normal"]))

    if rep.get("total_deficits_perimes", 0):
        E.append(Paragraph(
            "Déficits perdus par péremption : "
            + _eur(rep["total_deficits_perimes"]), st["normal"]))
        for d in rep["deficits"]:
            if d.get("perime") and (d.get("perte_peremption") or d["solde"]):
                E.append(Paragraph(
                    f"Millésime {d['annee_origine']} : "
                    + _eur(d.get("perte_peremption") or d["solde"])
                    + " perdus, exclus du stock disponible.", st["normal"]))

    # ── Aide 2042C-PRO ───────────────────────────────────────────────────
    aide = L["aide_2042c"]
    E.append(Paragraph("Aide au report — 2042C-PRO", st["h2"]))
    lignes = [["Case", "Montant"]]
    if aide["case_5NA"] is not None:
        lignes.append(["5NA — bénéfice location meublée non professionnelle",
                       _eur(aide["case_5NA"])])
    if aide["case_5NY"] is not None:
        lignes.append(["5NY — déficit location meublée non professionnelle",
                       _eur(aide["case_5NY"])])
    for cd in aide["cases_deficits_anterieurs"]:
        lignes.append([f"{cd['case']} — déficit {cd['annee_origine']} "
                       "non encore déduit", _eur(cd["montant"])])
    if len(lignes) == 1:
        lignes.append(["Aucune case à servir", "—"])
    E.append(_table(lignes, largeurs=[110 * mm, 60 * mm]))
    # Seule chaîne de données à échapper au traitement : l'exception n'était
    # pas motivée, et un « & » dans la note ferait échouer la génération.
    E.append(Paragraph(_xml(aide["note"]), st["note"]))

    # ── Contrôles de cohérence ───────────────────────────────────────────
    E.append(Paragraph("Contrôles de cohérence internes", st["h2"]))
    lignes = [["Contrôle", "Résultat", "Détail"]]
    for ctl in L["controles"]:
        lignes.append([Paragraph(_xml(ctl["nom"]), st["normal"]),
                       "conforme" if ctl["ok"] else "ANOMALIE",
                       Paragraph(_xml(ctl["detail"]), st["normal"])])
    t = _table(lignes, largeurs=[80 * mm, 22 * mm, 68 * mm],
               aligne_droite=())
    for i, ctl in enumerate(L["controles"], start=1):
        t.setStyle(TableStyle([
            ("TEXTCOLOR", (1, i), (1, i), VERT if ctl["ok"] else ROUGE),
            ("FONTNAME", (1, i), (1, i), "Helvetica-Bold")]))
    E.append(t)

    pied = _pied_de_page(L["provisoire"])
    doc.build(E, onFirstPage=pied, onLaterPages=pied)
