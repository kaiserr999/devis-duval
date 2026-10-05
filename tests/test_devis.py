"""Tests des routes /api/devis."""
from datetime import datetime, timezone

import pytest

from app.extensions import db
from app.models import Client, Devis, LigneDevis

ANNEE = datetime.now(timezone.utc).year

LIGNES = [
    {"description": "Peinture salon (m²)", "quantite": "32.5",
     "prix_unitaire": "24.90"},
    {"description": "Sous-couche", "quantite": 3, "prix_unitaire": 45.33},
]


@pytest.fixture
def mme_martin(app):
    """Un client enregistré."""
    client = Client(nom="Mme Martin")
    db.session.add(client)
    db.session.commit()
    return client


@pytest.fixture
def creer(client, mme_martin):
    """Crée un devis via l'API et renvoie son JSON."""
    def _creer(lignes=LIGNES, **extra):
        reponse = client.post("/api/devis", json={
            "client_id": mme_martin.id, "lignes": lignes, **extra})
        assert reponse.status_code == 201, reponse.get_json()
        return reponse.get_json()
    return _creer


def passer_statut(client, devis_id, statut):
    return client.patch(f"/api/devis/{devis_id}/statut",
                        json={"statut": statut})


# --- Création ------------------------------------------------------------

def test_creer_devis_calcule_le_total(creer):
    devis = creer()
    assert devis["statut"] == "brouillon"
    assert [ligne["sous_total"] for ligne in devis["lignes"]] == [
        "809.25", "135.99"]
    assert devis["total"] == "945.24"


def test_creer_ignore_total_numero_statut_envoyes(creer):
    lignes = [{"description": "Enduit", "quantite": "12.5",
               "prix_unitaire": "18.40", "sous_total": "1.00"}]
    devis = creer(lignes=lignes, total="1.00", numero="PIRATE",
                  statut="accepte")
    assert devis["total"] == "230.00"
    assert devis["lignes"][0]["sous_total"] == "230.00"
    assert devis["numero"] == f"D-{ANNEE}-0001"
    assert devis["statut"] == "brouillon"


def test_creer_devis_sans_ligne(creer):
    devis = creer(lignes=[])
    assert devis["lignes"] == []
    assert devis["total"] == "0.00"


def test_numeros_automatiques_successifs(creer):
    numeros = [creer()["numero"] for _ in range(3)]
    assert numeros == [f"D-{ANNEE}-0001", f"D-{ANNEE}-0002",
                       f"D-{ANNEE}-0003"]


def test_numero_continue_apres_le_plus_grand(creer, mme_martin):
    db.session.add(Devis(numero=f"D-{ANNEE}-0041", client=mme_martin))
    db.session.add(Devis(numero=f"D-{ANNEE - 1}-0099", client=mme_martin))
    db.session.commit()
    assert creer()["numero"] == f"D-{ANNEE}-0042"


@pytest.mark.parametrize("client_id", [None, "1", True, 1.5])
def test_creer_client_id_invalide(client, mme_martin, client_id):
    reponse = client.post("/api/devis", json={"client_id": client_id})
    assert reponse.status_code == 400
    assert "client_id" in reponse.get_json()["erreur"]


def test_creer_client_inexistant(client, app):
    reponse = client.post("/api/devis", json={"client_id": 999})
    assert reponse.status_code == 400
    assert "n'existe pas" in reponse.get_json()["erreur"]


@pytest.mark.parametrize("ligne, message", [
    ({"quantite": 1, "prix_unitaire": 1}, "description"),
    ({"description": "  ", "quantite": 1, "prix_unitaire": 1},
     "description"),
    ({"description": "x" * 256, "quantite": 1, "prix_unitaire": 1}, "255"),
    ({"description": "A", "prix_unitaire": 1}, "obligatoires"),
    ({"description": "A", "quantite": 0, "prix_unitaire": 1},
     "supérieure à 0"),
    ({"description": "A", "quantite": "-2", "prix_unitaire": 1},
     "supérieure à 0"),
    ({"description": "A", "quantite": 1, "prix_unitaire": -1}, "négatif"),
    ({"description": "A", "quantite": "abc", "prix_unitaire": 1}, "nombre"),
    ({"description": "A", "quantite": True, "prix_unitaire": 1}, "nombre"),
    ({"description": "A", "quantite": "NaN", "prix_unitaire": 1}, "nombre"),
    ({"description": "A", "quantite": 1, "prix_unitaire": "9.999"},
     "2 décimales"),
    ({"description": "A", "quantite": 1, "prix_unitaire": "100000000"},
     "trop grand"),
    ({"description": "A", "quantite": "99999", "prix_unitaire": "99999"},
     "trop grand"),
    ("pas un objet", "objet JSON"),
])
def test_creer_ligne_invalide(client, mme_martin, ligne, message):
    reponse = client.post("/api/devis", json={
        "client_id": mme_martin.id, "lignes": [ligne]})
    assert reponse.status_code == 400
    erreur = reponse.get_json()["erreur"]
    assert erreur.startswith("Ligne 1")
    assert message in erreur
    assert Devis.query.count() == 0


def test_creer_lignes_pas_une_liste(client, mme_martin):
    reponse = client.post("/api/devis", json={
        "client_id": mme_martin.id, "lignes": "Peinture"})
    assert reponse.status_code == 400


def test_creer_sans_json(client):
    assert client.post("/api/devis", data="x").status_code == 400


# --- Liste et lecture ----------------------------------------------------

def test_lister_et_filtrer(client, creer, mme_martin):
    autre = Client(nom="M. Durand")
    db.session.add(autre)
    db.session.commit()
    premier = creer()
    client.post("/api/devis", json={"client_id": autre.id,
                                    "lignes": LIGNES})
    passer_statut(client, premier["id"], "envoye")

    assert len(client.get("/api/devis").get_json()) == 2
    par_client = client.get(f"/api/devis?client_id={mme_martin.id}")
    assert [d["id"] for d in par_client.get_json()] == [premier["id"]]
    envoyes = client.get("/api/devis?statut=envoye").get_json()
    assert [d["id"] for d in envoyes] == [premier["id"]]


@pytest.mark.parametrize("filtre", ["statut=perdu", "client_id=abc"])
def test_lister_filtre_invalide(client, filtre):
    assert client.get(f"/api/devis?{filtre}").status_code == 400


def test_voir_devis(client, creer):
    devis = creer()
    reponse = client.get(f"/api/devis/{devis['id']}")
    assert reponse.status_code == 200
    assert reponse.get_json() == devis


def test_voir_devis_inexistant(client):
    reponse = client.get("/api/devis/999")
    assert reponse.status_code == 404
    assert reponse.get_json() == {"erreur": "Devis introuvable."}


# --- Modification --------------------------------------------------------

def test_modifier_remplace_les_lignes(client, creer):
    devis = creer()
    reponse = client.put(f"/api/devis/{devis['id']}", json={"lignes": [
        {"description": "Plafond", "quantite": 10, "prix_unitaire": "21"}]})
    assert reponse.status_code == 200
    donnees = reponse.get_json()
    assert len(donnees["lignes"]) == 1
    assert donnees["total"] == "210.00"
    assert donnees["numero"] == devis["numero"]
    # les anciennes lignes sont supprimées de la base
    assert LigneDevis.query.count() == 1


def test_modifier_sans_lignes(client, creer):
    devis = creer()
    assert client.put(f"/api/devis/{devis['id']}",
                      json={}).status_code == 400


def test_modifier_invalide_ne_change_rien(client, creer):
    devis = creer()
    reponse = client.put(f"/api/devis/{devis['id']}", json={"lignes": [
        {"description": "A", "quantite": 0, "prix_unitaire": 1}]})
    assert reponse.status_code == 400
    db.session.rollback()
    assert client.get(f"/api/devis/{devis['id']}").get_json() == devis


def test_modifier_devis_envoye_interdit(client, creer):
    devis = creer()
    passer_statut(client, devis["id"], "envoye")
    reponse = client.put(f"/api/devis/{devis['id']}",
                         json={"lignes": LIGNES})
    assert reponse.status_code == 409
    assert "brouillon" in reponse.get_json()["erreur"]


def test_modifier_devis_inexistant(client):
    assert client.put("/api/devis/999",
                      json={"lignes": []}).status_code == 404


# --- Statut --------------------------------------------------------------

@pytest.mark.parametrize("fin", ["accepte", "refuse"])
def test_parcours_complet_du_statut(client, creer, fin):
    devis = creer()
    assert passer_statut(client, devis["id"], "envoye").status_code == 200
    reponse = passer_statut(client, devis["id"], fin)
    assert reponse.status_code == 200
    assert reponse.get_json()["statut"] == fin


@pytest.mark.parametrize("chemin, interdit", [
    ([], "accepte"),                     # brouillon -> accepte
    ([], "brouillon"),                   # brouillon -> brouillon
    (["envoye"], "brouillon"),           # retour en arrière
    (["envoye", "accepte"], "refuse"),   # statut final
    (["envoye", "refuse"], "envoye"),
])
def test_transitions_interdites(client, creer, chemin, interdit):
    devis = creer()
    for statut in chemin:
        assert passer_statut(client, devis["id"], statut).status_code == 200
    reponse = passer_statut(client, devis["id"], interdit)
    assert reponse.status_code == 409
    assert "interdit" in reponse.get_json()["erreur"]


def test_statut_inconnu(client, creer):
    devis = creer()
    reponse = passer_statut(client, devis["id"], "perdu")
    assert reponse.status_code == 400


def test_envoyer_devis_vide_interdit(client, creer):
    devis = creer(lignes=[])
    reponse = passer_statut(client, devis["id"], "envoye")
    assert reponse.status_code == 409
    assert "sans ligne" in reponse.get_json()["erreur"]


def test_statut_devis_inexistant(client):
    assert passer_statut(client, 999, "envoye").status_code == 404


# --- Suppression ---------------------------------------------------------

def test_supprimer_brouillon(client, creer):
    devis = creer()
    assert client.delete(f"/api/devis/{devis['id']}").status_code == 204
    assert Devis.query.count() == 0
    assert LigneDevis.query.count() == 0


def test_supprimer_devis_envoye_interdit(client, creer):
    devis = creer()
    passer_statut(client, devis["id"], "envoye")
    assert client.delete(f"/api/devis/{devis['id']}").status_code == 409
    assert Devis.query.count() == 1


def test_supprimer_devis_inexistant(client):
    assert client.delete("/api/devis/999").status_code == 404
