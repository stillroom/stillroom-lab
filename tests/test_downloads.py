"""Read-only download boundary: contained files, proof and permission binding."""
from pathlib import Path

import pytest

from services.artifacts import OUTPUT, generate
from services.query import PermissionContext, QueryResult
from test_proof import result  # noqa: F401 -- shared real-Postgres fixture


@pytest.mark.parametrize('extension', ['md', 'xlsx', 'pptx'])
def test_download_requires_matching_permission_and_preserves_bytes(result: QueryResult, extension: str) -> None:
    from services.downloads import read_artifact

    path = generate(result, OUTPUT / f'{result.query_id}.{extension}')
    try:
        payload = read_artifact(path.name, PermissionContext(role='owner', client_id='CLIENT-1'))
        assert payload == path.read_bytes()
        for permission in [PermissionContext(role='analyst', client_id='CLIENT-1'),
                           PermissionContext(role='owner', client_id='CLIENT-2')]:
            with pytest.raises(ValueError, match='permission'):
                read_artifact(path.name, permission)
    finally:
        path.unlink()


@pytest.mark.parametrize('name', ['../spec.md', '/etc/passwd', 'README.md', 'sub/file.md'])
def test_download_rejects_non_artifact_names(name: str) -> None:
    from services.downloads import read_artifact

    with pytest.raises(ValueError):
        read_artifact(name, PermissionContext(role='owner', client_id='CLIENT-1'))


def test_download_rejects_symlink(result: QueryResult, tmp_path: Path) -> None:
    from services.downloads import read_artifact

    target = tmp_path / 'private.md'
    target.write_text('private')
    link = OUTPUT / f'{result.query_id}.md'
    link.symlink_to(target)
    try:
        with pytest.raises((OSError, ValueError)):
            read_artifact(link.name, PermissionContext(role='owner', client_id='CLIENT-1'))
    finally:
        link.unlink()
