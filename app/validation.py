"""Outils de validation partagés par les routes."""
from flask import abort, request


def lire_json():
    """Renvoie le corps JSON de la requête, ou 400 s'il est invalide."""
    donnees = request.get_json(silent=True)
    if not isinstance(donnees, dict):
        abort(400, description="Le corps de la requête doit être un "
                               "objet JSON.")
    return donnees
