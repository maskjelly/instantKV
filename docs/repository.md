# Repository maintenance

Audience: contributors and the repository maintainer.
Keep current instructions separate from proposals, history and generated output.

## Where files belong

| Path | Responsibility |
| --- | --- |
| `crates/instantkv-core/` | Storage, indexes, policy and embedded tests |
| `crates/instantkv/` | HTTP, CLI, MCP, authentication and transport tests |
| `config/` | Supported configuration profiles |
| `examples/` | Runnable integrations and generated API schemas |
| `scripts/` | Setup, verification, backup and benchmark tools |
| `eval/` | Optional benchmark adapters, model calls and spending controls |
| `site/` | Static documentation, evidence UI and Worker routing |
| `docs/` | Current user and contributor guides |
| `docs/proposals/` | Unimplemented designs; state status at the top |
| `docs/history/` | Dated snapshots and superseded designs |
| `docs/validation/` | Dated check records; never claim they describe a later revision |
| `docs/benchmarks/`, `docs/demo-results/` | Published raw evidence and reproduction notes |
| `archive/` | Retired code retained to reproduce historical evidence |

Root files define the build, setup, contribution, license and security contracts.
Personal outreach, scratch notes and temporary run outputs belong outside this repository.
Git ignores local databases, credentials, virtual environments and generated site assets.

## One source for each fact

- README: product boundary and first successful use.
- [Documentation map](README.md): choose a reading path.
- [Roadmap](roadmap.md): product scope and pending milestones.
- [Project plan](project-plan.md): active repository work and completion evidence.
- [Performance](performance.md): measured claims with raw report links.
- [Contributor guide](../CONTRIBUTING.md): development setup and verification commands.
- `site/src/lib/docs.ts`: published documentation routes and groups.

Link to detailed contracts instead of copying their tables into several pages.
Keep benchmark reports intact. New runs get new output directories and revision metadata.
Generated schemas stay committed, but must match the Rust types.
Website assets and machine-readable guides are built from source; never edit their generated copies.

## Manage changes

1. Describe one problem and its observable completion criteria in an issue or PR.
2. Name the affected area: core, transport, docs, site, evaluation or release.
3. Keep fixes separate from speculative features and unrelated cleanup.
4. Update the canonical guide when behavior changes; update links when files move.
5. Run the relevant [verification mode](../scripts/README.md#verification).
6. Record actual checks and limits in the PR. Do not equate local success with CI or deployment.

The default reviewer is recorded in [CODEOWNERS](../.github/CODEOWNERS).
This file requests review; branch protection is a separate repository setting.
No extra approval process is needed for routine documentation changes.

## Documentation lifecycle

Current guides describe the current source and clearly identify unreleased features.
Proposals describe goals and acceptance gates; they do not claim availability.
History records what happened at a named time or revision; it is not an installation guide.
Validation records report only checks actually run, including failures and skipped checks.

Move superseded material into history or archive. Update incoming relative links in the same change.
Preserve published website routes by updating their source mapping.
Retired browser routes stay redirected or return HTTP 410.
If a new guide duplicates an existing page, edit the existing page instead.

## Before release

Use one tested commit for binaries, schemas, checksums and release notes.
Install each packaged binary and test restart and restore on every advertised platform.
Update installer defaults after matching assets exist. Follow [operations](operations.md) for backup and upgrade guidance.
Keep source state, published release state and deployment state separate.
