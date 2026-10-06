#!/usr/bin/env python3
"""Regression cases for the repository hygiene gate."""
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('repo_check', Path(__file__).with_name('check-repo.py'))
check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check)


class RepositoryChecks(unittest.TestCase):
    def test_allows_source_and_example_environment(self):
        for name in ['README.md', '.env.example', 'archive/browser-demo/instantkv.toml', 'config/local.toml', 'site/.env.example']:
            self.assertEqual(check.path_errors(Path(name)), [], name)

    def test_rejects_private_and_generated_files(self):
        for name in ['.env', 'archive/browser-demo/.tunnel-token', 'site/public/llms.txt',
                     'site/public/assets/logo.svg', 'eval/__pycache__/run.pyc', '.venv/bin/python',
                     'data/instantkv.redb', 'instantkv.toml', 'random-notes.md']:
            self.assertTrue(check.path_errors(Path(name)), name)

    def test_missing_file_and_heading_fail(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'README.md').write_text('[Missing](missing.md)\n[Anchor](guide.md#unknown)\n')
            (root / 'guide.md').write_text('# Guide\n')
            self.assertEqual(len(check.link_errors(root, Path('README.md'))), 2)

    def test_unicode_paths_duplicates_and_reference_links(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'café guide.md').write_text('# Overview\n## Reopen\n## Reopen\n')
            (root / 'README.md').write_text('[Guide](caf%C3%A9%20guide.md#reopen-1)\n[ref]: <café%20guide.md#overview>\n')
            self.assertEqual(check.link_errors(root, Path('README.md')), [])

    def test_fences_and_inline_examples_are_not_links(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'README.md').write_text('```md\n[Example](absent.md)\n```\n`[example](absent.md)`\n')
            self.assertEqual(check.link_errors(root, Path('README.md')), [])

    def test_heading_code_keeps_its_text(self):
        self.assertIn('use-search', check.heading_ids('## Use `search`\n'))

    def test_link_cannot_escape_repository(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'README.md').write_text('[Outside](../private.txt)\n')
            self.assertIn('leaves the repository', check.link_errors(root, Path('README.md'))[0])

    def test_git_integration_checks_new_files_and_forced_private_files(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            subprocess.run(['git', 'init', '-q', folder], check=True)
            (root / 'README.md').write_text('# Test\n')
            (root / '.gitignore').write_text('.env\n')
            command = ['python3', str(Path(check.__file__)), '--root', folder]
            self.assertEqual(subprocess.run(command, capture_output=True).returncode, 0)
            (root / '.env').write_text('fixture-only\n')
            subprocess.run(['git', '-C', folder, 'add', '-f', '.env'], check=True)
            failed = subprocess.run(command, capture_output=True, text=True)
            self.assertNotEqual(failed.returncode, 0)
            self.assertIn('private environment', failed.stdout)


if __name__ == '__main__':
    unittest.main()
