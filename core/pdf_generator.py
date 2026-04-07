"""Génération du PDF BAT (blocs adresse 4 par page)."""
from __future__ import annotations
import io
from datetime import datetime

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import (SimpleDocTemplate, Table, TableStyle,
                                Paragraph, Spacer)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle


PAGE_W, PAGE_H = A4
MARGIN = 1.5 * cm
LONGUEUR_MAX = 38

ORANGE = colors.HexColor("#E67E22")
ROUGE = colors.HexColor("#E74C3C")
GRIS_CLAIR = colors.HexColor("#F2F2F2")


def _style_adresse() -> ParagraphStyle:
    styles = getSampleStyleSheet()
    return ParagraphStyle(
        "adresse",
        parent=styles["Normal"],
        fontName="Courier",
        fontSize=9,
        leading=13,
    )


def _style_num() -> ParagraphStyle:
    styles = getSampleStyleSheet()
    return ParagraphStyle(
        "num",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=7,
        textColor=colors.grey,
        alignment=2,  # right
    )


def _bloc_adresse(adresse: dict, style: ParagraphStyle,
                  style_num: ParagraphStyle) -> list:
    """Retourne une liste de Paragraphes pour un bloc."""
    lignes_afnor = ["L1", "L2", "L3", "L4", "L5", "L6"]
    contenu = []

    # Numéro de ligne source
    num = adresse.get("ligne_source", "")
    contenu.append(Paragraph(f"#{num}", style_num))

    for k in lignes_afnor:
        val = (adresse.get(k) or adresse.get(k.lower()) or "").strip()
        if not val:
            continue
        couleur = ""
        if len(val) > LONGUEUR_MAX:
            couleur = f'<font color="#{ORANGE.hexval()[2:]}"><b>{val}</b></font>'
        else:
            couleur = val
        contenu.append(Paragraph(couleur, style))

    return contenu


def generer_pdf_bat(adresses: list[dict], nom_dossier: str) -> bytes:
    """
    Génère un PDF BAT avec grille 2×2 blocs par page.
    adresses : liste de dicts avec l1..l6 (minuscules, depuis Supabase)
               ou L1..L6 (majuscules, depuis composer)
    """
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=MARGIN, bottomMargin=MARGIN,
    )

    style = _style_adresse()
    style_num = _style_num()
    styles = getSampleStyleSheet()

    def _normaliser(a: dict) -> dict:
        """Normalise les clés l1→L1 depuis Supabase."""
        out = dict(a)
        for k in ("l1", "l2", "l3", "l4", "l5", "l6"):
            if k in out:
                out[k.upper()] = out.pop(k)
        return out

    adresses_norm = [_normaliser(a) for a in adresses]

    elements = []

    # En-tête
    titre = Paragraph(
        f"<b>BAT — {nom_dossier}</b>",
        styles["Heading2"]
    )
    date_str = datetime.now().strftime("%d/%m/%Y %H:%M")
    sous_titre = Paragraph(
        f"Généré le {date_str} · {len(adresses_norm)} destinataires",
        styles["Normal"]
    )
    elements.extend([titre, sous_titre, Spacer(1, 0.5 * cm)])

    # Grille 2×2
    col_w = (PAGE_W - 2 * MARGIN) / 2

    for i in range(0, len(adresses_norm), 4):
        groupe = adresses_norm[i:i + 4]
        # Compléter à 4 si nécessaire
        while len(groupe) < 4:
            groupe.append({})

        blocs = [_bloc_adresse(a, style, style_num) if a else [""] for a in groupe]

        data = [
            [blocs[0], blocs[1]],
            [blocs[2], blocs[3]],
        ]

        t = Table(data, colWidths=[col_w, col_w], rowHeights=[4 * cm, 4 * cm])
        t.setStyle(TableStyle([
            ("BOX", (0, 0), (-1, -1), 0.5, colors.black),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("PADDING", (0, 0), (-1, -1), 6),
            ("BACKGROUND", (0, 0), (-1, -1), GRIS_CLAIR),
        ]))
        elements.append(t)
        elements.append(Spacer(1, 0.3 * cm))

    doc.build(elements)
    buf.seek(0)
    return buf.read()
