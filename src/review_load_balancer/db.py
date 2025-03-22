import os
from contextlib import contextmanager
from pathlib import Path

import psycopg2

SCHEMA = "review_load_balancer"


def get_database_url() -> str:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is not set. Provide a production database URL.")
    return database_url


@contextmanager
def db_cursor():
    conn = psycopg2.connect(get_database_url())
    try:
        with conn.cursor() as cursor:
            yield cursor
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def load_sql(path: Path) -> str:
    return path.read_text(encoding="utf-8")
