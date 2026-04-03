"""Consolidation des lignes d'adresse et éclatement multi-contacts."""
import pandas as pd
from .mapper import STANDARD_FIELDS


# ---------------------------------------------------------------------------
# Consolidation Adresse1/2/3
# ---------------------------------------------------------------------------

def consolidate_addresses(df: pd.DataFrame) -> tuple[pd.DataFrame, list[dict]]:
    """
    RÈGLE CRITIQUE : Adresse1 ne doit JAMAIS être vide si Adresse2 ou Adresse3 est remplie.
    Retourne (df_modifié, journal).
    """
    df = df.copy()
    journal = []
    cols = set(df.columns)

    has_a1 = "Adresse1" in cols
    has_a2 = "Adresse2" in cols
    has_a3 = "Adresse3" in cols

    for idx in df.index:
        a1 = df.at[idx, "Adresse1"].strip() if has_a1 else ""
        a2 = df.at[idx, "Adresse2"].strip() if has_a2 else ""
        a3 = df.at[idx, "Adresse3"].strip() if has_a3 else ""

        before = {"Adresse1": a1, "Adresse2": a2, "Adresse3": a3}

        if not a1 and a2:
            # Adresse1 vide, Adresse2 remplie → décaler
            a1, a2, a3 = a2, a3, ""
        elif not a1 and not a2 and a3:
            # Adresse1 et 2 vides, Adresse3 remplie → décaler
            a1, a2, a3 = a3, "", ""

        after = {"Adresse1": a1, "Adresse2": a2, "Adresse3": a3}

        if before != after:
            journal.append({
                "ligne": idx + 2,
                "avant": before,
                "apres": after,
                "message": f"Ligne {idx + 2} : consolidation adresse",
                "type": "consolidation",
            })
            if has_a1:
                df.at[idx, "Adresse1"] = a1
            if has_a2:
                df.at[idx, "Adresse2"] = a2
            if has_a3:
                df.at[idx, "Adresse3"] = a3

    return df, journal


# ---------------------------------------------------------------------------
# Suppression des lignes vides
# ---------------------------------------------------------------------------

def remove_empty_rows(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """
    Une ligne est vide si Nom ET Adresse1 ET CodePostal sont tous vides.
    Retourne (df_filtré, nb_supprimées).
    """
    def is_empty(row):
        nom = row.get("Nom", "").strip() if isinstance(row.get("Nom"), str) else ""
        adr = row.get("Adresse1", "").strip() if isinstance(row.get("Adresse1"), str) else ""
        cp = row.get("CodePostal", "").strip() if isinstance(row.get("CodePostal"), str) else ""
        return not nom and not adr and not cp

    mask = df.apply(is_empty, axis=1)
    nb_removed = mask.sum()
    return df[~mask].reset_index(drop=True), int(nb_removed)


# ---------------------------------------------------------------------------
# Détection des doublons
# ---------------------------------------------------------------------------

def detect_duplicates(df: pd.DataFrame) -> list[dict]:
    """
    Doublon si Nom + CodePostal identiques (en minuscules, après nettoyage).
    Retourne liste de dicts avec info sur les doublons — ne supprime PAS.
    """
    if "Nom" not in df.columns or "CodePostal" not in df.columns:
        return []

    key = (
        df["Nom"].str.lower().str.strip()
        + "|"
        + df["CodePostal"].str.lower().str.strip()
    )
    duplicated_mask = key.duplicated(keep=False)
    duplicates = []
    seen = set()

    for idx in df[duplicated_mask].index:
        k = key[idx]
        if k not in seen:
            seen.add(k)
            group_idxs = df.index[key == k].tolist()
            duplicates.append({
                "cle": k,
                "lignes": [i + 2 for i in group_idxs],
                "nom": df.at[group_idxs[0], "Nom"],
                "codepostal": df.at[group_idxs[0], "CodePostal"],
            })

    return duplicates


# ---------------------------------------------------------------------------
# Éclatement multi-contacts
# ---------------------------------------------------------------------------

COMMON_FIELDS = ["Societe", "Adresse1", "Adresse2", "Adresse3", "CodePostal", "Ville"]
PERSONAL_FIELDS = ["Civilite", "Nom", "Prenom"]


def explode_multi_contacts(
    df: pd.DataFrame,
    multi_contacts: dict[str, list[str]],
    source_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Éclate les lignes multi-contacts.
    multi_contacts: {champ_standard: [col_source_1, col_source_2, ...]}
    source_df: le DataFrame source AVANT mapping (pour retrouver les colonnes brutes).

    Retourne un nouveau DataFrame avec une ligne par contact.
    """
    # Nombre de contacts par groupe
    n_contacts = max(len(v) for v in multi_contacts.values())
    rows = []

    for idx in df.index:
        for i in range(n_contacts):
            new_row = {}
            for field in STANDARD_FIELDS:
                if field in multi_contacts:
                    cols_for_field = multi_contacts[field]
                    if i < len(cols_for_field):
                        # Valeur du i-ème contact pour ce champ
                        src_col = cols_for_field[i]
                        new_row[field] = source_df.at[idx, src_col] if src_col in source_df.columns else ""
                    else:
                        new_row[field] = ""
                else:
                    new_row[field] = df.at[idx, field] if field in df.columns else ""
            # Ne pas créer de ligne si tous les champs personnels sont vides
            personal_empty = all(
                not str(new_row.get(f, "")).strip() for f in PERSONAL_FIELDS
            )
            if not personal_empty:
                rows.append(new_row)

    if not rows:
        return df

    return pd.DataFrame(rows, columns=STANDARD_FIELDS)
