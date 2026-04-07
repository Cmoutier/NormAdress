"""Étape 5 — Génération et validation du BAT PDF."""
from datetime import datetime
import streamlit as st

from core.db import (get_dossier, charger_adresses, changer_statut,
                     mettre_a_jour_parametres)
from core.pdf_generator import generer_pdf_bat


st.title("BAT — Bon À Tirer")
st.caption("Étape 5 / 6")

dossier_id = st.session_state.get("dossier_id")
if not dossier_id:
    st.switch_page("app.py")

dossier = get_dossier(dossier_id)
st.markdown(f"**Dossier :** {dossier['nom']}")

# Charger les adresses (depuis session ou base)
adresses = st.session_state.get("adresses")
if not adresses:
    with st.spinner("Chargement depuis la base..."):
        adresses = charger_adresses(dossier_id)
if not adresses:
    st.error("Aucune adresse composée. Reprenez depuis l'étape Composition.")
    if st.button("Retour Composition"):
        st.switch_page("pages/04_composition.py")
    st.stop()

# ---------------------------------------------------------------------------
# Statut workflow
# ---------------------------------------------------------------------------

statut = dossier["statut"]
params = dossier.get("parametres") or {}

STATUT_LABEL = {
    "en_cours":  "🟡 En cours",
    "a_valider": "🔵 BAT envoyé — en attente validation",
    "valide":    "🟢 Validé par le client",
    "exporte":   "✅ Exporté",
}
st.markdown(f"**Statut :** {STATUT_LABEL.get(statut, statut)}")

if params.get("date_envoi_bat"):
    st.caption(f"BAT envoyé le {params['date_envoi_bat']}")
if params.get("date_validation_client"):
    st.caption(f"Validé le {params['date_validation_client']}")

# ---------------------------------------------------------------------------
# Génération PDF
# ---------------------------------------------------------------------------

st.markdown("---")

if st.button("Générer le PDF BAT", type="primary"):
    with st.spinner("Génération du PDF..."):
        pdf_bytes = generer_pdf_bat(adresses, dossier["nom"])

    nom_fichier = f"BAT_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
    st.download_button(
        label=f"Télécharger {nom_fichier}",
        data=pdf_bytes,
        file_name=nom_fichier,
        mime="application/pdf",
    )

# ---------------------------------------------------------------------------
# Workflow validation
# ---------------------------------------------------------------------------

st.markdown("---")
st.markdown("**Workflow de validation client**")

col1, col2 = st.columns(2)

with col1:
    if st.button("Marquer comme envoyé au client"):
        date_envoi = datetime.now().strftime("%d/%m/%Y %H:%M")
        params["date_envoi_bat"] = date_envoi
        mettre_a_jour_parametres(dossier_id, params)
        changer_statut(dossier_id, "a_valider")
        st.success(f"Statut → À valider (envoyé le {date_envoi})")
        st.rerun()

with col2:
    if statut in ("a_valider", "en_cours"):
        if st.button("Marquer comme validé par le client", type="primary"):
            date_valid = datetime.now().strftime("%d/%m/%Y %H:%M")
            params["date_validation_client"] = date_valid
            mettre_a_jour_parametres(dossier_id, params)
            changer_statut(dossier_id, "valide")
            st.success(f"Validé le {date_valid}")
            st.rerun()

if dossier["statut"] == "valide":
    st.markdown("---")
    if st.button("Passer à l'export →", type="primary"):
        st.switch_page("pages/06_export.py")
