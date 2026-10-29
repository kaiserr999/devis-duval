"""Tests de l'inscription d'un client par lui-même (sans le gérant)."""
import pytest
from flask import g

from app.extensions import db
from app.models import Client, Utilisateur
from tests.conftest import GERANT_EMAIL

MOT_DE_PASSE = "mot-de-passe-client"


def texte(reponse):
    return reponse.get_data(as_text=True)


def inscrire(navigateur, email="jean.martin@example.com", **extra):
    donnees = {"email": email, "mot_de_passe": MOT_DE_PASSE,
               "confirmation": MOT_DE_PASSE, **extra}
    return navigateur.post("/inscription", data=donnees)


def changer_de_navigateur():
    """Les tests partagent un contexte d'application : on oublie
    l'utilisateur de la requête précédente."""
    g.pop("_login_user", None)


def comptes():
    return db.session.scalars(db.select(Utilisateur)).all()


def test_page_inscription(anonyme):
    page = texte(anonyme.get("/inscription"))
    assert "Créer mon compte client" in page
    assert 'name="telephone"' in page


def test_lien_depuis_l_espace_client(anonyme):
    page = texte(anonyme.get("/connexion?suivant=/espace/"))
    assert 'href="/inscription"' in page


def test_inscription_minimale(anonyme):
    reponse = inscrire(anonyme, email="  Jean.Martin@Example.com ")
    assert reponse.status_code == 302
    assert reponse.headers["Location"].endswith("/espace/")
    [compte] = comptes()
    assert compte.email == "jean.martin@example.com"
    assert compte.est_client
    assert compte.verifier_mot_de_passe(MOT_DE_PASSE)
    # Fiche client créée automatiquement, sans téléphone ni nom saisis
    assert compte.client.email == "jean.martin@example.com"
    assert compte.client.telephone is None
    assert compte.client.nom == "jean.martin"
    # Connecté directement sur son espace
    page = texte(anonyme.get("/espace/"))
    assert "Mes devis" in page
    assert "Aucun devis pour le moment" in page


def test_inscription_avec_telephone_et_nom(anonyme):
    inscrire(anonyme, telephone=" 06 12 34 56 78 ", nom="Jean Martin")
    [compte] = comptes()
    assert compte.client.telephone == "06 12 34 56 78"
    assert compte.client.nom == "Jean Martin"


@pytest.mark.parametrize("donnees, message", [
    ({"email": "pas-un-email"}, "Adresse email invalide."),
    ({"confirmation": "autre-mot-de-passe"}, "pas identiques"),
    ({"mot_de_passe": "court", "confirmation": "court"}, "10 caractères"),
    ({"telephone": "0" * 31}, "30 caractères"),
])
def test_inscription_invalide(anonyme, donnees, message):
    champs = {"email": "jean.martin@example.com",
              "mot_de_passe": MOT_DE_PASSE, "confirmation": MOT_DE_PASSE,
              **donnees}
    reponse = anonyme.post("/inscription", data=champs)
    assert reponse.status_code == 400
    assert message in texte(reponse)
    assert comptes() == []
    assert db.session.scalars(db.select(Client)).first() is None


@pytest.mark.parametrize("email", [GERANT_EMAIL, "client@example.com"])
def test_email_deja_utilise(anonyme, gerant, email):
    client = Client(nom="Déjà inscrit", email="client@example.com")
    compte = Utilisateur(email="client@example.com", client=client,
                         mot_de_passe_hash="x")
    db.session.add(compte)
    db.session.commit()
    reponse = inscrire(anonyme, email=email)
    assert reponse.status_code == 400
    assert "Un compte existe déjà" in texte(reponse)
    assert len(comptes()) == 2


def test_fiche_existante_recoit_un_lien_par_email(app, anonyme):
    """Le gérant a déjà créé la fiche : pas de compte sans preuve que
    l'email est le sien, le lien d'invitation part à cette adresse."""
    db.session.add(Client(nom="Mme Martin", email="Martin@Example.com"))
    db.session.commit()
    reponse = inscrire(anonyme, email="martin@example.com")
    page = texte(reponse)
    assert reponse.status_code == 200
    assert "nous venons de vous envoyer un email" in page
    assert "/activation/" not in page
    assert comptes() == []
    [message] = app.extensions["emails_envoyes"]
    assert message["To"] == "Martin@Example.com"
    assert "/activation/" in message.get_body(("plain",)).get_content()


def test_le_gerant_voit_le_nouveau_client(anonyme, client):
    inscrire(anonyme, telephone="06 12 34 56 78")
    changer_de_navigateur()
    page = texte(client.get("/clients"))
    assert "jean.martin" in page


def test_le_client_inscrit_voit_ses_devis_envoyes(app, anonyme, client):
    inscrire(anonyme)
    changer_de_navigateur()
    nouveau = db.session.scalars(db.select(Client)).one()
    reponse = client.post("/api/devis", json={
        "client_id": nouveau.id,
        "lignes": [{"description": "Peinture", "quantite": "10",
                    "prix_unitaire": "20.00"}]})
    devis_id = reponse.get_json()["id"]
    client.patch(f"/api/devis/{devis_id}/statut", json={"statut": "envoye"})
    # Il a déjà un compte : l'email contient le lien de connexion
    [message] = app.extensions["emails_envoyes"]
    assert "/connexion" in message.get_body(("plain",)).get_content()
    changer_de_navigateur()
    assert reponse.get_json()["numero"] in texte(anonyme.get("/espace/"))
