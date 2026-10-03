"""Full official source histories. QA labels never enter the stored documents."""
import ast
from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sqlite3


def read_json(value):
    if not isinstance(value,str):return value
    try:return json.loads(value)
    except json.JSONDecodeError:return ast.literal_eval(value)


def longmemeval(path):
    import ijson
    with Path(path).open('rb') as f:
        for q in ijson.items(f,'item'):
            sessions={}
            for sid,date,turns in zip(q['haystack_session_ids'],q['haystack_dates'],q['haystack_sessions'],strict=True):
                text=date+'\n'+'\n'.join(t['role']+': '+t['content'] for t in turns)
                sessions[sid]=sessions.get(sid,'')+('\n' if sid in sessions else '')+text
            docs=[{'id':sid,'content':text} for sid,text in sessions.items()]
            relevant={sid:1 for sid in q['answer_session_ids']}
            if not set(relevant)<=set(sessions):raise ValueError('LongMemEval evidence source missing')
            question={'id':q['question_id'],'text':q['question'],'answer':q['answer'],
                      'category':'abstention' if q['question_id'].endswith('_abs') else q['question_type'],
                      'original_category':q['question_type'],'date':q['question_date'],
                      'relevant':relevant,'abstention':q['question_id'].endswith('_abs'),'rubric_kind':'longmemeval'}
            yield {'id':q['question_id'],'documents':lambda docs=docs:iter(docs),'questions':[question]}


def locomo(path):
    labels={1:'multi-hop',2:'temporal',3:'open-domain',4:'single-hop',5:'abstention'}
    for conv in json.loads(Path(path).read_text()):
        docs=[];ids=set()
        for name,session in conv['conversation'].items():
            if not isinstance(session,list):continue
            date=conv['conversation'][name+'_date_time']
            event=int(datetime.strptime(date,'%I:%M %p on %d %B, %Y').replace(tzinfo=timezone.utc).timestamp()*1000)
            for turn in session:
                text=date+'\n'+turn['speaker']+': '+turn['text']
                if turn.get('blip_caption'):text+='\nImage caption: '+turn['blip_caption']
                docs.append({'id':turn['dia_id'],'content':text,'event_ms':event});ids.add(turn['dia_id'])
        questions=[]
        for i,q in enumerate(conv['qa']):
            refs=list(dict.fromkeys(ref for r in q.get('evidence',[]) for ref in re.findall(r'D\d+:\d+',r)))
            relevant={ref:1 for ref in refs} if refs and set(refs)<=ids and q['category']!=5 else None
            questions.append({'id':conv['sample_id']+'/'+str(i),'text':q['question'],
                'answer':str(q.get('answer','The conversation does not provide the information needed to answer.')),
                'category':labels[q['category']],'relevant':relevant,'abstention':q['category']==5,
                'rubric_kind':'locomo','evidence_unavailable_reason':None if relevant else 'No positive evidence labels for abstention, or unresolved official evidence'})
        yield {'id':conv['sample_id'],'documents':lambda docs=docs:iter(docs),'questions':questions}


def ama(path):
    with Path(path).open() as f:
        for line in f:
            row=json.loads(line)
            def documents(row=row):
                for i,turn in enumerate(row['trajectory']):
                    yield {'id':str(turn.get('turn_idx',i)),'content':row['task']+'\nAction: '+str(turn['action'])+'\nObservation: '+str(turn['observation'])}
            questions=[{'id':str(row['episode_id'])+'/'+str(q.get('question_uuid',i)),
                'text':q['question'],'answer':q['answer'],'category':q.get('type',row['task_type']),
                'relevant':None,'rubric_kind':'ama','task':row['task'],'task_type':row['task_type'],
                'domain':row['domain'],'episode_id':str(row['episode_id'])} for i,q in enumerate(row['qa_pairs'])]
            yield {'id':str(row['episode_id']),'documents':documents,'questions':questions}


def beam(paths):
    import pyarrow.parquet as pq
    def flatten(value):
        if isinstance(value,list):
            for v in value:yield from flatten(v)
        elif isinstance(value,dict) and 'content' in value:yield value
        elif isinstance(value,dict) and 'turns' in value:
            yield from flatten(value['turns'])
        elif isinstance(value,dict):
            # Parquet struct fields may reorder numbered plan groups lexically.
            for key in sorted(value,key=lambda x:[int(p) if p.isdigit() else p for p in re.split(r'(\d+)',x)]):
                yield from flatten(value[key])
        else:raise ValueError('Unexpected BEAM chat shape')
    for path in paths:
        size=Path(path).name.split('-')[0]
        for batch in pq.ParquetFile(path).iter_batches(batch_size=1):
            row=batch.to_pylist()[0]
            def documents(row=row):
                for i,turn in enumerate(flatten(row['chat'])):
                    yield {'id':str(i),'content':str(turn.get('time_anchor',''))+'\n'+str(turn['role'])+': '+turn['content']}
            questions=[]
            probes=read_json(row['probing_questions'])
            for category,qs in probes.items():
                for i,q in enumerate(qs):
                    questions.append({'id':size+'/'+row['conversation_id']+'/'+category+'/'+str(i),
                        'text':q['question'],'answer':q.get('ideal_response',q.get('ideal_answer',q.get('answer',q.get('ideal_summary',q.get('expected_compliance',''))))),'category':category,
                        'relevant':None,'rubric_kind':'beam','rubrics':q['rubric'],
                        'abstention':category=='abstention','size':size})
            yield {'id':size+'/'+row['conversation_id'],'documents':documents,'questions':questions}


def trajectory_index(source):
    path=Path(source).with_suffix('.index.sqlite3')
    stamp=Path(str(path)+'.ready')
    if stamp.exists() and stamp.read_text()==str(Path(source).stat().st_size):return path
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE IF NOT EXISTS trajectories (id TEXT PRIMARY KEY, data TEXT)')
        with Path(source).open() as f:
            for line in f:
                row=json.loads(line);db.execute('INSERT OR REPLACE INTO trajectories VALUES (?,?)',(row['id'],line))
    stamp.write_text(str(Path(source).stat().st_size));return path


def v2(root,tier):
    root=Path(root);index=trajectory_index(root/'trajectories.jsonl')
    mapping=json.loads((root/f'haystacks/lme_v2_{tier}.json').read_text())
    groups=defaultdict(list)
    with (root/'questions.jsonl').open() as f:
        for line in f:
            q=json.loads(line);ids=tuple(mapping[q['id']])
            groups[ids].append({'id':q['id'],'text':q['question'],'answer':q['answer'],
                'category':q['question_type'],'domain':q['domain'],'relevant':None,
                'rubric_kind':'v2','official_question':q,'image':str(root/q['image']) if q.get('image') else None})
    for ids,questions in groups.items():
        group=hashlib.sha256(json.dumps(ids).encode()).hexdigest()[:16]
        def documents(ids=ids):
            with sqlite3.connect(index) as db:
                for identity in ids:
                    result=db.execute('SELECT data FROM trajectories WHERE id=?',(identity,)).fetchone()
                    if not result:raise ValueError('V2 haystack trajectory missing')
                    traj=json.loads(result[0])
                    for state in traj['states']:
                        text='Goal: '+traj['goal']+'\nOutcome: '+traj['outcome']+'\nURL: '+str(state['url'])+'\nAction: '+str(state.get('action') or '')+'\nThought: '+str(state.get('thought') or '')+'\nObservation: '+state['accessibility_tree']
                        yield {'id':identity+'/'+str(state['state_index']),'content':text,
                            'image':str(root/state['screenshot']) if state.get('screenshot') else None}
        yield {'id':tier+'/'+group,'documents':documents,'questions':questions,'trajectory_count':len(ids)}


def cases(suite,data_root):
    root=Path(data_root)
    if suite=='longmemeval-s':return longmemeval(root/'longmemeval_s_cleaned.json')
    if suite=='locomo':return locomo(root/'locomo10.json')
    if suite=='ama-bench':return ama(root/'ama/test/open_end_qa_set.jsonl')
    if suite=='beam':return beam(sorted((root/'beam/data').glob('*.parquet')))
    if suite=='beam-10m':return beam(sorted((root/'beam-10m/data').glob('*.parquet')))
    if suite.startswith('longmemeval-v2-'):return v2(root/'lme-v2',suite.rsplit('-',1)[1])
    raise ValueError('Unknown official suite: '+suite)
