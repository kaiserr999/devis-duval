"""Tests de l'export PDF des devis."""
from decimal import Decimal
from io import BytesIO

import pytest
from pypdf import PdfReader

from app.extensions import db
from app.models import Client, Devis, LigneDevis


@pytest.fixture
def devis(app):
    client = Client(nom="Mme Martin", adresse="3 rue Haute, 69003 Lyon",
                    email="martin@example.com")
    devis = Devis(numero="D-2026-0007", statut="envoye", client=client)
    devis.lignes = [
        LigneDevis(description="Peinture salon (m²)",
                   quantite=Decimal("42"), prix_unitaire=Decimal("18.50")),
        LigneDevis(description="Préparation des murs",
                   quantite=Decimal("1"), prix_unitaire=Decimal("1200")),
    ]
    devis.calculer_total()
    db.session.add(devis)
    db.session.commit()
    return devis


def texte_pdf(contenu):
    """Texte du PDF, espaces insécables ramenées à des espaces simples."""
    pages = PdfReader(BytesIO(contenu)).pages
    texte = "\n".join(page.extract_text() for page in pages)
    return texte.replace(" ", " ")


def test_telecharger_pdf(client, devis):
    reponse = client.get(f"/devis/{devis.id}/pdf")
    assert reponse.status_code == 200
    assert reponse.mimetype == "application/pdf"
    assert reponse.headers["Content-Disposition"] == \
        'attachment; filename="devis-D-2026-0007.pdf"'
    assert reponse.data.startswith(b"%PDF")


def test_apercu_pdf_dans_le_navigateur(client, devis):
    reponse = client.get(f"/devis/{devis.id}/pdf?apercu=1")
    assert reponse.headers["Content-Disposition"].startswith("inline;")


def test_contenu_du_pdf(client, devis):
    texte = texte_pdf(client.get(f"/devis/{devis.id}/pdf").data)
    for attendu in ["SARL Peinture Duval", "D-2026-0007", "Mme Martin",
                    "3 rue Haute, 69003 Lyon", "Peinture salon (m²)",
                    "Préparation des murs", "777,00 €", "1 977,00 €",
                    "Bon pour accord"]:
        assert attendu in texte, attendu
    assert "BROUILLON" not in texte


def test_pdf_brouillon_marque_provisoire(client, devis):
    devis.statut = "brouillon"
    db.session.commit()
    texte = texte_pdf(client.get(f"/devis/{devis.id}/pdf").data)
    assert "BROUILLON" in texte


def test_pdf_devis_sans_ligne(client, devis):
    devis.lignes = []
    devis.calculer_total()
    db.session.commit()
    texte = texte_pdf(client.get(f"/devis/{devis.id}/pdf").data)
    assert "Aucune ligne." in texte


def test_pdf_long_sur_plusieurs_pages(client, devis):
    devis.lignes = [LigneDevis(description=f"Poste {numero}",
                               quantite=Decimal("1"),
                               prix_unitaire=Decimal("10"))
                    for numero in range(1, 61)]
    devis.calculer_total()
    db.session.commit()
    contenu = client.get(f"/devis/{devis.id}/pdf").data
    assert len(PdfReader(BytesIO(contenu)).pages) >= 2
    texte = texte_pdf(contenu)
    assert "Poste 60" in texte
    assert "600,00 €" in texte
    # En-tête du tableau répété sur chaque page
    assert texte.count("Prix unitaire") >= 2


def test_pdf_devis_inexistant(client):
    assert client.get("/devis/999/pdf").status_code == 404


def test_bouton_pdf_sur_le_detail(client, devis):
    page = client.get(f"/devis/{devis.id}").get_data(as_text=True)
    assert f"/devis/{devis.id}/pdf" in page
