#!/usr/bin/env python3
"""Author editable classic-desktop artwork with native Tesseract text and shapes."""
import argparse
import json
from pathlib import Path
import subprocess
ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / 'docs/assets'
WORK = ROOT / '.tesseract-work'
parser = argparse.ArgumentParser()
parser.add_argument('--tsrct', required=True, help='Pinned Tesseract 0.3.0 executable')
CLI = str(Path(parser.parse_args().tsrct).resolve())
def run(*args):
    subprocess.run([CLI, *map(str, args)], check=True, cwd=ROOT)
def color(value):
    return [int(value[i:i+2], 16)/255 for i in (1, 3, 5)] + [1]
NAVY, DESKTOP, GRAY = '#000080', '#008080', '#C0C0C0'
INK, WHITE, DARK, YELLOW = '#101010', '#FFFFFF', '#808080', '#FFFF80'
PIXELS = [(8,6),(8,7),(8,8),(8,9),(8,10),(8,11),(8,12),(8,13),
          (9,9),(10,8),(11,7),(12,6),(10,10),(11,11),(12,12),(13,13)]
class Board:
    def __init__(self, name, width, height):
        self.path = ASSETS / f'{name}.tsrct'
        if not self.path.exists(): run('project','create','--project',self.path)
        run('project','import-font','--project',self.path,'--file',ASSETS/'fonts/VT323-Regular.ttf')
        self.layout = WORK/f'{name}.json'
        run('project','checkout','--project',self.path,'--output',self.layout)
        self.doc = json.loads(self.layout.read_text())
        self.doc['dimensions'] = {'width':width,'height':height}
        self.doc['composition']['layers'] = []
        self.id = 0
    def layer(self, kind, name, x, y, payload):
        self.id += 1
        self.doc['composition']['layers'].insert(0, {
            'type':kind,'id':self.id,'name':name,'blendMode':'normal',
            'activeRange':{'start':0,'duration':3000},
            'transform':{'anchorPoint':[0,0],'position':[x,y],'scale':[100,100],'rotation':0,'opacity':100}, **payload})
    def rect(self, name, x, y, w, h, fill):
        self.layer('Rect',name,x,y,{'rect':{'size':[w,h],'fillColor':color(fill),'roundness':0}})
    def text(self, name, text, x, y, size=30, fill=INK):
        self.layer('Text',name,x,y,{'sourceText':{'text':text,'fontFamily':'VT323','fontStyle':'Regular',
            'fontSize':size,'fillColor':color(fill),'strokeWidth':0,'justification':'left','leading':size*1.18}})
    def bevel(self, name, x, y, w, h, fill=GRAY, inset=False):
        top,bottom = (DARK,WHITE) if inset else (WHITE,INK)
        self.rect(name,x,y,w,h,fill)
        self.rect(name+' top',x,y,w,3,top); self.rect(name+' left',x,y,3,h,top)
        self.rect(name+' bottom',x,y+h-3,w,3,bottom); self.rect(name+' right',x+w-3,y,3,h,bottom)
    def window(self, title, x, y, w, h, bar=NAVY):
        self.rect(title+' shadow',x+7,y+7,w,h,'#004C4C')
        self.bevel(title+' frame',x,y,w,h)
        self.rect(title+' title bar',x+7,y+7,w-14,38,bar)
        self.text(title+' title',title,x+18,y+36,30,WHITE)
        self.bevel(title+' close',x+w-40,y+13,27,25)
        self.text(title+' close glyph','x',x+w-33,y+33,25)
    def arrow(self, name, x1, y1, x2, y2, fill=NAVY):
        if y1 == y2:
            sign = 1 if x2 > x1 else -1
            self.rect(name,min(x1,x2),y1-2,abs(x2-x1),4,fill)
            for step in range(5): self.rect(name+str(step),x2-sign*(step+1)*3,y2-2-step*2,3,4+step*4,fill)
        else:
            sign = 1 if y2 > y1 else -1
            self.rect(name,x1-2,min(y1,y2),4,abs(y2-y1),fill)
            for step in range(5): self.rect(name+str(step),x2-2-step*2,y2-sign*(step+1)*3,4+step*4,3,fill)
    def mark(self, x, y, scale=1):
        u = 8*scale
        self.bevel('Memory disk',x,y,16*u,16*u,NAVY)
        self.rect('Disk top label',x+2*u,y+u,12*u,3*u,'#4080C0')
        for i in range(3): self.bevel(f'Knowledge slot {i}',x+2*u,y+(6+3*i)*u,4*u,2*u,YELLOW)
        for px,py in PIXELS: self.rect(f'K pixel {px}:{py}',x+px*u,y+py*u,u,u,WHITE)
    def save(self):
        self.layout.write_text(json.dumps(self.doc,indent=2)+'\n')
        run('project','commit','--project',self.path,'--file',self.layout)
        run('preview','--project',self.path,'--time','1','--output',self.path.with_suffix('.png'))
def desktop(name, width, height, title, status):
    b = Board(name,width,height)
    b.rect('Desktop',0,0,width,height,DESKTOP)
    b.text('Heading',title,42,66,52,WHITE)
    b.text('Status',status,44,107,28,YELLOW)
    b.bevel('Status bar',28,height-54,width-56,32,GRAY,True)
    return b
WORK.mkdir(exist_ok=True)
b = desktop('brand',1200,400,'instantKV / Memory Manager','KNOWLEDGE FOR REMOTE CLOUD AGENTS')
b.window('Memory Manager',32,128,1136,206)
b.mark(59,184,.95)
b.text('Wordmark','instantKV',217,265,102,NAVY)
b.text('Tagline','A mother base.\nA private memory for every agent.',627,219,30)
b.text('Lifecycle','PARK > COMPACT > RESTORE > CONTINUE',627,308,26,NAVY)
b.text('Status label','Rust / self-hosted / HTTP + CLI + MCP / single node',45,369,24)
b.save()
b = Board('logo',512,512)
b.rect('Icon canvas',0,0,512,512,GRAY); b.mark(64,64,3); b.save()
b = desktop('swarm',1600,1040,'One mother base. Independent cloud agents.',
            'WORKING TODAY: SHARED READS + PRIVATE WRITES / ONE SERVER')
b.window('Mother knowledge / namespace: mother',350,152,900,195)
b.text('Mother copy','Project facts / verified decisions / source references',383,234,34)
b.text('Mother policy','Operator writes. Every scoped agent reads the same live base.',383,286,29)
for label,x,ns in [('Agent Alpha',50,'alpha'),('Agent Beta',840,'beta')]:
    b.arrow(label+' read',x+350,470,x+350,364,YELLOW)
    b.text(label+' shared label','READ mother',x+391,417,30,WHITE)
    b.window(label+' / remote worker',x,478,710,167)
    b.text(label+' workflow','Recall shared facts. Work independently.',x+25,563,31)
    b.text(label+' credential',f'One scoped token: mother read + {ns} write',x+25,607,29,NAVY)
    b.arrow(label+' private write',x+355,654,x+355,709,YELLOW)
    b.window('Private '+ns+' knowledge + checkpoints',x,720,710,184)
    b.text(label+' private data','Own findings / capsule / next action',x+25,807,32)
    b.text(label+' boundaries','Sibling access: DENIED / mother write: DENIED',x+25,858,28,NAVY)
b.text('Repeat pattern','Add namespaces + grants per agent. No physical fork or replica is created yet.',52,958,31,WHITE)
b.text('Status label','Mother = shared knowledge namespace / private scope = enforced by token grants',44,1011,26)
b.save()
b = desktop('architecture',1600,1110,'How instantKV stores agent memory',
            'IMPLEMENTED / SINGLE NODE / ACKNOWLEDGE DURABLE WRITES AFTER COMMIT')
for title,x,w in [('Remote agents',44,340),('HTTP / CLI / MCP',453,330),('Policy + engine',852,704)]: b.window(title,x,155,w,200)
b.text('Agent detail','Mother + own scope\nSave before compact\nRestore before work',67,240,30)
b.text('Transport detail','Typed tools\nExact key recall\nScoped bearer token',476,240,30)
b.text('Policy detail','Per-namespace grants / size limits / revisions\nQuotas / TTL policy / bounded blocking work\nRust + Tokio + Axum',877,240,30)
b.arrow('Clients',391,260,443,260,YELLOW); b.arrow('Engine',791,260,842,260,YELLOW)
b.arrow('Durable path',1160,364,1160,429,YELLOW)
b.window('Durable / redb',852,440,704,190)
b.text('Durable detail','Mother + private knowledge + checkpoints\nOne database file / survives process restart\nImmediate transaction durability',877,520,30)
b.window('Disposable scratch / RAM',44,440,704,190)
b.text('Scratch detail','Optional per-namespace cache / TTL + FIFO\nIndexed, bounded expiry cleanup\nEmpty after process restart',69,520,30)
b.rect('RAM branch',396,392,765,4,YELLOW); b.arrow('RAM down',396,392,396,429,YELLOW)
b.window('Storage schema / format v1',44,695,1512,290)
b.text('Record label','records_v1',70,788,36,NAVY)
b.text('Record fields','(namespace, key) -> header + bytes\nrevision / written_at / expires_at / order\nusage_v1: entries + bytes + high-water\nexpiry_v1: ordered deadlines',70,832,27)
b.rect('Schema divider',647,762,3,195,DARK)
b.text('Capsule label','Checkpoint: one transaction',675,788,36,NAVY)
b.text('Capsule fields','__checkpoint/id: immutable capsule + references\n__latest/agent/session: checkpoint ID\n+ namespace usage counters\nAll commit together. Retry with identical ID + payload.',675,832,27)
b.text('Status label','Namespaces isolate agents. agent_id and session_id are labels, not permission boundaries.',44,1081,26)
b.save()
b = desktop('lifecycle',1600,730,'Compaction handoff: save once, resume with context',
            'WORKING TODAY / YOUR AGENT RUNTIME CHOOSES WHEN TO SAVE AND RESTORE')
for i,(title,lines) in enumerate([
    ('1. PARK','Reusable facts\nMother references\nPrivate findings'),
    ('2. CHECKPOINT','Goal + constraints\nDecisions + tasks\nNext action + refs'),
    ('3. COMPACT','Wait for save ACK\nKeep locator outside\nthe prompt context'),
    ('4. RESTORE','Recover small capsule\nFetch details by key\nContinue the task')]):
    x = 42+i*395
    b.window(title,x,177,331,240); b.text(title+' detail',lines,x+22,277,30)
    if i<3: b.arrow(title+' next',x+342,302,x+382,302,YELLOW)
b.window('Locator / durable runtime session metadata',42,477,1516,145)
b.text('Locator copy','server URL + checkpoint namespace + checkpoint ID  (or agent / session for latest)',66,560,32)
b.text('Locator secret note','Credential comes from the agent secret store. Keep tokens out of knowledge and capsules.',66,600,27,NAVY)
b.text('Status label','Restore budget limits the complete response. Missing, stale and forbidden references stay visible.',44,701,25)
b.save()
b = desktop('distributed',1600,1140,'The mothership grows after every completed run',
            'FUTURE PROPOSAL / REPLICATION + AUTOMATIC CONSOLIDATION ARE NOT IMPLEMENTED')
b.window('Mothership / canonical knowledge',350,153,900,165,'#805000')
b.text('Canonical copy','Versioned facts + provenance + conflict history',383,239,34)
b.text('Canonical detail','Publish a baseline manifest for the next swarm run.',383,285,29)
for x,label in [(50,'Worker A'),(855,'Worker B')]:
    b.arrow(label+' baseline',x+350,326,x+350,412,YELLOW)
    b.text(label+' fork label','VERSIONED BASELINE',x+385,382,26,WHITE)
    b.window(label+' / independent node',x,425,695,173,'#805000')
    b.text(label+' copy','Local KV: baseline + private overlay',x+25,513,32)
    b.text(label+' copy2','Work / checkpoint / reconnect / continue',x+25,563,29)
    b.arrow(label+' delta',x+350,607,x+350,713,YELLOW)
    b.text(label+' completion','RUN COMPLETE: DELTA + SOURCES',x+383,670,25,WHITE)
b.window('Consolidation / durable run-completion jobs',50,725,1500,198,'#805000')
b.text('Consolidation steps','1. Import idempotently   2. Deduplicate   3. Validate source + permissions',78,812,32)
b.text('Consolidation steps2','4. Surface conflicts    5. Review / approve    6. Publish with revision checks',78,861,32)
b.text('Consolidation loop','Published baseline returns to the mothership; the next swarm starts from that version.',78,899,26,NAVY)
b.rect('Publication route out',1558,880,22,4,YELLOW)
b.arrow('Publication route up',1580,880,1580,237,YELLOW)
b.arrow('Publication to mothership',1580,237,1260,237,YELLOW)
b.text('Publication label','PUBLISH vNext',1280,202,28,WHITE)
b.window('Knowledge meter / proposed quality metrics',50,974,1500,83,'#805000')
b.text('Meter text','Validated facts / source coverage / freshness / unresolved conflicts / recall success',78,1041,28)
b.text('Status label','No silent last-writer-wins merge. Summaries retain provenance. Rejected candidates stay outside canon.',44,1111,25)
b.save()
svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128" shape-rendering="crispEdges" role="img" aria-labelledby="title"><title id="title">instantKV memory disk</title><path fill="#000080" d="M0 0h128v128H0z"/><path fill="#4080c0" d="M16 8h96v24H16z"/>'
svg += ''.join(f'<rect x="16" y="{48+i*24}" width="32" height="16" fill="#ffff80"/>' for i in range(3))
svg += ''.join(f'<rect x="{x*8}" y="{y*8}" width="8" height="8" fill="#fff"/>' for x,y in PIXELS)
(ASSETS/'logo.svg').write_text(svg+'</svg>\n')
print('Rendered brand, logo, swarm, architecture, lifecycle and distributed proposal.')
