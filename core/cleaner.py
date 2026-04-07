"""Nettoyage et normalisation des données source."""
import re
import unicodedata


# ---------------------------------------------------------------------------
# Civilités
# ---------------------------------------------------------------------------

CIVILITE_MAP = {
    # Masculin singulier
    "monsieur": "M.", "m": "M.", "mr": "M.", "m.": "M.", "mr.": "M.",
    # Féminin singulier
    "madame": "Mme", "mme": "Mme", "mme.": "Mme",
    # Mademoiselle
    "mademoiselle": "Mlle", "mlle": "Mlle", "mlle.": "Mlle",
    # Docteur
    "docteur": "Dr", "dr": "Dr", "dr.": "Dr",
    # Pluriels (multi-contacts — conservés tels quels)
    "messieurs": "Messieurs", "mm.": "Messieurs",
    "mesdames": "Mesdames",
}

INDICATEURS_PRO = {"sa", "sas", "sarl", "sci", "eurl", "sasu", "seml",
                   "association", "mairie", "commune", "département", "syndicat"}


def clean_whitespace(value: str) -> str:
    """Supprime BOM, espaces insécables, zero-width, tabs, retours ligne."""
    if not isinstance(value, str):
        value = str(value) if value is not None else ""
    value = value.replace("\ufeff", "")   # BOM
    value = value.replace("\u00a0", " ")  # espace insécable
    value = value.replace("\u200b", "")   # zero-width space
    value = value.replace("\t", " ").replace("\r", " ").replace("\n", " ")
    value = re.sub(r" +", " ", value)
    return value.strip()


def clean_civilite(value: str) -> tuple[str, bool]:
    """
    Normalise la civilité.
    Retourne (valeur_normalisée, reconnue).
    """
    v = clean_whitespace(value)
    key = v.lower().rstrip(".")
    # Essai direct
    if key in CIVILITE_MAP:
        return CIVILITE_MAP[key], True
    # Essai avec point
    if v.lower() in CIVILITE_MAP:
        return CIVILITE_MAP[v.lower()], True
    return v, False


def clean_nom(value: str) -> str:
    """Nom de famille en MAJUSCULES."""
    v = clean_whitespace(value)
    return v.upper() if v else ""


def clean_prenom(value: str) -> str:
    """
    Prénom en Format Titre.
    Gère les tirets (Jean-Pierre) et les particules (de, du, de la, d').
    """
    v = clean_whitespace(value)
    if not v:
        return ""
    PARTICULES = {"de", "du", "des", "la", "le", "les", "d"}

    def titre_mot(mot: str) -> str:
        if mot.lower() in PARTICULES:
            return mot.lower()
        if "-" in mot:
            return "-".join(p.capitalize() for p in mot.split("-"))
        return mot.capitalize()

    return " ".join(titre_mot(m) for m in v.split())


def clean_codepostal(value) -> tuple[str, bool]:
    """
    Normalise un code postal.
    Gère les flottants Excel (75001.0 → 75001).
    Retourne (valeur_normalisée, valide).
    """
    if value is None or str(value).strip() == "":
        return "", False
    v = str(value).strip()
    # Flottant Excel : 75001.0 → 75001
    if re.match(r"^\d+\.0+$", v):
        v = str(int(float(v)))
    # Nettoyage espaces
    v = re.sub(r"\s", "", v)
    if re.match(r"^\d+$", v):
        if len(v) == 4:
            v = "0" + v
        elif len(v) == 3:
            v = "00" + v
        elif len(v) == 2:
            v = "000" + v
        elif len(v) == 1:
            v = "0000" + v
        if len(v) == 5:
            return v, True
        # Trop long ou trop court
        return v, False
    # Non numérique (CEDEX, étranger…)
    return v, False


def clean_ville(value: str) -> str:
    """Ville en MAJUSCULES, espaces nettoyés, CEDEX conservé."""
    v = clean_whitespace(value)
    return v.upper() if v else ""


def clean_field(value) -> str:
    """Nettoyage générique : whitespace uniquement."""
    return clean_whitespace(str(value) if value is not None else "")


def clean_row(row: dict) -> dict:
    """
    Applique tous les nettoyages à un dict de champs internes.
    Champs attendus selon le mapping core/mapper.py.
    """
    out = {}

    for k, v in row.items():
        out[k] = clean_field(v)

    # Civilités
    for c in ("civilite_1", "civilite_2", "civilite_3"):
        if out.get(c):
            out[c], _ = clean_civilite(out[c])

    # Noms
    for n in ("nom_1", "nom_2", "nom_3"):
        if out.get(n):
            out[n] = clean_nom(out[n])

    # Prénoms
    for p in ("prenom_1", "prenom_2", "prenom_3"):
        if out.get(p):
            out[p] = clean_prenom(out[p])

    # Code postal
    if out.get("code_postal"):
        out["code_postal"], _ = clean_codepostal(out["code_postal"])

    # Ville
    if out.get("ville"):
        out["ville"] = clean_ville(out["ville"])

    # Société
    if out.get("societe"):
        out["societe"] = clean_whitespace(out["societe"])

    return out
