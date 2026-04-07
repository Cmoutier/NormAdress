"""Contrôles qualité AFNOR XPZ-10-11."""
from __future__ import annotations
import re

LONGUEUR_MAX = 38  # norme AFNOR


def valider_adresse(adresse: dict, mode: str = "postal") -> list[dict]:
    """
    Valide les 6 lignes AFNOR et retourne une liste d'alertes.
    adresse : dict avec clés L1 à L6 + Formule (+ pays optionnel)
    mode    : 'postal' | 'bal_interne'
    """
    alertes = []

    # Longueur des lignes
    for ligne in ("L1", "L2", "L3", "L4", "L5", "L6"):
        val = (adresse.get(ligne) or "").strip()
        if val and len(val) > LONGUEUR_MAX:
            alertes.append({
                "code": "LONGUEUR",
                "ligne": ligne,
                "message": f"{ligne} dépasse 38 car. ({len(val)} car.)",
                "bloquant": False,
            })

    if mode == "bal_interne":
        alertes.append({
            "code": "BAL_INTERNE",
            "ligne": "",
            "message": "Mode BAL interne — non conforme AFNOR, non bloquant",
            "bloquant": False,
        })
        return alertes

    # Mode postal — champs obligatoires
    l4 = (adresse.get("L4") or "").strip()
    l6 = (adresse.get("L6") or "").strip()

    if not l4:
        alertes.append({
            "code": "L4_VIDE",
            "ligne": "L4",
            "message": "Voie manquante — adresse incomplète",
            "bloquant": True,
        })

    if not l6:
        alertes.append({
            "code": "L6_VIDE",
            "ligne": "L6",
            "message": "CP/Ville manquants — adresse incomplète",
            "bloquant": True,
        })
    else:
        m = re.match(r"^(\d{5})", l6)
        if not m:
            alertes.append({
                "code": "CP_INVALIDE_FR",
                "ligne": "L6",
                "message": f"CP '{l6[:10]}' non conforme (5 chiffres attendus)",
                "bloquant": False,
            })

        # Adresse étrangère : uniquement si le champ pays est renseigné et non français
        pays = (adresse.get("pays") or "").strip().upper()
        if pays and pays not in ("FRANCE", "FR", ""):
            alertes.append({
                "code": "ETRANGER",
                "ligne": "L6",
                "message": f"Adresse étrangère ({pays}) — vérification recommandée",
                "bloquant": False,
            })

    # L1 vide
    l1 = (adresse.get("L1") or "").strip()
    if not l1:
        alertes.append({
            "code": "L1_VIDE",
            "ligne": "L1",
            "message": "Ligne 1 vide — destinataire non identifié",
            "bloquant": False,
        })

    return alertes


def a_alerte_bloquante(alertes: list[dict]) -> bool:
    return any(a["bloquant"] for a in alertes)
