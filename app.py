"""NormAdress — Application Streamlit de mise en conformité d'adresses."""
import json
from datetime import datetime
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
from cleaner.laposte import apply_laposte_rules, format_attention, format_envelope_lines
from cleaner.bat import generate_bat
from cleaner.exporter import export_excel, export_rapport

_favicon = Image.open(Path(__file__).parent / "favicon.png")
st.set_page_config(page_title="NormAdress", page_icon=_favicon, layout="wide")

# ---------------------------------------------------------------------------
# Helpers visuels
# ---------------------------------------------------------------------------

def sample_value(df, col):
    vals = df[col].dropna()
    vals = vals[vals.astype(str).str.strip() != ""]
    return str(vals.iloc[0]) if len(vals) > 0 else "—"


def envelope_html(lines: list[tuple[str, str]], compact: bool = False) -> str:
    """Carte enveloppe La Poste stylée."""
    rows_html = ""
    for label, content in lines:
        is_cp = label == "L6"
        weight = "font-weight:700;" if is_cp else ""
        color  = "color:#1E6B3C;" if is_cp else "color:#1a1a1a;"
        lbl_style = (
            "display:inline-block;width:22px;font-size:9px;"
            "color:#bbb;vertical-align:middle;margin-right:4px;"
        )
        rows_html += (
            f"<div style='line-height:1.75;{weight}{color}'>"
            f"<span style='{lbl_style}'>{label}</span>{content}</div>"
        )

    missing = not any(l == "L4" for l, _ in lines)
    warning = (
        "<div style='margin-top:6px;font-size:10px;color:#c00;font-family:sans-serif;'>"
        "⚠ Ligne de voie (Adresse1) manquante</div>"
        if missing and lines else ""
    )

    pad = "10px 12px" if compact else "14px 16px"
    min_h = "100px" if compact else "130px"

    return f"""
<div style="
    border:2px solid #1E6B3C;border-radius:8px;padding:{pad};
    font-family:'Courier New',monospace;font-size:13px;
    background:#fff;min-height:{min_h};
    box-shadow:2px 2px 8px rgba(0,0,0,.07);
">
    <div style="font-size:9px;color:#bbb;letter-spacing:1px;margin-bottom:6px;font-family:sans-serif;">
        LA POSTE — NF Z 10-011
    </div>
    {rows_html}
    {warning}
</div>"""


def source_card_html(row_orig: dict) -> str:
    """Carte données source (avant traitement)."""
    rows_html = ""
    for k, v in row_orig.items():
        v_str = str(v).strip()
        if not v_str:
            continue
        rows_html += (
            f"<div style='line-height:1.7;color:#555;font-size:12.5px;'>"
            f"<span style='font-size:9px;color:#aaa;display:inline-block;"
            f"width:80px;font-family:sans-serif;'>{k}</span>{v_str}</div>"
        )
    if not rows_html:
        rows_html = "<div style='color:#ccc;font-size:11px;'>— vide —</div>"
    return f"""
<div style="
    border:1px solid #ddd;border-radius:8px;padding:14px 16px;
    font-family:'Courier New',monospace;
    background:#fafafa;min-height:130px;
">
    <div style="font-size:9px;color:#bbb;letter-spacing:1px;margin-bottom:6px;font-family:sans-serif;">
        DONNÉES SOURCE
    </div>
    {rows_html}
</div>"""


# ---------------------------------------------------------------------------
# Sidebar — Gestion des travaux
# ---------------------------------------------------------------------------
with st.sidebar:
    st.image("logo.svg", width=120) if Path("logo.svg").exists() else None
    st.markdown("## Travaux")
    st.caption("Sauvegardez vos paramètres pour reprendre ou modifier ce travail plus tard.")

    # Chargement d'un travail existant
    work_file = st.file_uploader("Charger un travail (.json)", type=["json"], key="work_loader")
    if work_file:
        try:
            loaded = json.loads(work_file.read().decode("utf-8"))
            st.session_state["loaded_work"] = loaded
            st.success(f"Travail chargé : **{loaded.get('nom', '—')}**")
            st.caption(f"Créé le {loaded.get('date', '—')}")
            if loaded.get("notes"):
                st.info(loaded["notes"])
        except Exception as e:
            st.error(f"Fichier invalide : {e}")

    st.divider()

    # Sauvegarde du travail courant
    st.markdown("**Enregistrer le travail courant**")
    work_name = st.text_input("Nom du travail / client", placeholder="Ex : Mairie de Lyon — Mai 2026")
    work_notes = st.text_area("Notes", placeholder="Ex : En attente validation BP…", height=80)

    mapping_to_save = st.session_state.get("last_mapping", {})
    options_to_save = st.session_state.get("last_options", {})
    laposte_to_save = st.session_state.get("last_laposte_options", {})

    if mapping_to_save:
        work_data = {
            "version": "1.1",
            "nom": work_name or "Travail sans nom",
            "date": datetime.now().strftime("%d/%m/%Y %H:%M"),
            "notes": work_notes,
            "mapping": mapping_to_save,
            "options": options_to_save,
            "laposte": laposte_to_save,
        }
        st.download_button(
            "💾 Enregistrer le travail",
            data=json.dumps(work_data, ensure_ascii=False, indent=2),
            file_name=f"travail_{datetime.now().strftime('%Y%m%d_%H%M')}.json",
            mime="application/json",
            use_container_width=True,
        )
    else:
        st.button("💾 Enregistrer le travail", disabled=True, use_container_width=True,
                  help="Lancez d'abord un traitement pour activer la sauvegarde.")

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

# Récupérer le travail chargé depuis la sidebar
loaded_work     = st.session_state.get("loaded_work", {})
loaded_mapping  = loaded_work.get("mapping", {})
loaded_options  = loaded_work.get("options", {})
loaded_laposte  = loaded_work.get("laposte", {})

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
# ÉTAPE 2 — Mapping
# ---------------------------------------------------------------------------
st.subheader("Étape 2 — Associer les colonnes aux champs Word")

initial_mapping = auto_map(list(source_df.columns))
nb_auto = sum(1 for v in initial_mapping.values() if v)
nb_total = len(source_df.columns)

if nb_auto == nb_total:
    st.success(f"Toutes les colonnes reconnues automatiquement ({nb_auto}/{nb_total}).")
elif nb_auto > 0:
    st.info(f"**{nb_auto}/{nb_total}** colonnes reconnues. Complétez les lignes vides.")
else:
    st.warning("Aucune colonne reconnue — associez-les manuellement.")

IGNORE = "— Ne pas importer —"

FIELD_DESC = {
    "Civilite":   "Civilite — M. / Mme / Mlle",
    "Nom":        "Nom — en MAJUSCULES",
    "Prenom":     "Prenom — en Titre",
    "Societe":    "Societe — raison sociale",
    "Adresse1":   "Adresse1 — N° et voie (L4, obligatoire)",
    "Adresse2":   "Adresse2 — BP, lieu-dit, complément (L5)",
    "Adresse3":   "Adresse3 — bâtiment, résidence, étage (L3)",
    "CodePostal": "CodePostal — 5 chiffres",
    "Ville":      "Ville — en MAJUSCULES",
}
col_options_labeled = [IGNORE] + [FIELD_DESC[f] for f in STANDARD_FIELDS]
label_to_field = {IGNORE: ""} | {FIELD_DESC[f]: f for f in STANDARD_FIELDS}
field_to_label = {f: FIELD_DESC[f] for f in STANDARD_FIELDS}

def resolve_default(col):
    # Priorité : travail chargé > détection auto
    field = loaded_mapping.get(col) or initial_mapping.get(col, "")
    return field_to_label.get(field, IGNORE)

mapping_df = pd.DataFrame({
    "Colonne source":    list(source_df.columns),
    "Exemple de valeur": [sample_value(source_df, c) for c in source_df.columns],
    "Champ de fusion Word": [resolve_default(c) for c in source_df.columns],
})

edited_mapping = st.data_editor(
    mapping_df,
    column_config={
        "Colonne source":    st.column_config.TextColumn(disabled=True, width="medium"),
        "Exemple de valeur": st.column_config.TextColumn(disabled=True, width="medium"),
        "Champ de fusion Word": st.column_config.SelectboxColumn(
            options=col_options_labeled, required=True, width="large",
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
# ÉTAPE 3 — Multi-contacts
# ---------------------------------------------------------------------------
multi_contacts = detect_multi_contacts(mapping)
explode = False
if multi_contacts:
    fields_str = ", ".join(f"**{f}** ({len(c)} colonnes)" for f, c in multi_contacts.items())
    st.subheader("Étape 3 — Fichier multi-contacts détecté")
    st.warning(f"Plusieurs colonnes → même champ : {fields_str}.")
    explode = st.checkbox("Éclater en une ligne par contact", value=False)
    st.divider()

# ---------------------------------------------------------------------------
# ÉTAPE 4 — Options
# ---------------------------------------------------------------------------
step_n = 3 + int(bool(multi_contacts))
st.subheader(f"Étape {step_n} — Options de traitement")

def _opt(key, label, default, help_txt=""):
    val = loaded_options.get(key, default)
    return st.checkbox(label, value=val, help=help_txt)

def _lp(key, label, default, help_txt=""):
    val = loaded_laposte.get(key, default)
    return st.checkbox(label, value=val, help=help_txt)

with st.expander("Règles de base", expanded=False):
    b1, b2 = st.columns(2)
    with b1:
        opt_espaces    = _opt("espaces",    "Espaces et caractères invisibles", True)
        opt_civilite   = _opt("civilite",   "Civilités (M. / Mme / Mlle)", True)
        opt_nom        = _opt("nom",        "Nom en MAJUSCULES", True)
        opt_prenom     = _opt("prenom",     "Prénom en Titre (Jean-Pierre)", True)
    with b2:
        opt_codepostal      = _opt("codepostal",      "Codes postaux (1000 → 01000)", True)
        opt_ville           = _opt("ville",           "Ville en MAJUSCULES", True)
        opt_consolidation   = _opt("consolidation",   "Consolider Adresse1/2/3", True)
        opt_supprimer_vides = _opt("supprimer_vides", "Supprimer les lignes vides", True)

with st.expander("Conformité La Poste — NF Z 10-011", expanded=True):
    st.caption("Structure normalisée en 6 lignes : L1 Identité · L2 Complément · L3 Bâtiment · L4 Voie · L5 BP/lieu-dit · L6 CP Ville")
    lp1, lp2, lp3 = st.columns(3)
    with lp1:
        opt_bp_cs       = _lp("bp_cs",       "**BP / CS / TSA**", True, "B.P.123 → BP 123")
        opt_ponctuation = _lp("ponctuation_adresse", "**Ponctuation parasite**", True, "Supprime virgules, parenthèses dans les adresses")
    with lp2:
        opt_completude  = _lp("completude",   "**Vérifier la complétude**", True, "Signale les adresses sans voie, CP ou ville")
        opt_attention   = _lp("attention",    "**À L'ATTENTION DE (B2B)**", False, "Société + Contact → insère la mention en Adresse2")
    with lp3:
        opt_abrev       = _lp("abreviations_voies", "**Abréviations RNVP**", False, "AVENUE→AV · BOULEVARD→BD · IMPASSE→IMP")
        opt_desacc      = _lp("desaccentuation",    "**Désaccentuation OCR**", False, "É→E · À→A · Ç→C pour lecture optique")

options = {
    "espaces": opt_espaces, "civilite": opt_civilite, "nom": opt_nom,
    "prenom": opt_prenom, "codepostal": opt_codepostal, "ville": opt_ville,
}
laposte_options = {
    "bp_cs": opt_bp_cs, "ponctuation_adresse": opt_ponctuation,
    "completude": opt_completude, "abreviations_voies": opt_abrev,
    "desaccentuation": opt_desacc or opt_abrev, "attention": opt_attention,
}

st.divider()

# ---------------------------------------------------------------------------
# ÉTAPE 5 — Lancement
# ---------------------------------------------------------------------------
step_n2 = step_n + 1
st.subheader(f"Étape {step_n2} — Lancer la mise en conformité")

champs = sorted(set(mapping.values()))
st.markdown(f"**{len(mapping)}** colonne(s) → `{'` · `'.join(champs)}`")

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

            # Mémoriser pour sauvegarde travail
            st.session_state["last_mapping"]         = mapping
            st.session_state["last_options"]         = options
            st.session_state["last_laposte_options"] = laposte_options

            st.session_state.update({
                "result_df": mapped_df,
                "original_mapped": original_mapped,
                "rapport_lignes": rapport_lignes,
                "doublons": doublons,
                "consolidation_journal": consolidation_journal,
                "coherence_alerts": coherence_alerts,
                "laposte_alerts": laposte_alerts,
                "nb_importees": nb_importees,
                "nb_exportees": nb_exportees,
                "nb_supprimees": nb_supprimees,
                "processed": True,
                "envelope_idx": 0,
                "work_name": work_name if "work_name" in dir() else "",
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

doublon_indices      = {ln - 2 for d in doublons for ln in d["lignes"]}
consolidated_indices = {e["ligne"] - 2 for e in consolidation_journal}

st.divider()
st.subheader("Résultats")

m1, m2, m3, m4, m5, m6 = st.columns(6)
m1.metric("Importées",      nb_imp)
m2.metric("Exportées",      nb_exp)
m3.metric("Supprimées",     nb_supp)
m4.metric("Doublons",       len(doublons),             help="Signalés, non supprimés")
m5.metric("Consolidations", len(consolidation_journal), help="Adresses réorganisées")
m6.metric("Alertes",        len(coherence_alerts) + len(laposte_alerts))

# ---------------------------------------------------------------------------
# TABS
# ---------------------------------------------------------------------------
tab_env, tab_table, tab_alertes = st.tabs([
    "Aperçu enveloppes",
    "Tableau complet",
    "Alertes et anomalies",
])

# ---- Tab 1 : Aperçu enveloppes avec navigation ----
with tab_env:
    total = len(result_df)
    idx_list = list(result_df.index)

    # Initialisation de l'index
    if "envelope_idx" not in st.session_state:
        st.session_state["envelope_idx"] = 0
    if st.session_state["envelope_idx"] >= total:
        st.session_state["envelope_idx"] = 0

    current_pos = st.session_state["envelope_idx"]  # position 0-based
    current_idx = idx_list[current_pos]              # index DataFrame

    # Barre de navigation
    nav1, nav2, nav3, nav4, nav5 = st.columns([1, 1, 3, 1, 1])
    with nav1:
        if st.button("⏮ Premier", use_container_width=True, disabled=current_pos == 0):
            st.session_state["envelope_idx"] = 0
            st.rerun()
    with nav2:
        if st.button("◀ Précédent", use_container_width=True, disabled=current_pos == 0):
            st.session_state["envelope_idx"] -= 1
            st.rerun()
    with nav3:
        # Saut direct à un numéro de pli
        jump = st.number_input(
            f"Pli (1 – {total})", min_value=1, max_value=total,
            value=current_pos + 1, step=1, label_visibility="collapsed",
        )
        if jump - 1 != current_pos:
            st.session_state["envelope_idx"] = jump - 1
            st.rerun()
        st.markdown(
            f"<div style='text-align:center;color:#666;font-size:13px;margin-top:2px;'>"
            f"Pli <b>{current_pos + 1}</b> sur <b>{total}</b></div>",
            unsafe_allow_html=True,
        )
    with nav4:
        if st.button("Suivant ▶", use_container_width=True, disabled=current_pos >= total - 1):
            st.session_state["envelope_idx"] += 1
            st.rerun()
    with nav5:
        if st.button("Dernier ⏭", use_container_width=True, disabled=current_pos >= total - 1):
            st.session_state["envelope_idx"] = total - 1
            st.rerun()

    st.markdown("---")

    # Badges statut
    badges = []
    if current_idx in doublon_indices:
        badges.append("🔴 Doublon détecté")
    if current_idx in consolidated_indices:
        badges.append("🟡 Adresse réorganisée")
    if badges:
        st.warning("  ·  ".join(badges))

    # Affichage côte à côte : SOURCE | ENVELOPPE
    col_src, col_arr, col_env = st.columns([5, 1, 5])

    with col_src:
        st.markdown("**Données source (avant traitement)**")
        row_orig = original_mapped.loc[current_idx].to_dict() if current_idx in original_mapped.index else {}
        orig_display = {k: v for k, v in row_orig.items() if str(v).strip()}
        st.markdown(source_card_html(orig_display), unsafe_allow_html=True)

    with col_arr:
        st.markdown(
            "<div style='text-align:center;font-size:28px;padding-top:60px;color:#1E6B3C;'>→</div>",
            unsafe_allow_html=True,
        )

    with col_env:
        st.markdown("**Adresse normalisée — Format La Poste**")
        row_clean = result_df.loc[current_idx].to_dict()
        env_lines = format_envelope_lines(row_clean)
        st.markdown(envelope_html(env_lines), unsafe_allow_html=True)

    # Détail des champs normalisés
    with st.expander("Voir tous les champs normalisés"):
        row_df = pd.DataFrame([result_df.loc[current_idx]])
        st.dataframe(row_df, use_container_width=True, hide_index=True)

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
            with st.expander(f"✅ {len(auto_fixed)} correction(s) automatique(s)"):
                by_type = defaultdict(list)
                for a in auto_fixed: by_type[a["type"]].append(a)
                for t, items in by_type.items():
                    st.markdown(f"**{t}** ({len(items)} ligne(s))")
                    for a in items:
                        st.markdown(f"- Ligne {a['ligne']} : {a['message']} → *{a['suggestion']}*")

        if to_review:
            with st.expander(f"⚠️ {len(to_review)} point(s) à vérifier manuellement"):
                by_type = defaultdict(list)
                for a in to_review: by_type[a["type"]].append(a)
                for t, items in by_type.items():
                    st.markdown(f"**{t}** ({len(items)} ligne(s))")
                    for a in items:
                        st.markdown(f"- Ligne {a['ligne']} : {a['message']} → *{a['suggestion']}*")

        if laposte_alerts:
            with st.expander(f"📮 {len(laposte_alerts)} alerte(s) La Poste"):
                by_type = defaultdict(list)
                for a in laposte_alerts: by_type[a["type"]].append(a)
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

dl1, dl2, dl3 = st.columns(3)

with dl1:
    try:
        excel_bytes = export_excel(
            result_df, original_mapped, rapport_lignes, doublons, consolidation_journal,
        )
        st.download_button(
            "📥 Fichier Excel nettoyé",
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
        "📄 Rapport de traitement",
        data=rapport_txt.encode("utf-8"),
        file_name="rapport_normadress.txt",
        mime="text/plain",
        use_container_width=True,
    )

with dl3:
    try:
        saved_work_name = st.session_state.get("work_name", "") or "NormAdress"
        bat_html = generate_bat(
            result_df,
            nom_travail=saved_work_name,
            doublons=doublons,
            consolidation_journal=consolidation_journal,
        )
        st.download_button(
            "🖨️ BAT — Bon À Tirer (HTML)",
            data=bat_html.encode("utf-8"),
            file_name=f"BAT_{datetime.now().strftime('%Y%m%d_%H%M')}.html",
            mime="text/html",
            use_container_width=True,
            help="Ouvrez dans un navigateur → Ctrl+P pour imprimer ou enregistrer en PDF",
        )
    except Exception as e:
        st.error(f"Erreur génération BAT : {e}")
