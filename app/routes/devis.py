"""Routes des devis et de leurs lignes."""
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from flask import Blueprint, abort, jsonify, request

from app.extensions import db
from app.models import Client, Devis, LigneDevis
from app.models.devis import STATUTS
from app.validation import lire_json

devis_bp = Blueprint("devis", __name__, url_prefix="/api/devis")

# Statuts atteignables depuis chaque statut (pas de retour en arrière)
TRANSITIONS = {
    "brouillon": {"envoye"},
    "envoye": {"accepte", "refuse"},
    "accepte": set(),
    "refuse": set(),
}

# DECIMAL(10, 2) : 8 chiffres avant la virgule au maximum
MONTANT_MAX = Decimal("100000000")


def lire_montant(valeur, nom):
    """Convertit un nombre JSON en Decimal (2 décimales max). Lève 400."""
    if isinstance(valeur, bool) or not isinstance(valeur, (int, float, str)):
        abort(400, description=f"{nom} doit être un nombre.")
    try:
        montant = Decimal(str(valeur).strip())
    except InvalidOperation:
        abort(400, description=f"{nom} doit être un nombre.")
    if not montant.is_finite():
        abort(400, description=f"{nom} doit être un nombre.")
    if montant.as_tuple().exponent < -2:
        abort(400, description=f"{nom} : 2 décimales au maximum.")
    if abs(montant) >= MONTANT_MAX:
        abort(400, description=f"{nom} est trop grand.")
    return montant


def construire_lignes(donnees):
    """Valide la liste 'lignes' et renvoie des LigneDevis. Lève 400."""
    lignes = donnees.get("lignes", [])
    if not isinstance(lignes, list):
        abort(400, description="Le champ 'lignes' doit être une liste.")

    resultat = []
    for numero, ligne in enumerate(lignes, start=1):
        prefixe = f"Ligne {numero}"
        if not isinstance(ligne, dict):
            abort(400, description=f"{prefixe} : objet JSON attendu.")

        description = ligne.get("description")
        if not isinstance(description, str) or not description.strip():
            abort(400, description=f"{prefixe} : la description est "
                                   "obligatoire.")
        description = description.strip()
        if len(description) > 255:
            abort(400, description=f"{prefixe} : la description dépasse "
                                   "255 caractères.")

        if "quantite" not in ligne or "prix_unitaire" not in ligne:
            abort(400, description=f"{prefixe} : 'quantite' et "
                                   "'prix_unitaire' sont obligatoires.")
        quantite = lire_montant(ligne["quantite"], f"{prefixe} : quantite")
        prix = lire_montant(ligne["prix_unitaire"],
                            f"{prefixe} : prix_unitaire")
        if quantite <= 0:
            abort(400, description=f"{prefixe} : la quantité doit être "
                                   "supérieure à 0.")
        if prix < 0:
            abort(400, description=f"{prefixe} : le prix unitaire ne peut "
                                   "pas être négatif.")

        # sous_total envoyé par le client : ignoré, le serveur le calcule
        nouvelle = LigneDevis(description=description, quantite=quantite,
                              prix_unitaire=prix)
        if nouvelle.calculer_sous_total() >= MONTANT_MAX:
            abort(400, description=f"{prefixe} : sous-total trop grand.")
        resultat.append(nouvelle)
    return resultat


def appliquer_lignes(devis, lignes):
    """Remplace les lignes du devis et recalcule le total. Lève 400."""
    devis.lignes = lignes
    if devis.calculer_total() >= MONTANT_MAX:
        abort(400, description="Le total du devis est trop grand.")


def prochain_numero():
    """Génère le numéro suivant de l'année : D-2026-0001, D-2026-0002..."""
    prefixe = f"D-{datetime.now(timezone.utc).year}-"
    numeros = db.session.scalars(
        db.select(Devis.numero).where(Devis.numero.like(prefixe + "%")))
    dernier = 0
    for numero in numeros:
        suffixe = numero[len(prefixe):]
        if suffixe.isdigit():
            dernier = max(dernier, int(suffixe))
    return f"{prefixe}{dernier + 1:04d}"


def trouver_devis(devis_id):
    """Renvoie le devis demandé, ou 404."""
    return db.get_or_404(Devis, devis_id, description="Devis introuvable.")


def exiger_brouillon(devis, action):
    """Lève 409 si le devis n'est plus un brouillon."""
    if devis.statut != "brouillon":
        abort(409, description=f"Seul un devis en brouillon peut être "
                               f"{action} (statut actuel : {devis.statut}).")


@devis_bp.get("")
def lister_devis():
    """Liste les devis, filtrables par ?client_id= et ?statut=."""
    requete = db.select(Devis).order_by(Devis.id)

    client_id = request.args.get("client_id")
    if client_id is not None:
        if not client_id.isdigit():
            abort(400, description="client_id doit être un entier.")
        requete = requete.where(Devis.client_id == int(client_id))

    statut = request.args.get("statut")
    if statut is not None:
        if statut not in STATUTS:
            abort(400, description="Statut inconnu. Valeurs possibles : "
                                   + ", ".join(STATUTS) + ".")
        requete = requete.where(Devis.statut == statut)

    devis = db.session.scalars(requete).all()
    return jsonify([d.to_dict() for d in devis]), 200


@devis_bp.post("")
def creer_devis():
    """Crée un devis en brouillon (numéro et total calculés)."""
    donnees = lire_json()

    client_id = donnees.get("client_id")
    if isinstance(client_id, bool) or not isinstance(client_id, int):
        abort(400, description="Le champ 'client_id' (entier) est "
                               "obligatoire.")
    client = db.session.get(Client, client_id)
    if client is None:
        abort(400, description="Le client indiqué n'existe pas.")

    # numero, statut et total envoyés par le client sont ignorés.
    # Le devis n'est rattaché au client qu'une fois les lignes validées.
    devis = Devis(numero=prochain_numero(), statut="brouillon")
    appliquer_lignes(devis, construire_lignes(donnees))
    devis.client = client
    db.session.add(devis)
    db.session.commit()
    return jsonify(devis.to_dict()), 201


@devis_bp.get("/<int:devis_id>")
def voir_devis(devis_id):
    """Renvoie un devis avec ses lignes."""
    return jsonify(trouver_devis(devis_id).to_dict()), 200


@devis_bp.put("/<int:devis_id>")
def modifier_devis(devis_id):
    """Remplace les lignes d'un devis en brouillon."""
    devis = trouver_devis(devis_id)
    exiger_brouillon(devis, "modifié")
    donnees = lire_json()
    if "lignes" not in donnees:
        abort(400, description="Le champ 'lignes' est obligatoire.")
    appliquer_lignes(devis, construire_lignes(donnees))
    db.session.commit()
    return jsonify(devis.to_dict()), 200


@devis_bp.patch("/<int:devis_id>/statut")
def changer_statut(devis_id):
    """Fait avancer le statut : brouillon -> envoye -> accepte/refuse."""
    devis = trouver_devis(devis_id)
    nouveau = lire_json().get("statut")
    if nouveau not in STATUTS:
        abort(400, description="Statut inconnu. Valeurs possibles : "
                               + ", ".join(STATUTS) + ".")
    if nouveau not in TRANSITIONS[devis.statut]:
        abort(409, description=f"Passage de '{devis.statut}' à "
                               f"'{nouveau}' interdit.")
    if nouveau == "envoye" and not devis.lignes:
        abort(409, description="Impossible d'envoyer un devis sans ligne.")
    devis.statut = nouveau
    db.session.commit()
    return jsonify(devis.to_dict()), 200


@devis_bp.delete("/<int:devis_id>")
def supprimer_devis(devis_id):
    """Supprime un devis en brouillon (ses lignes partent avec lui)."""
    devis = trouver_devis(devis_id)
    exiger_brouillon(devis, "supprimé")
    db.session.delete(devis)
    db.session.commit()
    return "", 204
