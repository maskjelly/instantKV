#!/usr/bin/env python3
"""Save GitHub release-download snapshots in a private local SQLite database."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import sqlite3
import sys
from urllib.request import Request, urlopen

REPOSITORY = 'maskjelly/instantKV'
ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = re.compile(r'^instantkv-(linux-x86_64|linux-arm64|darwin-arm64)\.tar\.gz$')


def fetch_assets(fetch_page):
    """Do not record partial API results or counts for checksum/source files."""
    assets = []
    seen = set()
    for page in range(1, 101):
        releases = fetch_page(page)
        if not isinstance(releases, list):
            raise ValueError('GitHub did not return a release list')
        for release in releases:
            if release['draft']:
                continue
            for asset in release['assets']:
                match = ARCHIVE.fullmatch(asset['name'])
                if not match:
                    continue
                asset_id, count = asset['id'], asset['download_count']
                if type(asset_id) is not int or type(count) is not int or count < 0:
                    raise ValueError('Invalid release asset ID or download count')
                if asset_id in seen:
                    raise ValueError('Duplicate asset ID; retry the changing release listing')
                seen.add(asset_id)
                assets.append((asset_id, release['tag_name'], asset['name'], match[1], count))
        if len(releases) < 100:
            return assets
    raise ValueError('Release page limit reached; no snapshot saved')


def github_page(page):
    request = Request(
        f'https://api.github.com/repos/{REPOSITORY}/releases?per_page=100&page={page}',
        headers={'Accept': 'application/vnd.github+json',
                 'X-GitHub-Api-Version': '2022-11-28',
                 'User-Agent': 'instantkv-local-install-report'},
    )
    # Public API only. Do not load credentials or send user/device information.
    with urlopen(request, timeout=30) as response:
        return json.load(response)


def private_database(path):
    path = path.expanduser().resolve()
    if path == ROOT or ROOT in path.parents:
        raise ValueError('Keep metrics outside the repository and website build')
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if not path.exists():
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.close(fd)
    os.chmod(path, 0o600)
    db = sqlite3.connect(path)
    db.executescript('''
      CREATE TABLE IF NOT EXISTS snapshots (
        id INTEGER PRIMARY KEY, observed_at TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS downloads (
        snapshot_id INTEGER NOT NULL REFERENCES snapshots(id),
        asset_id INTEGER NOT NULL, release TEXT NOT NULL, name TEXT NOT NULL,
        platform TEXT NOT NULL, count INTEGER NOT NULL CHECK(count >= 0),
        PRIMARY KEY(snapshot_id, asset_id));
    ''')
    return db


def save_snapshot(db, assets, observed_at):
    with db:
        snapshot = db.execute('INSERT INTO snapshots(observed_at) VALUES (?)', (observed_at,)).lastrowid
        db.executemany('INSERT INTO downloads VALUES (?, ?, ?, ?, ?, ?)',
                       [(snapshot, *asset) for asset in assets])
    return snapshot


def report(db):
    latest = db.execute('SELECT id, observed_at FROM snapshots ORDER BY id DESC LIMIT 1').fetchone()
    if not latest:
        return {'repository': REPOSITORY, 'status': 'No snapshots. Run with --refresh.'}
    previous = db.execute('SELECT id FROM snapshots WHERE id < ? ORDER BY id DESC LIMIT 1', (latest[0],)).fetchone()
    old = dict(db.execute('SELECT asset_id, count FROM downloads WHERE snapshot_id = ?', (previous[0],))) if previous else {}
    rows = []
    for asset, release, name, platform, count in db.execute('SELECT asset_id, release, name, platform, count FROM downloads WHERE snapshot_id = ? ORDER BY release, platform', (latest[0],)):
        delta = count - old[asset] if asset in old else None
        rows.append({'asset_id': asset, 'release': release, 'platform': platform,
                     'downloads': count, 'change_since_previous': delta,
                     'counter_decreased': delta is not None and delta < 0})
    removed = sorted(set(old) - {row['asset_id'] for row in rows})
    return {'repository': REPOSITORY, 'observed_at': latest[1],
            'metric': 'GitHub binary archive downloads; not verified installs or unique users',
            'source_installs': 'Unknown; source builds do not report installation events',
            'structured_memory_release': 'Unreleased; existing v0.1.2 downloads are legacy KV/checkpoint tools',
            'listed_asset_downloads': sum(row['downloads'] for row in rows),
            'removed_asset_ids_since_previous': removed, 'assets': rows}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', type=Path, default=Path.home() / '.local/state/instantkv-maintainer/install-metrics.sqlite3')
    parser.add_argument('--refresh', action='store_true', help='Read the public GitHub release API; otherwise report offline')
    args = parser.parse_args()
    # Complete the fetch before opening/writing the ledger.
    assets = fetch_assets(github_page) if args.refresh else None
    with private_database(args.database) as db:
        if assets is not None:
            save_snapshot(db, assets, datetime.now(timezone.utc).isoformat())
        print(json.dumps(report(db), indent=2))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(f'Install report failed: {error}', file=sys.stderr)
        sys.exit(1)
