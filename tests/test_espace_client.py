"""Tests de l'espace client : contact obligatoire, email à l'envoi du
devis, création du compte client, pages du client et droits d'accès."""
from decimal import Decimal

import pytest
from werkzeug.security import generate_password_hash

from app.extensions import db
from app.invitations import creer_jeton
from app.models import Client, Devis, LigneDevis, Utilisateur
from tests.conftest import GERANT_EMAIL

MOT_DE_PASSE = "mot-de-passe-client"


def texte(reponse):
    return reponse.get_data(as_text=True)


def emails(app):
    """Emails envoyés pendant le test (MAIL_MEMOIRE)."""
    return app.extensions.get("emails_envoyes", [])


def corps(message):
    return message.get_body(("plain",)).get_content()


def ajouter_devis(client_modele, numero, statut="brouillon"):
    devis = Devis(numero=numero, statut=statut, client=client_modele)
    devis.lignes = [LigneDevis(description="Peinture salon",
                               quantite=Decimal("10"),
                               prix_unitaire=Decimal("25.50"))]
    devis.lignes[0].calculer_sous_total()
    devis.calculer_total()
    db.session.add(devis)
    db.session.commit()
    return devis


def creer_compte(client_modele):
    compte = Utilisateur(
        email=client_modele.email, client=client_modele,
        mot_de_passe_hash=generate_password_hash(
            MOT_DE_PASSE, method="pbkdf2:sha256:1000"))
    db.session.add(compte)
    db.session.commit()
    return compte


@pytest.fixture
def mme_martin(app):
    client = Client(nom="Mme Martin", email="martin@example.com",
                    telephone="06 00 00 00 00")
    db.session.add(client)
    db.session.commit()
    return client


@pytest.fixture
def m_durand(app):
    """Client joignable par téléphone seulement."""
    client = Client(nom="M. Durand", telephone="07 00 00 00 00")
    db.session.add(client)
    db.session.commit()
    return client


@pytest.fixture
def brouillon(mme_martin):
    return ajouter_devis(mme_martin, "D-2026-0001")


@pytest.fixture
def compte(mme_martin):
    return creer_compte(mme_martin)


@pytest.fixture
def espace(app, compte):
    """Client HTTP connecté avec le compte client de Mme Martin."""
    navigateur = app.test_client()
    with navigateur.session_transaction() as session:
        session["_user_id"] = str(compte.id)
        session["_fresh"] = True
    return navigateur


# --- Email ou téléphone obligatoire ---

def test_page_client_sans_contact_refusee(client):
    reponse = client.post("/clients/nouveau", data={
        "nom": "Dupont", "email": "", "telephone": " "})
    assert reponse.status_code == 400
    assert "Indiquez au moins un email ou un téléphone." in texte(reponse)
    assert db.session.scalars(db.select(Client)).first() is None


def test_devis_refuse_pour_client_sans_contact(client):
    # Client enregistré avant la règle, sans email ni téléphone
    ancien = Client(nom="Ancien client")
    db.session.add(ancien)
    db.session.commit()
    reponse = client.post("/api/devis", json={"client_id": ancien.id,
                                              "lignes": []})
    assert reponse.status_code == 400
    assert "ni email ni téléphone" in reponse.get_json()["erreur"]
    assert db.session.scalars(db.select(Devis)).first() is None


def test_envoi_refuse_pour_client_sans_contact(client):
    ancien = Client(nom="Ancien client")
    db.session.add(ancien)
    devis = ajouter_devis(ancien, "D-2026-0001")
    reponse = client.patch(f"/api/devis/{devis.id}/statut",
                           json={"statut": "envoye"})
    assert reponse.status_code == 409
    assert "ni email ni téléphone" in reponse.get_json()["erreur"]
    assert devis.statut == "brouillon"


def test_formulaire_devis_signale_client_sans_contact(client):
    db.session.add(Client(nom="Ancien client"))
    db.session.commit()
    page = texte(client.get("/devis/nouveau"))
    assert "Ancien client (sans email ni téléphone)" in page


# --- Email au client quand le devis est envoyé ---

def test_envoi_du_devis_par_email(app, client, brouillon):
    reponse = client.post(f"/devis/{brouillon.id}/statut",
                          data={"statut": "envoye"}, follow_redirects=True)
    assert "Email envoyé à martin@example.com." in texte(reponse)
    assert brouillon.statut == "envoye"

    [message] = emails(app)
    assert message["To"] == "martin@example.com"
    assert "D-2026-0001" in message["Subject"]
    assert "Votre devis" in message["Subject"]
    assert "/activation/" in corps(message)
    assert "255,00" in corps(message)
    [pdf] = list(message.iter_attachments())
    assert pdf.get_filename() == "devis-D-2026-0001.pdf"
    assert pdf.get_content().startswith(b"%PDF")


def test_envoi_via_api_envoie_aussi_l_email(app, client, brouillon):
    reponse = client.patch(f"/api/devis/{brouillon.id}/statut",
                           json={"statut": "envoye"})
    assert reponse.status_code == 200
    assert len(emails(app)) == 1


def test_client_avec_compte_recoit_le_lien_de_connexion(app, client,
                                                        brouillon, compte):
    client.post(f"/devis/{brouillon.id}/statut", data={"statut": "envoye"})
    [message] = emails(app)
    assert "/activation/" not in corps(message)
    assert "/connexion" in corps(message)


def test_client_sans_email_pas_d_email(app, client, m_durand):
    devis = ajouter_devis(m_durand, "D-2026-0001")
    reponse = client.post(f"/devis/{devis.id}/statut",
                          data={"statut": "envoye"}, follow_redirects=True)
    assert devis.statut == "envoye"
    assert emails(app) == []
    assert "prévenez ce client par téléphone (07 00 00 00 00)" \
        in texte(reponse)


def test_accepte_n_envoie_pas_d_email(app, client, mme_martin):
    devis = ajouter_devis(mme_martin, "D-2026-0001", statut="envoye")
    client.post(f"/devis/{devis.id}/statut", data={"statut": "accepte"})
    assert devis.statut == "accepte"
    assert emails(app) == []


def test_echec_smtp_n_annule_pas_l_envoi(app, client, brouillon,
                                         monkeypatch):
    def refuser(message):
        raise OSError("serveur injoignable")
    monkeypatch.setattr("app.notifications.envoyer", refuser)
    reponse = client.post(f"/devis/{brouillon.id}/statut",
                          data={"statut": "envoye"}, follow_redirects=True)
    assert brouillon.statut == "envoye"
    assert "n&#39;a pas pu être envoyé" in texte(reponse)


def test_sans_serveur_email_lien_affiche(app, client, brouillon):
    app.config.update(MAIL_MEMOIRE=False, MAIL_SERVER=None)
    reponse = client.post(f"/devis/{brouillon.id}/statut",
                          data={"statut": "envoye"}, follow_redirects=True)
    page = texte(reponse)
    assert "affiché dans le terminal" in page
    assert "/activation/" in page


def test_envoi_par_smtp(app, client, brouillon, monkeypatch):
    appels = []

    class FauxSMTP:
        def __init__(self, serveur, port, timeout):
            appels.append(("connexion", serveur, port))

        def __enter__(self):
            return self

        def __exit__(self, *erreur):
            return False

        def starttls(self):
            appels.append(("starttls",))

        def login(self, utilisateur, mot_de_passe):
            appels.append(("login", utilisateur, mot_de_passe))

        def send_message(self, message):
            appels.append(("envoi", message["To"]))

    monkeypatch.setattr("smtplib.SMTP", FauxSMTP)
    app.config.update(MAIL_MEMOIRE=False, MAIL_SERVER="smtp.example.com",
                      MAIL_PORT=587, MAIL_USERNAME="duval",
                      MAIL_PASSWORD="secret")
    client.post(f"/devis/{brouillon.id}/statut", data={"statut": "envoye"})
    assert appels == [("connexion", "smtp.example.com", 587),
                      ("starttls",), ("login", "duval", "secret"),
                      ("envoi", "martin@example.com")]


# --- Invitation depuis la fiche client ---

def test_fiche_propose_l_invitation(client, mme_martin):
    page = texte(client.get(f"/clients/{mme_martin.id}"))
    assert "Pas encore de compte" in page
    assert "Envoyer l'invitation par email" in page


def test_inviter_client(app, client, mme_martin):
    reponse = client.post(f"/clients/{mme_martin.id}/inviter",
                          follow_redirects=True)
    assert "Email envoyé à martin@example.com." in texte(reponse)
    [message] = emails(app)
    assert "espace client" in message["Subject"]
    assert "/activation/" in corps(message)


def test_inviter_client_qui_a_deja_un_compte(app, client, mme_martin,
                                             compte):
    reponse = client.post(f"/clients/{mme_martin.id}/inviter",
                          follow_redirects=True)
    assert "a déjà un compte client" in texte(reponse)
    assert emails(app) == []
    assert "Compte créé le" in texte(client.get(f"/clients/{mme_martin.id}"))


# --- Création du compte client ---

def lien_activation(client_modele):
    return f"/activation/{creer_jeton(client_modele)}"


def test_page_d_activation(anonyme, mme_martin):
    reponse = anonyme.get(lien_activation(mme_martin))
    assert reponse.status_code == 200
    assert 'value="martin@example.com"' in texte(reponse)


def test_creer_son_compte(anonyme, mme_martin):
    reponse = anonyme.post(lien_activation(mme_martin), data={
        "mot_de_passe": MOT_DE_PASSE, "confirmation": MOT_DE_PASSE})
    assert reponse.status_code == 302
    assert reponse.headers["Location"].endswith("/espace/")
    assert mme_martin.compte.email == "martin@example.com"
    assert mme_martin.compte.verifier_mot_de_passe(MOT_DE_PASSE)
    # Connecté directement
    assert anonyme.get("/espace/").status_code == 200


@pytest.mark.parametrize("mot_de_passe, confirmation, message", [
    ("mot-de-passe-1", "mot-de-passe-2", "pas identiques"),
    ("court", "court", "10 caractères"),
])
def test_creer_son_compte_invalide(anonyme, mme_martin, mot_de_passe,
                                   confirmation, message):
    reponse = anonyme.post(lien_activation(mme_martin), data={
        "mot_de_passe": mot_de_passe, "confirmation": confirmation})
    assert reponse.status_code == 400
    assert message in texte(reponse)
    assert mme_martin.compte is None
    assert db.session.scalars(db.select(Utilisateur)).first() is None


def test_lien_deja_utilise(anonyme, mme_martin, compte):
    reponse = anonyme.get(lien_activation(mme_martin))
    assert reponse.status_code == 302
    assert "/connexion" in reponse.headers["Location"]


def test_lien_falsifie(anonyme, mme_martin):
    reponse = anonyme.get(lien_activation(mme_martin) + "x")
    assert reponse.status_code == 400
    assert "pas valide" in texte(reponse)


def test_lien_expire(app, anonyme, mme_martin):
    lien = lien_activation(mme_martin)
    app.config["INVITATION_VALIDITE_JOURS"] = -1
    reponse = anonyme.get(lien)
    assert reponse.status_code == 400
    assert "expiré" in texte(reponse)


def test_lien_perime_si_l_email_change(anonyme, mme_martin):
    lien = lien_activation(mme_martin)
    mme_martin.email = "nouvel-email@example.com"
    db.session.commit()
    reponse = anonyme.get(lien)
    assert reponse.status_code == 400
    assert "plus valable" in texte(reponse)


def test_email_deja_pris_par_le_gerant(anonyme, gerant):
    client_modele = Client(nom="Gérant aussi client", email=GERANT_EMAIL)
    db.session.add(client_modele)
    db.session.commit()
    reponse = anonyme.post(lien_activation(client_modele), data={
        "mot_de_passe": MOT_DE_PASSE, "confirmation": MOT_DE_PASSE})
    assert reponse.status_code == 400
    assert "déjà utilisé" in texte(reponse)


# --- Espace client ---

def test_connexion_client_mene_a_son_espace(anonyme, compte):
    reponse = anonyme.post("/connexion", data={
        "email": "martin@example.com", "mot_de_passe": MOT_DE_PASSE})
    assert reponse.status_code == 302
    assert reponse.headers["Location"].endswith("/espace/")


def test_le_client_voit_ses_devis_sauf_brouillons(espace, mme_martin,
                                                  m_durand):
    ajouter_devis(mme_martin, "D-2026-0001", statut="envoye")
    ajouter_devis(mme_martin, "D-2026-0002", statut="accepte")
    ajouter_devis(mme_martin, "D-2026-0003")  # brouillon
    ajouter_devis(m_durand, "D-2026-0004", statut="envoye")
    page = texte(espace.get("/espace/"))
    assert "D-2026-0001" in page
    assert "D-2026-0002" in page
    assert "D-2026-0003" not in page
    assert "D-2026-0004" not in page
    assert "Mes devis" in page
    assert "Clients" not in page


def test_detail_et_pdf_de_son_devis(espace, mme_martin):
    devis = ajouter_devis(mme_martin, "D-2026-0001", statut="envoye")
    page = texte(espace.get(f"/espace/devis/{devis.id}"))
    assert "Peinture salon" in page
    assert "255,00" in page
    assert "Bon pour accord" in page
    pdf = espace.get(f"/espace/devis/{devis.id}/pdf")
    assert pdf.status_code == 200
    assert pdf.mimetype == "application/pdf"


@pytest.mark.parametrize("chemin", ["", "/pdf"])
def test_pas_acces_aux_devis_des_autres(espace, mme_martin, m_durand,
                                        chemin):
    autre = ajouter_devis(m_durand, "D-2026-0001", statut="envoye")
    brouillon = ajouter_devis(mme_martin, "D-2026-0002")
    for devis in (autre, brouillon):
        reponse = espace.get(f"/espace/devis/{devis.id}{chemin}")
        assert reponse.status_code == 404


@pytest.mark.parametrize("url", ["/", "/devis", "/clients",
                                 "/devis/1/pdf"])
def test_client_n_accede_pas_aux_pages_du_gerant(espace, url):
    reponse = espace.get(url)
    assert reponse.status_code == 302
    assert reponse.headers["Location"].endswith("/espace/")


def test_client_n_accede_pas_a_l_api(espace):
    reponse = espace.get("/api/clients")
    assert reponse.status_code == 403
    assert reponse.get_json() == {"erreur": "Accès réservé au gérant."}


def test_gerant_redirige_hors_de_l_espace_client(client):
    reponse = client.get("/espace/")
    assert reponse.status_code == 302
    assert reponse.headers["Location"].endswith("/devis")


def test_espace_exige_une_connexion(anonyme):
    reponse = anonyme.get("/espace/")
    assert reponse.status_code == 302
    assert "/connexion" in reponse.headers["Location"]


# --- Suppression, commandes ---

def test_supprimer_client_supprime_son_compte(client, mme_martin, compte):
    compte_id = compte.id
    reponse = client.post(f"/clients/{mme_martin.id}/supprimer")
    assert reponse.status_code == 302
    assert db.session.get(Utilisateur, compte_id) is None


def test_creer_gerant_refuse_un_compte_client(app, compte):
    resultat = app.test_cli_runner().invoke(args=[
        "creer-gerant", "martin@example.com",
        "--mot-de-passe", "un-mot-de-passe"])
    assert resultat.exit_code != 0
    assert "compte d'un client" in resultat.output


def test_seed_reset_garde_le_gerant(app, gerant, compte):
    db.session.expunge_all()  # la commande tourne dans sa propre session
    resultat = app.test_cli_runner().invoke(args=["seed", "--reset"])
    assert resultat.exit_code == 0
    comptes = db.session.scalars(db.select(Utilisateur)).all()
    assert [c.email for c in comptes] == [GERANT_EMAIL]
