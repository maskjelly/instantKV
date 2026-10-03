"""Isolated, authenticated loopback backends for matched full-suite inputs."""
import hashlib
import http.client
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(1024*1024), b''): h.update(block)
    return h.hexdigest()


def chunks(text):
    # Same lossless bounds as prior reports. No labels or QA text in documents.
    start = 0
    while start < len(text):
        end = min(len(text), start + 9500)
        while len(text[start:end].encode()) > 14000: end -= 1
        yield text[start:end]
        start = end


class Backend:
    def __init__(self, provider, directory, config):
        self.provider = provider; self.path = Path(directory); self.config = config
        self.path.mkdir(parents=True,exist_ok=True)
        self.process = None; self.connection = None; self.rss_samples = []
        self.saved = 0; self.write_samples = []; self.input_bytes = 0
        self.environment = {k:v for k,v in os.environ.items() if not k.startswith('INSTANTKV_')}
        if provider != 'instantkv': raise ValueError('Provider adapter unavailable: '+provider)
        binary = ROOT/'target/release/instantkv'
        if sha(binary) != config['binary_sha256']: raise RuntimeError('Frozen binary SHA mismatch')
        subprocess.run([str(binary),'init'],cwd=self.path,env=self.environment,check=True,capture_output=True)
        with socket.socket() as reservation:
            reservation.bind(('127.0.0.1',0));self.port=reservation.getsockname()[1]
        original=(self.path/'instantkv.toml').read_text()
        a=original.index('[[namespaces]]');b=original.index('[[namespaces]]',a+1)
        policy=original[a:b].replace('max_entries = 10000','max_entries = 50000000').replace('max_bytes = 67108864','max_bytes = 107374182400')
        effective=original[:a]+policy+original[b:]
        effective=effective.replace('127.0.0.1:8080',f'127.0.0.1:{self.port}')
        (self.path/'instantkv.toml').write_text(effective)
        self.effective_config=effective
        secrets=dict(line.split('=',1) for line in (self.path/'.instantkv/credentials.env').read_text().splitlines())
        self.headers={'Authorization':'Bearer '+secrets['INSTANTKV_APP_TOKEN'],'Content-Type':'application/json'}
        self.started=time.perf_counter()
        self.process=subprocess.Popen([str(binary),'serve'],cwd=self.path,env=self.environment,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        try:
            for _ in range(600):
                if self.process.poll() is not None: raise RuntimeError('Backend startup exited')
                try:
                    self.connection=http.client.HTTPConnection('127.0.0.1',self.port,timeout=180)
                    status,_,_=self.request('GET','/healthz')
                    if status==200:break
                except OSError:pass
                if self.connection:self.connection.close()
                time.sleep(.01)
            else:raise RuntimeError('Backend startup timeout')
            self.startup_ms=(time.perf_counter()-self.started)*1000
            self.sample_rss()
        except BaseException:
            self.close();raise

    def request(self,method,route,body=None):
        raw=None if body is None else json.dumps(body,separators=(',',':'),ensure_ascii=False).encode()
        began=time.perf_counter_ns()
        self.connection.request(method,route,body=raw,headers=self.headers)
        response=self.connection.getresponse();data=response.read()
        elapsed=(time.perf_counter_ns()-began)/1e6
        return response.status,json.loads(data) if data else None,elapsed

    def insert(self,doc):
        for part,text in enumerate(chunks(doc['content'])):
            key=f'm{self.saved:09d}'
            metadata={'source_id':doc['id'],'part':part}
            if doc.get('image'):metadata['image']=doc['image']
            memory={'content':text,'topic':'evidence','tags':[],'occurred_at_ms':doc.get('event_ms',1760000000000),'metadata':metadata}
            status,value,latency=self.request('POST','/v1/namespaces/knowledge/memories',{'key':key,'memory':memory})
            if status!=200 and status!=201:raise RuntimeError(f'Ingestion HTTP {status}; no dropped document permitted')
            if value['memory']['content']!=text:raise RuntimeError('Stored content changed')
            self.saved+=1;self.write_samples.append(latency);self.input_bytes+=len(text.encode())
            if self.saved%500==0:self.sample_rss()

    def search(self,text,limit=20):
        started=time.perf_counter()
        hits=[];seen=set();cursor=None;pages=0;elapsed=0;truncated=False;reduced=False
        work={k:0 for k in ['index_reads','postings_scanned','scored_candidates','candidates_scanned','scanned_bytes']}
        cursors=set()
        while pages<64:
            body={'query':text,'limit':20,'max_bytes':65536,'expand':self.config['instantkv']['expand'],'cursor':cursor}
            status,page,latency=self.request('POST','/v1/namespaces/knowledge/search',body)
            pages+=1;elapsed+=latency
            if status!=200:return {'status':status,'hits':[],'latency_ms':elapsed,'failure':True,'pages':pages,'truncated':truncated,'query_reduced':reduced,'work':work}
            truncated=truncated or page['truncated'];reduced=reduced or page['query_reduced']
            for k in work:work[k]+=page[k]
            for item in page['items']:
                if item['key'] not in seen:hits.append(item);seen.add(item['key'])
            sources=list(dict.fromkeys(h['memory']['metadata']['source_id'] for h in hits))
            cursor=page['next_cursor']
            if len(sources)>=limit or not cursor:break
            if cursor in cursors:raise RuntimeError('Ranked cursor did not progress')
            cursors.add(cursor)
        total=(time.perf_counter()-started)*1000
        self.sample_rss()
        return {'status':200,'hits':hits,'latency_ms':total,'http_latency_ms':elapsed,'failure':False,'pages':pages,'truncated':truncated or (pages==64 and bool(cursor)),'query_reduced':reduced,'work':work}

    def sample_rss(self):
        if self.process and self.process.poll() is None:
            rss=int(subprocess.check_output(['ps','-o','rss=','-p',str(self.process.pid)],text=True).strip())*1024
            self.rss_samples.append(rss)

    def resources(self):
        self.sample_rss()
        database=self.path/'.instantkv/data'
        return {'startup_ms':self.startup_ms,'sampled_rss_bytes':self.rss_samples,
                'largest_sampled_rss_bytes':max(self.rss_samples),'saved_chunks':self.saved,
                'stored_content_bytes':self.input_bytes,'database_bytes':sum(p.stat().st_size for p in database.rglob('*') if p.is_file()),
                'index_bytes':None,'index_bytes_reason':'redb shares record and index pages; separate index size not instrumented',
                'write_latency_samples_ms':self.write_samples,
                'write_throughput_per_second':self.saved/(sum(self.write_samples)/1000) if self.saved else 0,
                'effective_config':self.effective_config,'binary_sha256':self.config['binary_sha256'],
                'binary_bytes':(ROOT/'target/release/instantkv').stat().st_size}

    def close(self):
        if self.connection:self.connection.close()
        if self.process:
            self.process.terminate()
            try:self.process.wait(timeout=15)
            except subprocess.TimeoutExpired:self.process.kill();self.process.wait()

    def __enter__(self):return self
    def __exit__(self,*args):self.close()
