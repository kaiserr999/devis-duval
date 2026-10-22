#!/bin/sh
# Démarrage du conteneur : migrations, données de démo et compte du gérant
# (optionnels), puis serveur gunicorn.
set -e

flask db upgrade

# SEED_DEMO=1 : insère les clients et devis de démonstration si la base
# est vide (ne touche à rien sinon)
if [ "$SEED_DEMO" = "1" ]; then
    flask seed
fi

# Crée le compte du gérant, ou remet son mot de passe, à partir des
# variables d'environnement (jamais écrites dans le dépôt)
if [ -n "$GERANT_EMAIL" ] && [ -n "$GERANT_MOT_DE_PASSE" ]; then
    flask creer-gerant "$GERANT_EMAIL" --mot-de-passe "$GERANT_MOT_DE_PASSE"
fi

# PORT est fourni par l'hébergeur (Render), 5000 en local
exec gunicorn --bind "0.0.0.0:${PORT:-5000}" --workers 2 \
    --access-logfile - run:app
