"""Tests unitaires pour cleaner/consolidator.py."""
import pytest
import pandas as pd
from cleaner.consolidator import (
    consolidate_addresses,
    remove_empty_rows,
    detect_duplicates,
    explode_multi_contacts,
)


def make_df(data):
    return pd.DataFrame(data)


class TestConsolidateAddresses:
    def test_no_change_needed(self):
        df = make_df({"Adresse1": ["10 rue de la Paix"], "Adresse2": ["Apt 3"], "Adresse3": [""]})
        result, journal = consolidate_addresses(df)
        assert result.at[0, "Adresse1"] == "10 rue de la Paix"
        assert result.at[0, "Adresse2"] == "Apt 3"
        assert len(journal) == 0

    def test_adresse1_empty_adresse2_filled(self):
        df = make_df({"Adresse1": [""], "Adresse2": ["10 rue de la Paix"], "Adresse3": ["Batiment A"]})
        result, journal = consolidate_addresses(df)
        assert result.at[0, "Adresse1"] == "10 rue de la Paix"
        assert result.at[0, "Adresse2"] == "Batiment A"
        assert result.at[0, "Adresse3"] == ""
        assert len(journal) == 1

    def test_adresse1_adresse2_empty_adresse3_filled(self):
        df = make_df({"Adresse1": [""], "Adresse2": [""], "Adresse3": ["10 rue de la Paix"]})
        result, journal = consolidate_addresses(df)
        assert result.at[0, "Adresse1"] == "10 rue de la Paix"
        assert result.at[0, "Adresse2"] == ""
        assert result.at[0, "Adresse3"] == ""
        assert len(journal) == 1

    def test_journal_contains_info(self):
        df = make_df({"Adresse1": [""], "Adresse2": ["10 rue"], "Adresse3": [""]})
        result, journal = consolidate_addresses(df)
        assert journal[0]["ligne"] == 2  # index 0 → ligne 2 (en-tête = ligne 1)

    def test_multiple_rows(self):
        df = make_df({
            "Adresse1": ["10 rue", "", ""],
            "Adresse2": ["", "20 avenue", ""],
            "Adresse3": ["", "", "30 boulevard"],
        })
        result, journal = consolidate_addresses(df)
        assert result.at[0, "Adresse1"] == "10 rue"
        assert result.at[1, "Adresse1"] == "20 avenue"
        assert result.at[2, "Adresse1"] == "30 boulevard"
        assert len(journal) == 2

    def test_missing_adresse_columns(self):
        df = make_df({"Nom": ["Dupont"], "Ville": ["Paris"]})
        result, journal = consolidate_addresses(df)
        assert len(journal) == 0

    def test_no_modification_of_original(self):
        df = make_df({"Adresse1": [""], "Adresse2": ["10 rue"], "Adresse3": [""]})
        original = df.copy()
        consolidate_addresses(df)
        pd.testing.assert_frame_equal(df, original)


class TestRemoveEmptyRows:
    def test_remove_fully_empty(self):
        df = make_df({
            "Nom": ["Dupont", "", "Martin"],
            "Adresse1": ["10 rue", "", "5 avenue"],
            "CodePostal": ["75001", "", "69000"],
        })
        result, nb = remove_empty_rows(df)
        assert nb == 1
        assert len(result) == 2

    def test_keep_partial(self):
        df = make_df({
            "Nom": ["Dupont", ""],
            "Adresse1": ["", "10 rue"],
            "CodePostal": ["75001", ""],
        })
        result, nb = remove_empty_rows(df)
        assert nb == 0
        assert len(result) == 2

    def test_all_empty(self):
        df = make_df({
            "Nom": ["", ""],
            "Adresse1": ["", ""],
            "CodePostal": ["", ""],
        })
        result, nb = remove_empty_rows(df)
        assert nb == 2
        assert len(result) == 0

    def test_no_empty(self):
        df = make_df({
            "Nom": ["Dupont"],
            "Adresse1": ["10 rue"],
            "CodePostal": ["75001"],
        })
        result, nb = remove_empty_rows(df)
        assert nb == 0
        assert len(result) == 1

    def test_reset_index(self):
        df = make_df({
            "Nom": ["", "Dupont"],
            "Adresse1": ["", "10 rue"],
            "CodePostal": ["", "75001"],
        })
        result, nb = remove_empty_rows(df)
        assert result.index.tolist() == [0]


class TestDetectDuplicates:
    def test_no_duplicates(self):
        df = make_df({
            "Nom": ["DUPONT", "MARTIN"],
            "CodePostal": ["75001", "69000"],
        })
        result = detect_duplicates(df)
        assert result == []

    def test_simple_duplicate(self):
        df = make_df({
            "Nom": ["DUPONT", "DUPONT"],
            "CodePostal": ["75001", "75001"],
        })
        result = detect_duplicates(df)
        assert len(result) == 1
        assert len(result[0]["lignes"]) == 2

    def test_case_insensitive(self):
        df = make_df({
            "Nom": ["dupont", "DUPONT"],
            "CodePostal": ["75001", "75001"],
        })
        result = detect_duplicates(df)
        assert len(result) == 1

    def test_different_cp_not_duplicate(self):
        df = make_df({
            "Nom": ["DUPONT", "DUPONT"],
            "CodePostal": ["75001", "69000"],
        })
        result = detect_duplicates(df)
        assert result == []

    def test_missing_columns(self):
        df = make_df({"Nom": ["Dupont"]})
        result = detect_duplicates(df)
        assert result == []

    def test_three_duplicates(self):
        df = make_df({
            "Nom": ["DUPONT", "DUPONT", "DUPONT"],
            "CodePostal": ["75001", "75001", "75001"],
        })
        result = detect_duplicates(df)
        assert len(result) == 1
        assert len(result[0]["lignes"]) == 3


class TestExplodeMultiContacts:
    def test_basic_explode(self):
        from cleaner.mapper import STANDARD_FIELDS
        df = pd.DataFrame([{f: "" for f in STANDARD_FIELDS}])
        df.at[0, "Nom"] = "DUPONT"
        df.at[0, "Prenom"] = "Jean"

        source_df = pd.DataFrame({
            "Nom1": ["DUPONT"],
            "Nom2": ["MARTIN"],
            "Prenom1": ["Jean"],
            "Prenom2": ["Marie"],
        })

        multi = {"Nom": ["Nom1", "Nom2"], "Prenom": ["Prenom1", "Prenom2"]}
        result = explode_multi_contacts(df, multi, source_df)
        assert len(result) == 2

    def test_common_fields_duplicated(self):
        from cleaner.mapper import STANDARD_FIELDS
        df = pd.DataFrame([{f: "" for f in STANDARD_FIELDS}])
        df.at[0, "Nom"] = "DUPONT"
        df.at[0, "Ville"] = "PARIS"
        df.at[0, "CodePostal"] = "75001"

        source_df = pd.DataFrame({
            "Nom1": ["DUPONT"],
            "Nom2": ["MARTIN"],
        })

        multi = {"Nom": ["Nom1", "Nom2"]}
        result = explode_multi_contacts(df, multi, source_df)
        assert len(result) == 2
        # La ville doit être dupliquée
        assert result.at[0, "Ville"] == "PARIS"
        assert result.at[1, "Ville"] == "PARIS"
