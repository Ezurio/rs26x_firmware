"""Shared, network-free helpers for loading and parsing the release YAML files.

Plain module (not a test file, not conftest.py) so both conftest.py fixtures
and test modules can import it directly -- including at collection time, for
parametrization over releases/components/URLs.
"""
import re
from pathlib import Path
from urllib.parse import unquote

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
RELEASES_DIR = REPO_ROOT / "releases"
INDEX_YAML_PATH = RELEASES_DIR / "index.yaml"
LATEST_YAML_PATH = REPO_ROOT / "latest.yaml"

KNOWN_COMPONENTS = {"rs26x_app", "canvas_fw", "rm1261_fw", "rm1262_fw"}

# RM126x firmware is updated over the air by the app, which needs a binary
# image that older releases never published. Their manifests record only the
# version that shipped with the release; url/sha256/size_bytes are optional
# (all three or none) for these components.
RM126X_COMPONENTS = {"rm1261_fw", "rm1262_fw"}
ARTIFACT_FIELDS = ("url", "sha256", "size_bytes")

DOWNLOAD_URL_RE = re.compile(
    r"^https://github\.com/(?P<owner>[^/]+)/(?P<repo>[^/]+)"
    r"/releases/download/(?P<tag>[^/]+)/(?P<filename>.+)$"
)
NOTES_URL_RE = re.compile(
    r"^https://raw\.githubusercontent\.com/(?P<owner>[^/]+)/(?P<repo>[^/]+)"
    r"/refs/heads/(?P<branch>[^/]+)/releases/(?P<version>[^/]+)/RELEASE_NOTES\.md$"
)


def parse_release_download_url(url):
    """Split a `.../releases/download/<tag>/<filename>` URL into its parts,
    or return None if it doesn't match that shape. Used to resolve a
    private repo's asset via the GitHub API when a token is available,
    since the plain download URL requires a browser session, not a bearer
    token, for private repos.
    """
    match = DOWNLOAD_URL_RE.match(url)
    if not match:
        return None
    parts = match.groupdict()
    parts["filename"] = unquote(parts["filename"])
    return parts


def parse_notes_url(url):
    """Split a raw `.../refs/heads/<branch>/releases/<version>/RELEASE_NOTES.md`
    URL into its parts, or return None if it doesn't match that shape.
    """
    match = NOTES_URL_RE.match(url)
    return match.groupdict() if match else None


def load_yaml(path):
    with open(path, "r") as f:
        return yaml.safe_load(f)


def load_index():
    return load_yaml(INDEX_YAML_PATH)


def load_latest():
    return load_yaml(LATEST_YAML_PATH)


def release_manifest_paths():
    """All releases/*.yaml manifest files, excluding index.yaml, sorted by name."""
    return sorted(
        p for p in RELEASES_DIR.glob("*.yaml") if p.name != "index.yaml"
    )


def load_release_manifests():
    """dict: release_version -> {"path": Path, "data": dict} for every manifest file."""
    manifests = {}
    for path in release_manifest_paths():
        data = load_yaml(path)
        version = data.get("release_version", path.stem)
        manifests[version] = {"path": path, "data": data}
    return manifests


def iter_component_artifacts():
    """Yield (release_version, component_name, component_dict) for every
    component entry in every release manifest. Network-free, safe to call
    at collection time for parametrization.
    """
    for version, entry in sorted(load_release_manifests().items()):
        data = entry["data"]
        for name, component in data.get("components", {}).items():
            yield version, name, component


def unique_artifacts_by_url():
    """dict: url -> {"size_bytes": int, "sha256": str, "releases": [(version, component_name), ...]}

    Collapses the same downloadable file (identical URL) referenced by
    multiple releases into a single entry (components with no artifact, such as
    older RM126x entries, are skipped), so callers only need to fetch it
    once. Also useful for asserting that all releases referencing a URL
    agree on its size/hash.
    """
    by_url = {}
    for version, name, component in iter_component_artifacts():
        url = component.get("url")
        if url is None:
            continue
        entry = by_url.setdefault(
            url,
            {
                "size_bytes": component.get("size_bytes"),
                "sha256": component.get("sha256"),
                "releases": [],
            },
        )
        entry["releases"].append((version, name))
    return by_url
