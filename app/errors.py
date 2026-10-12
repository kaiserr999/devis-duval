"""Gestionnaires d'erreurs : toutes les erreurs de l'API en JSON."""
from flask import jsonify
from werkzeug.exceptions import HTTPException


def register_error_handlers(app):
    """Renvoie les erreurs HTTP sous la forme {"erreur": "..."}."""

    @app.errorhandler(HTTPException)
    def erreur_http(erreur):
        return jsonify({"erreur": erreur.description}), erreur.code
