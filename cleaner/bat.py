"""
Génération du BAT (Bon À Tirer) — document HTML de validation client.

Le BAT est envoyé au client avant le lancement de la campagne postale.
Il présente l'intégralité des plis au format enveloppe La Poste NF Z 10-011,
imprimable depuis n'importe quel navigateur (Ctrl+P → Enregistrer en PDF).
"""
from datetime import datetime
import pandas as pd
from cleaner.laposte import format_envelope_lines


_CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: Arial, sans-serif; background: #f4f4f4; color: #1a1a1a; }

.header {
    background: #1E6B3C; color: white;
    padding: 20px 32px; margin-bottom: 24px;
}
.header h1 { font-size: 22px; font-weight: 700; letter-spacing: 1px; }
.header .meta { font-size: 12px; opacity: .75; margin-top: 4px; }
.header .stats { font-size: 13px; margin-top: 12px; }
.header .stats span {
    background: rgba(255,255,255,.15);
    padding: 3px 10px; border-radius: 12px; margin-right: 8px;
}

.grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 16px;
    padding: 0 32px 32px;
}

.card {
    background: white;
    border: 2px solid #1E6B3C;
    border-radius: 8px;
    padding: 14px 16px;
    font-family: 'Courier New', monospace;
    font-size: 13px;
    min-height: 140px;
    break-inside: avoid;
    page-break-inside: avoid;
}
.card .card-num {
    font-family: Arial, sans-serif;
    font-size: 9px; color: #aaa;
    letter-spacing: 1px; margin-bottom: 8px;
    display: flex; justify-content: space-between;
}
.card .line { line-height: 1.8; }
.card .line .lbl {
    display: inline-block; width: 22px;
    font-size: 8px; color: #ccc; vertical-align: middle;
}
.card .line-l6 { font-weight: 700; color: #1E6B3C; }
.card .warning {
    margin-top: 6px; font-size: 10px; color: #c00;
    font-family: Arial, sans-serif;
}
.card.doublon { border-color: #c00; }
.card.doublon .card-num { color: #c00; }
.card.consolidated { border-color: #e6a800; }

.footer {
    text-align: center; padding: 20px;
    font-size: 11px; color: #999;
    border-top: 1px solid #ddd; margin-top: 16px;
}

@media print {
    body { background: white; }
    .header { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
    .card { border: 2px solid #1E6B3C !important; }
    .grid { padding: 0; }
}
"""


def _card_html(
    row: dict,
    line_num: int,
    is_doublon: bool = False,
    is_consolidated: bool = False,
) -> str:
    lines = format_envelope_lines(row)
    has_voie = any(lbl == "L4" for lbl, _ in lines)

    lines_html = ""
    for lbl, content in lines:
        cls = "line-l6" if lbl == "L6" else ""
        lines_html += (
            f"<div class='line {cls}'>"
            f"<span class='lbl'>{lbl}</span>{content}</div>"
        )

    warning = "<div class='warning'>⚠ Ligne de voie manquante</div>" if not has_voie else ""

    badges = []
    if is_doublon:
        badges.append("DOUBLON")
    if is_consolidated:
        badges.append("ADRESSE RÉORG.")
    badge_str = " · ".join(badges)

    card_cls = "card"
    if is_doublon:
        card_cls += " doublon"
    elif is_consolidated:
        card_cls += " consolidated"

    return f"""
<div class="{card_cls}">
    <div class="card-num">
        <span>Pli n° {line_num}</span>
        <span>{badge_str}</span>
    </div>
    {lines_html}
    {warning}
</div>"""


def generate_bat(
    df: pd.DataFrame,
    nom_travail: str = "",
    doublons: list | None = None,
    consolidation_journal: list | None = None,
) -> str:
    """
    Génère le HTML complet du BAT.

    Args:
        df: DataFrame nettoyé (champs standards)
        nom_travail: nom du projet / client
        doublons: liste des doublons détectés
        consolidation_journal: liste des consolidations d'adresse

    Returns:
        Chaîne HTML complète.
    """
    doublons = doublons or []
    consolidation_journal = consolidation_journal or []

    doublon_indices = {ln - 2 for d in doublons for ln in d["lignes"]}
    consolidated_indices = {e["ligne"] - 2 for e in consolidation_journal}

    titre = nom_travail or "BAT — Vérification des adresses"
    date_str = datetime.now().strftime("%d/%m/%Y à %H:%M")
    nb = len(df)
    nb_doublons = len(doublons)
    nb_consol = len(consolidated_indices)

    cards_html = ""
    for position, (idx, row) in enumerate(df.iterrows(), start=1):
        cards_html += _card_html(
            row.to_dict(),
            line_num=position,
            is_doublon=idx in doublon_indices,
            is_consolidated=idx in consolidated_indices,
        )

    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>BAT — {titre}</title>
<style>{_CSS}</style>
</head>
<body>

<div class="header">
    <h1>BAT — Bon À Tirer</h1>
    <div class="meta">
        NormAdress · Norme La Poste NF Z 10-011 · Généré le {date_str}
    </div>
    <div style="font-size:16px;margin-top:8px;font-weight:600;">{titre}</div>
    <div class="stats">
        <span>{nb} pli(s)</span>
        {"<span style='background:rgba(255,80,80,.3);'>⚠ " + str(nb_doublons) + " doublon(s)</span>" if nb_doublons else ""}
        {"<span style='background:rgba(255,200,0,.3);'>⟳ " + str(nb_consol) + " adresse(s) réorganisée(s)</span>" if nb_consol else ""}
    </div>
</div>

<div class="grid">
{cards_html}
</div>

<div class="footer">
    Document généré par NormAdress · Norme AFNOR NF Z 10-011 ·
    Imprimable via Ctrl+P · Les plis en rouge contiennent des doublons à vérifier.
</div>

</body>
</html>"""
