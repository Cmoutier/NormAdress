"""Tests pour cleaner/coherence.py."""
import pytest
import pandas as pd
from cleaner.coherence import (
    detect_civilite_in_nom,
    detect_nom_prenom_combine,
    check_societe_contact,
    detect_cedex,
    detect_full_address_in_field,
    detect_nom_sans_adresse,
    fix_codepostal_float,
    run_all,
)


def df1(**kwargs):
    return pd.DataFrame([kwargs])


class TestFixCodepostalFloat:
    def test_detects_float(self):
        df = df1(CodePostal="75001.0")
        result, alerts = fix_codepostal_float(df)
        assert result.at[0, "CodePostal"] == "75001"
        assert len(alerts) == 1
        assert alerts[0]["auto_fixable"] is True

    def test_no_change_normal(self):
        df = df1(CodePostal="75001")
        result, alerts = fix_codepostal_float(df)
        assert result.at[0, "CodePostal"] == "75001"
        assert alerts == []

    def test_multiple_decimals(self):
        df = df1(CodePostal="1000.00")
        result, alerts = fix_codepostal_float(df)
        assert result.at[0, "CodePostal"] == "1000"
        assert len(alerts) == 1

    def test_no_column(self):
        df = df1(Nom="DUPONT")
        result, alerts = fix_codepostal_float(df)
        assert alerts == []

    def test_empty_value(self):
        df = df1(CodePostal="")
        result, alerts = fix_codepostal_float(df)
        assert alerts == []


class TestDetectCiviliteInNom:
    def test_mr_prefix(self):
        df = df1(Nom="M. DUPONT", Civilite="")
        result, alerts = detect_civilite_in_nom(df)
        assert result.at[0, "Nom"] == "DUPONT"
        assert result.at[0, "Civilite"] == "M."
        assert len(alerts) == 1
        assert alerts[0]["auto_fixable"] is True

    def test_mme_prefix(self):
        df = df1(Nom="Mme MARTIN", Civilite="")
        result, alerts = detect_civilite_in_nom(df)
        assert result.at[0, "Nom"] == "MARTIN"
        assert "Mme" in result.at[0, "Civilite"]

    def test_monsieur_prefix(self):
        df = df1(Nom="Monsieur BERNARD", Civilite="")
        result, alerts = detect_civilite_in_nom(df)
        assert result.at[0, "Nom"] == "BERNARD"

    def test_no_prefix(self):
        df = df1(Nom="DUPONT", Civilite="")
        result, alerts = detect_civilite_in_nom(df)
        assert result.at[0, "Nom"] == "DUPONT"
        assert alerts == []

    def test_existing_civilite_preserved(self):
        df = df1(Nom="M. DUPONT", Civilite="Mme")
        result, alerts = detect_civilite_in_nom(df)
        assert result.at[0, "Nom"] == "DUPONT"
        assert result.at[0, "Civilite"] == "Mme"  # conservée

    def test_no_nom_column(self):
        df = df1(Ville="PARIS")
        result, alerts = detect_civilite_in_nom(df)
        assert alerts == []

    def test_dr_prefix(self):
        df = df1(Nom="Dr. MARTIN", Civilite="")
        result, alerts = detect_civilite_in_nom(df)
        assert result.at[0, "Nom"] == "MARTIN"


class TestDetectNomPrenomCombine:
    def test_two_words_no_prenom(self):
        df = df1(Nom="DUPONT Jean", Prenom="")
        alerts = detect_nom_prenom_combine(df)
        assert len(alerts) == 1
        assert alerts[0]["auto_fixable"] is False

    def test_single_word_ok(self):
        df = df1(Nom="DUPONT", Prenom="")
        alerts = detect_nom_prenom_combine(df)
        assert alerts == []

    def test_prenom_filled_ok(self):
        df = df1(Nom="DUPONT Jean", Prenom="Jean")
        alerts = detect_nom_prenom_combine(df)
        assert alerts == []

    def test_no_nom_column(self):
        df = df1(Ville="PARIS")
        alerts = detect_nom_prenom_combine(df)
        assert alerts == []

    def test_hyphenated_name(self):
        df = df1(Nom="DUPONT Jean-Pierre", Prenom="")
        alerts = detect_nom_prenom_combine(df)
        assert len(alerts) == 1


class TestCheckSocieteContact:
    def test_societe_and_nom(self):
        df = df1(Societe="ACME Corp", Nom="DUPONT", Prenom="Jean")
        alerts = check_societe_contact(df)
        assert len(alerts) == 1
        assert alerts[0]["auto_fixable"] is False
        assert "ACME Corp" in alerts[0]["message"]

    def test_societe_only(self):
        df = df1(Societe="ACME Corp", Nom="", Prenom="")
        alerts = check_societe_contact(df)
        assert alerts == []

    def test_nom_only(self):
        df = df1(Societe="", Nom="DUPONT", Prenom="Jean")
        alerts = check_societe_contact(df)
        assert alerts == []

    def test_no_societe_column(self):
        df = df1(Nom="DUPONT", Prenom="Jean")
        alerts = check_societe_contact(df)
        assert alerts == []


class TestDetectCedex:
    def test_cedex_detected(self):
        df = df1(Ville="paris cedex 08")
        result, alerts = detect_cedex(df)
        assert "CEDEX" in result.at[0, "Ville"]
        assert len(alerts) == 1
        assert alerts[0]["auto_fixable"] is True

    def test_cedex_uppercase(self):
        df = df1(Ville="PARIS CEDEX")
        result, alerts = detect_cedex(df)
        assert len(alerts) == 1

    def test_no_cedex(self):
        df = df1(Ville="PARIS")
        result, alerts = detect_cedex(df)
        assert alerts == []

    def test_no_ville_column(self):
        df = df1(Nom="DUPONT")
        result, alerts = detect_cedex(df)
        assert alerts == []


class TestDetectFullAddressInField:
    def test_full_address_no_cp_column(self):
        df = df1(Adresse1="10 rue de la Paix 75001 PARIS", CodePostal="")
        alerts = detect_full_address_in_field(df)
        assert len(alerts) == 1

    def test_normal_address(self):
        df = df1(Adresse1="10 rue de la Paix", CodePostal="75001")
        alerts = detect_full_address_in_field(df)
        assert alerts == []

    def test_no_adresse_column(self):
        df = df1(Nom="DUPONT")
        alerts = detect_full_address_in_field(df)
        assert alerts == []

    def test_cp_in_adresse_with_cp_column(self):
        df = df1(Adresse1="10 rue de la Paix 75001", CodePostal="75001")
        alerts = detect_full_address_in_field(df)
        assert len(alerts) == 1


class TestDetectNomSansAdresse:
    def test_nom_sans_adresse(self):
        df = df1(Nom="DUPONT", Adresse1="", CodePostal="")
        alerts = detect_nom_sans_adresse(df)
        assert len(alerts) == 1
        assert alerts[0]["auto_fixable"] is False

    def test_nom_avec_adresse(self):
        df = df1(Nom="DUPONT", Adresse1="10 rue de la Paix", CodePostal="75001")
        alerts = detect_nom_sans_adresse(df)
        assert alerts == []

    def test_societe_sans_adresse(self):
        df = df1(Societe="ACME", Nom="", Adresse1="", CodePostal="")
        alerts = detect_nom_sans_adresse(df)
        assert len(alerts) == 1

    def test_no_nom_column(self):
        df = df1(Ville="PARIS")
        alerts = detect_nom_sans_adresse(df)
        assert alerts == []


class TestRunAll:
    def test_run_all_applies_auto_fixes(self):
        df = pd.DataFrame([{
            "Civilite": "",
            "Nom": "M. DUPONT",
            "Prenom": "Jean",
            "Societe": "",
            "Adresse1": "10 rue de la Paix",
            "Adresse2": "",
            "Adresse3": "",
            "CodePostal": "75001.0",
            "Ville": "paris cedex 01",
        }])
        result, alerts = run_all(df)
        assert result.at[0, "CodePostal"] == "75001"
        assert result.at[0, "Nom"] == "DUPONT"
        assert result.at[0, "Civilite"] == "M."
        assert "CEDEX" in result.at[0, "Ville"]
        auto = [a for a in alerts if a["auto_fixable"]]
        assert len(auto) >= 3

    def test_run_all_empty_df(self):
        from cleaner.mapper import STANDARD_FIELDS
        df = pd.DataFrame(columns=STANDARD_FIELDS)
        result, alerts = run_all(df)
        assert alerts == []
