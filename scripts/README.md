# Repository tools

Run tools from the repository root. Storage experiments use isolated state.
Keep outputs outside the checkout unless preparing release artifacts in ignored `dist/`.

## Verification

| Command | Scope |
| --- | --- |
| `./scripts/check.sh` | Repository, Rust, offline evaluation, schemas, local demos and site |
| `./scripts/check.sh --repo` | Layout, accidental generated/private files and local Markdown links |
| `./scripts/check.sh --core` | Repository checks plus Rust, protocols, offline evaluation and schemas |
| `./scripts/check.sh --site` | Repository checks plus site formatting, types, tests, build and links |

Full/core checks need a Python environment from `eval/requirements-offline.txt`.
Set `INSTANTKV_TEST_PYTHON` to that environment's interpreter.
[Setup and requirements](../CONTRIBUTING.md).
The checker uses Git's file list, including new non-ignored files; it does not scan arbitrary ignored state.
It checks local Markdown files and headings, not external URLs or every embedded command.
No model is installed and no paid model API is called by verification.

## Setup and operations

- `install.sh`, `quickstart.sh`, `kv.sh`: release installation and Docker use.
- `package-release.sh`, `test-package-release.py`: create archives and verify their exact contents and checksums.
- `backup.sh`, `restore-drill.sh`: offline backup and isolated restore.
- `install-opencode-mcp.py`, `opencode-memory-demo.py`: optional OpenCode integration.

Use the [quick start](../docs/quickstart.md) and [operations guide](../docs/operations.md) for these commands.

## Experiments and evidence

- `memory-bench.py`, `local-smoke.py`: local storage, resource samples and restart checks.
- `ranked-bench.py`, `retrieval-suite.py`, `compare-supermemory.py`: retrieval measurements.
- `prepare-retrieval-suite.py`: dataset normalization.
- `verify-retrieval.py`, `verify-retrieval-suite.py`: independent score checks.
- `export-eval-resources.py`, `export-qa-evidence.py`: saved evidence exports.
- `benchmark-suite.sh`: historical raw KV workload runner.

Follow the [benchmark methodology](../docs/benchmarks.md) and [evaluation policy](../docs/evaluation-policy.md).
Full official model evaluation is owned by [eval/](../eval/README.md).
Local storage experiments do not measure agent answer quality.

## Optional artwork

`render-design.py` rebuilds retained diagram assets. It is not a product build dependency.
[Asset sources](../docs/assets/README.md).
