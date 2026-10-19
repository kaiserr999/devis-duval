"""Interface web (templates Jinja) pour le gérant."""
from decimal import Decimal

from flask import Blueprint, redirect, url_for
from werkzeug.exceptions import HTTPException

from app.extensions import db

pages_bp = Blueprint("pages", __name__)

LIBELLES_STATUT = {
    "brouillon": "Brouillon",
    "envoye": "Envoyé",
    "accepte": "Accepté",
    "refuse": "Refusé",
}


def essayer(action, *args):
    """Exécute une règle métier de l'API et renvoie (résultat, erreur).

    Une erreur 400/409 devient un message à afficher dans la page au lieu
    d'une réponse JSON ; les changements en cours sont annulés.
    """
    try:
        return action(*args), None
    except HTTPException as erreur:
        db.session.rollback()
        return None, erreur.description


@pages_bp.app_template_filter("euro")
def euro(montant):
    """1387.5 -> '1 387,50 €' (espace insécable, virgule décimale).

    Espace insécable classique (U+00A0) : les polices de base du PDF
    n'ont pas l'espace fine (U+202F).
    """
    texte = f"{Decimal(str(montant or 0)):,.2f}"
    return (texte.replace(",", " ").replace(".", ",")
            + " €")


@pages_bp.app_template_filter("nombre")
def nombre(valeur):
    """2.50 -> '2,5' ; 3.00 -> '3'."""
    texte = f"{Decimal(str(valeur)).normalize():f}"
    return texte.replace(".", ",")


@pages_bp.app_template_filter("date_fr")
def date_fr(moment):
    return moment.strftime("%d/%m/%Y") if moment else ""


@pages_bp.app_context_processor
def variables_communes():
    return {"LIBELLES_STATUT": LIBELLES_STATUT}


@pages_bp.get("/")
def accueil():
    return redirect(url_for("pages.liste_devis"))


from app.pages import clients, devis  # noqa: E402,F401  (enregistre les routes)
