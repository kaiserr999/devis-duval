"""Fixtures pytest."""
import pytest
from werkzeug.security import generate_password_hash

from app import create_app
from app.config import TestConfig
from app.extensions import db
from app.models import Utilisateur

GERANT_EMAIL = "gerant@duval.example.com"
GERANT_MOT_DE_PASSE = "mot-de-passe-de-test"


@pytest.fixture
def app():
    """Application configurée pour les tests, base en mémoire."""
    app = create_app(TestConfig)
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def gerant(app):
    """Compte du gérant (hash rapide : seul le test du modèle vérifie
    l'algorithme par défaut)."""
    utilisateur = Utilisateur(
        email=GERANT_EMAIL,
        mot_de_passe_hash=generate_password_hash(
            GERANT_MOT_DE_PASSE, method="pbkdf2:sha256:1000"))
    db.session.add(utilisateur)
    db.session.commit()
    return utilisateur


@pytest.fixture
def anonyme(app):
    """Client HTTP de test, non connecté."""
    return app.test_client()


@pytest.fixture
def client(app, gerant):
    """Client HTTP de test, connecté en tant que gérant."""
    client = app.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = str(gerant.id)
        session["_fresh"] = True
    return client
