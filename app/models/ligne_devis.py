"""Modèle LigneDevis."""
from decimal import Decimal, ROUND_HALF_UP

from app.extensions import db

CENTIME = Decimal("0.01")


class LigneDevis(db.Model):
    """Ligne d'un devis (prestation ou fourniture)."""

    __tablename__ = "lignes_devis"
    __table_args__ = (
        db.CheckConstraint("quantite > 0", name="ck_ligne_quantite"),
        db.CheckConstraint("prix_unitaire >= 0", name="ck_ligne_prix"),
    )

    id = db.Column(db.Integer, primary_key=True)
    devis_id = db.Column(
        db.Integer,
        db.ForeignKey("devis.id", ondelete="CASCADE"),
        nullable=False,
    )
    description = db.Column(db.String(255), nullable=False)
    quantite = db.Column(db.Numeric(10, 2), nullable=False)
    prix_unitaire = db.Column(db.Numeric(10, 2), nullable=False)
    sous_total = db.Column(db.Numeric(10, 2), nullable=False,
                           default=Decimal("0.00"))

    devis = db.relationship("Devis", back_populates="lignes")

    def calculer_sous_total(self):
        """Calcule quantite x prix_unitaire, arrondi au centime."""
        quantite = Decimal(str(self.quantite))
        prix = Decimal(str(self.prix_unitaire))
        self.sous_total = (quantite * prix).quantize(
            CENTIME, rounding=ROUND_HALF_UP)
        return self.sous_total

    def to_dict(self):
        """Représentation JSON de la ligne (montants en chaîne)."""
        return {
            "id": self.id,
            "devis_id": self.devis_id,
            "description": self.description,
            "quantite": str(self.quantite),
            "prix_unitaire": str(self.prix_unitaire),
            "sous_total": str(self.sous_total),
        }
