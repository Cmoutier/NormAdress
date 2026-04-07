"""Étape 3 — Détection pro / particulier et révision."""
import pandas as pd
import streamlit as st

from core.db import get_dossier, charger_mapping, sauvegarder_adresses, changer_statut
from core.mapper import construire_df_mappe
from core.cleaner import clean_row
from core.detector import detecter_type

st.set_page_config(page_title="Détection — NormAdress",
                   page_icon="favicon.png", layout="wide")

st.title("Détection pro / particulier")
st.caption("Étape 3 / 6")

dossier_id = st.session_state.get("dossier_id")
if not dossier_id:
    st.warning("Aucun dossier sélectionné.")
    st.stop()

dossier = get_dossier(dossier_id)
df_source = st.session_state.get("df_source")
mapping = st.session_state.get("mapping") or charger_mapping(dossier_id)

if df_source is None or not mapping:
    st.error("Données manquantes. Reprenez depuis l'étape Mapping.")
    if st.button("Retour Mapping"):
        st.switch_page("pages/02_mapping.py")
    st.stop()

st.markdown(f"**Dossier :** {dossier['nom']}")

# ---------------------------------------------------------------------------
# Construction du DataFrame mappé et nettoyé
# ---------------------------------------------------------------------------

@st.cache_data
def preparer_df(df_bytes_hash, mapping_key):
    return None  # clé de cache uniquement


if "df_mappe" not in st.session_state:
    df_mappe = construire_df_mappe(df_source, mapping)
    rows_clean = [clean_row(row) for row in df_mappe.to_dict("records")]
    df_clean = pd.DataFrame(rows_clean)
    # Détection automatique
    df_clean["type_contact"] = df_clean.apply(
        lambda r: detecter_type(r.to_dict()), axis=1
    )
    df_clean["type_detecte_auto"] = True
    st.session_state["df_mappe"] = df_clean

df = st.session_state["df_mappe"].copy()

# ---------------------------------------------------------------------------
# Compteurs
# ---------------------------------------------------------------------------

nb_part = (df["type_contact"] == "particulier").sum()
nb_pro = (df["type_contact"] == "professionnel").sum()
nb_inc = (df["type_contact"] == "inconnu").sum()

col1, col2, col3 = st.columns(3)
col1.metric("Particuliers", nb_part)
col2.metric("Professionnels", nb_pro)
col3.metric("Inconnus", nb_inc)

# ---------------------------------------------------------------------------
# Tableau de révision
# ---------------------------------------------------------------------------

FILTRE_OPTIONS = ["Tous", "particulier", "professionnel", "inconnu"]
COULEURS = {"particulier": "🟢", "professionnel": "🔵", "inconnu": "🟠"}

filtre = st.selectbox("Filtrer par type", FILTRE_OPTIONS)
df_affich = df if filtre == "Tous" else df[df["type_contact"] == filtre]

st.caption(f"{len(df_affich)} ligne(s) affichée(s)")

# Affichage avec correction manuelle
for idx in df_affich.index:
    row = df.loc[idx]
    type_actuel = row["type_contact"]
    icone = COULEURS.get(type_actuel, "⚪")

    with st.expander(
        f"{icone} #{idx + 1} — {(row.get('societe') or row.get('nom_1') or row.get('identite_1') or '—')[:60]}"
    ):
        c1, c2 = st.columns([3, 1])
        with c1:
            champs_affich = ["societe", "civilite_1", "nom_1", "prenom_1",
                             "identite_1", "adresse_voie", "code_postal", "ville"]
            for champ in champs_affich:
                val = row.get(champ, "")
                if val:
                    st.text(f"{champ}: {val}")
        with c2:
            nouveau_type = st.selectbox(
                "Type",
                ["particulier", "professionnel", "inconnu"],
                index=["particulier", "professionnel", "inconnu"].index(type_actuel),
                key=f"type_{idx}",
            )
            if nouveau_type != type_actuel:
                st.session_state["df_mappe"].at[idx, "type_contact"] = nouveau_type
                st.session_state["df_mappe"].at[idx, "type_detecte_auto"] = False
                st.rerun()

# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

st.markdown("---")
if st.button("Valider la détection →", type="primary"):
    st.session_state["df_mappe"] = st.session_state["df_mappe"]
    st.switch_page("pages/04_composition.py")
