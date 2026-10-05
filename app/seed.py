"""Données de démonstration et commande `flask seed`."""
from decimal import Decimal

import click

from app.extensions import db
from app.models import Client, Devis, LigneDevis

CLIENTS = [
    {
        "nom": "Martine Lefebvre",
        "email": "martine.lefebvre@example.com",
        "telephone": "06 12 34 56 78",
        "adresse": "12 rue des Lilas, 69003 Lyon",
    },
    {
        "nom": "SCI Les Tilleuls",
        "email": "gestion@sci-tilleuls.example.com",
        "telephone": "04 78 00 11 22",
        "adresse": "45 avenue Jean Jaurès, 69007 Lyon",
    },
    {
        "nom": "Karim Benali",
        "email": "karim.benali@example.com",
        "telephone": "07 98 76 54 32",
        "adresse": "3 impasse du Moulin, 69100 Villeurbanne",
    },
    {
        "nom": "Boulangerie Au Bon Pain",
        "email": "contact@aubonpain.example.com",
        "telephone": "04 72 33 44 55",
        "adresse": "8 place de la Mairie, 69500 Bron",
    },
]

# (index du client, numéro, statut, [(description, quantité, prix unitaire)])
DEVIS = [
    (0, "D-2026-0001", "accepte", [
        ("Peinture murs salon (m²)", "42", "18.50"),
        ("Peinture plafond salon (m²)", "25", "21.00"),
        ("Protection sols et mobilier", "1", "85.00"),
    ]),
    (1, "D-2026-0002", "envoye", [
        ("Ravalement façade (m²)", "180", "32.00"),
        ("Location échafaudage (jour)", "6", "120.00"),
        ("Traitement anti-mousse (m²)", "180", "4.50"),
    ]),
    (2, "D-2026-0003", "brouillon", [
        ("Peinture chambre enfant (m²)", "30", "18.50"),
        ("Pose papier peint (rouleau)", "8", "27.90"),
    ]),
    (3, "D-2026-0004", "refuse", [
        ("Peinture boutique (m²)", "65", "22.00"),
        ("Laque boiseries vitrine (ml)", "14", "15.75"),
        ("Intervention hors horaires d'ouverture", "1", "250.00"),
    ]),
    (0, "D-2026-0005", "brouillon", [
        ("Peinture cage d'escalier (m²)", "38.5", "24.00"),
    ]),
]


def seed_data():
    """Insère les données de démo. Renvoie False si la base n'est pas vide."""
    if db.session.query(Client.id).first() is not None:
        return False

    clients = [Client(**donnees) for donnees in CLIENTS]
    db.session.add_all(clients)

    for index_client, numero, statut, lignes in DEVIS:
        devis = Devis(client=clients[index_client], numero=numero,
                      statut=statut)
        for description, quantite, prix in lignes:
            ligne = LigneDevis(description=description,
                               quantite=Decimal(quantite),
                               prix_unitaire=Decimal(prix))
            ligne.calculer_sous_total()
            devis.lignes.append(ligne)
        devis.calculer_total()
        db.session.add(devis)

    db.session.commit()
    return True


def vider_tables():
    """Supprime toutes les données (lignes, devis, clients)."""
    LigneDevis.query.delete()
    Devis.query.delete()
    Client.query.delete()
    db.session.commit()


@click.command("seed")
@click.option("--reset", is_flag=True,
              help="Vide les tables avant d'insérer les données de démo.")
def seed_command(reset):
    """Remplit la base avec des données de démonstration."""
    if reset:
        vider_tables()
        click.echo("Tables vidées.")
    if seed_data():
        click.echo(f"{len(CLIENTS)} clients et {len(DEVIS)} devis insérés.")
    else:
        click.echo("La base contient déjà des clients : rien n'a été "
                   "inséré (utiliser --reset pour repartir de zéro).")
