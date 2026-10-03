#!/usr/bin/env python3
"""Independently score stored rankings with trec_eval (pip install pytrec-eval-terrier)."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import pytrec_eval

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--report', type=Path, required=True)
parser.add_argument('--dataset', type=Path, required=True)
args = parser.parse_args()
report = json.loads(args.report.read_text())
assert report['complete']
for name, digest in report['dataset_hashes'].items():
    assert hashlib.sha256((args.dataset/name).read_bytes()).hexdigest() == digest
qrels = {}
with (args.dataset/'qrels/test.tsv').open() as f:
    for row in csv.DictReader(f, delimiter='\t'):
        qrels.setdefault(row['query-id'], {})[row['corpus-id']] = int(row['score'])
evaluator = pytrec_eval.RelevanceEvaluator(qrels, {'recall.10', 'ndcg_cut.10', 'recip_rank'})
for provider, results in report['providers'].items():
    queries = results['scifact']['queries']
    assert len(queries) == report['test_queries']
    assert len({q['query_id'] for q in queries}) == len(queries)
    run = {q['query_id']: {doc: float(10-i) for i, doc in enumerate(
        list(dict.fromkeys(q['ranked_doc_ids']))[:10])} for q in queries}
    scores = evaluator.evaluate(run)
    assert len(scores) == len(queries)
    mapping = {'recall_10': 'recall_at_10', 'ndcg_cut_10': 'ndcg_at_10', 'recip_rank': 'mrr_at_10'}
    for trec_name, name in mapping.items():
        mean = sum(s[trec_name] for s in scores.values())/len(scores)
        assert abs(mean-results['scifact']['metrics'][name]) < 1e-10
        for query in queries:
            assert abs(scores[query['query_id']][trec_name]-query[name]) < 1e-10
        print(f'{provider}: {name}={mean:.12f}; independently verified')
