"""Semantic checks on the upgrade graph itself: connectivity/multi-hop
reachability, the (informational) `requires` constraints, and the RM126x
OTA capability that `component_order` relies on.

Structural/per-file shape checks (fields present, valid enum values, etc.)
live in test_schema.py; cross-file field agreement lives in
test_index_consistency.py / test_latest_consistency.py. This module is
about what the graph *means*: can every release actually get to latest,
and are stated version preconditions actually true.
"""
import operator
import re

from releasedata import (
    OTA_CAPABILITY,
    RM126X_COMPONENTS,
    app_capabilities,
    load_release_manifests,
)

REQUIRES_RE = re.compile(r"^(==|>=|<=|>|<)\s*(\S+)$")
OPERATORS = {
    "==": operator.eq,
    ">=": operator.ge,
    "<=": operator.le,
    ">": operator.gt,
    "<": operator.lt,
}

def _satisfies(actual_version, constraint):
    match = REQUIRES_RE.match(constraint)
    assert match, f"unparseable requires constraint: {constraint!r}"
    op_symbol, required_version = match.groups()
    return OPERATORS[op_symbol](_version_key(actual_version), _version_key(required_version))


def _version_key(version):
    """Turn "2.1.2" or "127.4.1.806" into a comparable tuple of ints,
    e.g. (2, 1, 2) or (127, 4, 1, 806). Good enough for the two version
    schemes actually used in this repo (semver-ish app/canvas versions,
    and <major>.<minor>.<patch>.<build> RM firmware versions).
    """
    return tuple(int(p) if p.isdigit() else p for p in version.split("."))


def _build_direct_from_graph(index_data):
    """dict: version -> set(versions it can be upgraded directly from)."""
    return {r["version"]: set(r["direct_from"]) for r in index_data["releases"]}


def test_initial_release_has_no_direct_from(index_data):
    first = index_data["releases"][0]
    assert first["direct_from"] == [], (
        f"first release in index ({first['version']}) should have no direct_from "
        f"predecessors, got {first['direct_from']}"
    )


def test_every_non_initial_release_has_at_least_one_direct_from_edge(index_data):
    missing = [
        r["version"]
        for r in index_data["releases"][1:]
        if not r["direct_from"]
    ]
    assert not missing, f"non-initial releases with no direct_from edge: {missing}"


def test_every_release_can_reach_latest_via_multi_hop_upgrade_chain(index_data, latest_data):
    """The whole point of direct_from graphs plus multi-hop support: a
    device on ANY known release must have some chain of direct upgrades
    that eventually lands it on latest_release.
    """
    graph = _build_direct_from_graph(index_data)
    target = latest_data["latest_release"]
    all_versions = set(graph.keys())

    # BFS backward from target: a version V can reach `target` if it's a
    # direct predecessor of `target`, or a direct predecessor of something
    # that can reach `target`.
    reachable = {target}
    frontier = {target}
    while frontier:
        next_frontier = set()
        for v in frontier:
            predecessors = graph.get(v, set())
            new = predecessors - reachable
            reachable |= new
            next_frontier |= new
        frontier = next_frontier

    stranded = all_versions - reachable
    assert not stranded, (
        f"release(s) with no multi-hop upgrade path to latest ({target}): {stranded}"
    )


def test_direct_from_graph_has_no_cycles(index_data):
    """A version cannot (transitively) be reachable from a release that
    itself depends on it -- that would make "latest" unreachable in
    practice and indicates a data error.
    """
    graph = _build_direct_from_graph(index_data)

    def has_cycle_from(start):
        stack = [start]
        seen = set()
        while stack:
            node = stack.pop()
            if node == start and seen:
                return True
            if node in seen:
                continue
            seen.add(node)
            stack.extend(graph.get(node, ()))
        return False

    cyclic = [v for v in graph if has_cycle_from(v)]
    assert not cyclic, f"cycle(s) detected in direct_from graph involving: {cyclic}"


def test_requires_precondition_is_satisfied_by_the_releases_own_bundle():
    """A `requires` entry (e.g. rs26x_app 1.2.0 requires canvas_fw >=2.1.2)
    must be consistent with what that same release manifest actually
    bundles for that component -- otherwise the release contradicts its
    own precondition.
    """
    manifests = load_release_manifests()
    violations = []
    for version, entry in manifests.items():
        data = entry["data"]
        requires = data["upgrade"].get("requires", {})
        for component_name, constraint in requires.items():
            bundled_version = data["components"][component_name]["version"]
            if not _satisfies(bundled_version, constraint):
                violations.append(
                    f"{version}: requires {component_name} {constraint}, but this "
                    f"release itself bundles {component_name} {bundled_version}"
                )
    assert not violations, "\n".join(violations)


def test_requires_is_satisfied_by_every_direct_predecessor():
    """`requires` is informational: update tools finish the installed
    release first and then walk the new release's component_order, so they
    never evaluate it. It still has to be true. For a release R with
    `requires` on component B, a device sitting exactly on any release in
    R's direct_from must already satisfy it, since that is the state the
    tool leaves the device in before starting the hop to R. (The release's
    own bundle satisfying it is checked separately above.)
    """
    manifests = load_release_manifests()
    violations = []
    for version, entry in manifests.items():
        data = entry["data"]
        for component_name, constraint in data["upgrade"].get("requires", {}).items():
            for source in data["upgrade"]["direct_from"]:
                source_version = manifests[source]["data"]["components"][component_name]["version"]
                if not _satisfies(source_version, constraint):
                    violations.append(
                        f"{version}: requires {component_name} {constraint}, but a device "
                        f"finishing {source} (direct_from) has {component_name} {source_version}"
                    )
    assert not violations, "\n".join(violations)


def test_rm126x_artifacts_can_be_installed_by_an_ota_capable_app():
    """RM126x firmware is installed by the app already on the device. For a
    release that ships an RM126x artifact:
    - if component_order puts the RM126x after rs26x_app, the release's own
      app (installed just before) must have the rm126x_ota capability;
    - if it puts the RM126x before rs26x_app, the app installed on arrival
      is the one from each direct_from source, so every source must have it.
    """
    manifests = load_release_manifests()
    violations = []
    for version, entry in manifests.items():
        data = entry["data"]
        shipped = sorted(
            name for name in RM126X_COMPONENTS if "url" in data["components"][name]
        )
        if not shipped:
            continue

        order = data["upgrade"]["component_order"]
        app_position = order.index("rs26x_app")
        rm_before_app = any(order.index(name) < app_position for name in shipped)

        if rm_before_app:
            for source in data["upgrade"]["direct_from"]:
                if OTA_CAPABILITY not in app_capabilities(manifests[source]["data"]):
                    violations.append(
                        f"{version}: component_order updates {shipped} before rs26x_app, "
                        f"but its direct_from source {source} has no {OTA_CAPABILITY}"
                    )
        elif OTA_CAPABILITY not in app_capabilities(data):
            violations.append(
                f"{version}: ships RM126x artifacts {shipped} but its rs26x_app "
                f"does not declare {OTA_CAPABILITY}"
            )
    assert not violations, "\n".join(violations)
