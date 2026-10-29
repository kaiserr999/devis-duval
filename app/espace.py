"""Espace client : le client connecté consulte ses devis.

Il ne voit que ses propres devis, et jamais les brouillons (pas encore
envoyés). L'accès est réservé aux comptes client (voir app/auth.py).
"""
from flask import Blueprint, abort, render_template, request
from flask_login import current_user

from app.extensions import db
from app.models import Devis
from app.pdf import reponse_pdf, valable_jusqu_au

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


@espace_bp.get("/")
def accueil():
    devis = db.session.scalars(
        devis_visibles().order_by(Devis.id.desc())).all()
    return render_template("espace/accueil.html", client=current_user.client,
                           devis=devis)


@espace_bp.get("/devis/<int:devis_id>")
def detail_devis(devis_id):
    devis = trouver_devis_client(devis_id)
    return render_template("espace/devis.html", devis=devis,
                           valable_jusqu_au=valable_jusqu_au(devis))


@espace_bp.get("/devis/<int:devis_id>/pdf")
def pdf_devis(devis_id):
    """Télécharge le devis en PDF (?apercu=1 : l'ouvre dans le navigateur)."""
    return reponse_pdf(trouver_devis_client(devis_id),
                       apercu=bool(request.args.get("apercu")))
