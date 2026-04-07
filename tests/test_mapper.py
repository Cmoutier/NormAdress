"""Tests core/mapper.py"""
import pandas as pd
import pytest
from core.mapper import auto_map, normaliser_cle, construire_df_mappe, CHAMPS_CIBLES


class TestNormaliserCle:
    def test_minuscules(self):
        assert normaliser_cle("NOM") == "nom"

    def test_accents(self):
        assert normaliser_cle("Prénom") == "prnom"

    def test_tirets_espaces(self):
        assert normaliser_cle("Raison Sociale") == "raisonsociale"

    def test_chiffres(self):
        assert normaliser_cle("Nom-1") == "nom1"


class TestAutoMap:
    def test_nom_standard(self):
        m = auto_map(["Nom", "Prénom", "Ville"])
        assert m.get("Nom") == "nom_1"
        assert m.get("Prénom") == "prenom_1"
        assert m.get("Ville") == "ville"

    def test_synonyme_societe(self):
        m = auto_map(["Structure", "Adresse", "CP"])
        assert m.get("Structure") == "societe"

    def test_synonyme_cp(self):
        m = auto_map(["Code Postal"])
        assert m.get("Code Postal") == "code_postal"

    def test_synonyme_rue(self):
        m = auto_map(["Rue 1", "Rue 2"])
        assert m.get("Rue 1") == "adresse_voie"
        assert m.get("Rue 2") == "adresse_comp_int"

    def test_pas_de_doublon_champ(self):
        # Deux colonnes qui mappent au même champ → seule la première est prise
        m = auto_map(["Nom", "name"])
        valeurs = list(m.values())
        assert valeurs.count("nom_1") == 1

    def test_colonne_inconnue_ignoree(self):
        m = auto_map(["ColonneInconnueXYZ"])
        assert "ColonneInconnueXYZ" not in m

    def test_mapping_vide(self):
        assert auto_map([]) == {}


class TestConstruireDfMappe:
    def test_renommage(self):
        df = pd.DataFrame({"Nom": ["DUPONT"], "Ville": ["PARIS"]})
        mapping = {"Nom": "nom_1", "Ville": "ville"}
        df_m = construire_df_mappe(df, mapping)
        assert "nom_1" in df_m.columns
        assert "ville" in df_m.columns
        assert "Nom" not in df_m.columns

    def test_champs_manquants_remplis_vide(self):
        df = pd.DataFrame({"Nom": ["DUPONT"]})
        mapping = {"Nom": "nom_1"}
        df_m = construire_df_mappe(df, mapping)
        # Tous les champs cibles doivent exister
        for champ in CHAMPS_CIBLES:
            assert champ in df_m.columns

    def test_colonne_source_absente_ignoree(self):
        df = pd.DataFrame({"Nom": ["DUPONT"]})
        mapping = {"Nom": "nom_1", "ColonneAbsente": "ville"}
        df_m = construire_df_mappe(df, mapping)
        assert "nom_1" in df_m.columns
