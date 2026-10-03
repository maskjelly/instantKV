#!/usr/bin/env python3
"""Run full suites in sequence; timed local measurements never overlap."""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
import subprocess
import sys
from budget import Budget

ROOT=Path(__file__).resolve().parents[1]
SUITES=['longmemeval-s','locomo','ama-bench','longmemeval-v2-small','beam','longmemeval-v2-medium','beam-10m']

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config',type=Path,default=ROOT/'eval/campaign.json')
    for name in ['data-root','sources','key-file','budget-file','output']:
        p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--providers',nargs='+',default=['instantkv','sqlite-fts5','supermemory-local'])
    args=p.parse_args();config=json.loads(args.config.read_text())
    args.output.mkdir(parents=True,exist_ok=True)
    budget=Budget(args.budget_file,config['total_api_cap_usd'])
    queue=[(suite,provider) for suite in SUITES for provider in args.providers]
    status={'config':str(args.config),'jobs':[], 'complete':False,'budget':budget.summary()}
    status_path=args.output/'campaign-status.json'
    for suite,provider in queue:
        dest=args.output/(suite+'--'+provider)
        record={'suite':suite,'provider':provider,'output':str(dest),'started_at':datetime.now(timezone.utc).isoformat()}
        if (dest/'report.json').exists():
            report=json.loads((dest/'report.json').read_text())
            if report['complete']:
                record['status']='previously_complete';status['jobs'].append(record);continue
            raise RuntimeError('Preserve incomplete evidence. Use a new campaign output directory: '+str(dest))
        record['status']='running';status['jobs'].append(record)
        status_path.write_text(json.dumps(status,indent=2)+'\n')
        cmd=[sys.executable,str(ROOT/'eval/run.py'),'--suite',suite,'--provider',provider]
        for name in ['config','data_root','sources','key_file','budget_file']:
            cmd+=['--'+name.replace('_','-'),str(getattr(args,name))]
        cmd+=['--output',str(dest)]
        print('START',suite,provider,flush=True)
        with (args.output/(suite+'--'+provider+'.log')).open('w') as log:
            result=subprocess.run(cmd,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
        report=json.loads((dest/'report.json').read_text()) if (dest/'report.json').exists() else {'complete':False,'failure_type':'NoReport','failure':'See retained job log'}
        record.update(status='complete' if report['complete'] else 'failed',returncode=result.returncode,finished_at=datetime.now(timezone.utc).isoformat())
        status['budget']=budget.summary();status_path.write_text(json.dumps(status,indent=2)+'\n')
        with (args.output/'ledger.jsonl').open('a') as ledger:
            ledger.write(json.dumps(record|{'report':report},ensure_ascii=False)+'\n')
        print(record['status'].upper(),suite,provider,flush=True)
        if report.get('failure_type')=='BudgetExceeded':
            status['stop_reason']='Shared API budget exhausted';status_path.write_text(json.dumps(status,indent=2)+'\n');return
    status['complete']=all(j['status'] in ('complete','previously_complete') for j in status['jobs'])
    status_path.write_text(json.dumps(status,indent=2)+'\n')

if __name__=='__main__':main()
