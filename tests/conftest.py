import os

import pytest
import requests
from requests.adapters import HTTPAdapter, Retry

from releasedata import (
    KNOWN_COMPONENTS,
    load_index,
    load_latest,
    load_release_manifests,
    parse_release_download_url,
)

REQUEST_TIMEOUT = 30
GITHUB_API = "https://api.github.com"


@pytest.fixture(scope="session")
def index_data():
    return load_index()


@pytest.fixture(scope="session")
def latest_data():
    return load_latest()


@pytest.fixture(scope="session")
def release_manifests():
    return load_release_manifests()


@pytest.fixture(scope="session")
def known_components():
    return KNOWN_COMPONENTS


@pytest.fixture(scope="session")
def http_session():
    session = requests.Session()
    retries = Retry(
        total=5,
        backoff_factor=1.0,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "HEAD"],
    )
    adapter = HTTPAdapter(max_retries=retries)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update(
        {"User-Agent": "rs2xx-firmware-release-tests (+release manifest validation)"}
    )
    yield session
    session.close()


@pytest.fixture(scope="session")
def github_token():
    """Optional bearer token for GITHUB_TOKEN, used only to validate content
    against a not-yet-public repo during development. When unset, all
    requests are anonymous -- the same access a device in the field would
    have -- which is the real test of the "public repo, no intermediary
    server" design goal.
    """
    return os.environ.get("GITHUB_TOKEN")


@pytest.fixture(scope="session")
def url_content_cache():
    """Session-wide cache so files shared across releases are downloaded once."""
    return {}


@pytest.fixture(scope="session")
def release_asset_index_cache():
    """Session-wide cache of (owner, repo, tag) -> {filename: asset_id},
    so a release's asset list is only looked up once even though a release
    has multiple components sharing the same tag.
    """
    return {}


def _fetch_private_asset_via_api(http_session, token, url, release_asset_index_cache):
    """Resolve and download a `.../releases/download/<tag>/<file>` URL via
    the GitHub API using a bearer token. Needed for private repos: the
    plain download URL 302s to a location that requires a browser session,
    not a bearer token, so we must go through the assets API instead.
    """
    parts = parse_release_download_url(url)
    if parts is None:
        raise ValueError(f"not a recognized GitHub release download URL: {url}")

    owner, repo, tag, filename = parts["owner"], parts["repo"], parts["tag"], parts["filename"]
    auth_headers = {"Authorization": f"token {token}"}

    cache_key = (owner, repo, tag)
    if cache_key not in release_asset_index_cache:
        resp = http_session.get(
            f"{GITHUB_API}/repos/{owner}/{repo}/releases/tags/{tag}",
            headers={**auth_headers, "Accept": "application/vnd.github+json"},
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        release_asset_index_cache[cache_key] = {
            asset["name"]: asset["id"] for asset in resp.json()["assets"]
        }

    asset_id = release_asset_index_cache[cache_key].get(filename)
    if asset_id is None:
        raise LookupError(f"no asset named {filename!r} in {owner}/{repo} release {tag}")

    asset_resp = http_session.get(
        f"{GITHUB_API}/repos/{owner}/{repo}/releases/assets/{asset_id}",
        headers={**auth_headers, "Accept": "application/octet-stream"},
        timeout=REQUEST_TIMEOUT,
    )
    asset_resp.raise_for_status()
    return asset_resp.content


@pytest.fixture(scope="session")
def fetch_url(http_session, url_content_cache, github_token, release_asset_index_cache):
    def _fetch(url):
        if url not in url_content_cache:
            if github_token:
                content = _fetch_private_asset_via_api(
                    http_session, github_token, url, release_asset_index_cache
                )
            else:
                response = http_session.get(url, timeout=REQUEST_TIMEOUT)
                response.raise_for_status()
                content = response.content
            url_content_cache[url] = content
        return url_content_cache[url]

    return _fetch
