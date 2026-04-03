"""Tests pour cleaner/laposte.py — Règles La Poste NF Z 10-011."""
import pytest
import pandas as pd
from cleaner.laposte import (
    remove_accents,
    normalize_for_postal,
    normalize_voie,
    clean_address_punctuation,
    normalize_bp_cs,
    format_attention,
    check_completude,
    apply_laposte_rules,
)


class TestRemoveAccents:
    def test_e_accent(self):
        assert remove_accents("É") == "E"
        assert remove_accents("é") == "e"
        assert remove_accents("è") == "e"
        assert remove_accents("ê") == "e"

    def test_a_accent(self):
        assert remove_accents("à") == "a"
        assert remove_accents("â") == "a"

    def test_cedille(self):
        assert remove_accents("ç") == "c"
        assert remove_accents("Ç") == "C"

    def test_no_accent(self):
        assert remove_accents("PARIS") == "PARIS"

    def test_full_word(self):
        assert remove_accents("ÎLE-DE-FRANCE") == "ILE-DE-FRANCE"

    def test_mixed(self):
        result = remove_accents("Résidence des Érables")
        assert "E" in result
        assert "é" not in result


class TestNormalizeForPostal:
    def test_lowercase_to_upper_no_accent(self):
        assert normalize_for_postal("paris") == "PARIS"

    def test_accented_uppercase(self):
        result = normalize_for_postal("île-de-france")
        assert result == "ILE-DE-FRANCE"

    def test_cedille(self):
        assert normalize_for_postal("François") == "FRANCOIS"


class TestNormalizeVoie:
    def test_avenue(self):
        assert normalize_voie("10 AVENUE DES FLEURS") == "10 AV DES FLEURS"

    def test_boulevard(self):
        assert normalize_voie("25 BOULEVARD HAUSSMANN") == "25 BD HAUSSMANN"

    def test_impasse(self):
        assert normalize_voie("3 IMPASSE DU MOULIN") == "3 IMP DU MOULIN"

    def test_rue_unchanged(self):
        # RUE reste RUE selon la norme
        assert normalize_voie("10 RUE DE LA PAIX") == "10 RUE DE LA PAIX"

    def test_allee(self):
        assert normalize_voie("5 ALLEE DES ROSES") == "5 ALL DES ROSES"

    def test_residence(self):
        assert "RES" in normalize_voie("RESIDENCE LES PINS")

    def test_chemin(self):
        assert normalize_voie("CHEMIN DES VIGNES") == "CHE DES VIGNES"

    def test_place(self):
        assert normalize_voie("2 PLACE DU GENERAL DE GAULLE") == "2 PL DU GENERAL DE GAULLE"

    def test_no_voie(self):
        assert normalize_voie("BATIMENT A") == "BATIMENT A"

    def test_empty(self):
        assert normalize_voie("") == ""

    def test_route(self):
        assert normalize_voie("ROUTE DE LYON") == "RTE DE LYON"

    def test_square(self):
        assert normalize_voie("12 SQUARE DES ARTS") == "12 SQ DES ARTS"


class TestCleanAddressPunctuation:
    def test_comma_replaced(self):
        result = clean_address_punctuation("10 rue de la Paix, Appt 3")
        assert "," not in result
        assert "Appt 3" in result

    def test_trailing_dot_removed(self):
        result = clean_address_punctuation("10 rue de la Paix.")
        assert not result.endswith(".")

    def test_parentheses_removed(self):
        result = clean_address_punctuation("Bâtiment A (entrée B)")
        assert "(" not in result
        assert ")" not in result

    def test_semicolon_replaced(self):
        result = clean_address_punctuation("10 rue de la Paix; Apt 3")
        assert ";" not in result

    def test_no_change_normal(self):
        result = clean_address_punctuation("10 RUE DE LA PAIX")
        assert result == "10 RUE DE LA PAIX"

    def test_hyphen_preserved(self):
        result = clean_address_punctuation("JEAN-PIERRE")
        assert "-" in result

    def test_apostrophe_preserved(self):
        result = clean_address_punctuation("CHEMIN DE L'EGLISE")
        assert "'" in result


class TestNormalizeBpCs:
    def test_bp_with_dots(self):
        assert normalize_bp_cs("B.P.123") == "BP 123"

    def test_bp_no_space(self):
        assert normalize_bp_cs("BP123") == "BP 123"

    def test_cs_normalize(self):
        assert normalize_bp_cs("CS70001") == "CS 70001"

    def test_tsa_normalize(self):
        assert normalize_bp_cs("TSA12345") == "TSA 12345"

    def test_already_correct(self):
        assert normalize_bp_cs("BP 123") == "BP 123"

    def test_no_bp(self):
        assert normalize_bp_cs("10 RUE DE LA PAIX") == "10 RUE DE LA PAIX"

    def test_case_insensitive(self):
        result = normalize_bp_cs("b.p.456")
        assert "BP 456" in result


class TestFormatAttention:
    def test_full(self):
        result = format_attention("M.", "Jean", "DUPONT")
        assert "DUPONT" in result
        assert "Jean" in result
        assert "M." in result
        assert "ATTENTION" in result

    def test_no_civilite(self):
        result = format_attention("", "Jean", "DUPONT")
        assert "DUPONT" in result

    def test_empty(self):
        result = format_attention("", "", "")
        assert result == ""


class TestCheckCompletude:
    def test_complete_address(self):
        df = pd.DataFrame([{
            "Nom": "DUPONT", "Societe": "", "Adresse1": "10 RUE DE LA PAIX",
            "CodePostal": "75001", "Ville": "PARIS"
        }])
        alerts = check_completude(df)
        assert alerts == []

    def test_missing_adresse1(self):
        df = pd.DataFrame([{
            "Nom": "DUPONT", "Societe": "", "Adresse1": "",
            "CodePostal": "75001", "Ville": "PARIS"
        }])
        alerts = check_completude(df)
        assert len(alerts) == 1
        assert "Adresse1" in alerts[0]["message"]

    def test_missing_codepostal(self):
        df = pd.DataFrame([{
            "Nom": "DUPONT", "Societe": "", "Adresse1": "10 RUE",
            "CodePostal": "", "Ville": "PARIS"
        }])
        alerts = check_completude(df)
        assert len(alerts) == 1
        assert "CodePostal" in alerts[0]["message"]

    def test_missing_identite(self):
        df = pd.DataFrame([{
            "Nom": "", "Societe": "", "Adresse1": "10 RUE",
            "CodePostal": "75001", "Ville": "PARIS"
        }])
        alerts = check_completude(df)
        assert len(alerts) == 1
        assert "identité" in alerts[0]["message"]

    def test_societe_counts_as_identite(self):
        df = pd.DataFrame([{
            "Nom": "", "Societe": "ACME Corp", "Adresse1": "10 RUE",
            "CodePostal": "75001", "Ville": "PARIS"
        }])
        alerts = check_completude(df)
        assert alerts == []


class TestApplyLaposteRules:
    def _make_df(self, **kwargs):
        from cleaner.mapper import STANDARD_FIELDS
        row = {f: "" for f in STANDARD_FIELDS}
        row.update(kwargs)
        return pd.DataFrame([row])

    def test_bp_normalized(self):
        df = self._make_df(Adresse1="B.P.123", CodePostal="75001", Ville="PARIS", Nom="DUPONT")
        result, alerts = apply_laposte_rules(df, {"bp_cs": True})
        assert result.at[0, "Adresse1"] == "BP 123"

    def test_ponctuation_cleaned(self):
        df = self._make_df(Adresse1="10 rue de la Paix, Apt 3", CodePostal="75001", Ville="PARIS", Nom="DUPONT")
        result, alerts = apply_laposte_rules(df, {"ponctuation_adresse": True})
        assert "," not in result.at[0, "Adresse1"]

    def test_abrev_voies(self):
        df = self._make_df(Adresse1="10 AVENUE DES FLEURS", CodePostal="75001", Ville="PARIS", Nom="DUPONT")
        result, alerts = apply_laposte_rules(df, {"abreviations_voies": True})
        assert "AV" in result.at[0, "Adresse1"]
        assert "AVENUE" not in result.at[0, "Adresse1"]

    def test_desaccentuation(self):
        df = self._make_df(Adresse1="Résidence des Érables", CodePostal="75001", Ville="PARIS", Nom="DUPONT")
        result, alerts = apply_laposte_rules(df, {"desaccentuation": True})
        assert "é" not in result.at[0, "Adresse1"]
        assert "É" not in result.at[0, "Adresse1"]

    def test_completude_alert(self):
        df = self._make_df(Nom="DUPONT", Adresse1="", CodePostal="", Ville="")
        result, alerts = apply_laposte_rules(df, {"completude": True})
        assert len(alerts) > 0
        assert alerts[0]["type"] == "Adresse incomplète (norme La Poste)"

    def test_no_rules_applied(self):
        df = self._make_df(Adresse1="10 AVENUE DES FLEURS", Nom="DUPONT", CodePostal="75001", Ville="PARIS")
        opts = {k: False for k in ["bp_cs", "ponctuation_adresse", "abreviations_voies", "desaccentuation", "completude"]}
        result, alerts = apply_laposte_rules(df, opts)
        assert result.at[0, "Adresse1"] == "10 AVENUE DES FLEURS"
        assert alerts == []
