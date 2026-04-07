"""Étape 4 — Composition AFNOR + Formule."""
import pandas as pd
import streamlit as st

from core.db import get_dossier, sauvegarder_adresses
from core.composer import composer_adresse
from core.validator import valider_adresse, a_alerte_bloquante


st.title("Composition AFNOR")
st.caption("Étape 4 / 6")

dossier_id = st.session_state.get("dossier_id")
if not dossier_id:
    st.warning("Aucun dossier sélectionné.")
    st.stop()

dossier = get_dossier(dossier_id)
df: pd.DataFrame = st.session_state.get("df_mappe")

if df is None:
    st.error("Données manquantes. Reprenez depuis l'étape Détection.")
    if st.button("Retour"):
        st.switch_page("views/03_detection.py")
    st.stop()

st.markdown(f"**Dossier :** {dossier['nom']}")

parametres = dossier.get("parametres") or {}
mode = dossier.get("mode_distribution", "postal")
ordre = parametres.get("ordre_nom_prenom", "afnor")
format_pro = parametres.get("format_pro", "A")

# ---------------------------------------------------------------------------
# Composition
# ---------------------------------------------------------------------------

@st.cache_data(show_spinner="Composition en cours...")
def composer_tout(df_json: str, mode: str, ordre: str, format_pro: str) -> list[dict]:
    import json
    rows = json.loads(df_json)
    resultats = []
    for row in rows:
        type_c = row.get("type_contact", "particulier")
        adresse = composer_adresse(
            row, mode=mode, type_contact=type_c,
            format_pro=format_pro, ordre=ordre
        )
        adresse["type_contact"] = type_c
        adresse["type_detecte_auto"] = row.get("type_detecte_auto", True)
        alertes = valider_adresse(adresse, mode=mode)
        adresse["alertes"] = alertes
        adresse["valide"] = not a_alerte_bloquante(alertes)
        # Conserver les champs source pour l'export
        for k in ("societe", "civilite_1", "nom_1", "prenom_1", "identite_1",
                  "code_postal", "ville", "id_client"):
            adresse[k] = row.get(k, "")
        resultats.append(adresse)
    return resultats

adresses = composer_tout(
    df.to_json(orient="records"),
    mode, ordre, format_pro
)

# ---------------------------------------------------------------------------
# Métriques
# ---------------------------------------------------------------------------

nb_bloquant = sum(1 for a in adresses if a_alerte_bloquante(a.get("alertes", [])))
nb_avertissement = sum(
    1 for a in adresses
    if a.get("alertes") and not a_alerte_bloquante(a["alertes"])
)

c1, c2, c3 = st.columns(3)
c1.metric("Total destinataires", len(adresses))
c2.metric("Alertes bloquantes", nb_bloquant, delta=None,
          delta_color="inverse" if nb_bloquant else "off")
c3.metric("Avertissements", nb_avertissement)

# ---------------------------------------------------------------------------
# Tableau
# ---------------------------------------------------------------------------

filtre_alertes = st.checkbox("Uniquement les lignes avec alertes")

affich = adresses
if filtre_alertes:
    affich = [a for a in adresses if a.get("alertes")]

st.caption(f"{len(affich)} ligne(s)")

LIGNES = ["L1", "L2", "L3", "L4", "L5", "L6", "Formule"]

for i, a in enumerate(affich):
    alertes = a.get("alertes", [])
    bloquant = a_alerte_bloquante(alertes)
    icone = "🔴" if bloquant else ("⚠️" if alertes else "✅")
    label = (a.get("L1") or a.get("societe") or f"Ligne {i+1}")[:60]

    with st.expander(f"{icone} #{i+1} — {label}"):
        col_adr, col_edit = st.columns([3, 2])

        with col_adr:
            for ligne in LIGNES:
                val = a.get(ligne, "")
                if val:
                    st.text(f"{ligne}: {val}")

        with col_edit:
            if alertes:
                for alerte in alertes:
                    badge = "🔴" if alerte["bloquant"] else "⚠️"
                    st.markdown(
                        f"{badge} `{alerte['code']}` {alerte['message']}"
                    )
            # Édition manuelle
            with st.form(key=f"edit_{i}"):
                nouvelles_vals = {}
                for ligne in ["L1", "L2", "L3", "L4", "L5", "L6"]:
                    nouvelles_vals[ligne] = st.text_input(
                        ligne,
                        value=a.get(ligne, ""),
                        max_chars=38,
                        key=f"inp_{i}_{ligne}",
                    )
                if st.form_submit_button("Appliquer"):
                    for k, v in nouvelles_vals.items():
                        adresses[adresses.index(a)][k] = v
                    st.rerun()

# ---------------------------------------------------------------------------
# Sauvegarde et suite
# ---------------------------------------------------------------------------

st.markdown("---")
if st.button("Sauvegarder et générer le BAT →", type="primary"):
    with st.spinner("Sauvegarde en base..."):
        sauvegarder_adresses(dossier_id, adresses)
    st.session_state["adresses"] = adresses
    st.switch_page("views/05_bat.py")
