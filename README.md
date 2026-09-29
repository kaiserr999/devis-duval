# Devis Duval

Application web de gestion de devis pour **SARL Peinture Duval** (client
fictif), réalisée dans le cadre du Portfolio Holberton.

Le gérant crée des clients, puis des devis composés de lignes
(description, quantité, prix unitaire). **Le total d'un devis est toujours
calculé côté serveur**, jamais saisi à la main.

## Stack

- Python 3 / Flask (factory `create_app()`)
- SQLAlchemy (Flask-SQLAlchemy), SQLite en développement
- pytest, pycodestyle
- Docker / docker-compose

## Structure

```
app/
  __init__.py        factory create_app()
  config.py          Config (SQLite fichier) / TestConfig (SQLite mémoire)
  extensions.py      instance SQLAlchemy (+ PRAGMA foreign_keys pour SQLite)
  models/            Client, Devis, LigneDevis
  routes/health.py   GET /api/health
tests/               conftest.py, tests des modèles et des routes
run.py
```

## Modèle de données

| Table          | Colonnes                                                                  |
|----------------|---------------------------------------------------------------------------|
| `clients`      | id, nom (obligatoire), email, telephone, adresse, cree_le                 |
| `devis`        | id, client_id → clients, numero (unique), date_creation, statut, total    |
| `lignes_devis` | id, devis_id → devis (ON DELETE CASCADE), description, quantite, prix_unitaire, sous_total |

- Montants en `DECIMAL(10,2)` et `decimal.Decimal` en Python, jamais en float.
- `CHECK (quantite > 0)` et `CHECK (prix_unitaire >= 0)`.
- `statut` ∈ brouillon / envoye / accepte / refuse (défaut : brouillon).
- `LigneDevis.calculer_sous_total()` et `Devis.calculer_total()` arrondissent
  au centime (`ROUND_HALF_UP`).

## Installation locale

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python run.py            # http://localhost:5000/api/health
```

## Docker

```bash
docker compose up --build
```

## Tests et style

```bash
pytest -v
pycodestyle .
```

## Branches

- `main` : version stable
- `develop` : intégration des fonctionnalités
