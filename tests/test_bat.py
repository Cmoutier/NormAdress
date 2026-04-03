"""Tests pour cleaner/bat.py et format_envelope_lines."""
import pytest
import pandas as pd
from cleaner.laposte import format_envelope_lines
from cleaner.bat import generate_bat, _card_html


class TestFormatEnvelopeLines:
    def _row(self, **kw):
        from cleaner.mapper import STANDARD_FIELDS
        r = {f: "" for f in STANDARD_FIELDS}
        r.update(kw)
        return r

    def test_particulier_simple(self):
        r = self._row(Civilite="M.", Prenom="Jean", Nom="DUPONT",
                      Adresse1="10 RUE DE LA PAIX", CodePostal="75001", Ville="PARIS")
        lines = format_envelope_lines(r)
        labels = [l for l, _ in lines]
        contents = [c for _, c in lines]
        assert "L1" in labels
        assert "L4" in labels
        assert "L6" in labels
        assert "M. Jean DUPONT" in contents
        assert "10 RUE DE LA PAIX" in contents
        assert "75001 PARIS" in contents

    def test_b2b_societe_contact(self):
        r = self._row(Societe="ACME CORP", Nom="DUPONT", Prenom="Jean",
                      Adresse1="10 AV DES FLEURS", CodePostal="69000", Ville="LYON")
        lines = format_envelope_lines(r)
        assert lines[0] == ("L1", "ACME CORP")
        assert lines[1][0] == "L2"
        assert "DUPONT" in lines[1][1]

    def test_societe_sans_contact(self):
        r = self._row(Societe="ACME CORP", Adresse1="10 RUE", CodePostal="75001", Ville="PARIS")
        lines = format_envelope_lines(r)
        assert lines[0] == ("L1", "ACME CORP")
        assert not any(l == "L2" for l, _ in lines)

    def test_adresse3_en_l3(self):
        r = self._row(Nom="DUPONT", Adresse3="BAT A", Adresse1="10 RUE", CodePostal="75001", Ville="PARIS")
        lines = format_envelope_lines(r)
        labels = [l for l, _ in lines]
        assert "L3" in labels
        assert labels.index("L3") < labels.index("L4")

    def test_adresse2_en_l5(self):
        r = self._row(Nom="DUPONT", Adresse1="10 RUE", Adresse2="BP 123",
                      CodePostal="75001", Ville="PARIS")
        lines = format_envelope_lines(r)
        labels = [l for l, _ in lines]
        assert "L5" in labels
        assert "BP 123" in dict(lines)["L5"]

    def test_ligne_vide_ignoree(self):
        r = self._row(Nom="DUPONT", Adresse1="10 RUE", CodePostal="75001", Ville="PARIS")
        lines = format_envelope_lines(r)
        # Pas de L3 ni L5 si vides
        labels = [l for l, _ in lines]
        assert "L3" not in labels
        assert "L5" not in labels

    def test_tout_vide(self):
        from cleaner.mapper import STANDARD_FIELDS
        r = {f: "" for f in STANDARD_FIELDS}
        lines = format_envelope_lines(r)
        assert lines == []

    def test_cp_ville_concatenes(self):
        r = self._row(Nom="DUPONT", Adresse1="10 RUE", CodePostal="75001", Ville="PARIS")
        lines = format_envelope_lines(r)
        cp_line = dict(lines).get("L6", "")
        assert "75001" in cp_line
        assert "PARIS" in cp_line


class TestCardHtml:
    def _row(self, **kw):
        from cleaner.mapper import STANDARD_FIELDS
        r = {f: "" for f in STANDARD_FIELDS}
        r.update(kw)
        return r

    def test_returns_string(self):
        r = self._row(Nom="DUPONT", Adresse1="10 RUE", CodePostal="75001", Ville="PARIS")
        html = _card_html(r, line_num=1)
        assert isinstance(html, str)
        assert "DUPONT" in html

    def test_contains_line_num(self):
        r = self._row(Nom="DUPONT", Adresse1="10 RUE", CodePostal="75001", Ville="PARIS")
        html = _card_html(r, line_num=42)
        assert "42" in html

    def test_doublon_class(self):
        r = self._row(Nom="DUPONT", Adresse1="10 RUE", CodePostal="75001", Ville="PARIS")
        html = _card_html(r, line_num=1, is_doublon=True)
        assert "doublon" in html.lower()

    def test_consolidated_class(self):
        r = self._row(Nom="DUPONT", Adresse1="10 RUE", CodePostal="75001", Ville="PARIS")
        html = _card_html(r, line_num=1, is_consolidated=True)
        assert "consolidated" in html.lower()

    def test_missing_voie_warning(self):
        r = self._row(Nom="DUPONT", CodePostal="75001", Ville="PARIS")
        html = _card_html(r, line_num=1)
        assert "voie" in html.lower()


class TestGenerateBat:
    def _make_df(self, n=3):
        from cleaner.mapper import STANDARD_FIELDS
        rows = []
        for i in range(n):
            rows.append({
                "Civilite": "M.", "Nom": f"DUPONT{i}", "Prenom": "Jean",
                "Societe": "", "Adresse1": f"{i+1} RUE DE LA PAIX",
                "Adresse2": "", "Adresse3": "", "CodePostal": "75001", "Ville": "PARIS",
            })
        return pd.DataFrame(rows, columns=STANDARD_FIELDS)

    def test_returns_html_string(self):
        df = self._make_df(3)
        html = generate_bat(df)
        assert isinstance(html, str)
        assert "<!DOCTYPE html>" in html

    def test_contains_all_rows(self):
        df = self._make_df(5)
        html = generate_bat(df)
        for i in range(5):
            assert f"DUPONT{i}" in html

    def test_nom_travail_in_html(self):
        df = self._make_df(2)
        html = generate_bat(df, nom_travail="Client Test SA")
        assert "Client Test SA" in html

    def test_doublon_badge(self):
        df = self._make_df(2)
        doublons = [{"lignes": [2, 3], "nom": "DUPONT0", "codepostal": "75001"}]
        html = generate_bat(df, doublons=doublons)
        assert "DOUBLON" in html

    def test_nf_z_mention(self):
        df = self._make_df(1)
        html = generate_bat(df)
        assert "NF Z 10-011" in html

    def test_empty_df(self):
        from cleaner.mapper import STANDARD_FIELDS
        df = pd.DataFrame(columns=STANDARD_FIELDS)
        html = generate_bat(df)
        assert isinstance(html, str)

    def test_print_css(self):
        df = self._make_df(1)
        html = generate_bat(df)
        assert "@media print" in html

    def test_pli_numbering(self):
        df = self._make_df(3)
        html = generate_bat(df)
        assert "Pli n° 1" in html
        assert "Pli n° 3" in html
