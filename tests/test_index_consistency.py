"""Cross-checks between releases/index.yaml and the individual release manifests
it summarizes.
"""
from releasedata import KNOWN_COMPONENTS, load_release_manifests


def test_index_has_no_duplicate_versions(index_data):
    versions = [r["version"] for r in index_data["releases"]]
    assert len(versions) == len(set(versions)), f"duplicate versions in index: {versions}"


def test_every_release_manifest_has_an_index_entry(index_data):
    manifest_versions = set(load_release_manifests().keys())
    index_versions = {r["version"] for r in index_data["releases"]}
    orphans = manifest_versions - index_versions
    assert not orphans, f"release manifest(s) missing from index.yaml: {orphans}"


def test_every_index_entry_has_a_release_manifest(index_data):
    manifest_versions = set(load_release_manifests().keys())
    index_versions = {r["version"] for r in index_data["releases"]}
    dangling = index_versions - manifest_versions
    assert not dangling, f"index.yaml references release(s) with no manifest file: {dangling}"


def test_index_entry_components_match_manifest_components(index_data):
    manifests = load_release_manifests()
    mismatches = []
    for entry in index_data["releases"]:
        version = entry["version"]
        manifest = manifests[version]["data"]
        for component_name in KNOWN_COMPONENTS:
            index_version = entry["components"].get(component_name)
            manifest_version = manifest["components"][component_name]["version"]
            if index_version != manifest_version:
                mismatches.append(
                    f"{version}/{component_name}: index says {index_version!r}, "
                    f"manifest says {manifest_version!r}"
                )
    assert not mismatches, "\n".join(mismatches)


def test_index_entry_component_keys_are_exactly_known_set(index_data):
    for entry in index_data["releases"]:
        assert set(entry["components"].keys()) == KNOWN_COMPONENTS, entry["version"]


def test_index_entry_direct_from_matches_manifest_upgrade_direct_from(index_data):
    manifests = load_release_manifests()
    mismatches = []
    for entry in index_data["releases"]:
        version = entry["version"]
        manifest = manifests[version]["data"]
        index_set = set(entry["direct_from"])
        manifest_set = set(manifest["upgrade"]["direct_from"])
        if index_set != manifest_set:
            mismatches.append(
                f"{version}: index direct_from {sorted(index_set)} != "
                f"manifest direct_from {sorted(manifest_set)}"
            )
    assert not mismatches, "\n".join(mismatches)


def test_direct_from_entries_reference_versions_earlier_in_index(index_data):
    """direct_from must only reference releases that precede the release in
    the index's ordering -- no forward references, no self-references.
    Index order is treated as the canonical chronological release order.
    """
    versions_in_order = [r["version"] for r in index_data["releases"]]
    position = {v: i for i, v in enumerate(versions_in_order)}

    violations = []
    for entry in index_data["releases"]:
        version = entry["version"]
        for source in entry["direct_from"]:
            if source not in position:
                violations.append(f"{version}: direct_from references unknown version {source!r}")
            elif position[source] >= position[version]:
                violations.append(
                    f"{version}: direct_from references {source!r}, which does not "
                    f"precede it in index.yaml"
                )
    assert not violations, "\n".join(violations)
