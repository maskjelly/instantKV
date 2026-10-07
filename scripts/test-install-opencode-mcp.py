#!/usr/bin/env python3
"""The V1 installer must leave an OpenCode V2 config untouched."""
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    with tempfile.TemporaryDirectory() as folder:
        base = Path(folder)
        config = base / 'opencode.json'
        original = '{"mcp":{"servers":{"other":{"type":"local","command":["other"]}}}}\n'
        config.write_text(original)
        install = base / 'bin'
        result = subprocess.run([
            sys.executable, str(ROOT / 'scripts/install-opencode-mcp.py'),
            '--config', str(config), '--install-dir', str(install),
            '--binary', str(base / 'missing-binary'),
        ], capture_output=True, text=True, check=False)
        assert result.returncode != 0
        assert 'OpenCode V2' in result.stderr
        assert config.read_text() == original
        assert not install.exists()
    print('PASS: OpenCode V2 configuration stays unchanged.')


if __name__ == '__main__':
    main()
