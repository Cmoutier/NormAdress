"""Étape 1 — Création d'un nouveau dossier."""
import streamlit as st
from core.db import creer_dossier, charger_mapping, sauvegarder_mapping, get_dossier

st.title("Nouveau dossier")
st.caption("Étape 1 / 6")

# ---------------------------------------------------------------------------
# Pré-remplissage si duplication
# ---------------------------------------------------------------------------

duplication_id = st.session_state.pop("duplication_source_id", None)
src = {}
src_mapping = {}

if duplication_id:
    try:
        src_dossier = get_dossier(duplication_id)
        if src_dossier:
            src = src_dossier.get("parametres") or {}
            src["client"] = src_dossier.get("client", "")
            src["nom"] = src_dossier.get("nom", "")
            src_mapping = charger_mapping(duplication_id)
            st.info(
                f"Duplication de **{src_dossier['nom']}** — "
                "Le mapping sera repris automatiquement. "
                "Modifiez le nom et uploadez les nouveaux fichiers."
            )
    except Exception as e:
        st.warning(f"Impossible de charger le dossier source : {e}")

# Valeurs par défaut (duplication ou vierge)
def_nom    = src.get("nom", "")
def_client = src.get("client", "")
def_ordre  = 1 if src.get("ordre_nom_prenom") == "alt" else 0
def_format = 1 if src.get("format_pro") == "B" else 0
def_pays   = src.get("pays_defaut", "France")
def_entete = {"auto": 0, "oui": 1, "non": 2}.get(src.get("entete", "auto"), 0)

# ---------------------------------------------------------------------------
# Formulaire
# ---------------------------------------------------------------------------

with st.form("form_dossier"):
    nom = st.text_input(
        "Nom du dossier *",
        value=def_nom,
        placeholder="ex: Gazette Synerpa — Avril 2025",
    )
    client = st.text_input("Nom du client", value=def_client,
                           placeholder="ex: SYNERPA")

    col1, col2 = st.columns(2)
    with col1:
        fichier_excel = st.file_uploader(
            "Fichier Excel source *",
            type=["xlsx", "xls", "csv"],
            help="Fichier contenant les destinataires",
        )
    with col2:
        fichier_word = st.file_uploader(
            "Fichier Word client (courrier)",
            type=["docx"],
            help="Le courrier à fusionner — optionnel à cette étape",
        )

    st.markdown("**Paramètres campagne**")
    col3, col4, col5 = st.columns(3)
    with col3:
        ordre = st.selectbox(
            "Ordre identité",
            ["AFNOR — Civilité Prénom NOM", "Civilité NOM Prénom"],
            index=def_ordre,
        )
    with col4:
        format_pro = st.selectbox(
            "Format professionnel",
            ["Mode A — L1 Société / L2 Contact",
             "Mode B — L1 Contact / L2 Société"],
            index=def_format,
        )
    with col5:
        pays_defaut = st.text_input("Pays par défaut", value=def_pays)

    entete = st.radio(
        "En-tête dans le fichier",
        ["Auto-détecter", "Oui", "Non"],
        horizontal=True,
        index=def_entete,
    )

    submitted = st.form_submit_button("Créer le dossier", type="primary")

if submitted:
    if not nom:
        st.error("Le nom du dossier est obligatoire.")
        st.stop()
    if not fichier_excel:
        st.error("Veuillez charger un fichier Excel source.")
        st.stop()

    try:
        ordre_val     = "afnor" if "AFNOR" in ordre else "alt"
        format_pro_val = "A" if "Mode A" in format_pro else "B"
        entete_val    = {"Auto-détecter": "auto", "Oui": "oui", "Non": "non"}[entete]

        parametres = {
            "ordre_nom_prenom": ordre_val,
            "format_pro":       format_pro_val,
            "pays_defaut":      pays_defaut,
            "entete":           entete_val,
            "fichier_source_nom": fichier_excel.name,
            "fichier_word_nom":   fichier_word.name if fichier_word else "",
        }

        dossier = creer_dossier(nom=nom, client=client, parametres=parametres)
        dossier_id = dossier["id"]

        # Copier le mapping source si duplication
        if src_mapping:
            sauvegarder_mapping(dossier_id, src_mapping)
            st.session_state["mapping"] = src_mapping

        # Stocker en session
        st.session_state["dossier_id"]        = dossier_id
        st.session_state["fichier_excel"]     = fichier_excel.read()
        st.session_state["fichier_excel_nom"] = fichier_excel.name
        st.session_state["df_source"]         = None
        st.session_state["df_mappe"]          = None
        if fichier_word:
            st.session_state["fichier_word"]     = fichier_word.read()
            st.session_state["fichier_word_nom"] = fichier_word.name
        st.session_state["parametres"] = parametres

        st.success(f"Dossier **{nom}** créé.")
        st.switch_page("mapping")

    except Exception as e:
        st.error(f"Erreur lors de la création du dossier : {e}")
