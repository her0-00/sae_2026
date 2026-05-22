import psycopg2
import psycopg2.extras
from contextlib import contextmanager
from flask import current_app


@contextmanager
def get_db():
    """Fournit une connexion PostgreSQL et la ferme proprement."""
    conn = psycopg2.connect(current_app.config["DATABASE_URL"])
    try:
        yield conn
    finally:
        conn.close()


def query(sql, params=None, fetchone=False):
    """Exécute une requête SELECT et retourne les résultats en dict."""
    with get_db() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params or ())
            if fetchone:
                return cur.fetchone()
            return cur.fetchall()


def execute(sql, params=None):
    """Exécute une requête INSERT/UPDATE/DELETE."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params or ())
        conn.commit()
