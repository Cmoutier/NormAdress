"""Règles de nettoyage des données d'adresse."""
import re


# ---------------------------------------------------------------------------
# Nettoyage générique des caractères
# ---------------------------------------------------------------------------

def clean_whitespace(value: str) -> str:
    """Supprime les caractères parasites et normalise les espaces."""
    if not isinstance(value, str):
        value = str(value) if value is not None else ""
    # BOM Unicode
    value = value.replace("\ufeff", "")
    # Espaces insécables U+00A0
    value = value.replace("\u00a0", " ")
    # Zero-width space U+200B
    value = value.replace("\u200b", "")
    # Tabulations et retours à la ligne
    value = re.sub(r"[\t\r\n]+", " ", value)
    # Espaces multiples
    value = re.sub(r" {2,}", " ", value)
    # Strip
    return value.strip()


# ---------------------------------------------------------------------------
# Civilité
# ---------------------------------------------------------------------------

_CIVILITE_MAP = {
    "m": "M.",
    "mr": "M.",
    "m.": "M.",
    "mr.": "M.",
    "monsieur": "M.",
    "mme": "Mme",
    "mme.": "Mme",
    "madame": "Mme",
    "mlle": "Mlle",
    "mlle.": "Mlle",
    "mademoiselle": "Mlle",
}


def clean_civilite(value: str) -> tuple[str, bool]:
    """
    Retourne (valeur_normalisée, ok).
    ok=False si la valeur n'est pas reconnue (non vide).
    """
    v = clean_whitespace(value)
    if not v:
        return "", True
    normalized = _CIVILITE_MAP.get(v.lower())
    if normalized:
        return normalized, True
    return v, False


# ---------------------------------------------------------------------------
# Nom
# ---------------------------------------------------------------------------

def clean_nom(value: str) -> str:
    v = clean_whitespace(value)
    v = re.sub(r" {2,}", " ", v.upper())
    return v.strip()


# ---------------------------------------------------------------------------
# Prénom
# ---------------------------------------------------------------------------

_PARTICULES = {"de", "du", "des", "de la", "d"}


def _title_with_hyphen(word: str) -> str:
    """Titre avec gestion des prénoms composés avec tiret."""
    parts = word.split("-")
    return "-".join(p.capitalize() for p in parts)


def clean_prenom(value: str) -> str:
    v = clean_whitespace(value)
    if not v:
        return ""
    words = v.split()
    result = []
    i = 0
    while i < len(words):
        w = words[i].lower()
        # Détecter "de la" (2 mots)
        if w == "de" and i + 1 < len(words) and words[i + 1].lower() == "la":
            result.append("de")
            result.append("la")
            i += 2
            continue
        if w in _PARTICULES:
            result.append(w)
        else:
            result.append(_title_with_hyphen(words[i]))
        i += 1
    return " ".join(result)


# ---------------------------------------------------------------------------
# Code postal
# ---------------------------------------------------------------------------

def clean_codepostal(value: str) -> tuple[str, bool]:
    """
    Retourne (valeur_normalisée, ok).
    ok=False si la valeur est invalide.
    """
    v = clean_whitespace(value)
    v = v.replace(" ", "")
    if not v:
        return "", True
    if not v.isdigit():
        return v, False
    n = int(v)
    length = len(v.lstrip("0") or "0")
    if len(v) == 5:
        return v, True
    if 1000 <= n <= 9999:
        return f"0{v}", True
    if 100 <= n <= 999:
        return f"00{v}", True
    if len(v) == 5:
        return v, True
    # Tenter un zero-pad si entre 1 et 5 chiffres
    if 1 <= len(v) <= 4:
        return v.zfill(5), True
    return v, False


# ---------------------------------------------------------------------------
# Ville
# ---------------------------------------------------------------------------

def clean_ville(value: str) -> str:
    v = clean_whitespace(value)
    v = re.sub(r" {2,}", " ", v.upper())
    return v.strip()


# ---------------------------------------------------------------------------
# Champ générique (Societe, Adresse1/2/3)
# ---------------------------------------------------------------------------

def clean_generic(value: str) -> str:
    return clean_whitespace(value)


# ---------------------------------------------------------------------------
# Application de toutes les règles à un DataFrame
# ---------------------------------------------------------------------------

def apply_rules(df, options: dict | None = None) -> tuple:
    """
    Applique les règles de nettoyage au DataFrame.
    options: dict de {règle: bool} pour activer/désactiver.
    Retourne (df_clean, rapport_lignes) où rapport_lignes est une liste de dicts.
    """
    import pandas as pd

    if options is None:
        options = {}

    df = df.copy()
    rapport = []

    # Colonnes présentes
    cols = set(df.columns)

    def _apply_col(col, clean_fn, check_fn=None):
        if col not in cols:
            return
        for idx in df.index:
            raw = df.at[idx, col]
            if callable(check_fn):
                new_val, ok = check_fn(raw)
                if not ok and new_val:
                    rapport.append({
                        "ligne": idx + 2,
                        "colonne": col,
                        "valeur": raw,
                        "message": f"Valeur non reconnue pour {col} : «{raw}»",
                        "type": "warning",
                    })
            else:
                new_val = clean_fn(raw)
            if str(new_val) != str(raw):
                df.at[idx, col] = new_val

    # Espaces sur toutes les colonnes
    if options.get("espaces", True):
        for col in cols:
            for idx in df.index:
                df.at[idx, col] = clean_whitespace(str(df.at[idx, col]))

    # Civilité
    if options.get("civilite", True) and "Civilite" in cols:
        for idx in df.index:
            raw = df.at[idx, "Civilite"]
            new_val, ok = clean_civilite(str(raw))
            if not ok and str(raw).strip():
                rapport.append({
                    "ligne": idx + 2,
                    "colonne": "Civilite",
                    "valeur": raw,
                    "message": f"Civilité non reconnue : «{raw}»",
                    "type": "warning",
                })
            df.at[idx, "Civilite"] = new_val

    # Nom
    if options.get("nom", True) and "Nom" in cols:
        for idx in df.index:
            df.at[idx, "Nom"] = clean_nom(str(df.at[idx, "Nom"]))

    # Prénom
    if options.get("prenom", True) and "Prenom" in cols:
        for idx in df.index:
            df.at[idx, "Prenom"] = clean_prenom(str(df.at[idx, "Prenom"]))

    # Code postal
    if options.get("codepostal", True) and "CodePostal" in cols:
        for idx in df.index:
            raw = df.at[idx, "CodePostal"]
            new_val, ok = clean_codepostal(str(raw))
            if not ok and str(raw).strip():
                rapport.append({
                    "ligne": idx + 2,
                    "colonne": "CodePostal",
                    "valeur": raw,
                    "message": f"Code postal invalide : «{raw}»",
                    "type": "error",
                })
            df.at[idx, "CodePostal"] = new_val

    # Ville
    if options.get("ville", True) and "Ville" in cols:
        for idx in df.index:
            df.at[idx, "Ville"] = clean_ville(str(df.at[idx, "Ville"]))

    # Champs génériques
    for field in ["Societe", "Adresse1", "Adresse2", "Adresse3"]:
        if field in cols:
            for idx in df.index:
                df.at[idx, field] = clean_generic(str(df.at[idx, field]))

    return df, rapport
