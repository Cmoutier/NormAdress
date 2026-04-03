"""Tests unitaires pour cleaner/mapper.py."""
import pytest
from cleaner.mapper import auto_map, detect_multi_contacts, normalize_col, STANDARD_FIELDS


class TestNormalizeCol:
    def test_lowercase(self):
        assert normalize_col("NOM") == "nom"

    def test_remove_accents_e(self):
        # é → e, then alphanum only
        result = normalize_col("prénom")
        assert "e" in result
        assert "p" in result

    def test_remove_special_chars(self):
        assert normalize_col("code_postal") == "codepostal"

    def test_remove_spaces(self):
        assert normalize_col("code postal") == "codepostal"


class TestAutoMap:
    def test_exact_match(self):
        mapping = auto_map(["nom", "prenom", "ville"])
        assert mapping["nom"] == "Nom"
        assert mapping["prenom"] == "Prenom"
        assert mapping["ville"] == "Ville"

    def test_synonym_match(self):
        mapping = auto_map(["lastname", "firstname", "city"])
        assert mapping["lastname"] == "Nom"
        assert mapping["firstname"] == "Prenom"
        assert mapping["city"] == "Ville"

    def test_unrecognized_column(self):
        mapping = auto_map(["colonne_inconnue"])
        assert mapping["colonne_inconnue"] == ""

    def test_codepostal_synonyms(self):
        for col in ["cp", "zip", "postal", "postcode", "code_postal"]:
            mapping = auto_map([col])
            assert mapping[col] == "CodePostal", f"Failed for {col}"

    def test_adresse_synonyms(self):
        for col in ["adresse", "rue", "street", "voie"]:
            mapping = auto_map([col])
            assert mapping[col] == "Adresse1", f"Failed for {col}"

    def test_societe_synonyms(self):
        for col in ["company", "entreprise"]:
            mapping = auto_map([col])
            assert mapping[col] == "Societe", f"Failed for {col}"

    def test_civilite_synonyms(self):
        for col in ["civ", "titre", "title", "gender", "sexe"]:
            mapping = auto_map([col])
            assert mapping[col] == "Civilite", f"Failed for {col}"

    def test_empty_columns(self):
        mapping = auto_map([])
        assert mapping == {}

    def test_case_insensitive(self):
        mapping = auto_map(["NOM", "PRENOM", "VILLE"])
        assert mapping["NOM"] == "Nom"
        assert mapping["PRENOM"] == "Prenom"
        assert mapping["VILLE"] == "Ville"


class TestDetectMultiContacts:
    def test_no_multi(self):
        mapping = {"Nom": "Nom", "Prenom": "Prenom"}
        result = detect_multi_contacts(mapping)
        assert result == {}

    def test_multi_nom(self):
        mapping = {"Nom1": "Nom", "Nom2": "Nom", "Ville": "Ville"}
        result = detect_multi_contacts(mapping)
        assert "Nom" in result
        assert len(result["Nom"]) == 2
        assert "Ville" not in result

    def test_multi_several_fields(self):
        mapping = {"Nom1": "Nom", "Nom2": "Nom", "Prenom1": "Prenom", "Prenom2": "Prenom"}
        result = detect_multi_contacts(mapping)
        assert "Nom" in result
        assert "Prenom" in result

    def test_ignore_empty_mapping(self):
        mapping = {"ColA": "", "Nom": "Nom"}
        result = detect_multi_contacts(mapping)
        assert result == {}
