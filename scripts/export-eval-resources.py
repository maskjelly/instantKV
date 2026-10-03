#!/usr/bin/env python3
"""Export recorded resource samples; never rerun or estimate missing measurements."""
import argparse
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def percentiles(values):
    if not values:
        return None
    ordered = sorted(values)
    return {f'p{p}': ordered[max(0, math.ceil(len(ordered) * p / 100) - 1)] for p in (50, 95, 99)}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--results', type=Path, required=True, help='Directory containing recorded provider runs')
    parser.add_argument('--output', type=Path, default=ROOT / 'docs/benchmarks/2026-10-04-full-retrieval/runtime-metrics.json')
    args = parser.parse_args()
    summary = json.loads((ROOT / 'docs/benchmarks/2026-10-04-full-retrieval/summary.json').read_text())
    result = {'schema_version': 1, 'runtime_commit': summary['runtime_commit'], 'host': summary['host'],
              'percentile_method': 'Nearest rank over all recorded query/request samples, including failures',
              'cpu_utilization': None, 'cpu_time': None, 'energy': None,
              'scope': 'Recorded retrieval only. Shared host load; process scopes differ. No speed or RAM ratios.', 'runs': []}
    fields = ['case_id', 'repetition', 'startup_ms', 'sampled_rss_bytes', 'largest_sampled_rss_bytes',
              'rss_scope', 'saved_chunks', 'stored_content_bytes', 'database_bytes', 'index_bytes',
              'index_bytes_reason', 'write_latency_samples_ms', 'write_latency_sample_unit',
              'write_batch_sizes', 'write_throughput_per_second', 'binary_sha256', 'binary_bytes',
              'source_documents', 'normalized_documents_sha256', 'reuse_scope_note']
    for suite, providers in summary['suites'].items():
        for provider, expected in providers.items():
            directory = args.results / Path(expected['report']).parent.name
            resource_path = directory / 'resources.jsonl'
            retrieval_path = directory / 'retrieval.jsonl'
            resources = [json.loads(line) for line in resource_path.open()]
            # Iterate file lines, not str.splitlines(): source text can contain Unicode line separators.
            queries = [json.loads(line) for line in retrieval_path.open()]
            repetitions = sorted({q['repetition'] for q in queries})
            assert len(queries) == expected['all_questions'] * len(repetitions)
            assert len({q['question_id'] for q in queries}) == expected['all_questions']
            ranking_path = ROOT / 'docs/benchmarks/2026-10-04-full-retrieval' / f'{suite}--{provider}.json'
            published = json.loads(ranking_path.read_text())
            raw_rankings = {(q['question_id'], q['repetition']): q['ranking'] for q in queries}
            assert all(raw_rankings[(q['question_id'], q['repetition'])] == q['ranking'] for q in published)
            latencies = [q['retrieval']['latency_ms'] for q in queries]
            writes = [t for r in resources for t in r['write_latency_samples_ms']]
            chunks = sum(r['saved_chunks'] for r in resources)
            scope = 'Native Rust server; fresh database per corpus'
            if provider == 'sqlite-fts5':
                scope = 'In-process Python runner + SQLite; fresh database per corpus'
            elif provider == 'supermemory-local':
                scope = 'Server + descendants; cumulative corpus scopes in one suite server'
            startup_samples = [r['startup_ms'] for r in resources]
            if provider == 'supermemory-local':
                # Shared backend startup is repeated in each corpus record; count it only once.
                assert len(set(startup_samples)) == 1
                startup_samples = startup_samples[:1]
            run = {'suite': suite, 'provider': provider, 'queried_questions': expected['all_questions'],
                   'query_samples': len(queries), 'repetitions': len(repetitions), 'rss_scope': scope,
                   'query_latency_ms': percentiles(latencies), 'query_latency_samples_ms': latencies,
                   'write_latency_ms': percentiles(writes),
                   'write_latency_unit': resources[0].get('write_latency_sample_unit', 'Individual record write request'),
                   'startup_latency_ms': percentiles(startup_samples), 'startup_samples': len(startup_samples),
                   'largest_sampled_rss_bytes': max(r['largest_sampled_rss_bytes'] for r in resources),
                   'largest_database_bytes': max(r['database_bytes'] for r in resources),
                   'database_scope': 'Cumulative suite database' if provider == 'supermemory-local' else 'Largest individual corpus database',
                   'write_throughput_records_per_second': chunks / (sum(writes) / 1000) if sum(writes) else None,
                   'throughput_scope': 'Records / summed write request time; excludes startup and other overhead. Not concurrent query throughput.',
                   'failures': sum(bool(q['retrieval']['failure']) for q in queries),
                   'truncated_queries': sum(bool(q['retrieval']['truncated']) for q in queries),
                   'reduced_queries': sum(bool(q['retrieval']['query_reduced']) for q in queries),
                   'ranking_sha256': sha(ranking_path),
                   'source_sha256': {'resources.jsonl': sha(resource_path), 'retrieval.jsonl': sha(retrieval_path)},
                   'resources': [{k: r[k] for k in fields if k in r} for r in resources]}
            assert run['largest_sampled_rss_bytes'] == expected['largest_sampled_rss_bytes']
            assert run['failures'] == expected['failures'] and run['truncated_queries'] == expected['truncated_queries']
            result['runs'].append(run)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(f'Exported {len(result["runs"])} full recorded resource runs to {args.output}')

if __name__ == '__main__':
    main()
