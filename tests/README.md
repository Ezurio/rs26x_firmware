# Release manifest tests

Validates the YAML files in this repo (`latest.yaml`, `releases/index.yaml`,
`releases/*.yaml`) for internal consistency and, optionally, against the
live GitHub release assets they point to.

## Setup

Dependencies (`pyyaml`, `requests`, `pytest`) are listed in `pyproject.toml`:

```
pip install pyyaml requests pytest
```

## Running

From the repo root:

```
python3 -m pytest tests/                 # everything, including live network checks
python3 -m pytest tests/ -m "not network" # offline only: schema, index/latest/graph consistency
python3 -m pytest tests/ -m network       # only the live download/hash/reachability checks
```

Offline tests are fast (no network) and check things like: required fields
are present, `sha256`/`size_bytes` are well-formed, `release_version` matches
the filename, `index.yaml` and `latest.yaml` agree with each release
manifest, the `direct_from` upgrade graph has no cycles and every release
can reach `latest_release` via some chain of hops, and `requires`/
`component_order` preconditions are internally consistent (see
"Intermediate upgrade states" below).

Network tests download every unique release artifact (deduped by URL, since
some files are reused across multiple releases) and verify its size and
sha256 match the manifest, plus that every `notes_url` (a raw link to that release's `RELEASE_NOTES.md`) resolves.

## Testing against a private repo

The repo backing these releases (`Ezurio/rs26x_firmware`) may not always be
public yet. If it's private, anonymous requests to the release/download
URLs will 404 -- which is actually correct behavior for these tests to
show, since it means the "public repo, no intermediary server" design goal
isn't met yet.

To validate artifact content anyway while the repo is still private, set
`GITHUB_TOKEN` to a token with `repo` scope (e.g. from `gh auth token`):

```
export GITHUB_TOKEN=$(gh auth token)
python3 -m pytest tests/ -m network
```

When set, the network tests resolve assets through the GitHub API instead
of the plain download URLs (which require a browser session, not a bearer
token, for private repos). When unset, everything runs fully anonymous --
the same access a device in the field would have.

## Layout

| File | Covers |
|---|---|
| `releasedata.py` | Network-free YAML loading/parsing helpers, shared by fixtures and by test parametrization |
| `conftest.py` | Fixtures: loaded YAML data, an HTTP session with retries, and URL/asset caches so shared files are only fetched once |
| `test_schema.py` | Per-file structural validation (required fields, formats, enums). `rm1261_fw`/`rm1262_fw` may omit `url`/`sha256`/`size_bytes` (all or none); every other component requires them |
| `test_index_consistency.py` | `releases/index.yaml` agrees with each release manifest |
| `test_latest_consistency.py` | `latest.yaml` agrees with `index.yaml` and its release manifest |
| `test_upgrade_graph.py` | The `direct_from` graph is well-formed and fully connects to latest; `requires`/`component_order` preconditions hold |
| `test_release_artifacts.py` | Live: artifact size/hash match, notes URLs resolve (`@pytest.mark.network`) |

### Intermediate upgrade states

Because updating `rs26x_app` and updating firmware components (e.g.
`canvas_fw`) are separate operations, an update tool with no stored
progress state may see a device mid-upgrade -- some components already
flashed, others not. `test_upgrade_graph.py` checks two things that make
this resolvable without persisted state:

- `component_order` never contains a cycle, so a valid order to finish in
  always exists.
- For every release with a `requires` precondition, and for every release
  it can be reached directly from (`direct_from`), the precondition is
  guaranteed to hold by the time `rs26x_app` is updated -- either because
  the required component doesn't change and already satisfies it, or
  because `component_order` has a *required* edge forcing it to be
  updated first.
