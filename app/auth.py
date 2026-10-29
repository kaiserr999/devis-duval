"""Connexion (gérant et clients), création du compte client, protection
des routes, commande CLI."""
from urllib.parse import urlsplit

import click
from flask import Blueprint, flash, has_request_context, jsonify, \
    redirect, render_template, request, url_for
from flask_login import current_user, login_user, logout_user
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db, login_manager
from app.invitations import LienInvalide, lire_jeton
from app.models import Utilisateur

auth_bp = Blueprint("auth", __name__)

# Blueprints réservés au gérant connecté, et à un client connecté. Restent
# publics : /api/health (supervision, CI), la connexion, la création du
# compte client (lien reçu par email), les fichiers statiques et la
# documentation Swagger.
BLUEPRINTS_GERANT = {"pages", "clients", "devis"}
BLUEPRINTS_CLIENT = {"espace"}

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
    """before_request : bloque les routes protégées sans session, et
    garde chacun chez soi (le client dans son espace, le gérant dans
    l'application)."""
    blueprint = request.blueprint
    if blueprint not in BLUEPRINTS_GERANT | BLUEPRINTS_CLIENT:
        return None
    if not current_user.is_authenticated:
        return login_manager.unauthorized()
    if blueprint in BLUEPRINTS_GERANT and current_user.est_client:
        if request.path.startswith("/api/"):
            return jsonify({"erreur": "Accès réservé au gérant."}), 403
        return redirect(url_for("espace.accueil"))
    if blueprint in BLUEPRINTS_CLIENT and current_user.est_gerant:
        flash("L'espace client est réservé aux clients.", "info")
        return redirect(url_for("pages.liste_devis"))
    return None


def page_accueil(utilisateur):
    """Première page après connexion : espace client ou liste des devis."""
    if utilisateur.est_client:
        return url_for("espace.accueil")
    return url_for("pages.liste_devis")


@auth_bp.app_context_processor
def url_accueil():
    """Lien du logo et des pages d'erreur, selon la personne connectée."""
    if not has_request_context():
        # Template rendu hors requête (PDF depuis une commande, tests)
        return {}
    if current_user.is_authenticated:
        return {"url_accueil": page_accueil(current_user)}
    return {"url_accueil": url_for("auth.connexion")}


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
        return redirect(suivant or page_accueil(current_user))
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
        return redirect(suivant or page_accueil(utilisateur))

    return render_template("auth/connexion.html", suivant=suivant,
                           email=email,
                           erreur="Email ou mot de passe incorrect."), 401


@auth_bp.route("/activation/<jeton>", methods=["GET", "POST"])
def activation(jeton):
    """Création du compte client depuis le lien reçu par email."""
    try:
        client = lire_jeton(jeton)
    except LienInvalide as erreur:
        return render_template("auth/activation.html", client=None,
                               lien_invalide=str(erreur)), 400
    if client.compte is not None:
        flash("Votre compte existe déjà : connectez-vous.", "info")
        return redirect(url_for("auth.connexion"))

    email = normaliser_email(client.email)
    if request.method == "GET":
        return render_template("auth/activation.html", client=client,
                               email=email)

    mot_de_passe = request.form.get("mot_de_passe", "")
    compte = Utilisateur(email=email)
    erreur = None
    if mot_de_passe != request.form.get("confirmation", ""):
        erreur = "Les deux mots de passe ne sont pas identiques."
    elif db.session.scalars(db.select(Utilisateur)
                            .where(Utilisateur.email == email)).first():
        erreur = ("Cet email est déjà utilisé par un autre compte. "
                  "Contactez votre artisan.")
    else:
        try:
            compte.definir_mot_de_passe(mot_de_passe)
        except ValueError as exc:
            erreur = str(exc)
    if erreur:
        return render_template("auth/activation.html", client=client,
                               email=email, erreur=erreur), 400

    compte.client = client
    db.session.add(compte)
    db.session.commit()
    login_user(compte)
    flash("Votre compte est créé. Bienvenue dans votre espace client !",
          "succes")
    return redirect(url_for("espace.accueil"))


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
    if existe and utilisateur.est_client:
        raise click.ClickException(f"{email} est le compte d'un client, "
                                   "pas celui du gérant.")
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
