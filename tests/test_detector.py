"""Tests core/detector.py"""
import pytest
from core.detector import detecter_type, detecter_mode_distribution


class TestDetecterType:
    def test_pro_avec_societe(self):
        assert detecter_type({"societe": "SYNERPA", "nom_1": ""}) == "professionnel"

    def test_particulier_nom(self):
        assert detecter_type({"societe": "", "nom_1": "DUPONT"}) == "particulier"

    def test_particulier_identite(self):
        assert detecter_type({"societe": "", "identite_1": "DUPONT Jean"}) == "particulier"

    def test_inconnu(self):
        assert detecter_type({"societe": "", "nom_1": "", "prenom_1": ""}) == "inconnu"

    def test_pro_sarl(self):
        assert detecter_type({"societe": "Dupont SARL"}) == "professionnel"


class TestDetecterMode:
    def test_postal_avec_voie(self):
        assert detecter_mode_distribution({"adresse_voie", "code_postal"}) == "postal"

    def test_bal_sans_adresse(self):
        assert detecter_mode_distribution({"societe", "nom_1"}) == "bal_interne"

    def test_bal_vide(self):
        assert detecter_mode_distribution(set()) == "bal_interne"
