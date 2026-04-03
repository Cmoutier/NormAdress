"""Chargement et détection de la structure du fichier source."""
import io
import chardet
import pandas as pd


def detect_encoding(raw_bytes: bytes) -> str:
    result = chardet.detect(raw_bytes)
    return result.get("encoding") or "utf-8"


def detect_separator(raw_bytes: bytes, encoding: str) -> str:
    sample = raw_bytes[:4096].decode(encoding, errors="replace")
    counts = {sep: sample.count(sep) for sep in [";", ",", "\t", "|"]}
    return max(counts, key=counts.get)


def load_file(uploaded_file) -> dict:
    """
    Charge un fichier uploadé (xlsx, xls, csv).
    Retourne un dict :
        {
            "type": "excel" | "csv",
            "sheets": [str],           # noms des feuilles (excel uniquement)
            "dataframes": {sheet: df}, # ou {"data": df} pour csv
        }
    """
    name = uploaded_file.name.lower()
    raw = uploaded_file.read()
    uploaded_file.seek(0)

    if name.endswith(".csv"):
        encoding = detect_encoding(raw)
        separator = detect_separator(raw, encoding)
        # Supprimer BOM
        text = raw.decode(encoding, errors="replace").lstrip("\ufeff")
        df = pd.read_csv(
            io.StringIO(text),
            sep=separator,
            dtype=str,
            keep_default_na=False,
        )
        return {"type": "csv", "sheets": ["data"], "dataframes": {"data": df}}

    elif name.endswith((".xlsx", ".xls")):
        excel = pd.ExcelFile(io.BytesIO(raw), engine="openpyxl")
        sheets = excel.sheet_names
        dataframes = {}
        for sheet in sheets:
            dataframes[sheet] = pd.read_excel(
                excel, sheet_name=sheet, dtype=str, keep_default_na=False
            )
        return {"type": "excel", "sheets": sheets, "dataframes": dataframes}

    else:
        raise ValueError(f"Format non supporté : {name}")
