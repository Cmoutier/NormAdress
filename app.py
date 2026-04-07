"""NormAdress v4 — Tableau de bord principal."""
import streamlit as st
from core.db import lister_dossiers, changer_statut

st.set_page_config(
    page_title="NormAdress",
    page_icon="favicon.png",
    layout="wide",
)

STATUT_LABEL = {
    "en_cours":  "🟡 En cours",
    "a_valider": "🔵 À valider",
    "valide":    "🟢 Validé",
    "exporte":   "✅ Exporté",
}

st.title("NormAdress")
st.caption("Composition d'adresses postales AFNOR — STEP")

st.markdown("---")

col_titre, col_btn = st.columns([6, 2])
with col_titre:
    st.subheader("Dossiers")
with col_btn:
    if st.button("+ Nouveau dossier", type="primary", use_container_width=True):
        st.switch_page("pages/01_nouveau_dossier.py")

try:
    dossiers = lister_dossiers()
except Exception as e:
    st.error(f"Impossible de se connecter à la base de données : {e}")
    st.stop()

if not dossiers:
    st.info("Aucun dossier. Créez votre premier dossier pour commencer.")
else:
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
                from datetime import datetime
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
                    # Redirige vers l'étape en cours
                    statut = d["statut"]
                    if statut == "en_cours":
                        st.switch_page("pages/02_mapping.py")
                    elif statut == "a_valider":
                        st.switch_page("pages/05_bat.py")
                    elif statut in ("valide", "exporte"):
                        st.switch_page("pages/06_export.py")
                    else:
                        st.switch_page("pages/02_mapping.py")
