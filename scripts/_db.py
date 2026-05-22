"""Connexion PostgreSQL partagée."""
import os
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).parent.parent / ".env")


def get_conn():
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        raise EnvironmentError("DATABASE_URL manquant dans .env")
    return psycopg2.connect(dsn)
