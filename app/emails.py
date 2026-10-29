"""Envoi d'emails : SMTP si MAIL_SERVER est défini, sinon affichage dans
le terminal (développement). Dans les tests, les emails sont gardés en
mémoire dans app.extensions["emails_envoyes"]."""
import smtplib
from email.message import EmailMessage
from email.utils import formataddr

from flask import current_app


def construire(destinataire, sujet, texte, html=None, pieces_jointes=()):
    """Prépare un email (texte, version HTML facultative, pièces jointes
    sous la forme (nom, contenu, type MIME))."""
    config = current_app.config
    message = EmailMessage()
    message["Subject"] = sujet
    message["From"] = formataddr((config["ENTREPRISE"]["nom"],
                                  config["MAIL_EXPEDITEUR"]))
    message["To"] = destinataire
    message.set_content(texte)
    if html:
        message.add_alternative(html, subtype="html")
    for nom, contenu, type_mime in pieces_jointes:
        principal, secondaire = type_mime.split("/")
        message.add_attachment(contenu, maintype=principal,
                               subtype=secondaire, filename=nom)
    return message


def envoyer(message):
    """Envoie l'email et renvoie le mode utilisé : "smtp", "console" ou
    "memoire". Lève OSError (dont smtplib.SMTPException) en cas d'échec."""
    config = current_app.config
    if config.get("MAIL_MEMOIRE"):
        current_app.extensions.setdefault("emails_envoyes", []).append(
            message)
        return "memoire"

    if not config.get("MAIL_SERVER"):
        texte = message.get_body(("plain",)).get_content()
        current_app.logger.warning(
            "MAIL_SERVER non défini : email NON envoyé, affiché ici.\n"
            "À : %s\nSujet : %s\n\n%s", message["To"], message["Subject"],
            texte)
        return "console"

    classe = smtplib.SMTP_SSL if config["MAIL_USE_SSL"] else smtplib.SMTP
    with classe(config["MAIL_SERVER"], config["MAIL_PORT"],
                timeout=15) as serveur:
        if config["MAIL_USE_TLS"] and not config["MAIL_USE_SSL"]:
            serveur.starttls()
        if config.get("MAIL_USERNAME"):
            serveur.login(config["MAIL_USERNAME"], config["MAIL_PASSWORD"])
        serveur.send_message(message)
    return "smtp"
