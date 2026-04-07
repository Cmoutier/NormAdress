"""Mapping automatique colonnes source → champs internes NormAdress."""
from __future__ import annotations
import re

CHAMPS_CIBLES = [
    # Identité contact 1
    "civilite_1", "nom_1", "prenom_1", "identite_1",
    # Identité contact 2
    "civilite_2", "nom_2", "prenom_2", "identite_2",
    # Identité contact 3
    "civilite_3", "nom_3", "prenom_3",
    # Organisation
    "societe",
    # Formule source
    "formule_source",
    # Adresse
    "adresse_voie", "adresse_comp_int", "adresse_comp_ext", "adresse_lieu_dit",
    "code_postal", "ville", "pays",
    # Identifiant
    "id_client",
]

SYNONYMS: dict[str, list[str]] = {
    "civilite_1": ["civilité", "civilite", "civ", "titre", "salutation",
                   "civilité1", "civilite1", "civ1"],
    "nom_1":      ["nom", "nom1", "name", "lastname", "nom_famille", "nom de famille"],
    "prenom_1":   ["prénom", "prenom", "prenom1", "prénom1", "firstname", "first name"],
    "identite_1": ["contact", "destinataire", "identité", "identite",
                   "nom complet", "contact 1"],

    "civilite_2": ["civilité2", "civilite2", "civ2", "civilité-2", "civilite-2",
                   "formule2", "formule-2"],
    "nom_2":      ["nom2", "nom-2", "nom 2"],
    "prenom_2":   ["prénom2", "prenom2", "prénom-2", "prenom-2", "prénom 2"],
    "identite_2": ["contact2", "contact 2", "destinataire 2"],

    "civilite_3": ["civilité3", "civilite3", "civ3", "civilité7", "civilite7",
                   "titre6", "civilité-3"],
    "nom_3":      ["nom3", "nom-3", "nom8", "nom 3"],
    "prenom_3":   ["prénom3", "prenom3", "prénom-3", "prenom-3", "prénom9", "prenom9"],

    "societe":    ["raison sociale", "société", "societe", "structure", "company",
                   "entreprise", "organisation", "établissement", "ets"],

    "formule_source": ["formule", "formule1", "formule-1", "appel", "politesse"],

    "adresse_voie":     ["rue", "voie", "adresse", "adresse1", "rue1", "adresse 1",
                         "rue 1", "address", "adr", "n° et libellé", "libellé voie"],
    "adresse_comp_int": ["adresse2", "rue2", "adresse 2", "rue 2", "complement",
                         "complément", "appt", "appartement", "étage", "compl int"],
    "adresse_comp_ext": ["adresse3", "rue3", "adresse 3", "rue 3", "bâtiment",
                         "batiment", "résidence", "residence", "compl ext"],
    "adresse_lieu_dit": ["lieu-dit", "lieu dit", "lieudit", "bp", "boîte postale",
                         "service", "cs", "tsa"],

    "code_postal": ["cp", "code postal", "codepostal", "zip", "postal", "code_postal",
                    "code postale", "c.p."],
    "ville":       ["ville", "city", "commune", "localité", "localite"],
    "pays":        ["pays", "country", "nation"],

    "id_client":   ["id", "identifiant", "référence", "ref", "numéro", "numero",
                    "code client", "n°"],
}


def normaliser_cle(s: str) -> str:
    """Minuscules + suppression de tout ce qui n'est pas alphanumérique."""
    return re.sub(r"[^a-z0-9]", "", s.lower().strip())


def auto_map(columns: list[str]) -> dict[str, str]:
    """
    Associe automatiquement les colonnes source aux champs cibles via synonymes.
    Retourne {colonne_source: champ_cible}.
    """
    # Pré-calcul : clé normalisée → champ cible
    index: dict[str, str] = {}
    for champ, syns in SYNONYMS.items():
        # Le nom du champ lui-même
        index[normaliser_cle(champ)] = champ
        for s in syns:
            index[normaliser_cle(s)] = champ

    mapping: dict[str, str] = {}
    champs_pris: set[str] = set()

    for col in columns:
        cle = normaliser_cle(col)
        champ = index.get(cle)
        if champ and champ not in champs_pris:
            mapping[col] = champ
            champs_pris.add(champ)

    return mapping


def construire_df_mappe(df, mapping: dict[str, str]):
    """
    Construit un DataFrame avec les noms de champs internes
    à partir du mapping {col_source: champ_cible}.
    """
    import pandas as pd

    cols_source = [c for c in mapping if c in df.columns]
    df_mappe = df[cols_source].rename(columns=mapping).copy()

    # S'assurer que tous les champs cibles existent (vide si absent)
    for champ in CHAMPS_CIBLES:
        if champ not in df_mappe.columns:
            df_mappe[champ] = ""

    return df_mappe
