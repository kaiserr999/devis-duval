"""Connexion du gérant : pages, protection des routes, commande CLI."""
from urllib.parse import urlsplit

import click
from flask import Blueprint, flash, jsonify, redirect, render_template, \
    request, url_for
from flask_login import current_user, login_user, logout_user
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db, login_manager
from app.models import Utilisateur

auth_bp = Blueprint("auth", __name__)

# Blueprints réservés au gérant connecté. Restent publics : /api/health
# (supervision, CI), la page de connexion, les fichiers statiques et la
# documentation Swagger.
BLUEPRINTS_PROTEGES = {"pages", "clients", "devis"}

# Comparé quand l'email est inconnu, pour que la réponse prenne le même
# temps qu'avec un vrai compte (on ne devine pas les emails existants)
HASH_FACTICE = generate_password_hash("mot-de-passe-factice")


def normaliser_email(email):
    return (email or "").strip().lower()


@login_manager.user_loader
def charger_utilisateur(utilisateur_id):
    return db.session.get(Utilisateur, int(utilisateur_id))


@login_manager.unauthorized_handler
def non_connecte():
    """401 JSON pour l'API, redirection vers la connexion pour les pages."""
    if request.path.startswith("/api/"):
        return jsonify({"erreur": "Authentification requise."}), 401
    flash("Connectez-vous pour accéder à l'application.", "info")
    return redirect(url_for("auth.connexion", suivant=request.full_path
                            if request.query_string else request.path))


def exiger_connexion():
    """before_request : bloque les routes protégées sans session."""
    if request.blueprint in BLUEPRINTS_PROTEGES \
            and not current_user.is_authenticated:
        return login_manager.unauthorized()
    return None


def adresse_sure(cible):
    """N'accepte qu'un chemin local (/devis/3), jamais un autre site."""
    if not cible:
        return None
    morceaux = urlsplit(cible)
    if morceaux.scheme or morceaux.netloc or not cible.startswith("/") \
            or cible.startswith("//") or "\\" in cible:
        return None
    return cible


@auth_bp.route("/connexion", methods=["GET", "POST"])
def connexion():
    suivant = adresse_sure(request.values.get("suivant"))
    if current_user.is_authenticated:
        return redirect(suivant or url_for("pages.liste_devis"))
    if request.method == "GET":
        return render_template("auth/connexion.html", suivant=suivant)

    email = normaliser_email(request.form.get("email"))
    mot_de_passe = request.form.get("mot_de_passe", "")
    utilisateur = db.session.scalars(
        db.select(Utilisateur).where(Utilisateur.email == email)).first()
    if utilisateur is None:
        check_password_hash(HASH_FACTICE, mot_de_passe)
    elif utilisateur.verifier_mot_de_passe(mot_de_passe):
        login_user(utilisateur)
        return redirect(suivant or url_for("pages.liste_devis"))

    return render_template("auth/connexion.html", suivant=suivant,
                           email=email,
                           erreur="Email ou mot de passe incorrect."), 401


@auth_bp.post("/deconnexion")
def deconnexion():
    logout_user()
    flash("Vous êtes déconnecté.", "succes")
    return redirect(url_for("auth.connexion"))


@click.command("creer-gerant")
@click.argument("email")
@click.password_option("--mot-de-passe", prompt="Mot de passe",
                       confirmation_prompt="Confirmer le mot de passe")
def creer_gerant_command(email, mot_de_passe):
    """Crée le compte EMAIL, ou change son mot de passe s'il existe."""
    email = normaliser_email(email)
    if "@" not in email or len(email) > 120:
        raise click.BadParameter("email invalide.", param_hint="EMAIL")

    utilisateur = db.session.scalars(
        db.select(Utilisateur).where(Utilisateur.email == email)).first()
    existe = utilisateur is not None
    if not existe:
        utilisateur = Utilisateur(email=email)
    try:
        utilisateur.definir_mot_de_passe(mot_de_passe)
    except ValueError as erreur:
        raise click.ClickException(str(erreur))
    db.session.add(utilisateur)
    db.session.commit()
    click.echo(f"Mot de passe de {email} modifié." if existe
               else f"Compte {email} créé.")
