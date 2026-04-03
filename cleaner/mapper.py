"""Mapping automatique colonnes source → champs standards."""
import re

STANDARD_FIELDS = [
    "Civilite",
    "Nom",
    "Prenom",
    "Societe",
    "Adresse1",
    "Adresse2",
    "Adresse3",
    "CodePostal",
    "Ville",
]

SYNONYMS = {
    "Civilite": ["civilite", "civ", "titre", "title", "gender", "sexe", "salutation", "mrmme"],
    "Nom": ["nom", "name", "lastname", "last_name", "nom_famille", "surname", "nomdefamille"],
    "Prenom": ["prenom", "prenom", "firstname", "first_name", "forename", "prenoms"],
    "Societe": ["societe", "societe", "company", "entreprise", "organization", "raisonsociale", "raison_sociale"],
    "Adresse1": ["adresse1", "adresse", "address", "rue", "street", "adr1", "voie", "ligne1"],
    "Adresse2": ["adresse2", "complement", "address2", "adr2", "complement_adresse", "ligne2"],
    "Adresse3": ["adresse3", "address3", "adr3", "ligne3", "batiment", "immeuble", "residence"],
    "CodePostal": ["codepostal", "code_postal", "cp", "zip", "postal", "postcode"],
    "Ville": ["ville", "city", "commune", "town", "localite"],
}


def normalize_key(s: str) -> str:
    """Minuscules + suppression de tout ce qui n'est pas alphanumérique."""
    s = s.lower()
    s = re.sub(r"[^a-z0-9]", "", s)
    # Supprimer les accents courants
    replacements = {
        "é": "e", "è": "e", "ê": "e", "ë": "e",
        "à": "a", "â": "a", "ä": "a",
        "î": "i", "ï": "i",
        "ô": "o", "ö": "o",
        "ù": "u", "û": "u", "ü": "u",
        "ç": "c",
    }
    # Appliqué avant la suppression des non-alphanum
    return s


def normalize_col(col: str) -> str:
    col_lower = col.lower()
    for old, new in [
        ("é", "e"), ("è", "e"), ("ê", "e"), ("ë", "e"),
        ("à", "a"), ("â", "a"), ("ä", "a"),
        ("î", "i"), ("ï", "i"),
        ("ô", "o"), ("ö", "o"),
        ("ù", "u"), ("û", "u"), ("ü", "u"),
        ("ç", "c"),
    ]:
        col_lower = col_lower.replace(old, new)
    return re.sub(r"[^a-z0-9]", "", col_lower)


def auto_map(columns: list[str]) -> dict[str, str]:
    """
    Retourne un dict {colonne_source: champ_standard | ''}.
    Si plusieurs colonnes matchent le même champ, elles sont toutes mappées.
    """
    mapping = {}
    for col in columns:
        norm = normalize_col(col)
        matched = ""
        for field, synonyms in SYNONYMS.items():
            if norm in synonyms:
                matched = field
                break
        mapping[col] = matched
    return mapping


def detect_multi_contacts(mapping: dict[str, str]) -> dict[str, list[str]]:
    """
    Retourne les champs qui ont plusieurs colonnes sources associées.
    Ex: {"Nom": ["Nom_contact1", "Nom_contact2"]}
    """
    from collections import defaultdict
    field_to_cols = defaultdict(list)
    for col, field in mapping.items():
        if field:
            field_to_cols[field].append(col)
    return {field: cols for field, cols in field_to_cols.items() if len(cols) > 1}
