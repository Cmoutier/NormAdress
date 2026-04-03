# CLAUDE.md — Instructions pour Claude Code
# Projet : NormAdress — Mise en conformité de fichiers Excel pour publipostage Word

## Contexte métier

NormAdress est une application web interne utilisée par une entreprise de routage postal. Les clients fournissent des fichiers Excel contenant des listes d'adresses pour réaliser des publipostages (impression + mise sous pli + envoi postal). Ces fichiers sont souvent mal formatés et nécessitent une mise en conformité avant utilisation dans Word.

L'application applique les règles de la norme **La Poste NF Z 10-011** (RNVP — Restructuration, Normalisation et Validation Postale) et génère un **BAT (Bon À Tirer)** imprimable pour validation client.

---

## Stack technique

- **Backend** : Python 3.11+
- **Interface** : Streamlit (pas Flask, pas FastAPI — Streamlit uniquement)
- **Traitement fichiers** : pandas + openpyxl
- **Tests** : pytest + pytest-cov
- **Export** : openpyxl (Excel coloré) + HTML (BAT) + JSON (travaux)
- **Base de données** : aucune — application 100% stateless
- **Favicon** : PIL/Pillow (conversion SVG → PNG)

---

## Pipeline de déploiement

```
Développement local → GitHub (push sur main) → Render (déploiement automatique)
```

- Repo GitHub : **https://github.com/Cmoutier/NormAdress**
- URL application : **https://normadress.onrender.com**
- CI : GitHub Actions (`.github/workflows/ci.yml`)
- Render se met en veille après 15 min d'inactivité (plan gratuit — cold start ~60s)

```bash
git add .
git commit -m "feat: description"
git push origin main
# → Render redéploie automatiquement
```

---

## Structure du projet

```
normadress/
├── app.py                    # Point d'entrée Streamlit (interface complète)
├── render.yaml               # Configuration déploiement Render
├── requirements.txt          # Dépendances Python
├── favicon.svg               # SVG source du favicon (tableur + baguette magique)
├── favicon.png               # PNG 128×128 fond transparent (généré depuis favicon.svg)
├── favicon_src.svg           # SVG intermédiaire (icône seule sans texte)
├── logo.svg                  # Logo complet NormAdress (icône + texte)
├── README.md
├── .github/
│   └── workflows/
│       └── ci.yml
├── .streamlit/
│   └── config.toml           # Thème vert #1E6B3C
├── .claude/
│   └── mcp_config.json
├── cleaner/
│   ├── __init__.py
│   ├── loader.py             # Chargement Excel/CSV, détection encoding/séparateur
│   ├── mapper.py             # Mapping colonnes → champs standards (synonymes)
│   ├── rules.py              # Règles de nettoyage (civilité, nom, prénom, CP, ville…)
│   ├── consolidator.py       # Consolidation adresses + doublons + multi-contacts
│   ├── coherence.py          # Contrôles de cohérence inter-champs
│   ├── laposte.py            # Règles La Poste NF Z 10-011 + format_envelope_lines
│   ├── bat.py                # Génération BAT HTML (Bon À Tirer)
│   └── exporter.py           # Génération Excel coloré + rapport TXT
└── tests/
    ├── __init__.py
    ├── test_rules.py
    ├── test_mapper.py
    ├── test_consolidator.py
    ├── test_coherence.py
    ├── test_laposte.py
    ├── test_bat.py
    ├── test_loader.py
    ├── test_exporter.py
    ├── create_fixtures.py    # Script de génération des fixtures
    └── fixtures/
        ├── demo_standard.xlsx
        ├── demo_multi_contacts.xlsx
        ├── demo_adresses_mal_remplies.xlsx
        ├── demo_colonnes_synonymes.xlsx
        └── demo_csv_semicolon.csv
```

---

## requirements.txt

```
streamlit>=1.32.0
pandas>=2.2.1
openpyxl>=3.1.2
pytest>=8.1.1
pytest-cov>=5.0.0
chardet>=5.2.0
Pillow>=10.0.0
```

> Les versions sont assouplies (`>=`) pour compatibilité avec Render (Python 3.11).

---

## Champs standards de sortie — noms de fusion Word

Ces noms doivent être **EXACTEMENT** respectés :

| Champ | Description | Norme La Poste |
|---|---|---|
| `Civilite` | M. / Mme / Mlle | — |
| `Nom` | Nom de famille en MAJUSCULES | — |
| `Prenom` | Prénom en Titre | — |
| `Societe` | Raison sociale | L1 (B2B) |
| `Adresse1` | N° et libellé de voie | **L4 — obligatoire** |
| `Adresse2` | BP, lieu-dit, complément distribution | L5 |
| `Adresse3` | Bâtiment, résidence, étage | L3 |
| `CodePostal` | 5 chiffres avec zéro initial | L6 (1re partie) |
| `Ville` | En MAJUSCULES | L6 (2e partie) |

### Structure enveloppe NF Z 10-011 (6 lignes max)

```
L1 — Raison sociale  OU  Civilité Prénom NOM
L2 — Contact B2B (À L'ATTENTION DE…)  OU  complément d'identité
L3 — Adresse3 : bâtiment, résidence, étage
L4 — Adresse1 : N° et libellé de voie  ← OBLIGATOIRE
L5 — Adresse2 : BP, CS, TSA, lieu-dit
L6 — CODE POSTAL  VILLE  (ou CEDEX)
```

---

## Modules cleaner/ — description détaillée

### loader.py
- Charge `.xlsx`, `.xls`, `.csv`
- Détecte l'encoding via `chardet`, le séparateur CSV automatiquement
- Retourne `{"type", "sheets", "dataframes"}` — ne modifie JAMAIS le fichier source

### mapper.py
- `auto_map(columns)` → dict `{col_source: champ_standard}` via table de synonymes
- `detect_multi_contacts(mapping)` → détecte les doublons de champ (ex : 2 colonnes "Nom")
- `normalize_col(col)` → minuscules + suppression accents + suppression non-alphanum

### rules.py
- `clean_whitespace(value)` — BOM, espaces insécables, zero-width, tabulations, strip
- `clean_civilite(value)` → `(valeur, ok)` — M./Mme/Mlle + signalement si inconnu
- `clean_nom(value)` → MAJUSCULES + strip
- `clean_prenom(value)` → Titre + tirets composés + particules minuscules
- `clean_codepostal(value)` → `(valeur, ok)` — zéro-padding + validation
- `clean_ville(value)` → MAJUSCULES
- `apply_rules(df, options)` → `(df_clean, rapport_lignes)`

### consolidator.py
- `consolidate_addresses(df)` → décale Adresse1/2/3 si L1 vide — retourne `(df, journal)`
- `remove_empty_rows(df)` → supprime si Nom ET Adresse1 ET CodePostal tous vides
- `detect_duplicates(df)` → Nom+CodePostal identiques — SIGNALE, ne supprime PAS
- `explode_multi_contacts(df, multi_contacts, source_df)` → une ligne par contact

### coherence.py
Contrôles inter-champs — toutes les fonctions retournent des alertes avec `auto_fixable: bool` :

| Fonction | Action | Auto |
|---|---|---|
| `fix_codepostal_float` | `75001.0` → `75001` | ✅ |
| `detect_civilite_in_nom` | `M. DUPONT` → Civilite=M., Nom=DUPONT | ✅ |
| `detect_cedex` | `paris cedex 08` → `PARIS CEDEX 08` | ✅ |
| `detect_nom_prenom_combine` | `DUPONT Jean` avec Prénom vide | ⚠ |
| `check_societe_contact` | Société + Contact → ordre postal recommandé | ⚠ |
| `detect_full_address_in_field` | CP détecté dans Adresse1 | ⚠ |
| `detect_nom_sans_adresse` | Contact sans adresse ni CP | ⚠ |
| `run_all(df)` | Point d'entrée — exécute tout dans l'ordre | — |

### laposte.py
Règles La Poste NF Z 10-011 + RNVP :

- `remove_accents(value)` — désaccentuation OCR (É→E, À→A, Ç→C)
- `normalize_voie(adresse)` — AVENUE→AV, BOULEVARD→BD, IMPASSE→IMP… (table RNVP complète)
- `clean_address_punctuation(value)` — virgules, parenthèses, points dans adresses
- `normalize_bp_cs(value)` — B.P.123→BP 123, CS70001→CS 70001, TSA→TSA
- `format_attention(civ, prenom, nom)` → `"A L'ATTENTION DE M. JEAN DUPONT"`
- `check_completude(df)` — Identité + Adresse1 + CodePostal + Ville obligatoires
- `apply_laposte_rules(df, options)` → `(df, alerts)` — point d'entrée
- `format_envelope_lines(row)` → `list[tuple[str, str]]` — lignes L1 à L6 selon la norme

### bat.py
Génération du BAT (Bon À Tirer) HTML :

- `generate_bat(df, nom_travail, doublons, consolidation_journal)` → HTML complet
- Grille 3 colonnes, CSS `@media print`, plis numérotés
- Badges rouge (doublon) et jaune (adresse réorganisée)
- Mention NF Z 10-011, imprimable via Ctrl+P → PDF

### exporter.py
- `export_excel(df, original_df, rapport_lignes, doublons, consolidation_journal)` → bytes
  - Coloration : vert = corrigé, orange = adresse consolidée, rouge = doublon
- `export_rapport(...)` → string TXT avec résumé + détail de chaque anomalie

---

## Interface Streamlit — app.py

### Sidebar
- **Gestion des travaux** : chargement `.json` (restaure mapping + options) + sauvegarde
- Format JSON : `{version, nom, date, notes, mapping, options, laposte}`

### Flux principal (étapes numérotées)

1. **Import** — `st.file_uploader` (xlsx/xls/csv) + sélection feuille si multi-feuilles
2. **Mapping** — `st.data_editor` tableau compact : colonne source | exemple | champ cible
   - Détection auto pré-remplie + priorité au travail chargé
3. **Multi-contacts** — si détecté : `st.warning` + case à cocher pour éclater
4. **Options** — expander "Règles de base" + expander "Conformité La Poste NF Z 10-011"
5. **Lancement** — bouton "Mettre en conformité"

### Pipeline de traitement (dans l'ordre)
1. Construction DataFrame mappé
2. Éclatement multi-contacts (si activé)
3. `run_coherence(df)` — corrections auto + alertes
4. `apply_rules(df, options)` — nettoyage de base
5. Mention "À L'ATTENTION DE" (si option activée)
6. `apply_laposte_rules(df, laposte_options)` — conformité La Poste
7. `consolidate_addresses(df)` (si option activée)
8. `remove_empty_rows(df)` (si option activée)
9. `detect_duplicates(df)`

### Résultats — 3 onglets

**Onglet "Aperçu enveloppes"**
- Navigation : ⏮ Précédent · n/total · Suivant ⏭ + saut direct au numéro de pli
- Côte à côte : carte source (données brutes) → enveloppe normalisée (L1-L6)
- Badge doublon / adresse réorganisée sur le pli courant

**Onglet "Tableau complet"**
- DataFrame coloré (rouge = doublon, jaune = consolidé)

**Onglet "Alertes et anomalies"**
- Corrections automatiques (✅), points à vérifier (⚠), alertes La Poste (📮), doublons, anomalies

### Téléchargements
- `adresses_normalisees.xlsx` — Excel coloré
- `rapport_normadress.txt` — rapport texte
- `BAT_YYYYMMDD_HHMM.html` — Bon À Tirer HTML imprimable

---

## Règles de nettoyage — spécifications exactes

### Civilité
- `M`, `Mr`, `MR`, `Monsieur`, `M.`, `Mr.` → `M.`
- `Mme`, `MME`, `Madame`, `mme`, `mme.` → `Mme`
- `Mlle`, `MLLE`, `Mademoiselle` → `Mlle`
- Non reconnue → laisser, signaler dans le rapport

### Nom
- MAJUSCULES + strip + espaces multiples → simple

### Prénom
- Format Titre : première lettre de chaque mot
- Tirets : `jean-pierre` → `Jean-Pierre`
- Particules `de`, `du`, `de la`, `d` → minuscules

### Code postal
- `75001.0` (float Excel) → `75001` (via `coherence.fix_codepostal_float`)
- 4 chiffres (1000-9999) → zéro préfixé : `1000` → `01000`
- 3 chiffres → deux zéros : `750` → `00750`
- 5 chiffres → laisser tel quel
- Non numérique → signaler

### Espaces et caractères
- BOM U+FEFF, espaces insécables U+00A0, zero-width U+200B
- Tabulations/retours à la ligne → espace
- Espaces multiples → simple, strip

### Consolidation adresses (règle critique)
- Adresse1 ne doit **JAMAIS** être vide si Adresse2 ou Adresse3 est remplie
- Adresse1 vide + Adresse2 remplie → décalage : A1←A2, A2←A3, A3←''
- Adresse1 et A2 vides + A3 remplie → A1←A3, A2/A3←''

### Doublons
- Critère : Nom + CodePostal identiques (minuscules)
- **SIGNALÉS uniquement — jamais supprimés automatiquement**

---

## Contrôles de cohérence inter-champs

Exécutés **avant** les règles de nettoyage via `coherence.run_all()` :

| Cas | Exemple | Traitement |
|---|---|---|
| CP float Excel | `75001.0` | Auto → `75001` |
| Civilité dans le Nom | `M. DUPONT` | Auto → Civ=M., Nom=DUPONT |
| CEDEX dans Ville | `paris cedex 08` | Auto → `PARIS CEDEX 08` |
| Nom + Prénom combinés | `DUPONT Jean` (Prénom vide) | Signalé |
| Société + Contact | Ordre postal recommandé | Signalé |
| Adresse complète dans un champ | CP détecté dans Adresse1 | Signalé |
| Contact sans adresse | Nom renseigné mais Adresse1 et CP vides | Signalé |

---

## Conformité La Poste NF Z 10-011

Options disponibles dans l'interface :

| Option | Par défaut | Description |
|---|---|---|
| BP / CS / TSA | ✅ | `B.P.123` → `BP 123` |
| Ponctuation parasite | ✅ | Virgules, parenthèses dans les adresses |
| Vérifier la complétude | ✅ | Identité + Adresse1 + CP + Ville obligatoires |
| À L'ATTENTION DE (B2B) | ⬜ | Société + Contact → mention réglementaire en Adresse2 |
| Abréviations RNVP | ⬜ | AVENUE→AV, BOULEVARD→BD, IMPASSE→IMP… |
| Désaccentuation OCR | ⬜ | É→E, À→A, Ç→C (active aussi avec abréviations) |

---

## Gestion des travaux (save/load)

Format JSON sauvegardé :
```json
{
  "version": "1.1",
  "nom": "Client XYZ — Campagne Mai 2026",
  "date": "03/04/2026 14:30",
  "notes": "En attente validation BP...",
  "mapping": {"Colonne source": "ChampStandard"},
  "options": {"espaces": true, "civilite": true, ...},
  "laposte": {"bp_cs": true, "completude": true, ...}
}
```

Au rechargement : pré-remplit le tableau de mapping + toutes les options.
Priorité : travail chargé > détection automatique.

---

## Exigences de qualité

- Couverture tests : **≥ 90%** sur le package `cleaner/` (actuellement ~95%)
- 228 tests passent (pytest)
- Aucune exception non gérée → toujours `st.error()` avec message clair
- Fichiers multi-feuilles → `st.selectbox` pour choisir la feuille
- CSV → détection automatique du séparateur via `chardet`
- Taille max recommandée : 50 000 lignes → `st.warning` au-delà
- Ne **jamais** modifier le fichier source — copie en mémoire uniquement

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

# Régénérer les fixtures de test
python tests/create_fixtures.py

# Régénérer le favicon depuis favicon.svg
python -c "
from svglib.svglib import svg2rlg
from reportlab.graphics import renderPM
from PIL import Image
import io
drawing = svg2rlg('favicon.svg')
scale = 128 / max(drawing.width, drawing.height)
drawing.width *= scale; drawing.height *= scale
drawing.transform = (scale, 0, 0, scale, 0, 0)
buf = io.BytesIO()
renderPM.drawToFile(drawing, buf, fmt='PNG')
buf.seek(0)
img = Image.open(buf).convert('RGBA')
data = img.getdata()
new_data = [(255,255,255,0) if r>240 and g>240 and b>240 else (r,g,b,a) for r,g,b,a in data]
img.putdata(new_data)
img.save('favicon.png')
"

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
- Ne pas ajouter de base de données — application stateless
- Ne pas fixer les versions de dépendances avec `==` (utiliser `>=` pour compatibilité Render)
- Ne pas supprimer le favicon.svg ni le logo.svg — ils sont la source des assets visuels
