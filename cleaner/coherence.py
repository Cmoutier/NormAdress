"""
Contrôles de cohérence inter-champs.
Chaque fonction retourne une liste de dicts :
  {
    "ligne": int,          # numéro de ligne (base 1, en-tête = ligne 1)
    "type": str,           # catégorie du problème
    "champs": list[str],   # champs concernés
    "message": str,        # description lisible
    "suggestion": str,     # action recommandée
    "auto_fixable": bool,  # peut être corrigé automatiquement
  }
"""
import re
import pandas as pd


# ---------------------------------------------------------------------------
# Civilité embarquée dans le champ Nom
# ---------------------------------------------------------------------------

_CIV_PREFIXES = re.compile(
    r"^(m\.|mr\.?|mme\.?|mlle\.?|dr\.?|pr\.?|me\.?|maître\.?|docteur|monsieur|madame|mademoiselle)\s+",
    re.IGNORECASE,
)


def detect_civilite_in_nom(df: pd.DataFrame) -> tuple[pd.DataFrame, list[dict]]:
    """
    Détecte et extrait la civilité embarquée dans le champ Nom.
    Ex : 'M. DUPONT' → Civilite='M.', Nom='DUPONT'
    """
    if "Nom" not in df.columns:
        return df, []

    df = df.copy()
    alerts = []

    for idx in df.index:
        nom = str(df.at[idx, "Nom"]).strip()
        m = _CIV_PREFIXES.match(nom)
        if not m:
            continue

        civ_found = m.group(1).strip()
        nom_clean = nom[m.end():].strip()

        # Ne pas écraser une civilité déjà renseignée
        existing_civ = str(df.at[idx, "Civilite"]).strip() if "Civilite" in df.columns else ""

        alerts.append({
            "ligne": idx + 2,
            "type": "Civilité dans le Nom",
            "champs": ["Nom", "Civilite"],
            "message": f"Civilité «{civ_found}» détectée dans le champ Nom : «{nom}»",
            "suggestion": f"Nom corrigé → «{nom_clean}»" + (
                f", Civilité déjà renseignée «{existing_civ}» conservée"
                if existing_civ else f", Civilité → «{civ_found}»"
            ),
            "auto_fixable": True,
        })

        df.at[idx, "Nom"] = nom_clean
        if "Civilite" in df.columns and not existing_civ:
            from cleaner.rules import clean_civilite
            new_civ, _ = clean_civilite(civ_found)
            df.at[idx, "Civilite"] = new_civ

    return df, alerts


# ---------------------------------------------------------------------------
# Nom + Prénom combinés dans un seul champ
# ---------------------------------------------------------------------------

def detect_nom_prenom_combine(df: pd.DataFrame) -> list[dict]:
    """
    Détecte les cas où le champ Nom semble contenir aussi le prénom.
    Heuristique : Nom contient au moins 2 mots ET le Prénom est vide.
    Ex : 'DUPONT Jean-Pierre' ou 'Jean-Pierre DUPONT'
    """
    if "Nom" not in df.columns:
        return []

    alerts = []
    prenom_col = "Prenom" if "Prenom" in df.columns else None

    for idx in df.index:
        nom = str(df.at[idx, "Nom"]).strip()
        prenom = str(df.at[idx, prenom_col]).strip() if prenom_col else ""

        if not nom or prenom:
            continue

        words = nom.split()
        if len(words) >= 2:
            alerts.append({
                "ligne": idx + 2,
                "type": "Nom + Prénom combinés",
                "champs": ["Nom"],
                "message": f"Le champ Nom «{nom}» semble contenir le prénom (champ Prénom vide)",
                "suggestion": "Vérifiez si ce champ doit être séparé en Nom / Prénom",
                "auto_fixable": False,
            })

    return alerts


# ---------------------------------------------------------------------------
# Société + Contact : ordre d'adressage postal
# ---------------------------------------------------------------------------

def check_societe_contact(df: pd.DataFrame) -> list[dict]:
    """
    Quand Société ET Nom/Prénom sont renseignés, vérifie la cohérence
    pour l'adressage postal professionnel.
    Norme postale : ligne contact AVANT la société dans l'adresse.
    """
    if "Societe" not in df.columns:
        return []

    alerts = []
    has_nom = "Nom" in df.columns
    has_prenom = "Prenom" in df.columns

    for idx in df.index:
        societe = str(df.at[idx, "Societe"]).strip()
        nom = str(df.at[idx, "Nom"]).strip() if has_nom else ""
        prenom = str(df.at[idx, "Prenom"]).strip() if has_prenom else ""

        if societe and (nom or prenom):
            contact = " ".join(filter(None, [nom, prenom]))
            alerts.append({
                "ligne": idx + 2,
                "type": "Société + Contact",
                "champs": ["Societe", "Nom", "Prenom"],
                "message": f"Société «{societe}» avec contact «{contact}»",
                "suggestion": (
                    "Ordre postal recommandé : Civilité + Prénom + Nom en ligne 1, "
                    "Société en ligne 2 (ou inversement selon votre convention client)"
                ),
                "auto_fixable": False,
            })

    return alerts


# ---------------------------------------------------------------------------
# CEDEX dans le champ Ville
# ---------------------------------------------------------------------------

_CEDEX_RE = re.compile(r"\bCEDEX\b\s*\d*", re.IGNORECASE)


def detect_cedex(df: pd.DataFrame) -> tuple[pd.DataFrame, list[dict]]:
    """
    Détecte CEDEX dans le champ Ville et le normalise en MAJUSCULES.
    Ex : 'Paris cedex 08' → 'PARIS CEDEX 08'
    """
    if "Ville" not in df.columns:
        return df, []

    df = df.copy()
    alerts = []

    for idx in df.index:
        ville = str(df.at[idx, "Ville"]).strip()
        if _CEDEX_RE.search(ville):
            ville_norm = _CEDEX_RE.sub(lambda m: m.group(0).upper(), ville).upper()
            alerts.append({
                "ligne": idx + 2,
                "type": "CEDEX détecté",
                "champs": ["Ville"],
                "message": f"Adresse CEDEX : «{ville}»",
                "suggestion": f"Normalisé → «{ville_norm}»",
                "auto_fixable": True,
            })
            df.at[idx, "Ville"] = ville_norm

    return df, alerts


# ---------------------------------------------------------------------------
# Adresse complète dans un seul champ
# ---------------------------------------------------------------------------

_CP_IN_TEXT = re.compile(r"\b\d{4,5}\b")
_STREET_WORDS = re.compile(
    r"\b(rue|avenue|boulevard|impasse|allée|chemin|voie|place|square|résidence|route|bd|av)\b",
    re.IGNORECASE,
)


def detect_full_address_in_field(df: pd.DataFrame) -> list[dict]:
    """
    Détecte si Adresse1 contient une adresse complète (numéro + rue + CP + ville).
    """
    if "Adresse1" not in df.columns:
        return []

    alerts = []
    for idx in df.index:
        adr = str(df.at[idx, "Adresse1"]).strip()
        if not adr:
            continue
        cp_col = str(df.at[idx, "CodePostal"]).strip() if "CodePostal" in df.columns else ""
        has_cp_in_adr = bool(_CP_IN_TEXT.search(adr))
        has_street = bool(_STREET_WORDS.search(adr))

        if has_cp_in_adr and has_street and not cp_col:
            alerts.append({
                "ligne": idx + 2,
                "type": "Adresse complète dans un seul champ",
                "champs": ["Adresse1"],
                "message": f"Adresse1 semble contenir une adresse complète avec CP : «{adr}»",
                "suggestion": "Séparez manuellement rue / code postal / ville dans les colonnes appropriées",
                "auto_fixable": False,
            })
        elif has_cp_in_adr and has_street and cp_col:
            alerts.append({
                "ligne": idx + 2,
                "type": "Code postal dans le champ Adresse",
                "champs": ["Adresse1", "CodePostal"],
                "message": f"Adresse1 contient un code postal alors que CodePostal est déjà renseigné : «{adr}»",
                "suggestion": "Vérifiez si le code postal est en doublon dans Adresse1",
                "auto_fixable": False,
            })

    return alerts


# ---------------------------------------------------------------------------
# Lignes avec nom mais sans adresse
# ---------------------------------------------------------------------------

def detect_nom_sans_adresse(df: pd.DataFrame) -> list[dict]:
    """
    Détecte les lignes qui ont un nom mais aucune adresse renseignée.
    Ces lignes sont inutilisables pour un publipostage postal.
    """
    alerts = []
    has_nom = "Nom" in df.columns or "Societe" in df.columns
    has_adr = "Adresse1" in df.columns
    has_cp = "CodePostal" in df.columns

    if not has_nom or not has_adr:
        return []

    for idx in df.index:
        nom = str(df.at[idx, "Nom"]).strip() if "Nom" in df.columns else ""
        societe = str(df.at[idx, "Societe"]).strip() if "Societe" in df.columns else ""
        adr = str(df.at[idx, "Adresse1"]).strip() if has_adr else ""
        cp = str(df.at[idx, "CodePostal"]).strip() if has_cp else ""

        if (nom or societe) and not adr and not cp:
            label = nom or societe
            alerts.append({
                "ligne": idx + 2,
                "type": "Contact sans adresse",
                "champs": ["Adresse1", "CodePostal"],
                "message": f"«{label}» n'a ni adresse ni code postal",
                "suggestion": "Cette ligne ne peut pas être utilisée pour un envoi postal",
                "auto_fixable": False,
            })

    return alerts


# ---------------------------------------------------------------------------
# Code postal au format float (75001.0 → 75001)
# ---------------------------------------------------------------------------

def fix_codepostal_float(df: pd.DataFrame) -> tuple[pd.DataFrame, list[dict]]:
    """
    Corrige les codes postaux exportés comme float par Excel : '75001.0' → '75001'.
    """
    if "CodePostal" not in df.columns:
        return df, []

    df = df.copy()
    alerts = []
    _float_re = re.compile(r"^(\d+)\.0+$")

    for idx in df.index:
        val = str(df.at[idx, "CodePostal"]).strip()
        m = _float_re.match(val)
        if m:
            fixed = m.group(1)
            alerts.append({
                "ligne": idx + 2,
                "type": "Code postal format Excel (float)",
                "champs": ["CodePostal"],
                "message": f"Code postal au format décimal : «{val}»",
                "suggestion": f"Corrigé automatiquement → «{fixed}»",
                "auto_fixable": True,
            })
            df.at[idx, "CodePostal"] = fixed

    return df, alerts


# ---------------------------------------------------------------------------
# Point d'entrée : exécuter tous les contrôles
# ---------------------------------------------------------------------------

def run_all(df: pd.DataFrame) -> tuple[pd.DataFrame, list[dict]]:
    """
    Exécute tous les contrôles de cohérence dans l'ordre logique.
    Les corrections auto sont appliquées au DataFrame retourné.
    Retourne (df_corrigé, liste_alertes).
    """
    all_alerts = []

    df, alerts = fix_codepostal_float(df)
    all_alerts.extend(alerts)

    df, alerts = detect_civilite_in_nom(df)
    all_alerts.extend(alerts)

    df, alerts = detect_cedex(df)
    all_alerts.extend(alerts)

    all_alerts.extend(detect_nom_prenom_combine(df))
    all_alerts.extend(check_societe_contact(df))
    all_alerts.extend(detect_full_address_in_field(df))
    all_alerts.extend(detect_nom_sans_adresse(df))

    return df, all_alerts
