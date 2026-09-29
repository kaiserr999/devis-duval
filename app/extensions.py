"""Extensions Flask partagées."""
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import event
from sqlalchemy.engine import Engine

db = SQLAlchemy()


@event.listens_for(Engine, "connect")
def activer_cles_etrangeres_sqlite(dbapi_connection, connection_record):
    """Active les clés étrangères sur SQLite (nécessaire pour ON DELETE)."""
    if dbapi_connection.__class__.__module__.startswith("sqlite3"):
        curseur = dbapi_connection.cursor()
        curseur.execute("PRAGMA foreign_keys=ON")
        curseur.close()
