"""Tests des données de démonstration."""
from decimal import Decimal

from app.models import Client, Devis, LigneDevis
from app.seed import CLIENTS, DEVIS, seed_data


def test_seed_remplit_la_base(app):
    assert seed_data() is True
    assert Client.query.count() == len(CLIENTS)
    assert Devis.query.count() == len(DEVIS)
    assert LigneDevis.query.count() == sum(len(d[3]) for d in DEVIS)


def test_seed_totaux_calcules(app):
    seed_data()
    devis = Devis.query.filter_by(numero="D-2026-0001").one()
    # 42 x 18.50 + 25 x 21.00 + 1 x 85.00
    assert devis.total == Decimal("1387.00")
    for d in Devis.query.all():
        assert d.total == sum(ligne.sous_total for ligne in d.lignes)


def test_seed_idempotent(app):
    assert seed_data() is True
    assert seed_data() is False
    assert Client.query.count() == len(CLIENTS)


def test_commande_seed_reset(app):
    runner = app.test_cli_runner()
    resultat = runner.invoke(args=["seed"])
    assert "insérés" in resultat.output
    resultat = runner.invoke(args=["seed"])
    assert "déjà" in resultat.output
    resultat = runner.invoke(args=["seed", "--reset"])
    assert "Tables vidées" in resultat.output
    assert Client.query.count() == len(CLIENTS)
