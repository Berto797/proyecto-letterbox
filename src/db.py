import os

import psycopg
from dotenv import load_dotenv
from psycopg.rows import TupleRow

load_dotenv()


def open_connection() -> psycopg.Connection[TupleRow]:
    """Abre una conexión con PostgreSQL usando las variables de entorno POSTGRES_*"""
    return psycopg.connect(
        host=os.environ["POSTGRES_HOST"],
        port=os.environ["POSTGRES_PORT"],
        dbname=os.environ["POSTGRES_DB"],
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
    )
