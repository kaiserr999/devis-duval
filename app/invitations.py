"""Lien de création du compte client, envoyé par email.

Le lien contient un jeton signé avec SECRET_KEY (itsdangerous) : il ne
peut pas être fabriqué sans la clé, expire après
INVITATION_VALIDITE_JOURS et n'est plus valable si l'email du client
change. Aucune table n'est nécessaire.
"""
from flask import current_app
from itsdangerous import BadSignature, SignatureExpired, \
    URLSafeTimedSerializer

from app.extensions import db
from app.models import Client

SEL = "invitation-espace-client"


class LienInvalide(Exception):
    """Lien d'invitation expiré, falsifié ou périmé (message à afficher)."""


def _serialiseur():
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"],
                                  salt=SEL)


def _normaliser(email):
    return (email or "").strip().lower()


def creer_jeton(client):
    """Jeton d'invitation pour ce client (qui doit avoir un email)."""
    return _serialiseur().dumps({"client_id": client.id,
                                 "email": _normaliser(client.email)})


def lire_jeton(jeton):
    """Renvoie le client invité. Lève LienInvalide."""
    jours = current_app.config["INVITATION_VALIDITE_JOURS"]
    try:
        donnees = _serialiseur().loads(jeton, max_age=jours * 24 * 3600)
    except SignatureExpired:
        raise LienInvalide("Ce lien a expiré. Demandez un nouveau lien à "
                           "votre artisan.")
    except BadSignature:
        raise LienInvalide("Ce lien n'est pas valide. Vérifiez qu'il a été "
                           "copié en entier.")

    client_id = donnees.get("client_id") if isinstance(donnees, dict) \
        else None
    client = db.session.get(Client, client_id) \
        if isinstance(client_id, int) else None
    if client is None or not client.email \
            or _normaliser(client.email) != donnees.get("email"):
        raise LienInvalide("Ce lien n'est plus valable. Demandez un nouveau "
                           "lien à votre artisan.")
    return client
