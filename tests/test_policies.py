"""Read policy files as vault documents, not as application internals."""
import re

import yaml

from test_seed import DATA, seed


def test_policies_have_frontmatter_and_resolving_wikilinks() -> None:
    seed()
    files = list((DATA / "policies").glob("*.md"))
    assert files
    for path in files:
        text = path.read_text()
        assert text.startswith("---\n")
        _, header, body = text.split("---", 2)
        metadata = yaml.safe_load(header)
        assert isinstance(metadata, dict)
        assert {"id", "created", "owner", "status", "related"} <= metadata.keys()
        assert metadata["status"] == "mock"
        links = re.findall(r"\[\[([^\]]+)\]\]", text)
        assert links
        assert body.strip()
        for link in links:
            assert (path.parent / f"{link}.md").is_file()
