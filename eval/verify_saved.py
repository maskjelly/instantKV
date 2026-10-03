#!/usr/bin/env python3
"""Verify published full-suite rankings against official source labels with trec_eval."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import pytrec_eval


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--data-root',type=Path,required=True)
    p.add_argument('--results',type=Path,required=True)
    args=p.parse_args();receipts={}
    for file in sorted(args.results.glob('*--*.json')):
        suite=file.name.split('--')[0];rows=json.loads(file.read_text())
        if suite=='longmemeval-s':
            source=args.data_root/'longmemeval_s_cleaned.json'
            original=json.loads(source.read_text())
            qrels={q['question_id']:{sid:1 for sid in q['answer_session_ids']} for q in original}
            expected=500
        elif suite=='locomo':
            source=args.data_root/'locomo10.json';original=json.loads(source.read_text());qrels={};expected=0
            for conv in original:
                ids={turn['dia_id'] for turns in conv['conversation'].values() if isinstance(turns,list) for turn in turns}
                for i,q in enumerate(conv['qa']):
                    expected+=1
                    refs=set(ref for evidence in q.get('evidence',[]) for ref in re.findall(r'D\d+:\d+',evidence))
                    if q['category']!=5 and refs and refs<=ids:qrels[conv['sample_id']+'/'+str(i)]={ref:1 for ref in refs}
        else:raise ValueError('Unsupported published source suite')
        assert len(rows)==expected and len({r['question_id'] for r in rows})==expected
        run={r['question_id']:{sid:float(len(r['ranking'])-i) for i,sid in enumerate(r['ranking'])} for r in rows if r['question_id'] in qrels}
        assert set(run)==set(qrels)
        scores=pytrec_eval.RelevanceEvaluator(qrels,{'recall_10','ndcg_cut_10'}).evaluate(run)
        metrics={key:sum(v[key] for v in scores.values())/len(scores) for key in ['recall_10','ndcg_cut_10']}
        selected=[r for r in rows if r['question_id'] in qrels]
        for trec,stored in [('recall_10','recall_at_10'),('ndcg_cut_10','ndcg_at_10')]:
            assert abs(metrics[trec]-sum(r['metrics'][stored] for r in selected)/len(selected))<1e-12
        receipts[file.name]={'verified':True,'full_queried_questions':expected,'positive_evidence_questions':len(qrels),'metrics':metrics,
            'rankings_sha256':hashlib.sha256(file.read_bytes()).hexdigest(),'official_source_sha256':hashlib.sha256(source.read_bytes()).hexdigest()}
    output=args.results/'verification.json';output.write_text(json.dumps({'tool':'pytrec_eval','receipts':receipts},indent=2)+'\n')
    print('Verified',len(receipts),'full-suite ranking files:',output)

if __name__=='__main__':main()
