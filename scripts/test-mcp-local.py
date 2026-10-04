#!/usr/bin/env python3
"""Real stdio MCP lifecycle and persistence test; no model or API key required."""
import argparse
import json
import os
from pathlib import Path
import selectors
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


class Session:
    def __init__(self, binary, directory, cwd):
        env = {k: v for k, v in os.environ.items() if not k.startswith('INSTANTKV_')}
        self.log = tempfile.TemporaryFile(mode='w+')
        self.child = subprocess.Popen([str(binary), 'mcp-local', '--dir', str(directory)],
                                      cwd=cwd, env=env, stdin=subprocess.PIPE,
                                      stdout=subprocess.PIPE, stderr=self.log, text=True, bufsize=1)
        self.sequence = 0
        self.call('initialize', {'protocolVersion': '2025-11-25', 'capabilities': {},
                                'clientInfo': {'name': 'instantkv-lifecycle-test', 'version': '1'}})
        self.send({'jsonrpc': '2.0', 'method': 'notifications/initialized'})

    def send(self, message):
        self.child.stdin.write(json.dumps(message) + '\n')
        self.child.stdin.flush()

    def call(self, method, params):
        self.sequence += 1
        self.send({'jsonrpc': '2.0', 'id': self.sequence, 'method': method, 'params': params})
        with selectors.DefaultSelector() as ready:
            ready.register(self.child.stdout, selectors.EVENT_READ)
            while True:
                assert ready.select(15), 'MCP response timed out'
                line = self.child.stdout.readline()
                assert line, 'MCP exited before responding'
                event = json.loads(line)  # Also proves init logs never pollute stdout.
                if event.get('id') == self.sequence:
                    assert 'error' not in event, event
                    return event['result']

    def tool(self, name, arguments):
        response = self.call('tools/call', {'name': name, 'arguments': arguments})
        assert not response.get('isError'), response
        return json.loads(response['content'][0]['text'])

    def close(self):
        self.child.stdin.close()
        try:
            assert self.child.wait(timeout=10) == 0
        finally:
            if self.child.poll() is None:
                self.child.kill()
                self.child.wait()
            self.child.stdout.close()
            self.log.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', type=Path, default=ROOT / 'target/release/instantkv')
    args = parser.parse_args()
    with tempfile.TemporaryDirectory() as folder:
        directory = Path(folder) / 'memory'
        first = Session(args.binary.resolve(), directory, ROOT)
        try:
            tools = {t['name'] for t in first.call('tools/list', {})['tools']}
            assert {'remember', 'recall', 'search', 'browse', 'forget'} <= tools
            first.tool('remember', {'key': 'profile/test', 'content': 'Prefer TOML configuration.', 'topic': 'profile'})
        finally:
            first.close()
        if os.name == 'posix':
            assert (directory / '.instantkv/credentials.env').stat().st_mode & 0o777 == 0o600
        second = Session(args.binary.resolve(), directory, Path(folder))
        try:
            page = second.tool('recall', {'topic': 'profile'})
            item = next(i for i in page['items'] if i['key'] == 'profile/test')
            assert item['memory']['content'] == 'Prefer TOML configuration.'
            second.tool('remember', {'key': item['key'], 'if_revision': item['revision'],
                                    'content': 'Prefer JSON configuration.', 'topic': 'profile'})
            page = second.tool('recall', {'topic': 'profile'})
            assert len(page['items']) == 1 and page['items'][0]['memory']['content'] == 'Prefer JSON configuration.'
        finally:
            second.close()
    print('PASS: native MCP initialization, tools, private credentials, EOF shutdown, restart from another cwd, durable recall and revision update.')


if __name__ == '__main__':
    main()
