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


class TestCodePostalEdgeCases:
    def test_2_chiffres(self):
        val, ok = clean_codepostal("75")
        assert val == "00075"
        assert ok is True  # padde à 5 chiffres → valide

    def test_1_chiffre(self):
        val, ok = clean_codepostal("7")
        assert val == "00007"
        assert ok is True  # padde à 5 chiffres → valide

    def test_6_chiffres(self):
        val, ok = clean_codepostal("750001")
        assert ok is False  # trop long → invalide


class TestCleanRow:
    from core.cleaner import clean_row

    def test_row_complet(self):
        from core.cleaner import clean_row
        row = {
            "civilite_1": "Monsieur", "nom_1": "dupont", "prenom_1": "jean",
            "code_postal": "75001.0", "ville": "paris",
            "societe": "  SYNERPA  ",
        }
        out = clean_row(row)
        assert out["civilite_1"] == "M."
        assert out["nom_1"] == "DUPONT"
        assert out["prenom_1"] == "Jean"
        assert out["code_postal"] == "75001"
        assert out["ville"] == "PARIS"
        assert out["societe"] == "SYNERPA"

    def test_row_multi_contacts(self):
        from core.cleaner import clean_row
        row = {
            "civilite_2": "Mme", "nom_2": "martin", "prenom_2": "marie",
            "civilite_3": "M.", "nom_3": "durand", "prenom_3": "pierre",
        }
        out = clean_row(row)
        assert out["nom_2"] == "MARTIN"
        assert out["prenom_2"] == "Marie"
        assert out["nom_3"] == "DURAND"

    def test_row_champs_vides(self):
        from core.cleaner import clean_row
        out = clean_row({"nom_1": "", "ville": ""})
        assert out["nom_1"] == ""
        assert out["ville"] == ""
