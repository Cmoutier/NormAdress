"""Détection du type de contact (particulier / professionnel) et du mode de distribution."""
import re

INDICATEURS_PRO = {
    "sa", "sas", "sarl", "sci", "eurl", "sasu", "seml",
    "association", "mairie", "commune", "département", "syndicat",
    "établissement", "fondation", "mutuelle", "caisse", "comité",
    "chambre", "fédération", "union", "groupement", "clinique",
    "hôpital", "ehpad", "résidence", "groupe",
}

CHAMPS_ADRESSE = {"adresse_voie", "code_postal", "ville"}


def detecter_type(row: dict) -> str:
    """
    Détecte si un destinataire est particulier, professionnel ou inconnu.

    Priorité :
    1. 'societe' remplie → professionnel
    2. Indicateur légal dans société → professionnel
    3. nom_1 ou prenom_1 ou identite_1 rempli → particulier
    4. Sinon → inconnu
    """
    societe = (row.get("societe") or "").strip()

    if societe:
        # Vérifie indicateur pro dans la raison sociale
        mots = re.split(r"[\s,\-\(\)/\.]+", societe.lower())
        if any(m in INDICATEURS_PRO for m in mots):
            return "professionnel"
        return "professionnel"

    if any((row.get(k) or "").strip() for k in ("nom_1", "prenom_1", "identite_1")):
        return "particulier"

    return "inconnu"


def detecter_mode_distribution(champs_mappes: set) -> str:
    """
    Si aucun champ adresse (adresse_voie, code_postal, ville) n'est mappé
    → mode BAL interne, sinon postal.
    """
    if not CHAMPS_ADRESSE.intersection(champs_mappes):
        return "bal_interne"
    return "postal"
