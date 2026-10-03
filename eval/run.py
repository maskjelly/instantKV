#!/usr/bin/env python3
"""Full frozen official-suite retrieval and GPT-6 Luna QA. No test-set tuning."""
import argparse
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import random
import shutil
import subprocess
import tempfile
import time
import traceback

from api import EvaluationAPI
from budget import BudgetExceeded
from backend import Backend, sha
from baselines import make_backend
from datasets import cases
from rubrics import Rubrics

ROOT=Path(__file__).resolve().parents[1]


def percentiles(values):
    if not values:return None
    s=sorted(values)
    return {f'p{p}':s[max(0,math.ceil(len(s)*p/100)-1)] for p in (50,95,99)}


def metrics(ranking,relevant):
    if not relevant:return None
    ids=list(dict.fromkeys(ranking));out={}
    for k in (1,5,10):
        chosen=ids[:k];out[f'recall_at_{k}']=sum(relevant.get(x,0)>0 for x in chosen)/len(relevant)
    gains=[relevant.get(x,0) for x in ids[:10]]
    ideal=sorted(relevant.values(),reverse=True)[:10]
    dcg=sum(g/math.log2(i+2) for i,g in enumerate(gains));idcg=sum(g/math.log2(i+2) for i,g in enumerate(ideal))
    out['ndcg_at_10']=dcg/idcg if idcg else 0
    out['mrr']=next((1/(i+1) for i,x in enumerate(ids) if relevant.get(x,0)>0),0)
    return out


def confidence(rows):
    groups=defaultdict(list)
    for r in rows:groups[r['case_id']].append(r['score'])
    keys=list(groups);rng=random.Random(20261004);means=[]
    if len(keys)<2:return {'low':None,'high':None,'reason':'Only one independent source history'}
    for _ in range(2000):
        drawn=[groups[rng.choice(keys)] for _ in keys]
        means.append(sum(map(sum,drawn))/sum(map(len,drawn)))
    means.sort();return {'low':means[49],'high':means[1949],'method':'95% percentile bootstrap clustered by source history; 2000 resamples, seed 20261004'}


def write(path,obj):
    tmp=Path(str(path)+'.tmp');tmp.write_text(json.dumps(obj,indent=2,ensure_ascii=False)+'\n');tmp.replace(path)


def build_context(hits,config):
    import tiktoken
    encoding=tiktoken.get_encoding('o200k_base')
    sources=[];parts=[];images=[]
    remaining=config['context_limit_tokens']
    for hit in hits:
        memory=hit['memory'];meta=memory['metadata'];identity=meta['source_id']
        if identity not in sources:
            if len(sources)==config['top_k']:continue
            sources.append(identity)
        text=f"\n[Source {identity}, part {meta['part']}]\n"+memory['content']
        encoded=encoding.encode(text,disallowed_special=())
        if len(encoded)>remaining:encoded=encoded[:remaining]
        if encoded:parts.append(encoding.decode(encoded));remaining-=len(encoded)
        if meta.get('image') and meta['image'] not in images:images.append(meta['image'])
        if remaining==0:break
    return ''.join(parts),images[:10],remaining==0


def source_files(suite,root):
    root=Path(root)
    if suite=='longmemeval-s':return [root/'longmemeval_s_cleaned.json']
    if suite=='locomo':return [root/'locomo10.json']
    if suite=='ama-bench':return [root/'ama/test/open_end_qa_set.jsonl']
    if suite in ('beam','beam-10m'):return sorted((root/suite/'data').glob('*.parquet'))
    tier=suite.rsplit('-',1)[1]
    return [root/'lme-v2/questions.jsonl',root/'lme-v2/trajectories.jsonl',root/f'lme-v2/haystacks/lme_v2_{tier}.json',root/'lme-v2/checksums.sha256']


def run(args):
    config=json.loads(args.config.read_text());destination=args.output;destination.mkdir(parents=True,exist_ok=False)
    api=EvaluationAPI(config,args.key_file,args.budget_file)
    rubrics=Rubrics(args.sources,api)
    catalog=[];count=0
    for case in cases(args.suite,args.data_root):
        catalog.append({'case_id':case['id'],'questions':len(case['questions']),'trajectory_count':case.get('trajectory_count')});count+=len(case['questions'])
    if not count:raise ValueError('Empty official dataset')
    expected=config['datasets'][args.suite].get('questions')
    if expected is not None and count!=expected:raise ValueError('Official question count mismatch')
    if config['qa_repetitions']!=1:raise ValueError('This runner supports one full QA repetition per frozen run')
    if args.suite=='longmemeval-s' and count!=500:raise ValueError('Full LongMemEval-S requires all 500 questions')
    report={'schema_version':1,'complete':False,'suite':args.suite,'provider':args.provider,
        'recorded_at':datetime.now(timezone.utc).isoformat(),'config':config,'config_sha256':sha(args.config),
        'source_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        'runtime_commit':config['runtime_commit'],'runtime_dirty':bool(subprocess.check_output(['git','status','--porcelain','--','crates','Cargo.lock'],cwd=ROOT,text=True).strip()),
        'harness_sha256':{p.name:sha(p) for p in Path(__file__).parent.glob('*.py')},
        'dataset_files':{str(p.relative_to(args.data_root)):sha(p) for p in source_files(args.suite,args.data_root)},
        'host':{'platform':platform.platform(),'cpu':subprocess.check_output(['sysctl','-n','machdep.cpu.brand_string'],text=True).strip(),'ram_bytes':int(subprocess.check_output(['sysctl','-n','hw.memsize'],text=True))},
        'expected_questions':count,'cases':catalog,'retrieval_repetitions':config['retrieval_repetitions'],
        'qa_repetitions':config['qa_repetitions'],'protocol':'Full official sources and official evaluators where available; GPT-6 Luna variant. LoCoMo additionally uses a declared matched-model judge. No official leaderboard model-parity claim.',
        'budget':api.budget.summary(),'phase':'retrieval','completed_retrieval_questions':0,'completed_qa_questions':0}
    if report['runtime_dirty']:raise ValueError('Cannot run final evaluation with dirty runtime')
    write(destination/'report.json',report)
    contexts=[];resource_rows=[];retrieval_rows=[]
    try:
        with (destination/'retrieval.jsonl').open('w') as raw, (destination/'resources.jsonl').open('w') as resources:
            for repetition in range(config['retrieval_repetitions']):
                for ci,case in enumerate(cases(args.suite,args.data_root)):
                    with tempfile.TemporaryDirectory(prefix='instantkv-official-case-') as tmp:
                        with make_backend(args.provider,tmp,config) as backend:
                            rolling=hashlib.sha256();documents=0
                            for doc in case['documents']():
                                rolling.update(json.dumps(doc,sort_keys=True,ensure_ascii=False).encode());documents+=1
                                backend.insert(doc)
                                if documents%500==0:print(args.suite,'rep',repetition+1,'case',ci+1,'stored documents',documents,flush=True)
                            for q in case['questions']:
                                value=backend.search(q['text']);ranking=list(dict.fromkeys(h['memory']['metadata']['source_id'] for h in value['hits']))[:20]
                                scored=metrics(ranking,q['relevant'])
                                row={'case_id':case['id'],'question_id':q['id'],'repetition':repetition+1,
                                    'ranking':ranking,'metrics':scored,'retrieval':value}
                                raw.write(json.dumps(row,ensure_ascii=False)+'\n');raw.flush()
                                retrieval_rows.append({k:v for k,v in row.items() if k!='retrieval'}|{k:value[k] for k in ['latency_ms','failure','truncated','query_reduced']})
                                if repetition==0:
                                    context,images,cut=build_context(value['hits'],config)
                                    if q.get('image'):images.append(q['image'])
                                    contexts.append({'case_id':case['id'],'question':q,'context':context,'images':list(dict.fromkeys(images)),
                                        'context_truncated':cut,'retrieval_ms':value['latency_ms'],'retrieval_failure':value['failure']})
                                report['completed_retrieval_questions']+=1
                            resource=backend.resources()|{'case_id':case['id'],'repetition':repetition+1,'source_documents':documents,'normalized_documents_sha256':rolling.hexdigest()}
                            resources.write(json.dumps(resource,ensure_ascii=False)+'\n');resources.flush();resource_rows.append(resource)
                    write(destination/'report.json',report)
                    print(args.suite,'retrieval',repetition+1,'case',ci+1,'/',len(catalog),'questions',report['completed_retrieval_questions'],flush=True)
        if len(contexts)!=count or len(retrieval_rows)!=count*config['retrieval_repetitions']:raise ValueError('Full suite coverage mismatch')
        with (destination/'contexts.jsonl').open('w') as f:
            for row in contexts:f.write(json.dumps(row,ensure_ascii=False)+'\n')
        report['phase']='qa';write(destination/'report.json',report)
        qa_rows=[]
        def answer(row):
            q=row['question'];result={'case_id':row['case_id'],'question_id':q['id'],'category':q['category'],
                'score':0,'failure':False,'retrieval_ms':row['retrieval_ms'],'context_truncated':row['context_truncated']}
            if row['retrieval_failure']:
                return result|{'failure':True,'error':'Retrieval failed; no answer attempted'}
            try:
                reader=api.respond(rubrics.reader_messages(q,row['context'],row['images']),'reader')
                judgement=rubrics.judge(q,reader['text'])
                return result|{'reader':reader,'judgement':judgement,'score':judgement['score'],'qa_latency_ms':row['retrieval_ms']+reader['api_latency_ms']}
            except BudgetExceeded:
                raise
            except Exception as error:
                return result|{'failure':True,'error':type(error).__name__+': '+str(error),'reader':locals().get('reader')}
        with ThreadPoolExecutor(max_workers=config['api_concurrency']) as pool,(destination/'qa.jsonl').open('w') as raw:
            pending={pool.submit(answer,row):row['question']['id'] for row in contexts}
            for future in as_completed(pending):
                row=future.result();qa_rows.append(row);raw.write(json.dumps(row,ensure_ascii=False)+'\n');raw.flush()
                report['completed_qa_questions']=len(qa_rows);report['budget']=api.budget.summary()
                write(destination/'report.json',report)
                if len(qa_rows)%25==0:print(args.suite,'QA',len(qa_rows),'/',count,'budget upper $',round(report['budget']['accounted_upper_usd'],4),flush=True)
        categorized={}
        for category in sorted({q['category'] for q in qa_rows}):
            rows=[q for q in qa_rows if q['category']==category]
            categorized[category]={'questions':len(rows),'qa_score':sum(q['score'] for q in rows)/len(rows),'failures':sum(q['failure'] for q in rows)}
        available=[x['metrics'] for x in retrieval_rows if x['metrics'] is not None]
        report.update(complete=True,phase='complete',qa_score=sum(x['score'] for x in qa_rows)/count,
            qa_confidence_interval=confidence(qa_rows),qa_failure_rate=sum(x['failure'] for x in qa_rows)/count,
            categories=categorized,retrieval_metrics={k:sum(r[k] for r in available)/len(available) for k in available[0]} if available else None,
            retrieval_metric_questions_per_repetition=len(available)//config['retrieval_repetitions'],
            unavailable_retrieval_metrics_reason=None if available else 'Suite provides QA references/rubrics, not positive source evidence qrels; no fabricated recall.',
            retrieval_latency_ms=percentiles([x['latency_ms'] for x in retrieval_rows]),
            qa_latency_ms=percentiles([x['qa_latency_ms'] for x in qa_rows if 'qa_latency_ms' in x]),
            truncation_rate=sum(x['truncated'] for x in retrieval_rows)/len(retrieval_rows),
            query_reduction_rate=sum(x['query_reduced'] for x in retrieval_rows)/len(retrieval_rows),
            retrieval_failure_rate=sum(x['failure'] for x in retrieval_rows)/len(retrieval_rows),
            resource_summary={'largest_sampled_rss_bytes':max(r['largest_sampled_rss_bytes'] for r in resource_rows),
                'write_latency_ms':percentiles([t for r in resource_rows for t in r['write_latency_samples_ms']]),
                'startup_latency_ms':percentiles([r['startup_ms'] for r in resource_rows]),
                'largest_case_database_bytes':max(r['database_bytes'] for r in resource_rows)},
            budget=api.budget.summary())
        report['raw_sha256']={p.name:sha(p) for p in destination.glob('*.jsonl')}
        write(destination/'report.json',report)
        print(args.suite,'COMPLETE',count,'QA score',report['qa_score'],flush=True)
    except BaseException as error:
        report.update(complete=False,phase='failed',failure_type=type(error).__name__,failure=str(error),budget=api.budget.summary())
        write(destination/'report.json',report);raise


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--suite',required=True);p.add_argument('--provider',default='instantkv')
    p.add_argument('--config',type=Path,default=ROOT/'eval/campaign.json')
    p.add_argument('--data-root',type=Path,required=True);p.add_argument('--sources',type=Path,required=True)
    p.add_argument('--key-file',type=Path,required=True);p.add_argument('--budget-file',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    run(p.parse_args())

if __name__=='__main__':main()
