# CLAUDE.md — Instructions pour Claude Code
# Projet : NormAdress — Mise en conformité de fichiers Excel pour publipostage Word

## Contexte métier

NormAdress est une application web interne utilisée par une entreprise de routage postal. Les clients fournissent des fichiers Excel contenant des listes d'adresses pour réaliser des publipostages (impression + mise sous pli + envoi postal). Ces fichiers sont souvent mal formatés et nécessitent une mise en conformité avant utilisation dans Word.

---

## Stack technique obligatoire

- **Backend** : Python 3.11+
- **Interface** : Streamlit (pas Flask, pas FastAPI — Streamlit uniquement)
- **Traitement fichiers** : pandas + openpyxl
- **Tests** : pytest + pytest-cov
- **Export** : openpyxl pour la génération du fichier Excel propre
- **Base de données** : aucune en v1 — application 100% stateless

---

## Pipeline de déploiement à mettre en place

Claude Code doit configurer l'intégralité du pipeline suivant :

```
Développement local → GitHub (push sur main) → Render (déploiement automatique)
```

### Étape 1 — Initialisation Git et GitHub

Le repo GitHub existe déjà : **https://github.com/Cmoutier/NormAdress**

```bash
git init
git add .
git commit -m "feat: initial commit NormAdress"
git remote add origin https://github.com/Cmoutier/NormAdress.git
git branch -M main
git push -u origin main
```

### Étape 2 — Fichiers de configuration Render

Créer le fichier `render.yaml` à la racine :

```yaml
services:
  - type: web
    name: normadress
    env: python
    buildCommand: pip install -r requirements.txt
    startCommand: streamlit run app.py --server.port $PORT --server.address 0.0.0.0 --server.headless true
    envVars:
      - key: PYTHON_VERSION
        value: 3.11.0
    plan: free
```

Créer aussi `.streamlit/config.toml` :

```toml
[server]
headless = true
enableCORS = false
enableXsrfProtection = false

[theme]
primaryColor = "#1E6B3C"
backgroundColor = "#FFFFFF"
secondaryBackgroundColor = "#F2F2F2"
textColor = "#1A1A1A"
font = "sans serif"
```

### Étape 3 — Instructions de connexion Render (à afficher à l'utilisateur)

L'utilisateur possède déjà un compte Render. Une fois le code pushé sur GitHub,
Claude Code doit afficher ces instructions :

```
DÉPLOIEMENT RENDER — À FAIRE UNE SEULE FOIS MANUELLEMENT :

Vous avez déjà un compte Render — ajoutez simplement un nouveau service :

1. Connectez-vous sur https://render.com
2. Dans votre dashboard, cliquer "New +" → "Web Service"
3. Sélectionner "Build and deploy from a Git repository"
4. Connecter GitHub si ce n'est pas déjà fait, puis sélectionner "Cmoutier/NormAdress"
5. Render détecte automatiquement render.yaml — vérifier que les paramètres sont corrects
6. Cliquer "Create Web Service"
7. Le déploiement démarre automatiquement (3-5 minutes)
8. Chaque push sur la branche "main" redéploiera l'application automatiquement

Note : le plan gratuit Render permet plusieurs services — pas de conflit avec vos
services existants. Les 750h/mois de compute sont partagées entre tous vos services.

URL de l'application : https://normadress.onrender.com (ou similaire selon disponibilité)
```

### Étape 4 — GitHub Actions CI

Créer `.github/workflows/ci.yml` :

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install -r requirements.txt
      - run: pytest tests/ -v --cov=cleaner --cov-fail-under=90
```

---

## Configuration MCP pour le développement

Claude Code doit créer `.claude/mcp_config.json` :

```json
{
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": [
        "-y",
        "@modelcontextprotocol/server-filesystem",
        "/chemin/vers/normadress"
      ]
    },
    "github": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-github"],
      "env": {
        "GITHUB_PERSONAL_ACCESS_TOKEN": "${GITHUB_TOKEN}"
      }
    }
  }
}
```

Remplacer `/chemin/vers/normadress` par le chemin absolu réel du projet.
Le `GITHUB_TOKEN` doit être défini en variable d'environnement locale par l'utilisateur.

Le MCP GitHub permet à Claude Code de : créer des commits, ouvrir des pull requests,
lire l'état du repo et créer des issues pour tracker les bugs détectés pendant les tests.

---

## Structure de projet imposée

```
normadress/
├── app.py                    # Point d'entrée Streamlit
├── render.yaml               # Configuration déploiement Render
├── requirements.txt          # Dépendances Python avec versions figées
├── README.md                 # Documentation utilisateur
├── .github/
│   └── workflows/
│       └── ci.yml            # Pipeline CI GitHub Actions
├── .streamlit/
│   └── config.toml           # Thème et config serveur Streamlit
├── .claude/
│   └── mcp_config.json       # Configuration MCP pour développement
├── cleaner/
│   ├── __init__.py
│   ├── loader.py             # Chargement et détection structure fichier
│   ├── mapper.py             # Mapping colonnes → champs standards
│   ├── rules.py              # Toutes les règles de nettoyage (testables unitairement)
│   ├── consolidator.py       # Consolidation lignes d'adresse + éclatement multi-contacts
│   └── exporter.py           # Génération Excel propre + rapport texte
└── tests/
    ├── test_rules.py
    ├── test_mapper.py
    ├── test_consolidator.py
    └── fixtures/
        ├── demo_standard.xlsx
        ├── demo_multi_contacts.xlsx
        ├── demo_adresses_mal_remplies.xlsx
        ├── demo_colonnes_synonymes.xlsx
        └── demo_csv_semicolon.csv
```

---

## requirements.txt imposé

```
streamlit==1.32.0
pandas==2.2.1
openpyxl==3.1.2
pytest==8.1.1
pytest-cov==5.0.0
chardet==5.2.0
```

---

## Champs standards de sortie (noms de colonnes dans l'Excel exporté)

Ces noms doivent être EXACTEMENT respectés — ce sont les noms de champs de fusion Word clients :

| Nom colonne Excel | Description |
|---|---|
| Civilite | M. / Mme / Mlle |
| Nom | Nom de famille en MAJUSCULES |
| Prenom | Prénom en Titre |
| Societe | Raison sociale |
| Adresse1 | Première ligne d'adresse (toujours remplie si adresse disponible) |
| Adresse2 | Deuxième ligne (complément) |
| Adresse3 | Troisième ligne (bâtiment, résidence…) |
| CodePostal | 5 chiffres avec zéro initial |
| Ville | En MAJUSCULES |

---

## Règles de nettoyage — spécifications exactes

### Civilité
- `M`, `Mr`, `MR`, `Monsieur`, `monsieur`, `M.` → `M.`
- `Mme`, `MME`, `Madame`, `madame`, `mme`, `mme.` → `Mme`
- `Mlle`, `MLLE`, `Mademoiselle` → `Mlle`
- Valeur non reconnue → laisser telle quelle, signaler dans le rapport

### Nom
- Tout convertir en MAJUSCULES
- Supprimer les espaces en début/fin
- Espaces multiples → espace simple

### Prénom
- Format Titre : première lettre de chaque mot en majuscule
- Prénoms composés avec tiret : `jean-pierre` → `Jean-Pierre`
- Particules `de`, `du`, `de la` restent en minuscules

### Code postal
- Supprimer tous les espaces
- Valeur 1000–9999 (4 chiffres) → zéro préfixé : `1000` → `01000`
- Valeur 100–999 (3 chiffres) → deux zéros : `750` → `00750`
- Déjà 5 chiffres → laisser tel quel
- Valeur non numérique ou longueur incorrecte → signaler dans le rapport

### Ville
- Tout convertir en MAJUSCULES
- Supprimer espaces parasites

### Espaces et caractères
- Supprimer BOM Unicode (U+FEFF)
- Espaces insécables (U+00A0) → espace normale
- U+200B (zero-width space) → supprimer
- Tabulations et retours à la ligne → espace simple
- Espaces multiples consécutifs → espace simple
- Strip début et fin de chaque cellule

### Consolidation des lignes d'adresse
RÈGLE CRITIQUE : Adresse1 ne doit JAMAIS être vide si Adresse2 ou Adresse3 est remplie.
- Adresse1 vide + Adresse2 remplie → Adresse1←Adresse2, Adresse2←Adresse3, Adresse3←''
- Adresse1 et 2 vides + Adresse3 remplie → Adresse1←Adresse3, Adresse2/3←''
- Chaque consolidation tracée dans le rapport (ligne + valeurs avant/après)

### Lignes vides
- Vide si Nom ET Adresse1 ET CodePostal sont tous vides après nettoyage
- Supprimées et comptées dans le rapport

### Doublons
- Doublon si Nom + CodePostal identiques (après nettoyage, en minuscules)
- SIGNALÉS uniquement — jamais supprimés automatiquement
- Listés dans le rapport avec numéro de ligne original

---

## Détection automatique du mapping (mapper.py)

```python
SYNONYMS = {
    'Civilite': ['civilite', 'civ', 'titre', 'title', 'gender', 'sexe', 'salutation', 'mr/mme'],
    'Nom': ['nom', 'name', 'lastname', 'last_name', 'nom_famille', 'surname', 'nomdefamille'],
    'Prenom': ['prenom', 'prénom', 'firstname', 'first_name', 'forename', 'prenoms'],
    'Societe': ['societe', 'société', 'company', 'entreprise', 'organization', 'raisonsociale', 'raison_sociale'],
    'Adresse1': ['adresse1', 'adresse', 'address', 'rue', 'street', 'adr1', 'voie', 'ligne1'],
    'Adresse2': ['adresse2', 'complement', 'address2', 'adr2', 'complement_adresse', 'ligne2'],
    'Adresse3': ['adresse3', 'address3', 'adr3', 'ligne3', 'batiment', 'immeuble', 'residence'],
    'CodePostal': ['codepostal', 'code_postal', 'cp', 'zip', 'postal', 'postcode'],
    'Ville': ['ville', 'city', 'commune', 'town', 'localite'],
}
```

Normalisation : tout en minuscules, supprimer tout ce qui n'est pas alphanumérique.

---

## Gestion des fichiers multi-contacts par ligne

- Détecter si plusieurs colonnes mappent sur le même champ (ex: 2 colonnes "Nom")
- Afficher un `st.warning` avec confirmation `st.checkbox`
- Éclater chaque ligne source en N lignes (une par contact)
- Champs communs (adresse, CP, ville, société) dupliqués sur chaque ligne

---

## Interface Streamlit — comportement attendu

1. **Upload** : `st.file_uploader` acceptant xlsx, xls, csv
2. **Mapping** : tableau éditable colonne source → champ cible (détection auto pré-remplie)
3. **Alerte multi-contacts** : `st.warning` + confirmation si détecté
4. **Options** : cases à cocher pour chaque règle (toutes cochées par défaut)
5. **Lancement** : bouton "Mettre en conformité"
6. **Résultats** :
   - Métriques : lignes importées / exportées / doublons / supprimées
   - Tableau avec coloration (vert = corrigé, orange = adresse consolidée, rouge = doublon)
   - Liste détaillée des doublons
   - Bouton téléchargement Excel propre
   - Bouton téléchargement rapport TXT

---

## Exigences de qualité

- Couverture minimale : 90% sur `rules.py` et `consolidator.py`
- Aucune exception non gérée → toujours `st.error()` avec message clair
- Fichiers multi-feuilles → `st.selectbox` pour choisir la feuille
- CSV → détection automatique du séparateur via `chardet`
- Taille max recommandée : 50 000 lignes → `st.warning` au-delà
- Ne jamais modifier le fichier source — copie en mémoire uniquement

---

## Commandes de développement

```bash
# Installation
pip install -r requirements.txt

# Lancement local
streamlit run app.py

# Tests
pytest tests/ -v --cov=cleaner --cov-report=term-missing
pytest tests/ --cov=cleaner --cov-fail-under=90

# Déploiement
git add .
git commit -m "feat: description"
git push origin main
# → Render redéploie automatiquement
```

---

## Ce qu'il ne faut PAS faire

- Ne pas utiliser Flask, FastAPI ou Vercel — Streamlit + Render uniquement
- Ne pas supprimer automatiquement les doublons — signaler seulement
- Ne pas modifier les fichiers sources — copie en mémoire uniquement
- Ne pas utiliser xlrd pour les .xlsx (déprécié) — openpyxl uniquement
- Ne pas hardcoder les chemins de fichiers
- Ne pas ajouter de base de données en v1 — application stateless
