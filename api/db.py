import psycopg2
import psycopg2.extras
from contextlib import contextmanager
from decimal import Decimal
from flask import current_app
import json


class DecimalEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, Decimal):
            return float(o)
        return super().default(o)


@contextmanager
def get_db():
    """Fournit une connexion PostgreSQL et la ferme proprement."""
    conn = psycopg2.connect(current_app.config["DATABASE_URL"])
    try:
        yield conn
    finally:
        conn.close()


def _cast_row(row):
    """Convertit les Decimal en float dans un dict."""
    if row is None:
        return None
    return {k: float(v) if isinstance(v, Decimal) else v for k, v in row.items()}


def query(sql, params=None, fetchone=False):
    """Exécute une requête SELECT et retourne les résultats en dict."""
    with get_db() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params or ())
            if fetchone:
                return _cast_row(cur.fetchone())
            return [_cast_row(r) for r in cur.fetchall()]


def execute(sql, params=None):
    """Exécute une requête INSERT/UPDATE/DELETE."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params or ())
        conn.commit()
