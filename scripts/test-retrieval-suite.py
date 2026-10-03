#!/usr/bin/env python3
import importlib.util
from pathlib import Path
import unittest
import json
import tempfile
spec = importlib.util.spec_from_file_location('suite', Path(__file__).with_name('retrieval-suite.py'))
suite = importlib.util.module_from_spec(spec)
spec.loader.exec_module(suite)

class HarnessTests(unittest.TestCase):
    def test_graded_gain_and_missing_evidence(self):
        result = suite.metrics(['b', 'x', 'a'], {'a': 2, 'b': 1, 'c': 1}, 2)
        self.assertAlmostEqual(result['recall_at_2'], 1/3)
        self.assertAlmostEqual(result['ndcg_at_2'], 1/(2+1/suite.math.log2(3)))
        self.assertEqual(result['all_evidence_at_2'], 0)
    def test_deduplication_and_self_exclusion(self):
        self.assertEqual(suite.unique_ids(['self', 'a', 'a', 'b'], 'self'), ['a', 'b'])
        self.assertEqual(suite.metrics(['a', 'a', 'b'], {'b': 1}, 2)['mrr_at_2'], .5)
    def test_lossless_unicode_chunk_bounds(self):
        source = ('🌍café\n' * 6000)
        chunks = list(suite.chunks(source))
        self.assertEqual(''.join(chunks), source)
        self.assertTrue(all(len(c) <= 9500 and len(c.encode()) <= 14000 for c in chunks))

class PreparationTests(unittest.TestCase):
    def test_locomo_compound_references_without_summary_leak(self):
        spec = importlib.util.spec_from_file_location('prepare', Path(__file__).with_name('prepare-retrieval-suite.py'))
        prepare = importlib.util.module_from_spec(spec); spec.loader.exec_module(prepare)
        source = [{'sample_id': 'scope', 'conversation': {
            'session_1_date_time': '1:00 pm on 1 January, 2024',
            'session_1': [{'dia_id': 'D1:1', 'speaker': 'A', 'text': 'first'},
                          {'dia_id': 'D1:2', 'speaker': 'B', 'text': 'second'}]},
            'session_summary': 'SUMMARY_SECRET', 'qa': [{'category': 1, 'question': 'which?',
                'answer': 'ANSWER_SECRET', 'evidence': ['D1:1; D1:2']}]}]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'source.json'; path.write_text(json.dumps(source))
            result = prepare.locomo(path)
        self.assertEqual(len(result['queries'][0]['relevant']), 2)
        self.assertTrue(all('SECRET' not in doc['content'] for doc in result['documents']))

    def test_longmemeval_keeps_source_and_excludes_labels(self):
        spec = importlib.util.spec_from_file_location('prepare', Path(__file__).with_name('prepare-retrieval-suite.py'))
        prepare = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(prepare)
        instances = []
        for kind in range(6):
            for index in range(2):
                instances.append({'question_id': f'{kind}-{index}', 'question_type': str(kind),
                    'question': 'QUESTION_SECRET', 'answer': 'ANSWER_SECRET',
                    'haystack_session_ids': ['a', 'a'], 'haystack_dates': ['date1', 'date2'],
                    'haystack_sessions': [[{'role': 'user', 'content': 'SOURCE1', 'has_answer': True}],
                                         [{'role': 'assistant', 'content': 'SOURCE2'}]],
                    'answer_session_ids': ['a']})
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'source.json'
            path.write_text(json.dumps(instances))
            result = prepare.longmemeval(path, {'repository': 'test', 'revision': 'test'})
        self.assertEqual(len(result['documents']), 12)
        for doc in result['documents']:
            self.assertIn('SOURCE1', doc['content'])
            self.assertIn('SOURCE2', doc['content'])
            self.assertNotIn('SECRET', doc['content'])
            self.assertNotIn('has_answer', doc['content'])

if __name__ == '__main__': unittest.main()
