"""Tests des routes /api/clients."""
import pytest

from app.extensions import db
from app.models import Client, Devis


@pytest.fixture
def mme_martin(app):
    """Un client enregistré."""
    client = Client(nom="Mme Martin", email="martin@example.com",
                    telephone="06 00 00 00 00", adresse="1 rue Haute")
    db.session.add(client)
    db.session.commit()
    return client


# --- Liste ---------------------------------------------------------------

def test_lister_vide(client):
    reponse = client.get("/api/clients")
    assert reponse.status_code == 200
    assert reponse.get_json() == []


def test_lister_par_ordre_alphabetique(client, app):
    db.session.add_all([Client(nom="Zoé"), Client(nom="Albert")])
    db.session.commit()
    noms = [c["nom"] for c in client.get("/api/clients").get_json()]
    assert noms == ["Albert", "Zoé"]


# --- Création ------------------------------------------------------------

def test_creer_client(client):
    reponse = client.post("/api/clients", json={
        "nom": "  Karim Benali ", "email": "karim@example.com",
        "telephone": "07 11 22 33 44", "adresse": "3 impasse du Moulin",
    })
    assert reponse.status_code == 201
    donnees = reponse.get_json()
    assert donnees["id"] is not None
    assert donnees["nom"] == "Karim Benali"
    assert donnees["cree_le"] is not None
    assert db.session.get(Client, donnees["id"]) is not None


def test_creer_client_nom_seul(client):
    reponse = client.post("/api/clients", json={"nom": "SCI Tilleuls"})
    assert reponse.status_code == 201
    assert reponse.get_json()["email"] is None


def test_creer_ignore_id_et_champs_inconnus(client):
    reponse = client.post("/api/clients",
                          json={"nom": "Test", "id": 999, "pirate": 1})
    assert reponse.status_code == 201
    donnees = reponse.get_json()
    assert donnees["id"] != 999
    assert "pirate" not in donnees


@pytest.mark.parametrize("corps, message", [
    ({}, "obligatoire"),
    ({"nom": "   "}, "obligatoire"),
    ({"nom": 42}, "chaîne"),
    ({"nom": "x" * 121}, "120"),
    ({"nom": "Test", "email": "pas-un-email"}, "email"),
    ({"nom": "Test", "telephone": "0" * 31}, "30"),
])
def test_creer_client_invalide(client, corps, message):
    reponse = client.post("/api/clients", json=corps)
    assert reponse.status_code == 400
    assert message in reponse.get_json()["erreur"]
    assert Client.query.count() == 0


def test_creer_sans_json(client):
    reponse = client.post("/api/clients", data="nom=Test")
    assert reponse.status_code == 400
    assert "JSON" in reponse.get_json()["erreur"]


def test_creer_json_liste(client):
    reponse = client.post("/api/clients", json=[{"nom": "Test"}])
    assert reponse.status_code == 400


# --- Lecture -------------------------------------------------------------

def test_voir_client(client, mme_martin):
    reponse = client.get(f"/api/clients/{mme_martin.id}")
    assert reponse.status_code == 200
    assert reponse.get_json()["nom"] == "Mme Martin"


def test_voir_client_inexistant(client):
    reponse = client.get("/api/clients/999")
    assert reponse.status_code == 404
    assert reponse.get_json() == {"erreur": "Client introuvable."}


# --- Modification --------------------------------------------------------

def test_modifier_client(client, mme_martin):
    reponse = client.put(f"/api/clients/{mme_martin.id}",
                         json={"nom": "Mme Martin-Durand",
                               "email": "durand@example.com"})
    assert reponse.status_code == 200
    donnees = reponse.get_json()
    assert donnees["nom"] == "Mme Martin-Durand"
    assert donnees["email"] == "durand@example.com"
    # PUT remplace tout : les champs absents sont vidés
    assert donnees["telephone"] is None
    assert donnees["adresse"] is None


def test_modifier_client_invalide(client, mme_martin):
    reponse = client.put(f"/api/clients/{mme_martin.id}", json={"nom": ""})
    assert reponse.status_code == 400
    db.session.expire_all()
    assert db.session.get(Client, mme_martin.id).nom == "Mme Martin"


def test_modifier_client_inexistant(client):
    reponse = client.put("/api/clients/999", json={"nom": "Test"})
    assert reponse.status_code == 404


# --- Suppression ---------------------------------------------------------

def test_supprimer_client(client, mme_martin):
    reponse = client.delete(f"/api/clients/{mme_martin.id}")
    assert reponse.status_code == 204
    assert db.session.get(Client, mme_martin.id) is None


def test_supprimer_client_inexistant(client):
    assert client.delete("/api/clients/999").status_code == 404


def test_supprimer_client_avec_devis_refuse(client, mme_martin):
    db.session.add(Devis(numero="D-2026-0001", client=mme_martin))
    db.session.commit()
    reponse = client.delete(f"/api/clients/{mme_martin.id}")
    assert reponse.status_code == 409
    assert "devis" in reponse.get_json()["erreur"]
    assert db.session.get(Client, mme_martin.id) is not None


# --- Erreurs génériques --------------------------------------------------

def test_methode_non_autorisee_en_json(client):
    reponse = client.patch("/api/clients")
    assert reponse.status_code == 405
    assert "erreur" in reponse.get_json()
