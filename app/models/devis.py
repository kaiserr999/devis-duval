"""Modèle Devis."""
from decimal import Decimal

from app.extensions import db
from app.models.client import maintenant

STATUTS = ("brouillon", "envoye", "accepte", "refuse")


class Devis(db.Model):
    """Devis adressé à un client, composé de lignes."""

    __tablename__ = "devis"
    __table_args__ = (
        db.CheckConstraint(
            "statut IN ('brouillon', 'envoye', 'accepte', 'refuse')",
            name="ck_devis_statut",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey("clients.id"),
                          nullable=False)
    numero = db.Column(db.String(30), unique=True, nullable=False)
    date_creation = db.Column(db.DateTime, nullable=False,
                              default=maintenant)
    statut = db.Column(db.String(20), nullable=False, default="brouillon")
    total = db.Column(db.Numeric(10, 2), nullable=False,
                      default=Decimal("0.00"))

    client = db.relationship("Client", back_populates="devis")
    lignes = db.relationship(
        "LigneDevis",
        back_populates="devis",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def calculer_total(self):
        """Recalcule le total à partir des sous-totaux des lignes."""
        total = Decimal("0.00")
        for ligne in self.lignes:
            total += ligne.calculer_sous_total()
        self.total = total.quantize(Decimal("0.01"))
        return self.total

    def to_dict(self):
        """Représentation JSON du devis (montants en chaîne)."""
        return {
            "id": self.id,
            "client_id": self.client_id,
            "numero": self.numero,
            "date_creation": (self.date_creation.isoformat()
                              if self.date_creation else None),
            "statut": self.statut,
            "total": str(self.total) if self.total is not None else None,
            "lignes": [ligne.to_dict() for ligne in self.lignes],
        }
