"""Étape 3 — Détection pro / particulier et révision."""
import pandas as pd
import streamlit as st

from core.db import get_dossier, charger_mapping
from core.mapper import construire_df_mappe
from core.cleaner import clean_row
from core.detector import detecter_type

st.title("Détection pro / particulier")
st.caption("Étape 3 / 6")

dossier_id = st.session_state.get("dossier_id")
if not dossier_id:
    st.switch_page("app.py")

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
# Préparation (une seule fois)
# ---------------------------------------------------------------------------

if "df_mappe" not in st.session_state:
    with st.spinner("Analyse en cours…"):
        df_mappe = construire_df_mappe(df_source, mapping)
        rows_clean = [clean_row(row) for row in df_mappe.to_dict("records")]
        df_clean = pd.DataFrame(rows_clean)
        df_clean["type_contact"] = df_clean.apply(
            lambda r: detecter_type(r.to_dict()), axis=1
        )
        df_clean["type_detecte_auto"] = True
        st.session_state["df_mappe"] = df_clean

df = st.session_state["df_mappe"]

# ---------------------------------------------------------------------------
# Compteurs (cliquables pour filtrer)
# ---------------------------------------------------------------------------

nb_part = int((df["type_contact"] == "particulier").sum())
nb_pro  = int((df["type_contact"] == "professionnel").sum())
nb_inc  = int((df["type_contact"] == "inconnu").sum())

col1, col2, col3, col4 = st.columns(4)
col1.metric("Total", len(df))
col2.metric("🟢 Particuliers", nb_part)
col3.metric("🔵 Professionnels", nb_pro)
col4.metric("🟠 Inconnus", nb_inc)

# ---------------------------------------------------------------------------
# Filtre + pagination
# ---------------------------------------------------------------------------

LIGNES_PAR_PAGE = 50

FILTRE_OPTIONS = ["Tous", "particulier", "professionnel", "inconnu"]

# Pré-sélectionner "inconnu" si des inconnus existent
defaut_filtre = "inconnu" if nb_inc > 0 else "Tous"
if "filtre_detection" not in st.session_state:
    st.session_state["filtre_detection"] = defaut_filtre

filtre = st.radio(
    "Afficher",
    FILTRE_OPTIONS,
    index=FILTRE_OPTIONS.index(st.session_state["filtre_detection"]),
    horizontal=True,
    key="filtre_detection",
)

df_affich = df if filtre == "Tous" else df[df["type_contact"] == filtre]
total_affich = len(df_affich)

if total_affich == 0:
    st.info("Aucune ligne pour ce filtre.")
else:
    # Pagination
    nb_pages = max(1, (total_affich - 1) // LIGNES_PAR_PAGE + 1)
    if "page_detection" not in st.session_state:
        st.session_state["page_detection"] = 0

    page = st.session_state["page_detection"]
    debut = page * LIGNES_PAR_PAGE
    fin   = min(debut + LIGNES_PAR_PAGE, total_affich)

    st.caption(f"Lignes {debut + 1}–{fin} sur {total_affich}")

    # Affichage paginé
    COULEURS = {"particulier": "🟢", "professionnel": "🔵", "inconnu": "🟠"}

    for idx in df_affich.index[debut:fin]:
        row = df.loc[idx]
        type_actuel = row["type_contact"]
        icone = COULEURS.get(type_actuel, "⚪")
        label = (str(row.get("societe") or row.get("nom_1") or
                     row.get("identite_1") or "—"))[:60]

        with st.expander(f"{icone} #{idx + 1} — {label}"):
            c1, c2 = st.columns([3, 1])
            with c1:
                for champ in ["societe", "civilite_1", "nom_1", "prenom_1",
                               "identite_1", "adresse_voie", "code_postal", "ville"]:
                    val = str(row.get(champ, "") or "")
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

    # Navigation pages
    if nb_pages > 1:
        cp1, cp2, cp3, cp4 = st.columns([1, 2, 2, 1])
        with cp1:
            if st.button("← Préc.", disabled=(page == 0)):
                st.session_state["page_detection"] = page - 1
                st.rerun()
        with cp2:
            st.caption(f"Page {page + 1} / {nb_pages}")
        with cp3:
            saisie = st.number_input(
                "Aller à la page", min_value=1, max_value=nb_pages,
                value=page + 1, step=1, key="goto_detection",
                label_visibility="collapsed",
            )
            if saisie - 1 != page:
                st.session_state["page_detection"] = saisie - 1
                st.rerun()
        with cp4:
            if st.button("Suiv. →", disabled=(page >= nb_pages - 1)):
                st.session_state["page_detection"] = page + 1
                st.rerun()

# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

st.markdown("---")
if st.button("Valider la détection →", type="primary"):
    st.switch_page("pages/04_composition.py")
