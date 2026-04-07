"""NormAdress v4 — Point d'entrée navigation + tableau de bord."""
from datetime import datetime
import streamlit as st

st.set_page_config(
    page_title="NormAdress",
    page_icon="favicon.png",
    layout="wide",
)

# Chemins de fichiers — seule forme acceptée par st.switch_page()
PAGE_NOUVEAU     = "pages/01_nouveau_dossier.py"
PAGE_MAPPING     = "pages/02_mapping.py"
PAGE_DETECTION   = "pages/03_detection.py"
PAGE_COMPOSITION = "pages/04_composition.py"
PAGE_BAT         = "pages/05_bat.py"
PAGE_EXPORT      = "pages/06_export.py"

STATUT_PAGE = {
    "en_cours":  PAGE_MAPPING,
    "a_valider": PAGE_BAT,
    "valide":    PAGE_EXPORT,
    "exporte":   PAGE_EXPORT,
}

# ---------------------------------------------------------------------------
# Indicateur dossier actif + bouton fermer (sidebar)
# ---------------------------------------------------------------------------

dossier_id = st.session_state.get("dossier_id")

if dossier_id:
    with st.sidebar:
        try:
            from core.db import get_dossier as _get
            _d = _get(dossier_id)
            if _d:
                st.caption("Dossier actif")
                st.markdown(f"**{_d['nom']}**")
        except Exception:
            pass
        if st.button("✕ Fermer le dossier", use_container_width=True):
            for k in ("dossier_id", "df_source", "df_mappe", "mapping",
                      "adresses", "fichier_excel", "fichier_word",
                      "fichier_excel_nom", "fichier_word_nom", "parametres"):
                st.session_state.pop(k, None)
            st.rerun()
        st.divider()

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
            st.switch_page(PAGE_NOUVEAU)

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

    for d in dossiers:
        with st.container(border=True):
            c1, c2, c3, c4, c5 = st.columns([4, 2, 2, 1, 1])
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
                    for k in ("df_source", "df_mappe", "mapping", "adresses",
                              "fichier_excel", "fichier_word"):
                        st.session_state.pop(k, None)
                    st.session_state["dossier_id"] = d["id"]
                    st.session_state["target_page"] = d["statut"]
                    st.rerun()
            with c5:
                if st.button("Dupliquer", key=f"dup_{d['id']}",
                             use_container_width=True):
                    for k in ("dossier_id", "df_source", "df_mappe", "mapping",
                              "adresses", "fichier_excel", "fichier_word"):
                        st.session_state.pop(k, None)
                    st.session_state["duplication_source_id"] = d["id"]
                    st.switch_page(PAGE_NOUVEAU)

# ---------------------------------------------------------------------------
# Navigation conditionnelle
# st.navigation() supprime l'auto-navigation générée par pages/
# ---------------------------------------------------------------------------

dossier_id = st.session_state.get("dossier_id")

nav_accueil = [
    st.Page(page_tableau_de_bord,  title="Tableau de bord",       icon="🏠", default=True),
    st.Page(PAGE_NOUVEAU,          title="Nouveau dossier",        icon="📁"),
]

nav = {"": nav_accueil}

if dossier_id:
    nav["Dossier en cours"] = [
        st.Page(PAGE_MAPPING,     title="Mapping des colonnes",  icon="🔗"),
        st.Page(PAGE_DETECTION,   title="Détection pro / part.", icon="🔍"),
        st.Page(PAGE_COMPOSITION, title="Composition AFNOR",     icon="✉️"),
        st.Page(PAGE_BAT,         title="BAT — Validation",      icon="📄"),
        st.Page(PAGE_EXPORT,      title="Export final",          icon="📤"),
    ]

pg = st.navigation(nav)

# Redirection différée : switch_page APRÈS que la navigation est construite.
_statut = st.session_state.pop("target_page", None)
if _statut and dossier_id:
    st.switch_page(STATUT_PAGE.get(_statut, PAGE_MAPPING))

pg.run()
