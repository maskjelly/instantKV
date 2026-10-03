#!/usr/bin/env python3
"""Bounded parallel full-suite quality runs. Shared-load timing is not isolated."""
import argparse
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]

def write(path,data):
    tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(data,indent=2)+'\n');tmp.replace(path)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,required=True)
    p.add_argument('--existing-pid',type=int,required=True)
    p.add_argument('--resume-live',action='store_true')
    p.add_argument('--retry-batched-longmemeval',action='store_true')
    args=p.parse_args();root=args.root;output=root/'results'
    config=ROOT/'eval/parallel-quality.json';settings=json.loads(config.read_text())
    old=json.loads((output/'campaign-status.json').read_text())
    existing=old['jobs'][0];existing['external_pid']=args.existing_pid
    jobs=[existing]
    for suite in ['longmemeval-s','locomo','ama-bench','longmemeval-v2-small']:
        for provider in ['instantkv','sqlite-fts5','supermemory-local']:
            if suite=='longmemeval-s' and provider=='instantkv':continue
            jobs.append({'suite':suite,'provider':provider,'output':str(output/(suite+'--'+provider+'--parallel')),'status':'queued','expected_questions':settings['datasets'][suite]['questions']})
    if args.resume_live:
        jobs=old['jobs']
        for job in jobs:
            if job['status']=='running':job['external_pid']=job.get('pid',args.existing_pid)
    if args.retry_batched_longmemeval:
        jobs.insert(1,{'suite':'longmemeval-s','provider':'supermemory-local','output':str(output/'longmemeval-s--supermemory-local--batch16'),'status':'queued','expected_questions':500,'reason':'Fresh full retry with batch ingestion; interrupted one-record run retained separately'})
    status={'config':str(config),'jobs':jobs,'complete':False,'expected_total_jobs':len(jobs),
        'mode':settings['measurement_mode'],'deferred_suites':['longmemeval-v2-medium','beam','beam-10m'],'budget':old['budget']}
    live={};limits={'instantkv':2,'sqlite-fts5':3,'supermemory-local':2}
    def finish(job,returncode=None):
        path=Path(job['output'])/'report.json'
        report=json.loads(path.read_text()) if path.exists() else {'complete':False,'failure_type':'NoReport'}
        job.update(status='complete' if report.get('complete') else 'failed',finished_at=datetime.now(timezone.utc).isoformat())
        if returncode is not None:job['returncode']=returncode
        with (output/'ledger.jsonl').open('a') as ledger:ledger.write(json.dumps({'job':job,'report':report})+'\n')
        if report.get('failure_type')=='BudgetExceeded':status['stop_reason']='Shared API cap reached'
    while True:
        for index,job in enumerate(jobs):
            if job['status']!='running' or index in live:continue
            rpath=Path(job['output'])/'report.json'
            r=json.loads(rpath.read_text()) if rpath.exists() else {}
            try:os.kill(job['external_pid'],0);alive=True
            except ProcessLookupError:alive=False
            if r.get('complete') or r.get('phase')=='failed' or not alive:finish(job)
        for index,(process,log) in list(live.items()):
            if process.poll() is not None:
                log.close();finish(jobs[index],process.returncode);del live[index]
        active={provider:sum(j['provider']==provider and j['status']=='running' for j in jobs) for provider in limits}
        if not status.get('stop_reason'):
            for index,job in enumerate(jobs):
                provider=job['provider']
                if job['status']!='queued' or active[provider]>=limits[provider]:continue
                dest=Path(job['output'])
                if dest.exists():raise RuntimeError('Preserve existing evidence; destination already exists: '+str(dest))
                command=[sys.executable,str(ROOT/'eval/run.py'),'--suite',job['suite'],'--provider',provider,'--config',str(config),
                    '--data-root',str(root/'data'),'--sources',str(root),'--key-file','/private/tmp/instantkv-evaluation-openai.key',
                    '--budget-file',str(root/'api-budget.sqlite3'),'--output',str(dest)]
                log=(output/(dest.name+'.log')).open('w')
                process=subprocess.Popen(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
                live[index]=(process,log);active[provider]+=1
                job.update(status='running',pid=process.pid,started_at=datetime.now(timezone.utc).isoformat())
                print('START',job['suite'],provider,'pid',process.pid,flush=True)
        write(output/'campaign-status.json',status)
        if not live and not any(j['status']=='running' for j in jobs) and (status.get('stop_reason') or not any(j['status']=='queued' for j in jobs)):break
        time.sleep(3)
    status['complete']=all(j['status']=='complete' for j in jobs)
    write(output/'campaign-status.json',status)

if __name__=='__main__':main()
