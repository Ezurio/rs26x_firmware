"""Live network validation: every release artifact URL is reachable and its
actual bytes match the declared size_bytes/sha256, and every notes_url
(raw RELEASE_NOTES.md) resolves.

These tests hit the network and download real files (dozens of MB in
aggregate across all releases). Files referenced by the same URL across
multiple releases are downloaded once and cached for the test session
(see `fetch_url` in conftest.py) rather than re-fetched per release.
"""
import hashlib

import pytest

from releasedata import (
    release_manifest_paths,
    unique_artifacts_by_url,
)


def _artifact_id(url, info):
    label = "+".join(f"{version}:{name}" for version, name in info["releases"])
    return f"{label}:{url.rsplit('/', 1)[-1]}"


UNIQUE_ARTIFACTS = list(unique_artifacts_by_url().items())
UNIQUE_ARTIFACT_IDS = [_artifact_id(url, info) for url, info in UNIQUE_ARTIFACTS]


@pytest.mark.network
@pytest.mark.parametrize("url,info", UNIQUE_ARTIFACTS, ids=UNIQUE_ARTIFACT_IDS)
def test_artifact_matches_declared_size_and_hash(url, info, fetch_url):
    content = fetch_url(url)

    assert len(content) == info["size_bytes"], (
        f"{url}: downloaded {len(content)} bytes, manifest declares "
        f"size_bytes={info['size_bytes']} (referenced by {info['releases']})"
    )

    actual_sha256 = hashlib.sha256(content).hexdigest()
    assert actual_sha256 == info["sha256"], (
        f"{url}: sha256 mismatch, downloaded content hashes to {actual_sha256}, "
        f"manifest declares sha256={info['sha256']} (referenced by {info['releases']})"
    )


@pytest.mark.network
@pytest.mark.parametrize("path", release_manifest_paths(), ids=lambda p: p.name)
def test_notes_url_is_reachable(path, http_session, github_token):
    from releasedata import load_yaml

    notes_url = load_yaml(path)["notes_url"]

    # raw.githubusercontent.com accepts a token header, which is needed
    # while the repo is still private.
    headers = {"Authorization": f"token {github_token}"} if github_token else {}
    response = http_session.get(
        notes_url, headers=headers, timeout=30, allow_redirects=True
    )

    assert response.status_code < 400, (
        f"{notes_url} returned HTTP {response.status_code}"
    )
