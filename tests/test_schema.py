"""Structural validation of each YAML file in isolation. No network access,
no cross-file comparisons (see test_index_consistency.py / test_latest_consistency.py
/ test_upgrade_graph.py for those).
"""
import datetime
import re

import pytest

from releasedata import (
    ARTIFACT_FIELDS,
    KNOWN_COMPONENTS,
    REPO_ROOT,
    RM126X_COMPONENTS,
    iter_component_artifacts,
    load_release_manifests,
    parse_notes_url,
    release_manifest_paths,
)

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
VALID_ORDER_CONSTRAINTS = {"required", "recommended"}
REQUIRES_CONSTRAINT_RE = re.compile(r"^(==|>=|<=|>|<)\s*\S+$")
TRUSTED_ARTIFACT_URL_PREFIX = "https://raw.githubusercontent.com/Ezurio/"


def test_latest_yaml_has_required_fields(latest_data):
    required = {
        "schema_version",
        "latest_release",
        "components",
        "release_manifest",
        "updated_at",
    }
    missing = required - latest_data.keys()
    assert not missing, f"latest.yaml is missing fields: {missing}"


def test_latest_yaml_components_are_known_set(latest_data):
    assert set(latest_data["components"].keys()) == KNOWN_COMPONENTS


def test_latest_yaml_updated_at_is_valid_iso_date_not_in_future(latest_data):
    updated_at = datetime.date.fromisoformat(str(latest_data["updated_at"]))
    assert updated_at <= datetime.date.today()


def test_latest_yaml_release_manifest_is_relative_releases_path(latest_data):
    assert latest_data["release_manifest"].startswith("releases/")
    assert latest_data["release_manifest"].endswith(".yaml")


@pytest.mark.parametrize("path", release_manifest_paths(), ids=lambda p: p.name)
def test_release_manifest_has_required_top_level_fields(path):
    from releasedata import load_yaml

    data = load_yaml(path)
    required = {
        "schema_version",
        "release_version",
        "release_date",
        "notes_url",
        "components",
        "upgrade",
    }
    missing = required - data.keys()
    assert not missing, f"{path.name} is missing fields: {missing}"


@pytest.mark.parametrize("path", release_manifest_paths(), ids=lambda p: p.name)
def test_release_version_matches_filename(path):
    from releasedata import load_yaml

    data = load_yaml(path)
    assert data["release_version"] == path.stem, (
        f"{path.name}: release_version {data['release_version']!r} "
        f"does not match filename"
    )


@pytest.mark.parametrize("path", release_manifest_paths(), ids=lambda p: p.name)
def test_release_date_is_valid_iso_date(path):
    from releasedata import load_yaml

    data = load_yaml(path)
    datetime.date.fromisoformat(str(data["release_date"]))


@pytest.mark.parametrize("path", release_manifest_paths(), ids=lambda p: p.name)
def test_release_components_are_exactly_known_set(path):
    from releasedata import load_yaml

    data = load_yaml(path)
    assert set(data["components"].keys()) == KNOWN_COMPONENTS


@pytest.mark.parametrize("path", release_manifest_paths(), ids=lambda p: p.name)
def test_release_notes_url_is_trusted_and_versioned(path):
    from releasedata import load_yaml

    data = load_yaml(path)
    notes_url = data["notes_url"]
    assert notes_url.startswith(TRUSTED_ARTIFACT_URL_PREFIX), notes_url
    parts = parse_notes_url(notes_url)
    assert parts, (
        f"{path.name}: notes_url must be a raw URL to releases/<version>/"
        f"RELEASE_NOTES.md, got {notes_url!r}"
    )
    assert parts["version"] == data["release_version"], notes_url


@pytest.mark.parametrize("path", release_manifest_paths(), ids=lambda p: p.name)
def test_release_notes_file_exists_in_repo(path):
    notes = REPO_ROOT / "releases" / path.stem / "RELEASE_NOTES.md"
    assert notes.is_file(), f"{path.name}: missing {notes.relative_to(REPO_ROOT)}"


@pytest.mark.parametrize(
    "version,name,component",
    list(iter_component_artifacts()),
    ids=lambda v: v if isinstance(v, str) else "",
)
def test_component_artifact_fields_are_well_formed(version, name, component):
    assert "version" in component, f"{version}/{name} missing 'version'"

    present = [f for f in ARTIFACT_FIELDS if f in component]
    if name in RM126X_COMPONENTS and not present:
        return
    missing = [f for f in ARTIFACT_FIELDS if f not in component]
    assert not missing, (
        f"{version}/{name} missing {missing}"
        + (" (url/sha256/size_bytes are all-or-none)" if name in RM126X_COMPONENTS else "")
    )

    assert component["url"].startswith(TRUSTED_ARTIFACT_URL_PREFIX), (
        f"{version}/{name} url not on trusted host: {component['url']}"
    )
    assert SHA256_RE.match(component["sha256"]), (
        f"{version}/{name} sha256 is not 64 lowercase hex chars: {component['sha256']!r}"
    )
    assert isinstance(component["size_bytes"], int) and component["size_bytes"] > 0, (
        f"{version}/{name} size_bytes must be a positive int: {component['size_bytes']!r}"
    )


@pytest.mark.parametrize("path", release_manifest_paths(), ids=lambda p: p.name)
def test_upgrade_direct_from_is_list_of_strings(path):
    from releasedata import load_yaml

    data = load_yaml(path)
    direct_from = data["upgrade"]["direct_from"]
    assert isinstance(direct_from, list)
    assert all(isinstance(v, str) for v in direct_from)
    assert data["release_version"] not in direct_from, "release cannot upgrade from itself"
    assert len(direct_from) == len(set(direct_from)), "duplicate entries in direct_from"


@pytest.mark.parametrize("path", release_manifest_paths(), ids=lambda p: p.name)
def test_component_order_entries_are_well_formed(path):
    from releasedata import load_yaml

    data = load_yaml(path)
    for entry in data["upgrade"].get("component_order", []):
        assert entry["update"] in KNOWN_COMPONENTS, entry
        assert entry["before"] in KNOWN_COMPONENTS, entry
        assert entry["update"] != entry["before"], entry
        assert entry["constraint"] in VALID_ORDER_CONSTRAINTS, entry
        assert entry.get("reason"), f"{path.name}: component_order entry missing reason: {entry}"


@pytest.mark.parametrize("path", release_manifest_paths(), ids=lambda p: p.name)
def test_requires_entries_are_well_formed(path):
    from releasedata import load_yaml

    data = load_yaml(path)
    requires = data["upgrade"].get("requires", {})
    for component_name, constraint in requires.items():
        assert component_name in KNOWN_COMPONENTS, (
            f"{path.name}: unknown component in requires: {component_name!r}"
        )
        assert REQUIRES_CONSTRAINT_RE.match(constraint), (
            f"{path.name}: requires[{component_name}] is not a valid constraint "
            f"expression: {constraint!r}"
        )


def test_all_release_urls_point_at_the_same_github_repo():
    """The design goal is one public repo serving all release artifacts
    directly, with no intermediary server. If some release's component
    URLs or notes_url point at a different repo (typo, copy-paste from an
    old manifest, renamed repo not updated everywhere), that release's
    files are silently unreachable via this repo's canonical location.
    """
    repo_re = re.compile(r"^https://(?:raw\.githubusercontent\.com|github\.com)/([^/]+/[^/]+)/")
    urls_by_repo = {}

    for path in release_manifest_paths():
        from releasedata import load_yaml

        data = load_yaml(path)
        all_urls = [data["notes_url"]] + [
            c["url"] for c in data["components"].values() if "url" in c
        ]
        for url in all_urls:
            match = repo_re.match(url)
            assert match, f"{path.name}: url does not look like a GitHub URL: {url}"
            urls_by_repo.setdefault(match.group(1), []).append((path.name, url))

    assert len(urls_by_repo) == 1, (
        "release URLs are split across more than one GitHub repo, expected "
        f"exactly one canonical repo: { {repo: [u for _, u in entries[:1]] for repo, entries in urls_by_repo.items()} }"
    )


def test_shared_urls_have_consistent_size_and_hash_across_releases():
    """If two releases point at the same URL (a firmware/app image reused
    unchanged across releases), they must agree on its declared size and
    hash -- otherwise at least one of them is simply wrong.
    """
    by_url = {}
    for version, name, component in iter_component_artifacts():
        if "url" not in component:
            continue
        url = component["url"]
        fingerprint = (component["size_bytes"], component["sha256"])
        by_url.setdefault(url, []).append((version, name, fingerprint))

    inconsistent = {
        url: entries
        for url, entries in by_url.items()
        if len({fp for _, _, fp in entries}) > 1
    }
    assert not inconsistent, (
        "Same URL declared with different size/hash across releases: "
        f"{inconsistent}"
    )
