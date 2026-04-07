"""Tests core/composer.py"""
import pytest
from core.composer import composer_adresse, generer_formule


class TestComposerParticulier:
    def base_row(self):
        return {
            "civilite_1": "M.", "nom_1": "DUPONT", "prenom_1": "Jean",
            "adresse_voie": "12 rue de la Paix",
            "code_postal": "75001", "ville": "PARIS",
        }

    def test_l1_afnor(self):
        r = composer_adresse(self.base_row(), mode="postal",
                             type_contact="particulier", ordre="afnor")
        assert r["L1"] == "M. Jean DUPONT"

    def test_l1_alt(self):
        r = composer_adresse(self.base_row(), mode="postal",
                             type_contact="particulier", ordre="alt")
        assert r["L1"] == "M. DUPONT Jean"

    def test_l4_voie(self):
        r = composer_adresse(self.base_row())
        assert r["L4"] == "12 rue de la Paix"

    def test_l6(self):
        r = composer_adresse(self.base_row())
        assert r["L6"] == "75001 PARIS"

    def test_l6_etranger(self):
        row = self.base_row()
        row["pays"] = "BELGIQUE"
        row["code_postal"] = "1000"
        row["ville"] = "BRUXELLES"
        r = composer_adresse(row)
        assert "BELGIQUE" in r["L6"]


class TestComposerPro:
    def base_row(self):
        return {
            "societe": "SYNERPA",
            "civilite_1": "Mme", "nom_1": "MARTIN", "prenom_1": "Sophie",
            "adresse_voie": "5 avenue des Fleurs",
            "code_postal": "69002", "ville": "LYON",
        }

    def test_format_a_l1_societe(self):
        r = composer_adresse(self.base_row(), mode="postal",
                             type_contact="professionnel", format_pro="A")
        assert r["L1"] == "SYNERPA"
        assert "MARTIN" in r["L2"]

    def test_format_b_l1_contact(self):
        r = composer_adresse(self.base_row(), mode="postal",
                             type_contact="professionnel", format_pro="B")
        assert "MARTIN" in r["L1"]
        assert r["L2"] == "SYNERPA"


class TestComposerBalInterne:
    def test_l4_vide(self):
        row = {
            "societe": "HELIOPARC",
            "civilite_1": "M.", "nom_1": "LERBS", "prenom_1": "Alexander",
        }
        r = composer_adresse(row, mode="bal_interne")
        assert r["L4"] == ""
        assert "LERBS" in r["L2"]
        assert "attention" in r["L2"].lower()


class TestFormule:
    def test_homme(self):
        row = {"civilite_1": "M.", "prenom_1": "Jean", "nom_1": "DUPONT"}
        assert generer_formule(row) == "Cher Monsieur Jean DUPONT,"

    def test_femme(self):
        row = {"civilite_1": "Mme", "prenom_1": "Marie", "nom_1": "MARTIN"}
        assert generer_formule(row) == "Chère Madame Marie MARTIN,"

    def test_deux_hommes(self):
        row = {
            "civilite_1": "M.", "prenom_1": "Jean", "nom_1": "DUPONT",
            "civilite_2": "M.", "prenom_2": "Pierre", "nom_2": "MARTIN",
        }
        f = generer_formule(row)
        assert f.startswith("Chers Messieurs")

    def test_source_prioritaire(self):
        row = {
            "civilite_1": "M.", "prenom_1": "Jean", "nom_1": "DUPONT",
            "formule_source": "Cher ami,",
        }
        assert generer_formule(row) == "Cher ami,"
