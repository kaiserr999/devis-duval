"""Vérifie que les migrations Alembic sont à jour avec les modèles."""
from alembic import command
from sqlalchemy import inspect

from app import create_app
from app.config import TestConfig
from app.extensions import db, migrate


def test_migrations_a_jour_avec_les_modeles(tmp_path):
    class ConfigFichier(TestConfig):
        SQLALCHEMY_DATABASE_URI = "sqlite:///" + str(tmp_path / "m.db")

    app = create_app(ConfigFichier)
    with app.app_context():
        config = migrate.get_config()
        command.upgrade(config, "head")

        tables = set(inspect(db.engine).get_table_names())
        assert {"clients", "devis", "lignes_devis"} <= tables

        # Échoue si un modèle a changé sans « flask db migrate »
        command.check(config)
