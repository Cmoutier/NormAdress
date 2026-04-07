"""Construction des 6 lignes AFNOR XPZ-10-11 et de la Formule de politesse."""
from __future__ import annotations
from typing import Optional


# ---------------------------------------------------------------------------
# Helpers identité
# ---------------------------------------------------------------------------

def _identite(row: dict, n: int, ordre: str = "afnor") -> str:
    """
    Construit la chaîne identité pour le contact n (1, 2 ou 3).
    ordre : 'afnor' → Civilité Prénom NOM | 'alt' → Civilité NOM Prénom
    """
    identite_key = f"identite_{n}"
    if (row.get(identite_key) or "").strip():
        return row[identite_key].strip()

    civ = (row.get(f"civilite_{n}") or "").strip()
    nom = (row.get(f"nom_{n}") or "").strip()
    pre = (row.get(f"prenom_{n}") or "").strip()

    if ordre == "afnor":
        parts = [civ, pre, nom]
    else:
        parts = [civ, nom, pre]

    return " ".join(p for p in parts if p)


def _contacts_remplis(row: dict) -> list[int]:
    """Retourne la liste des indices (1, 2, 3) des contacts renseignés."""
    contacts = []
    for n in (1, 2, 3):
        has_id = (row.get(f"identite_{n}") or "").strip()
        has_nom = (row.get(f"nom_{n}") or "").strip()
        has_pre = (row.get(f"prenom_{n}") or "").strip()
        if has_id or has_nom or has_pre:
            contacts.append(n)
    return contacts


# ---------------------------------------------------------------------------
# Formule de politesse
# ---------------------------------------------------------------------------

_GENRE = {
    "M.": "m", "Mme": "f", "Mlle": "f",
    "Messieurs": "mm", "Mesdames": "ff",
    "Dr": "m",  # par défaut masculin
}


def _genre(civ: str) -> Optional[str]:
    return _GENRE.get(civ)


def generer_formule(row: dict, ordre: str = "afnor") -> str:
    """
    Génère la formule de politesse selon les contacts présents.
    Si formule_source est mappée, l'utilise telle quelle.
    """
    if (row.get("formule_source") or "").strip():
        return row["formule_source"].strip()

    contacts = _contacts_remplis(row)
    if not contacts:
        return ""

    def prenom_nom(n: int) -> str:
        pre = (row.get(f"prenom_{n}") or "").strip()
        nom = (row.get(f"nom_{n}") or "").strip()
        id_ = (row.get(f"identite_{n}") or "").strip()
        if id_:
            return id_
        if ordre == "afnor":
            return f"{pre} {nom}".strip()
        return f"{nom} {pre}".strip()

    def nom_seul(n: int) -> str:
        nom = (row.get(f"nom_{n}") or "").strip()
        id_ = (row.get(f"identite_{n}") or "").strip()
        return nom or id_

    civs = [_genre((row.get(f"civilite_{n}") or "").strip()) for n in contacts]

    if len(contacts) == 1:
        n = contacts[0]
        g = civs[0]
        pn = prenom_nom(n)
        if g == "f":
            return f"Chère Madame {pn},"
        else:
            return f"Cher Monsieur {pn},"

    if len(contacts) == 2:
        n1, n2 = contacts
        g1, g2 = civs
        pn1, pn2 = prenom_nom(n1), prenom_nom(n2)
        nn1, nn2 = nom_seul(n1), nom_seul(n2)
        if g1 == "m" and g2 == "m":
            return f"Chers Messieurs {pn1} et {pn2},"
        elif g1 == "f" and g2 == "f":
            return f"Chères Mesdames {pn1} et {pn2},"
        else:
            return f"Chers Monsieur {nn1} et Madame {nn2},"

    # 3 contacts
    parties = []
    for i, n in enumerate(contacts):
        g = civs[i]
        titre = "Madame" if g == "f" else "Monsieur"
        parties.append(f"{titre} {nom_seul(n)}")
    return "Chers " + ", ".join(parties[:-1]) + " et " + parties[-1] + ","


# ---------------------------------------------------------------------------
# Composition des 6 lignes AFNOR
# ---------------------------------------------------------------------------

def composer_adresse(row: dict, mode: str = "postal",
                     type_contact: str = "particulier",
                     format_pro: str = "A",
                     ordre: str = "afnor") -> dict:
    """
    Compose les 6 lignes AFNOR + Formule.

    Paramètres :
        mode         : 'postal' | 'bal_interne'
        type_contact : 'particulier' | 'professionnel' | 'inconnu'
        format_pro   : 'A' (L1=Société/L2=Contact) | 'B' (L1=Contact/L2=Société)
        ordre        : 'afnor' (Civ Prénom NOM) | 'alt' (Civ NOM Prénom)
    """
    societe = (row.get("societe") or "").strip()
    voie = (row.get("adresse_voie") or "").strip()
    comp_int = (row.get("adresse_comp_int") or "").strip()
    comp_ext = (row.get("adresse_comp_ext") or "").strip()
    lieu_dit = (row.get("adresse_lieu_dit") or "").strip()
    cp = (row.get("code_postal") or "").strip()
    ville = (row.get("ville") or "").strip()
    pays = (row.get("pays") or "").strip().upper()

    contacts = _contacts_remplis(row)
    id_c1 = _identite(row, 1, ordre) if contacts else ""

    l6 = f"{cp} {ville}".strip()
    if pays and pays not in ("FRANCE", "FR"):
        l6 = f"{l6} {pays}".strip()

    formule = generer_formule(row, ordre)

    if mode == "bal_interne":
        l1 = societe if societe else ""
        if contacts:
            noms_contacts = []
            for n in contacts:
                noms_contacts.append(_identite(row, n, ordre))
            l2 = "A l'attention de " + " et ".join(noms_contacts)
        else:
            l2 = ""
        return {
            "L1": l1, "L2": l2, "L3": "", "L4": "", "L5": "", "L6": "",
            "Formule": formule,
        }

    # Mode postal
    if type_contact == "particulier":
        l1 = id_c1
        l2 = comp_int
        l3 = comp_ext
        l4 = voie
        l5 = lieu_dit
        return {"L1": l1, "L2": l2, "L3": l3, "L4": l4, "L5": l5, "L6": l6,
                "Formule": formule}

    # Professionnel
    if format_pro == "A":
        l1 = societe
        l2 = id_c1
        l3 = comp_ext
        l4 = voie
        l5 = lieu_dit
    else:  # Format B
        l1 = id_c1
        l2 = societe
        l3 = comp_ext
        l4 = voie
        l5 = lieu_dit

    return {"L1": l1, "L2": l2, "L3": l3, "L4": l4, "L5": l5, "L6": l6,
            "Formule": formule}
