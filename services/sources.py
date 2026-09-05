"""Fixed read-only adapters. Email/policy bodies are inert source data."""
import csv
from datetime import date
from email import policy
from email.parser import Parser
import hashlib
import io
import json
from pathlib import Path
import sqlite3
from typing import Any

import yaml

from services.mapping import Family
from services.ontology import StrictModel

SOURCE_ROOT = Path(__file__).resolve().parents[1] / "sources/generated"
# Ticket-01's fixed observation date, documented in sources/MESSINESS.md.
FIXTURE_OBSERVED_AT = date(2026, 9, 1)


class SourceRow(StrictModel):
    dataset: str
    values: dict[str, Any]
    locator: str
    content_digest: str


def read_bytes(path: Path) -> bytes:
    if not path.resolve().is_relative_to(SOURCE_ROOT) or SOURCE_ROOT.is_symlink():
        raise ValueError("Source path escapes the generated fixture directory")
    return path.read_bytes()


def read_family(family: Family) -> list[SourceRow]:
    result: list[SourceRow] = []

    def add(dataset: str, values: dict[str, Any], path: Path, raw: bytes) -> None:
        result.append(SourceRow(dataset=dataset, values=values,
                                locator=str(path.relative_to(SOURCE_ROOT)),
                                content_digest=hashlib.sha256(raw).hexdigest()))

    if family == "crm":
        path = SOURCE_ROOT / "crm.sqlite"
        raw = read_bytes(path)
        # Query the exact captured bytes, without opening the source for writing,
        # creating a journal, or racing a second read of the original file.
        with sqlite3.connect(":memory:") as db:
            db.deserialize(raw)
            db.execute("PRAGMA query_only=ON")
            db.row_factory = sqlite3.Row
            for dataset in ("customers", "opportunities"):
                for row in db.execute(f"SELECT * FROM {dataset} ORDER BY id"):
                    add(dataset, dict(row), path, raw)
    elif family == "billing":
        for dataset in ("invoices", "payments"):
            path = SOURCE_ROOT / f"{dataset}.csv"
            raw = read_bytes(path)
            for row in csv.DictReader(io.StringIO(raw.decode("utf-8"))):
                add(dataset, dict(row), path, raw)
    elif family == "support":
        path = SOURCE_ROOT / "support.json"
        raw = read_bytes(path)
        for row in json.loads(raw):
            add("tickets", row, path, raw)
    elif family == "email":
        for path in sorted((SOURCE_ROOT / "emails").glob("*.txt")):
            raw = read_bytes(path)
            message = Parser(policy=policy.default).parsestr(raw.decode("utf-8"))
            values = dict(message.items())
            values["body"] = message.get_payload()
            add("messages", values, path, raw)
    elif family == "policy":
        for path in sorted((SOURCE_ROOT / "policies").glob("*.md")):
            raw = read_bytes(path)
            _, frontmatter, body = raw.decode("utf-8").split("---", 2)
            values = yaml.safe_load(frontmatter)
            values["body"] = body
            add("documents", values, path, raw)
    return result
