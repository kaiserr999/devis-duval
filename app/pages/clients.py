"""Pages des clients : liste, fiche, création, modification, suppression."""
from flask import flash, redirect, render_template, request, url_for

from app.extensions import db
from app.models import Client, Devis
from app.notifications import inviter_client
from app.pages import essayer, pages_bp
from app.routes.clients import CHAMPS, supprimer, trouver_client, \
    valider_client


def formulaire(client=None, valeurs=None, erreur=None):
    """Affiche le formulaire client (création si client est None)."""
    if valeurs is None:
        valeurs = {champ: getattr(client, champ, None) or ""
                   for champ in CHAMPS}
    statut_http = 400 if erreur else 200
    return render_template("clients/formulaire.html", client=client,
                           valeurs=valeurs, erreur=erreur), statut_http


def lire_formulaire():
    """Renvoie (champs validés, None) ou (None, message d'erreur)."""
    return essayer(valider_client, request.form.to_dict())


@pages_bp.get("/clients")
def liste_clients():
    clients = db.session.scalars(
        db.select(Client).order_by(Client.nom, Client.id)).all()
    return render_template("clients/liste.html", clients=clients)


@pages_bp.route("/clients/nouveau", methods=["GET", "POST"])
def nouveau_client():
    if request.method == "GET":
        return formulaire()
    champs, erreur = lire_formulaire()
    if erreur:
        return formulaire(valeurs=request.form, erreur=erreur)
    client = Client(**champs)
    db.session.add(client)
    db.session.commit()
    flash(f"Client « {client.nom} » créé.", "succes")
    return redirect(url_for("pages.fiche_client", client_id=client.id))


@pages_bp.get("/clients/<int:client_id>")
def fiche_client(client_id):
    client = trouver_client(client_id)
    devis = db.session.scalars(
        db.select(Devis).where(Devis.client_id == client.id)
        .order_by(Devis.id.desc())).all()
    return render_template("clients/fiche.html", client=client, devis=devis)


@pages_bp.route("/clients/<int:client_id>/modifier",
                methods=["GET", "POST"])
def modifier_client(client_id):
    client = trouver_client(client_id)
    if request.method == "GET":
        return formulaire(client)
    champs, erreur = lire_formulaire()
    if erreur:
        return formulaire(client, valeurs=request.form, erreur=erreur)
    for champ, valeur in champs.items():
        setattr(client, champ, valeur)
    db.session.commit()
    flash("Client modifié.", "succes")
    return redirect(url_for("pages.fiche_client", client_id=client.id))


@pages_bp.post("/clients/<int:client_id>/inviter")
def inviter(client_id):
    """Envoie (ou renvoie) au client le lien de création de son espace."""
    client = trouver_client(client_id)
    if client.compte is not None:
        flash(f"{client.nom} a déjà un compte client.", "info")
    else:
        flash(*inviter_client(client).message())
    return redirect(url_for("pages.fiche_client", client_id=client.id))


@pages_bp.post("/clients/<int:client_id>/supprimer")
def supprimer_client(client_id):
    client = trouver_client(client_id)
    nom = client.nom
    _, erreur = essayer(supprimer, client)
    if erreur:
        flash(erreur, "erreur")
        return redirect(url_for("pages.fiche_client", client_id=client_id))
    flash(f"Client « {nom} » supprimé.", "succes")
    return redirect(url_for("pages.liste_clients"))
