import os
from contextlib import contextmanager
from pathlib import Path

import psycopg2
from psycopg2.extras import RealDictCursor

SCHEMA = "review_load_balancer"


def get_database_url() -> str:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is not set. Provide a production database URL.")
    return database_url


@contextmanager
def db_cursor(dict_rows: bool = True):
    conn = psycopg2.connect(get_database_url())
    try:
        cursor_factory = RealDictCursor if dict_rows else None
        with conn.cursor(cursor_factory=cursor_factory) as cursor:
            cursor.execute(f"SET search_path TO {SCHEMA};")
            yield cursor
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def load_sql(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def run_sql(path: Path) -> None:
    with db_cursor(dict_rows=False) as cursor:
        cursor.execute(load_sql(path))
