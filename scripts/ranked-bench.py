#!/usr/bin/env python3
"""Measure ranked retrieval on BEIR SciFact. Reuse, never overwrite, the baseline."""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import http.client
import importlib.util
import json
import os
from pathlib import Path
import platform
import socket
import subprocess
import tempfile
import time

spec = importlib.util.spec_from_file_location('comparison', Path(__file__).with_name('compare-supermemory.py'))
comparison = importlib.util.module_from_spec(spec)
spec.loader.exec_module(comparison)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset', type=Path, required=True)
    parser.add_argument('--binary', type=Path, default=Path('target/release/instantkv'))
    parser.add_argument('--baseline', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    baseline = json.loads(args.baseline.read_text())
    hashes = {str(p.relative_to(args.dataset)): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in [args.dataset/'corpus.jsonl', args.dataset/'queries.jsonl', args.dataset/'qrels/test.tsv']}
    assert baseline['complete'] and hashes == baseline['dataset_hashes']
    corpus = [json.loads(line) for line in (args.dataset/'corpus.jsonl').read_text().splitlines()]
    queries = {r['_id']: r['text'] for r in map(json.loads, (args.dataset/'queries.jsonl').read_text().splitlines())}
    qrels = {}
    with (args.dataset/'qrels/test.tsv').open() as f:
        for row in csv.DictReader(f, delimiter='\t'):
            if int(row['score']) > 0:
                qrels.setdefault(row['query-id'], {})[row['corpus-id']] = int(row['score'])
    chunks = []
    for doc in corpus:
        content = doc['title']+'\n'+doc['text']
        for start in range(0, len(content), 9500):
            chunks.append({'id': doc['_id'], 'part': start//9500, 'content': content[start:start+9500]})
    binary = args.binary.resolve()
    results = {'binary_bytes': binary.stat().st_size, 'binary_sha256': hashlib.sha256(binary.read_bytes()).hexdigest()}
    report = {'complete': False, 'recorded_at': datetime.now(timezone.utc).isoformat(),
              'benchmark': 'BEIR SciFact test; local ranked BM25 retrieval', 'dataset_hashes': hashes,
              'documents': len(corpus), 'stored_chunks': len(chunks), 'test_queries': len(qrels),
              'source_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
              'source_dirty': bool(subprocess.check_output(['git', 'status', '--porcelain'], text=True).strip()),
              'host': {'platform': platform.platform(), 'cpu': subprocess.check_output(['sysctl', '-n', 'machdep.cpu.brand_string'], text=True).strip()},
              'harness_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'metric_harness_sha256': hashlib.sha256(Path(comparison.__file__).read_bytes()).hexdigest(),
              'baseline_sha256': hashlib.sha256(args.baseline.read_bytes()).hexdigest(),
              'methodology': {'transport': 'sequential authenticated loopback HTTP/1.1 keepalive',
                  'instantkv': 'local profile; BM25 k1=1.2, b=0.75; English Snowball stemming; OR terms; no query adapter, embeddings, reranking or qrels tuning',
                  'limits': 'One host/run. Supermemory results reused from the separate same-host baseline run, not rerun here. Sampled RSS, not peak; no model, phone, energy or agent-quality evaluation.'},
              'providers': {'instantkv': results, 'supermemory': baseline['providers']['supermemory']}}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    environment = {k: v for k, v in os.environ.items() if not k.startswith('INSTANTKV_')}
    with tempfile.TemporaryDirectory(prefix='instantkv-ranked-') as tmp:
        state = Path(tmp)
        subprocess.run([str(binary), 'init'], cwd=state, env=environment, check=True, capture_output=True)
        with socket.socket() as s:
            s.bind(('127.0.0.1', 0)); port = s.getsockname()[1]
        config = state/'instantkv.toml'
        config.write_text(config.read_text().replace('127.0.0.1:8080', f'127.0.0.1:{port}'))
        creds = dict(line.split('=', 1) for line in (state/'.instantkv/credentials.env').read_text().splitlines())
        headers = {'Authorization': 'Bearer '+creds['INSTANTKV_APP_TOKEN'], 'Content-Type': 'application/json'}
        proc = subprocess.Popen([str(binary), 'serve'], cwd=state, env=environment, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        connection = http.client.HTTPConnection('127.0.0.1', port, timeout=300)
        def request(method, path, body=None):
            encoded = None if body is None else json.dumps(body, separators=(',', ':')).encode()
            started = time.perf_counter_ns()
            connection.request(method, path, body=encoded, headers=headers)
            response = connection.getresponse(); raw = response.read()
            elapsed = (time.perf_counter_ns()-started)/1e6
            assert 200 <= response.status < 300, (response.status, raw[:400])
            return json.loads(raw), elapsed
        def rss():
            return int(subprocess.check_output(['ps', '-o', 'rss=', '-p', str(proc.pid)], text=True).strip())*1024
        try:
            for _ in range(300):
                if proc.poll() is not None:
                    raise RuntimeError('server exited at startup')
                try:
                    request('GET', '/healthz'); break
                except OSError:
                    connection.close(); time.sleep(.05)
            else:
                raise RuntimeError('startup timeout')
            samples = [rss()]; results['post_boot_rss_bytes'] = samples[0]
            saves = []
            for i, chunk in enumerate(chunks):
                value, ms = request('POST', '/v1/namespaces/knowledge/memories', {
                    'key': f"scifact/{chunk['id']}/{chunk['part']}",
                    'memory': {'content': chunk['content'], 'topic': 'scifact', 'tags': [],
                               'metadata': {'doc_id': chunk['id'], 'part': chunk['part']}, 'occurred_at_ms': 1760000000000+i}})
                assert value['memory']['content'] == chunk['content']
                saves.append(ms)
                if i % 250 == 0:
                    samples.append(rss()); print(f'saved {i+1}/{len(chunks)}', flush=True)
            results.update(saved_chunks=len(chunks), save_latency_ms=comparison.stats(saves),
                           database_bytes=(state/'.instantkv/data/instantkv.redb').stat().st_size)
            def search(query):
                value, ms = request('POST', '/v1/namespaces/knowledge/search', {
                    'query': query, 'topic': 'scifact', 'limit': 10, 'max_bytes': 65536})
                assert not value['truncated'], 'evaluation requires complete scoring work'
                ids = list(dict.fromkeys(item['memory']['metadata']['doc_id'] for item in value['items']))
                return ids, ms, {k: value[k] for k in ['postings_scanned', 'candidates_scanned', 'scanned_bytes', 'truncated']}
            ordered = sorted(qrels, key=int)
            for qid in ordered[:5]: search(queries[qid])
            evaluated = []
            for i, qid in enumerate(ordered):
                ids, ms, work = search(queries[qid])
                evaluated.append({'query_id': qid, 'query': queries[qid], 'ranked_doc_ids': ids,
                                  'latency_ms': ms, 'work': work, **comparison.metric(ids, qrels[qid])})
                if i % 50 == 0:
                    samples.append(rss()); print(f'queried {i+1}/{len(ordered)}', flush=True)
            results['scifact'] = {'metrics': {k: sum(row[k] for row in evaluated)/len(evaluated)
                for k in ['recall_at_10', 'ndcg_at_10', 'mrr_at_10']},
                'query_latency_ms': comparison.stats([row['latency_ms'] for row in evaluated]), 'queries': evaluated}
            titles = []
            for doc in corpus[::max(1, len(corpus)//100)][:100]:
                query = ' '.join(doc['title'].split()[:3])[:200]
                ids, ms, work = search(query)
                titles.append({'doc_id': doc['_id'], 'query': query, 'ranked_doc_ids': ids,
                               'hit_at_10': doc['_id'] in ids, 'latency_ms': ms, 'work': work})
            results['title_lookup'] = {'hit_at_10': sum(row['hit_at_10'] for row in titles)/len(titles),
                                      'query_latency_ms': comparison.stats([row['latency_ms'] for row in titles]), 'queries': titles}
            samples.append(rss())
            results.update(rss_samples_bytes=samples, largest_sampled_rss_bytes=max(samples), errors=0)
        finally:
            connection.close(); proc.kill(); proc.wait(timeout=10)
    report['complete'] = True
    args.output.write_text(json.dumps(report, indent=2)+'\n')
    print(results['scifact']['metrics'], flush=True)
    print('Report:', args.output, flush=True)


if __name__ == '__main__':
    main()
