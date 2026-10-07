#!/usr/bin/env python3
"""Install instantKV as a local MCP in OpenCode, preserving other settings."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import runpy
import shutil
import subprocess
import tempfile
import re

ROOT = Path(__file__).resolve().parents[1]
BEGIN = '\n<instantkv-memory-policy>\n'
END = '\n</instantkv-memory-policy>\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=Path.home() / '.config/opencode/opencode.json')
    parser.add_argument('--data-dir', type=Path, default=Path.home() / '.local/share/instantkv/opencode')
    parser.add_argument('--binary', type=Path, default=ROOT / 'target/release/instantkv')
    parser.add_argument('--install-dir', type=Path, default=Path.home() / '.local/bin')
    parser.add_argument('--model', default='openai/gpt-6-luna', help='Model for the optional memory agent; leaves your default model unchanged')
    args = parser.parse_args()
    config_path = args.config.expanduser().resolve()
    binary = args.binary.expanduser().resolve()
    data_dir = args.data_dir.expanduser().resolve()
    installed = args.install_dir.expanduser().resolve() / 'instantkv'
    config = json.loads(config_path.read_text()) if config_path.exists() else {'$schema': 'https://opencode.ai/config.json'}
    # Parse before editing or copying anything. JSONC remains the user's file.
    if config_path.with_suffix('.jsonc').exists():
        parser.error('An opencode.jsonc file exists. Use --config with a separate JSON config and merge it explicitly.')
    opencode = shutil.which('opencode')
    if opencode:
        version = subprocess.run([opencode, '--version'], capture_output=True, text=True, check=False)
        match = re.search(r'\b(\d+)\.\d+(?:\.\d+)?\b', version.stdout)
        if match and int(match.group(1)) >= 2:
            parser.error('This installer supports OpenCode V1 only. Use the OpenCode V2 MCP config in docs/agents.md.')
    if isinstance(config.get('mcp'), dict) and 'servers' in config['mcp']:
        parser.error('OpenCode V2 MCP config detected. Use the OpenCode V2 MCP config in docs/agents.md.')
    if binary == (ROOT / 'target/release/instantkv').resolve():
        subprocess.run(['cargo', 'build', '--release', '--locked', '-p', 'instantkv'], cwd=ROOT, check=True)
    elif not binary.exists():
        parser.error(f'Binary not found: {binary}')
    help_result = subprocess.run([str(binary), 'mcp-local', '--help'], capture_output=True, text=True)
    if help_result.returncode:
        parser.error('Build the current binary first: cargo build --release --locked -p instantkv')
    prompt = runpy.run_path(str(ROOT / 'scripts/opencode-memory-demo.py'))['AGENT_PROMPT']
    config.setdefault('mcp', {})['instantKV'] = {
        'type': 'local', 'enabled': True, 'timeout': 15000,
        'command': [str(installed), 'mcp-local', '--dir', str(data_dir)],
    }
    agents = config.setdefault('agent', {})
    agents['memory'] = {
        'description': 'Automatic persistent memory with visible instantKV tools.',
        'mode': 'primary', 'model': args.model, 'prompt': prompt,
        'permission': {'*': 'deny', **{f'instantKV_{name}': 'allow' for name in
                       ('remember', 'recall', 'search', 'browse', 'forget')}},
    }
    # Normal build sessions get the same capture rules without losing coding tools.
    build = agents.setdefault('build', {})
    prior = build.get('prompt', '')
    if BEGIN in prior:
        start = prior.index(BEGIN)
        finish = prior.find(END, start)
        if finish == -1:
            parser.error('Incomplete existing instantKV policy block; repair the config before installing.')
        prior = prior[:start] + prior[finish + len(END):]
    build['prompt'] = prior + BEGIN + prompt.split('\n', 1)[1] + END
    build.setdefault('permission', {}).update({f'instantKV_{name}': 'allow' for name in
                                              ('remember', 'recall', 'search', 'browse', 'forget')})
    installed.parent.mkdir(parents=True, exist_ok=True)
    if binary != installed:
        # Replace atomically, so an existing running process keeps its old executable.
        with tempfile.NamedTemporaryFile(dir=installed.parent, delete=False) as handle:
            staged_binary = Path(handle.name)
        try:
            shutil.copy2(binary, staged_binary)
            staged_binary.chmod(0o755)
            os.replace(staged_binary, installed)
        finally:
            staged_binary.unlink(missing_ok=True)
    config_path.parent.mkdir(parents=True, exist_ok=True)
    if config_path.exists():
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        backup = config_path.with_name(config_path.name + '.backup-' + stamp)
        shutil.copy2(config_path, backup)
        backup.chmod(0o600)
        print(f'Previous settings: {backup}')
    with tempfile.NamedTemporaryFile(mode='w', dir=config_path.parent, delete=False) as handle:
        staged_config = Path(handle.name)
        json.dump(config, handle, indent=2)
        handle.write('\n')
    try:
        staged_config.chmod(0o600)
        os.replace(staged_config, config_path)
    finally:
        staged_config.unlink(missing_ok=True)
    print(f'Installed: {installed}')
    print(f'Memory directory: {data_dir}')
    print('Restart OpenCode. Check: opencode mcp list')
    print('For a clean recording: opencode --agent memory')


if __name__ == '__main__':
    main()
