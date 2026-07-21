"""Semantic checks on the upgrade graph itself: connectivity/multi-hop
reachability, and the meaning (not just shape) of `requires` preconditions.

Structural/per-file shape checks (fields present, valid enum values, etc.)
live in test_schema.py; cross-file field agreement lives in
test_index_consistency.py / test_latest_consistency.py. This module is
about what the graph *means*: can every release actually get to latest,
and are stated version preconditions actually true.
"""
import operator
import re

from releasedata import load_release_manifests

REQUIRES_RE = re.compile(r"^(==|>=|<=|>|<)\s*(\S+)$")
OPERATORS = {
    "==": operator.eq,
    ">=": operator.ge,
    "<=": operator.le,
    ">": operator.gt,
    "<": operator.lt,
}

# `requires` is documented (see comments in e.g. 1.2.0.yaml) as a precondition
# checked "before attempting the app update" -- i.e. the dependent component
# is always implicitly rs26x_app, the component whose version defines the
# release itself.
DEPENDENT_COMPONENT = "rs26x_app"


def _satisfies(actual_version, constraint):
    match = REQUIRES_RE.match(constraint)
    assert match, f"unparseable requires constraint: {constraint!r}"
    op_symbol, required_version = match.groups()
    return OPERATORS[op_symbol](_version_key(actual_version), _version_key(required_version))


def _version_key(version):
    """Turn "2.1.2" or "R127.4.1.806" into a comparable tuple of ints,
    e.g. (2, 1, 2) or (127, 4, 1, 806). Good enough for the two version
    schemes actually used in this repo (semver-ish app/canvas versions,
    and R<major>.<minor>.<patch>.<build> RM firmware versions).
    """
    numeric_part = version.lstrip("Rr")
    return tuple(int(p) if p.isdigit() else p for p in numeric_part.split("."))


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


def test_component_order_has_no_ordering_cycles():
    """Within a single release's rollout, component_order entries impose
    "update before" edges between components. A device applying that
    release with no memory of its own progress relies on there being at
    least one valid order to finish in -- if the edges cycle, no such
    order exists and "what's the next action" has no answer.
    """
    manifests = load_release_manifests()
    violations = []
    for version, entry in manifests.items():
        edges = {
            (e["update"], e["before"])
            for e in entry["data"]["upgrade"].get("component_order", [])
        }
        nodes = {n for edge in edges for n in edge}

        def has_cycle_from(start, edges=edges):
            stack = [start]
            seen = set()
            while stack:
                node = stack.pop()
                if node == start and seen:
                    return True
                if node in seen:
                    continue
                seen.add(node)
                stack.extend(b for a, b in edges if a == node)
            return False

        cyclic = [n for n in nodes if has_cycle_from(n)]
        if cyclic:
            violations.append(f"{version}: component_order cycle involving {cyclic}")
    assert not violations, "\n".join(violations)


def test_requires_preconditions_resolvable_from_every_direct_predecessor():
    """The update tool flashes rs26x_app and the other components as
    separate operations and cannot assume it remembers "how far it got".
    So for a release R with a `requires` precondition on component B, a
    device that just finished ANY of R's direct_from predecessors must
    already satisfy that precondition by the time rs26x_app gets updated,
    using only information visible in R itself (its own component_order
    and requires) -- otherwise the device could land in a state where the
    precondition is violated and nothing in the manifest graph says how to
    fix it.

    Two cases, per predecessor:
    - B doesn't change between the predecessor and R: the precondition
      must already hold for the predecessor's bundled B version (R isn't
      going to touch B, so whatever the device has is final).
    - B does change (predecessor's B version != R's B version): R's
      component_order must place B before rs26x_app (as a *required*
      ordering, not just recommended) so the tool always updates B first
      and rs26x_app's precondition is satisfied by the time it's applied.
    """
    manifests = load_release_manifests()
    violations = []

    for version, entry in manifests.items():
        data = entry["data"]
        requires = data["upgrade"].get("requires", {})
        if not requires:
            continue

        order_edges = {
            (e["update"], e["before"]): e["constraint"]
            for e in data["upgrade"].get("component_order", [])
        }

        for component_b, constraint in requires.items():
            final_b_version = data["components"][component_b]["version"]

            for predecessor_version in data["upgrade"]["direct_from"]:
                predecessor = manifests[predecessor_version]["data"]
                incoming_b_version = predecessor["components"][component_b]["version"]

                if incoming_b_version == final_b_version:
                    if not _satisfies(incoming_b_version, constraint):
                        violations.append(
                            f"{version}: a device arriving from {predecessor_version} has "
                            f"{component_b}={incoming_b_version}, which does not satisfy "
                            f"requires {component_b} {constraint}, and {version} does not "
                            f"update {component_b} to fix it"
                        )
                else:
                    edge_constraint = order_edges.get((component_b, DEPENDENT_COMPONENT))
                    if edge_constraint != "required":
                        violations.append(
                            f"{version}: a device arriving from {predecessor_version} has "
                            f"{component_b}={incoming_b_version} and needs it updated to "
                            f"{final_b_version} to satisfy requires {component_b} {constraint}, "
                            f"but component_order has no required "
                            f"'{component_b} before {DEPENDENT_COMPONENT}' entry to guarantee "
                            f"that happens before {DEPENDENT_COMPONENT} is updated"
                        )
                    elif not _satisfies(final_b_version, constraint):
                        violations.append(
                            f"{version}: requires {component_b} {constraint}, but this "
                            f"release's own {component_b} ({final_b_version}) does not satisfy it"
                        )

    assert not violations, "\n".join(violations)
