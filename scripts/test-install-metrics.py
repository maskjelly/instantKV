#!/usr/bin/env python3
"""Counting and privacy regressions for the maintainer download ledger."""
import importlib.util
from pathlib import Path
import sqlite3
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('metrics', Path(__file__).with_name('install-metrics.py'))
metrics = importlib.util.module_from_spec(spec)
spec.loader.exec_module(metrics)


def release(count=4):
    return {'draft': False, 'tag_name': 'v0.1.2', 'assets': [
        {'id': 1, 'name': 'instantkv-darwin-arm64.tar.gz', 'download_count': count},
        {'id': 2, 'name': 'instantkv-darwin-arm64.tar.gz.sha256', 'download_count': 20},
    ]}


class MetricsTests(unittest.TestCase):
    def test_only_binary_archives_are_counted(self):
        draft = release(); draft['draft'] = True
        assets = metrics.fetch_assets(lambda page: [release(), draft])
        self.assertEqual(assets, [(1, 'v0.1.2', 'instantkv-darwin-arm64.tar.gz', 'darwin-arm64', 4)])

    def test_pagination_is_complete(self):
        pages = []
        def fetch(page):
            pages.append(page)
            return [{'draft': False, 'tag_name': 'v0', 'assets': []}] * 100 if page == 1 else [release()]
        self.assertEqual(len(metrics.fetch_assets(fetch)), 1)
        self.assertEqual(pages, [1, 2])

    def test_api_failure_does_not_create_partial_snapshot(self):
        def fetch(page):
            if page == 2:
                raise OSError('network failed')
            return [{'draft': False, 'tag_name': 'v0', 'assets': []}] * 100
        with self.assertRaises(OSError):
            metrics.fetch_assets(fetch)

    def test_negative_count_and_duplicate_id_rejected(self):
        for data in ([release(-1)], [release(), release()]):
            with self.assertRaises(ValueError):
                metrics.fetch_assets(lambda page: data)

    def test_deltas_resets_and_removed_assets_stay_honest(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = metrics.private_database(Path(tmp) / 'metrics.sqlite3')
            metrics.save_snapshot(db, metrics.fetch_assets(lambda page: [release(10)]), 'first')
            metrics.save_snapshot(db, metrics.fetch_assets(lambda page: [release(14)]), 'second')
            self.assertEqual(metrics.report(db)['assets'][0]['change_since_previous'], 4)
            metrics.save_snapshot(db, metrics.fetch_assets(lambda page: [release(2)]), 'third')
            self.assertTrue(metrics.report(db)['assets'][0]['counter_decreased'])
            metrics.save_snapshot(db, [], 'fourth')
            self.assertEqual(metrics.report(db)['removed_asset_ids_since_previous'], [1])
            db.close()

    def test_snapshot_rollback(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = metrics.private_database(Path(tmp) / 'metrics.sqlite3')
            assets = metrics.fetch_assets(lambda page: [release()])
            with self.assertRaises(sqlite3.IntegrityError):
                metrics.save_snapshot(db, assets + assets, 'invalid')
            self.assertEqual(db.execute('SELECT COUNT(*) FROM snapshots').fetchone()[0], 0)
            db.close()

    def test_private_permissions_and_repo_refusal(self):
        with self.assertRaises(ValueError):
            metrics.private_database(metrics.ROOT / 'site/public/install-metrics.sqlite3')
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'private/metrics.sqlite3'
            db = metrics.private_database(path)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertEqual(metrics.report(db)['status'], 'No snapshots. Run with --refresh.')
            db.close()


if __name__ == '__main__':
    unittest.main()
