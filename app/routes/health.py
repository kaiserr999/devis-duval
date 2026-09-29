"""Route de vérification de santé."""
from flask import Blueprint, jsonify

health_bp = Blueprint("health", __name__, url_prefix="/api")


@health_bp.get("/health")
def health():
    """Indique que l'API répond."""
    return jsonify({"statut": "ok"}), 200
