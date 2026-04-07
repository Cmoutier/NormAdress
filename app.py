"""NormAdress v4 — Point d'entrée navigation + tableau de bord."""
from datetime import datetime
import streamlit as st

st.set_page_config(
    page_title="NormAdress",
    page_icon="favicon.png",
    layout="wide",
)

# ---------------------------------------------------------------------------
# Tableau de bord (page par défaut)
# ---------------------------------------------------------------------------

def page_tableau_de_bord():
    from core.db import lister_dossiers

    st.title("NormAdress")
    st.caption("Composition d'adresses postales AFNOR — STEP")
    st.markdown("---")

    col_titre, col_btn = st.columns([6, 2])
    with col_titre:
        st.subheader("Dossiers")
    with col_btn:
        if st.button("+ Nouveau dossier", type="primary", use_container_width=True):
            st.switch_page("nouveau-dossier")

    try:
        dossiers = lister_dossiers()
    except Exception as e:
        st.error(f"Impossible de se connecter à la base de données : {e}")
        st.stop()

    if not dossiers:
        st.info("Aucun dossier. Créez votre premier dossier pour commencer.")
        return

    STATUT_LABEL = {
        "en_cours":  "🟡 En cours",
        "a_valider": "🔵 À valider",
        "valide":    "🟢 Validé",
        "exporte":   "✅ Exporté",
    }
    STATUT_PAGE = {
        "en_cours":  "mapping",
        "a_valider": "bat",
        "valide":    "export",
        "exporte":   "export",
    }

    for d in dossiers:
        with st.container(border=True):
            c1, c2, c3, c4 = st.columns([4, 2, 2, 2])
            with c1:
                st.markdown(f"**{d['nom']}**")
                if d.get("client"):
                    st.caption(d["client"])
            with c2:
                st.markdown(STATUT_LABEL.get(d["statut"], d["statut"]))
            with c3:
                created = d.get("created_at", "")
                if created:
                    try:
                        dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                        st.caption(dt.strftime("%d/%m/%Y %H:%M"))
                    except Exception:
                        st.caption(created[:10])
            with c4:
                if st.button("Reprendre", key=f"open_{d['id']}",
                             use_container_width=True):
                    st.session_state["dossier_id"] = d["id"]
                    st.session_state["df_source"] = None
                    st.session_state["df_mappe"] = None
                    st.session_state["mapping"] = None
                    st.session_state["adresses"] = None
                    st.switch_page(STATUT_PAGE.get(d["statut"], "mapping"))


# ---------------------------------------------------------------------------
# Navigation conditionnelle
# ---------------------------------------------------------------------------

dossier_id = st.session_state.get("dossier_id")

pages_accueil = [
    st.Page(page_tableau_de_bord, title="Tableau de bord",
            icon="🏠", default=True, url_path="accueil"),
    st.Page("pages/01_nouveau_dossier.py", title="Nouveau dossier",
            icon="📁", url_path="nouveau-dossier"),
]

nav = {"": pages_accueil}

if dossier_id:
    nav["Dossier en cours"] = [
        st.Page("pages/02_mapping.py",     title="Mapping des colonnes",  icon="🔗", url_path="mapping"),
        st.Page("pages/03_detection.py",   title="Détection pro / part.", icon="🔍", url_path="detection"),
        st.Page("pages/04_composition.py", title="Composition AFNOR",     icon="✉️", url_path="composition"),
        st.Page("pages/05_bat.py",         title="BAT — Validation",      icon="📄", url_path="bat"),
        st.Page("pages/06_export.py",      title="Export final",          icon="📤", url_path="export"),
    ]

pg = st.navigation(nav)
pg.run()
