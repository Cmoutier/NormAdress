"""
Règles La Poste — Norme NF Z 10-011 et RNVP
(Restructuration, Normalisation et Validation Postale)

Sources :
- Norme AFNOR NF Z 10-011 : structure des adresses postales françaises
- Guide La Poste "6 règles d'or pour l'écriture des adresses"
- RNVP La Poste : règles de normalisation des libellés de voies

Structure normalisée en 6 lignes :
  L1 — Identité du destinataire (Civilité Prénom NOM)
  L2 — Complément d'identité (service, bâtiment, appartement)  ← Adresse3
  L3 — Numéro et libellé de la voie                            ← Adresse1
  L4 — Lieu-dit ou BP/CS                                       ← Adresse2
  L5 — Code postal + Localité (+ CEDEX éventuellement)
  L6 — Pays (international uniquement)
"""

import re
import unicodedata
import pandas as pd


# ---------------------------------------------------------------------------
# Règle 1 : Majuscules sans accent (norme OCR La Poste)
# ---------------------------------------------------------------------------

def remove_accents(value: str) -> str:
    """
    Supprime les accents pour la lecture optique (OCR).
    É→E, À→A, Ç→C, Ô→O, etc.
    Conserve les caractères non latins tels quels.
    """
    normalized = unicodedata.normalize("NFD", value)
    return "".join(c for c in normalized if unicodedata.category(c) != "Mn")


def normalize_for_postal(value: str) -> str:
    """Majuscules + suppression des accents (norme La Poste)."""
    return remove_accents(value.upper())


# ---------------------------------------------------------------------------
# Règle 2 : Abréviations normalisées des types de voie (RNVP)
# ---------------------------------------------------------------------------

# Table officielle La Poste (extrait principal — RNVP)
VOIE_ABREVIATIONS = {
    "ALLEE":        "ALL",
    "ALLEES":       "ALL",
    "AVENUE":       "AV",
    "AVENUES":      "AV",
    "BOULEVARD":    "BD",
    "BOULEVARDS":   "BD",
    "CHEMIN":       "CHE",
    "CHEMINS":      "CHE",
    "CITE":         "CIT",
    "CITES":        "CIT",
    "DOMAINE":      "DOM",
    "DOMAINES":     "DOM",
    "ESPLANADE":    "ESP",
    "ESPLANADES":   "ESP",
    "HAMEAU":       "HAM",
    "HAMEAUX":      "HAM",
    "IMPASSE":      "IMP",
    "IMPASSES":     "IMP",
    "LIEU DIT":     "LD",
    "LIEU-DIT":     "LD",
    "LOTISSEMENT":  "LOT",
    "LOTISSEMENTS": "LOT",
    "PASSAGE":      "PAS",
    "PASSAGES":     "PAS",
    "PLACE":        "PL",
    "PLACES":       "PL",
    "RESIDENCE":    "RES",
    "RESIDENCES":   "RES",
    "ROUTE":        "RTE",
    "ROUTES":       "RTE",
    "RUE":          "RUE",  # RUE reste RUE selon la norme
    "RUES":         "RUE",
    "SQUARE":       "SQ",
    "SQUARES":      "SQ",
    "VILLA":        "VLA",
    "VILLAS":       "VLA",
    "VOIE":         "VOI",
    "VOIES":        "VOI",
    "ZONE":         "ZI",   # zone industrielle
    "ZONE INDUSTRIELLE": "ZI",
    "ZONE ARTISANALE":   "ZA",
    "ZONE COMMERCIALE":  "ZC",
    "ZONE D ACTIVITE":   "ZAC",
    "ZONE D ACTIVITES":  "ZAC",
}

# Regex qui match un type de voie en début ou milieu de chaîne
_VOIE_RE = re.compile(
    r"\b(" + "|".join(re.escape(k) for k in sorted(VOIE_ABREVIATIONS, key=len, reverse=True)) + r")\b"
)


def normalize_voie(adresse: str) -> str:
    """
    Normalise les libellés de voie selon la table RNVP La Poste.
    Entrée en MAJUSCULES (appeler après normalize_for_postal).
    Ex : '10 AVENUE DES FLEURS' → '10 AV DES FLEURS'
    """
    if not adresse:
        return adresse
    return _VOIE_RE.sub(lambda m: VOIE_ABREVIATIONS[m.group(1)], adresse)


# ---------------------------------------------------------------------------
# Règle 3 : Suppression de la ponctuation parasite dans les adresses
# ---------------------------------------------------------------------------

def clean_address_punctuation(value: str) -> str:
    """
    Supprime la ponctuation non significative dans les champs d'adresse.
    Conserve : tirets (noms composés), apostrophes (chemin de l'...), slash (BP/CS).
    Supprime : virgules, points finaux, points-virgules, parenthèses.
    """
    # Virgules → espace
    value = re.sub(r",", " ", value)
    # Points en fin de mot (sauf abréviations type BP.) → supprimer
    value = re.sub(r"\.(?=\s|$)", "", value)
    # Parenthèses
    value = re.sub(r"[(){}[\]]", "", value)
    # Points-virgules
    value = re.sub(r";", " ", value)
    # Espaces multiples
    value = re.sub(r" {2,}", " ", value)
    return value.strip()


# ---------------------------------------------------------------------------
# Règle 4 : BP / CS — Boîte Postale et Courrier Spécial
# ---------------------------------------------------------------------------

_BP_RE = re.compile(r"\b(B\.?P\.?)\s*(\d+)\b", re.IGNORECASE)
_CS_RE = re.compile(r"\b(C\.?S\.?)\s*(\d+)\b", re.IGNORECASE)
_TSA_RE = re.compile(r"\b(TSA)\s*(\d+)\b", re.IGNORECASE)


def normalize_bp_cs(value: str) -> str:
    """
    Normalise les mentions BP, CS, TSA selon la norme La Poste.
    Ex : 'b.p.123' → 'BP 123', 'CS70001' → 'CS 70001'
    """
    value = _BP_RE.sub(lambda m: f"BP {m.group(2)}", value)
    value = _CS_RE.sub(lambda m: f"CS {m.group(2)}", value)
    value = _TSA_RE.sub(lambda m: f"TSA {m.group(2)}", value)
    return value


# ---------------------------------------------------------------------------
# Règle 5 : Mention "À L'ATTENTION DE" (adressage professionnel)
# ---------------------------------------------------------------------------

def format_attention(civilite: str, prenom: str, nom: str) -> str:
    """
    Génère la mention réglementaire pour l'adressage B2B.
    Ex : 'À L'ATTENTION DE M. JEAN DUPONT'
    """
    parts = [p.strip() for p in [civilite, prenom, nom] if p.strip()]
    if not parts:
        return ""
    return "A L'ATTENTION DE " + " ".join(parts)


# ---------------------------------------------------------------------------
# Règle 6 : Validation de complétude selon la norme
# ---------------------------------------------------------------------------

CHAMPS_OBLIGATOIRES_POSTAL = ["Adresse1", "CodePostal", "Ville"]
CHAMPS_IDENTITE = ["Nom", "Societe"]


def check_completude(df: pd.DataFrame) -> list[dict]:
    """
    Vérifie la complétude des adresses selon la norme NF Z 10-011.
    Une adresse postale valide doit avoir AU MINIMUM :
    - Une ligne d'identité (Nom OU Société)
    - Une ligne de voie (Adresse1)
    - Un code postal (5 chiffres)
    - Une localité (Ville)
    """
    alerts = []
    cols = set(df.columns)

    for idx in df.index:
        manquants = []

        # Identité
        a_identite = any(
            str(df.at[idx, c]).strip()
            for c in CHAMPS_IDENTITE if c in cols
        )
        if not a_identite:
            manquants.append("identité (Nom ou Société)")

        # Champs obligatoires
        for champ in CHAMPS_OBLIGATOIRES_POSTAL:
            if champ in cols and not str(df.at[idx, champ]).strip():
                manquants.append(champ)

        if manquants:
            alerts.append({
                "ligne": idx + 2,
                "type": "Adresse incomplète (norme La Poste)",
                "champs": [c for c in CHAMPS_OBLIGATOIRES_POSTAL + CHAMPS_IDENTITE if c in cols],
                "message": f"Champs manquants : {', '.join(manquants)}",
                "suggestion": "Cette adresse ne respecte pas la norme NF Z 10-011 — elle ne peut pas être acheminée",
                "auto_fixable": False,
            })

    return alerts


# ---------------------------------------------------------------------------
# Application au DataFrame
# ---------------------------------------------------------------------------

def apply_laposte_rules(df: pd.DataFrame, options: dict) -> tuple[pd.DataFrame, list[dict]]:
    """
    Applique les règles La Poste sélectionnées.
    options:
      - "desaccentuation": bool  — supprimer les accents (OCR)
      - "abreviations_voies": bool — normaliser les types de voies
      - "ponctuation_adresse": bool — nettoyer la ponctuation dans les adresses
      - "bp_cs": bool — normaliser BP/CS/TSA
      - "completude": bool — valider la complétude
    """
    df = df.copy()
    alerts = []
    cols = set(df.columns)

    adresse_fields = [f for f in ["Adresse1", "Adresse2", "Adresse3"] if f in cols]

    # BP / CS
    if options.get("bp_cs", True):
        for field in adresse_fields:
            for idx in df.index:
                v = str(df.at[idx, field])
                fixed = normalize_bp_cs(v)
                if fixed != v:
                    df.at[idx, field] = fixed

    # Ponctuation parasite dans les adresses
    if options.get("ponctuation_adresse", True):
        for field in adresse_fields:
            for idx in df.index:
                v = str(df.at[idx, field])
                fixed = clean_address_punctuation(v)
                if fixed != v:
                    df.at[idx, field] = fixed

    # Abréviations des voies (nécessite majuscules d'abord)
    if options.get("abreviations_voies", False):
        for field in adresse_fields:
            for idx in df.index:
                v = str(df.at[idx, field]).upper()
                v = remove_accents(v)
                fixed = normalize_voie(v)
                df.at[idx, field] = fixed

    # Désaccentuation (Nom, Ville, Adresses, Société)
    if options.get("desaccentuation", False):
        for field in (adresse_fields + ["Nom", "Ville", "Societe"]):
            if field not in cols:
                continue
            for idx in df.index:
                v = str(df.at[idx, field])
                fixed = remove_accents(v)
                if fixed != v:
                    df.at[idx, field] = fixed

    # Validation de complétude
    if options.get("completude", True):
        alerts.extend(check_completude(df))

    return df, alerts


# ---------------------------------------------------------------------------
# Format enveloppe — structure NF Z 10-011
# ---------------------------------------------------------------------------

def format_envelope_lines(row: dict) -> list[tuple[str, str]]:
    """
    Retourne les lignes d'adresse selon la norme La Poste NF Z 10-011.
    Chaque tuple : (numéro_ligne, contenu)

    Structure :
      L1 — Raison sociale OU Civilité Prénom NOM
      L2 — Complément identité (contact B2B)
      L3 — Adresse3 : bâtiment, résidence, étage
      L4 — Adresse1 : N° et libellé de voie  (ligne obligatoire)
      L5 — Adresse2 : BP, lieu-dit, complément de distribution
      L6 — CODE POSTAL  VILLE
    """
    civ     = str(row.get("Civilite",   "")).strip()
    prenom  = str(row.get("Prenom",     "")).strip()
    nom     = str(row.get("Nom",        "")).strip()
    societe = str(row.get("Societe",    "")).strip()
    adr1    = str(row.get("Adresse1",   "")).strip()
    adr2    = str(row.get("Adresse2",   "")).strip()
    adr3    = str(row.get("Adresse3",   "")).strip()
    cp      = str(row.get("CodePostal", "")).strip()
    ville   = str(row.get("Ville",      "")).strip()

    contact = " ".join(p for p in [civ, prenom, nom] if p)
    lines: list[tuple[str, str]] = []

    if societe:
        lines.append(("L1", societe))
        if contact:
            lines.append(("L2", contact))
    elif contact:
        lines.append(("L1", contact))

    if adr3:
        lines.append(("L3", adr3))
    if adr1:
        lines.append(("L4", adr1))
    if adr2:
        lines.append(("L5", adr2))

    cp_ville = " ".join(p for p in [cp, ville] if p)
    if cp_ville:
        lines.append(("L6", cp_ville))

    return lines
