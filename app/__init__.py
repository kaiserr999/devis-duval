"""Factory de l'application Flask."""
import os

from flask import Flask

from app.config import Config
from app.extensions import db, migrate


def create_app(config_class=Config):
    """Crée et configure une instance de l'application."""
    app = Flask(__name__)
    app.config.from_object(config_class)

    os.makedirs(os.path.join(os.path.dirname(app.root_path), "instance"),
                exist_ok=True)

    db.init_app(app)
    # render_as_batch : SQLite ne sait pas modifier une table (ALTER)
    migrate.init_app(app, db, render_as_batch=True)

    from app import models  # noqa: F401  (enregistre les modèles)
    from app.routes.health import health_bp
    app.register_blueprint(health_bp)

    from app.seed import seed_command
    app.cli.add_command(seed_command)

    return app
