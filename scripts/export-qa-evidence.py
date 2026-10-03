#!/usr/bin/env python3
import argparse,hashlib,json,math,random
from collections import defaultdict
from pathlib import Path
r=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description='Verify and publish a completed native 500-question LongMemEval-S QA pass.')
parser.add_argument('--run-directory', type=Path, required=True)
parser.add_argument('--contexts', type=Path)
args=parser.parse_args()
d=args.run_directory
report=json.loads((d/'report.json').read_text());rows=[json.loads(x) for x in (d/'qa.jsonl').open()]
assert report['complete'] and len(rows)==500 and len({x['question_id'] for x in rows})==500
assert all(not x['failure'] for x in rows)
assert sum(x['score'] for x in rows)/500==report['qa_score']
assert all(x['reader']['model']=='gpt-6-luna' for x in rows)
assert all(c['model']=='gpt-6-luna' for x in rows for c in x['judgement']['judge_calls'])
context=args.contexts or Path(report['parent_report']).parent/'contexts.jsonl';contexts=[json.loads(x) for x in context.open()]
assert {x['question_id'] for x in rows}=={x['question']['id'] for x in contexts}
sha=lambda b:hashlib.sha256(b).hexdigest()
assert sha(context.read_bytes())==report['saved_contexts_sha256']
assert sha((d/'qa.jsonl').read_bytes())==report['raw_sha256']['qa.jsonl']
# Recompute the exact recorded source-history-cluster bootstrap.
groups=defaultdict(list)
for x in rows:groups[x['case_id']].append(x['score'])
keys=list(groups);rng=random.Random(20261004);means=[]
for _ in range(2000):
 vals=[v for k in [rng.choice(keys) for _ in keys] for v in groups[k]]
 means.append(sum(vals)/len(vals))
means.sort()
ci={'low':means[49],'high':means[1949]}
assert ci['low']==report['qa_confidence_interval']['low'] and ci['high']==report['qa_confidence_interval']['high'], (ci,report['qa_confidence_interval'])
lat=sorted(x['reader']['api_latency_ms'] for x in rows)
latency={f'p{p}':lat[math.ceil(len(lat)*p/100)-1] for p in [50,95,99]}
out=r/'docs/benchmarks/2026-10-04-full-retrieval'
for source,target in [('qa.jsonl','longmemeval-s--instantkv--qa.jsonl'),('report.json','longmemeval-s--instantkv--qa-report.json')]:
 b=(d/source).read_bytes();assert b'sk-proj-' not in b; (out/target).write_bytes(b)
summary={'schema_version':1,'complete':True,'suite':'LongMemEval-S','provider':'instantKV','questions':500,'correct':int(sum(x['score'] for x in rows)),'qa_score':report['qa_score'],'qa_failures':0,'confidence_interval':report['qa_confidence_interval'],'categories':report['categories'],'reader_model':'gpt-6-luna','judge_model':'gpt-6-luna','reasoning_effort':'medium','context_limit_tokens':16384,'max_output_tokens':4096,'reader_api_latency_ms':latency,'runtime_commit':report['runtime_commit'],'protocol':'Official LongMemEval judge rubric with GPT-6 Luna reader/judge; model variant, not official leaderboard parity. One full QA repetition. No competitor QA comparison.','scope':'Model QA from saved native retrieval contexts. External model calls are evaluation only; memory storage/retrieval remain local. Reader API timings exclude retrieval and judge calls.','verification':'Recomputed all 500 binary scores, failures, model identities and clustered bootstrap; verified question coverage against saved contexts and their hash.','raw_sha256':{name:sha((out/name).read_bytes()) for name in ['longmemeval-s--instantkv--qa.jsonl','longmemeval-s--instantkv--qa-report.json']}}
(out/'qa-summary.json').write_text(json.dumps(summary,indent=2)+'\n')
print({k:summary[k] for k in ['questions','correct','qa_score','qa_failures','reader_api_latency_ms']})
