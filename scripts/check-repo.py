#!/usr/bin/env python3
"""Check source layout, local documentation links and accidental generated files."""
import argparse
from pathlib import Path
import re
import subprocess
from urllib.parse import unquote, urlsplit

ROOT_FILES = {
    '.dockerignore', '.editorconfig', '.env.example', '.gitattributes', '.gitignore',
    'AGENTS.md', 'CHANGELOG.md', 'CONTRIBUTING.md', 'Cargo.lock', 'Cargo.toml',
    'Dockerfile', 'LICENSE', 'README.md', 'SECURITY.md', 'compose.yaml',
}
ROOT_DIRS = {'.github', 'archive', 'config', 'crates', 'docs', 'eval', 'examples', 'scripts', 'site'}
GENERATED = {'target', 'node_modules', '__pycache__', '.venv', 'venv', '.astro', '.wrangler', '.instantkv'}
SITE_GENERATED = {'assets', 'benchmark-data', 'recordings', 'examples', 'llms.txt', 'llms-full.txt'}


def source_text(text):
    """Examples contain paths and links that are intentionally not source links."""
    text = re.sub(r'(?ms)^\s*(`{3,}|~{3,})[^\n]*\n.*?^\s*\1\s*$', '', text)
    return text


def heading_ids(text):
    seen = {}
    result = set()
    for heading in re.findall(r'^#{1,6}\s+(.+?)\s*#*\s*$', source_text(text), re.M):
        heading = re.sub(r'\[([^]]+)\]\([^)]*\)', r'\1', heading)
        slug = re.sub(r'[^\w\-\s]', '', heading.lower().replace('`', '')).replace(' ', '-')
        count = seen.get(slug, 0)
        seen[slug] = count + 1
        result.add(f'{slug}-{count}' if count else slug)
    result.update(re.findall(r'\bid=["\']([^"\']+)["\']', text))
    return result


def path_errors(path):
    parts = path.parts
    errors = []
    if (len(parts) == 1 and parts[0] not in ROOT_FILES) or (len(parts) > 1 and parts[0] not in ROOT_DIRS):
        errors.append('has no place in the repository layout')
    name = path.name
    if any(p in GENERATED for p in parts) or parts[0] in {'dist', 'data', 'benchmark-results', '.build', '.tesseract-work'}:
        errors.append('generated or local runtime state is included')
    if parts[:2] == ('site', 'dist') or (parts[:2] == ('site', 'public') and len(parts) > 2 and parts[2] in SITE_GENERATED):
        errors.append('generated website output is included')
    if name in {'.DS_Store', '.tunnel-token', '.dev.vars'} or name.startswith('.dev.vars.') or name.startswith('._') or name.endswith('.pyc'):
        errors.append('machine state or private credentials are included')
    if (name == '.env' or name.startswith('.env.')) and name != '.env.example':
        errors.append('private environment file is included')
    if re.search(r'\.redb(?:\.|$)', name) or path == Path('instantkv.toml'):
        errors.append('local database or generated configuration is included')
    return errors


def link_errors(root, path):
    root = root.resolve()
    text = re.sub(r'`+[^`\n]*`+', '', source_text((root / path).read_text()))
    targets = re.findall(r'\]\((<[^>]+>|[^\s)]+)(?:\s+["\'][^\n]*?["\'])?\)', text)
    targets += re.findall(r'^\s*\[[^]]+\]:\s*(<[^>]+>|\S+)', text, re.M)
    targets += re.findall(r'\b(?:href|src)=["\']([^"\']+)["\']', text)
    errors = []
    for target in targets:
        target = target.strip('<>')
        url = urlsplit(target)
        if url.scheme or url.netloc:
            continue
        base = root if url.path.startswith('/') else (root / path).parent
        resolved = (base / unquote(url.path).lstrip('/')).resolve() if url.path else root / path
        try:
            resolved.relative_to(root)
        except ValueError:
            errors.append(f'{target}: leaves the repository')
            continue
        if not resolved.exists():
            errors.append(f'{target}: missing local target')
        elif url.fragment and resolved.suffix == '.md' and unquote(url.fragment) not in heading_ids(resolved.read_text()):
            errors.append(f'{target}: missing Markdown heading')
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    root = args.root.resolve()
    output = subprocess.check_output(['git', '-C', str(root), 'ls-files', '--cached', '--others', '--exclude-standard', '-z'])
    paths = sorted({Path(p) for p in output.decode().split('\0') if p and (root / p).is_file()})
    errors = []
    for path in paths:
        errors.extend(f'{path}: {error}' for error in path_errors(path))
        if path.suffix == '.md':
            errors.extend(f'{path}: {error}' for error in link_errors(root, path))
    if errors:
        for error in errors:
            print(error)
        raise SystemExit(1)
    print(f'Checked layout, accidental generated/private files and local Markdown links in {len(paths)} source files.')


if __name__ == '__main__':
    main()
