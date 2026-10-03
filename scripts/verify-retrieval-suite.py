#!/usr/bin/env python3
"""Verify all saved rankings with independent trec_eval. Requires pytrec-eval-terrier."""
import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import pytrec_eval

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('reports', type=Path, nargs='+')
parser.add_argument('--output', type=Path, required=True)
parser.add_argument('--datasets', type=Path, help='Normalized input directory; verify labels and source scopes too')
args = parser.parse_args()
receipt = {'scorer': 'pytrec-eval-terrier', 'version': importlib.metadata.version('pytrec-eval-terrier'), 'reports': []}
for path in args.reports:
    report = json.loads(path.read_text())
    assert report['complete']
    source = None
    if args.datasets:
        data_path = args.datasets/(path.stem+'.json')
        assert hashlib.sha256(data_path.read_bytes()).hexdigest() == report['dataset_sha256']
        source = json.loads(data_path.read_text())
        assert len(source['queries']) == report['test_queries']
        source_queries = {q['id']: q for q in source['queries']}
        source_scopes = {d['id']: d['scope'] for d in source['documents']}
    verified = {'report': path.name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'providers': {}}
    for provider, result in report['providers'].items():
        rows = result['queries']
        assert len(rows) == report['test_queries'] == len({q['query_id'] for q in rows})
        qrels = {q['query_id']: q['relevant'] for q in rows}
        if source:
            for row in rows:
                expected = source_queries[row['query_id']]
                assert row['query'] == expected['text'] and row['relevant'] == expected['relevant']
                assert row['scope'] == expected['scope'] and row['category'] == expected['category']
                assert len(set(row['ranked_doc_ids'])) == len(row['ranked_doc_ids'])
                assert expected.get('exclude_id') not in row['ranked_doc_ids']
                assert all(source_scopes[doc] == expected['scope'] for doc in row['ranked_doc_ids'])
            qrels = {q['id']: q['relevant'] for q in source['queries']}
            verified['source_inputs_verified'] = True
        values = {}
        for k in (5, 10, 20):
            evaluator = pytrec_eval.RelevanceEvaluator(qrels, {f'recall.{k}', f'ndcg_cut.{k}', 'recip_rank'})
            run = {q['query_id']: {doc: float(k-i) for i, doc in enumerate(q['ranked_doc_ids'][:k])} for q in rows}
            scores = evaluator.evaluate(run)
            assert len(scores) == len(rows)
            for trec, name in [(f'recall_{k}', f'recall_at_{k}'), (f'ndcg_cut_{k}', f'ndcg_at_{k}'), ('recip_rank', f'mrr_at_{k}')]:
                for q in rows:
                    assert abs(scores[q['query_id']][trec]-q[name]) < 1e-10, (path.name, provider, q['query_id'], name)
                mean = sum(s[trec] for s in scores.values())/len(rows)
                assert abs(mean-result['metrics'][name]) < 1e-10
                values[name] = mean
        verified['providers'][provider] = values
    receipt['reports'].append(verified)
    print(path.name, 'all query Recall/nDCG/MRR independently verified')
args.output.write_text(json.dumps(receipt, indent=2)+'\n')
