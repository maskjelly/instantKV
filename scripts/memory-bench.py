#!/usr/bin/env python3
"""Measure structured-memory HTTP retrieval and verify all records after abrupt restart.

Fresh local profile per run. No model, internet request or third-party Python package.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import http.client
import importlib.util
import json
import math
import os
from pathlib import Path
import platform
import socket
import subprocess
import tempfile
import time
from urllib.parse import urlencode


def percentiles(samples):
    ordered = sorted(samples)
    return {**{f'p{p}': ordered[max(0, math.ceil(len(ordered)*p/100)-1)] for p in [50, 95, 99]},
            'samples': samples}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', default='target/release/instantkv')
    parser.add_argument('--records', type=int, default=10000)
    parser.add_argument('--runs', type=int, default=3)
    parser.add_argument('--queries', type=int, default=300)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if not 100 <= args.records <= 10000 or not 1 <= args.runs <= 10 or not 10 <= args.queries <= 10000:
        parser.error('records 100..10000, runs 1..10, queries 10..10000')
    binary = Path(args.binary).resolve()
    source_commit = subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
    runtime_source = subprocess.check_output(['git','log','-1','--format=%H','--',
        'crates/instantkv-core/src','crates/instantkv/src'],text=True).strip()
    environment = {k: v for k, v in os.environ.items() if not k.startswith('INSTANTKV_')}
    base_time = 1760000000000  # Synthetic event time, independent of benchmark wall clock.
    spec = importlib.util.spec_from_file_location('local_llm',Path(__file__).resolve().parents[1]/'examples/local-llm.py')
    local_llm = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(local_llm)
    runs = []
    for iteration in range(1, args.runs+1):
        with tempfile.TemporaryDirectory(prefix='instantkv-memory-') as temporary:
            state = Path(temporary)
            subprocess.run([str(binary), 'init'], cwd=state, env=environment, check=True, capture_output=True)
            config = state / 'instantkv.toml'
            with socket.socket() as reservation:
                reservation.bind(('127.0.0.1', 0))
                port = reservation.getsockname()[1]
            config.write_text(config.read_text().replace('127.0.0.1:8080', f'127.0.0.1:{port}'))
            secrets = dict(line.split('=', 1) for line in (state / '.instantkv/credentials.env').read_text().splitlines())
            headers = {'Authorization': 'Bearer '+secrets['INSTANTKV_APP_TOKEN'], 'Content-Type':'application/json'}
            server, connection = None, None

            def stop():
                nonlocal server, connection
                if connection:
                    connection.close()
                    connection = None
                if server:
                    server.kill()
                    server.wait(timeout=10)
                    server = None

            def start():
                nonlocal server, connection
                server = subprocess.Popen([str(binary), 'serve'], cwd=state, env=environment,
                                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                for _ in range(200):
                    if server.poll() is not None:
                        raise RuntimeError('server exited during startup')
                    try:
                        connection = http.client.HTTPConnection('127.0.0.1', port, timeout=15)
                        connection.request('GET', '/healthz')
                        response = connection.getresponse()
                        response.read()
                        if response.status == 200:
                            return
                    except OSError:
                        if connection:
                            connection.close()
                    time.sleep(0.05)
                raise RuntimeError('server startup timed out')

            def request(method, route, value=None):
                body = None if value is None else json.dumps(value, separators=(',', ':')).encode()
                began = time.perf_counter_ns()
                connection.request(method, route, body=body, headers=headers)
                response = connection.getresponse()
                raw = response.read()
                elapsed_ms = (time.perf_counter_ns()-began)/1e6
                if not 200 <= response.status < 300:
                    raise RuntimeError(f'{method}: HTTP {response.status}: {raw.decode()}')
                return (json.loads(raw) if raw else None), elapsed_ms, len(raw)

            def rss():
                return int(subprocess.check_output(['ps', '-o', 'rss=', '-p', str(server.pid)], text=True).strip())*1024

            def content(index):
                return f'entry-{index:06d}: Prefer Rust for local tools. '.ljust(512, 'x')

            def recall(params):
                value, ms, size = request('GET', '/v1/namespaces/knowledge/memories?'+urlencode(params))
                assert size <= int(params.get('max_bytes', 16384))
                assert value['scanned'] <= 1000
                assert value['scanned_bytes'] <= 4194304
                return value, ms, size

            try:
                start()
                idle = rss()
                rss_samples = [idle]
                saves = []
                expected = {}
                for index in range(args.records):
                    value, ms, _ = request('POST', '/v1/namespaces/knowledge/memories', {
                        'key':f'entries/{index:06d}', 'memory': {
                            'content':content(index), 'topic':f'topic-{index%20}', 'tags':[f'tag-{index%4}'],
                            'metadata':{'source':'synthetic','index':index}, 'occurred_at_ms':base_time+index,
                        },
                    })
                    assert value['memory']['content'] == content(index)
                    expected[index] = value
                    saves.append(ms)
                    if index % 500 == 0:
                        rss_samples.append(rss())
                queries = {
                    'browse':{}, 'topic':{'topic':'topic-3'}, 'tag':{'tag':'tag-1'},
                    'time':{'since_ms':base_time+args.records-40, 'until_ms':base_time+args.records-1},
                    'combined':{'topic':'topic-3','tag':'tag-3','query':'Rust local'},
                    'keyword_first_page':{'query':'entry-000000'},
                }
                timings = {}
                for name, filters in queries.items():
                    params = {**filters, 'limit':10, 'max_bytes':16384}
                    # Warmup is excluded. This is a warm-cache, sequential workload.
                    for _ in range(20):
                        recall(params)
                    samples = []
                    max_scanned, max_size = 0, 0
                    for _ in range(args.queries):
                        page, ms, size = recall(params)
                        for item in page['items']:
                            if 'topic' in filters:
                                assert item['memory']['topic'] == filters['topic']
                            if 'tag' in filters:
                                assert filters['tag'] in item['memory']['tags']
                            if 'since_ms' in filters:
                                assert filters['since_ms'] <= item['memory']['occurred_at_ms'] <= filters['until_ms']
                        if name == 'keyword_first_page':
                            if args.records > 1000:
                                assert not page['items'] and page['next_cursor'] is not None
                            else:
                                assert len(page['items']) == 1
                        samples.append(ms)
                        max_scanned = max(max_scanned, page['scanned'])
                        max_size = max(max_size, size)
                    timings[name] = {'filters':params, 'latency_ms':percentiles(samples),
                                     'max_scanned_candidates':max_scanned, 'max_response_bytes':max_size}
                    rss_samples.append(rss())
                before_restart = rss()
                stop()
                start()
                seen = set()
                params = {'limit':50,'max_bytes':65536}
                while True:
                    page, _, _ = recall(params)
                    for item in page['items']:
                        index = item['memory']['metadata']['index']
                        assert item == expected[index]
                        assert item['key'] == f'entries/{index:06d}' and index not in seen
                        assert item['memory']['content'] == content(index)
                        assert item['memory']['topic'] == f'topic-{index%20}'
                        assert item['memory']['tags'] == [f'tag-{index%4}']
                        assert item['memory']['occurred_at_ms'] == base_time+index
                        seen.add(index)
                    if page['next_cursor'] is None:
                        break
                    params['cursor'] = page['next_cursor']
                assert len(seen) == args.records
                # Continue a sparse keyword scan until the oldest memory is found.
                params = {'query':'entry-000000','limit':10}
                sparse_pages, found = 0, []
                while True:
                    page, _, _ = recall(params)
                    sparse_pages += 1
                    found.extend(item['key'] for item in page['items'])
                    if page['next_cursor'] is None:
                        break
                    params['cursor'] = page['next_cursor']
                assert found == ['entries/000000']
                exact_reads = []
                deletes = []
                for index in range(args.queries):
                    index %= args.records
                    route = '/v1/namespaces/knowledge/memories/'+f'entries/{index:06d}'
                    item, ms, _ = request('GET', route)
                    assert item == expected[index]
                    exact_reads.append(ms)
                deleted = set()
                for index in range(min(args.queries, args.records)):
                    route = '/v1/namespaces/knowledge/memories/'+f'entries/{index:06d}'
                    headers['If-Match'] = '"'+str(expected[index]['revision'])+'"'
                    _, ms, _ = request('DELETE', route)
                    deletes.append(ms)
                    deleted.add(index)
                del headers['If-Match']
                remaining = set()
                params = {'limit':50,'max_bytes':65536}
                while True:
                    page, _, _ = recall(params)
                    remaining.update(item['memory']['metadata']['index'] for item in page['items'])
                    if page['next_cursor'] is None:
                        break
                    params['cursor'] = page['next_cursor']
                assert remaining == set(expected)-deleted
                # Separately verify the real MCP bridge used by the model example.
                # No inference run, no mutations, and not included in HTTP timings.
                bridge = local_llm.MemoryBridge(str(binary),f'http://127.0.0.1:{port}',state/'.instantkv/credentials.env')
                try:
                    result = bridge.invoke('recall',{'topic':'topic-3','limit':1})
                    assert result['items'][0]['memory']['topic'] == 'topic-3'
                finally:
                    bridge.close()
                rss_samples.append(rss())
                runs.append({'iteration':iteration, 'record_count':args.records, 'content_bytes':512,
                             'topic_count':20,'tag_count':4, 'queries_per_workload':args.queries,
                             'save_latency_ms':percentiles(saves), 'queries':timings,
                             'exact_read_latency_ms':percentiles(exact_reads),
                             'forget_latency_ms':percentiles(deletes),
                             'verified_deleted_memories':len(deleted),
                             'verified_remaining_memories':len(remaining),
                             'idle_rss_bytes':idle,'before_restart_rss_bytes':before_restart,
                             'rss_samples_bytes':rss_samples, 'largest_sampled_rss_bytes':max(rss_samples),
                             'database_bytes':(state/'.instantkv/data/instantkv.redb').stat().st_size,
                             'exact_memories_after_kill_restart':len(seen), 'sparse_keyword_pages':sparse_pages,
                             'mcp_bridge_verified':True,
                             'errors':0})
                print(f'Run {iteration}: {args.records} exact memories recovered; topic p95 {timings["topic"]["latency_ms"]["p95"]:.3f} ms', flush=True)
            finally:
                stop()
    report = {'schema_version':1, 'recorded_at':datetime.now(timezone.utc).isoformat(),
              'source_commit':source_commit, 'runtime_source':runtime_source,
              'source_dirty':bool(subprocess.check_output(['git','status','--porcelain'],text=True).strip()),
              'runtime_dirty':bool(subprocess.check_output(['git','status','--porcelain','--',
                  'crates','Cargo.lock','config/local.toml'],text=True).strip()),
              'harness_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'binary_sha256':hashlib.sha256(binary.read_bytes()).hexdigest(),
              'binary_bytes':binary.stat().st_size, 'platform':platform.platform(), 'machine':platform.machine(),
              'rustc':subprocess.check_output(['rustc','--version'],text=True).strip(),
              'version':subprocess.check_output([str(binary),'--version'],text=True).strip(),
              'profile':'local', 'transport':'authenticated sequential loopback HTTP/1.1 keep-alive, concurrency 1',
              'durability':'immediate commits; records and secondary indexes share a transaction',
              'cache':'20 warmup queries per workload; warm OS/database cache', 'runs':runs,
              'limits':'One host; sampled RSS, not peak RSS. Synthetic 512-byte content plus envelope/metadata. Keyword timing is one bounded page, not complete search. Excludes model, inference, mobile devices, energy use and power-loss recovery.'}
    if platform.system() == 'Darwin':
        report['cpu'] = subprocess.check_output(['sysctl','-n','machdep.cpu.brand_string'],text=True).strip()
        report['hardware_model'] = subprocess.check_output(['sysctl','-n','hw.model'],text=True).strip()
        report['hardware_memory_bytes'] = int(subprocess.check_output(['sysctl','-n','hw.memsize'],text=True).strip())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2)+'\n')
    print(f'Report: {args.output}')


if __name__ == '__main__':
    main()
