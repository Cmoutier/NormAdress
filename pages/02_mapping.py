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
    st.warning("Aucun dossier sélectionné. Retournez au tableau de bord.")
    if st.button("Tableau de bord"):
        st.switch_page("app.py")
    st.stop()

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

with st.expander("ℹ️ À quoi correspondent les champs AFNOR ?"):
    st.markdown("""
**Structure d'une enveloppe AFNOR (norme NF Z 10-011) — 6 lignes max :**

| Ligne | Champ(s) | Rôle |
|-------|----------|------|
| **L1** | `societe` *ou* `civilite_1 + nom_1 + prenom_1` | Destinataire principal |
| **L2** | `identite_2` (B2B) *ou* complément d'identité | Contact au sein de la société |
| **L3** | `adresse_comp_int` | Bâtiment, résidence, étage, appartement |
| **L4** | `adresse_voie` ← **obligatoire** | Numéro et libellé de la voie (ex : 12 RUE DE LA PAIX) |
| **L5** | `adresse_comp_ext` / `adresse_lieu_dit` | BP, CS, TSA, lieu-dit |
| **L6** | `code_postal` + `ville` | Code postal 5 chiffres + ville en majuscules |

---

**Identité du destinataire :**
- `civilite_1 / nom_1 / prenom_1` — particulier : M. Jean DUPONT
- `identite_1` — identité complète dans une seule colonne (ex : "Jean DUPONT")
- `societe` — raison sociale (B2B) ; prend la place de L1
- `civilite_2 / nom_2 / prenom_2` — 2e contact dans la même enveloppe (B2B)

**Adresse :**
- `adresse_voie` — **L4, obligatoire** — numéro + libellé de voie
- `adresse_comp_int` — bâtiment, résidence, étage *(L3)*
- `adresse_comp_ext` — BP, CS, TSA *(L5)*
- `adresse_lieu_dit` — lieu-dit, hameau *(L5 si comp_ext vide)*
- `code_postal` — 5 chiffres (ex : 75001, 01000)
- `ville` — commune (sera mise en majuscules)
- `pays` — uniquement si adresses étrangères

**Autre :**
- `id_client` — référence client (conservée dans l'export, non envoyée)
- `formule_source` — formule de politesse déjà rédigée dans le fichier source
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
