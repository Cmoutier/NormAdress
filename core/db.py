"""Connexion Supabase et CRUD pour dossiers, adresses, mappings."""
from __future__ import annotations
import os
import json
from functools import lru_cache

from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()


@lru_cache(maxsize=1)
def get_client() -> Client:
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_KEY"]
    return create_client(url, key)


# ---------------------------------------------------------------------------
# Dossiers
# ---------------------------------------------------------------------------

def lister_dossiers() -> list[dict]:
    db = get_client()
    res = db.table("dossiers").select("*").order("created_at", desc=True).execute()
    return res.data


def creer_dossier(nom: str, client: str, mode: str = "postal",
                  parametres: dict | None = None) -> dict:
    db = get_client()
    payload = {
        "nom": nom,
        "client": client,
        "statut": "en_cours",
        "mode_distribution": mode,
        "parametres": parametres or {},
    }
    res = db.table("dossiers").insert(payload).execute()
    return res.data[0]


def get_dossier(dossier_id: str) -> dict | None:
    db = get_client()
    res = db.table("dossiers").select("*").eq("id", dossier_id).execute()
    return res.data[0] if res.data else None


def mettre_a_jour_dossier(dossier_id: str, **kwargs) -> dict:
    db = get_client()
    res = db.table("dossiers").update(kwargs).eq("id", dossier_id).execute()
    return res.data[0]


def changer_statut(dossier_id: str, statut: str) -> dict:
    return mettre_a_jour_dossier(dossier_id, statut=statut)


def mettre_a_jour_parametres(dossier_id: str, parametres: dict) -> dict:
    return mettre_a_jour_dossier(dossier_id, parametres=parametres)


# ---------------------------------------------------------------------------
# Mappings
# ---------------------------------------------------------------------------

def sauvegarder_mapping(dossier_id: str, mapping: dict[str, str]) -> None:
    """Remplace tous les mappings du dossier."""
    db = get_client()
    db.table("mappings").delete().eq("dossier_id", dossier_id).execute()
    if not mapping:
        return
    rows = [
        {"dossier_id": dossier_id, "colonne_source": k, "champ_cible": v}
        for k, v in mapping.items()
    ]
    db.table("mappings").insert(rows).execute()


def charger_mapping(dossier_id: str) -> dict[str, str]:
    db = get_client()
    res = db.table("mappings").select("*").eq("dossier_id", dossier_id).execute()
    return {r["colonne_source"]: r["champ_cible"] for r in res.data}


# ---------------------------------------------------------------------------
# Adresses
# ---------------------------------------------------------------------------

def sauvegarder_adresses(dossier_id: str, adresses: list[dict]) -> None:
    """Remplace toutes les adresses du dossier."""
    db = get_client()
    db.table("adresses").delete().eq("dossier_id", dossier_id).execute()
    if not adresses:
        return
    rows = []
    def _trunc(v: str, n: int = 38) -> str:
        return (v or "")[:n]

    for i, a in enumerate(adresses):
        rows.append({
            "dossier_id": dossier_id,
            "ligne_source": i + 1,
            "type_contact": a.get("type_contact", "inconnu"),
            "type_detecte_auto": a.get("type_detecte_auto", True),
            "formule": (a.get("Formule") or "")[:200],
            "l1": _trunc(a.get("L1", "")),
            "l2": _trunc(a.get("L2", "")),
            "l3": _trunc(a.get("L3", "")),
            "l4": _trunc(a.get("L4", "")),
            "l5": _trunc(a.get("L5", "")),
            "l6": _trunc(a.get("L6", "")),
            "alertes": a.get("alertes", []),
            "valide": a.get("valide", False),
        })
    # Insertion par lots de 500
    for i in range(0, len(rows), 500):
        db.table("adresses").insert(rows[i:i+500]).execute()


def charger_adresses(dossier_id: str) -> list[dict]:
    db = get_client()
    res = (db.table("adresses")
           .select("*")
           .eq("dossier_id", dossier_id)
           .order("ligne_source")
           .execute())
    return res.data


def mettre_a_jour_adresse(adresse_id: str, **kwargs) -> dict:
    db = get_client()
    res = db.table("adresses").update(kwargs).eq("id", adresse_id).execute()
    return res.data[0]
