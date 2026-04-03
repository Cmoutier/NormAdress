"""NormAdress — Application Streamlit de mise en conformité d'adresses."""
import io
from pathlib import Path
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
st.set_page_config(
    page_title="NormAdress",
    page_icon=_favicon,
    layout="wide",
)

# ---------------------------------------------------------------------------
# En-tête
# ---------------------------------------------------------------------------
col_logo, col_title = st.columns([1, 10])
with col_logo:
    try:
        st.image("logo.svg", width=80)
    except Exception:
        pass
with col_title:
    st.title("NormAdress")
    st.caption("Mise en conformité de fichiers d'adresses pour publipostage Word")

st.divider()

# ---------------------------------------------------------------------------
# ÉTAPE 1 — Import du fichier
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

# Sélection feuille
if len(file_data["sheets"]) > 1:
    sheet_name = st.selectbox(
        "Ce fichier contient plusieurs feuilles — laquelle traiter ?",
        file_data["sheets"],
    )
else:
    sheet_name = file_data["sheets"][0]

source_df = file_data["dataframes"][sheet_name].copy()
nb_importees = len(source_df)

c1, c2 = st.columns(2)
c1.success(f"**{nb_importees}** lignes importées — **{len(source_df.columns)}** colonnes détectées")
if nb_importees > 50_000:
    c2.warning("Fichier volumineux (>50 000 lignes) — le traitement peut être lent.")

with st.expander("Aperçu des premières lignes du fichier source"):
    st.dataframe(source_df.head(5), use_container_width=True)

st.divider()

# ---------------------------------------------------------------------------
# ÉTAPE 2 — Correspondance des colonnes
# ---------------------------------------------------------------------------
st.subheader("Étape 2 — Associer les colonnes aux champs de publipostage")

initial_mapping = auto_map(list(source_df.columns))
nb_auto = sum(1 for v in initial_mapping.values() if v)
nb_total = len(source_df.columns)

if nb_auto == nb_total:
    st.success(f"Toutes les colonnes ont été reconnues automatiquement ({nb_auto}/{nb_total}).")
elif nb_auto > 0:
    st.info(
        f"**{nb_auto}/{nb_total}** colonnes reconnues automatiquement. "
        "Vérifiez et complétez les colonnes non reconnues ci-dessous."
    )
else:
    st.warning(
        "Aucune colonne n'a été reconnue automatiquement. "
        "Associez manuellement chaque colonne à son champ de publipostage."
    )

st.caption(
    "**Champ cible** = nom du champ de fusion dans vos courriers Word. "
    "Choisissez **— Ne pas importer —** pour ignorer une colonne."
)

# Récupérer un exemple de valeur pour chaque colonne
def sample_value(col):
    vals = source_df[col].dropna()
    vals = vals[vals.astype(str).str.strip() != ""]
    return str(vals.iloc[0]) if len(vals) > 0 else "—"

options_list = ["— Ne pas importer —"] + STANDARD_FIELDS

FIELD_LABELS = {
    "Civilite":   "Civilite  — M. / Mme / Mlle",
    "Nom":        "Nom  — en MAJUSCULES",
    "Prenom":     "Prenom  — en Titre",
    "Societe":    "Societe  — raison sociale",
    "Adresse1":   "Adresse1  — ligne principale",
    "Adresse2":   "Adresse2  — complément",
    "Adresse3":   "Adresse3  — bâtiment / résidence",
    "CodePostal": "CodePostal  — 5 chiffres",
    "Ville":      "Ville  — en MAJUSCULES",
}
labeled_options = ["— Ne pas importer —"] + [FIELD_LABELS[f] for f in STANDARD_FIELDS]
field_from_label = {"— Ne pas importer —": ""} | {FIELD_LABELS[f]: f for f in STANDARD_FIELDS}

mapping = {}

# Séparation reconnues / non reconnues
auto_cols = [c for c in source_df.columns if initial_mapping.get(c)]
manual_cols = [c for c in source_df.columns if not initial_mapping.get(c)]

def render_mapping_row(src_col, default_field, key_prefix):
    col_a, col_b, col_c = st.columns([3, 1, 3])
    with col_a:
        if default_field:
            st.markdown(f"**`{src_col}`**  ✅")
        else:
            st.markdown(f"**`{src_col}`**  ❓")
        st.caption(f"ex : *{sample_value(src_col)}*")
    with col_b:
        st.markdown("<div style='text-align:center;padding-top:18px;font-size:20px'>→</div>", unsafe_allow_html=True)
    with col_c:
        default_label = FIELD_LABELS.get(default_field, "— Ne pas importer —")
        default_idx = labeled_options.index(default_label) if default_label in labeled_options else 0
        chosen_label = st.selectbox(
            "Champ cible",
            labeled_options,
            index=default_idx,
            key=f"{key_prefix}_{src_col}",
            label_visibility="collapsed",
        )
        return field_from_label[chosen_label]

if auto_cols:
    with st.expander(f"Colonnes reconnues automatiquement ({len(auto_cols)})", expanded=True):
        for src_col in auto_cols:
            chosen = render_mapping_row(src_col, initial_mapping[src_col], "map")
            if chosen:
                mapping[src_col] = chosen
            st.markdown("---")

if manual_cols:
    with st.expander(
        f"Colonnes non reconnues — à associer manuellement ({len(manual_cols)})",
        expanded=True,
    ):
        st.caption("Ces colonnes n'ont pas été identifiées automatiquement. Associez-les au bon champ ou laissez **— Ne pas importer —** pour les ignorer.")
        for src_col in manual_cols:
            chosen = render_mapping_row(src_col, "", "map")
            if chosen:
                mapping[src_col] = chosen
            st.markdown("---")

# Vérification : au moins un champ mappé
if not mapping:
    st.warning("Aucune colonne associée — associez au moins un champ pour continuer.")
    st.stop()

st.divider()

# ---------------------------------------------------------------------------
# ÉTAPE 3 — Multi-contacts (si détecté)
# ---------------------------------------------------------------------------
multi_contacts = detect_multi_contacts(mapping)
explode = False
if multi_contacts:
    fields_str = ", ".join(
        f"**{field}** ({len(cols)} colonnes)" for field, cols in multi_contacts.items()
    )
    st.subheader("Étape 3 — Fichier multi-contacts détecté")
    st.warning(
        f"Plusieurs colonnes sont associées au même champ : {fields_str}. "
        "Cela signifie que chaque ligne contient plusieurs contacts (ex : Nom1 / Nom2). "
        "Cochez la case ci-dessous pour créer une ligne par contact."
    )
    explode = st.checkbox("Éclater en une ligne par contact", value=False)
    st.divider()

# ---------------------------------------------------------------------------
# ÉTAPE 4 — Options de nettoyage
# ---------------------------------------------------------------------------
st.subheader("Étape 3 — Options de nettoyage" if not multi_contacts else "Étape 4 — Options de nettoyage")

with st.expander("Règles de base (toutes activées par défaut)", expanded=False):
    col1, col2 = st.columns(2)
    with col1:
        opt_espaces    = st.checkbox("Supprimer les espaces et caractères invisibles", value=True)
        opt_civilite   = st.checkbox("Normaliser les civilités (M. / Mme / Mlle)", value=True)
        opt_nom        = st.checkbox("Mettre le Nom en MAJUSCULES", value=True)
        opt_prenom     = st.checkbox("Mettre le Prénom en Titre (Jean-Pierre)", value=True)
    with col2:
        opt_codepostal      = st.checkbox("Corriger les codes postaux (ex: 1000 → 01000)", value=True)
        opt_ville           = st.checkbox("Mettre la Ville en MAJUSCULES", value=True)
        opt_consolidation   = st.checkbox("Consolider les lignes d'adresse (Adresse1 toujours remplie en premier)", value=True)
        opt_supprimer_vides = st.checkbox("Supprimer les lignes entièrement vides", value=True)

st.markdown("**Conformité La Poste — Norme NF Z 10-011 (RNVP)**")
st.caption(
    "Ces règles alignent vos adresses sur les exigences de La Poste pour garantir l'acheminement. "
    "Les deux premières sont activées par défaut car elles ne changent pas le sens des données."
)
with st.expander("Règles La Poste", expanded=True):
    lp1, lp2 = st.columns(2)
    with lp1:
        opt_bp_cs = st.checkbox(
            "Normaliser BP / CS / TSA",
            value=True,
            help="Ex : 'B.P.123' → 'BP 123', 'CS70001' → 'CS 70001'",
        )
        opt_ponctuation = st.checkbox(
            "Supprimer la ponctuation parasite dans les adresses",
            value=True,
            help="Virgules, points, parenthèses dans les champs Adresse",
        )
        opt_completude = st.checkbox(
            "Vérifier la complétude (norme NF Z 10-011)",
            value=True,
            help="Signale les adresses sans Numéro+Voie, CodePostal ou Ville",
        )
    with lp2:
        opt_abrev = st.checkbox(
            "Abréviations officielles des types de voie (RNVP)",
            value=False,
            help="Ex : 'AVENUE' → 'AV', 'BOULEVARD' → 'BD', 'IMPASSE' → 'IMP'\n"
                 "⚠️ Active automatiquement la désaccentuation",
        )
        opt_desacc = st.checkbox(
            "Désaccentuation (OCR La Poste)",
            value=False,
            help="Supprime les accents pour la lecture optique : É→E, À→A, Ç→C\n"
                 "Recommandé pour les envois en masse",
        )
        opt_attention = st.checkbox(
            "Générer 'À L'ATTENTION DE' pour les B2B",
            value=False,
            help="Quand Société + Contact : insère 'A L'ATTENTION DE M. DUPONT' en Adresse2",
        )

options = {
    "espaces":    opt_espaces,
    "civilite":   opt_civilite,
    "nom":        opt_nom,
    "prenom":     opt_prenom,
    "codepostal": opt_codepostal,
    "ville":      opt_ville,
}

laposte_options = {
    "bp_cs":              opt_bp_cs,
    "ponctuation_adresse": opt_ponctuation,
    "completude":         opt_completude,
    "abreviations_voies": opt_abrev,
    "desaccentuation":    opt_desacc or opt_abrev,  # abréviations implique désaccentuation
}

st.divider()

# ---------------------------------------------------------------------------
# ÉTAPE 5 — Lancement
# ---------------------------------------------------------------------------
st.subheader("Étape 4 — Lancer la mise en conformité" if not multi_contacts else "Étape 5 — Lancer la mise en conformité")

champs_mappes = list(set(mapping.values()))
st.markdown(
    "**Récapitulatif :** "
    f"{len(mapping)} colonne(s) associée(s) → champs : {', '.join(f'`{c}`' for c in champs_mappes)}"
)

run = st.button("Mettre en conformité", type="primary", use_container_width=True)

if run:
    with st.spinner("Traitement en cours…"):
        try:
            # Construire le DataFrame mappé
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

            # Cohérence inter-champs (avant nettoyage)
            mapped_df, coherence_alerts = run_coherence(mapped_df)

            mapped_df, rapport_lignes = apply_rules(mapped_df, options)

            # Mention "À L'ATTENTION DE" pour les B2B
            if opt_attention and "Societe" in mapped_df.columns:
                for idx in mapped_df.index:
                    soc = str(mapped_df.at[idx, "Societe"]).strip()
                    nom = str(mapped_df.at[idx, "Nom"]).strip() if "Nom" in mapped_df.columns else ""
                    prenom = str(mapped_df.at[idx, "Prenom"]).strip() if "Prenom" in mapped_df.columns else ""
                    civ = str(mapped_df.at[idx, "Civilite"]).strip() if "Civilite" in mapped_df.columns else ""
                    if soc and (nom or prenom):
                        adr2 = str(mapped_df.at[idx, "Adresse2"]).strip() if "Adresse2" in mapped_df.columns else ""
                        if not adr2 and "Adresse2" in mapped_df.columns:
                            mapped_df.at[idx, "Adresse2"] = format_attention(civ, prenom, nom)

            # Règles La Poste (RNVP)
            mapped_df, laposte_alerts = apply_laposte_rules(mapped_df, laposte_options)

            consolidation_journal = []
            if opt_consolidation:
                mapped_df, consolidation_journal = consolidate_addresses(mapped_df)

            nb_supprimees = 0
            if opt_supprimer_vides:
                mapped_df, nb_supprimees = remove_empty_rows(mapped_df)
                original_mapped = original_mapped.reindex(mapped_df.index)

            doublons = detect_duplicates(mapped_df)
            nb_exportees = len(mapped_df)

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
            })

        except Exception as e:
            st.error(f"Erreur pendant le traitement : {e}")
            raise

# ---------------------------------------------------------------------------
# RÉSULTATS
# ---------------------------------------------------------------------------
if st.session_state.get("processed"):
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
    m1.metric("Importées",      nb_imp)
    m2.metric("Exportées",      nb_exp)
    m3.metric("Supprimées",     nb_supp)
    m4.metric("Doublons",       len(doublons),                help="Signalés mais non supprimés")
    m5.metric("Consolidations", len(consolidation_journal),   help="Lignes d'adresse réorganisées")
    m6.metric("Alertes cohérence", len(coherence_alerts) + len(laposte_alerts), help="Problèmes inter-champs et conformité La Poste")

    # --- Alertes de cohérence groupées par type ---
    if coherence_alerts:
        from collections import defaultdict
        by_type = defaultdict(list)
        for a in coherence_alerts:
            by_type[a["type"]].append(a)

        auto_fixed = [a for a in coherence_alerts if a["auto_fixable"]]
        to_review  = [a for a in coherence_alerts if not a["auto_fixable"]]

        if auto_fixed:
            with st.expander(f"✅ {len(auto_fixed)} correction(s) appliquée(s) automatiquement"):
                for t, items in by_type.items():
                    if not items[0]["auto_fixable"]:
                        continue
                    st.markdown(f"**{t}** ({len(items)} ligne(s))")
                    for a in items:
                        st.markdown(f"  - Ligne {a['ligne']} : {a['message']}  \n    → *{a['suggestion']}*")

        if to_review:
            with st.expander(f"⚠️ {len(to_review)} point(s) à vérifier manuellement"):
                for t, items in by_type.items():
                    if items[0]["auto_fixable"]:
                        continue
                    st.markdown(f"**{t}** ({len(items)} ligne(s))")
                    for a in items:
                        st.markdown(f"  - Ligne {a['ligne']} : {a['message']}  \n    → *{a['suggestion']}*")

    # Alertes La Poste
    if laposte_alerts:
        from collections import defaultdict as _dd
        lp_by_type = _dd(list)
        for a in laposte_alerts:
            lp_by_type[a["type"]].append(a)
        with st.expander(f"📮 {len(laposte_alerts)} alerte(s) de conformité La Poste (NF Z 10-011)"):
            for t, items in lp_by_type.items():
                st.markdown(f"**{t}** ({len(items)} ligne(s))")
                for a in items[:20]:  # limiter l'affichage
                    st.markdown(f"  - Ligne {a['ligne']} : {a['message']}  \n    → *{a['suggestion']}*")
                if len(items) > 20:
                    st.caption(f"… et {len(items) - 20} autres lignes du même type.")

    # Doublons
    if doublons:
        with st.expander(f"⚠️ {len(doublons)} doublon(s) détecté(s) — non supprimés, à vérifier"):
            for d in doublons:
                lignes_str = ", ".join(str(l) for l in d["lignes"])
                st.write(f"• **{d['nom']}** / {d['codepostal']} → lignes {lignes_str}")

    # Anomalies de nettoyage
    if rapport_lignes:
        with st.expander(f"⚠️ {len(rapport_lignes)} anomalie(s) de données"):
            for entry in rapport_lignes:
                fn = st.error if entry["type"] == "error" else st.warning
                fn(f"Ligne {entry['ligne']} [{entry['colonne']}] : {entry['message']}")

    # Tableau
    st.markdown("**Aperçu des données nettoyées**")
    st.caption("🟥 Rouge = doublon (à vérifier)   🟨 Jaune = adresse réorganisée automatiquement")

    doublon_indices = {ln - 2 for d in doublons for ln in d["lignes"]}
    consolidated_indices = {e["ligne"] - 2 for e in consolidation_journal}

    def highlight_row(row):
        idx = row.name
        if idx in doublon_indices:
            return ["background-color: #FFC7CE"] * len(row)
        if idx in consolidated_indices:
            return ["background-color: #FFEB9C"] * len(row)
        return [""] * len(row)

    try:
        st.dataframe(result_df.style.apply(highlight_row, axis=1), use_container_width=True, height=400)
    except Exception:
        st.dataframe(result_df, use_container_width=True, height=400)

    st.divider()
    st.subheader("Téléchargement")

    dl1, dl2 = st.columns(2)
    with dl1:
        try:
            excel_bytes = export_excel(result_df, original_mapped, rapport_lignes, doublons, consolidation_journal)
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
        rapport_txt = export_rapport(nb_imp, nb_exp, nb_supp, rapport_lignes, doublons, consolidation_journal)
        st.download_button(
            "Télécharger le rapport de traitement",
            data=rapport_txt.encode("utf-8"),
            file_name="rapport_normadress.txt",
            mime="text/plain",
            use_container_width=True,
        )
