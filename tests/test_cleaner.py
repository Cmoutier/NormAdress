"""Tests core/cleaner.py"""
import pytest
from core.cleaner import (
    clean_whitespace, clean_civilite, clean_nom, clean_prenom,
    clean_codepostal, clean_ville,
)


class TestWhitespace:
    def test_bom(self):
        assert clean_whitespace("\ufeffBonjour") == "Bonjour"

    def test_espace_insecable(self):
        assert clean_whitespace("Paris\u00a0Cedex") == "Paris Cedex"

    def test_zero_width(self):
        assert clean_whitespace("AB\u200bCD") == "ABCD"

    def test_tabs(self):
        assert clean_whitespace("A\tB") == "A B"

    def test_espaces_multiples(self):
        assert clean_whitespace("  A   B  ") == "A B"


class TestCivilite:
    @pytest.mark.parametrize("inp,expected", [
        ("Monsieur", "M."), ("M", "M."), ("Mr", "M."), ("MR", "M."),
        ("Madame", "Mme"), ("Mme", "Mme"), ("MME", "Mme"),
        ("Mademoiselle", "Mlle"), ("Mlle", "Mlle"),
        ("Docteur", "Dr"), ("Dr", "Dr"),
        ("Messieurs", "Messieurs"),
    ])
    def test_normalisation(self, inp, expected):
        val, ok = clean_civilite(inp)
        assert val == expected
        assert ok is True

    def test_inconnue(self):
        val, ok = clean_civilite("Maître")
        assert ok is False


class TestNom:
    def test_majuscules(self):
        assert clean_nom("dupont") == "DUPONT"

    def test_strip(self):
        assert clean_nom("  Martin  ") == "MARTIN"


class TestPrenom:
    def test_titre(self):
        assert clean_prenom("jean") == "Jean"

    def test_tiret(self):
        assert clean_prenom("jean-pierre") == "Jean-Pierre"

    def test_particule(self):
        assert clean_prenom("Marie de la Tour") == "Marie de la Tour"

    def test_majuscule_entree(self):
        assert clean_prenom("JEAN") == "Jean"


class TestCodePostal:
    def test_normal(self):
        val, ok = clean_codepostal("75001")
        assert val == "75001"
        assert ok is True

    def test_float_excel(self):
        val, ok = clean_codepostal("69002.0")
        assert val == "69002"
        assert ok is True

    def test_4_chiffres(self):
        val, ok = clean_codepostal("1000")
        assert val == "01000"
        assert ok is True

    def test_3_chiffres(self):
        val, ok = clean_codepostal("750")
        assert val == "00750"
        assert ok is True

    def test_vide(self):
        val, ok = clean_codepostal("")
        assert ok is False

    def test_non_numerique(self):
        val, ok = clean_codepostal("ABCDE")
        assert ok is False


class TestVille:
    def test_majuscules(self):
        assert clean_ville("paris") == "PARIS"

    def test_cedex(self):
        assert clean_ville("paris cedex 08") == "PARIS CEDEX 08"
