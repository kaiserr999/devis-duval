"""Tests des modèles Client, Devis et LigneDevis."""
from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import Client, Devis, LigneDevis


@pytest.fixture
def devis(app):
    """Un devis enregistré pour un client."""
    client = Client(nom="Mme Martin")
    devis = Devis(numero="D-2026-0001", client=client)
    db.session.add(devis)
    db.session.commit()
    return devis


def test_total_egal_somme_des_sous_totaux(devis):
    devis.lignes = [
        LigneDevis(description="Peinture salon",
                   quantite=Decimal("32.5"), prix_unitaire=Decimal("24.90")),
        LigneDevis(description="Sous-couche",
                   quantite=Decimal("3"), prix_unitaire=Decimal("45.33")),
        LigneDevis(description="Protection sols",
                   quantite=Decimal("1"), prix_unitaire=Decimal("0.10")),
    ]
    devis.calculer_total()
    db.session.commit()
    db.session.expire_all()

    attendu = sum(ligne.sous_total for ligne in devis.lignes)
    assert devis.total == attendu
    assert devis.total == Decimal("945.34")


def test_calcul_sans_derive_d_arrondi(devis):
    ligne = LigneDevis(description="Enduit",
                       quantite=Decimal("12.5"),
                       prix_unitaire=Decimal("18.40"))
    devis.lignes.append(ligne)

    assert ligne.calculer_sous_total() == Decimal("230.00")
    devis.calculer_total()
    db.session.commit()
    db.session.expire_all()

    assert ligne.sous_total == Decimal("230.00")
    assert devis.total == Decimal("230.00")
    assert str(devis.total) == "230.00"


def test_suppression_devis_supprime_les_lignes(devis):
    devis.lignes = [
        LigneDevis(description="A", quantite=1, prix_unitaire=10),
        LigneDevis(description="B", quantite=2, prix_unitaire=20),
    ]
    devis.calculer_total()
    db.session.commit()
    assert db.session.query(LigneDevis).count() == 2

    db.session.delete(devis)
    db.session.commit()

    assert db.session.query(Devis).count() == 0
    assert db.session.query(LigneDevis).count() == 0


def test_cascade_au_niveau_base(devis):
    """ON DELETE CASCADE fonctionne aussi hors ORM (SQL brut)."""
    devis.lignes.append(
        LigneDevis(description="A", quantite=1, prix_unitaire=10))
    devis.calculer_total()
    db.session.commit()

    db.session.execute(db.delete(Devis).where(Devis.id == devis.id))
    db.session.commit()

    assert db.session.query(LigneDevis).count() == 0


@pytest.mark.parametrize("quantite, prix", [(0, 10), (-1, 10), (1, -0.01)])
def test_contraintes_check(devis, quantite, prix):
    devis.lignes.append(LigneDevis(description="X", quantite=quantite,
                                   prix_unitaire=prix, sous_total=0))
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()


def test_statut_par_defaut_brouillon(devis):
    assert devis.statut == "brouillon"


def test_to_dict(devis):
    devis.lignes.append(LigneDevis(description="A", quantite=Decimal("2"),
                                   prix_unitaire=Decimal("15.50")))
    devis.calculer_total()
    db.session.commit()

    donnees = devis.to_dict()
    assert donnees["numero"] == "D-2026-0001"
    assert donnees["total"] == "31.00"
    assert donnees["lignes"][0]["sous_total"] == "31.00"
    assert devis.client.to_dict()["nom"] == "Mme Martin"
