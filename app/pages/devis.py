"""Pages des devis : liste, détail, création, modification, statut."""
from flask import Response, flash, redirect, render_template, request, \
    url_for

from app.extensions import db
from app.models import Client, Devis
from app.models.devis import STATUTS
from app.pages import LIBELLES_STATUT, essayer, nombre, pages_bp
from app.pdf import generer_pdf, nom_fichier
from app.routes.devis import TRANSITIONS, appliquer_lignes, \
    appliquer_statut, construire_lignes, nouveau_devis, trouver_devis

# Texte des boutons qui font avancer le statut
ACTIONS_STATUT = {
    "envoye": "Marquer comme envoyé",
    "accepte": "Accepté par le client",
    "refuse": "Refusé par le client",
}


def nombre_saisi(texte):
    """'1 200,50' -> '1200.50' : accepte la virgule et les espaces."""
    return texte.replace(" ", "").replace(" ", "") \
        .replace(" ", "").replace(",", ".")


def lignes_du_formulaire():
    """Lit les colonnes du tableau de lignes. Les lignes vides sont
    ignorées ; les montants restent en texte (validés par l'API)."""
    colonnes = zip(request.form.getlist("description"),
                   request.form.getlist("quantite"),
                   request.form.getlist("prix_unitaire"))
    lignes = []
    for description, quantite, prix in colonnes:
        if not (description.strip() or quantite.strip() or prix.strip()):
            continue
        ligne = {"description": description}
        if quantite.strip():
            ligne["quantite"] = nombre_saisi(quantite)
        if prix.strip():
            ligne["prix_unitaire"] = nombre_saisi(prix)
        lignes.append(ligne)
    return lignes


def formulaire(devis=None, client_id=None, lignes=None, erreur=None):
    """Affiche le formulaire devis (création si devis est None)."""
    if lignes is None:
        # Quantité sans zéros inutiles (30.00 -> 30) ; le template affiche
        # ensuite les montants avec une virgule
        lignes = [{"description": ligne.description,
                   "quantite": nombre(ligne.quantite),
                   "prix_unitaire": f"{ligne.prix_unitaire:.2f}"}
                  for ligne in devis.lignes] if devis else []
    clients = db.session.scalars(
        db.select(Client).order_by(Client.nom, Client.id)).all()
    statut_http = 400 if erreur else 200
    return render_template("devis/formulaire.html", devis=devis,
                           clients=clients, client_id=client_id,
                           lignes=lignes, erreur=erreur), statut_http


@pages_bp.get("/devis")
def liste_devis():
    statut = request.args.get("statut")
    if statut not in STATUTS:
        statut = None
    requete = db.select(Devis).order_by(Devis.id.desc())
    if statut:
        requete = requete.where(Devis.statut == statut)
    return render_template("devis/liste.html",
                           devis=db.session.scalars(requete).all(),
                           statut=statut, statuts=STATUTS)


@pages_bp.route("/devis/nouveau", methods=["GET", "POST"])
def creer_devis():
    if request.method == "GET":
        return formulaire(client_id=request.args.get("client_id", type=int))

    lignes = lignes_du_formulaire()
    client_id = request.form.get("client_id", type=int)
    client = db.session.get(Client, client_id) if client_id else None
    if client is None:
        return formulaire(client_id=client_id, lignes=lignes,
                          erreur="Choisissez un client.")
    devis, erreur = essayer(nouveau_devis, client, {"lignes": lignes})
    if erreur:
        return formulaire(client_id=client_id, lignes=lignes, erreur=erreur)
    flash(f"Devis {devis.numero} créé en brouillon.", "succes")
    return redirect(url_for("pages.detail_devis", devis_id=devis.id))


@pages_bp.get("/devis/<int:devis_id>")
def detail_devis(devis_id):
    devis = trouver_devis(devis_id)
    actions = {statut: ACTIONS_STATUT[statut]
               for statut in sorted(TRANSITIONS[devis.statut])}
    return render_template("devis/detail.html", devis=devis,
                           actions=actions)


@pages_bp.get("/devis/<int:devis_id>/pdf")
def pdf_devis(devis_id):
    """Télécharge le devis en PDF (?apercu=1 : l'ouvre dans le navigateur)."""
    devis = trouver_devis(devis_id)
    mode = "inline" if request.args.get("apercu") else "attachment"
    return Response(generer_pdf(devis), mimetype="application/pdf", headers={
        "Content-Disposition": f'{mode}; filename="{nom_fichier(devis)}"'})


def exiger_brouillon(devis):
    """Redirige vers le détail si le devis n'est plus modifiable."""
    if devis.statut != "brouillon":
        flash("Seul un devis en brouillon peut être modifié ou supprimé.",
              "erreur")
        return redirect(url_for("pages.detail_devis", devis_id=devis.id))
    return None


@pages_bp.route("/devis/<int:devis_id>/modifier", methods=["GET", "POST"])
def modifier_devis(devis_id):
    devis = trouver_devis(devis_id)
    refus = exiger_brouillon(devis)
    if refus:
        return refus
    if request.method == "GET":
        return formulaire(devis)

    lignes = lignes_du_formulaire()

    def remplacer_lignes():
        appliquer_lignes(devis, construire_lignes({"lignes": lignes}))
        db.session.commit()
    _, erreur = essayer(remplacer_lignes)
    if erreur:
        return formulaire(devis, lignes=lignes, erreur=erreur)
    flash("Devis modifié.", "succes")
    return redirect(url_for("pages.detail_devis", devis_id=devis.id))


@pages_bp.post("/devis/<int:devis_id>/statut")
def changer_statut(devis_id):
    devis = trouver_devis(devis_id)
    nouveau = request.form.get("statut")
    _, erreur = essayer(appliquer_statut, devis, nouveau)
    if erreur:
        flash(erreur, "erreur")
    else:
        flash(f"Devis {devis.numero} : statut "
              f"« {LIBELLES_STATUT[nouveau]} ».", "succes")
    return redirect(url_for("pages.detail_devis", devis_id=devis_id))


@pages_bp.post("/devis/<int:devis_id>/supprimer")
def supprimer_devis(devis_id):
    devis = trouver_devis(devis_id)
    refus = exiger_brouillon(devis)
    if refus:
        return refus
    numero = devis.numero
    db.session.delete(devis)
    db.session.commit()
    flash(f"Devis {numero} supprimé.", "succes")
    return redirect(url_for("pages.liste_devis"))
