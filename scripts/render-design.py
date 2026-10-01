#!/usr/bin/env python3
"""Author editable native Tesseract diagrams and branding. No raster layout flattening."""
import argparse
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / 'docs/assets'
WORK = ROOT / '.tesseract-work'
parser = argparse.ArgumentParser()
parser.add_argument('--tsrct', required=True, help='Pinned Tesseract 0.3.0 executable')
args = parser.parse_args()
CLI = str(Path(args.tsrct).resolve())

def run(*args):
    subprocess.run([CLI, *map(str, args)], check=True, cwd=ROOT)

def color(value):
    value = value.lstrip('#')
    return [int(value[i:i+2],16)/255 for i in (0,2,4)] + [1]

INK = '#182D27'
GREEN = '#267D60'
LIME = '#D8ED9B'
PAPER = '#F5F3ED'
MUTED = '#63766D'
LINE = '#B7C6BB'

class Board:
    def __init__(self, name, width, height):
        self.path = ASSETS / f'{name}.tsrct'
        if not self.path.exists(): run('project','create','--project',self.path)
        run('project','import-font','--project',self.path,'--file',ASSETS/'fonts/SpaceGrotesk.ttf')
        self.layout = WORK/f'{name}.json'
        run('project','checkout','--project',self.path,'--output',self.layout)
        self.doc = json.loads(self.layout.read_text())
        self.doc['dimensions']={'width':width,'height':height}
        self.doc['composition']['layers']=[]
        self.id=0
    def layer(self, kind, name, x, y, payload):
        self.id+=1
        layer={'type':kind,'id':self.id,'name':name,'blendMode':'normal','activeRange':{'start':0,'duration':3000},'transform':{'anchorPoint':[0,0],'position':[x,y],'scale':[100,100],'rotation':0,'opacity':100},**payload}
        self.doc['composition']['layers'].insert(0,layer)
    def rect(self,name,x,y,w,h,fill,roundness=0,stroke=None):
        rect={'size':[w,h],'fillColor':color(fill),'roundness':roundness}
        if stroke: rect.update(strokeEnabled=True,strokeColor=color(stroke),strokeWidth=1.5)
        self.layer('Rect',name,x,y,{'rect':rect})
    def text(self,name,text,x,y,size=20,fill=INK,weight=400):
        self.layer('Text',name,x,y,{'sourceText':{'text':text,'fontFamily':'Space Grotesk Light','fontStyle':'Regular','fontSize':size,'fontVariations':{'id':self.id+1,'axes':{'wght':weight}},'fillColor':color(fill),'strokeWidth':0,'justification':'left','leading':size*1.35}})
    def polygon(self,name,points,fill):
        commands=[{'type':'moveTo' if i==0 else 'lineTo','x':x,'y':y} for i,(x,y) in enumerate(points)]+[{'type':'close'}]
        self.layer('Shape',name,0,0,{'shape':{'path':{'commands':commands},'fills':[{'paint':{'type':'solid','color':color(fill)},'fillRule':'nonZeroWinding','blendMode':'normal','opacity':100}]}})
    def arrow(self,name,x1,y1,x2,y2,fill=GREEN):
        if y1==y2:
            self.rect(name,x1,y1-1.5,x2-x1-9,3,fill)
            self.polygon(name+' head',[(x2,y2),(x2-10,y2-6),(x2-10,y2+6)],fill)
        else:
            self.rect(name,x1-1.5,y1,3,y2-y1-9,fill)
            self.polygon(name+' head',[(x2,y2),(x2-6,y2-10),(x2+6,y2-10)],fill)
    def mark(self,x,y,scale=1,fill=GREEN):
        for i in range(3): self.rect(f'Cache tile {i}',x+20*scale,y+(20+i*32)*scale,24*scale,24*scale,fill,4*scale)
        self.polygon('Folded K ribbon',[(x+a*scale,y+b*scale) for a,b in [(44,53),(82,20),(112,20),(65,64),(112,108),(82,108),(44,75)]],fill)
    def save(self):
        self.layout.write_text(json.dumps(self.doc,indent=2)+'\n')
        run('project','commit','--project',self.path,'--file',self.layout)
        run('preview','--project',self.path,'--time','1','--output',self.path.with_suffix('.png'))

WORK.mkdir(exist_ok=True)
b=Board('architecture',1600,1100)
b.rect('Paper',0,0,1600,1100,PAPER)
b.mark(52,30,0.55)
b.text('Brand','instantKV',126,85,40,INK,700)
b.text('Title','Memory that survives compaction.',64,170,52,INK,700)
b.text('Subtitle','Park knowledge. Commit a capsule. Restore only what the agent needs.',64,211,22,MUTED)
b.rect('Single node badge',1250,55,286,42,LIME,21)
b.text('Single node label','SINGLE NODE  /  RUST',1274,84,17,INK,700)

b.arrow('Runtime to clients',345,342,386,342)
b.arrow('Clients to policy',615,342,658,342)
b.arrow('Policy to durable',1086,342,1132,342)
b.rect('Scratch branch',1084,399,30,3,GREEN)
b.rect('Scratch route down',1111,399,3,137,GREEN)
b.arrow('Scratch route right',1111,536,1132,536)
b.rect('Expiry calls core',875,438,3,62,MUTED)
b.polygon('Expiry core arrow',[(876.5,432),(870.5,443),(882.5,443)],MUTED)

for name,x,y,w,h in [('Agent runtime',64,264,280,164),('Clients',392,264,222,164),('Memory service',664,264,420,164),('Durable storage',1136,264,400,164),('Expiry worker',664,500,420,154),('Scratch cache',1136,500,400,154)]:
    b.rect(name+' panel',x,y,w,h,'#FFFFFF',14,LINE)

b.text('Runtime label','01  AGENT RUNTIME',84,302,14,GREEN,700)
b.text('Runtime title','Save / compact / restore',84,338,21,INK,700)
b.text('Runtime details','Keep the locator outside\nthe compacted context.',84,377,18,MUTED)
b.text('Client label','02  CLIENTS',412,302,14,GREEN,700)
b.text('Client title','HTTP · CLI · MCP',412,338,22,INK,700)
b.text('Client details','Shared namespace grants.\nScoped tool access.',412,377,17,MUTED)
b.text('Service label','03  SHARED POLICY',686,302,14,GREEN,700)
b.text('Service title','Memory service',686,338,25,INK,700)
b.text('Service details','Scoped auth · size / TTL limits\nQuotas · revisions · bounded work',686,377,19,MUTED)
b.text('Durable label','04  DURABLE / REDB',1158,302,14,GREEN,700)
b.text('Durable title','Knowledge + checkpoints',1158,338,24,INK,700)
b.text('Durable details','Atomic commit, then acknowledge.\nRetained across server restart.',1158,377,18,MUTED)
b.text('Expiry title','Bounded expiry worker',686,544,25,INK,700)
b.text('Expiry details','Ordered deadline index; capped batches.\nReads hide expired data immediately.',686,583,19,MUTED)
b.text('Scratch title','Scratch / RAM',1158,544,25,INK,700)
b.text('Scratch details','TTL + FIFO eviction within quota.\nDisposable on process restart.',1158,583,19,MUTED)

b.rect('Handoff capsule',64,500,550,154,LIME,14)
b.text('Handoff title','COMPACTION HANDOFF',86,539,15,INK,700)
b.text('Handoff copy','goal · constraints · decisions · next action',86,577,23,INK,700)
b.text('Handoff detail','A self-contained capsule; fetch details by key later.',86,614,18,INK)

b.rect('Schema panel',64,715,1472,286,INK,20)
b.text('Schema label','STORED SCHEMA  /  FORMAT v1',88,757,16,LIME,700)
b.rect('Schema separator 1',560,778,1,185,'#426054')
b.rect('Schema separator 2',1040,778,1,185,'#426054')
b.text('Record schema','records_v1',88,805,27,'#FFFFFF',700)
b.text('Record key','(namespace, key) → header + bytes',88,844,20,LIME)
b.text('Record fields','revision · write time · expiry · insertion order\nexpiry_v1 → ordered deadline index\nusage_v1 → entries / bytes / revision high-water',88,883,17,'#C5D1C8')
b.text('Checkpoint schema','Checkpoint bundle',586,805,27,'#FFFFFF',700)
b.text('Checkpoint identity','id · agent_id · session_id',586,844,20,LIME)
b.text('Checkpoint fields','capsule → goal / summary / constraints\n             decisions / tasks / next action\nreferences → namespace / key / revision',586,883,17,'#C5D1C8')
b.text('Commit schema','One transaction',1066,805,27,'#FFFFFF',700)
b.text('Commit fields','immutable bundle\n+ session latest pointer\n+ namespace usage counters',1066,850,20,LIME)
b.text('Commit result','All commit together, or none do.',1066,953,17,'#C5D1C8')
b.text('Footer','Exact recall  ·  Bounded restore  ·  Durable acknowledgements',64,1058,20,MUTED)
b.save()

b=Board('brand',1200,420)
b.rect('Ink background',0,0,1200,420,INK)
b.mark(68,81,1.9,LIME)
b.text('Wordmark','instantKV',318,223,105,'#FFFFFF',700)
b.text('Tagline','A durable place for agent memory.',325,283,28,'#BDCEC4')
b.text('Descriptor','SAVE  /  COMPACT  /  RESTORE',325,341,15,LIME,700)
b.save()

b=Board('logo',512,512)
b.rect('Ink background',0,0,512,512,INK,80)
b.mark(-8,0,4,LIME)
b.save()

(ASSETS/'logo.svg').write_text('''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128" role="img" aria-labelledby="title"><title id="title">instantKV — parked memory, ready to recall</title><g fill="#267d60"><rect x="20" y="20" width="24" height="24" rx="4"/><rect x="20" y="52" width="24" height="24" rx="4"/><rect x="20" y="84" width="24" height="24" rx="4"/><path d="M44 53 82 20H112L65 64 112 108H82L44 75Z"/></g></svg>\n''')
print('Rendered: architecture 1600×1100, brand 1200×420, logo 512×512.')
