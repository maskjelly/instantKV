# Private installation reporting

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
Collection is manual. No background task is installed.
Back up the database as private maintainer state, outside Git and the site build.

## Interpret the counts

- A download is not a completed installation or a unique user. Repeated downloads count again.
- Source builds do not report installation events. Their install count is unknown.
- Published v0.1.2 binaries contain legacy KV/checkpoint tools. They do not prove use of the unreleased memory MVP.
- Checksum files and GitHub source archives are excluded. Only known native binary archive names count.
- The first snapshot is a baseline. Later snapshots show each asset's change from the previous observation.
- Deleted assets are listed separately. Decreased counters remain negative and flagged; the script does not invent installs.

The collector saves only release tags, asset IDs, platforms, public download counts
and observation time. It stores no visitor, account, IP or device identifiers.
Each complete snapshot is one SQLite transaction. Failed API pages do not create
partial snapshots. GitHub's public API can rate-limit requests; failed refreshes
leave the previous report available.

If verified install counts become necessary, define an explicit opt-in reporting
contract first. Do not rename download counts as installs.
