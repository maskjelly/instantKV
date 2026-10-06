#!/usr/bin/env python3
"""Validate the contents and checksum of locally produced release archives."""
import argparse
import hashlib
from pathlib import Path
import tarfile


def verify(archive):
    expected = Path(str(archive) + '.sha256').read_text().split()[0]
    if hashlib.sha256(archive.read_bytes()).hexdigest() != expected:
        raise ValueError(f'{archive.name}: checksum mismatch')
    required = {'instantkv', 'LICENSE', 'README.md', 'BUILD.txt'}
    with tarfile.open(archive) as package:
        members = package.getmembers()
        names = [member.name for member in members]
        if len(names) != len(required) or set(names) != required:
            raise ValueError(f'{archive.name}: unexpected archive members {names}')
        if not all(member.isfile() for member in members):
            raise ValueError(f'{archive.name}: entries must be regular files')
        binary = package.getmember('instantkv')
        if binary.size == 0 or not binary.mode & 0o111:
            raise ValueError(f'{archive.name}: binary must be nonempty and executable')
        build = package.extractfile('BUILD.txt').read().decode()
        if not all(f'{field}: ' in build for field in ['Version', 'Commit', 'Platform']):
            raise ValueError(f'{archive.name}: incomplete build metadata')
    print(f'PASS: {archive.name}: checksum, four expected files, binary mode and build metadata')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archives', nargs='+', type=Path)
    args = parser.parse_args()
    for archive in args.archives:
        verify(archive)


if __name__ == '__main__':
    main()
