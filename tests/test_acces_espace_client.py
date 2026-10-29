"""Tests de l'accès à l'espace client : lien du menu, page de connexion
client et compte client de démo créé par flask seed."""
from app.extensions import db
from app.models import Utilisateur
from app.seed import CLIENTS, COMPTE_CLIENT_DEMO, seed_data

EMAIL_DEMO = CLIENTS[COMPTE_CLIENT_DEMO["index_client"]]["email"]


def texte(reponse):
    return reponse.get_data(as_text=True)


def test_menu_visiteur_montre_l_espace_client(anonyme):
    page = texte(anonyme.get("/connexion"))
    assert "Espace client" in page
    assert "/connexion?suivant=/espace/" in page


def test_page_connexion_client(anonyme):
    page = texte(anonyme.get("/connexion?suivant=/espace/"))
    assert "<h1>Espace client</h1>" in page
    assert "/inscription" in page
    # Pas de compte de démo tant que flask seed n'a pas tourné
    assert "Compte client de démonstration" not in page


def test_espace_sans_connexion_mene_a_la_connexion_client(anonyme):
    reponse = anonyme.get("/espace/", follow_redirects=True)
    page = texte(reponse)
    assert "<h1>Espace client</h1>" in page
    assert "votre espace client" in page


def test_seed_cree_le_compte_client_de_demo(app):
    seed_data()
    compte = db.session.scalars(db.select(Utilisateur).where(
        Utilisateur.email == EMAIL_DEMO)).one()
    assert compte.est_client
    assert compte.client.nom == "SCI Les Tilleuls"
    assert compte.verifier_mot_de_passe(COMPTE_CLIENT_DEMO["mot_de_passe"])


def test_connexion_avec_le_compte_de_demo(app, anonyme):
    seed_data()
    page = texte(anonyme.get("/connexion?suivant=/espace/"))
    assert "Compte client de démonstration" in page
    assert EMAIL_DEMO in page
    reponse = anonyme.post("/connexion", data={
        "email": EMAIL_DEMO, "suivant": "/espace/",
        "mot_de_passe": COMPTE_CLIENT_DEMO["mot_de_passe"]})
    assert reponse.headers["Location"].endswith("/espace/")
    page = texte(anonyme.get("/espace/"))
    assert "D-2026-0002" in page   # envoyé : à accepter en ligne
    assert "D-2026-0006" in page   # déjà accepté
    assert "D-2026-0001" not in page  # devis d'un autre client


def test_mauvais_mot_de_passe_reste_sur_la_page_client(anonyme):
    reponse = anonyme.post("/connexion", data={
        "email": "x@example.com", "mot_de_passe": "faux-mot-de-passe",
        "suivant": "/espace/"})
    assert reponse.status_code == 401
    assert "<h1>Espace client</h1>" in texte(reponse)


def test_commande_seed_affiche_le_compte_de_demo(app):
    resultat = app.test_cli_runner().invoke(args=["seed"])
    assert f"Compte client de démo : {EMAIL_DEMO}" in resultat.output
