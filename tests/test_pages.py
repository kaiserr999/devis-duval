"""Tests de l'interface web (pages Jinja)."""
from decimal import Decimal

import pytest

from app import create_app
from app.config import TestConfig
from app.extensions import db
from app.models import Client, Devis, LigneDevis


@pytest.fixture
def mme_martin(app):
    client = Client(nom="Mme Martin", email="martin@example.com",
                    telephone="06 00 00 00 00")
    db.session.add(client)
    db.session.commit()
    return client


@pytest.fixture
def brouillon(mme_martin):
    devis = Devis(numero="D-2026-0001", statut="brouillon",
                  client=mme_martin)
    devis.lignes = [LigneDevis(description="Peinture salon",
                               quantite=Decimal("10"),
                               prix_unitaire=Decimal("25.50"))]
    devis.calculer_total()
    db.session.add(devis)
    db.session.commit()
    return devis


def texte(reponse):
    return reponse.get_data(as_text=True)


def lignes_formulaire(*lignes):
    """[(description, quantite, prix), ...] -> champs de formulaire."""
    return {
        "description": [ligne[0] for ligne in lignes],
        "quantite": [ligne[1] for ligne in lignes],
        "prix_unitaire": [ligne[2] for ligne in lignes],
    }


# --- Navigation ---

def test_accueil_redirige_vers_les_devis(client):
    reponse = client.get("/")
    assert reponse.status_code == 302
    assert reponse.headers["Location"].endswith("/devis")


@pytest.mark.parametrize("url", ["/clients", "/clients/nouveau", "/devis",
                                 "/devis/nouveau", "/devis?statut=envoye"])
def test_pages_vides_s_affichent(client, url):
    assert client.get(url).status_code == 200


def test_page_inexistante_en_html(client):
    reponse = client.get("/clients/999")
    assert reponse.status_code == 404
    assert reponse.mimetype == "text/html"
    assert "Client introuvable." in texte(reponse)


def test_api_reste_en_json(client):
    reponse = client.get("/api/clients/999")
    assert reponse.status_code == 404
    assert reponse.get_json() == {"erreur": "Client introuvable."}


# --- Clients ---

def test_liste_et_fiche_client(client, brouillon):
    assert "Mme Martin" in texte(client.get("/clients"))
    page = texte(client.get(f"/clients/{brouillon.client_id}"))
    assert "martin@example.com" in page
    assert "D-2026-0001" in page
    assert "255,00" in page


def test_creer_client(client):
    reponse = client.post("/clients/nouveau", data={
        "nom": "  SCI Les Tilleuls ", "email": "", "telephone": "",
        "adresse": "3 rue Haute"})
    assert reponse.status_code == 302
    nouveau = db.session.scalars(db.select(Client)).one()
    assert nouveau.nom == "SCI Les Tilleuls"
    assert nouveau.email is None
    assert reponse.headers["Location"].endswith(f"/clients/{nouveau.id}")


def test_creer_client_invalide_garde_la_saisie(client):
    reponse = client.post("/clients/nouveau", data={
        "nom": "Dupont", "email": "pas-un-email"})
    assert reponse.status_code == 400
    page = texte(reponse)
    assert "Le champ &#39;email&#39; est invalide." in page
    assert 'value="Dupont"' in page
    assert db.session.scalars(db.select(Client)).first() is None


def test_modifier_client(client, mme_martin):
    reponse = client.post(f"/clients/{mme_martin.id}/modifier",
                          data={"nom": "Mme Martin-Durand"})
    assert reponse.status_code == 302
    assert mme_martin.nom == "Mme Martin-Durand"
    assert mme_martin.email is None


def test_supprimer_client_sans_devis(client, mme_martin):
    client_id = mme_martin.id
    reponse = client.post(f"/clients/{client_id}/supprimer",
                          follow_redirects=True)
    assert "Client « Mme Martin » supprimé." in texte(reponse)
    assert db.session.get(Client, client_id) is None


def test_supprimer_client_avec_devis_refuse(client, brouillon):
    reponse = client.post(f"/clients/{brouillon.client_id}/supprimer",
                          follow_redirects=True)
    assert "Ce client a des devis" in texte(reponse)
    assert db.session.get(Client, brouillon.client_id) is not None


# --- Devis ---

def test_liste_devis_filtree(client, brouillon):
    assert "D-2026-0001" in texte(client.get("/devis"))
    assert "D-2026-0001" in texte(client.get("/devis?statut=brouillon"))
    assert "D-2026-0001" not in texte(client.get("/devis?statut=envoye"))


def test_detail_devis(client, brouillon):
    page = texte(client.get(f"/devis/{brouillon.id}"))
    assert "Peinture salon" in page
    assert "25,50" in page
    assert "255,00" in page
    assert "Marquer comme envoyé" in page


def test_creer_devis_total_calcule_par_le_serveur(client, mme_martin):
    reponse = client.post("/devis/nouveau", data={
        "client_id": mme_martin.id, "total": "1",
        **lignes_formulaire(("Peinture", "2,5", "1 000,10"),
                            ("", "", ""),
                            ("Sous-couche", "3", "45.33"))})
    assert reponse.status_code == 302
    devis = db.session.scalars(db.select(Devis)).one()
    assert devis.statut == "brouillon"
    assert len(devis.lignes) == 2
    # 2,5 x 1000,10 + 3 x 45,33 = 2500,25 + 135,99
    assert devis.total == Decimal("2636.24")
    assert reponse.headers["Location"].endswith(f"/devis/{devis.id}")


def test_creer_devis_sans_client(client):
    reponse = client.post("/devis/nouveau",
                          data=lignes_formulaire(("Peinture", "1", "10")))
    assert reponse.status_code == 400
    assert "Choisissez un client." in texte(reponse)


def test_creer_devis_ligne_invalide_garde_la_saisie(client, mme_martin):
    reponse = client.post("/devis/nouveau", data={
        "client_id": mme_martin.id,
        **lignes_formulaire(("Peinture", "0", "10"))})
    assert reponse.status_code == 400
    page = texte(reponse)
    assert "Ligne 1 : la quantité doit être supérieure à 0." in page
    assert 'value="Peinture"' in page
    assert db.session.scalars(db.select(Devis)).first() is None


def test_modifier_devis(client, brouillon):
    reponse = client.post(f"/devis/{brouillon.id}/modifier",
                          data=lignes_formulaire(("Plafond", "4", "30")))
    assert reponse.status_code == 302
    assert [ligne.description for ligne in brouillon.lignes] == ["Plafond"]
    assert brouillon.total == Decimal("120.00")


def test_modifier_devis_invalide_ne_change_rien(client, brouillon):
    reponse = client.post(f"/devis/{brouillon.id}/modifier",
                          data=lignes_formulaire(("Plafond", "abc", "30")))
    assert reponse.status_code == 400
    db.session.expire_all()
    assert [ligne.description for ligne in brouillon.lignes] == \
        ["Peinture salon"]
    assert brouillon.total == Decimal("255.00")


def test_cycle_de_vie_du_statut(client, brouillon):
    url = f"/devis/{brouillon.id}/statut"
    client.post(url, data={"statut": "envoye"})
    assert brouillon.statut == "envoye"

    page = texte(client.get(f"/devis/{brouillon.id}"))
    assert "Accepté par le client" in page
    assert "Modifier" not in page

    reponse = client.post(url, data={"statut": "brouillon"},
                          follow_redirects=True)
    assert "interdit" in texte(reponse)
    client.post(url, data={"statut": "accepte"})
    assert brouillon.statut == "accepte"


def test_devis_envoye_ni_modifiable_ni_supprimable(client, brouillon):
    brouillon.statut = "envoye"
    db.session.commit()
    for url in (f"/devis/{brouillon.id}/modifier",
                f"/devis/{brouillon.id}/supprimer"):
        reponse = client.post(url, data=lignes_formulaire(("X", "1", "1")),
                              follow_redirects=True)
        assert "Seul un devis en brouillon" in texte(reponse)
    devis = db.session.get(Devis, brouillon.id)
    assert devis.lignes[0].description == "Peinture salon"


def test_supprimer_devis_brouillon(client, brouillon):
    devis_id = brouillon.id
    reponse = client.post(f"/devis/{devis_id}/supprimer")
    assert reponse.status_code == 302
    assert db.session.get(Devis, devis_id) is None


# --- Sécurité ---

class ConfigAvecCsrf(TestConfig):
    WTF_CSRF_ENABLED = True


def test_formulaire_sans_jeton_csrf_refuse():
    app = create_app(ConfigAvecCsrf)
    with app.app_context():
        db.create_all()
        client = app.test_client()
        reponse = client.post("/clients/nouveau", data={"nom": "Pirate"})
        assert reponse.status_code == 400
        assert db.session.scalars(db.select(Client)).first() is None
        # L'API JSON n'utilise pas de jeton CSRF
        assert client.post("/api/clients",
                           json={"nom": "API"}).status_code == 201
        db.session.remove()
        db.drop_all()
