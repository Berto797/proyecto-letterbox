import os

import psycopg
from psycopg.rows import TupleRow


def open_connection() -> psycopg.Connection[TupleRow]:
    """Abre una conexión con PostgreSQL usando las variables de entorno POSTGRES_*.

    Los datos de conexión se leen de POSTGRES_HOST, POSTGRES_PORT,
    POSTGRES_DB, POSTGRES_USER y POSTGRES_PASSWORD. Esta función no
    carga el archivo .env: las variables tienen que estar ya en el
    entorno (main.py las carga al ejecutarse).

    Returns:
        Conexión abierta que devuelve las filas como tuplas. Conviene
        usarla en un bloque with, que hace commit al salir sin errores
        (o rollback si hay una excepción) y cierra la conexión.

    Raises:
        KeyError: Si falta alguna de las variables POSTGRES_*.
        psycopg.OperationalError: Si no se puede conectar con PostgreSQL.
    """
    return psycopg.connect(
        host=os.environ["POSTGRES_HOST"],
        port=os.environ["POSTGRES_PORT"],
        dbname=os.environ["POSTGRES_DB"],
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
    )
