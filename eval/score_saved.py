#!/usr/bin/env python3
"""Rescore every question from a complete saved retrieval pass; no re-ingestion."""
import argparse
from concurrent.futures import ThreadPoolExecutor,as_completed
from datetime import datetime,timezone
import json
from pathlib import Path
import subprocess
from api import EvaluationAPI
from backend import sha
from budget import BudgetExceeded
from rubrics import Rubrics
from run import confidence,write

ROOT=Path(__file__).resolve().parents[1]

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--root',type=Path,required=True)
    args=p.parse_args();original=json.loads((args.input/'report.json').read_text())
    contexts=[json.loads(x) for x in (args.input/'contexts.jsonl').open()]
    assert len(contexts)==original['expected_questions']
    assert len({r['question']['id'] for r in contexts})==len(contexts)
    config=original['config'];args.output.mkdir(parents=True,exist_ok=False)
    api=EvaluationAPI(config,'/private/tmp/instantkv-evaluation-openai.key',args.root/'api-budget.sqlite3')
    rubrics=Rubrics(args.root,api)
    report={**original,'complete':False,'phase':'qa','completed_qa_questions':0,
        'source_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        'qa_started_at':datetime.now(timezone.utc).isoformat(),'parent_report':str(args.input/'report.json'),
        'saved_contexts_sha256':sha(args.input/'contexts.jsonl'),
        'rate_policy':'Shared conservative 150K estimated TPM / 400 RPM against verified account 200K TPM / 500 RPM',
        'qa_status':'Fresh full scoring; previous burst failures retained in parent raw outputs'}
    for key in ['qa_score','qa_confidence_interval','qa_failure_rate','categories','raw_sha256']:report.pop(key,None)
    write(args.output/'report.json',report)
    rows=[]
    def answer(row):
        q=row['question'];base={'case_id':row['case_id'],'question_id':q['id'],'category':q['category'],'score':0,'failure':False}
        if row['retrieval_failure']:return base|{'failure':True,'error':'Original retrieval failed'}
        try:
            reader=api.respond(rubrics.reader_messages(q,row['context'],row['images']),'reader')
            judge=rubrics.judge(q,reader['text'])
            return base|{'reader':reader,'judgement':judge,'score':judge['score']}
        except BudgetExceeded:raise
        except Exception as error:return base|{'failure':True,'error':type(error).__name__+': '+str(error),'reader':locals().get('reader')}
    try:
        with ThreadPoolExecutor(max_workers=8) as pool,(args.output/'qa.jsonl').open('w') as raw:
            pending=[pool.submit(answer,row) for row in contexts]
            for future in as_completed(pending):
                row=future.result();rows.append(row);raw.write(json.dumps(row,ensure_ascii=False)+'\n');raw.flush()
                report.update(completed_qa_questions=len(rows),budget=api.budget.summary())
                write(args.output/'report.json',report)
                if len(rows)%10==0:print('QA',len(rows),'/',len(contexts),'failures',sum(r['failure'] for r in rows),flush=True)
        report.update(complete=True,phase='complete',qa_score=sum(r['score'] for r in rows)/len(rows),
            qa_failure_rate=sum(r['failure'] for r in rows)/len(rows),qa_confidence_interval=confidence(rows),
            categories={c:{'questions':sum(r['category']==c for r in rows),'qa_score':sum(r['score'] for r in rows if r['category']==c)/sum(r['category']==c for r in rows)} for c in {r['category'] for r in rows}},
            raw_sha256={'qa.jsonl':sha(args.output/'qa.jsonl')})
    except BaseException as error:
        report.update(complete=False,phase='failed',failure_type=type(error).__name__,failure=str(error))
        raise
    finally:write(args.output/'report.json',report)

if __name__=='__main__':main()
