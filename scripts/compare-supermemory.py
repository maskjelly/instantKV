#!/usr/bin/env python3
"""Local BEIR SciFact retrieval comparison. No paid API or generation model.

Requires a separately downloaded, checksum-verified Supermemory local binary.
Only its direct-memory API is used; extraction/reranking/query rewriting are off.
"""
import argparse
import csv
import difflib
from datetime import datetime, timezone
import hashlib
import http.client
import json
import math
import os
from pathlib import Path
import platform
import re
import socket
import subprocess
import tempfile
import time
import urllib.parse


def stats(values):
    ordered = sorted(values)
    return {**{f'p{p}': ordered[max(0, math.ceil(len(ordered)*p/100)-1)]
               for p in (50, 95, 99)}, 'samples_ms': values}


def metric(ranking, relevant):
    ranking = list(dict.fromkeys(ranking))[:10]
    found = [relevant.get(doc, 0) for doc in ranking]
    ideal = sorted(relevant.values(), reverse=True)[:10]
    dcg = sum((2**gain-1)/math.log2(i+2) for i, gain in enumerate(found))
    idcg = sum((2**gain-1)/math.log2(i+2) for i, gain in enumerate(ideal))
    return {'recall_at_10': sum(g > 0 for g in found)/len(relevant),
            'ndcg_at_10': dcg/idcg if idcg else 0,
            'mrr_at_10': next((1/(i+1) for i, g in enumerate(found) if g > 0), 0)}


def keyword_adapter(query):
    # Fixed before evaluation. No qrels, corpus statistics, models or tuning.
    stop = set('a an the of in on at to for by with and or is are was were be '
               'been being that this these those as from it its'.split())
    terms = [t for t in re.findall(r'[A-Za-z0-9]+', query.lower()) if t not in stop]
    return ' '.join(terms[:8])[:256]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset', type=Path, required=True)
    parser.add_argument('--supermemory-binary', type=Path, required=True)
    parser.add_argument('--instantkv-binary', type=Path, default=Path('target/release/instantkv'))
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    corpus = [json.loads(line) for line in (args.dataset/'corpus.jsonl').read_text().splitlines()]
    all_queries = {r['_id']: r['text'] for r in
                   (json.loads(line) for line in (args.dataset/'queries.jsonl').read_text().splitlines())}
    qrels = {}
    with (args.dataset/'qrels/test.tsv').open() as f:
        for row in csv.DictReader(f, delimiter='\t'):
            if int(row['score']) > 0:
                qrels.setdefault(row['query-id'], {})[row['corpus-id']] = int(row['score'])
    queries = [(qid, all_queries[qid]) for qid in sorted(qrels, key=int)]
    chunks = []
    for doc in corpus:
        content = doc['title']+'\n'+doc['text']
        # Preserve all text. Split at a shared limit below Supermemory's 10k chars.
        for start in range(0, len(content), 9500):
            chunks.append({'id':doc['_id'], 'part':start//9500, 'content':content[start:start+9500]})
    report = {'complete':False, 'recorded_at':datetime.now(timezone.utc).isoformat(),
              'benchmark':'BEIR SciFact test; local direct-memory retrieval',
              'dataset_url':'https://public.ukp.informatik.tu-darmstadt.de/thakur/BEIR/datasets/scifact.zip',
              'dataset_hashes':{str(p.relative_to(args.dataset)):hashlib.sha256(p.read_bytes()).hexdigest()
                                for p in [args.dataset/'corpus.jsonl', args.dataset/'queries.jsonl', args.dataset/'qrels/test.tsv']},
              'documents':len(corpus), 'stored_chunks':len(chunks), 'test_queries':len(queries),
              'host':{'platform':platform.platform(), 'cpu':subprocess.check_output(['sysctl','-n','machdep.cpu.brand_string'],text=True).strip()},
              'source_commit':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
              'harness_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'methodology':{'transport':'sequential authenticated loopback HTTP/1.1 keepalive',
                'top_k':10, 'supermemory':'v0.0.8; local bge-base-en-v1.5 768d; direct /v4/memories; threshold 0; no rerank or query rewrite',
                'instantkv':'default local profile; literal AND; first eight non-stopword alphanumeric query tokens; newest-first; paginate until 10 hits or exhaustion',
                'limits':'Retrieval benchmark, not agent/model accuracy, phone performance, extraction quality or power-loss test. One run. RSS sums each server and its descendant processes; sampled, not peak. Two source documents are split without truncation. InstantKV adapter is not semantic ranking.'},
              'providers':{}}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    binaries = {'supermemory':args.supermemory_binary.resolve(), 'instantkv':args.instantkv_binary.resolve()}
    env = {k:v for k,v in os.environ.items() if not k.startswith(('INSTANTKV_', 'SUPERMEMORY_', 'OPENAI_', 'ANTHROPIC_', 'GEMINI_', 'GROQ_', 'WORKERS_AI_'))}

    for provider in ('instantkv', 'supermemory'):
        binary = binaries[provider]
        results = {'binary_bytes':binary.stat().st_size, 'binary_sha256':hashlib.sha256(binary.read_bytes()).hexdigest()}
        report['providers'][provider] = results
        with tempfile.TemporaryDirectory(prefix=f'ikv-compare-{provider}-') as tmp:
            state = Path(tmp)
            with socket.socket() as s:
                s.bind(('127.0.0.1', 0)); port = s.getsockname()[1]
            run_env = dict(env)
            if provider == 'instantkv':
                subprocess.run([str(binary), 'init'], cwd=state, env=run_env, check=True, capture_output=True)
                config = state/'instantkv.toml'
                config.write_text(config.read_text().replace('127.0.0.1:8080', f'127.0.0.1:{port}'))
                creds = dict(l.split('=',1) for l in (state/'.instantkv/credentials.env').read_text().splitlines())
                key = creds['INSTANTKV_APP_TOKEN']
                command = [str(binary),'serve']
            else:
                run_env.update(PORT=str(port), SUPERMEMORY_DATA_DIR=str(state/'data'),
                    SUPERMEMORY_DISABLE_TELEMETRY='1', OPENAI_API_KEY='local-unused',
                    OPENAI_BASE_URL='http://127.0.0.1:9/v1', OPENAI_MODEL='not-configured')
                key = None
                command = [str(binary)]
            with (state/'private.log').open('w') as log:
                os.chmod(state/'private.log', 0o600)
                began = time.perf_counter()
                proc = subprocess.Popen(command,cwd=state,env=run_env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
                connection = http.client.HTTPConnection('127.0.0.1',port,timeout=300)
                try:
                    for _ in range(1200):
                        if proc.poll() is not None:
                            raise RuntimeError(f'{provider} exited at startup; inspect private log locally')
                        if provider == 'supermemory':
                            match = re.search(r'sm_[A-Za-z0-9_-]+',(state/'private.log').read_text(errors='replace'))
                            if match: key = match.group()
                        try:
                            connection.request('GET','/healthz' if provider=='instantkv' else '/')
                            response=connection.getresponse();response.read()
                            if key: break
                        except OSError: connection.close()
                        time.sleep(0.1)
                    else: raise RuntimeError('startup deadline exceeded')
                    results['startup_to_http_ms']=(time.perf_counter()-began)*1000
                    headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'}
                    def request(method, path, body=None):
                        encoded=None if body is None else json.dumps(body,separators=(',',':')).encode()
                        start=time.perf_counter_ns()
                        connection.request(method,path,body=encoded,headers=headers)
                        r=connection.getresponse();raw=r.read();elapsed=(time.perf_counter_ns()-start)/1e6
                        value=json.loads(raw) if raw else None
                        if not 200<=r.status<300: raise RuntimeError(f'{provider} HTTP {r.status}: {str(value)[:400]}')
                        return value,elapsed
                    def rss():
                        rows = [tuple(map(int, line.split())) for line in subprocess.check_output(
                            ['ps','-axo','pid=,ppid=,rss='],text=True).splitlines()]
                        descendants = {proc.pid}
                        while True:
                            expanded = descendants | {pid for pid, parent, _ in rows if parent in descendants}
                            if expanded == descendants: break
                            descendants = expanded
                        return sum(size for pid, _, size in rows if pid in descendants)*1024
                    rss_samples=[rss()]
                    results['post_boot_rss_bytes']=rss_samples[0]
                    print(f'{provider}: started, {len(chunks)} chunks to save',flush=True)
                    # Sequential one-memory calls measure searchable completion, not queue ACKs.
                    saves=[]
                    results['returned_content_changes']=[]
                    for i,chunk in enumerate(chunks):
                        if provider=='instantkv':
                            value,ms=request('POST','/v1/namespaces/knowledge/memories',{'key':f"scifact/{chunk['id']}/{chunk['part']}",
                                'memory':{'content':chunk['content'],'topic':'scifact','tags':[],
                                          'metadata':{'doc_id':chunk['id'],'part':chunk['part']},'occurred_at_ms':1760000000000+i}})
                            assert value['memory']['content']==chunk['content']
                        else:
                            value,ms=request('POST','/v4/memories',{'containerTag':'scifact-comparison','memories':[
                                {'content':chunk['content'],'metadata':{'doc_id':chunk['id'],'part':chunk['part']}}]})
                            assert len(value['memories'])==1
                            returned=value['memories'][0]['memory']
                            assert value['memories'][0]['metadata']['doc_id']==chunk['id']
                            if returned!=chunk['content']:
                                changes=[{'operation':tag,'input':chunk['content'][a:b],'returned':returned[c:d]}
                                    for tag,a,b,c,d in difflib.SequenceMatcher(None,chunk['content'],returned).get_opcodes()
                                    if tag!='equal']
                                results['returned_content_changes'].append({'doc_id':chunk['id'],'part':chunk['part'],
                                    'input_sha256':hashlib.sha256(chunk['content'].encode()).hexdigest(),
                                    'returned_sha256':hashlib.sha256(returned.encode()).hexdigest(),'changes':changes})
                        saves.append(ms)
                        if i%100==0:
                            rss_samples.append(rss());print(f'{provider}: saved {i+1}/{len(chunks)}',flush=True)
                        if i%250==0:
                            results.update(saved_chunks=i+1,save_latency_ms=stats(saves),rss_samples_bytes=rss_samples)
                            args.output.write_text(json.dumps(report,indent=2)+'\n')
                    results.update(saved_chunks=len(chunks),save_latency_ms=stats(saves))
                    def search(query,adapt=True):
                        start=time.perf_counter_ns()
                        if provider=='supermemory':
                            value,_=request('POST','/v4/search',{'containerTag':'scifact-comparison','q':query,
                                'threshold':0,'limit':10,'rerank':False,'rewriteQuery':False})
                            ids=[hit['metadata']['doc_id'] for hit in value['results']]
                            return ids,(time.perf_counter_ns()-start)/1e6,1
                        params={'topic':'scifact','query':keyword_adapter(query) if adapt else query,'limit':10,'max_bytes':65536}
                        ids=[];pages=0
                        while True:
                            value,_=request('GET','/v1/namespaces/knowledge/memories?'+urllib.parse.urlencode(params))
                            pages+=1
                            ids.extend(hit['memory']['metadata']['doc_id'] for hit in value['items'])
                            ids=list(dict.fromkeys(ids))
                            if len(ids)>=10 or not value['next_cursor']: break
                            params['cursor']=value['next_cursor'];params['limit']=10-len(ids)
                        return ids[:10],(time.perf_counter_ns()-start)/1e6,pages
                    # Untimed first queries trigger embedding initialization and warm caches.
                    for _,q in queries[:5]: search(q)
                    evaluated=[]
                    for i,(qid,q) in enumerate(queries):
                        ids,ms,pages=search(q)
                        evaluated.append({'query_id':qid,'query':q,'effective_query':keyword_adapter(q) if provider=='instantkv' else q,
                                          'ranked_doc_ids':ids,'latency_ms':ms,'http_pages':pages,**metric(ids,qrels[qid])})
                        if i%50==0: rss_samples.append(rss());print(f'{provider}: queried {i+1}/{len(queries)}',flush=True)
                    results['scifact']={'metrics':{name:sum(r[name] for r in evaluated)/len(evaluated)
                        for name in ('recall_at_10','ndcg_at_10','mrr_at_10')},
                        'query_latency_ms':stats([r['latency_ms'] for r in evaluated]),'queries':evaluated}
                    # Same literal title tokens for both systems; no oracle topic/doc-id filter.
                    title_results=[]
                    for doc in corpus[::max(1,len(corpus)//100)][:100]:
                        title=' '.join(doc['title'].split()[:3])[:200]
                        ids,ms,pages=search(title,adapt=False)
                        title_results.append({'doc_id':doc['_id'],'query':title,'ranked_doc_ids':ids,
                            'hit_at_10':doc['_id'] in ids,'latency_ms':ms,'http_pages':pages})
                    results['title_lookup']={'hit_at_10':sum(r['hit_at_10'] for r in title_results)/len(title_results),
                        'query_latency_ms':stats([r['latency_ms'] for r in title_results]),'queries':title_results}
                    results['raw_scifact_query_contract']={'accepted_by_shape':sum(len(q.encode())<=256 and len(q.split())<=8 for _,q in queries),
                        'total':len(queries)} if provider=='instantkv' else {'accepted_by_shape':len(queries),'total':len(queries)}
                    rss_samples.append(rss());results['rss_samples_bytes']=rss_samples
                    results['largest_sampled_rss_bytes']=max(rss_samples)
                    results['errors']=0
                    print(provider,results['scifact']['metrics'],flush=True)
                finally:
                    connection.close()
                    proc.kill();proc.wait(timeout=10)
                    # Stop any child workers belonging to this isolated process group.
                    try: os.killpg(proc.pid,9)
                    except ProcessLookupError: pass
        args.output.write_text(json.dumps(report,indent=2)+'\n')
    report['complete']=True
    args.output.write_text(json.dumps(report,indent=2)+'\n')
    print('Report:',args.output,flush=True)


if __name__=='__main__':
    main()
