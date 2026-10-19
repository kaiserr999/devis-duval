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

    # Cookie de session : pas lisible en JavaScript, pas envoyé par les
    # formulaires d'autres sites, HTTPS seulement si SESSION_COOKIE_SECURE=1
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.environ.get("SESSION_COOKIE_SECURE") == "1"

    # En-tête des devis PDF (entreprise fictive du projet Portfolio)
    ENTREPRISE = {
        "nom": "SARL Peinture Duval",
        "adresse": "12 avenue des Artisans, 69007 Lyon",
        "telephone": "04 78 00 00 00",
        "email": "contact@peinture-duval.example.com",
        "siret": "000 000 000 00000",
    }
    # Durée de validité affichée sur le devis
    DEVIS_VALIDITE_JOURS = 30


class TestConfig(Config):
    """Configuration des tests (SQLite en mémoire)."""

    TESTING = True
    SECRET_KEY = "cle-de-test"
    # Formulaires postés sans jeton ; la protection CSRF a son propre test
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
