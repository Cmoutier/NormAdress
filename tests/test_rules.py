"""Tests unitaires pour cleaner/rules.py."""
import pytest
import pandas as pd
from cleaner.rules import (
    clean_whitespace,
    clean_civilite,
    clean_nom,
    clean_prenom,
    clean_codepostal,
    clean_ville,
    clean_generic,
    apply_rules,
)


class TestCleanWhitespace:
    def test_bom(self):
        assert clean_whitespace("\ufeffBonjour") == "Bonjour"

    def test_insecable(self):
        assert clean_whitespace("Jean\u00a0Dupont") == "Jean Dupont"

    def test_zero_width(self):
        assert clean_whitespace("Jean\u200bDupont") == "JeanDupont"

    def test_tab(self):
        assert clean_whitespace("Jean\tDupont") == "Jean Dupont"

    def test_newline(self):
        assert clean_whitespace("Jean\nDupont") == "Jean Dupont"

    def test_multiple_spaces(self):
        assert clean_whitespace("Jean   Dupont") == "Jean Dupont"

    def test_strip(self):
        assert clean_whitespace("  Jean  ") == "Jean"

    def test_empty(self):
        assert clean_whitespace("") == ""

    def test_combined(self):
        result = clean_whitespace("\ufeff  Jean\u00a0\tDupont  ")
        assert result == "Jean Dupont"


class TestCleanCivilite:
    @pytest.mark.parametrize("input_val,expected", [
        ("M", "M."),
        ("Mr", "M."),
        ("MR", "M."),
        ("Monsieur", "M."),
        ("monsieur", "M."),
        ("M.", "M."),
        ("Mme", "Mme"),
        ("MME", "Mme"),
        ("Madame", "Mme"),
        ("madame", "Mme"),
        ("mme", "Mme"),
        ("mme.", "Mme"),
        ("Mlle", "Mlle"),
        ("MLLE", "Mlle"),
        ("Mademoiselle", "Mlle"),
    ])
    def test_recognized(self, input_val, expected):
        result, ok = clean_civilite(input_val)
        assert result == expected
        assert ok is True

    def test_empty(self):
        result, ok = clean_civilite("")
        assert result == ""
        assert ok is True

    def test_unrecognized(self):
        result, ok = clean_civilite("Dr")
        assert result == "Dr"
        assert ok is False

    def test_whitespace_stripped(self):
        result, ok = clean_civilite("  Mme  ")
        assert result == "Mme"
        assert ok is True


class TestCleanNom:
    def test_uppercase(self):
        assert clean_nom("dupont") == "DUPONT"

    def test_already_upper(self):
        assert clean_nom("DUPONT") == "DUPONT"

    def test_strip(self):
        assert clean_nom("  Dupont  ") == "DUPONT"

    def test_multiple_spaces(self):
        assert clean_nom("du  pont") == "DU PONT"

    def test_empty(self):
        assert clean_nom("") == ""


class TestCleanPrenom:
    def test_simple(self):
        assert clean_prenom("jean") == "Jean"

    def test_composed_hyphen(self):
        assert clean_prenom("jean-pierre") == "Jean-Pierre"

    def test_multiple_words(self):
        result = clean_prenom("marie anne")
        assert result == "Marie Anne"

    def test_particule_de(self):
        result = clean_prenom("jean de la fontaine")
        assert "de" in result
        assert "la" in result

    def test_empty(self):
        assert clean_prenom("") == ""

    def test_already_title(self):
        assert clean_prenom("Marie") == "Marie"


class TestCleanCodePostal:
    def test_already_5_digits(self):
        result, ok = clean_codepostal("75001")
        assert result == "75001"
        assert ok is True

    def test_4_digits_pad(self):
        result, ok = clean_codepostal("1000")
        assert result == "01000"
        assert ok is True

    def test_3_digits_pad(self):
        result, ok = clean_codepostal("750")
        assert result == "00750"
        assert ok is True

    def test_with_space(self):
        result, ok = clean_codepostal("75 001")
        assert result == "75001"
        assert ok is True

    def test_empty(self):
        result, ok = clean_codepostal("")
        assert result == ""
        assert ok is True

    def test_non_numeric(self):
        result, ok = clean_codepostal("ABCDE")
        assert ok is False

    def test_leading_zero_preserved(self):
        result, ok = clean_codepostal("01000")
        assert result == "01000"
        assert ok is True


class TestCleanVille:
    def test_uppercase(self):
        assert clean_ville("paris") == "PARIS"

    def test_strip(self):
        assert clean_ville("  Lyon  ") == "LYON"

    def test_multiple_spaces(self):
        assert clean_ville("Saint  Cloud") == "SAINT CLOUD"


class TestCleanGeneric:
    def test_strip(self):
        assert clean_generic("  résidence les fleurs  ") == "résidence les fleurs"

    def test_empty(self):
        assert clean_generic("") == ""


class TestApplyRules:
    def _make_df(self, data):
        return pd.DataFrame(data)

    def test_apply_rules_basic(self):
        df = self._make_df({
            "Nom": ["dupont"],
            "Prenom": ["jean-pierre"],
            "Ville": ["paris"],
            "CodePostal": ["75001"],
            "Civilite": ["Mr"],
            "Adresse1": ["10 rue de la Paix"],
            "Adresse2": [""],
            "Adresse3": [""],
            "Societe": [""],
        })
        result, rapport = apply_rules(df)
        assert result.at[0, "Nom"] == "DUPONT"
        assert result.at[0, "Prenom"] == "Jean-Pierre"
        assert result.at[0, "Ville"] == "PARIS"
        assert result.at[0, "Civilite"] == "M."

    def test_apply_rules_codepostal_warning(self):
        df = self._make_df({
            "Nom": ["dupont"],
            "CodePostal": ["INVALID"],
            "Ville": ["Paris"],
        })
        result, rapport = apply_rules(df)
        assert any(r["colonne"] == "CodePostal" for r in rapport)

    def test_apply_rules_civilite_warning(self):
        df = self._make_df({
            "Civilite": ["Dr"],
            "Nom": ["Smith"],
        })
        result, rapport = apply_rules(df)
        assert any(r["colonne"] == "Civilite" for r in rapport)

    def test_apply_rules_options_disabled(self):
        df = self._make_df({
            "Nom": ["dupont"],
            "Ville": ["paris"],
        })
        result, rapport = apply_rules(df, {"nom": False, "ville": False})
        # Nom ne doit PAS être mis en majuscules si option désactivée
        assert result.at[0, "Nom"] == "dupont"

    def test_apply_rules_bom_cleaning(self):
        df = self._make_df({
            "Nom": ["\ufeffDupont"],
            "Ville": ["Paris"],
        })
        result, rapport = apply_rules(df)
        assert "\ufeff" not in result.at[0, "Nom"]
