"""Modèle Utilisateur (compte du gérant ou d'un client)."""
from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db
from app.models.client import maintenant

# Longueur minimale d'un mot de passe
MOT_DE_PASSE_MIN = 10


class Utilisateur(UserMixin, db.Model):
    """Compte qui peut se connecter à l'application.

    Sans client_id : compte du gérant (accès à toute l'application).
    Avec client_id : compte d'un client (accès à son espace seulement).
    """

    __tablename__ = "utilisateurs"
    __table_args__ = (
        # Un seul compte par client
        db.UniqueConstraint("client_id", name="uq_utilisateurs_client_id"),
    )

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    # Hash scrypt (Werkzeug), jamais le mot de passe en clair
    mot_de_passe_hash = db.Column(db.String(255), nullable=False)
    cree_le = db.Column(db.DateTime, nullable=False, default=maintenant)
    client_id = db.Column(
        db.Integer,
        db.ForeignKey("clients.id", ondelete="CASCADE",
                      name="fk_utilisateurs_client_id"),
    )

    client = db.relationship("Client", back_populates="compte")

    @property
    def est_client(self):
        return self.client_id is not None

    @property
    def est_gerant(self):
        return self.client_id is None

    def definir_mot_de_passe(self, mot_de_passe):
        """Hache et enregistre le mot de passe. Lève ValueError si trop
        court."""
        if len(mot_de_passe) < MOT_DE_PASSE_MIN:
            raise ValueError(f"Le mot de passe doit faire au moins "
                             f"{MOT_DE_PASSE_MIN} caractères.")
        self.mot_de_passe_hash = generate_password_hash(mot_de_passe)

    def verifier_mot_de_passe(self, mot_de_passe):
        return check_password_hash(self.mot_de_passe_hash, mot_de_passe)
