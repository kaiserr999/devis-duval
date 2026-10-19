"""Tests de la connexion du gérant."""
import pytest

from app.extensions import db
from app.models import Client, Utilisateur
from tests.conftest import GERANT_EMAIL, GERANT_MOT_DE_PASSE


def connecter(client, email=GERANT_EMAIL, mot_de_passe=GERANT_MOT_DE_PASSE,
              **extra):
    return client.post("/connexion", data={
        "email": email, "mot_de_passe": mot_de_passe, **extra})


# --- Accès refusé sans connexion ---

@pytest.mark.parametrize("url", ["/", "/devis", "/devis/nouveau",
                                 "/devis/1", "/devis/1/pdf", "/clients",
                                 "/clients/1/modifier"])
def test_pages_redirigent_vers_la_connexion(anonyme, url):
    reponse = anonyme.get(url)
    assert reponse.status_code == 302
    assert "/connexion" in reponse.headers["Location"]


def test_redirection_garde_la_page_demandee(anonyme):
    reponse = anonyme.get("/devis?statut=envoye")
    assert reponse.headers["Location"].endswith(
        "/connexion?suivant=/devis?statut%3Denvoye")


@pytest.mark.parametrize("methode, url", [
    ("get", "/api/clients"), ("post", "/api/clients"),
    ("get", "/api/devis"), ("delete", "/api/devis/1"),
    ("patch", "/api/devis/1/statut")])
def test_api_repond_401_en_json(anonyme, methode, url):
    reponse = getattr(anonyme, methode)(url, json={})
    assert reponse.status_code == 401
    assert reponse.get_json() == {"erreur": "Authentification requise."}


def test_formulaire_anonyme_ne_modifie_rien(anonyme):
    reponse = anonyme.post("/clients/nouveau", data={"nom": "Intrus"})
    assert reponse.status_code == 302
    assert db.session.scalars(db.select(Client)).first() is None


@pytest.mark.parametrize("url", ["/api/health", "/connexion",
                                 "/static/style.css", "/apidocs/"])
def test_routes_publiques(anonyme, url):
    assert anonyme.get(url).status_code == 200


# --- Connexion ---

def test_connexion_puis_acces(anonyme, gerant):
    reponse = connecter(anonyme)
    assert reponse.status_code == 302
    assert reponse.headers["Location"].endswith("/devis")
    assert anonyme.get("/clients").status_code == 200
    assert anonyme.get("/api/clients").status_code == 200


def test_connexion_email_insensible_a_la_casse(anonyme, gerant):
    reponse = connecter(anonyme, email="  Gerant@Duval.Example.com ")
    assert reponse.status_code == 302


def test_connexion_renvoie_vers_la_page_demandee(anonyme, gerant):
    reponse = connecter(anonyme, suivant="/devis?statut=envoye")
    assert reponse.headers["Location"].endswith("/devis?statut=envoye")


@pytest.mark.parametrize("suivant", ["https://pirate.example.com/",
                                     "//pirate.example.com/",
                                     "/\\pirate.example.com", "devis"])
def test_connexion_refuse_les_redirections_externes(anonyme, gerant,
                                                    suivant):
    reponse = connecter(anonyme, suivant=suivant)
    assert reponse.status_code == 302
    assert reponse.headers["Location"] == "/devis"


@pytest.mark.parametrize("email, mot_de_passe", [
    (GERANT_EMAIL, "mauvais-mot-de-passe"),
    ("inconnu@example.com", GERANT_MOT_DE_PASSE),
    ("", "")])
def test_identifiants_incorrects(anonyme, gerant, email, mot_de_passe):
    reponse = connecter(anonyme, email=email, mot_de_passe=mot_de_passe)
    assert reponse.status_code == 401
    # Même message dans tous les cas : on ne révèle pas si l'email existe
    assert "Email ou mot de passe incorrect." in \
        reponse.get_data(as_text=True)
    assert anonyme.get("/devis").status_code == 302


def test_page_connexion_redirige_si_deja_connecte(client):
    reponse = client.get("/connexion")
    assert reponse.status_code == 302
    assert reponse.headers["Location"].endswith("/devis")


def test_deconnexion(client):
    assert client.get("/devis").status_code == 200
    assert client.get("/deconnexion").status_code == 405  # POST uniquement
    reponse = client.post("/deconnexion", follow_redirects=True)
    assert "Vous êtes déconnecté." in reponse.get_data(as_text=True)
    assert client.get("/devis").status_code == 302


def test_menu_affiche_la_deconnexion(client, anonyme):
    assert "Déconnexion" in client.get("/devis").get_data(as_text=True)
    assert "Déconnexion" not in \
        anonyme.get("/connexion").get_data(as_text=True)


# --- Modèle ---

def test_mot_de_passe_hache(app):
    utilisateur = Utilisateur(email="a@example.com")
    utilisateur.definir_mot_de_passe("un-long-secret")
    assert "un-long-secret" not in utilisateur.mot_de_passe_hash
    assert utilisateur.mot_de_passe_hash.startswith("scrypt:")
    assert utilisateur.verifier_mot_de_passe("un-long-secret")
    assert not utilisateur.verifier_mot_de_passe("autre-secret")


def test_mot_de_passe_trop_court(app):
    with pytest.raises(ValueError, match="au moins 10"):
        Utilisateur(email="a@example.com").definir_mot_de_passe("court")


# --- Commande flask creer-gerant ---

def test_commande_cree_puis_modifie_le_compte(app):
    runner = app.test_cli_runner()
    resultat = runner.invoke(args=["creer-gerant", "Chef@Duval.fr"],
                             input="secret-tres-long\nsecret-tres-long\n")
    assert resultat.exit_code == 0, resultat.output
    assert "Compte chef@duval.fr créé." in resultat.output
    compte = db.session.scalars(db.select(Utilisateur)).one()
    assert compte.verifier_mot_de_passe("secret-tres-long")

    resultat = runner.invoke(args=["creer-gerant", "chef@duval.fr"],
                             input="nouveau-secret-long\n"
                                   "nouveau-secret-long\n")
    assert "Mot de passe de chef@duval.fr modifié." in resultat.output
    db.session.refresh(compte)
    assert compte.verifier_mot_de_passe("nouveau-secret-long")
    assert db.session.query(Utilisateur).count() == 1


@pytest.mark.parametrize("email, saisie, message", [
    ("chef@duval.fr", "court\ncourt\n", "au moins 10"),
    ("pas-un-email", "secret-tres-long\nsecret-tres-long\n",
     "email invalide"),
])
def test_commande_refuse_les_valeurs_invalides(app, email, saisie, message):
    resultat = app.test_cli_runner().invoke(args=["creer-gerant", email],
                                            input=saisie)
    assert resultat.exit_code != 0
    assert message in resultat.output
    assert db.session.query(Utilisateur).count() == 0
