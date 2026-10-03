#!/usr/bin/env python3
"""Frozen local retrieval evaluation. No extraction, generation, tuning or paid API."""
import argparse
from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import http.client
import json
import math
import os
from pathlib import Path
import platform
import re
import socket
import subprocess
import tempfile
import time


def metrics(ranking, relevant, k):
    ranking = list(dict.fromkeys(ranking))[:k]
    gains = [relevant.get(doc, 0) for doc in ranking]
    ideal = sorted(relevant.values(), reverse=True)[:k]
    # trec_eval/BEIR uses linear relevance gains, including graded NFCorpus labels.
    dcg = sum(g/math.log2(i+2) for i, g in enumerate(gains))
    idcg = sum(g/math.log2(i+2) for i, g in enumerate(ideal))
    found = sum(g > 0 for g in gains)
    return {f'recall_at_{k}': found/len(relevant), f'ndcg_at_{k}': dcg/idcg if idcg else 0,
            f'mrr_at_{k}': next((1/(i+1) for i, g in enumerate(gains) if g > 0), 0),
            f'any_evidence_at_{k}': float(found > 0), f'all_evidence_at_{k}': float(found == len(relevant))}


def percentiles(samples):
    ordered = sorted(samples)
    return {**{f'p{p}': ordered[max(0, math.ceil(len(ordered)*p/100)-1)] for p in (50, 95, 99)},
            'samples_ms': samples}


def chunks(text):
    """Shared 9,500-character/14,000-byte maximum; preserve all source text."""
    while text:
        end = min(len(text), 9500)
        while len(text[:end].encode()) > 14000:
            end -= 1
        yield text[:end]
        text = text[end:]


def unique_ids(hits, excluded):
    return list(dict.fromkeys(doc for doc in hits if doc != excluded))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset', type=Path, required=True, help='Normalized JSON; see prepare-retrieval-suite.py')
    parser.add_argument('--instantkv-binary', type=Path, default=Path('target/release/instantkv'))
    parser.add_argument('--supermemory-binary', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--supermemory-batch', type=int, default=16)
    args = parser.parse_args()
    if not 1 <= args.supermemory_batch <= 100:
        parser.error('supermemory batch 1..100')
    dataset = json.loads(args.dataset.read_text())
    scopes = sorted({doc['scope'] for doc in dataset['documents']})
    namespaces = {scope: f'eval_{i:03d}' for i, scope in enumerate(scopes)}
    by_scope = defaultdict(list)
    for doc in dataset['documents']:
        for part, content in enumerate(chunks(doc['content'])):
            by_scope[doc['scope']].append({'id': doc['id'], 'part': part, 'content': content,
                                         'event_ms': doc.get('event_ms', 1760000000000)})
    report = {'complete': False, 'recorded_at': datetime.now(timezone.utc).isoformat(),
              'benchmark': dataset['name'], 'dataset_sha256': hashlib.sha256(args.dataset.read_bytes()).hexdigest(),
              'provenance': dataset['provenance'], 'selection': dataset['selection'],
              'documents': len(dataset['documents']), 'stored_chunks': sum(map(len, by_scope.values())),
              'test_queries': len(dataset['queries']), 'scopes': len(scopes),
              'host': {'platform': platform.platform(), 'cpu': subprocess.check_output(['sysctl', '-n', 'machdep.cpu.brand_string'], text=True).strip()},
              'source_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
              'runtime_source': subprocess.check_output(['git', 'log', '-1', '--format=%H', '--', 'crates', 'Cargo.lock', 'config/local.toml'], text=True).strip(),
              'runtime_dirty': bool(subprocess.check_output(['git', 'status', '--porcelain', '--', 'crates', 'Cargo.lock', 'config/local.toml'], text=True).strip()),
              'harness_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'methodology': {'instantkv': 'BM25 k1=1.2, b=0.75, English stemming; original query; default 20,000 postings, 1,000 candidates, 4 MiB scan and 64 KiB response caps; isolated namespace per scope; 8 MiB cache',
                  'supermemory': 'official local v0.0.8; bge-base-en-v1.5 768d; direct memories API; threshold 0; rerank false; rewriteQuery false; isolated containerTag per scope',
                  'ingestion': f'instantKV sequential one-record writes; Supermemory batches of {args.supermemory_batch} records. No comparable per-record save-latency claim. All writes complete before queries.',
                  'queries': 'original full queries; top 20 unique source IDs via bounded pages; report @5/@10/@20; default-contract HTTP 400 counts as zero; self document excluded when dataset requests it; no query adapter',
                  'limits': 'One host/run per provider. Sampled process-tree RSS, not peak. Retrieval only: no answer model/judge, extraction, multimodal processing, mobile or power measurements.'},
              'providers': {}}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    def checkpoint():
        args.output.write_text(json.dumps(report, indent=2)+'\n')
    env = {k: v for k, v in os.environ.items() if not k.startswith(('INSTANTKV_', 'SUPERMEMORY_', 'OPENAI_', 'ANTHROPIC_', 'GEMINI_', 'GROQ_', 'WORKERS_AI_'))}
    for provider, binary in [('instantkv', args.instantkv_binary.resolve()), ('supermemory', args.supermemory_binary.resolve())]:
        results = {'binary_bytes': binary.stat().st_size, 'binary_sha256': hashlib.sha256(binary.read_bytes()).hexdigest(),
                   'queries': [], 'returned_content_change_count': 0}
        report['providers'][provider] = results
        with tempfile.TemporaryDirectory(prefix='ikv-eval-'+provider+'-') as temporary:
            state = Path(temporary)
            with socket.socket() as s:
                s.bind(('127.0.0.1', 0)); port = s.getsockname()[1]
            run_env = dict(env)
            if provider == 'instantkv':
                subprocess.run([str(binary), 'init'], cwd=state, env=run_env, check=True, capture_output=True)
                # Keep local resource policies; isolate each conversation/history's corpus statistics.
                original = (state/'instantkv.toml').read_text()
                policy = original[original.index('[[namespaces]]'):original.index('[[namespaces]]', original.index('[[namespaces]]')+1)]
                principal = '\n'.join(['[[auth.principals]]', 'name = "app"', 'token_env = "INSTANTKV_APP_TOKEN"',
                    'namespaces = '+json.dumps(list(namespaces.values())), 'operations = ["get", "put", "delete", "list", "stats"]'])
                head = original[:original.index('[[auth.principals]]')].replace('127.0.0.1:8080', f'127.0.0.1:{port}')
                config = head+principal+'\n'+''.join(policy.replace('name = "knowledge"', 'name = '+json.dumps(ns)) for ns in namespaces.values())
                (state/'instantkv.toml').write_text(config)
                creds = dict(line.split('=', 1) for line in (state/'.instantkv/credentials.env').read_text().splitlines())
                token = creds['INSTANTKV_APP_TOKEN']; command = [str(binary), 'serve']
            else:
                token = None; command = [str(binary)]
                run_env.update(PORT=str(port), SUPERMEMORY_DATA_DIR=str(state/'data'), SUPERMEMORY_DISABLE_TELEMETRY='1',
                               OPENAI_API_KEY='local-unused', OPENAI_BASE_URL='http://127.0.0.1:9/v1', OPENAI_MODEL='not-configured')
            with (state/'private.log').open('w') as log:
                os.chmod(state/'private.log', 0o600)
                process = subprocess.Popen(command, cwd=state, env=run_env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
                connection = http.client.HTTPConnection('127.0.0.1', port, timeout=300)
                try:
                    for _ in range(1200):
                        if process.poll() is not None:
                            raise RuntimeError(provider+' exited at startup')
                        if provider == 'supermemory':
                            match = re.search(r'sm_[A-Za-z0-9_-]+', (state/'private.log').read_text(errors='replace'))
                            if match: token = match.group()
                        try:
                            connection.request('GET', '/healthz' if provider == 'instantkv' else '/')
                            response = connection.getresponse(); response.read()
                            if token: break
                        except OSError: connection.close()
                        time.sleep(.1)
                    else: raise RuntimeError('startup timed out')
                    headers = {'Authorization': 'Bearer '+token, 'Content-Type': 'application/json'}
                    def request(path, body):
                        began = time.perf_counter_ns()
                        connection.request('POST', path, body=json.dumps(body, separators=(',', ':')).encode(), headers=headers)
                        response = connection.getresponse(); raw = response.read()
                        return response.status, json.loads(raw), (time.perf_counter_ns()-began)/1e6
                    def rss():
                        rows = [tuple(map(int, line.split())) for line in subprocess.check_output(['ps', '-axo', 'pid=,ppid=,rss='], text=True).splitlines()]
                        descendants = {process.pid}
                        while True:
                            expanded = descendants | {pid for pid, parent, _ in rows if parent in descendants}
                            if expanded == descendants: break
                            descendants = expanded
                        return sum(size for pid, _, size in rows if pid in descendants)*1024
                    ram = [rss()]; results['post_boot_rss_bytes'] = ram[0]
                    saved = 0; began = time.perf_counter()
                    for scope, records in by_scope.items():
                        batch_size = 1 if provider == 'instantkv' else args.supermemory_batch
                        for start in range(0, len(records), batch_size):
                            batch = records[start:start+batch_size]
                            if provider == 'instantkv':
                                chunk = batch[0]
                                status, value, _ = request('/v1/namespaces/'+namespaces[scope]+'/memories', {
                                    'key': f"doc/{chunk['id']}/{chunk['part']}",
                                    'memory': {'content': chunk['content'], 'occurred_at_ms': chunk['event_ms'],
                                               'metadata': {'doc_id': chunk['id'], 'part': chunk['part']}}})
                                if not 200 <= status < 300: raise RuntimeError(f'indexing HTTP {status}')
                                assert value['memory']['content'] == chunk['content']
                            else:
                                status, value, _ = request('/v4/memories', {'containerTag': namespaces[scope], 'memories': [
                                    {'content': chunk['content'], 'metadata': {'doc_id': chunk['id'], 'part': chunk['part']}} for chunk in batch]})
                                if not 200 <= status < 300: raise RuntimeError(f'indexing HTTP {status}')
                                assert len(value['memories']) == len(batch)
                                expected = {(c['id'], c['part']): c['content'] for c in batch}
                                returned = set()
                                for memory in value['memories']:
                                    identity = (memory['metadata']['doc_id'], memory['metadata']['part'])
                                    assert identity in expected and identity not in returned
                                    returned.add(identity)
                                    results['returned_content_change_count'] += memory['memory'] != expected[identity]
                            saved += len(batch)
                            if saved % 128 < batch_size:
                                ram.append(rss()); results['saved_chunks'] = saved; checkpoint()
                                print(f'{dataset["name"]} {provider}: saved {saved}/{report["stored_chunks"]}', flush=True)
                    results.update(saved_chunks=saved, ingestion_total_ms=(time.perf_counter()-began)*1000)
                    if provider == 'instantkv': results['database_bytes'] = (state/'.instantkv/data/instantkv.redb').stat().st_size
                    def search(query):
                        began = time.perf_counter_ns(); ids = []; pages = 0; truncated = False
                        counters = {'postings_scanned': 0, 'candidates_scanned': 0, 'scanned_bytes': 0}
                        if provider == 'supermemory':
                            status, value, _ = request('/v4/search', {'containerTag': namespaces[query['scope']], 'q': query['text'],
                                'threshold': 0, 'limit': 40, 'rerank': False, 'rewriteQuery': False})
                            if not 200 <= status < 300: return [], (time.perf_counter_ns()-began)/1e6, 1, False, {}, status
                            ids = unique_ids([hit['metadata']['doc_id'] for hit in value['results']], query.get('exclude_id'))[:20]
                            return ids, (time.perf_counter_ns()-began)/1e6, 1, False, {}, status
                        body = {'query': query['text'], 'limit': 20, 'max_bytes': 65536}
                        while True:
                            status, value, _ = request('/v1/namespaces/'+namespaces[query['scope']]+'/search', body)
                            pages += 1
                            if status == 400: return [], (time.perf_counter_ns()-began)/1e6, pages, False, {}, status
                            if not 200 <= status < 300: raise RuntimeError(f'query HTTP {status}')
                            truncated |= value['truncated']
                            for name in counters: counters[name] += value[name]
                            ids = unique_ids(ids+[hit['memory']['metadata']['doc_id'] for hit in value['items']], query.get('exclude_id'))
                            if len(ids) >= 20 or not value['next_cursor']: break
                            if pages >= 100: raise RuntimeError('unexpected pagination work')
                            body['cursor'] = value['next_cursor']
                        return ids[:20], (time.perf_counter_ns()-began)/1e6, pages, truncated, counters, status
                    for query in dataset['queries'][:5]: search(query)
                    for i, query in enumerate(dataset['queries']):
                        ids, ms, pages, truncated, work, status = search(query)
                        if provider == 'supermemory' and status != 200: raise RuntimeError(f'Supermemory query HTTP {status}')
                        row = {'query_id': query['id'], 'query': query['text'], 'scope': query['scope'], 'category': query['category'],
                               'relevant': query['relevant'], 'excluded_self_id': query.get('exclude_id'),
                               'ranked_doc_ids': ids, 'latency_ms': ms, 'http_pages': pages, 'http_status': status,
                               'truncated': truncated, 'work': work}
                        for k in (5, 10, 20): row.update(metrics(ids, query['relevant'], k))
                        results['queries'].append(row)
                        if i % 100 == 0:
                            ram.append(rss()); checkpoint(); print(f'{dataset["name"]} {provider}: queried {i+1}/{report["test_queries"]}', flush=True)
                    rows = results['queries']
                    names = [k for k in rows[0] if re.match(r'(recall|ndcg|mrr|any_evidence|all_evidence)_at_', k)]
                    results['metrics'] = {name: sum(row[name] for row in rows)/len(rows) for name in names}
                    results['categories'] = {}
                    for category in sorted({row['category'] for row in rows}):
                        group = [row for row in rows if row['category'] == category]
                        results['categories'][category] = {'queries': len(group), **{name: sum(row[name] for row in group)/len(group) for name in names}}
                    accepted = [row['latency_ms'] for row in rows if row['http_status'] == 200]
                    results.update(query_latency_ms=percentiles([row['latency_ms'] for row in rows]),
                        accepted_query_latency_ms=percentiles(accepted) if accepted else None,
                        contract_rejections=sum(row['http_status'] == 400 for row in rows),
                        truncated_queries=sum(row['truncated'] for row in rows), errors=0)
                    ram.append(rss()); results.update(rss_samples_bytes=ram, largest_sampled_rss_bytes=max(ram))
                    print(provider, results['metrics'], flush=True)
                finally:
                    connection.close(); process.kill(); process.wait(timeout=10)
                    try: os.killpg(process.pid, 9)
                    except ProcessLookupError: pass
        checkpoint()
    report['complete'] = True; checkpoint()
    print('Report:', args.output, flush=True)


if __name__ == '__main__':
    main()
