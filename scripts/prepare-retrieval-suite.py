#!/usr/bin/env python3
"""Prepare full BEIR/LoCoMo and a fixed 12-question LongMemEval-S retrieval sample.

Answers, generated summaries, observations and evidence labels never enter content.
"""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def beir(path):
    docs = [json.loads(line) for line in (path/'corpus.jsonl').read_text().splitlines()]
    queries = {q['_id']: q['text'] for q in map(json.loads, (path/'queries.jsonl').read_text().splitlines())}
    qrels = {}
    with (path/'qrels/test.tsv').open() as f:
        for row in csv.DictReader(f, delimiter='\t'):
            if int(row['score']) > 0:
                qrels.setdefault(row['query-id'], {})[row['corpus-id']] = int(row['score'])
    return {'name': 'BEIR '+path.name, 'provenance': {
        'url': 'https://public.ukp.informatik.tu-darmstadt.de/thakur/BEIR/datasets/'+path.name+'.zip',
        'files': {str(p.relative_to(path)): digest(p) for p in [path/'corpus.jsonl', path/'queries.jsonl', path/'qrels/test.tsv']}},
        'selection': 'Full corpus and full test split. Original queries. Self document excluded, as in BEIR evaluation.',
        'documents': [{'id': d['_id'], 'scope': 'corpus', 'content': d['title']+'\n'+d['text']} for d in docs],
        'queries': [{'id': qid, 'scope': 'corpus', 'category': 'all', 'text': queries[qid],
                     'relevant': qrels[qid], 'exclude_id': qid} for qid in sorted(qrels)]}


def locomo(path):
    conversations = json.loads(path.read_text())
    documents = []; queries = []; exclusions = []
    labels = {1: 'multi-hop', 2: 'temporal', 3: 'open-domain', 4: 'single-hop', 5: 'adversarial'}
    for conv in conversations:
        scope = conv['sample_id']; turns = {}
        for name, session in conv['conversation'].items():
            if not isinstance(session, list): continue
            date = conv['conversation'][name+'_date_time']
            event_ms = int(datetime.strptime(date, '%I:%M %p on %d %B, %Y').replace(tzinfo=timezone.utc).timestamp()*1000)
            for turn in session:
                identity = scope+'/'+turn['dia_id']
                assert turn['dia_id'] not in turns
                turns[turn['dia_id']] = identity
                text = date+'\n'+turn['speaker']+': '+turn['text']
                if turn.get('blip_caption'): text += '\nImage caption: '+turn['blip_caption']
                documents.append({'id': identity, 'scope': scope, 'content': text, 'event_ms': event_ms})
        for i, question in enumerate(conv['qa']):
            qid = scope+'/'+str(i)
            refs = list(dict.fromkeys(ref for evidence in question.get('evidence', [])
                                     for ref in re.findall(r'D\d+:\d+', evidence)))
            if question['category'] == 5 or not refs or any(ref not in turns for ref in refs):
                exclusions.append({'id': qid, 'category': labels[question['category']],
                    'reason': 'adversarial has no positive evidence' if question['category'] == 5 else 'missing or unresolved evidence labels'})
                continue
            queries.append({'id': qid, 'scope': scope, 'category': labels[question['category']],
                            'text': question['question'], 'relevant': {turns[ref]: 1 for ref in refs}})
    return {'name': 'LoCoMo evidence retrieval', 'provenance': {
        'url': 'https://github.com/snap-research/locomo/blob/3eb6f2c585f5e1699204e3c3bdf7adc5c28cb376/data/locomo10.json',
        'sha256': digest(path)},
        'selection': {'conversations': len(conversations), 'original_questions': sum(len(c['qa']) for c in conversations),
                      'exclusions': exclusions, 'policy': 'All ten full histories. All non-adversarial questions with complete resolvable evidence. Raw turns plus supplied image captions/date/speaker; no generated observations, summaries or answers. Dates have no timezone; interpreted as UTC for storage.'},
        'documents': documents, 'queries': queries}


def longmemeval(path, source):
    instances = json.loads(path.read_text())
    types = sorted({q['question_type'] for q in instances})
    selected = []
    for kind in types:
        eligible = sorted((q for q in instances if q['question_type'] == kind and not q['question_id'].endswith('_abs')),
                          key=lambda q: q['question_id'])
        selected.extend(eligible[:2])
    assert len(selected) == 12
    documents = []; queries = []
    for question in selected:
        scope = question['question_id']
        assert len(question['haystack_session_ids']) == len(question['haystack_dates']) == len(question['haystack_sessions'])
        sessions = {}
        for sid, date, turns in zip(question['haystack_session_ids'], question['haystack_dates'], question['haystack_sessions']):
            text = date+'\n'+'\n'.join(turn['role']+': '+turn['content'] for turn in turns)
            sessions[sid] = sessions.get(sid, '') + ('\n' if sid in sessions else '') + text
        documents.extend({'id': scope+'/'+sid, 'scope': scope, 'content': text} for sid, text in sessions.items())
        relevant = {scope+'/'+sid: 1 for sid in question['answer_session_ids']}
        assert relevant and set(relevant) <= {d['id'] for d in documents if d['scope'] == scope}
        queries.append({'id': scope, 'scope': scope, 'category': question['question_type'],
                        'text': question['question'], 'relevant': relevant})
    return {'name': 'LongMemEval-S session retrieval sample', 'provenance': {
        'url': 'https://huggingface.co/datasets/'+source['repository']+'/resolve/'+source['revision']+'/longmemeval_s_cleaned.json',
        'sha256': digest(path), 'revision': source['revision']},
        'selection': {'policy': 'First two non-abstention question IDs in lexical order per each of six categories; fixed before retrieval. Full original haystacks, not oracle histories. Repeated session IDs are joined without discarding text. Session ID recall, not QA accuracy or evidence-turn recall. No answers, has_answer labels or question text in indexed content.',
                      'selected_ids': [q['question_id'] for q in selected], 'original_questions': len(instances), 'questions_per_category': 2},
        'documents': documents, 'queries': queries}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--kind', choices=['beir', 'locomo', 'longmemeval'], required=True)
    args = parser.parse_args()
    if args.kind == 'beir': dataset = beir(args.input)
    elif args.kind == 'locomo': dataset = locomo(args.input)
    else: dataset = longmemeval(args.input, json.loads(args.input.with_name('longmemeval-source.json').read_text()))
    assert len({d['id'] for d in dataset['documents']}) == len(dataset['documents'])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(dataset, ensure_ascii=False)+'\n')
    print(dataset['name'], 'documents', len(dataset['documents']), 'queries', len(dataset['queries']))


if __name__ == '__main__': main()
