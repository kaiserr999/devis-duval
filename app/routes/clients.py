"""Routes CRUD des clients."""
from flask import Blueprint, abort, jsonify, request

from app.extensions import db
from app.models import Client

clients_bp = Blueprint("clients", __name__, url_prefix="/api/clients")

# Champs modifiables et longueur maximale (identique aux colonnes)
CHAMPS = {"nom": 120, "email": 120, "telephone": 30, "adresse": 255}


def lire_json():
    """Renvoie le corps JSON de la requête, ou 400 s'il est invalide."""
    donnees = request.get_json(silent=True)
    if not isinstance(donnees, dict):
        abort(400, description="Le corps de la requête doit être un "
                               "objet JSON.")
    return donnees


def valider_client(donnees):
    """Vérifie et nettoie les champs d'un client. Lève 400 si invalide."""
    propres = {}
    for champ, longueur_max in CHAMPS.items():
        valeur = donnees.get(champ)
        if valeur is not None:
            if not isinstance(valeur, str):
                abort(400, description=f"Le champ '{champ}' doit être "
                                       "une chaîne de caractères.")
            valeur = valeur.strip() or None
        if valeur is not None and len(valeur) > longueur_max:
            abort(400, description=f"Le champ '{champ}' dépasse "
                                   f"{longueur_max} caractères.")
        propres[champ] = valeur

    if propres["nom"] is None:
        abort(400, description="Le champ 'nom' est obligatoire.")
    if propres["email"] is not None and "@" not in propres["email"]:
        abort(400, description="Le champ 'email' est invalide.")
    return propres


def trouver_client(client_id):
    """Renvoie le client demandé, ou 404."""
    return db.get_or_404(Client, client_id,
                         description="Client introuvable.")


@clients_bp.get("")
def lister_clients():
    """Liste tous les clients, par ordre alphabétique."""
    clients = db.session.scalars(
        db.select(Client).order_by(Client.nom, Client.id)).all()
    return jsonify([client.to_dict() for client in clients]), 200


@clients_bp.post("")
def creer_client():
    """Crée un client."""
    client = Client(**valider_client(lire_json()))
    db.session.add(client)
    db.session.commit()
    return jsonify(client.to_dict()), 201


@clients_bp.get("/<int:client_id>")
def voir_client(client_id):
    """Renvoie un client."""
    return jsonify(trouver_client(client_id).to_dict()), 200


@clients_bp.put("/<int:client_id>")
def modifier_client(client_id):
    """Remplace les informations d'un client (champ absent = vidé)."""
    client = trouver_client(client_id)
    for champ, valeur in valider_client(lire_json()).items():
        setattr(client, champ, valeur)
    db.session.commit()
    return jsonify(client.to_dict()), 200


@clients_bp.delete("/<int:client_id>")
def supprimer_client(client_id):
    """Supprime un client, sauf s'il a des devis (409)."""
    client = trouver_client(client_id)
    if client.devis:
        abort(409, description="Ce client a des devis : il ne peut pas "
                               "être supprimé.")
    db.session.delete(client)
    db.session.commit()
    return "", 204
