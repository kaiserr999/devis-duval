"""Emails aux clients : devis envoyé (PDF joint) et invitation à créer
son espace client."""
from flask import current_app, render_template, url_for

from app.emails import construire, envoyer
from app.invitations import creer_jeton
from app.pdf import generer_pdf, nom_fichier, valable_jusqu_au


class Notification:
    """Résultat d'un email au client, pour informer le gérant."""

    def __init__(self, client, mode=None, lien=None, echec=False):
        self.client = client
        self.mode = mode      # "smtp", "console", "memoire" ou None
        self.lien = lien      # lien de l'email vers l'espace client
        self.echec = echec    # True si le serveur d'email a refusé

    @property
    def envoyee(self):
        return self.mode is not None

    def message(self):
        """(texte, catégorie) du message affiché au gérant."""
        client = self.client
        if not client.email:
            return (f"{client.nom} n'a pas d'email : prévenez ce client par "
                    f"téléphone ({client.telephone}).", "info")
        if self.echec:
            return (f"L'email à {client.email} n'a pas pu être envoyé. "
                    "Vérifiez la configuration MAIL_... du fichier .env.",
                    "erreur")
        if self.mode == "console":
            return ("Aucun serveur d'email configuré (MAIL_SERVER) : "
                    f"l'email pour {client.email} est affiché dans le "
                    f"terminal. Lien du client : {self.lien}", "info")
        return f"Email envoyé à {client.email}.", "succes"


def lien_espace(client):
    """Lien de l'email : création du compte, ou connexion s'il existe."""
    if client.compte is None:
        return url_for("auth.activation", jeton=creer_jeton(client),
                       _external=True)
    return url_for("auth.connexion", _external=True)


def _envoyer(client, sujet, gabarit, pieces_jointes=(), **contexte):
    """Envoie emails/<gabarit>.txt (+ .html) au client, s'il a un email."""
    if not client.email:
        return Notification(client)
    config = current_app.config
    lien = lien_espace(client)
    contexte.update(client=client, lien=lien,
                    compte_existe=client.compte is not None,
                    entreprise=config["ENTREPRISE"],
                    jours=config["INVITATION_VALIDITE_JOURS"])
    message = construire(
        client.email, sujet,
        render_template(f"emails/{gabarit}.txt", **contexte),
        render_template(f"emails/{gabarit}.html", **contexte),
        pieces_jointes)
    try:
        mode = envoyer(message)
    except OSError:
        current_app.logger.exception("Échec de l'envoi de l'email à %s",
                                     client.email)
        return Notification(client, lien=lien, echec=True)
    return Notification(client, mode=mode, lien=lien)


def notifier_devis_envoye(devis):
    """Envoie le devis (PDF joint) au client, avec le lien de son espace."""
    entreprise = current_app.config["ENTREPRISE"]["nom"]
    pdf = (nom_fichier(devis), generer_pdf(devis), "application/pdf") \
        if devis.client.email else None
    return _envoyer(devis.client, f"Votre devis {devis.numero} - {entreprise}",
                    "devis_envoye", pieces_jointes=[pdf] if pdf else [],
                    devis=devis, valable_jusqu_au=valable_jusqu_au(devis))


def inviter_client(client):
    """Envoie au client le lien de création de son espace."""
    entreprise = current_app.config["ENTREPRISE"]["nom"]
    return _envoyer(client, f"Votre espace client {entreprise}",
                    "invitation")
