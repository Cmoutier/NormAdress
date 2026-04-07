# CLAUDE.md — Instructions pour Claude Code
# Projet : NormAdress — Composition d'adresses postales AFNOR pour publipostage
# Société : STEP — step.eco
# Repo : https://github.com/Cmoutier/NormAdress
# Version : 4.0 — FINALE

---

## LIRE EN PREMIER — Contexte métier critique

STEP est une entreprise de routage postal. Elle reçoit des fichiers Excel hétérogènes
de ses clients, contenant des destinataires mélangés (particuliers ET professionnels
dans le même fichier). Le client fournit également son propre fichier Word (courrier)
à chaque campagne.

NormAdress produit :
1. Un Excel conforme à la norme AFNOR XPZ-10-11 (6 lignes + champ Formule)
2. Le fichier Word du client modifié avec les champs de fusion insérés et l'Excel lié
3. Un PDF de BAT (blocs adresse uniquement) pour validation client

**NormAdress n'est PAS** un nettoyeur de colonnes.
**NormAdress EST** un compositeur d'adresses postales avec workflow de validation.

---

## Deux modes de publipostage

NormAdress gère deux modes distincts, détectés automatiquement et confirmés par l'opérateur :

### Mode POSTAL (envoi La Poste)
- Adresse complète requise : L4 (voie) + L6 (CP + Ville) obligatoires
- 6 lignes AFNOR complètes
- Alerte BLOQUANTE si L4 ou L6 vides

### Mode BAL INTERNE (remise en main propre / boîte aux lettres)
- Pas d'adresse postale — distribution interne dans un bâtiment (ex: technopole)
- Seules L1 (société) et L2 (contact) sont utilisées
- Alerte INFORMATIVE seulement si L4/L6 vides : "Mode remise en main propre — non conforme AFNOR, non bloquant"
- Le champ `Formule` est généré automatiquement (salutation personnalisée)
- Détection automatique : si aucune colonne adresse/voie n'est mappée → proposer ce mode

---

## Stack technique obligatoire

- **Backend** : Python 3.11+
- **Interface** : Streamlit
- **Base de données** : Supabase (PostgreSQL) — obligatoire pour la persistance
- **Traitement fichiers** : pandas + openpyxl
- **Génération PDF BAT** : reportlab
- **Manipulation Word** : python-docx (injection champs de fusion)
- **Tests** : pytest + pytest-cov (couverture ≥ 85% sur core/)
- **Drag & drop** : streamlit-sortables

---

## Schéma base de données Supabase

Créer ces tables dans Supabase AVANT tout développement :

```sql
CREATE TABLE dossiers (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  nom VARCHAR(200) NOT NULL,
  client VARCHAR(200),
  statut VARCHAR(50) DEFAULT 'en_cours',
  -- statuts : en_cours | a_valider | valide | exporte
  mode_distribution VARCHAR(20) DEFAULT 'postal',
  -- valeurs : postal | bal_interne
  parametres JSONB DEFAULT '{}',
  -- contient : ordre_nom_prenom, format_pro, pays_defaut,
  --            fichier_source_nom, fichier_word_nom,
  --            date_envoi_bat, date_validation_client
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE adresses (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  dossier_id UUID REFERENCES dossiers(id) ON DELETE CASCADE,
  ligne_source INTEGER,
  type_contact VARCHAR(20),       -- particulier | professionnel | inconnu
  type_detecte_auto BOOLEAN,
  -- Champ formule de politesse (mode BAL interne + optionnel mode postal)
  formule VARCHAR(200),
  -- ex: "Cher Monsieur Jean DUPONT," ou "Chers Messieurs LERBS et GIRARDIN,"
  -- 6 lignes AFNOR
  l1 VARCHAR(38),
  l2 VARCHAR(38),
  l3 VARCHAR(38),
  l4 VARCHAR(38),
  l5 VARCHAR(38),
  l6 VARCHAR(38),
  -- Alertes qualité
  alertes JSONB DEFAULT '[]',
  -- ex: [{"code":"LONGUEUR","ligne":"L1","valeur":42,"bloquant":false}]
  valide BOOLEAN DEFAULT false,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE mappings (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  dossier_id UUID REFERENCES dossiers(id) ON DELETE CASCADE,
  colonne_source VARCHAR(200),
  champ_cible VARCHAR(100),
  created_at TIMESTAMPTZ DEFAULT NOW()
);
```

Variables d'environnement (Render + `.env` local) :
```
SUPABASE_URL=https://xxxx.supabase.co
SUPABASE_KEY=eyJ...
```

---

## Structure du projet

```
normadress/
├── app.py                         # Point d'entrée Streamlit — tableau de bord
├── render.yaml
├── requirements.txt
├── README.md
├── .env.example
├── .github/workflows/ci.yml
├── .streamlit/
│   ├── config.toml                # Thème vert NormAdress
│   └── favicon.png
├── .claude/mcp_config.json
├── pages/
│   ├── 01_nouveau_dossier.py      # Création dossier + upload fichiers
│   ├── 02_mapping.py              # Mapping colonnes drag & drop
│   ├── 03_detection.py            # Détection pro/particulier + révision
│   ├── 04_composition.py          # Composition 6 lignes AFNOR + Formule
│   ├── 05_bat.py                  # PDF BAT adresses + validation client
│   └── 06_export.py               # Export Excel + Word fusionné
├── core/
│   ├── __init__.py
│   ├── db.py                      # Connexion Supabase + CRUD
│   ├── detector.py                # Détection pro/particulier + mode distribution
│   ├── mapper.py                  # Mapping colonnes → champs internes
│   ├── composer.py                # Construction 6 lignes AFNOR + Formule
│   ├── cleaner.py                 # Nettoyage (casse, CP, espaces, civilités)
│   ├── validator.py               # Contrôles qualité AFNOR
│   ├── pdf_generator.py           # PDF BAT blocs adresse
│   └── word_injector.py           # Injection champs fusion dans le Word client
└── tests/
    ├── test_detector.py
    ├── test_composer.py
    ├── test_cleaner.py
    ├── test_validator.py
    └── fixtures/
        ├── synerpa_sample.xlsx     # Pro avec contact, CP flottant
        ├── helioparc_sample.xlsx   # Multi-contacts sans adresse
        └── voeux_sample.xlsx       # Contact concaténé NOM Prénom
```

---

## Workflow utilisateur — les 6 étapes

### ÉTAPE 1 — Nouveau dossier (`pages/01_nouveau_dossier.py`)

**Tableau de bord (app.py)** : liste tous les dossiers avec statut coloré + date + bouton "Reprendre".
Statuts : 🟡 En cours | 🔵 À valider | 🟢 Validé | ✅ Exporté

**Création d'un dossier :**
- Nom du dossier (ex: "Gazette Synerpa — Avril 2025")
- Nom du client
- Upload fichier Excel source (xlsx, xls, csv)
- Upload fichier Word client (le courrier — .docx)
- **Paramètres campagne** :
  - Ordre identité : `AFNOR — Civilité Prénom NOM` (défaut) | `Civilité NOM Prénom`
  - Format pro : `Mode A — L1 Société / L2 Contact` (défaut) | `Mode B — L1 Contact / L2 Société`
  - Pays par défaut : France (modifiable)
  - En-tête détectée : auto-détecter | oui | non
- Sauvegarde en base avec statut `en_cours`

---

### ÉTAPE 2 — Mapping des colonnes (`pages/02_mapping.py`)

**Interface drag & drop** (streamlit-sortables) : colonnes source à gauche, champs cibles à droite.
Afficher les 3 premières valeurs de chaque colonne source pour aider l'opérateur.

**Champs cibles disponibles :**

```
── IDENTITÉ CONTACT 1 ──────────────────────────
civilite_1       Civilité contact 1
nom_1            Nom contact 1
prenom_1         Prénom contact 1
identite_1       Identité complète concaténée contact 1 (NOM Prénom — pas de découpage)

── IDENTITÉ CONTACT 2 (multi-contacts) ─────────
civilite_2       Civilité contact 2
nom_2            Nom contact 2
prenom_2         Prénom contact 2
identite_2       Identité complète concaténée contact 2

── IDENTITÉ CONTACT 3 (multi-contacts) ─────────
civilite_3       Civilité contact 3
nom_3            Nom contact 3
prenom_3         Prénom contact 3

── ORGANISATION ────────────────────────────────
societe          Raison sociale / Structure

── FORMULE DE POLITESSE ────────────────────────
formule_source   Formule existante dans le fichier (Cher/Chère/Chers...)
                 Si mappée : utilisée telle quelle
                 Si non mappée : générée automatiquement

── ADRESSE ─────────────────────────────────────
adresse_voie     Numéro + type + nom de voie → L4 AFNOR
adresse_comp_int Complément intérieur (appt, étage) → L2 AFNOR
adresse_comp_ext Complément extérieur (bât, résidence) → L3 AFNOR
adresse_lieu_dit Lieu-dit ou BP → L5 AFNOR
code_postal      Code postal → L6 AFNOR
ville            Ville → L6 AFNOR
pays             Pays (optionnel — ajouté en L6 si étranger)

── IDENTIFIANT ─────────────────────────────────
id_client        Identifiant unique (conservé intact dans l'export)
```

**Détection automatique du mapping par synonymes** (dans `core/mapper.py`) :

```python
SYNONYMS = {
    'civilite_1':    ['civilité', 'civilite', 'civ', 'titre', 'formule-1', 'civilité-1', 'salutation'],
    'nom_1':         ['nom', 'nom-1', 'name', 'lastname', 'nom_famille'],
    'prenom_1':      ['prénom', 'prenom', 'prénom-1', 'prenom-1', 'firstname'],
    'identite_1':    ['contact', 'destinataire', 'identité'],
    'civilite_2':    ['civilité-2', 'civilite-2', 'formule-2'],
    'nom_2':         ['nom-2', 'nom2'],
    'prenom_2':      ['prénom-2', 'prenom-2'],
    'civilite_3':    ['civilité7', 'civilite7', 'titre6'],
    'nom_3':         ['nom8'],
    'prenom_3':      ['prénom-3', 'prenom-3', 'prénom9', 'prenom9'],
    'societe':       ['raison sociale', 'société', 'societe', 'structure', 'company', 'entreprise', 'organisation'],
    'formule_source':['formule-1', 'formule', 'appel'],
    'adresse_voie':  ['rue 1', 'rue1', 'adresse 1', 'adresse1', 'adresse', 'rue', 'voie', 'address'],
    'adresse_comp_int': ['rue 2', 'rue2', 'adresse 2', 'adresse2', 'complement', 'appt'],
    'adresse_comp_ext': ['rue 3', 'rue3', 'adresse 3', 'adresse3', 'bâtiment', 'batiment', 'résidence'],
    'adresse_lieu_dit': ['lieu-dit', 'lieu dit', 'bp', 'service'],
    'code_postal':   ['cp', 'code postal', 'codepostal', 'zip', 'postal'],
    'ville':         ['ville', 'city', 'commune', 'localité'],
    'pays':          ['pays', 'country', 'nation'],
    'id_client':     ['id', 'identifiant', 'référence', 'ref', 'numéro'],
}

def normaliser_cle(s):
    """Minuscules + suppression tout ce qui n'est pas alphanumérique"""
    import re
    return re.sub(r'[^a-z0-9]', '', s.lower().strip())
```

**Détection du mode distribution** :
- Si aucun champ adresse (adresse_voie, code_postal, ville) n'est mappé après auto-détection
  → afficher : "Aucune colonne adresse détectée. S'agit-il d'un publipostage en remise
    directe (boîte aux lettres interne) ?" avec bouton Confirmer / Non, je veux mapper
- Mode BAL interne confirmé → sauvegardé dans `dossiers.mode_distribution = 'bal_interne'`

**Cas spécial — fichier sans adresse à joindre avec un second fichier** :
- Bouton "Joindre un second fichier (adresses)" → upload d'un second Excel
- L'opérateur choisit la colonne de jointure commune (ex: Structure = Société)
- Fusion des deux fichiers en mémoire avant de continuer

Le mapping est sauvegardé en base (table `mappings`).

---

### ÉTAPE 3 — Détection pro / particulier (`pages/03_detection.py`)

**Règle de détection automatique** (dans `core/detector.py`) :

```python
def detecter_type(row) -> str:
    """
    Priorité :
    1. Si 'societe' remplie → 'professionnel'
    2. Si 'societe' vide ET (nom_1 OU prenom_1 OU identite_1 rempli) → 'particulier'
    3. Si civilite_1 contient indicateur pro (SA, SAS, SARL, SCI, EURL, SASU, SEML) → 'professionnel'
    4. Sinon → 'inconnu'
    """
```

**Interface de révision** :
- Tableau coloré : 🟢 particulier | 🔵 professionnel | 🟠 inconnu
- Filtre par type
- Toggle de correction manuelle ligne par ligne
- Compteur temps réel : X particuliers / Y professionnels / Z inconnus
- Bouton "Valider la détection"

---

### ÉTAPE 4 — Composition AFNOR + Formule (`pages/04_composition.py`)

Cœur de `core/composer.py`.

#### Règles de composition selon le mode

```
══════════════════════════════════════════════════════════════
MODE POSTAL — PARTICULIER
══════════════════════════════════════════════════════════════
L1 = Civilité + Prénom + NOM          (ordre selon paramètre — AFNOR par défaut)
     Si identite_1 mappée → utiliser telle quelle (pas de reconstruction)
     ex AFNOR     : "M. Jean DUPONT"
     ex alternatif: "M. DUPONT Jean"
L2 = adresse_comp_int (appt, étage)   vide si absent
L3 = adresse_comp_ext (bât, résidence) vide si absent
L4 = adresse_voie                      ← OBLIGATOIRE en mode postal
L5 = adresse_lieu_dit                  vide si absent
L6 = CodePostal + VILLE                ← OBLIGATOIRE en mode postal
     Si pays étranger : CodePostal + VILLE + PAYS (en majuscules)
     ex France   : "75001 PARIS"
     ex étranger : "1000 BRUXELLES BELGIQUE"

Formule = générée automatiquement :
  1 homme   → "Cher Monsieur [Prénom NOM],"
  1 femme   → "Chère Madame [Prénom NOM],"
  Si formule_source mappée → utiliser la valeur source telle quelle

Si 2 contacts : créer DEUX LIGNES séparées, L2-L6 identiques
  Ligne A : L1 = contact 1
  Ligne B : L1 = contact 2

══════════════════════════════════════════════════════════════
MODE POSTAL — PROFESSIONNEL — FORMAT A (défaut)
══════════════════════════════════════════════════════════════
L1 = Raison sociale
L2 = Civilité + Prénom + NOM du contact (ordre selon paramètre)
     Si identite_1 mappée → utiliser telle quelle
     vide si pas de contact nommé
L3 = adresse_comp_ext                  vide si absent
L4 = adresse_voie                      ← OBLIGATOIRE en mode postal
L5 = adresse_lieu_dit                  vide si absent
L6 = CodePostal + VILLE [+ PAYS]       ← OBLIGATOIRE en mode postal

Formule = générée selon contacts (même règle que particulier)

══════════════════════════════════════════════════════════════
MODE POSTAL — PROFESSIONNEL — FORMAT B
══════════════════════════════════════════════════════════════
L1 = Civilité + Prénom + NOM du contact (ou identite_1)
L2 = Raison sociale
L3 à L6 = identiques au Format A

══════════════════════════════════════════════════════════════
MODE BAL INTERNE — tous types confondus
══════════════════════════════════════════════════════════════
L1 = Raison sociale (si pro) ou vide (si particulier)
L2 = "A l'attention de" + Civilité(s) + Prénom(s) + NOM(s)
     ex: "A l'attention de Monsieur Thierry LESUR"
     ex: "A l'attention de Messieurs Alexander LERBS et Nicolas GIRARDIN"
L3 = vide
L4 = vide  → alerte informative "Mode BAL interne — non conforme AFNOR"
L5 = vide
L6 = vide

Formule = générée automatiquement selon nombre et genre des contacts :
  1 homme           → "Cher Monsieur [Prénom NOM],"
  1 femme           → "Chère Madame [Prénom NOM],"
  2 hommes          → "Chers Messieurs [Prénom NOM1] et [Prénom NOM2],"
  2 femmes          → "Chères Mesdames [Prénom NOM1] et [Prénom NOM2],"
  homme + femme     → "Chers Monsieur [NOM1] et Madame [NOM2],"
  3 contacts        → "Chers Monsieur [NOM1], Madame [NOM2] et Monsieur [NOM3],"
  Si formule_source mappée → utiliser la valeur source telle quelle
```

#### Règles de nettoyage (dans `core/cleaner.py`)

**Civilités :**
```
Monsieur, monsieur, M, Mr, MR, M.   → M.
Madame, madame, Mme, MME, mme.      → Mme
Mademoiselle, Mlle, MLLE            → Mlle
Docteur, Dr, DR                     → Dr
Messieurs                           → Messieurs  (conservé pour multi-contacts)
Mesdames                            → Mesdames   (conservé pour multi-contacts)
```

**Code postal :**
- CP stocké en flottant Excel (69002.0) → convertir : `str(int(float(cp)))` puis padder
- 4 chiffres → zéro initial : `1000` → `01000`
- 3 chiffres → deux zéros : `750` → `00750`
- Déjà 5 chiffres → conserver
- Non numérique → conserver + alerte CP_INVALIDE_FR

**Noms :**
- Noms de famille → MAJUSCULES
- Prénoms → Format Titre (Jean-Pierre, Marie-Claire)
- Particules de, du, de la, des → minuscules dans les prénoms
- Si `identite_1` mappée (NOM Prénom concaténé) → nettoyage espaces uniquement, pas de transformation de casse (l'opérateur a déjà formaté)

**Ville :** MAJUSCULES, espaces nettoyés, CEDEX conservé

**Général :**
- BOM (U+FEFF), espaces insécables (U+00A0), U+200B → supprimés
- Tabulations, retours ligne → espace simple
- Espaces multiples → espace simple
- Strip début/fin

#### Contrôles qualité (dans `core/validator.py`)

```python
ALERTES = [
    # Longueur AFNOR — 38 caractères max (norme XPZ-10-11)
    {"code": "LONGUEUR",       "ligne": "Ln", "message": "L{n} dépasse 38 car. ({val} car.)",           "bloquant": False},

    # Mode postal — champs obligatoires
    {"code": "L4_VIDE",        "ligne": "L4", "message": "Voie manquante — adresse incomplète",         "bloquant": True},
    {"code": "L6_VIDE",        "ligne": "L6", "message": "CP/Ville manquants — adresse incomplète",     "bloquant": True},

    # Mode BAL interne
    {"code": "BAL_INTERNE",    "ligne": "",   "message": "Mode BAL interne — non conforme AFNOR",       "bloquant": False},

    # CP
    {"code": "CP_INVALIDE_FR", "ligne": "L6", "message": "CP '{val}' non conforme (5 chiffres)",        "bloquant": False},
    {"code": "ETRANGER",       "ligne": "L6", "message": "Adresse étrangère — vérification recommandée","bloquant": False},

    # Identité
    {"code": "L1_VIDE",        "ligne": "L1", "message": "Ligne 1 vide — destinataire non identifié",   "bloquant": False},
    {"code": "TYPE_INCONNU",   "ligne": "",   "message": "Type pro/particulier non déterminé",           "bloquant": False},
]
```

**Interface composition :**
- Tableau avec aperçu des 6 lignes + Formule pour chaque destinataire
- Icônes alertes en ligne (⚠ orange = non bloquant, 🔴 rouge = bloquant)
- Filtre "Uniquement les lignes avec alertes"
- Compteur alertes bloquantes / non bloquantes
- Édition manuelle d'une ligne AFNOR possible (clic sur la cellule)
- Toutes les données sauvegardées en base

---

### ÉTAPE 5 — BAT PDF (`pages/05_bat.py`)

**Génération PDF** (dans `core/pdf_generator.py`) avec reportlab.

**Format du PDF :**
Grille de blocs adresse, 4 par page (2 colonnes × 2 lignes), simulant des étiquettes.
Chaque bloc :
```
┌─────────────────────────────────────┐
│ M. Jean DUPONT                      │  ← L1
│ Appartement 12                      │  ← L2 (si remplie)
│ Résidence Les Pins                  │  ← L3 (si remplie)
│ 12 rue de la Paix                   │  ← L4
│ 75001 PARIS                         │  ← L6
└─────────────────────────────────────┘
```
- Les lignes vides ne s'affichent PAS (comme sur une vraie enveloppe)
- Les lignes dépassant 38 caractères sont surlignées en orange dans le PDF
- Numéro de ligne source affiché en petit en haut à droite du bloc (pour retrouver dans Excel)
- En-tête du PDF : nom du dossier + date de génération + nb de destinataires

**Workflow validation :**
- Bouton "Générer le PDF BAT" → téléchargement
- Bouton "Marquer comme envoyé au client" → statut `a_valider` + date enregistrée
- Bouton "Marquer comme validé par le client" → statut `valide` + date enregistrée

---

### ÉTAPE 6 — Export (`pages/06_export.py`)

#### 6a. Export Excel

Un seul fichier, un seul onglet "Adresses_NormAdress" :

| ID_CLIENT | Formule | L1 | L2 | L3 | L4 | L5 | L6 |
|---|---|---|---|---|---|---|---|
| 001 | Cher Monsieur Jean DUPONT, | M. Jean DUPONT | Appt 12 | | 12 rue de la Paix | | 75001 PARIS |
| 002 | Chers Messieurs... | 2AE ASSISTANCE... | A l'attention de... | | | | |

Règles Excel :
- Les cellules vides restent vides (pas de texte, pas d'espace)
- CP exporté en TEXT (pas en nombre) → `@` format dans openpyxl pour éviter la perte du zéro initial
- Les lignes avec alertes bloquantes sont colorées en rouge pâle dans Excel (fond #FCEAEA)
- Les lignes avec alertes non bloquantes sont colorées en orange pâle (#FEF3E6)
- Largeur des colonnes ajustée automatiquement

#### 6b. Export Word (dans `core/word_injector.py`)

Le fichier Word fourni par le client est modifié avec python-docx :

1. Détecter la zone adresse dans le document (chercher un marqueur ou une zone de texte)
2. Injecter les champs de fusion Word : `{ MERGEFIELD "L1" }`, `{ MERGEFIELD "Formule" }`, etc.
3. Configurer la source de données : lier l'Excel exporté comme source de publipostage
4. Activer l'option "Supprimer les paragraphes vides" (via XML directement)

**Instruction affichée à l'opérateur après téléchargement du Word :**
```
Le fichier Word est prêt. Pour finaliser le publipostage :
1. Ouvrir le fichier Word téléchargé
2. Onglet "Publipostage" → "Terminer et fusionner" → "Modifier des documents individuels"
3. Sélectionner "Tous" → OK
4. Word génère les N lettres fusionnées dans un nouveau document
5. Imprimer ou exporter en PDF
```

**Après export :**
- Statut dossier → `exporte` + date enregistrée
- Les deux fichiers (Excel + Word) restent téléchargeables depuis le tableau de bord

---

## Cas spéciaux identifiés dans les fichiers réels

### Fichier SYNERPA (2 617 lignes — pro avec contact)
- 100% professionnel (Raison Sociale toujours remplie)
- CP stocké en flottant Excel (69002.0) → `str(int(float(cp))).zfill(5)`
- Rue 2 et Rue 3 parfois remplies → mapper sur adresse_comp_int et adresse_comp_ext
- Civilités : Monsieur, Madame, Docteur

### Fichier HELIOPARC (141 lignes — multi-contacts sans adresse)
- Mode BAL interne (pas de colonne adresse)
- Jusqu'à 3 contacts par ligne (colonnes Nom-1/2, Prénom-1/2/3, Civilité-1/2/7)
- Colonne `et` : connecteur entre contacts — ignorer dans le mapping
- Colonne `Formule-1` : Cher/Chère/Chers → mapper sur formule_source si disponible
- Colonne `Structure` = Société → mapper sur `societe`
- Pas d'adresse → mode BAL détecté automatiquement

### Fichier VOEUX (155 lignes — contact concaténé)
- Colonne `Contact` = "NOM Prénom" concaténé → mapper sur `identite_1` (pas de découpage)
- Colonne `Structure` = Société (150/155 remplie)
- Adresse 2 remplie sur 59 lignes → mapper sur adresse_comp_int

---

## Déploiement

### Git et GitHub
```bash
git init
git add .
git commit -m "feat: NormAdress v4 initial"
git remote add origin https://github.com/Cmoutier/NormAdress.git
git branch -M main
git push -u origin main
```

### render.yaml
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
      - key: SUPABASE_URL
        fromSecret: SUPABASE_URL
      - key: SUPABASE_KEY
        fromSecret: SUPABASE_KEY
    plan: free
```

### .streamlit/config.toml
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

### Instructions Render (à afficher à l'utilisateur après push)
```
DÉPLOIEMENT RENDER — compte existant STEP :

1. Dashboard Render → "New +" → "Web Service"
2. Sélectionner le repo GitHub "Cmoutier/NormAdress"
3. Render détecte render.yaml automatiquement
4. Dans "Environment" → ajouter les variables secrètes :
   SUPABASE_URL  (depuis dashboard Supabase → Settings → API)
   SUPABASE_KEY  (clé "anon public" depuis Supabase)
5. Cliquer "Create Web Service"
6. Chaque push sur main redéploie automatiquement

Note : sur le plan gratuit, l'app s'endort après 15min (30-50s de réveil).
```

### GitHub Actions CI
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
      - run: pytest tests/ -v --cov=core --cov-fail-under=85
```

---

## requirements.txt
```
streamlit==1.32.0
pandas==2.2.1
openpyxl==3.1.2
supabase==2.3.0
reportlab==4.1.0
python-docx==1.1.2
streamlit-sortables==0.2.0
pytest==8.1.1
pytest-cov==5.0.0
chardet==5.2.0
python-dotenv==1.0.1
```

---

## Configuration MCP (.claude/mcp_config.json)
```json
{
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/chemin/vers/normadress"]
    },
    "github": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-github"],
      "env": { "GITHUB_PERSONAL_ACCESS_TOKEN": "${GITHUB_TOKEN}" }
    }
  }
}
```

---

## État du développement (07/04/2026)

### Terminé ✅

```
✅  core/db.py              Connexion Supabase + CRUD dossiers/adresses/mappings
✅  core/cleaner.py         Nettoyage complet — whitespace, civilités, noms, CP, ville
✅  core/detector.py        Détection pro/part + mode BAL interne
✅  core/composer.py        6 lignes AFNOR + Formule (tous modes + multi-contacts)
✅  core/validator.py       8 codes d'alertes qualité AFNOR
✅  core/mapper.py          Mapping synonymes + auto_map + construire_df_mappe
✅  core/pdf_generator.py   PDF BAT grille 2×2, lignes longues surlignées orange
✅  core/word_injector.py   Injection MERGEFIELD Word (marqueurs {{Ln}} ou fin de doc)
✅  app.py                  Tableau de bord dossiers avec statuts colorés
✅  pages/01_nouveau_dossier.py  Création dossier + upload Excel/Word + paramètres
✅  pages/02_mapping.py     Mapping colonnes + détection mode BAL auto
✅  pages/03_detection.py   Révision pro/part ligne par ligne
✅  pages/04_composition.py Composition AFNOR + édition manuelle + sauvegarde en base
✅  pages/05_bat.py         Génération PDF + workflow validation client
✅  pages/06_export.py      Export Excel coloré + Word avec champs de fusion
✅  tests/test_cleaner.py   18 tests — 100% pass
✅  tests/test_detector.py  8 tests — 100% pass
✅  tests/test_composer.py  12 tests — 100% pass
✅  tests/test_validator.py 6 tests — 100% pass
                            → Total : 58 tests, 0 échec
```

### À faire / Prochaines étapes

```
⏳  Tables Supabase         À créer manuellement via SQL Editor (SQL dans section dédiée)
⏳  Render env vars         SUPABASE_URL + SUPABASE_KEY à configurer dans Render
⏳  cleaner/ (legacy)       Ancien package v3 — toujours présent, peut être supprimé
⏳  tests/fixtures          Fixtures réelles présentes mais non versionnées (.gitignore)
⏳  Drag & drop mapping     streamlit-sortables pas encore intégré dans pages/02
```

### Notes environnement local

**Python 3.14 + Windows** : `supabase>=2.28` tire `storage3` qui tire `pyiceberg`,
lequel nécessite Visual Studio Build Tools. L'app tourne sans problème sur Render
(Python 3.11, Linux). Pour tester localement sans supabase, lancer uniquement :
```bash
pytest tests/test_cleaner.py tests/test_detector.py tests/test_composer.py tests/test_validator.py
```

---

## Ce qu'il ne faut PAS faire
- Ne pas mélanger logique métier et pages Streamlit — tout dans `core/`
- Ne pas découper automatiquement les champs `identite_1` (NOM Prénom concaténé) — laisser tel quel
- Ne pas supprimer automatiquement les doublons ni corriger le type sans validation opérateur
- Ne pas rendre bloquantes les alertes BAL interne — informatif seulement
- Ne pas exporter le CP en nombre dans Excel — toujours en TEXT (format `@`)
- Ne pas hardcoder les credentials Supabase — variables d'environnement uniquement
- Ne pas utiliser xlrd pour .xlsx — openpyxl uniquement
- Ne pas utiliser Flask, FastAPI ou Vercel — Streamlit + Render uniquement
- Ne pas ajouter d'authentification en v1 — hors périmètre
