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
  config.py          Config (lit .env) / TestConfig (SQLite mémoire)
  extensions.py      SQLAlchemy (+ PRAGMA foreign_keys), Migrate, CSRFProtect
  models/            Client, Devis, LigneDevis
  errors.py          erreurs HTTP : JSON sous /api/, page HTML ailleurs
  routes/health.py   GET /api/health
  routes/clients.py  CRUD /api/clients
  routes/devis.py    /api/devis : lignes, totaux, statuts
  pages/             interface web (clients, devis) qui réutilise les règles de routes/
  pdf.py             génération du devis en PDF (xhtml2pdf)
  templates/         templates Jinja (base, clients/, devis/, erreur)
  static/style.css   styles de l'interface
  seed.py            commande flask seed (données de démo)
  swagger.py         config Flasgger + schémas OpenAPI partagés
tests/               modèles, API, pages, config, Swagger
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
cp .env.example .env       # puis remplir SECRET_KEY
export FLASK_APP=run.py
flask db upgrade         # crée / met à jour la base SQLite
flask seed               # insère des données de démo (clients, devis)
python run.py            # http://localhost:5000/api/health
```

Sous **Windows (PowerShell)**, pas besoin d'activer le venv (`Activate.ps1`
est souvent bloqué par la politique d'exécution) : on appelle directement
le Python du venv.

```powershell
py -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env   # puis remplir SECRET_KEY
$env:FLASK_APP = "run.py"
.\venv\Scripts\flask.exe db upgrade
.\venv\Scripts\flask.exe seed
.\venv\Scripts\python.exe run.py   # http://localhost:5000/apidocs/
```

`ModuleNotFoundError: No module named 'flask'` : le serveur a été lancé avec
le Python global au lieu de celui du venv. Port 5000 déjà utilisé : un autre
serveur tourne déjà (le fermer, ou lancer avec `$env:PORT = "5001"`).

## Interface web

Une fois le serveur lancé, ouvrir http://localhost:5000/ :

| Page | URL |
|---|---|
| Liste des devis, filtrable par statut | `/devis` |
| Nouveau devis (client + lignes, total estimé en direct) | `/devis/nouveau` |
| Détail d'un devis, changement de statut | `/devis/<id>` |
| Devis en PDF (téléchargement, ou aperçu avec `?apercu=1`) | `/devis/<id>/pdf` |
| Modifier / supprimer un devis (brouillon seulement) | `/devis/<id>/modifier` |
| Liste des clients | `/clients` |
| Fiche client (coordonnées + ses devis) | `/clients/<id>` |
| Nouveau / modifier un client | `/clients/nouveau`, `/clients/<id>/modifier` |

Les pages appliquent **les mêmes règles que l'API** (validation, total calculé
par le serveur, cycle des statuts) : elles appellent les fonctions de
`app/routes/`. Les montants se saisissent avec une virgule (`1 200,50`).
Les formulaires sont protégés contre le CSRF (Flask-WTF). L'API n'en a pas
besoin : elle n'accepte que du JSON, qu'un site tiers ne peut pas envoyer
sans autorisation CORS.

### Export PDF

Le PDF est généré par [xhtml2pdf](https://github.com/xhtml2pdf/xhtml2pdf) (pur Python,
rien à installer en plus sous Windows) à partir du template
`app/templates/devis/pdf.html` : en-tête de l'entreprise, client, lignes, total,
durée de validité et cadre « Bon pour accord ». Un devis en brouillon porte la
mention BROUILLON. Les coordonnées de l'entreprise et la durée de validité sont
dans `Config.ENTREPRISE` et `Config.DEVIS_VALIDITE_JOURS` (`app/config.py`).

## Documentation de l'API (Swagger)

Une fois le serveur lancé :

- **Swagger UI** : http://localhost:5000/apidocs/ (tester les routes depuis le navigateur)
- **Spec OpenAPI brute** : http://localhost:5000/apispec.json

La doc est générée par [Flasgger](https://github.com/flasgger/flasgger) à partir
du bloc YAML (après `---`) dans la docstring de chaque route. Les schémas
partagés (`Client`, `Devis`, `Ligne`, `Erreur`...) sont dans `app/swagger.py`.
`tests/test_swagger.py` échoue si une route `/api/...` n'est pas documentée.

## Données de démonstration

`flask seed` insère 4 clients et 5 devis (12 lignes) dans la base, avec des
totaux calculés par `calculer_total()`. La commande ne fait rien si la base
contient déjà des clients ; `flask seed --reset` vide les tables puis
réinsère les données.

Avec Docker : `docker compose exec web flask seed`.

## Migrations (Flask-Migrate / Alembic)

Après toute modification d'un modèle :

```bash
flask db migrate -m "description du changement"
# relire le fichier généré dans migrations/versions/
flask db upgrade
```

Le test `tests/test_migrations.py` échoue si un modèle a été modifié sans
migration correspondante.

## Configuration (.env)

Les secrets sont lus dans un fichier `.env` à la racine, jamais versionné.
Modèle : [.env.example](.env.example).

| Variable | Rôle |
|---|---|
| `SECRET_KEY` | Clé secrète Flask. **Obligatoire hors mode debug** : sans elle, ou avec la clé de dev, l'application refuse de démarrer. |
| `FLASK_DEBUG` | `1` en développement (rechargement auto, clé de dev tolérée), `0` en production. |
| `DATABASE_URL` | Optionnel, SQLite `instance/devis.db` par défaut. |

Générer une clé : `python -c "import secrets; print(secrets.token_hex(32))"`

## Docker

```bash
docker compose up --build   # lit SECRET_KEY dans .env
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
