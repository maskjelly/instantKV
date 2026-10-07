#!/usr/bin/env python3
"""Verify one-command setup, first memory, and reuse after a restart."""
import argparse
import json
import os
from pathlib import Path
import socket
import subprocess
import tempfile
import time
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', type=Path, default=ROOT / 'target/release/instantkv')
    args = parser.parse_args()
    binary = args.binary.resolve()
    environment = {key: value for key, value in os.environ.items() if not key.startswith('INSTANTKV_')}

    with tempfile.TemporaryDirectory(prefix='instantkv-first-use-') as folder:
        state = Path(folder) / 'my memory'
        with socket.socket() as reservation:
            reservation.bind(('127.0.0.1', 0))
            port = reservation.getsockname()[1]
        address = f'http://127.0.0.1:{port}'
        credentials = state / '.instantkv/credentials.env'

        def command(*arguments):
            return subprocess.run([str(binary), '--url', address, '--secrets-file',
                                   str(credentials), *arguments], cwd=folder,
                                  env=environment, check=True, text=True, capture_output=True)

        def start():
            child = subprocess.Popen([str(binary), 'start', '--dir', str(state),
                                      '--bind', f'127.0.0.1:{port}'], cwd=folder,
                                     env=environment, stdout=subprocess.DEVNULL,
                                     stderr=subprocess.PIPE, text=True)
            for _ in range(100):
                if child.poll() is not None:
                    raise AssertionError(f'start exited: {child.stderr.read()}')
                try:
                    with urlopen(address + '/healthz', timeout=1) as response:
                        if response.status == 200:
                            return child
                except OSError:
                    time.sleep(0.05)
            child.kill()
            child.wait()
            raise AssertionError('start did not become healthy')

        def stop(child):
            child.terminate()
            try:
                assert child.wait(timeout=10) == 0
            finally:
                if child.poll() is None:
                    child.kill()
                    child.wait()
                child.stderr.close()

        first = start()
        try:
            assert credentials.is_file()
            if os.name == 'posix':
                assert credentials.stat().st_mode & 0o777 == 0o600
            original_credentials = credentials.read_bytes()
            command('remember', 'Prefer Rust for local tools', '--key', 'preferences/language',
                    '--topic', 'preferences')
            search = json.loads(command('search', 'Rust local tools').stdout)
            assert any(item['key'] == 'preferences/language' for item in search['items'])
        finally:
            stop(first)

        second = start()
        try:
            assert credentials.read_bytes() == original_credentials
            search = json.loads(command('search', 'Rust local tools').stdout)
            assert any(item['key'] == 'preferences/language' for item in search['items'])
        finally:
            stop(second)
    print('PASS: first start, private credentials, save, search, restart and retained memory.')


if __name__ == '__main__':
    main()
