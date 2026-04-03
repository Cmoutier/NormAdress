"""Tests pour cleaner/loader.py."""
import io
import pytest
import pandas as pd
from cleaner.loader import load_file, detect_encoding, detect_separator


class FakeFile:
    """Simule un fichier uploadé Streamlit."""
    def __init__(self, content: bytes, name: str):
        self._content = content
        self.name = name
        self._pos = 0

    def read(self):
        data = self._content[self._pos:]
        self._pos = len(self._content)
        return data

    def seek(self, pos):
        self._pos = pos


def make_csv(content: str, encoding="utf-8") -> bytes:
    return content.encode(encoding)


def make_xlsx(data: dict) -> bytes:
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    cols = list(data.keys())
    ws.append(cols)
    rows = zip(*[data[c] for c in cols])
    for row in rows:
        ws.append(list(row))
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


class TestDetectEncoding:
    def test_utf8(self):
        enc = detect_encoding("bonjour".encode("utf-8"))
        assert enc is not None

    def test_latin1(self):
        enc = detect_encoding("café".encode("latin-1"))
        assert enc is not None


class TestDetectSeparator:
    def test_semicolon(self):
        raw = "a;b;c\n1;2;3".encode("utf-8")
        assert detect_separator(raw, "utf-8") == ";"

    def test_comma(self):
        raw = "a,b,c\n1,2,3".encode("utf-8")
        assert detect_separator(raw, "utf-8") == ","

    def test_tab(self):
        raw = "a\tb\tc\n1\t2\t3".encode("utf-8")
        assert detect_separator(raw, "utf-8") == "\t"


class TestLoadFile:
    def test_csv_semicolon(self):
        content = "Nom;Prenom;Ville\nDupont;Jean;Paris\nMartin;Marie;Lyon\n"
        f = FakeFile(make_csv(content), "test.csv")
        result = load_file(f)
        assert result["type"] == "csv"
        assert "data" in result["dataframes"]
        df = result["dataframes"]["data"]
        assert len(df) == 2
        assert "Nom" in df.columns

    def test_csv_comma(self):
        content = "Nom,Prenom\nDupont,Jean\n"
        f = FakeFile(make_csv(content), "test.csv")
        result = load_file(f)
        df = result["dataframes"]["data"]
        assert "Nom" in df.columns

    def test_csv_bom_stripped(self):
        content = "\ufeffNom;Ville\nDupont;Paris\n"
        f = FakeFile(make_csv(content), "test.csv")
        result = load_file(f)
        df = result["dataframes"]["data"]
        # La colonne ne doit pas avoir le BOM
        assert "Nom" in df.columns

    def test_xlsx_single_sheet(self):
        raw = make_xlsx({"Nom": ["Dupont", "Martin"], "Ville": ["Paris", "Lyon"]})
        f = FakeFile(raw, "test.xlsx")
        result = load_file(f)
        assert result["type"] == "excel"
        assert len(result["sheets"]) == 1
        df = result["dataframes"][result["sheets"][0]]
        assert len(df) == 2

    def test_xlsx_columns(self):
        raw = make_xlsx({"Civilite": ["Mr"], "Nom": ["Dupont"], "CodePostal": ["75001"]})
        f = FakeFile(raw, "test.xlsx")
        result = load_file(f)
        df = result["dataframes"][result["sheets"][0]]
        assert "Civilite" in df.columns
        assert "CodePostal" in df.columns

    def test_unsupported_format(self):
        f = FakeFile(b"data", "test.pdf")
        with pytest.raises(ValueError, match="non support"):
            load_file(f)

    def test_csv_returns_string_values(self):
        content = "CodePostal;Ville\n75001;Paris\n"
        f = FakeFile(make_csv(content), "test.csv")
        result = load_file(f)
        df = result["dataframes"]["data"]
        # Les valeurs doivent être des chaînes (object ou StringDtype selon pandas)
        assert str(df.at[0, "CodePostal"]) == "75001"

    def test_fixtures_demo_standard(self):
        import os
        fixture = os.path.join(os.path.dirname(__file__), "fixtures", "demo_standard.xlsx")
        with open(fixture, "rb") as fp:
            raw = fp.read()

        class RealFile:
            name = "demo_standard.xlsx"
            def read(self): return raw
            def seek(self, p): pass

        result = load_file(RealFile())
        assert result["type"] == "excel"
        df = result["dataframes"][result["sheets"][0]]
        assert len(df) > 0

    def test_fixtures_csv(self):
        import os
        fixture = os.path.join(os.path.dirname(__file__), "fixtures", "demo_csv_semicolon.csv")
        with open(fixture, "rb") as fp:
            raw = fp.read()

        class RealFile:
            name = "demo_csv_semicolon.csv"
            def read(self): return raw
            def seek(self, p): pass

        result = load_file(RealFile())
        assert result["type"] == "csv"
        df = result["dataframes"]["data"]
        assert len(df) > 0
