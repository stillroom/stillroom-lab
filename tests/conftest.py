"""Real Postgres fixtures; no SQLite substitute and no source regeneration."""
from collections.abc import Iterator
from pathlib import Path
import subprocess
from uuid import uuid4

import psycopg
from psycopg import sql
import pytest

from services.store import Store, DSN

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def store() -> Iterator[Store]:
    subprocess.run(["docker", "compose", "up", "-d", "--wait", "--wait-timeout", "90"],
                   cwd=ROOT, check=True, capture_output=True, timeout=180)
    schema = "test_" + uuid4().hex
    result = Store(schema=schema)
    try:
        yield result
    finally:
        with psycopg.connect(DSN) as conn:
            conn.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))
