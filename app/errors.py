"""Gestionnaires d'erreurs : JSON pour l'API, page HTML sinon."""
from flask import jsonify, render_template, request
from werkzeug.exceptions import HTTPException


def register_error_handlers(app):
    """Erreurs HTTP : {"erreur": "..."} sous /api/, page d'erreur ailleurs."""

    @app.errorhandler(HTTPException)
    def erreur_http(erreur):
        if request.path.startswith("/api/"):
            return jsonify({"erreur": erreur.description}), erreur.code
        return render_template("erreur.html", erreur=erreur), erreur.code
