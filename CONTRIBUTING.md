# Contributing

Keep each change focused on one observable problem.
Read [repository maintenance](docs/repository.md) for file ownership and documentation rules.
The engine stays frozen during the [finite benchmark campaign](docs/evaluation-policy.md).

## Set up verification

Use Rust 1.98 or later and Python 3. Site checks need Node 22.12 or later.
Docker checks need Docker Compose.

From the repository root:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r eval/requirements-offline.txt
cd site
npm ci
cd ..
INSTANTKV_TEST_PYTHON="$PWD/.venv/bin/python" ./scripts/check.sh
```

Dependency installation and first tokenizer setup may need internet access.
Verification needs no model, API credential or paid model call.
Use `--repo`, `--core` or `--site` for a focused change. [Exact scopes](scripts/README.md#verification).

CI runs the same core and site commands and checks npm advisories at high severity or above.
Run `npm audit --audit-level=high` in `site/` to repeat that network check. Packaging, portable binaries and container restore checks run separately.
Before deployment, also verify mobile layout, search, copying and benchmark controls in a browser.

## Preserve contracts

Test externally visible behavior and storage invariants. A regression test must fail with the old behavior.
Use fake clocks for deterministic expiry checks.
Preserve transactions, conditional writes, quotas, TTL, checkpoints and namespace grants.
Never log tokens or stored memory. Do not weaken durability to improve benchmarks.
Document storage-format changes and migration steps before implementation.

Regenerate schemas when Rust API types change:

```sh
cargo run --locked -p instantkv -- schema > examples/checkpoint.schema.json
cargo run --locked -p instantkv -- schema --kind memory > examples/memory.schema.json
```

The shared verification command compares these files with generated output.
Full model campaigns use the separate [evaluation environment](eval/README.md).
Run storage experiments on temporary databases; preserve published report bytes and hashes.

## Write and review

Use short, natural sentences based on ASD-STE100 principles. Exact dictionary compliance is not required.

- Use active voice, one topic per paragraph and one action per instruction.
- Keep API names, commands and configuration fields exact.
- Explain unfamiliar abbreviations once.
- Distinguish current source, released binaries, measured results and proposals.
- Link to canonical contracts and reports instead of repeating them.

Edit Markdown sources for website guides. Register public pages in `site/src/lib/docs.ts`.
A move must update incoming links and preserve published website routes.
Artwork is optional; [sources and licenses](docs/assets/README.md) are maintained separately.

Use the issue and PR templates. State the problem, resulting behavior, checks run and material limits.
Check off only completed work. An incomplete benchmark, unrun CI job or prepared artifact is not a successful release.
[Active repository plan](docs/project-plan.md) · [Operations](docs/operations.md) · [Website](docs/website.md).
