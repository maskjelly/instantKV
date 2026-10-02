#!/usr/bin/env python3
"""Verify a fresh local profile and record sampled RSS on macOS/Linux."""
import argparse
import hashlib
import http.client
import json
import os
import platform
from pathlib import Path
import socket
import subprocess
import tempfile
import time
from datetime import datetime, timezone


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', default='target/release/instantkv')
    parser.add_argument('--records', type=int, default=1000)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if not 1 <= args.records <= 10000:
        parser.error('--records must be between 1 and 10000 (local knowledge quota)')
    binary = Path(args.binary).resolve()
    environment = {k: v for k, v in os.environ.items() if not k.startswith('INSTANTKV_')}
    with tempfile.TemporaryDirectory(prefix='instantkv-local-') as temporary:
        state = Path(temporary)
        subprocess.run([str(binary), 'init'], cwd=state, env=environment, check=True, capture_output=True)
        config = state / 'instantkv.toml'
        assert 'cache_size_bytes = 8388608' in config.read_text()
        with socket.socket() as reservation:
            reservation.bind(('127.0.0.1', 0))
            port = reservation.getsockname()[1]
        config.write_text(config.read_text().replace('127.0.0.1:8080', f'127.0.0.1:{port}'))
        secrets = dict(line.split('=', 1) for line in (state / '.instantkv/credentials.env').read_text().splitlines())
        headers = {'Authorization': 'Bearer ' + secrets['INSTANTKV_APP_TOKEN'], 'Content-Type': 'application/json'}
        server = None
        connection = None

        def stop():
            nonlocal server, connection
            if connection:
                connection.close()
                connection = None
            if server:
                server.kill()  # Abrupt exit verifies retained committed state.
                server.wait(timeout=10)
                server = None

        def start():
            nonlocal server, connection
            server = subprocess.Popen([str(binary), 'serve'], cwd=state, env=environment, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            for _ in range(200):
                if server.poll() is not None:
                    raise RuntimeError('local server exited during startup')
                try:
                    connection = http.client.HTTPConnection('127.0.0.1', port, timeout=10)
                    connection.request('GET', '/healthz')
                    response = connection.getresponse()
                    response.read()
                    if response.status == 200:
                        return
                except OSError:
                    if connection:
                        connection.close()
                time.sleep(0.05)
            raise RuntimeError('local server did not become healthy')

        def request(method, route, value=None):
            connection.request(method, route, body=value, headers=headers)
            response = connection.getresponse()
            body = response.read()
            if not 200 <= response.status < 300:
                raise RuntimeError(f'{method} {route}: HTTP {response.status}')
            return body

        def rss():
            return int(subprocess.check_output(['ps', '-o', 'rss=', '-p', str(server.pid)], text=True).strip()) * 1024

        try:
            start()
            idle = rss()
            samples = [idle]
            value = json.dumps({'content': 'x' * 242}, separators=(',', ':')).encode()
            first = None
            began = time.monotonic()
            for index in range(args.records):
                receipt = json.loads(request('PUT', f'/v1/namespaces/knowledge/records/local/{index}', value))
                if first is None:
                    first = receipt
                if index % 100 == 0:
                    samples.append(rss())
            seconds = time.monotonic() - began
            samples.append(rss())
            checkpoint = {
                'id': 'local-handoff', 'agent_id': 'local-agent', 'session_id': 'smoke',
                'expected_latest_revision': None,
                'capsule': {'goal': 'Keep work locally', 'summary': 'A saved fact is ready to recall.',
                            'constraints': ['Stay on device'], 'decisions': ['Use local storage'],
                            'open_tasks': ['Continue after restart'], 'next_action': 'Recall local/0'},
                'references': [{'namespace': 'knowledge', 'key': 'local/0', 'revision': first['revision']}],
            }
            request('POST', '/v1/namespaces/checkpoints/checkpoints', json.dumps(checkpoint).encode())
            request('PUT', '/v1/namespaces/scratch/records/temporary', b'{"temporary":true}')
            stop()
            start()
            for index in range(args.records):
                assert request('GET', f'/v1/namespaces/knowledge/records/local/{index}') == value
            restored = json.loads(request('GET', '/v1/namespaces/checkpoints/sessions/local-agent/smoke/latest?max_bytes=32768'))
            assert restored['checkpoint_id'] == 'local-handoff'
            assert restored['references'][0]['status'] == 'available'
            assert json.loads(request('GET', '/v1/namespaces/scratch/stats'))['entries'] == 0
            samples.append(rss())
            report = {
                'recorded_at': datetime.now(timezone.utc).isoformat(),
                'source_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
                'source_dirty': bool(subprocess.check_output(['git', 'status', '--porcelain'], text=True).strip()),
                'binary_sha256': hashlib.sha256(binary.read_bytes()).hexdigest(),
                'platform': platform.platform(), 'machine': platform.machine(),
                'rustc': subprocess.check_output(['rustc', '--version'], text=True).strip(),
                'local_config_sha256': hashlib.sha256(config.read_bytes()).hexdigest(),
                'version': subprocess.check_output([str(binary), '--version'], text=True).strip(),
                'profile': 'local', 'transport': 'sequential loopback HTTP, keep-alive',
                'binary_bytes': binary.stat().st_size,
                'idle_rss_bytes': idle, 'rss_samples_bytes': samples,
                'largest_sampled_rss_bytes': max(samples),
                'record_count': args.records, 'value_bytes': len(value),
                'durable_write_seconds': seconds, 'durable_writes_per_second': args.records / seconds,
                'exact_reads_after_kill_restart': args.records,
                'checkpoint_restored': True, 'scratch_empty_after_restart': True,
                'database_bytes': (state / '.instantkv/data/instantkv.redb').stat().st_size,
                'limits': 'Sampled RSS, not peak RSS. One host/run; not phone, energy or end-to-end LLM evidence.',
            }
            if platform.system() == 'Darwin':
                report['hardware_model'] = subprocess.check_output(['sysctl', '-n', 'hw.model'], text=True).strip()
                report['hardware_memory_bytes'] = int(subprocess.check_output(['sysctl', '-n', 'hw.memsize'], text=True).strip())
                report['cpu'] = subprocess.check_output(['sysctl', '-n', 'machdep.cpu.brand_string'], text=True).strip()
            output = json.dumps(report, indent=2) + '\n'
            if args.output:
                args.output.parent.mkdir(parents=True, exist_ok=True)
                args.output.write_text(output)
            print(output, end='')
        finally:
            stop()


if __name__ == '__main__':
    main()
