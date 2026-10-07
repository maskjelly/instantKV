# Private product measurement

Keep adoption evidence on the maintainer's machine. Do not publish a counter.
The website and installed memory service send no installation events.

## Collect a snapshot

```sh
python3 scripts/install-metrics.py --refresh
```

This reads the public GitHub release API and stores binary-archive download
counts in `~/.local/state/instantkv-maintainer/install-metrics.sqlite3`.
The database has mode `0600`. A newly created parent directory has mode `0700`.
The script refuses database paths inside this repository, including symlink paths.
It needs Python 3 and its standard library. No token or additional package is required.

Read the latest report without a network request:

```sh
python3 scripts/install-metrics.py
```

Use `--database /private/path/install-metrics.sqlite3` for another local path.
If you own the GitHub repository, add its recent clone and page-view traffic:

```sh
gh auth status
python3 scripts/install-metrics.py --refresh --traffic
```

The GitHub CLI needs repository access. The script stores only aggregate daily
counts and the totals GitHub returns for its recent traffic window. It does
not store visitor identities. Run this once a week. GitHub traffic has a short
history, so missed weeks cannot be rebuilt from this source. Collection is
manual. No background task is installed.
Back up the database as private maintainer state, outside Git and the site build.

## Interpret the counts

- A download is not a completed installation or a unique user. Repeated downloads count again.
- Source builds do not report installation events. Their install count is unknown.
- Published v0.1.2 binaries contain legacy KV/checkpoint tools. They do not prove use of the unreleased memory MVP.
- Checksum files and GitHub source archives are excluded. Only known native binary archive names count.
- The first snapshot is a baseline. Later snapshots show each asset's change from the previous observation.
- Deleted assets are listed separately. Decreased counters remain negative and flagged; the script does not invent installs.
- Clone traffic includes automated clones, repeat clones and CI. Page views do not prove installation.
- `window_uniques` is GitHub's count for its traffic window. Daily unique counts cannot be added to get weekly unique people.
- Compare `last_7_days_count` with `previous_7_days_count` only as a direction signal. The window can include missing or partial days. Do not call the difference user growth.

The collector saves only release tags, asset IDs, platforms, public download counts
and observation time. It stores no visitor, account, IP or device identifiers.
Each complete snapshot is one SQLite transaction. Failed API pages or traffic
requests do not create partial snapshots. GitHub can rate-limit requests;
failed refreshes leave the previous report available.

## What to review each week

| Question | Signal | Limit |
| --- | --- | --- |
| Are people finding the project? | Repository views and website search reports | Views include repeat visits; search reports need site-owner access |
| Are people trying it? | Binary downloads, source clone trend and setup feedback | No source-install count; clones can be automated |
| Do people keep using it? | Repeated outside issues, examples, integrations and opt-in user reports | The local service sends no usage events |
| Is setup getting easier? | Fresh-install and harness smoke tests; reported setup failures | Tests prove the path tested, not market adoption |

Record the review date and any known campaign or release beside the private
ledger. Report each signal by its name. Do not add downloads and clones into
one installation count. Do not publish a growth percentage without a stable
time window and a baseline.

If verified install counts become necessary, define an explicit opt-in reporting
contract first. Do not rename download counts as installs.
