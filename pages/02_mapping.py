"""Étape 2 — Mapping des colonnes source → champs AFNOR."""
import io
import chardet
import pandas as pd
import streamlit as st

from core.db import (get_dossier, sauvegarder_mapping, charger_mapping,
                     mettre_a_jour_dossier)
from core.mapper import auto_map, CHAMPS_CIBLES, normaliser_cle
from core.detector import detecter_mode_distribution, CHAMPS_ADRESSE


st.title("Mapping des colonnes")
st.caption("Étape 2 / 6")

# ---------------------------------------------------------------------------
# Récupération du dossier et du fichier
# ---------------------------------------------------------------------------

dossier_id = st.session_state.get("dossier_id")
if not dossier_id:
    st.switch_page("app.py")

dossier = get_dossier(dossier_id)
if not dossier:
    st.error("Dossier introuvable.")
    st.stop()

st.markdown(f"**Dossier :** {dossier['nom']}")

# Charger le fichier depuis la session
fichier_bytes = st.session_state.get("fichier_excel")
fichier_nom = st.session_state.get("fichier_excel_nom", "")

if fichier_bytes is None:
    uploaded = st.file_uploader(
        "Recharger le fichier source",
        type=["xlsx", "xls", "csv"],
    )
    if not uploaded:
        st.info("Veuillez charger le fichier source pour continuer.")
        st.stop()
    fichier_bytes = uploaded.read()
    fichier_nom = uploaded.name
    st.session_state["fichier_excel"] = fichier_bytes
    st.session_state["fichier_excel_nom"] = fichier_nom


@st.cache_data
def charger_dataframe(data: bytes, nom: str) -> tuple[pd.DataFrame, list[str]]:
    if nom.endswith(".csv"):
        enc = chardet.detect(data)["encoding"] or "utf-8"
        buf = io.StringIO(data.decode(enc, errors="replace"))
        # Détection séparateur
        sample = buf.read(2048)
        buf.seek(0)
        sep = ";" if sample.count(";") > sample.count(",") else ","
        df = pd.read_csv(buf, sep=sep)
    else:
        buf = io.BytesIO(data)
        xf = pd.ExcelFile(buf)
        sheets = xf.sheet_names
        return None, sheets
    return df, []


# Gestion multi-feuilles
df = st.session_state.get("df_source")
if df is None:
    if not fichier_nom.endswith(".csv"):
        buf = io.BytesIO(fichier_bytes)
        xf = pd.ExcelFile(buf)
        sheets = xf.sheet_names
        if len(sheets) > 1:
            feuille = st.selectbox("Choisir la feuille", sheets)
        else:
            feuille = sheets[0]
        df = pd.read_excel(buf, sheet_name=feuille)
    else:
        enc = chardet.detect(fichier_bytes)["encoding"] or "utf-8"
        buf = io.StringIO(fichier_bytes.decode(enc, errors="replace"))
        sample = fichier_bytes.decode(enc, errors="replace")[:2048]
        sep = ";" if sample.count(";") > sample.count(",") else ","
        df = pd.read_csv(buf, sep=sep)
    df = df.fillna("").astype(str)
    df.columns = [str(c).strip() for c in df.columns]
    st.session_state["df_source"] = df

colonnes_source = list(df.columns)

# ---------------------------------------------------------------------------
# Mapping
# ---------------------------------------------------------------------------

mapping_existant = charger_mapping(dossier_id)
mapping_auto = auto_map(colonnes_source)
mapping_init = mapping_existant if mapping_existant else mapping_auto

CHAMPS_OPTIONS = ["(ignorer)"] + CHAMPS_CIBLES

st.markdown("### Association colonnes → champs AFNOR")
st.caption("Vérifiez et ajustez le mapping détecté automatiquement.")

with st.expander("ℹ️ Structure d'une enveloppe AFNOR"):
    col_part, col_pro = st.columns(2)

    with col_part:
        st.markdown("#### Pour un particulier")
        st.markdown("""
| Ligne | Détails de l'information | Exemple |
|-------|--------------------------|---------|
| **L1** | Identité du destinataire — civilité + prénom + nom *(obligatoire)* | M. Jean DUPONT |
| L2 | Complément d'identité intérieur (appartement, étage…) | Appartement 12 |
| L3 | Complément d'identité extérieur (bâtiment, résidence…) | Résidence Les Pins |
| **L4** | Numéro et libellé de la voie *(obligatoire)* | 12 RUE DE LA PAIX |
| L5 | Lieu-dit ou boîte postale (BP, CS, TSA…) | BP 123 |
| **L6** | Code postal + commune *(obligatoire)* | 75001 PARIS |
""")

    with col_pro:
        st.markdown("#### Pour une entreprise")
        st.markdown("""
| Ligne | Détails de l'information | Exemple |
|-------|--------------------------|---------|
| **L1** | Raison sociale / Structure *(obligatoire)* | ACME SARL |
| L2 | Identité du destinataire — civilité + prénom + nom | M. Jean DUPONT |
| L3 | Complément d'identité extérieur (bâtiment, résidence…) | Bât. B |
| **L4** | Numéro et libellé de la voie *(obligatoire)* | 12 RUE DE LA PAIX |
| L5 | Lieu-dit ou boîte postale (BP, CS, TSA…) | CS 12345 |
| **L6** | Code postal + commune *(obligatoire)* | 75001 PARIS |
""")


mapping_result: dict[str, str] = {}
nb_cols = 3
cols = st.columns(nb_cols)

for i, col_src in enumerate(colonnes_source):
    # Exemple de valeur
    exemples = df[col_src].replace("", pd.NA).dropna().head(3).tolist()
    exemple_str = " / ".join(str(e) for e in exemples) if exemples else "—"

    champ_defaut = mapping_init.get(col_src, "(ignorer)")
    if champ_defaut not in CHAMPS_OPTIONS:
        champ_defaut = "(ignorer)"

    with cols[i % nb_cols]:
        with st.container(border=True):
            st.markdown(f"**{col_src}**")
            st.caption(f"ex: {exemple_str[:60]}")
            choix = st.selectbox(
                "Champ cible",
                CHAMPS_OPTIONS,
                index=CHAMPS_OPTIONS.index(champ_defaut),
                key=f"map_{col_src}",
                label_visibility="collapsed",
            )
            if choix != "(ignorer)":
                mapping_result[col_src] = choix

# ---------------------------------------------------------------------------
# Détection mode distribution
# ---------------------------------------------------------------------------

champs_mappes = set(mapping_result.values())
mode_detecte = detecter_mode_distribution(champs_mappes)

if mode_detecte == "bal_interne":
    st.warning(
        "Aucune colonne adresse détectée. S'agit-il d'un publipostage en remise "
        "directe (boîte aux lettres interne) ?"
    )
    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("Confirmer — Mode BAL interne", type="primary"):
            sauvegarder_mapping(dossier_id, mapping_result)
            mettre_a_jour_dossier(dossier_id, mode_distribution="bal_interne")
            st.session_state["mapping"] = mapping_result
            st.session_state["mode_distribution"] = "bal_interne"
            st.switch_page("pages/03_detection.py")
    with col_b:
        st.info("Non, ajustez le mapping ci-dessus pour inclure une colonne adresse.")
else:
    if st.button("Valider le mapping", type="primary"):
        sauvegarder_mapping(dossier_id, mapping_result)
        mettre_a_jour_dossier(dossier_id, mode_distribution="postal")
        st.session_state["mapping"] = mapping_result
        st.session_state["mode_distribution"] = "postal"
        st.switch_page("pages/03_detection.py")
