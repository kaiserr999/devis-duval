"""Espace client : le client connecté consulte ses devis, et accepte ou
refuse en ligne ceux qui attendent sa réponse.

Il ne voit que ses propres devis, et jamais les brouillons (pas encore
envoyés). L'accès est réservé aux comptes client (voir app/auth.py).
"""
from datetime import datetime, timezone

from flask import Blueprint, abort, flash, redirect, render_template, \
    request, url_for
from flask_login import current_user

from app.extensions import db
from app.models import Devis
from app.models.client import maintenant
from app.notifications import notifier_reponse_client
from app.pages import essayer
from app.pdf import reponse_pdf, valable_jusqu_au
from app.routes.devis import appliquer_statut

espace_bp = Blueprint("espace", __name__, url_prefix="/espace")


def devis_visibles():
    """Requête des devis du client connecté, sans les brouillons."""
    return db.select(Devis).where(Devis.client_id == current_user.client_id,
                                  Devis.statut != "brouillon")


def trouver_devis_client(devis_id):
    """Devis du client connecté, ou 404 (même s'il appartient à un autre
    client : on ne révèle pas son existence)."""
    devis = db.session.scalars(
        devis_visibles().where(Devis.id == devis_id)).first()
    if devis is None:
        abort(404, description="Devis introuvable.")
    return devis


def est_expire(devis):
    """Vrai si la date de validité du devis est dépassée (fin de journée)."""
    return valable_jusqu_au(devis).date() < datetime.now(timezone.utc).date()


@espace_bp.get("/")
def accueil():
    devis = db.session.scalars(
        devis_visibles().order_by(Devis.id.desc())).all()
    en_attente = sum(1 for d in devis
                     if d.statut == "envoye" and not est_expire(d))
    return render_template("espace/accueil.html", client=current_user.client,
                           devis=devis, en_attente=en_attente)


@espace_bp.get("/devis/<int:devis_id>")
def detail_devis(devis_id):
    devis = trouver_devis_client(devis_id)
    return render_template("espace/devis.html", devis=devis,
                           valable_jusqu_au=valable_jusqu_au(devis),
                           expire=est_expire(devis))


# Réponses possibles du client et message affiché après coup
REPONSES = {
    "accepte": "Merci ! Votre accord pour le devis {numero} est enregistré. "
               "Nous vous recontactons pour planifier les travaux.",
    "refuse": "Votre refus du devis {numero} est enregistré. N'hésitez pas "
              "à nous contacter si vous souhaitez un autre devis.",
}


@espace_bp.post("/devis/<int:devis_id>/reponse")
def repondre(devis_id):
    """Le client accepte (case « Bon pour accord » cochée) ou refuse un
    devis envoyé et encore valable. Le gérant est prévenu par email."""
    devis = trouver_devis_client(devis_id)
    retour = redirect(url_for("espace.detail_devis", devis_id=devis.id))
    decision = request.form.get("decision")
    if decision not in REPONSES:
        abort(400, description="Réponse inconnue.")
    if devis.statut != "envoye":
        flash("Ce devis a déjà reçu une réponse.", "info")
        return retour
    if est_expire(devis):
        flash("Ce devis a expiré : contactez-nous pour en obtenir un "
              "nouveau.", "erreur")
        return retour
    if decision == "accepte" and not request.form.get("accord"):
        flash("Cochez la case « Bon pour accord » pour accepter le devis.",
              "erreur")
        return retour

    devis.reponse_en_ligne_le = maintenant()
    _, erreur = essayer(appliquer_statut, devis, decision)
    if erreur:
        flash(erreur, "erreur")
        return retour
    notifier_reponse_client(devis)
    flash(REPONSES[decision].format(numero=devis.numero), "succes")
    return retour


@espace_bp.get("/devis/<int:devis_id>/pdf")
def pdf_devis(devis_id):
    """Télécharge le devis en PDF (?apercu=1 : l'ouvre dans le navigateur)."""
    return reponse_pdf(trouver_devis_client(devis_id),
                       apercu=bool(request.args.get("apercu")))
