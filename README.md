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
  errors.py          erreurs HTTP renvoyées en JSON {"erreur": "..."}
  routes/health.py   GET /api/health
  routes/clients.py  CRUD /api/clients
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

## API

Toutes les réponses sont en JSON. En cas d'erreur, le corps est
`{"erreur": "message"}`.

### Clients

| Méthode  | Route               | Effet                                   | Succès |
|----------|---------------------|-----------------------------------------|--------|
| `GET`    | `/api/clients`      | Liste les clients (ordre alphabétique)  | 200    |
| `POST`   | `/api/clients`      | Crée un client                          | 201    |
| `GET`    | `/api/clients/<id>` | Affiche un client                       | 200    |
| `PUT`    | `/api/clients/<id>` | Remplace un client (champ absent = vidé)| 200    |
| `DELETE` | `/api/clients/<id>` | Supprime un client                      | 204    |

Corps attendu pour `POST` et `PUT` :

```json
{
  "nom": "Mme Martin",
  "email": "martin@example.com",
  "telephone": "06 12 34 56 78",
  "adresse": "12 rue des Lilas, 69003 Lyon"
}
```

- `nom` est obligatoire (120 caractères max) ; `email` (120), `telephone`
  (30) et `adresse` (255) sont facultatifs. Les espaces autour sont retirés.
- `id`, `cree_le` et les champs inconnus sont ignorés.
- Erreurs : **400** (JSON absent ou champ invalide), **404** (client
  introuvable), **409** (suppression d'un client qui a des devis).

Exemple :

```bash
curl -X POST http://localhost:5000/api/clients \
     -H "Content-Type: application/json" \
     -d '{"nom": "Mme Martin", "email": "martin@example.com"}'
```

### Devis

| Méthode  | Route                    | Effet                                     | Succès |
|----------|--------------------------|-------------------------------------------|--------|
| `GET`    | `/api/devis`             | Liste les devis (`?client_id=`, `?statut=`) | 200  |
| `POST`   | `/api/devis`             | Crée un devis en brouillon                | 201    |
| `GET`    | `/api/devis/<id>`        | Affiche un devis et ses lignes            | 200    |
| `PUT`    | `/api/devis/<id>`        | Remplace les lignes (brouillon seulement) | 200    |
| `PATCH`  | `/api/devis/<id>/statut` | Fait avancer le statut                    | 200    |
| `DELETE` | `/api/devis/<id>`        | Supprime le devis (brouillon seulement)   | 204    |

Corps attendu pour `POST` (pour `PUT`, seulement `lignes`) :

```json
{
  "client_id": 1,
  "lignes": [
    {"description": "Peinture salon (m²)", "quantite": "32.5", "prix_unitaire": "24.90"},
    {"description": "Sous-couche", "quantite": 3, "prix_unitaire": "45.33"}
  ]
}
```

Règles :

- **Le serveur calcule** `sous_total` et `total`. Le numéro est **généré
  automatiquement** (`D-2026-0001`, `D-2026-0002`… par année) et le statut
  de départ est `brouillon`. Les valeurs `total`, `sous_total`, `numero` et
  `statut` envoyées par le client sont ignorées.
- Montants : nombre ou chaîne (`"24.90"` recommandé), 2 décimales au
  maximum. Quantité > 0, prix unitaire >= 0.
- Statut, sans retour en arrière (corps : `{"statut": "envoye"}`) :

  ```
  brouillon ──> envoye ──> accepte
                     └───> refuse
  ```

- Un devis sans ligne ne peut pas être envoyé.
- Un devis qui n'est plus en brouillon ne peut plus être modifié ni
  supprimé.
- Erreurs : **400** (données invalides, client inexistant), **404** (devis
  introuvable), **409** (action interdite pour ce statut).

## Installation locale

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
export FLASK_APP=run.py
flask db upgrade         # crée / met à jour la base SQLite
python run.py            # http://localhost:5000/api/health
```

## Migrations (Flask-Migrate / Alembic)

Après toute modification d'un modèle :

```bash
flask db migrate -m "description du changement"
# relire le fichier généré dans migrations/versions/
flask db upgrade
```

Le test `tests/test_migrations.py` échoue si un modèle a été modifié sans
migration correspondante.

## Docker

```bash
docker compose up --build
```

Le conteneur applique les migrations (`flask db upgrade`) au démarrage.

## Intégration continue

GitHub Actions ([.github/workflows/ci.yml](.github/workflows/ci.yml)) lance
`pycodestyle` et `pytest`, puis construit l'image Docker et vérifie
`/api/health`, à chaque push sur `main`, `develop`, `feature/**` et à chaque
pull request.

## Tests et style

```bash
pytest -v
pycodestyle .
```

## Branches

- `main` : version stable
- `develop` : intégration des fonctionnalités
