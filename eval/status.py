#!/usr/bin/env python3
"""Read live evaluation progress. Optional dashboard binds only to localhost."""
import argparse
from datetime import datetime, timezone
import html
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from pathlib import Path
import sqlite3


def snapshot(root):
    output=root/'results'
    status_path=output/'campaign-status.json'
    campaign=json.loads(status_path.read_text()) if status_path.exists() else {}
    jobs=[]
    for job in campaign.get('jobs',[]):
        path=Path(job['output'])/'report.json'
        try:report=json.loads(path.read_text())
        except (OSError,json.JSONDecodeError):report={}
        expected=report.get('expected_questions',job.get('expected_questions',0))
        job=dict(job)
        if report.get('complete'):job['status']='complete'
        elif report.get('phase')=='failed':job['status']='failed'
        job.update(phase=report.get('phase',job.get('status')),expected_questions=expected,
            retrieval_done=report.get('completed_retrieval_questions',0),
            retrieval_total=expected*report.get('retrieval_repetitions',1 if campaign.get('mode') else 3),
            qa_done=report.get('completed_qa_questions',0),
            score=report.get('qa_score') if report.get('complete') else None,
            qa_failure_rate=report.get('qa_failure_rate'),retrieval_metrics=report.get('retrieval_metrics'),
            query_latency_ms=report.get('retrieval_latency_ms'),
            error=report.get('failure'),report_path=str(path))
        if job['phase']=='retrieval' and job['retrieval_done']:
            began=datetime.fromisoformat(job['started_at'])
            elapsed=(datetime.now(timezone.utc)-began).total_seconds()
            job['retrieval_eta_minutes']=round(elapsed*(job['retrieval_total']/job['retrieval_done']-1)/60,1)
        jobs.append(job)
    budget=campaign.get('budget',{})
    ledger=root/'api-budget.sqlite3'
    if ledger.exists():
        db=sqlite3.connect('file:'+str(ledger)+'?mode=ro',uri=True)
        try:
            cap=db.execute('SELECT cap FROM policy WHERE id=1').fetchone()[0]
            spent=db.execute("SELECT COALESCE(SUM(CASE WHEN status='reserved' THEN reserved ELSE charged END),0) FROM calls").fetchone()[0]
            budget={'cap_usd':cap,'accounted_upper_usd':spent,'remaining_usd':cap-spent}
        finally:db.close()
    return {'updated_at':datetime.now(timezone.utc).isoformat(),'complete':campaign.get('complete',False),
        'planned_jobs':campaign.get('expected_total_jobs',21),'completed_jobs':sum(j['status'] in ('complete','previously_complete') for j in jobs),
        'failed_jobs':sum(j['status']=='failed' for j in jobs),'jobs':jobs,'budget':budget,
        'stop_reason':campaign.get('stop_reason')}


def text(data):
    lines=[f"Full-suite evaluation: {data['completed_jobs']}/{data['planned_jobs']} jobs complete; {data['failed_jobs']} failed"]
    b=data['budget'];lines.append(f"API accounted upper cost: ${b.get('accounted_upper_usd',0):.4f} / ${b.get('cap_usd',250):.2f}")
    for j in data['jobs']:
        line=f"{j['suite']} / {j['provider']}: {j['phase']} | retrieval {j['retrieval_done']}/{j['retrieval_total']} | QA {j['qa_done']}/{j['expected_questions']}"
        if j['score'] is not None:line+=f" | QA score {j['score']:.2%}"
        if 'retrieval_eta_minutes' in j:line+=f" | retrieval ETA ~{j['retrieval_eta_minutes']} min (QA follows)"
        if j['error']:line+=' | ERROR: '+j['error']
        lines.append(line)
    if data['stop_reason']:lines.append('STOP: '+data['stop_reason'])
    lines.append('Full reports and raw outputs: results/<suite>--<provider>/')
    return '\n'.join(lines)


def page(data):
    rows=[]
    for j in data['jobs']:
        score=f"{j['score']:.2%}" if j['score'] is not None else 'Pending'
        metric=j['retrieval_metrics'] or {};recall=f"{metric['recall_at_10']:.2%}" if 'recall_at_10' in metric else '—'
        latency=j['query_latency_ms'] or {};p95=f"{latency['p95']:.2f} ms" if 'p95' in latency else '—'
        eta=f"~{j['retrieval_eta_minutes']} min of retrieval, then QA" if 'retrieval_eta_minutes' in j else ''
        values=[j['suite'],j['provider'],j['phase'],f"{j['retrieval_done']}/{j['retrieval_total']}",f"{j['qa_done']}/{j['expected_questions']}",score,recall,p95,eta]
        rows.append('<tr>'+''.join('<td>'+html.escape(str(v))+'</td>' for v in values)+'</tr>')
        if j['error']:rows.append('<tr><td colspan="9">Error: '+html.escape(j['error'])+'</td></tr>')
    b=data['budget']
    return ('<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width"><meta http-equiv="refresh" content="10">'
        '<title>instantKV evaluation</title><style>body{font:15px system-ui;margin:40px;color:#222;background:#fafafa}h1{font-size:26px}table{border-collapse:collapse;width:100%;background:white}td,th{text-align:left;padding:12px;border-bottom:1px solid #ddd}p{line-height:1.6}.table{overflow:auto}small{color:#666}</style></head><body>'
        '<h1>instantKV evaluation</h1>'
        f"<p><strong>{data['completed_jobs']} / {data['planned_jobs']} jobs complete · {data['failed_jobs']} failed</strong><br>"
        f"API accounted upper cost: ${b.get('accounted_upper_usd',0):.4f} / ${b.get('cap_usd',250):.2f}</p>"
        '<p>GPT-6 Luna answers and judges. One QA pass per provider. The parallel profile uses one retrieval pass; the initial instantKV run retains three. Parallel timings are under shared load. Partial runs have no full-suite score.</p>'
        '<div class="table"><table><thead><tr>'+''.join('<th>'+v+'</th>' for v in ['Suite','Provider','Phase','Retrieval','QA','QA score','Recall@10','Query p95','Estimate'])+'</tr></thead><tbody>'+''.join(rows)+'</tbody></table></div>'
        '<p>Priority queue: full LongMemEval-S, LoCoMo, AMA-Bench and V2 Small, each with instantKV, SQLite FTS5 and local Supermemory. V2 Medium and BEAM large histories are deferred.</p>'
        '<p>Comparison limits: GPT-6 Luna protocol variant; SQLite latency is in process; Supermemory is its local embedding path, not its full hosted pipeline. A dash means a metric is pending or unavailable.</p>'
        '<p>The full queue can take days. V2 Medium has 447 separate corpora. Estimates depend on corpus size and provider speed.</p>'
        '<small>Refreshes every 10 seconds. Updated '+html.escape(data['updated_at'])+'</small></body></html>')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,default=Path('/private/tmp/instantkv-official-eval'))
    p.add_argument('--serve',type=int,metavar='PORT')
    p.add_argument('--json',action='store_true')
    args=p.parse_args()
    if not args.serve:
        data=snapshot(args.root);print(json.dumps(data,indent=2) if args.json else text(data));return
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path not in ('/','/status.json'):
                self.send_error(404);return
            data=snapshot(args.root)
            raw=(json.dumps(data) if self.path=='/status.json' else page(data)).encode()
            self.send_response(200);self.send_header('Content-Type','application/json' if self.path=='/status.json' else 'text/html; charset=utf-8')
            self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
        def log_message(self,*args):pass
    print(f'Live status: http://127.0.0.1:{args.serve}',flush=True)
    HTTPServer(('127.0.0.1',args.serve),Handler).serve_forever()

if __name__=='__main__':main()
