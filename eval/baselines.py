"""Local comparison adapters. Source chunks and reader budgets match instantKV."""
import json
import os
from pathlib import Path
import re
import socket
import sqlite3
import subprocess
import time

from backend import Backend, chunks, sha


class SQLiteBackend:
    def __init__(self,provider,directory,config):
        self.path=Path(directory);self.path.mkdir(parents=True,exist_ok=True)
        self.config=config;self.saved=0;self.input_bytes=0;self.write_samples=[];self.rss_samples=[]
        started=time.perf_counter()
        self.db=sqlite3.connect(self.path/'fts.sqlite',isolation_level=None)
        self.db.execute('PRAGMA journal_mode=WAL');self.db.execute('PRAGMA synchronous=FULL')
        self.db.execute("CREATE VIRTUAL TABLE documents USING fts5(content, metadata UNINDEXED, tokenize='porter unicode61')")
        self.startup_ms=(time.perf_counter()-started)*1000
        self.sample_rss()
    def sample_rss(self):
        self.rss_samples.append(int(subprocess.check_output(['ps','-o','rss=','-p',str(os.getpid())],text=True).strip())*1024)
    def insert(self,doc):
        for part,text in enumerate(chunks(doc['content'])):
            metadata={'source_id':doc['id'],'part':part}
            if doc.get('image'):metadata['image']=doc['image']
            started=time.perf_counter()
            self.db.execute('INSERT INTO documents VALUES (?,?)',(text,json.dumps(metadata)))
            self.write_samples.append((time.perf_counter()-started)*1000)
            self.saved+=1;self.input_bytes+=len(text.encode())
            if self.saved%500==0:self.sample_rss()
    def search(self,text,limit=20):
        started=time.perf_counter();terms=list(dict.fromkeys(re.findall(r'\w+',text)))
        expression=' OR '.join('"'+t+'"' for t in terms)
        rows=self.db.execute('SELECT rowid,content,metadata,bm25(documents) FROM documents WHERE documents MATCH ? ORDER BY bm25(documents) LIMIT 1000',(expression,)).fetchall() if expression else []
        hits=[];sources=set();used=0;cut=False
        for key,content,metadata,score in rows:
            size=len(content.encode())
            if used+size>65536:cut=True;break
            meta=json.loads(metadata);sources.add(meta['source_id']);used+=size
            hits.append({'key':str(key),'memory':{'content':content,'metadata':meta},'score':-score})
            if len(sources)>=limit:break
        elapsed=(time.perf_counter()-started)*1000;self.sample_rss()
        return {'status':200,'hits':hits,'latency_ms':elapsed,'failure':False,'pages':1,'truncated':cut,'query_reduced':False,'work':{},'transport':'in-process SQLite FTS5, no HTTP'}
    def resources(self):
        self.sample_rss()
        return {'startup_ms':self.startup_ms,'sampled_rss_bytes':self.rss_samples,'largest_sampled_rss_bytes':max(self.rss_samples),
            'rss_scope':'Python benchmark process including adapter and interpreter; not an isolated service RSS',
            'saved_chunks':self.saved,'stored_content_bytes':self.input_bytes,'database_bytes':sum(p.stat().st_size for p in self.path.glob('fts.sqlite*')),
            'write_latency_samples_ms':self.write_samples,'write_throughput_per_second':self.saved/(sum(self.write_samples)/1000) if self.saved else 0,
            'effective_config':{'sqlite_version':sqlite3.sqlite_version,'tokenizer':'porter unicode61','ranking':'bm25','journal':'WAL','synchronous':'FULL','transport':'in-process','result_content_bytes':65536},
            'index_bytes':None,'index_bytes_reason':'FTS5 tables share database pages; separate index size not measured'}
    def close(self):self.db.close()
    def __enter__(self):return self
    def __exit__(self,*args):self.close()


class SupermemoryBackend(Backend):
    def __init__(self,provider,directory,config):
        self.path=Path(directory);self.path.mkdir(parents=True,exist_ok=True);self.config=config
        self.saved=0;self.input_bytes=0;self.write_samples=[];self.rss_samples=[];self.process=None;self.connection=None
        binary=Path(config['supermemory_binary'])
        if sha(binary)!=config['supermemory_binary_sha256']:raise ValueError('Pinned Supermemory binary SHA mismatch')
        with socket.socket() as s:s.bind(('127.0.0.1',0));self.port=s.getsockname()[1]
        env=dict(os.environ);env.update(PORT=str(self.port),SUPERMEMORY_DATA_DIR=str(self.path/'data'),SUPERMEMORY_DISABLE_TELEMETRY='1',OPENAI_API_KEY='local-unused',OPENAI_BASE_URL='http://127.0.0.1:9/v1',OPENAI_MODEL='not-configured')
        logpath=self.path/'private.log';self.log=logpath.open('w');logpath.chmod(0o600)
        import http.client
        started=time.perf_counter();self.headers={}
        self.process=subprocess.Popen([str(binary)],cwd=self.path,env=env,stdout=self.log,stderr=subprocess.STDOUT,start_new_session=True)
        try:
            for _ in range(1200):
                if self.process.poll() is not None:raise RuntimeError('Supermemory startup failed')
                match=re.search(r'sm_[A-Za-z0-9_-]+',logpath.read_text(errors='replace'))
                try:
                    self.connection=http.client.HTTPConnection('127.0.0.1',self.port,timeout=300)
                    self.connection.request('GET','/');resp=self.connection.getresponse();resp.read()
                    if match and resp.status==200:
                        self.headers={'Authorization':'Bearer '+match.group(),'Content-Type':'application/json'};break
                except OSError:pass
                if self.connection:self.connection.close()
                time.sleep(.1)
            else:raise RuntimeError('Supermemory startup timeout')
            self.startup_ms=(time.perf_counter()-started)*1000;self.sample_rss()
        except BaseException:self.close();raise
    def sample_rss(self):
        rows=[tuple(map(int,line.split())) for line in subprocess.check_output(['ps','-axo','pid=,ppid=,rss='],text=True).splitlines()]
        descendants={self.process.pid}
        while True:
            expanded=descendants|{pid for pid,parent,_ in rows if parent in descendants}
            if expanded==descendants:break
            descendants=expanded
        self.rss_samples.append(sum(rss for pid,_,rss in rows if pid in descendants)*1024)
    def insert(self,doc):
        for part,text in enumerate(chunks(doc['content'])):
            metadata={'source_id':doc['id'],'part':part}
            if doc.get('image'):metadata['image']=doc['image']
            status,value,elapsed=self.request('POST','/v4/memories',{'containerTag':'eval','memories':[{'content':text,'metadata':metadata}]})
            if not 200<=status<300 or len(value['memories'])!=1:raise RuntimeError('Supermemory ingestion failed; no dropped documents')
            if value['memories'][0]['memory']!=text:raise RuntimeError('Supermemory returned changed content')
            self.saved+=1;self.input_bytes+=len(text.encode());self.write_samples.append(elapsed)
            if self.saved%500==0:self.sample_rss()
    def search(self,text,limit=20):
        started=time.perf_counter()
        status,value,_=self.request('POST','/v4/search',{'containerTag':'eval','q':text,'threshold':0,'limit':40,'rerank':False,'rewriteQuery':False})
        hits=[]
        if status==200:
            for hit in value['results']:
                hits.append({'key':str(hit.get('id',len(hits))),'memory':{'content':hit['memory'],'metadata':hit['metadata']},'score':hit.get('score')})
        elapsed=(time.perf_counter()-started)*1000;self.sample_rss()
        return {'status':status,'hits':hits,'latency_ms':elapsed,'failure':status!=200,'pages':1,'truncated':False,'query_reduced':False,'work':{}}
    def resources(self):
        self.sample_rss()
        return {'startup_ms':self.startup_ms,'sampled_rss_bytes':self.rss_samples,'largest_sampled_rss_bytes':max(self.rss_samples),
            'rss_scope':'server process and descendants','saved_chunks':self.saved,'stored_content_bytes':self.input_bytes,
            'database_bytes':sum(p.stat().st_size for p in (self.path/'data').rglob('*') if p.is_file()),'index_bytes':None,'index_bytes_reason':'Not separately instrumented',
            'write_latency_samples_ms':self.write_samples,'write_throughput_per_second':self.saved/(sum(self.write_samples)/1000) if self.saved else 0,
            'binary_sha256':self.config['supermemory_binary_sha256'],'effective_config':{'version':'v0.0.8','embedding':'bge-base-en-v1.5 768d','rerank':False,'rewriteQuery':False,'direct_memory_api':True,'cloud_calls':False,'write_batch':1,'durability':'provider default; not claimed identical durable commit guarantee'}}
    def close(self):
        super().close()
        if getattr(self,'log',None):self.log.close()


def make_backend(provider,*args):
    adapter={'instantkv':Backend,'sqlite-fts5':SQLiteBackend,'supermemory-local':SupermemoryBackend}.get(provider)
    if adapter is None:raise ValueError('Unsupported baseline: '+provider)
    return adapter(provider,*args)
