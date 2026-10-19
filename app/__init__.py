"""Factory de l'application Flask."""
import os

from flasgger import Swagger
from flask import Flask

from app.config import CLE_DEV, Config
from app.extensions import csrf, db, login_manager, migrate
from app.swagger import CONFIG, TEMPLATE


def verifier_secret_key(app):
    """Exige SECRET_KEY hors debug ; clé de dev seulement en debug."""
    cle = app.config.get("SECRET_KEY")
    if cle and cle != CLE_DEV:
        return
    if app.debug:
        app.config["SECRET_KEY"] = CLE_DEV
        return
    raise RuntimeError(
        "SECRET_KEY manquante ou égale à la clé de développement. "
        "Copier .env.example en .env et y mettre une clé secrète "
        "(python -c \"import secrets; print(secrets.token_hex(32))\"), "
        "ou lancer en debug avec FLASK_DEBUG=1.")


def create_app(config_class=Config):
    """Crée et configure une instance de l'application."""
    app = Flask(__name__)
    app.config.from_object(config_class)
    verifier_secret_key(app)

    os.makedirs(os.path.join(os.path.dirname(app.root_path), "instance"),
                exist_ok=True)

    db.init_app(app)
    # render_as_batch : SQLite ne sait pas modifier une table (ALTER)
    migrate.init_app(app, db, render_as_batch=True)

    from app import models  # noqa: F401  (enregistre les modèles)
    from app.routes.health import health_bp
    from app.routes.clients import clients_bp
    from app.routes.devis import devis_bp
    app.register_blueprint(health_bp)
    app.register_blueprint(clients_bp)
    app.register_blueprint(devis_bp)
    for blueprint in (health_bp, clients_bp, devis_bp):
        csrf.exempt(blueprint)
    csrf.init_app(app)

    from app.pages import pages_bp
    app.register_blueprint(pages_bp)

    # Connexion du gérant : pages et API réservées (voir app/auth.py)
    from app.auth import auth_bp, creer_gerant_command, exiger_connexion
    login_manager.init_app(app)
    app.register_blueprint(auth_bp)
    app.before_request(exiger_connexion)
    app.cli.add_command(creer_gerant_command)

    # Documentation interactive : /apidocs/ (spec brute : /apispec.json)
    Swagger(app, config=CONFIG, template=TEMPLATE)

    from app.errors import register_error_handlers
    register_error_handlers(app)

    from app.seed import seed_command
    app.cli.add_command(seed_command)

    return app
