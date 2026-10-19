"""Route de vérification de santé."""
from flask import Blueprint, jsonify

health_bp = Blueprint("health", __name__, url_prefix="/api")


@health_bp.get("/health")
def health():
    """Indique que l'API répond.
    ---
    tags: [Santé]
    responses:
      200:
        description: L'API est disponible
        schema:
          type: object
          properties:
            statut:
              type: string
              example: ok
    """
    return jsonify({"statut": "ok"}), 200
