"""Cross-checks between latest.yaml and both the release index and the
release manifest it points to.
"""
from releasedata import KNOWN_COMPONENTS, load_release_manifests


def test_latest_release_exists_in_index(latest_data, index_data):
    index_versions = {r["version"] for r in index_data["releases"]}
    assert latest_data["latest_release"] in index_versions


def test_latest_release_is_the_last_entry_in_index(latest_data, index_data):
    """index.yaml's list order is the canonical chronological release order
    (see test_upgrade_graph.py); "latest" should be the newest, i.e. the
    last entry.
    """
    last_index_version = index_data["releases"][-1]["version"]
    assert latest_data["latest_release"] == last_index_version


def test_latest_release_manifest_path_matches_latest_release(latest_data):
    expected = f"releases/{latest_data['latest_release']}.yaml"
    assert latest_data["release_manifest"] == expected


def test_latest_release_manifest_file_agrees_on_release_version(latest_data):
    manifests = load_release_manifests()
    manifest = manifests[latest_data["latest_release"]]["data"]
    assert manifest["release_version"] == latest_data["latest_release"]


def test_latest_components_match_release_manifest_components(latest_data):
    manifests = load_release_manifests()
    manifest = manifests[latest_data["latest_release"]]["data"]

    mismatches = []
    for component_name in KNOWN_COMPONENTS:
        latest_version = latest_data["components"].get(component_name)
        manifest_version = manifest["components"][component_name]["version"]
        if latest_version != manifest_version:
            mismatches.append(
                f"{component_name}: latest.yaml says {latest_version!r}, "
                f"manifest says {manifest_version!r}"
            )
    assert not mismatches, "\n".join(mismatches)


def test_latest_components_match_index_entry(latest_data, index_data):
    index_entry = next(
        r for r in index_data["releases"] if r["version"] == latest_data["latest_release"]
    )

    mismatches = []
    for component_name in KNOWN_COMPONENTS:
        latest_version = latest_data["components"].get(component_name)
        index_version = index_entry["components"].get(component_name)
        if latest_version != index_version:
            mismatches.append(
                f"{component_name}: latest.yaml says {latest_version!r}, "
                f"index.yaml says {index_version!r}"
            )
    assert not mismatches, "\n".join(mismatches)
