"""NormAdress — Application Streamlit de mise en conformité d'adresses."""
import io
import pandas as pd
import streamlit as st

from cleaner.loader import load_file
from cleaner.mapper import auto_map, detect_multi_contacts, STANDARD_FIELDS
from cleaner.rules import apply_rules
from cleaner.consolidator import consolidate_addresses, remove_empty_rows, detect_duplicates
from cleaner.exporter import export_excel, export_rapport

st.set_page_config(
    page_title="NormAdress",
    page_icon="📬",
    layout="wide",
)

# ---------------------------------------------------------------------------
# En-tête
# ---------------------------------------------------------------------------
col_logo, col_title = st.columns([1, 8])
with col_logo:
    try:
        st.image("logo.svg", width=64)
    except Exception:
        st.write("📬")
with col_title:
    st.title("NormAdress")
    st.caption("Mise en conformité de fichiers d'adresses pour publipostage Word")

st.divider()

# ---------------------------------------------------------------------------
# Étape 1 — Upload
# ---------------------------------------------------------------------------
st.header("1. Importer le fichier")
uploaded = st.file_uploader(
    "Sélectionnez un fichier Excel ou CSV",
    type=["xlsx", "xls", "csv"],
    help="Formats supportés : .xlsx, .xls, .csv (séparateur détecté automatiquement)",
)

if not uploaded:
    st.info("Importez un fichier pour commencer.")
    st.stop()

# Chargement
try:
    file_data = load_file(uploaded)
except Exception as e:
    st.error(f"Erreur lors du chargement du fichier : {e}")
    st.stop()

# Sélection de la feuille si multi-feuilles Excel
if len(file_data["sheets"]) > 1:
    sheet_name = st.selectbox(
        "Le fichier contient plusieurs feuilles — choisissez celle à traiter :",
        file_data["sheets"],
    )
else:
    sheet_name = file_data["sheets"][0]

source_df = file_data["dataframes"][sheet_name].copy()

nb_importees = len(source_df)
if nb_importees > 50_000:
    st.warning(
        f"⚠️ Le fichier contient {nb_importees:,} lignes. "
        "Les performances peuvent être dégradées au-delà de 50 000 lignes."
    )

st.success(f"Fichier chargé : **{nb_importees}** lignes, **{len(source_df.columns)}** colonnes.")

st.divider()

# ---------------------------------------------------------------------------
# Étape 2 — Mapping des colonnes
# ---------------------------------------------------------------------------
st.header("2. Correspondance des colonnes")
st.write("Associez chaque colonne source à un champ standard (détection automatique pré-remplie) :")

initial_mapping = auto_map(list(source_df.columns))
options_list = ["(ignorer)"] + STANDARD_FIELDS

mapping = {}
cols_ui = st.columns(3)
for i, src_col in enumerate(source_df.columns):
    with cols_ui[i % 3]:
        default_field = initial_mapping.get(src_col, "")
        default_idx = options_list.index(default_field) if default_field in options_list else 0
        chosen = st.selectbox(
            f"`{src_col}`",
            options_list,
            index=default_idx,
            key=f"map_{src_col}",
        )
        if chosen != "(ignorer)":
            mapping[src_col] = chosen

st.divider()

# ---------------------------------------------------------------------------
# Étape 3 — Détection multi-contacts
# ---------------------------------------------------------------------------
multi_contacts = detect_multi_contacts(mapping)
explode = False
if multi_contacts:
    fields_str = ", ".join(
        f"{field} ({len(cols)} colonnes)" for field, cols in multi_contacts.items()
    )
    st.warning(
        f"⚠️ **Multi-contacts détectés** : {fields_str}. "
        "Plusieurs colonnes sont associées au même champ — chaque ligne sera éclatée en contacts séparés."
    )
    explode = st.checkbox(
        "Confirmer l'éclatement multi-contacts (une ligne par contact)",
        value=False,
    )
    st.divider()

# ---------------------------------------------------------------------------
# Étape 4 — Options de nettoyage
# ---------------------------------------------------------------------------
st.header("3. Options de nettoyage")
col1, col2, col3 = st.columns(3)
with col1:
    opt_espaces = st.checkbox("Nettoyer les espaces et caractères spéciaux", value=True)
    opt_civilite = st.checkbox("Normaliser les civilités", value=True)
    opt_nom = st.checkbox("Mettre le Nom en MAJUSCULES", value=True)
with col2:
    opt_prenom = st.checkbox("Mettre le Prénom en Titre", value=True)
    opt_codepostal = st.checkbox("Corriger les codes postaux", value=True)
    opt_ville = st.checkbox("Mettre la Ville en MAJUSCULES", value=True)
with col3:
    opt_consolidation = st.checkbox("Consolider les lignes d'adresse", value=True)
    opt_supprimer_vides = st.checkbox("Supprimer les lignes vides", value=True)

options = {
    "espaces": opt_espaces,
    "civilite": opt_civilite,
    "nom": opt_nom,
    "prenom": opt_prenom,
    "codepostal": opt_codepostal,
    "ville": opt_ville,
}

st.divider()

# ---------------------------------------------------------------------------
# Étape 5 — Traitement
# ---------------------------------------------------------------------------
st.header("4. Traitement")

if st.button("▶ Mettre en conformité", type="primary", use_container_width=True):
    with st.spinner("Traitement en cours…"):
        try:
            # 1. Construire le DataFrame mappé
            mapped_rows = []
            for _, row in source_df.iterrows():
                new_row = {f: "" for f in STANDARD_FIELDS}
                for src_col, field in mapping.items():
                    if field in STANDARD_FIELDS:
                        existing = new_row.get(field, "")
                        val = str(row.get(src_col, ""))
                        # En cas de multi-contacts non confirmé, on prend la première valeur
                        if not existing:
                            new_row[field] = val
                mapped_rows.append(new_row)

            mapped_df = pd.DataFrame(mapped_rows, columns=STANDARD_FIELDS)
            original_mapped = mapped_df.copy()

            # 2. Éclatement multi-contacts
            if explode and multi_contacts:
                from cleaner.consolidator import explode_multi_contacts
                mapped_df = explode_multi_contacts(mapped_df, multi_contacts, source_df)
                original_mapped = mapped_df.copy()

            # 3. Règles de nettoyage
            mapped_df, rapport_lignes = apply_rules(mapped_df, options)

            # 4. Consolidation adresses
            consolidation_journal = []
            if opt_consolidation:
                mapped_df, consolidation_journal = consolidate_addresses(mapped_df)

            # 5. Suppression lignes vides
            nb_supprimees = 0
            if opt_supprimer_vides:
                mapped_df, nb_supprimees = remove_empty_rows(mapped_df)
                original_mapped = original_mapped.reindex(mapped_df.index)

            # 6. Détection doublons
            doublons = detect_duplicates(mapped_df)

            nb_exportees = len(mapped_df)

            # Stocker en session
            st.session_state["result_df"] = mapped_df
            st.session_state["original_mapped"] = original_mapped
            st.session_state["rapport_lignes"] = rapport_lignes
            st.session_state["doublons"] = doublons
            st.session_state["consolidation_journal"] = consolidation_journal
            st.session_state["nb_importees"] = nb_importees
            st.session_state["nb_exportees"] = nb_exportees
            st.session_state["nb_supprimees"] = nb_supprimees
            st.session_state["processed"] = True

        except Exception as e:
            st.error(f"Erreur pendant le traitement : {e}")
            raise

# ---------------------------------------------------------------------------
# Résultats
# ---------------------------------------------------------------------------
if st.session_state.get("processed"):
    result_df = st.session_state["result_df"]
    original_mapped = st.session_state["original_mapped"]
    rapport_lignes = st.session_state["rapport_lignes"]
    doublons = st.session_state["doublons"]
    consolidation_journal = st.session_state["consolidation_journal"]
    nb_importees_s = st.session_state["nb_importees"]
    nb_exportees_s = st.session_state["nb_exportees"]
    nb_supprimees_s = st.session_state["nb_supprimees"]

    st.divider()
    st.header("5. Résultats")

    # Métriques
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Lignes importées", nb_importees_s)
    m2.metric("Lignes exportées", nb_exportees_s)
    m3.metric("Lignes supprimées", nb_supprimees_s)
    m4.metric("Doublons détectés", len(doublons))
    m5.metric("Consolidations", len(consolidation_journal))

    st.subheader("Aperçu des données nettoyées")

    # Coloration via styler
    doublon_indices = set()
    for d in doublons:
        for ligne_num in d["lignes"]:
            doublon_indices.add(ligne_num - 2)

    consolidated_indices = {entry["ligne"] - 2 for entry in consolidation_journal}

    def highlight_row(row):
        idx = row.name
        if idx in doublon_indices:
            return ["background-color: #FFC7CE"] * len(row)
        if idx in consolidated_indices:
            return ["background-color: #FFEB9C"] * len(row)
        return [""] * len(row)

    try:
        styled = result_df.style.apply(highlight_row, axis=1)
        st.dataframe(styled, use_container_width=True, height=400)
    except Exception:
        st.dataframe(result_df, use_container_width=True, height=400)

    # Légende
    st.caption("🟥 Rouge = doublon   🟨 Orange = adresse consolidée")

    # Doublons
    if doublons:
        with st.expander(f"⚠️ {len(doublons)} doublon(s) détecté(s) — cliquez pour voir le détail"):
            for d in doublons:
                lignes_str = ", ".join(str(l) for l in d["lignes"])
                st.write(f"• **{d['nom']}** / {d['codepostal']} → lignes {lignes_str}")

    # Anomalies
    if rapport_lignes:
        with st.expander(f"⚠️ {len(rapport_lignes)} anomalie(s) — cliquez pour voir le détail"):
            for entry in rapport_lignes:
                if entry["type"] == "error":
                    st.error(f"Ligne {entry['ligne']} [{entry['colonne']}] : {entry['message']}")
                else:
                    st.warning(f"Ligne {entry['ligne']} [{entry['colonne']}] : {entry['message']}")

    st.divider()
    st.subheader("6. Téléchargement")

    dl1, dl2 = st.columns(2)

    with dl1:
        try:
            excel_bytes = export_excel(
                result_df,
                original_mapped,
                rapport_lignes,
                doublons,
                consolidation_journal,
            )
            st.download_button(
                "📥 Télécharger le fichier Excel nettoyé",
                data=excel_bytes,
                file_name="adresses_normalisees.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )
        except Exception as e:
            st.error(f"Erreur génération Excel : {e}")

    with dl2:
        rapport_txt = export_rapport(
            nb_importees_s,
            nb_exportees_s,
            nb_supprimees_s,
            rapport_lignes,
            doublons,
            consolidation_journal,
        )
        st.download_button(
            "📄 Télécharger le rapport TXT",
            data=rapport_txt.encode("utf-8"),
            file_name="rapport_normadress.txt",
            mime="text/plain",
            use_container_width=True,
        )
