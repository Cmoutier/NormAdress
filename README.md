# NormAdress

Application web de mise en conformité de fichiers d'adresses pour publipostage Word.

## Fonctionnalités

- Import Excel (.xlsx, .xls) et CSV (détection automatique du séparateur)
- Détection automatique du mapping de colonnes
- Normalisation : civilités, noms, prénoms, codes postaux, villes
- Consolidation des lignes d'adresse (Adresse1 jamais vide si Adresse2/3 remplie)
- Détection des doublons (sans suppression automatique)
- Export Excel coloré + rapport TXT
- Gestion des fichiers multi-contacts

## Champs de sortie (noms de fusion Word)

`Civilite` · `Nom` · `Prenom` · `Societe` · `Adresse1` · `Adresse2` · `Adresse3` · `CodePostal` · `Ville`

## Installation

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Tests

```bash
pytest tests/ -v --cov=cleaner --cov-report=term-missing
```

## Déploiement

Push sur `main` → déploiement automatique sur Render.
