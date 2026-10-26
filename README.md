# RS26x LoRa Sensor Firmware Releases

This repository holds the released software for the RS26x LoRa sensor and the
YAML metadata that describes it. An update tool (the mobile app) reads the
metadata straight from this repo over `raw.githubusercontent.com`, works out
which components need updating and in what order, then downloads and verifies
each artifact. There is no intermediary server.

This document is the reference for the YAML schemas (currently
`schema_version: 2`) and for how a tool should use them to apply updates.

## Components

A release is made of four independently updatable components:

| Component | What it is | Artifact |
|---|---|---|
| `rs26x_app` | RS26x Python application | signed `.zip` |
| `canvas_fw` | Lyra24 Canvas firmware | signed `.bin` |
| `rm1261_fw` | RM1261 radio firmware (`127.x`) | OTA `.bin` |
| `rm1262_fw` | RM1262 radio firmware (`128.x`) | OTA `.bin` |

A device has either an RM1261 or an RM1262, never both. The tool acts only on
the one that matches the hardware and ignores the other.

Versions of the same component are compared segment by segment, numerically.
Radio firmware versions look like `127.4.1.806`, with no `R` prefix, matching what the device reports.

### RM126x OTA

The app can update the RM126x radio over the air, which needs a binary
image. Releases before the first OTA-capable one only ever published `.hex`
files that can't be used for OTA, so those files were removed from the repo
and from git history. Their manifests keep only the RM126x `version` that
shipped with the release, with no `url`, `sha256` or `size_bytes`. Those old
versions can't be installed from this repo.

## Repository layout

```
latest.yaml                     Pointer to the newest release
releases/index.yaml             Every release and the upgrade graph, in one file
releases/<version>.yaml         Full manifest for one release
releases/<version>/             The release's artifacts and RELEASE_NOTES.md
```

Artifacts and notes are referenced by raw URLs of the form
`https://raw.githubusercontent.com/Ezurio/rs26x_firmware/refs/heads/main/releases/<version>/<file>`.
A `+` in a filename is written as `%2B` in the URL.

A file that is unchanged between releases (for example `canvas_fw` 2.1.2 in
1.1.1 and 1.2.0) is stored again under each release's directory. Manifests
that share a URL must declare the same size and hash.

## `latest.yaml`

The entry point. A tool fetches this first.

```yaml
schema_version: 2
latest_release: "1.2.0"
components:                       # versions in the latest release
  rs26x_app: "1.2.0"
  canvas_fw: "2.1.2"
  rm1261_fw: "127.4.1.806"
  rm1262_fw: "128.4.1.806"
release_manifest: "releases/1.2.0.yaml"   # path relative to the repo root
updated_at: "2026-06-25"
```

It must agree with the matching entry in `index.yaml` and with the release
manifest it points to. Update it last, once everything else for a release is
in place.

## `releases/index.yaml`

A compact summary of every release, so a tool can plan an upgrade path without
downloading every manifest.

```yaml
schema_version: 2
releases:
  - version: "1.2.99"
    components: { rs26x_app: "1.2.99", canvas_fw: "2.1.2", rm1261_fw: "127.4.1.806", rm1262_fw: "128.4.1.806" }
    app_capabilities: ["rm126x_ota"]    # optional, same as rs26x_app capabilities
    direct_from: ["1.1.1", "1.2.0"]
```

- `components`: the version of each component shipped in that release.
- `direct_from`: releases that can upgrade straight to this one in one step.
  This is the edge list of the upgrade graph.
- `app_capabilities`: optional. Mirrors `components.rs26x_app.capabilities` in
  the manifest.

## Release manifest: `releases/<version>.yaml`

```yaml
schema_version: 2
release_version: "1.2.99"         # must match the filename
release_date: "2026-10-21"        # ISO date
notes_url: "https://raw.githubusercontent.com/.../releases/1.2.99/RELEASE_NOTES.md"

components:
  rs26x_app:
    version: "1.2.99"
    capabilities: ["rm126x_ota"]  # optional
    url: "https://raw.githubusercontent.com/.../releases/1.2.99/<file>"
    sha256: "<64 lowercase hex>"
    size_bytes: 12345
  canvas_fw: { version, url, sha256, size_bytes }
  rm1261_fw: { version, url, sha256, size_bytes }   # artifact fields all-or-none
  rm1262_fw: { version, url, sha256, size_bytes }   # artifact fields all-or-none

upgrade:
  direct_from: ["1.1.1", "1.2.0"]
  component_order: [rs26x_app, canvas_fw, rm1261_fw, rm1262_fw]
  requires: { canvas_fw: ">=2.1.2" }     # optional, informational only
```

### `components`

All four components are always listed, each with a `version`. `url`,
`sha256` and `size_bytes` come together as the artifact description. They are
required for `rs26x_app` and `canvas_fw`. For `rm1261_fw` and `rm1262_fw` they
are present only in releases that ship an OTA binary, and absent otherwise.
Before installing, a tool must verify the downloaded size and SHA-256.

**A component with no `url` has nothing to install, so the tool skips it.**

`capabilities` is an optional list on `rs26x_app` describing what the app can
do once installed. A missing list means no capabilities.

| Capability | Meaning |
|---|---|
| `rm126x_ota` | The app can update the RM126x radio firmware over the air |

### `upgrade.direct_from`

The releases from which this one can be installed in a single step. The first
release (`0.4.2`) has an empty list, since nothing can upgrade to it. A release
is never listed as upgrading from itself.

An edge from `A` to `B` exists when `A` is in `B.direct_from`. To get from the
installed release to the latest, a tool installs the latest directly if the
installed release is in `latest.direct_from`. Otherwise it follows the edges
through intermediate releases, installing each in turn. Every release should be
able to reach `latest_release`, and the graph must not have cycles.

### `upgrade.component_order`

The **complete** update order for this release, a list of all four component
names with no omissions or duplicates. A tool follows it exactly as written.
There are no `required` or `recommended` markers. Put the reason for an unusual
order in a YAML comment next to the list.

Examples: `0.4.2` and `0.4.3` put `canvas_fw` first ("need initial firmware
before loading application"), `1.0.3` and `1.1.1` put `rs26x_app` before
`canvas_fw` to avoid data loss during the Canvas 2.0.1 to 2.1.x transition, and
the default for everything else is app, Canvas, RM1261, RM1262.

The RM126x entries are normally last. The RM126x update needs the app that is
already installed to have the `rm126x_ota` capability, so it can't come before
a step that installs that app.

### `upgrade.requires` (informational)

A human-readable record of what a release needs installed first, for example
`canvas_fw: ">=2.1.2"`. Operators: `==`, `>=`, `<=`, `>`, `<`.

**Update tools must not read this field.** Every release in `direct_from`
already ships a component set that satisfies it, and finishing the installed
release first (below) guarantees that state. The tests check that every
constraint is satisfied by all of the release's `direct_from` sources.

## How a tool applies an update

The tool keeps no state between runs. It decides what to do from what is
installed on the device each time it runs, so an interrupted upgrade resumes
simply by running again.

1. **Fetch** `latest.yaml` and `releases/index.yaml`.
2. **Read the device**: installed app version, Canvas version, and the RM126x
   variant and version.
3. **Identify the installed release** from the app version. The component
   versions may not match any release exactly, for example an older app with
   newer firmware, or an interrupted upgrade.
4. **Finish the installed release first.** Walk that release's
   `component_order`. For each component that has an artifact and is installed
   at an *older* version than the release declares, install it.
5. **Plan the path** from the installed release to `latest_release` through
   `direct_from`.
6. **For each release on the path**, fetch its manifest and walk its
   `component_order` the same way: install each component that has an artifact
   and is older than the release's version.
7. **Never downgrade.** A component installed at a version at or above the
   release's is left alone. This keeps steps 4 and 6 safe when the installed
   state is ambiguous.
8. **Verify and install.** Check each artifact's size and SHA-256, then install
   it. If any step fails, stop. The device stays in a state a later run can
   continue from.

All updates are required, including the RM126x. The RM126x is normally last in
the order, so a failed RM126x update stops the upgrade only after the other
components are already updated.

## Adding a release

1. Create `releases/<version>/` with the artifacts and `RELEASE_NOTES.md`.
2. Write `releases/<version>.yaml`. Compute `sha256` and `size_bytes` from the
   actual files. Set `direct_from` and a complete `component_order`.
3. Add the release to `releases/index.yaml` with the same components,
   capabilities and `direct_from`.
4. Update `latest.yaml`.
5. Run the tests, which live on the `test_cases` branch:
   `python3 -m pytest tests -m "not network"`.
6. Tag the release commit `v<version>`.

Do not edit the manifest of a published release except to fix a mistake, since
devices and tools in the field read these files.

## Schema version history

- **1**: initial format. `component_order` was a list of
  `{update, before, constraint, reason}` entries with `required` or
  `recommended` constraints, and `requires` was read by tools. `index.yaml` had
  no `schema_version`.
- **2**: `component_order` is a complete flat list that tools follow as
  written, `requires` is informational only, `capabilities` and
  `app_capabilities` are added, RM126x artifact fields are optional (all or
  none), `notes_url` points at the raw `RELEASE_NOTES.md`, and `index.yaml`
  gains a `schema_version`. RM126x updates are required. The "optional"
  RM126x idea and `upgrade.policy` were dropped.
