"""Acceptance tests at the seed CLI / generated-source seam."""
from pathlib import Path
import sqlite3
import subprocess

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "sources" / "generated"


def seed() -> None:
    subprocess.run(["make", "seed"], cwd=ROOT, check=True)


def snapshot() -> dict[str, bytes]:
    return {str(p.relative_to(DATA)): p.read_bytes() for p in DATA.rglob("*") if p.is_file()}


def test_consecutive_rebuilds_are_byte_identical_and_remove_old_data() -> None:
    seed()
    first = snapshot()
    assert {"crm.sqlite", "invoices.csv", "payments.csv", "support.json"} <= first.keys()
    assert any(p.startswith("emails/") for p in first)
    assert any(p.startswith("policies/") for p in first)
    with sqlite3.connect(DATA / "crm.sqlite") as db:
        assert db.execute("SELECT count(*) FROM customers").fetchone()[0] >= 3
        assert db.execute("SELECT count(*) FROM opportunities").fetchone()[0] >= 1
    (DATA / "obsolete.txt").write_text("discard on rebuild")
    seed()
    assert snapshot() == first
