#!/usr/bin/env python3
"""Check retrieval metric math and the fixed keyword adapter."""
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('comparison', Path(__file__).with_name('compare-supermemory.py'))
comparison = importlib.util.module_from_spec(spec)
spec.loader.exec_module(comparison)


class Metrics(unittest.TestCase):
    def test_perfect_and_empty_rankings(self):
        relevant = {'a': 1, 'b': 1}
        self.assertEqual(comparison.metric(['a', 'b'], relevant),
                         {'recall_at_10': 1, 'ndcg_at_10': 1, 'mrr_at_10': 1})
        self.assertEqual(comparison.metric([], relevant),
                         {'recall_at_10': 0, 'ndcg_at_10': 0, 'mrr_at_10': 0})

    def test_duplicate_chunks_and_rank_cutoff(self):
        result = comparison.metric(['x', 'a', 'a', 'b'], {'a': 1, 'b': 1})
        self.assertEqual(result['recall_at_10'], 1)
        self.assertEqual(result['mrr_at_10'], 0.5)
        self.assertAlmostEqual(result['ndcg_at_10'],
                               (1/comparison.math.log2(3) + 1/comparison.math.log2(4)) /
                               (1 + 1/comparison.math.log2(3)))
        self.assertEqual(comparison.metric([str(i) for i in range(11)], {'10': 1})['recall_at_10'], 0)

    def test_adapter_is_bounded_and_deterministic(self):
        self.assertEqual(comparison.keyword_adapter('The effects of alpha and beta in the brain.'),
                         'effects alpha beta brain')
        self.assertEqual(len(comparison.keyword_adapter(' '.join('term'+str(i) for i in range(20))).split()), 8)
        self.assertLessEqual(len(comparison.keyword_adapter('x'*1000).encode()), 256)


if __name__ == '__main__':
    unittest.main()
