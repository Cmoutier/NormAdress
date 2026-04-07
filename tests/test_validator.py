"""Tests core/validator.py"""
import pytest
from core.validator import valider_adresse, a_alerte_bloquante


class TestValidateur:
    def test_adresse_complete_ok(self):
        a = {"L1": "M. Jean DUPONT", "L4": "12 rue de la Paix",
             "L6": "75001 PARIS", "L2": "", "L3": "", "L5": ""}
        alertes = valider_adresse(a, mode="postal")
        assert not a_alerte_bloquante(alertes)

    def test_l4_vide_bloquant(self):
        a = {"L1": "M. Jean DUPONT", "L4": "", "L6": "75001 PARIS"}
        alertes = valider_adresse(a, mode="postal")
        codes = [al["code"] for al in alertes]
        assert "L4_VIDE" in codes
        assert a_alerte_bloquante(alertes)

    def test_l6_vide_bloquant(self):
        a = {"L1": "M. Jean DUPONT", "L4": "12 rue", "L6": ""}
        alertes = valider_adresse(a, mode="postal")
        assert a_alerte_bloquante(alertes)

    def test_longueur_depassee(self):
        a = {"L1": "M. " + "X" * 40, "L4": "12 rue", "L6": "75001 PARIS"}
        alertes = valider_adresse(a, mode="postal")
        codes = [al["code"] for al in alertes]
        assert "LONGUEUR" in codes
        assert not any(al["bloquant"] for al in alertes if al["code"] == "LONGUEUR")

    def test_bal_interne_non_bloquant(self):
        a = {"L1": "HELIOPARC", "L2": "A l'attention de M. LERBS",
             "L4": "", "L6": ""}
        alertes = valider_adresse(a, mode="bal_interne")
        assert not a_alerte_bloquante(alertes)
        codes = [al["code"] for al in alertes]
        assert "BAL_INTERNE" in codes

    def test_cp_invalide(self):
        a = {"L1": "M. Dupont", "L4": "12 rue", "L6": "ABCDE PARIS"}
        alertes = valider_adresse(a, mode="postal")
        codes = [al["code"] for al in alertes]
        assert "CP_INVALIDE_FR" in codes
