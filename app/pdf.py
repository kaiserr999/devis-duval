"""Génération du devis en PDF (template Jinja rendu par xhtml2pdf)."""
from datetime import timedelta
from io import BytesIO

from flask import current_app, render_template
from xhtml2pdf import pisa


def nom_fichier(devis):
    return f"devis-{devis.numero}.pdf"


def generer_pdf(devis):
    """Renvoie le PDF du devis (bytes). Lève RuntimeError si échec."""
    config = current_app.config
    validite = config["DEVIS_VALIDITE_JOURS"]
    html = render_template(
        "devis/pdf.html",
        devis=devis,
        entreprise=config["ENTREPRISE"],
        validite_jours=validite,
        valable_jusqu_au=devis.date_creation + timedelta(days=validite),
    )
    sortie = BytesIO()
    resultat = pisa.CreatePDF(html, dest=sortie, encoding="utf-8")
    if resultat.err:
        raise RuntimeError(f"Échec de la génération du PDF {devis.numero}.")
    return sortie.getvalue()
