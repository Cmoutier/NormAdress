"""NormAdress — Application Streamlit de mise en conformité d'adresses."""
from pathlib import Path
from collections import defaultdict
import pandas as pd
import streamlit as st
from PIL import Image

from cleaner.loader import load_file
from cleaner.mapper import auto_map, detect_multi_contacts, STANDARD_FIELDS
from cleaner.rules import apply_rules
from cleaner.consolidator import consolidate_addresses, remove_empty_rows, detect_duplicates
from cleaner.coherence import run_all as run_coherence
from cleaner.laposte import apply_laposte_rules, format_attention
from cleaner.exporter import export_excel, export_rapport

_favicon = Image.open(Path(__file__).parent / "favicon.png")
st.set_page_config(page_title="NormAdress", page_icon=_favicon, layout="wide")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def sample_value(df, col):
    vals = df[col].dropna()
    vals = vals[vals.astype(str).str.strip() != ""]
    return str(vals.iloc[0]) if len(vals) > 0 else "—"


def format_envelope_lines(row: dict) -> list[tuple[str, str]]:
    """
    Retourne les lignes d'adresse selon la norme La Poste NF Z 10-011.
    Tuple : (numéro_ligne, contenu)
    Structure :
      L1 — Raison sociale OU Civilité Prénom NOM
      L2 — Complément identité (À L'ATTENTION DE / contact B2B)
      L3 — Adresse3 : bâtiment, résidence, étage
      L4 — Adresse1 : N° et libellé de voie  (ligne obligatoire)
      L5 — Adresse2 : BP, lieu-dit, complément de distribution
      L6 — CODE POSTAL  VILLE
    """
    civ    = str(row.get("Civilite",   "")).strip()
    prenom = str(row.get("Prenom",     "")).strip()
    nom    = str(row.get("Nom",        "")).strip()
    societe= str(row.get("Societe",    "")).strip()
    adr1   = str(row.get("Adresse1",   "")).strip()
    adr2   = str(row.get("Adresse2",   "")).strip()
    adr3   = str(row.get("Adresse3",   "")).strip()
    cp     = str(row.get("CodePostal", "")).strip()
    ville  = str(row.get("Ville",      "")).strip()

    contact = " ".join(p for p in [civ, prenom, nom] if p)
    lines = []

    if societe:
        lines.append(("L1", societe))
        if contact:
            lines.append(("L2", contact))
    elif contact:
        lines.append(("L1", contact))

    if adr3:
        lines.append(("L3", adr3))
    if adr1:
        lines.append(("L4", adr1))
    if adr2:
        lines.append(("L5", adr2))

    cp_ville = " ".join(p for p in [cp, ville] if p)
    if cp_ville:
        lines.append(("L6", cp_ville))

    return lines


def envelope_html(lines: list[tuple[str, str]], highlight_line: str = "L6") -> str:
    """Génère une carte enveloppe HTML."""
    rows_html = ""
    for label, content in lines:
        is_cp = label == highlight_line
        weight = "font-weight:700;" if is_cp else ""
        color  = "color:#1E6B3C;" if is_cp else "color:#1a1a1a;"
        lbl_style = (
            "display:inline-block;width:24px;font-size:9px;"
            "color:#aaa;vertical-align:middle;margin-right:4px;"
        )
        rows_html += (
            f"<div style='line-height:1.7;{weight}{color}'>"
            f"<span style='{lbl_style}'>{label}</span>{content}</div>"
        )

    missing = not any(l == "L4" for l, _ in lines)
    warning = (
        "<div style='margin-top:6px;font-size:10px;color:#c00;'>"
        "⚠ Ligne de voie manquante</div>"
        if missing else ""
    )

    return f"""
<div style="
    border:2px solid #1E6B3C;border-radius:8px;padding:12px 14px;
    font-family:'Courier New',monospace;font-size:12.5px;
    background:#fff;min-height:130px;
    box-shadow:2px 2px 8px rgba(0,0,0,.07);
    margin-bottom:4px;
">
    <div style="font-size:9px;color:#bbb;letter-spacing:1px;margin-bottom:6px;">
        LA POSTE — NF Z 10-011
    </div>
    {rows_html}
    {warning}
</div>"""


def source_card_html(row_orig: dict) -> str:
    """Génère une carte 'données source' HTML."""
    rows_html = ""
    for k, v in row_orig.items():
        v_str = str(v).strip()
        if not v_str:
            continue
        rows_html += (
            f"<div style='line-height:1.7;color:#555;'>"
            f"<span style='font-size:9px;color:#aaa;display:inline-block;"
            f"width:80px;'>{k}</span>{v_str}</div>"
        )
    return f"""
<div style="
    border:1px solid #ddd;border-radius:8px;padding:12px 14px;
    font-family:sans-serif;font-size:12.5px;
    background:#fafafa;min-height:130px;
    margin-bottom:4px;
">
    <div style="font-size:9px;color:#bbb;letter-spacing:1px;margin-bottom:6px;">
        DONNÉES SOURCE
    </div>
    {rows_html}
</div>"""


# ---------------------------------------------------------------------------
# En-tête
# ---------------------------------------------------------------------------
col_logo, col_title = st.columns([1, 11])
with col_logo:
    try:
        st.image("logo.svg", width=72)
    except Exception:
        pass
with col_title:
    st.title("NormAdress")
    st.caption("Mise en conformité de fichiers d'adresses pour publipostage Word")

st.divider()

# ---------------------------------------------------------------------------
# ÉTAPE 1 — Import
# ---------------------------------------------------------------------------
st.subheader("Étape 1 — Importer le fichier")

uploaded = st.file_uploader(
    "Glissez un fichier Excel ou CSV",
    type=["xlsx", "xls", "csv"],
    label_visibility="collapsed",
)

if not uploaded:
    st.info("Importez un fichier Excel (.xlsx / .xls) ou CSV pour commencer.")
    st.stop()

try:
    file_data = load_file(uploaded)
except Exception as e:
    st.error(f"Impossible de lire le fichier : {e}")
    st.stop()

if len(file_data["sheets"]) > 1:
    sheet_name = st.selectbox("Feuille à traiter :", file_data["sheets"])
else:
    sheet_name = file_data["sheets"][0]

source_df = file_data["dataframes"][sheet_name].copy()
nb_importees = len(source_df)

col_info, col_warn = st.columns(2)
col_info.success(f"**{nb_importees}** lignes · **{len(source_df.columns)}** colonnes")
if nb_importees > 50_000:
    col_warn.warning("Fichier volumineux (>50 000 lignes)")

with st.expander("Aperçu du fichier source (5 premières lignes)"):
    st.dataframe(source_df.head(5), use_container_width=True)

st.divider()

# ---------------------------------------------------------------------------
# ÉTAPE 2 — Mapping via tableau éditable
# ---------------------------------------------------------------------------
st.subheader("Étape 2 — Associer les colonnes aux champs Word")

initial_mapping = auto_map(list(source_df.columns))
nb_auto = sum(1 for v in initial_mapping.values() if v)
nb_total = len(source_df.columns)

if nb_auto == nb_total:
    st.success(f"Toutes les colonnes ont été reconnues automatiquement ({nb_auto}/{nb_total}).")
elif nb_auto > 0:
    st.info(f"**{nb_auto}/{nb_total}** colonnes reconnues. Complétez les lignes vides si nécessaire.")
else:
    st.warning("Aucune colonne reconnue automatiquement — associez-les manuellement.")

IGNORE = "— Ne pas importer —"
col_options = [IGNORE] + STANDARD_FIELDS

FIELD_DESC = {
    "Civilite":   "Civilite — M. / Mme / Mlle",
    "Nom":        "Nom — en MAJUSCULES",
    "Prenom":     "Prenom — en Titre",
    "Societe":    "Societe — raison sociale",
    "Adresse1":   "Adresse1 — N° et voie (ligne obligatoire)",
    "Adresse2":   "Adresse2 — BP, lieu-dit, complément",
    "Adresse3":   "Adresse3 — bâtiment, résidence, étage",
    "CodePostal": "CodePostal — 5 chiffres",
    "Ville":      "Ville — en MAJUSCULES",
}
col_options_labeled = [IGNORE] + [FIELD_DESC[f] for f in STANDARD_FIELDS]
label_to_field = {IGNORE: ""} | {FIELD_DESC[f]: f for f in STANDARD_FIELDS}
field_to_label = {f: FIELD_DESC[f] for f in STANDARD_FIELDS}

mapping_df = pd.DataFrame({
    "Colonne source": list(source_df.columns),
    "Exemple de valeur": [sample_value(source_df, c) for c in source_df.columns],
    "Champ de fusion Word": [
        field_to_label.get(initial_mapping.get(c, ""), IGNORE)
        for c in source_df.columns
    ],
})

edited_mapping = st.data_editor(
    mapping_df,
    column_config={
        "Colonne source": st.column_config.TextColumn(disabled=True, width="medium"),
        "Exemple de valeur": st.column_config.TextColumn(disabled=True, width="medium"),
        "Champ de fusion Word": st.column_config.SelectboxColumn(
            options=col_options_labeled,
            required=True,
            width="large",
        ),
    },
    hide_index=True,
    use_container_width=True,
    num_rows="fixed",
)

mapping = {
    row["Colonne source"]: label_to_field[row["Champ de fusion Word"]]
    for _, row in edited_mapping.iterrows()
    if row["Champ de fusion Word"] != IGNORE
}

if not mapping:
    st.warning("Associez au moins une colonne à un champ pour continuer.")
    st.stop()

st.divider()

# ---------------------------------------------------------------------------
# ÉTAPE 3 — Multi-contacts (si détecté)
# ---------------------------------------------------------------------------
multi_contacts = detect_multi_contacts(mapping)
explode = False
if multi_contacts:
    fields_str = ", ".join(
        f"**{f}** ({len(c)} colonnes)" for f, c in multi_contacts.items()
    )
    st.subheader("Étape 3 — Fichier multi-contacts détecté")
    st.warning(
        f"Plusieurs colonnes → même champ : {fields_str}. "
        "Chaque ligne contient plusieurs contacts (ex : Nom1 / Nom2)."
    )
    explode = st.checkbox("Éclater en une ligne par contact", value=False)
    st.divider()

# ---------------------------------------------------------------------------
# ÉTAPE 4 — Options
# ---------------------------------------------------------------------------
step_n = 3 + int(bool(multi_contacts))
st.subheader(f"Étape {step_n} — Options de traitement")

with st.expander("Règles de base", expanded=False):
    b1, b2 = st.columns(2)
    with b1:
        opt_espaces    = st.checkbox("Espaces et caractères invisibles", value=True)
        opt_civilite   = st.checkbox("Civilités (M. / Mme / Mlle)", value=True)
        opt_nom        = st.checkbox("Nom en MAJUSCULES", value=True)
        opt_prenom     = st.checkbox("Prénom en Titre (Jean-Pierre)", value=True)
    with b2:
        opt_codepostal      = st.checkbox("Codes postaux (1000 → 01000)", value=True)
        opt_ville           = st.checkbox("Ville en MAJUSCULES", value=True)
        opt_consolidation   = st.checkbox("Consolider Adresse1/2/3", value=True)
        opt_supprimer_vides = st.checkbox("Supprimer les lignes vides", value=True)

with st.expander("Conformité La Poste — NF Z 10-011", expanded=True):
    st.caption(
        "La norme impose une structure en 6 lignes maximum. "
        "Les deux premières options s'appliquent sans modifier le sens des données."
    )

    lp1, lp2, lp3 = st.columns(3)
    with lp1:
        opt_bp_cs = st.checkbox(
            "**BP / CS / TSA**", value=True,
            help="B.P.123 → BP 123 · CS70001 → CS 70001 · TSA12345 → TSA 12345",
        )
        opt_ponctuation = st.checkbox(
            "**Ponctuation parasite**", value=True,
            help="Supprime virgules, points et parenthèses dans les champs adresse",
        )
    with lp2:
        opt_completude = st.checkbox(
            "**Vérifier la complétude**", value=True,
            help="Signale les adresses sans voie, sans code postal ou sans ville",
        )
        opt_attention = st.checkbox(
            "**À L'ATTENTION DE (B2B)**", value=False,
            help="Société + Contact → insère 'A L'ATTENTION DE M. DUPONT' en Adresse2",
        )
    with lp3:
        opt_abrev = st.checkbox(
            "**Abréviations RNVP**", value=False,
            help="AVENUE → AV · BOULEVARD → BD · IMPASSE → IMP · CHEMIN → CHE…\n"
                 "Active la désaccentuation automatiquement.",
        )
        opt_desacc = st.checkbox(
            "**Désaccentuation OCR**", value=False,
            help="Supprime les accents pour la lecture optique de La Poste : É→E · À→A · Ç→C",
        )

options = {
    "espaces": opt_espaces, "civilite": opt_civilite, "nom": opt_nom,
    "prenom": opt_prenom, "codepostal": opt_codepostal, "ville": opt_ville,
}
laposte_options = {
    "bp_cs": opt_bp_cs,
    "ponctuation_adresse": opt_ponctuation,
    "completude": opt_completude,
    "abreviations_voies": opt_abrev,
    "desaccentuation": opt_desacc or opt_abrev,
}

st.divider()

# ---------------------------------------------------------------------------
# ÉTAPE 5 — Lancement
# ---------------------------------------------------------------------------
step_n2 = step_n + 1
st.subheader(f"Étape {step_n2} — Lancer la mise en conformité")

champs = sorted(set(mapping.values()))
st.markdown(f"**{len(mapping)}** colonne(s) mappée(s) → `{'` · `'.join(champs)}`")

if st.button("Mettre en conformité", type="primary", use_container_width=True):
    with st.spinner("Traitement en cours…"):
        try:
            mapped_rows = []
            for _, row in source_df.iterrows():
                new_row = {f: "" for f in STANDARD_FIELDS}
                for src_col, field in mapping.items():
                    if field in STANDARD_FIELDS and not new_row[field]:
                        new_row[field] = str(row.get(src_col, ""))
                mapped_rows.append(new_row)

            mapped_df = pd.DataFrame(mapped_rows, columns=STANDARD_FIELDS)
            original_mapped = mapped_df.copy()

            if explode and multi_contacts:
                from cleaner.consolidator import explode_multi_contacts
                mapped_df = explode_multi_contacts(mapped_df, multi_contacts, source_df)
                original_mapped = mapped_df.copy()

            mapped_df, coherence_alerts = run_coherence(mapped_df)
            mapped_df, rapport_lignes   = apply_rules(mapped_df, options)

            if opt_attention and "Societe" in mapped_df.columns:
                for idx in mapped_df.index:
                    soc  = str(mapped_df.at[idx, "Societe"]).strip()
                    nom  = str(mapped_df.at[idx, "Nom"]).strip()    if "Nom"    in mapped_df.columns else ""
                    prn  = str(mapped_df.at[idx, "Prenom"]).strip() if "Prenom" in mapped_df.columns else ""
                    civ  = str(mapped_df.at[idx, "Civilite"]).strip() if "Civilite" in mapped_df.columns else ""
                    adr2 = str(mapped_df.at[idx, "Adresse2"]).strip() if "Adresse2" in mapped_df.columns else ""
                    if soc and (nom or prn) and not adr2 and "Adresse2" in mapped_df.columns:
                        mapped_df.at[idx, "Adresse2"] = format_attention(civ, prn, nom)

            mapped_df, laposte_alerts = apply_laposte_rules(mapped_df, laposte_options)

            consolidation_journal = []
            if opt_consolidation:
                mapped_df, consolidation_journal = consolidate_addresses(mapped_df)

            nb_supprimees = 0
            if opt_supprimer_vides:
                mapped_df, nb_supprimees = remove_empty_rows(mapped_df)
                original_mapped = original_mapped.reindex(mapped_df.index)

            doublons    = detect_duplicates(mapped_df)
            nb_exportees = len(mapped_df)

            st.session_state.update({
                "result_df": mapped_df,
                "original_mapped": original_mapped,
                "source_df": source_df.copy(),
                "rapport_lignes": rapport_lignes,
                "doublons": doublons,
                "consolidation_journal": consolidation_journal,
                "coherence_alerts": coherence_alerts,
                "laposte_alerts": laposte_alerts,
                "nb_importees": nb_importees,
                "nb_exportees": nb_exportees,
                "nb_supprimees": nb_supprimees,
                "processed": True,
            })

        except Exception as e:
            st.error(f"Erreur : {e}")
            raise

# ---------------------------------------------------------------------------
# RÉSULTATS
# ---------------------------------------------------------------------------
if not st.session_state.get("processed"):
    st.stop()

result_df             = st.session_state["result_df"]
original_mapped       = st.session_state["original_mapped"]
rapport_lignes        = st.session_state["rapport_lignes"]
doublons              = st.session_state["doublons"]
consolidation_journal = st.session_state["consolidation_journal"]
coherence_alerts      = st.session_state.get("coherence_alerts", [])
laposte_alerts        = st.session_state.get("laposte_alerts", [])
nb_imp  = st.session_state["nb_importees"]
nb_exp  = st.session_state["nb_exportees"]
nb_supp = st.session_state["nb_supprimees"]

st.divider()
st.subheader("Résultats")

m1, m2, m3, m4, m5, m6 = st.columns(6)
m1.metric("Importées",       nb_imp)
m2.metric("Exportées",       nb_exp)
m3.metric("Supprimées",      nb_supp)
m4.metric("Doublons",        len(doublons),                help="Signalés, non supprimés")
m5.metric("Consolidations",  len(consolidation_journal),   help="Lignes d'adresse réorganisées")
m6.metric("Alertes",         len(coherence_alerts) + len(laposte_alerts))

# ---------------------------------------------------------------------------
# TABS
# ---------------------------------------------------------------------------
tab_env, tab_table, tab_alertes = st.tabs([
    "Aperçu enveloppes (La Poste)",
    "Tableau complet",
    "Alertes et anomalies",
])

# ---- Tab 1 : Aperçu enveloppes ----
with tab_env:
    st.markdown(
        "Visualisation des adresses normalisées au format **La Poste NF Z 10-011** "
        "(6 lignes maximum). Comparez les données source avec le rendu final."
    )

    doublon_indices      = {ln - 2 for d in doublons for ln in d["lignes"]}
    consolidated_indices = {e["ligne"] - 2 for e in consolidation_journal}

    n_preview = min(12, len(result_df))
    preview_indices = list(result_df.index[:n_preview])

    for row_start in range(0, len(preview_indices), 3):
        batch = preview_indices[row_start:row_start + 3]
        cols = st.columns(len(batch))
        for col_ui, idx in zip(cols, batch):
            with col_ui:
                row_clean = result_df.loc[idx].to_dict()
                row_orig  = original_mapped.loc[idx].to_dict() if idx in original_mapped.index else {}

                is_doublon      = idx in doublon_indices
                is_consolidated = idx in consolidated_indices

                # Badge statut
                badges = []
                if is_doublon:
                    badges.append('<span style="background:#FFC7CE;padding:2px 6px;border-radius:4px;font-size:10px;">doublon</span>')
                if is_consolidated:
                    badges.append('<span style="background:#FFEB9C;padding:2px 6px;border-radius:4px;font-size:10px;">adresse réorganisée</span>')

                badge_html = " ".join(badges)
                st.markdown(
                    f"<div style='font-size:11px;color:#888;margin-bottom:4px;'>"
                    f"Ligne {idx + 2} {badge_html}</div>",
                    unsafe_allow_html=True,
                )

                # Carte source (données brutes mappées)
                orig_display = {k: v for k, v in row_orig.items() if str(v).strip()}
                st.markdown(source_card_html(orig_display), unsafe_allow_html=True)

                # Flèche
                st.markdown(
                    "<div style='text-align:center;font-size:20px;margin:4px 0;color:#1E6B3C;'>↓</div>",
                    unsafe_allow_html=True,
                )

                # Carte enveloppe normalisée
                env_lines = format_envelope_lines(row_clean)
                st.markdown(envelope_html(env_lines), unsafe_allow_html=True)

    if len(result_df) > 12:
        st.caption(f"Aperçu limité aux 12 premières lignes sur {len(result_df)}.")

# ---- Tab 2 : Tableau ----
with tab_table:
    st.caption("🟥 Rouge = doublon · 🟨 Jaune = adresse réorganisée")

    def highlight_row(row):
        idx = row.name
        if idx in doublon_indices:
            return ["background-color:#FFC7CE"] * len(row)
        if idx in consolidated_indices:
            return ["background-color:#FFEB9C"] * len(row)
        return [""] * len(row)

    try:
        st.dataframe(
            result_df.style.apply(highlight_row, axis=1),
            use_container_width=True, height=500,
        )
    except Exception:
        st.dataframe(result_df, use_container_width=True, height=500)

# ---- Tab 3 : Alertes ----
with tab_alertes:
    if not coherence_alerts and not laposte_alerts and not doublons and not rapport_lignes:
        st.success("Aucune alerte — toutes les adresses sont conformes.")
    else:
        auto_fixed = [a for a in coherence_alerts if a["auto_fixable"]]
        to_review  = [a for a in coherence_alerts if not a["auto_fixable"]]

        if auto_fixed:
            with st.expander(f"✅ {len(auto_fixed)} correction(s) appliquée(s) automatiquement"):
                by_type = defaultdict(list)
                for a in auto_fixed:
                    by_type[a["type"]].append(a)
                for t, items in by_type.items():
                    st.markdown(f"**{t}** ({len(items)} ligne(s))")
                    for a in items:
                        st.markdown(f"- Ligne {a['ligne']} : {a['message']} → *{a['suggestion']}*")

        if to_review:
            with st.expander(f"⚠️ {len(to_review)} point(s) à vérifier manuellement"):
                by_type = defaultdict(list)
                for a in to_review:
                    by_type[a["type"]].append(a)
                for t, items in by_type.items():
                    st.markdown(f"**{t}** ({len(items)} ligne(s))")
                    for a in items:
                        st.markdown(f"- Ligne {a['ligne']} : {a['message']} → *{a['suggestion']}*")

        if laposte_alerts:
            with st.expander(f"📮 {len(laposte_alerts)} alerte(s) La Poste (NF Z 10-011)"):
                by_type = defaultdict(list)
                for a in laposte_alerts:
                    by_type[a["type"]].append(a)
                for t, items in by_type.items():
                    st.markdown(f"**{t}** ({len(items)} ligne(s))")
                    for a in items[:20]:
                        st.markdown(f"- Ligne {a['ligne']} : {a['message']} → *{a['suggestion']}*")
                    if len(items) > 20:
                        st.caption(f"… et {len(items) - 20} autres.")

        if doublons:
            with st.expander(f"⚠️ {len(doublons)} doublon(s) — non supprimés"):
                for d in doublons:
                    lignes_str = ", ".join(str(l) for l in d["lignes"])
                    st.write(f"• **{d['nom']}** / {d['codepostal']} → lignes {lignes_str}")

        if rapport_lignes:
            with st.expander(f"⚠️ {len(rapport_lignes)} anomalie(s) de données"):
                for e in rapport_lignes:
                    fn = st.error if e["type"] == "error" else st.warning
                    fn(f"Ligne {e['ligne']} [{e['colonne']}] : {e['message']}")

# ---------------------------------------------------------------------------
# Téléchargement
# ---------------------------------------------------------------------------
st.divider()
st.subheader("Téléchargement")

dl1, dl2 = st.columns(2)
with dl1:
    try:
        excel_bytes = export_excel(
            result_df, original_mapped, rapport_lignes, doublons, consolidation_journal,
        )
        st.download_button(
            "Télécharger le fichier Excel nettoyé",
            data=excel_bytes,
            file_name="adresses_normalisees.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
            type="primary",
        )
    except Exception as e:
        st.error(f"Erreur génération Excel : {e}")

with dl2:
    rapport_txt = export_rapport(
        nb_imp, nb_exp, nb_supp, rapport_lignes, doublons, consolidation_journal,
    )
    st.download_button(
        "Télécharger le rapport de traitement",
        data=rapport_txt.encode("utf-8"),
        file_name="rapport_normadress.txt",
        mime="text/plain",
        use_container_width=True,
    )
