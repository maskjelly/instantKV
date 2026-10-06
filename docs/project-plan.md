# Repository cleanup and release plan

Updated 6 October 2026. Audience: maintainers.
This plan manages the repository. Product milestones stay in the [roadmap](roadmap.md).
The engine remains frozen during the [finite evaluation campaign](evaluation-policy.md).

## Current cleanup

| Work | Result in this change | Completion check |
| --- | --- | --- |
| Entry points | Brief README, documentation map and three start guides | Source examples and site links pass |
| File ownership | [Repository map](repository.md) and default reviewer | Every source file has a supported home |
| Historical clutter | Retired code in `archive/`; snapshots in `docs/history/` | Relative links and archive tests pass |
| Proposals and validation | Separate directories, explicit status | Current guides do not present them as shipped features |
| Verification | One `scripts/check.sh` entry point used by contributors and CI | Core/site modes, schemas and tests pass |
| Hygiene enforcement | Source layout, accidental private/generated files and Markdown checks | Regression cases reject invalid fixtures |
| Review workflow | Focused issue/PR templates with completion criteria | Checks, compatibility and scope are recorded |
| Service website | Installation first; shared themes; task-based docs; report-backed evidence | Built-page checks and browser layout/interaction checks pass |
| Private adoption evidence | Local SQLite download snapshots outside Git | Counting and privacy regressions pass; source installs stay unknown |

[Validation record](validation/2026-10-06.md) records local checks and their limits.
Published benchmark JSON/JSONL stays byte-for-byte unchanged. Published site routes retain their existing slugs.
Personal correspondence stays outside the source repository.
Cleanup was committed and pushed as `58702e1`; its Linux x86_64, Linux ARM64,
macOS, container and website CI jobs passed. The service-site implementation was
pushed as `ab6e502`. [Website audit and acceptance contract](website.md).

## Next repository work

1. **Apply these rules to future changes.** Put one problem and observable completion criteria in each issue. Update the canonical guide, not a second prompt ledger.
2. **Prepare the memory-MVP release.** Choose a new version and use one tested commit for binaries, schemas, checksums and release notes.
3. **Verify packaged installation.** On each advertised platform, install → init → remember → search → checkpoint → restart → restore.
4. **Publish matching assets, then update the installer default.** Earlier binaries lack the new memory APIs; do not relabel them.

The repository rules do not configure branch protection or publish a release.
Device work, retrieval changes and remaining model-quality evaluation keep their separate acceptance gates in the roadmap and evaluation policy.

## Keep the cleanup from decaying

- Root files define the project, build and operating contracts. Put material in its assigned directory.
- Edit canonical guides instead of copying setup, benchmark tables or feature status into new documents.
- Keep historical reports, hashes and source revisions. Fresh runs use fresh output directories.
- Move stale guides to history; update incoming links and preserve published website routes.
- Run `scripts/check.sh` and record only checks actually completed.

Avoid new management documents unless they replace a missing contract or an existing page.
[Repository maintenance](repository.md) defines the durable rules; this page tracks their implementation.

## Rollback

This cleanup has no database migration. Revert the file moves, source mappings and tooling changes together if verification fails.
Preserve private notes in their external location. Use the [operations guide](operations.md) for storage backup or restore.
