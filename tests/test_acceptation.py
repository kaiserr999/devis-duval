"""Tests de l'acceptation / du refus d'un devis par le client, en ligne."""
from datetime import datetime, timedelta, timezone

import pytest
from flask import g, render_template

from app.extensions import db
from app.pdf import generer_pdf
from tests.conftest import GERANT_EMAIL
from tests.test_espace_client import ajouter_devis, compte, corps, \
    emails, espace, m_durand, mme_martin, texte  # noqa: F401  (fixtures)


@pytest.fixture
def envoye(mme_martin):  # noqa: F811
    return ajouter_devis(mme_martin, "D-2026-0001", statut="envoye")


def repondre(navigateur, devis, decision, accord=True):
    donnees = {"decision": decision}
    if accord:
        donnees["accord"] = "1"
    return navigateur.post(f"/espace/devis/{devis.id}/reponse", data=donnees,
                           follow_redirects=True)


# --- Affichage ---

def test_boutons_sur_un_devis_envoye(espace, envoye):  # noqa: F811
    page = texte(espace.get(f"/espace/devis/{envoye.id}"))
    assert "Votre réponse" in page
    assert "Accepter le devis" in page
    assert "Refuser le devis" in page


def test_accueil_signale_les_devis_en_attente(espace, envoye):  # noqa: F811
    page = texte(espace.get("/espace/"))
    assert "1 devis attend votre réponse" in page


def test_pas_de_boutons_une_fois_repondu(espace, mme_martin):  # noqa: F811
    devis = ajouter_devis(mme_martin, "D-2026-0001", statut="accepte")
    page = texte(espace.get(f"/espace/devis/{devis.id}"))
    assert "Accepter le devis" not in page


# --- Accepter / refuser ---

def test_accepter_en_ligne(app, espace, gerant, envoye):  # noqa: F811
    reponse = repondre(espace, envoye, "accepte")
    assert "Votre accord pour le devis D-2026-0001 est enregistré" \
        in texte(reponse)
    assert envoye.statut == "accepte"
    assert envoye.reponse_en_ligne_le is not None
    assert "Vous avez accepté ce devis en ligne" in texte(reponse)

    [message] = emails(app)
    assert message["To"] == GERANT_EMAIL
    assert "D-2026-0001 accepté par Mme Martin" in message["Subject"]
    assert f"/devis/{envoye.id}" in corps(message)


def test_refuser_en_ligne(app, espace, gerant, envoye):  # noqa: F811
    reponse = repondre(espace, envoye, "refuse", accord=False)
    assert "Votre refus du devis D-2026-0001 est enregistré" \
        in texte(reponse)
    assert envoye.statut == "refuse"
    [message] = emails(app)
    assert "refusé" in message["Subject"]


def test_accepter_sans_cocher_bon_pour_accord(espace, envoye):  # noqa: F811
    reponse = repondre(espace, envoye, "accepte", accord=False)
    assert "Cochez la case" in texte(reponse)
    assert envoye.statut == "envoye"
    assert envoye.reponse_en_ligne_le is None


def test_reponse_inconnue(espace, envoye):  # noqa: F811
    reponse = repondre(espace, envoye, "brouillon")
    assert reponse.status_code == 400
    assert envoye.statut == "envoye"


def test_pas_de_seconde_reponse(espace, envoye):  # noqa: F811
    repondre(espace, envoye, "accepte")
    reponse = repondre(espace, envoye, "refuse")
    assert "déjà reçu une réponse" in texte(reponse)
    assert envoye.statut == "accepte"


def test_devis_expire_ne_peut_plus_etre_accepte(espace, envoye):  # noqa: F811
    envoye.date_creation = datetime.now(timezone.utc) - timedelta(days=31)
    db.session.commit()
    page = texte(espace.get(f"/espace/devis/{envoye.id}"))
    assert "Ce devis a expiré" in page
    assert "Accepter le devis" not in page
    assert "attend votre réponse" not in texte(espace.get("/espace/"))
    reponse = repondre(espace, envoye, "accepte")
    assert "a expiré" in texte(reponse)
    assert envoye.statut == "envoye"


def test_pas_de_reponse_pour_le_devis_d_un_autre(espace, m_durand):  # noqa
    autre = ajouter_devis(m_durand, "D-2026-0002", statut="envoye")
    reponse = espace.post(f"/espace/devis/{autre.id}/reponse",
                          data={"decision": "accepte", "accord": "1"})
    assert reponse.status_code == 404
    assert autre.statut == "envoye"


def test_le_gerant_ne_repond_pas_a_la_place_du_client(client, envoye):  # noqa
    reponse = client.post(f"/espace/devis/{envoye.id}/reponse",
                          data={"decision": "accepte", "accord": "1"})
    assert reponse.status_code == 302
    assert envoye.statut == "envoye"


def test_echec_email_au_gerant_garde_la_reponse(espace, gerant, envoye,  # noqa
                                                monkeypatch):
    def refuser(message):
        raise OSError("serveur injoignable")
    monkeypatch.setattr("app.notifications.envoyer", refuser)
    reponse = repondre(espace, envoye, "accepte")
    assert reponse.status_code == 200
    assert envoye.statut == "accepte"


# --- Côté gérant ---

def test_le_gerant_voit_la_reponse_en_ligne(client, espace, envoye):  # noqa
    repondre(espace, envoye, "accepte")
    # Les tests partagent un contexte d'application : on oublie
    # l'utilisateur de la requête précédente (le client)
    g.pop("_login_user", None)
    page = texte(client.get(f"/devis/{envoye.id}"))
    assert "accepté en ligne" in page
    assert envoye.to_dict()["reponse_en_ligne_le"] is not None


def test_reponse_saisie_par_le_gerant_n_est_pas_en_ligne(client,  # noqa
                                                         envoye):
    client.post(f"/devis/{envoye.id}/statut", data={"statut": "accepte"})
    assert envoye.statut == "accepte"
    assert envoye.reponse_en_ligne_le is None
    assert "en ligne" not in texte(client.get(f"/devis/{envoye.id}"))


def test_pdf_mentionne_l_acceptation_en_ligne(espace, envoye):  # noqa
    repondre(espace, envoye, "accepte")
    assert generer_pdf(envoye).startswith(b"%PDF")
    html = render_template("devis/pdf.html", devis=envoye,
                           entreprise={}, validite_jours=30,
                           valable_jusqu_au=envoye.date_creation)
    assert "Accepté en ligne le" in html
