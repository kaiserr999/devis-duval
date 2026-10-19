"""Configuration de l'application."""
import os

from dotenv import load_dotenv

BASE_DIR = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))

# Charge le fichier .env (non versionné) s'il existe. Les variables déjà
# définies dans l'environnement (Docker, CI) restent prioritaires.
load_dotenv(os.path.join(BASE_DIR, ".env"))

# Clé utilisée seulement en mode debug, si SECRET_KEY n'est pas définie
CLE_DEV = "dev-secret-a-changer"


class Config:
    """Configuration par défaut (développement, SQLite fichier)."""

    # Pas de valeur par défaut : create_app() refuse de démarrer sans clé
    # hors mode debug
    SECRET_KEY = os.environ.get("SECRET_KEY")
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        "sqlite:///" + os.path.join(BASE_DIR, "instance", "devis.db"),
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JSON_SORT_KEYS = False


class TestConfig(Config):
    """Configuration des tests (SQLite en mémoire)."""

    TESTING = True
    SECRET_KEY = "cle-de-test"
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
