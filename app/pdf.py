"""Génération du devis en PDF (template Jinja rendu par xhtml2pdf)."""
from datetime import timedelta
from io import BytesIO

from flask import Response, current_app, render_template
from xhtml2pdf import pisa


def nom_fichier(devis):
    return f"devis-{devis.numero}.pdf"


def valable_jusqu_au(devis):
    """Date limite de validité du devis (DEVIS_VALIDITE_JOURS)."""
    jours = current_app.config["DEVIS_VALIDITE_JOURS"]
    return devis.date_creation + timedelta(days=jours)


def generer_pdf(devis):
    """Renvoie le PDF du devis (bytes). Lève RuntimeError si échec."""
    config = current_app.config
    html = render_template(
        "devis/pdf.html",
        devis=devis,
        entreprise=config["ENTREPRISE"],
        validite_jours=config["DEVIS_VALIDITE_JOURS"],
        valable_jusqu_au=valable_jusqu_au(devis),
    )
    sortie = BytesIO()
    resultat = pisa.CreatePDF(html, dest=sortie, encoding="utf-8")
    if resultat.err:
        raise RuntimeError(f"Échec de la génération du PDF {devis.numero}.")
    return sortie.getvalue()


def reponse_pdf(devis, apercu=False):
    """Réponse HTTP du PDF : téléchargement, ou affichage si apercu."""
    mode = "inline" if apercu else "attachment"
    return Response(generer_pdf(devis), mimetype="application/pdf", headers={
        "Content-Disposition": f'{mode}; filename="{nom_fichier(devis)}"'})
