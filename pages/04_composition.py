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
    st.switch_page("app.py")

dossier = get_dossier(dossier_id)
df: pd.DataFrame = st.session_state.get("df_mappe")

if df is None:
    st.error("Données manquantes. Reprenez depuis l'étape Détection.")
    if st.button("Retour"):
        st.switch_page("pages/03_detection.py")
    st.stop()

st.markdown(f"**Dossier :** {dossier['nom']}")

parametres   = dossier.get("parametres") or {}
mode         = dossier.get("mode_distribution", "postal")
ordre        = parametres.get("ordre_nom_prenom", "afnor")
format_pro   = parametres.get("format_pro", "A")

# ---------------------------------------------------------------------------
# Composition (mise en cache)
# ---------------------------------------------------------------------------

@st.cache_data(show_spinner="Composition des adresses AFNOR…")
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
        # Passer pays au validateur
        adresse["pays"] = row.get("pays", "")
        alertes = valider_adresse(adresse, mode=mode)
        adresse["alertes"] = alertes
        adresse["valide"] = not a_alerte_bloquante(alertes)
        for k in ("societe", "civilite_1", "nom_1", "prenom_1", "identite_1",
                  "code_postal", "ville", "id_client"):
            adresse[k] = row.get(k, "")
        resultats.append(adresse)
    return resultats

adresses = composer_tout(df.to_json(orient="records"), mode, ordre, format_pro)

# ---------------------------------------------------------------------------
# Métriques + filtres rapides
# ---------------------------------------------------------------------------

nb_total       = len(adresses)
nb_bloquant    = sum(1 for a in adresses if a_alerte_bloquante(a.get("alertes", [])))
nb_avertiss    = sum(1 for a in adresses
                     if a.get("alertes") and not a_alerte_bloquante(a["alertes"]))
nb_ok          = nb_total - nb_bloquant - nb_avertiss

# Compteur par code d'alerte
from collections import Counter
_codes_bloquant = Counter(
    al["code"]
    for a in adresses
    for al in a.get("alertes", [])
    if al["bloquant"]
)
_codes_avertiss = Counter(
    al["code"]
    for a in adresses
    for al in a.get("alertes", [])
    if not al["bloquant"]
)

# Filtre actif en session
if "filtre_compo" not in st.session_state:
    st.session_state["filtre_compo"] = "bloquant" if nb_bloquant else "tous"

c1, c2, c3, c4 = st.columns(4)
with c1:
    st.metric("Total", nb_total)
with c2:
    if st.button(f"🔴 {nb_bloquant} bloquante{'s' if nb_bloquant > 1 else ''}",
                 use_container_width=True,
                 type="primary" if st.session_state["filtre_compo"] == "bloquant" else "secondary"):
        st.session_state["filtre_compo"] = "bloquant"
        st.rerun()
with c3:
    if st.button(f"⚠️ {nb_avertiss} avertissement{'s' if nb_avertiss > 1 else ''}",
                 use_container_width=True,
                 type="primary" if st.session_state["filtre_compo"] == "avertiss" else "secondary"):
        st.session_state["filtre_compo"] = "avertiss"
        st.rerun()
with c4:
    if st.button(f"✅ {nb_ok} sans alerte",
                 use_container_width=True,
                 type="primary" if st.session_state["filtre_compo"] == "tous" else "secondary"):
        st.session_state["filtre_compo"] = "tous"
        st.rerun()

# Détail par code d'alerte + exports CSV
if _codes_bloquant or _codes_avertiss:
    with st.expander("📊 Détail des alertes + exports"):
        det1, det2 = st.columns(2)
        with det1:
            if _codes_bloquant:
                st.markdown("**🔴 Erreurs bloquantes par type**")
                for code, n in sorted(_codes_bloquant.items()):
                    st.markdown(f"- `{code}` : **{n}**")
        with det2:
            if _codes_avertiss:
                st.markdown("**⚠️ Avertissements par type**")
                for code, n in sorted(_codes_avertiss.items()):
                    st.markdown(f"- `{code}` : **{n}**")

        def _to_csv(liste_adresses: list[dict]) -> bytes:
            import io, csv
            buf = io.StringIO()
            w = csv.writer(buf, delimiter=";")
            w.writerow(["#", "L1", "L2", "L3", "L4", "L5", "L6", "Formule", "Alertes"])
            for idx, a in liste_adresses:
                codes = ", ".join(al["code"] for al in a.get("alertes", []))
                w.writerow([idx + 1,
                             a.get("L1",""), a.get("L2",""), a.get("L3",""),
                             a.get("L4",""), a.get("L5",""), a.get("L6",""),
                             a.get("Formule",""), codes])
            return buf.getvalue().encode("utf-8-sig")

        exp1, exp2 = st.columns(2)
        with exp1:
            if nb_bloquant:
                bloquants = [(i, a) for i, a in enumerate(adresses)
                             if a_alerte_bloquante(a.get("alertes", []))]
                st.download_button(
                    "⬇️ Export erreurs bloquantes (.csv)",
                    data=_to_csv(bloquants),
                    file_name="erreurs_bloquantes.csv",
                    mime="text/csv",
                    use_container_width=True,
                )
        with exp2:
            if nb_avertiss:
                avertiss = [(i, a) for i, a in enumerate(adresses)
                            if a.get("alertes") and not a_alerte_bloquante(a["alertes"])]
                st.download_button(
                    "⬇️ Export avertissements (.csv)",
                    data=_to_csv(avertiss),
                    file_name="avertissements.csv",
                    mime="text/csv",
                    use_container_width=True,
                )

# ---------------------------------------------------------------------------
# Filtrage + pagination
# ---------------------------------------------------------------------------

LIGNES_PAR_PAGE = 50
filtre = st.session_state["filtre_compo"]

if filtre == "bloquant":
    affich = [(i, a) for i, a in enumerate(adresses)
              if a_alerte_bloquante(a.get("alertes", []))]
elif filtre == "avertiss":
    affich = [(i, a) for i, a in enumerate(adresses)
              if a.get("alertes") and not a_alerte_bloquante(a["alertes"])]
else:
    affich = list(enumerate(adresses))

total_affich = len(affich)

if total_affich == 0:
    st.info("Aucune ligne pour ce filtre.")
else:
    nb_pages = max(1, (total_affich - 1) // LIGNES_PAR_PAGE + 1)
    if "page_compo" not in st.session_state:
        st.session_state["page_compo"] = 0
    page = min(st.session_state["page_compo"], nb_pages - 1)
    debut = page * LIGNES_PAR_PAGE
    fin   = min(debut + LIGNES_PAR_PAGE, total_affich)

    st.caption(f"Lignes {debut + 1}–{fin} sur {total_affich}")

    for orig_i, a in affich[debut:fin]:
        alertes = a.get("alertes", [])
        bloquant = a_alerte_bloquante(alertes)
        icone = "🔴" if bloquant else ("⚠️" if alertes else "✅")
        label = (a.get("L1") or a.get("societe") or f"Ligne {orig_i + 1}")[:60]

        with st.expander(f"{icone} #{orig_i + 1} — {label}"):
            col_adr, col_edit = st.columns([3, 2])

            with col_adr:
                for ligne in ("L1", "L2", "L3", "L4", "L5", "L6", "Formule"):
                    val = a.get(ligne, "")
                    if val:
                        st.text(f"{ligne}: {val}")

            with col_edit:
                if alertes:
                    for alerte in alertes:
                        badge = "🔴" if alerte["bloquant"] else "⚠️"
                        st.markdown(f"{badge} **{alerte['code']}** — {alerte['message']}")
                with st.form(key=f"edit_{orig_i}"):
                    nouvelles_vals = {}
                    for ligne in ("L1", "L2", "L3", "L4", "L5", "L6"):
                        nouvelles_vals[ligne] = st.text_input(
                            ligne, value=a.get(ligne, ""),
                            max_chars=38, key=f"inp_{orig_i}_{ligne}",
                        )
                    if st.form_submit_button("Appliquer la correction"):
                        for k, v in nouvelles_vals.items():
                            adresses[orig_i][k] = v
                        # Revalider
                        adresses[orig_i]["alertes"] = valider_adresse(
                            adresses[orig_i], mode=mode
                        )
                        adresses[orig_i]["valide"] = not a_alerte_bloquante(
                            adresses[orig_i]["alertes"]
                        )
                        st.rerun()

    if nb_pages > 1:
        pp1, pp2, pp3 = st.columns([1, 3, 1])
        with pp1:
            if st.button("← Préc.", key="prev_compo", disabled=(page == 0)):
                st.session_state["page_compo"] = page - 1
                st.rerun()
        with pp2:
            st.caption(f"Page {page + 1} / {nb_pages}")
        with pp3:
            if st.button("Suiv. →", key="next_compo", disabled=(page >= nb_pages - 1)):
                st.session_state["page_compo"] = page + 1
                st.rerun()

# ---------------------------------------------------------------------------
# Sauvegarde et suite
# ---------------------------------------------------------------------------

st.markdown("---")
if nb_bloquant:
    st.warning(f"{nb_bloquant} adresse(s) avec erreur bloquante. Vous pouvez quand même continuer.")

if st.button("Sauvegarder et générer le BAT →", type="primary"):
    with st.spinner("Sauvegarde en base…"):
        sauvegarder_adresses(dossier_id, adresses)
    st.session_state["adresses"] = adresses
    st.session_state.pop("page_compo", None)
    st.session_state.pop("filtre_compo", None)
    st.switch_page("pages/05_bat.py")
