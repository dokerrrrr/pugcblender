# PUBG UGC Toolkit changelog

## 1.0.1

- New placements use a single transform around the native pivot. For older imported projects, edits to position, rotation, and scale are mapped into the current coordinate system relative to the original game record.

## 1.0.0

This release supports offline map builds and format and geometry validation. Opening and re-saving maps in the target PUBG UGC client is scheduled for the next release. [Issue #18](https://github.com/dokerrrrr/pugcblender/issues/18)

- Installable `pugc` CLI, a neutral template for new projects, and support for working from an external directory.
- Shared PUGC v3 codec, consistent preflight validation, and import from a sidecar with stable IDs.
- Atomic project writes and recovery for interrupted map-and-sidecar writes.
- Machine-readable JSON v1 responses and batch editing with a preview and a SHA-256 check of the base revision.
- Search by ID, purpose, category, and dimensions. Diagnostics for the base, small, and full resource packs.
- Strict geometry verification of the saved map with explicit coverage. One end-to-end tutorial and a pinned revision for recovering archived projects.

[Migration](docs/MIGRATION.md) · [Release builds](docs/RELEASE_PREFLIGHT.md)
