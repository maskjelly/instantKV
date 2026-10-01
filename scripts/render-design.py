#!/usr/bin/env python3
"""Author Monolith: editable metal identity and minimal memory diagrams."""
import argparse
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / 'docs/assets'
WORK = ROOT / '.tesseract-work'
parser = argparse.ArgumentParser()
parser.add_argument('--tsrct', required=True, help='Pinned Tesseract 0.3.0 executable')
parser.add_argument('--only', nargs='+', help='Optional asset names to render')
args = parser.parse_args()
NAMES = ['brand','logo','swarm','architecture','lifecycle','distributed']
if args.only and any(name not in NAMES for name in args.only):
    parser.error('--only accepts: '+', '.join(NAMES))
CLI = str(Path(args.tsrct).resolve())
BG, PANEL, LINE = '#0B0D10', '#12161B', '#303640'
TEXT, MUTED, SILVER = '#EDF0F5', '#9EA7B5', '#C6CEDB'
PLANES = [
    [(0,8),(28,8),(28,120),(0,120)],
    [(38,56),(83,8),(116,8),(64,66)],
    [(38,76),(64,68),(116,120),(83,120)],
]
STOPS = [(0,'#778292'),(.15,'#E0E5EF'),(.38,'#A3AEBC'),(.49,'#F6F7FD'),
         (.54,'#808B9D'),(.78,'#D3DCE9'),(1,'#8A94A6')]

def run(*parts):
    subprocess.run([CLI,*map(str,parts)],check=True,cwd=ROOT)
def color(value):
    return [int(value[i:i+2],16)/255 for i in (1,3,5)]+[1]
def metal(t):
    for (a,ca),(b,cb) in zip(STOPS,STOPS[1:]):
        if a <= t <= b:
            mix=(t-a)/(b-a)
            return '#'+''.join(f'{round(int(ca[i:i+2],16)*(1-mix)+int(cb[i:i+2],16)*mix):02x}' for i in (1,3,5))
    return STOPS[-1][1]
def clip(points, boundary, above):
    result=[]
    previous=points[-1]
    for current in points:
        inside=lambda p: p[1]>=boundary if above else p[1]<=boundary
        if inside(previous)!=inside(current):
            t=(boundary-previous[1])/(current[1]-previous[1])
            result.append((previous[0]+t*(current[0]-previous[0]),boundary))
        if inside(current): result.append(current)
        previous=current
    return result

class Board:
    def __init__(self,name,width,height):
        self.name,self.width,self.height=name,width,height
        self.path=ASSETS/f'{name}.tsrct'
        self.layout=WORK/f'{name}.json'
        if args.only and name not in args.only:
            self.doc={'composition':{'layers':[]}}
        else:
            if not self.path.exists(): run('project','create','--project',self.path)
            run('project','import-font','--project',self.path,'--file',ASSETS/'fonts/SpaceGrotesk.ttf')
            run('project','checkout','--project',self.path,'--output',self.layout)
            self.doc=json.loads(self.layout.read_text())
        self.doc['dimensions']={'width':width,'height':height}
        self.doc['composition']['layers']=[]
        self.id=0
        self.rect('Graphite background',0,0,width,height,BG)
    def layer(self,kind,name,x,y,payload):
        self.id+=1
        self.doc['composition']['layers'].insert(0,{
            'type':kind,'id':self.id,'name':name,'blendMode':'normal',
            'activeRange':{'start':0,'duration':3000},
            'transform':{'anchorPoint':[0,0],'position':[x,y],'scale':[100,100],'rotation':0,'opacity':100},**payload})
    def rect(self,name,x,y,w,h,fill):
        self.layer('Rect',name,x,y,{'rect':{'size':[w,h],'fillColor':color(fill),'roundness':0}})
    def text(self,name,text,x,y,size=28,fill=TEXT,weight=400):
        self.layer('Text',name,x,y,{'sourceText':{
            'text':text,'fontFamily':'Space Grotesk Light','fontStyle':'Regular',
            'fontSize':size,'fontVariations':{'id':self.id+1,'axes':{'wght':weight}},
            'fillColor':color(fill),'strokeWidth':0,'justification':'left','leading':size*1.3}})
    def polygon(self,name,points,fill):
        commands=[{'type':'moveTo' if i==0 else 'lineTo','x':x,'y':y} for i,(x,y) in enumerate(points)]+[{'type':'close'}]
        self.layer('Shape',name,0,0,{'shape':{'path':{'commands':commands},'fills':[
            {'paint':{'type':'solid','color':color(fill)},'fillRule':'nonZeroWinding','blendMode':'normal','opacity':100}]}})
    def panel(self,title,x,y,w,h,details=(),size=28):
        self.rect(title+' boundary',x,y,w,h,LINE)
        self.rect(title+' surface',x+1,y+1,w-2,h-2,PANEL)
        self.text(title+' heading',title,x+26,y+48,30,weight=500)
        for i,line in enumerate(details): self.text(title+f' detail {i}',line,x+26,y+100+i*39,size,MUTED)
    def arrow(self,name,x1,y1,x2,y2):
        if y1==y2:
            sign=1 if x2>x1 else -1
            self.rect(name,min(x1,x2),y1-1,abs(x2-x1),2,SILVER)
            self.polygon(name+' head',[(x2,y2),(x2-sign*10,y2-5),(x2-sign*10,y2+5)],SILVER)
        else:
            sign=1 if y2>y1 else -1
            self.rect(name,x1-1,min(y1,y2),2,abs(y2-y1),SILVER)
            self.polygon(name+' head',[(x2,y2),(x2-5,y2-sign*10),(x2+5,y2-sign*10)],SILVER)
    def mark(self,x,y,scale):
        # Chrome is restricted to the logo. Clipped native planes remain editable.
        for plane,points in enumerate(PLANES):
            for strip in range(64):
                part=clip(points,strip*2,True)
                if part: part=clip(part,(strip+1)*2,False)
                if len(part)>=3:
                    self.polygon(f'Chrome plane {plane} / reflection {strip}',
                                 [(x+px*scale,y+py*scale) for px,py in part],metal((strip+.5)/64))
    def header(self,title,status,subtitle):
        self.text('Diagram status',status,72,65,18,MUTED,500)
        self.text('Diagram title',title,72,147,58,weight=500)
        self.text('Diagram subtitle',subtitle,72,197,26,MUTED)
    def footer(self,text):
        self.rect('Footer rule',72,self.height-75,self.width-144,1,LINE)
        self.text('Footer',text,72,self.height-34,22,MUTED)
    def save(self):
        if args.only and self.name not in args.only: return
        self.layout.write_text(json.dumps(self.doc,indent=2)+'\n')
        run('project','commit','--project',self.path,'--file',self.layout)
        run('preview','--project',self.path,'--time','1','--output',self.path.with_suffix('.png'))

WORK.mkdir(exist_ok=True)
b=Board('brand',1200,400)
b.mark(64,102,1.28)
b.text('Wordmark','instantKV',274,223,108,weight=500)
b.text('Tagline','Memory for cloud agents.',280,280,30,MUTED)
b.rect('Brand rule',64,336,1072,1,LINE)
b.text('Brand descriptor','SHARED KNOWLEDGE  /  PRIVATE AGENTS  /  DURABLE CONTEXT',64,371,18,MUTED,500)
b.save()
b=Board('logo',512,512)
b.mark(70,51,3.2)
b.save()

b=Board('swarm',1600,1090)
b.header('One base. Independent agents.','SWARM MEMORY / IMPLEMENTED / SINGLE NODE',
         'Shared project knowledge. A private workspace for every worker.')
b.panel('Shared knowledge base',350,255,900,175,
        ['Shared facts, decisions and source references.','Operator writes. Scoped agents read.'])
for name,x,namespace in [('Alpha',72,'alpha'),('Beta',878,'beta')]:
    middle=x+325
    b.arrow(name+' shared read',middle,497,middle,441)
    b.text(name+' read label','READ SHARED',middle+30,482,21,MUTED,500)
    b.panel('Agent '+name,x,508,650,160,
            ['Remote worker / scoped credential','Recall shared facts. Work independently.'])
    b.arrow(name+' private write',middle,677,middle,741)
    b.text(name+' write label','WRITE OWN SCOPE',middle+30,715,21,MUTED,500)
    b.panel('Private knowledge + checkpoints',x,754,650,165,
            [namespace+' + '+namespace+'_checkpoints','Sibling access denied. Shared writes denied.'],26)
b.text('Repeatable scopes','Repeat the namespace-and-grant pattern for each new agent.',72,969,28)
b.footer('One server, no physical replicas. Namespace grants isolate access; agent/session labels do not.')
b.save()

b=Board('architecture',1600,1200)
b.header('How memory is stored.','STORAGE ENGINE / IMPLEMENTED / SINGLE NODE',
         'Rust + Tokio + Axum. Durable writes are acknowledged after commit.')
b.panel('Agents',72,256,350,180,['Shared + private memory','Save / restore'],24)
b.panel('HTTP / CLI / MCP',474,256,350,180,['Typed tools. Exact keys.','Scoped bearer token'],24)
b.panel('Policy + engine',876,256,652,180,
        ['Grants / revisions / quotas','Size limits / bounded blocking work'],28)
b.arrow('Client transport',432,344,464,344)
b.arrow('Shared policy',834,344,866,344)
b.arrow('Durable branch',1202,446,1202,536)
b.rect('Scratch branch',402,482,800,2,SILVER)
b.arrow('Scratch down',402,482,402,536)
b.panel('Scratch / RAM',72,548,660,202,
        ['Optional working cache / TTL + FIFO','Bounded, indexed expiry cleanup','Empty after process restart.'],27)
b.panel('Knowledge + checkpoints / redb',868,548,660,202,
        ['Shared + private namespaces','One database file. Immediate durability.','Retained across process restart.'],27)
b.rect('Schema boundary',72,815,1456,271,LINE)
b.rect('Schema surface',73,816,1454,269,PANEL)
b.text('Records heading','records_v1',99,865,30,weight=500)
for i,line in enumerate(['(namespace, key) -> header + bytes','revision / time / expiry / insertion order',
                          'usage_v1: entries, bytes, revision','expiry_v1: ordered deadlines','metadata_v1: format, mode, purpose']):
    b.text('Record schema '+str(i),line,99,912+i*32,25,MUTED)
b.rect('Schema divider',762,842,1,215,LINE)
b.text('Checkpoint heading','Checkpoint / one transaction',788,865,30,weight=500)
for i,line in enumerate(['__checkpoint/id -> capsule + references','__latest/agent/session -> checkpoint ID',
                          '+ namespace usage counters','Immutable bundle. Conditional latest pointer.','All commit together, or none do.']):
    b.text('Checkpoint schema '+str(i),line,788,912+i*32,25,MUTED)
b.footer('Exact recall. Bounded restores. One database writer. No unbounded request queue.')
b.save()

b=Board('lifecycle',1600,730)
b.header('Save. Compact. Resume.','COMPACTION HANDOFF / IMPLEMENTED',
         'The runtime chooses when to save and restore. The server keeps the memory.')
for i,(title,details) in enumerate([
    ('01 / Store',['Facts + sources','Exact key recall']),
    ('02 / Checkpoint',['Goal + constraints','Decisions + tasks','Next action + refs']),
    ('03 / Compact',['Wait for durable ACK','Keep locator outside','compacted context']),
    ('04 / Restore',['Small capsule first','Fetch facts by key','Continue the task'])]):
    x=72+i*380
    b.panel(title,x,262,315,250,details,25)
    if i<3: b.arrow(title+' next',x+328,387,x+366,387)
b.rect('Locator boundary',72,559,1456,82,LINE)
b.rect('Locator surface',73,560,1454,80,PANEL)
b.text('Locator label','RUNTIME SESSION LOCATOR',98,607,16,MUTED,500)
b.text('Locator value','server / namespace / checkpoint ID',440,610,28)
b.footer('Persist the locator outside prompt text. Restore the capsule, then fetch references on demand.')
b.save()

b=Board('distributed',1600,1200)
b.header('Distributed agent memory.','DISTRIBUTED MEMORY / FUTURE PROPOSAL',
         'Replication and automatic run-completion consolidation are not implemented.')
b.panel('Canonical knowledge base',350,242,900,160,
        ['Versioned facts, sources and conflict history.','Baseline manifests seed the next swarm.'],27)
for name,x in [('Worker A',72),('Worker B',878)]:
    middle=x+325
    b.arrow(name+' baseline',middle,413,middle,514)
    b.text(name+' seed label','VERSIONED BASELINE',middle+30,471,21,MUTED,500)
    b.panel(name+' / independent node',x,527,650,171,
            ['Local baseline + private overlay','Work independently. Checkpoint locally.'],27)
    b.arrow(name+' completion',middle,709,middle,775)
    b.text(name+' completion label','SHAREABLE RUN DELTA',middle+30,752,21,MUTED,500)
b.panel('Consolidation / durable completion jobs',72,786,1456,168,
        ['Import -> deduplicate -> validate provenance',
         'Review conflicts -> publish with revision checks'],28)
b.rect('Publication out',1538,912,22,2,SILVER)
b.arrow('Publication up',1560,912,1560,321)
b.arrow('Publication to canon',1560,321,1267,321)
b.text('Publication label','PUBLISH NEXT',1290,281,21,MUTED,500)
b.rect('Meter boundary',72,998,1456,95,LINE)
b.rect('Meter surface',73,999,1454,93,PANEL)
b.text('Metrics heading','QUALITY METRICS / PROPOSED',98,1051,20,MUTED,500)
b.text('Meter metrics','Facts / sources / freshness / conflicts / recall',605,1052,26)
b.footer('No silent last-writer-wins merge. Accepted facts retain sources; conflicts require review.')
b.save()

svg='<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128" role="img" aria-labelledby="title"><title id="title">instantKV Monolith: split chrome K</title><defs><linearGradient id="chrome" x1="0" y1="0" x2="0" y2="128" gradientUnits="userSpaceOnUse">'
svg+=''.join(f'<stop offset="{position}" stop-color="{value}"/>' for position,value in STOPS)
svg+='</linearGradient></defs><g fill="url(#chrome)">'
svg+=''.join('<path d="'+' '.join(('M' if i==0 else 'L')+f'{x} {y}' for i,(x,y) in enumerate(plane))+'Z"/>' for plane in PLANES)
(ASSETS/'logo.svg').write_text(svg+'</g></svg>\n')
print('Rendered Monolith: '+', '.join(args.only or NAMES)+'.')
