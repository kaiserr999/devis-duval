"""Documentation Swagger (OpenAPI 2) servie par Flasgger sur /apidocs/."""
from app.models.devis import STATUTS

# Décimal envoyé en chaîne ou en nombre, 2 décimales max
MONTANT = {"type": "string", "example": "12.50"}

TEMPLATE = {
    "swagger": "2.0",
    "info": {
        "title": "API Devis Duval",
        "description": "Gestion des clients et des devis. Les montants "
                       "sont renvoyés en chaîne (ex. \"12.50\") et "
                       "calculés par le serveur.",
        "version": "1.0.0",
    },
    "consumes": ["application/json"],
    "produces": ["application/json"],
    "tags": [
        {"name": "Santé", "description": "Disponibilité de l'API"},
        {"name": "Clients", "description": "CRUD des clients"},
        {"name": "Devis", "description": "Devis, lignes et statuts"},
    ],
    "definitions": {
        "Erreur": {
            "type": "object",
            "properties": {
                "erreur": {"type": "string",
                           "example": "Client introuvable."},
            },
        },
        "ClientEntree": {
            "type": "object",
            "required": ["nom"],
            "properties": {
                "nom": {"type": "string", "maxLength": 120,
                        "example": "Boulangerie Au Bon Pain"},
                "email": {"type": "string", "maxLength": 120,
                          "example": "contact@aubonpain.example.com"},
                "telephone": {"type": "string", "maxLength": 30,
                              "example": "04 72 33 44 55"},
                "adresse": {"type": "string", "maxLength": 255,
                            "example": "8 place de la Mairie, 69500 Bron"},
            },
        },
        "Client": {
            "allOf": [
                {"$ref": "#/definitions/ClientEntree"},
                {
                    "type": "object",
                    "properties": {
                        "id": {"type": "integer", "example": 1},
                        "cree_le": {"type": "string", "format": "date-time"},
                    },
                },
            ],
        },
        "LigneEntree": {
            "type": "object",
            "required": ["description", "quantite", "prix_unitaire"],
            "properties": {
                "description": {"type": "string", "maxLength": 255,
                                "example": "Pose de carrelage (m²)"},
                "quantite": dict(MONTANT, example="2"),
                "prix_unitaire": MONTANT,
            },
        },
        "Ligne": {
            "type": "object",
            "properties": {
                "id": {"type": "integer"},
                "devis_id": {"type": "integer"},
                "description": {"type": "string"},
                "quantite": MONTANT,
                "prix_unitaire": MONTANT,
                "sous_total": dict(MONTANT, example="25.00"),
            },
        },
        "Devis": {
            "type": "object",
            "properties": {
                "id": {"type": "integer", "example": 1},
                "client_id": {"type": "integer", "example": 1},
                "numero": {"type": "string", "example": "D-2026-0001"},
                "date_creation": {"type": "string", "format": "date-time"},
                "statut": {"type": "string", "enum": list(STATUTS)},
                "total": dict(MONTANT, example="25.00"),
                "lignes": {"type": "array",
                           "items": {"$ref": "#/definitions/Ligne"}},
            },
        },
    },
}

CONFIG = {
    "headers": [],
    "specs": [{
        "endpoint": "apispec",
        "route": "/apispec.json",
        "rule_filter": lambda rule: rule.rule.startswith("/api/"),
        "model_filter": lambda tag: True,
    }],
    "static_url_path": "/flasgger_static",
    "swagger_ui": True,
    "specs_route": "/apidocs/",
}
