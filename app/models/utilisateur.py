"""Modèle Utilisateur (compte du gérant)."""
from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db
from app.models.client import maintenant

# Longueur minimale d'un mot de passe
MOT_DE_PASSE_MIN = 10


class Utilisateur(UserMixin, db.Model):
    """Compte qui peut se connecter à l'application."""

    __tablename__ = "utilisateurs"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    # Hash scrypt (Werkzeug), jamais le mot de passe en clair
    mot_de_passe_hash = db.Column(db.String(255), nullable=False)
    cree_le = db.Column(db.DateTime, nullable=False, default=maintenant)

    def definir_mot_de_passe(self, mot_de_passe):
        """Hache et enregistre le mot de passe. Lève ValueError si trop
        court."""
        if len(mot_de_passe) < MOT_DE_PASSE_MIN:
            raise ValueError(f"Le mot de passe doit faire au moins "
                             f"{MOT_DE_PASSE_MIN} caractères.")
        self.mot_de_passe_hash = generate_password_hash(mot_de_passe)

    def verifier_mot_de_passe(self, mot_de_passe):
        return check_password_hash(self.mot_de_passe_hash, mot_de_passe)
