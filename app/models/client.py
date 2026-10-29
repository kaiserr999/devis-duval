"""Modèle Client."""
from datetime import datetime, timezone

from app.extensions import db


def maintenant():
    """Date/heure courante en UTC."""
    return datetime.now(timezone.utc)


class Client(db.Model):
    """Client de l'entreprise."""

    __tablename__ = "clients"

    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120))
    telephone = db.Column(db.String(30))
    adresse = db.Column(db.String(255))
    cree_le = db.Column(db.DateTime, nullable=False, default=maintenant)

    devis = db.relationship("Devis", back_populates="client")
    # Compte de l'espace client (None tant que le client ne l'a pas créé)
    compte = db.relationship("Utilisateur", back_populates="client",
                             uselist=False)

    @property
    def a_un_contact(self):
        """Vrai si le client a un email ou un téléphone."""
        return bool(self.email or self.telephone)

    def to_dict(self):
        """Représentation JSON du client."""
        return {
            "id": self.id,
            "nom": self.nom,
            "email": self.email,
            "telephone": self.telephone,
            "adresse": self.adresse,
            "cree_le": self.cree_le.isoformat() if self.cree_le else None,
        }
