import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from budget import Budget, BudgetExceeded
from datasets import read_json
from backend import chunks
from run import metrics, build_context

class HarnessTests(unittest.TestCase):
    def test_concurrent_cap(self):
        with tempfile.TemporaryDirectory() as tmp:
            b=Budget(Path(tmp)/'budget.sqlite',1)
            def attempt(_):
                try:return b.reserve('gpt-6-luna','reader')
                except BudgetExceeded:return None
            with ThreadPoolExecutor(max_workers=8) as pool:
                reservations=list(pool.map(attempt,range(20)))
            self.assertEqual(sum(x is not None for x in reservations),3)
            self.assertLessEqual(b.summary()['accounted_upper_usd'],1)
            for identity in filter(None,reservations):b.failed(identity)
            self.assertEqual(b.summary()['statuses'],{'failed':3})
            with self.assertRaises(ValueError):Budget(b.path,250)
    def test_billed_and_unbilled_failures(self):
        with tempfile.TemporaryDirectory() as tmp:
            b=Budget(Path(tmp)/'budget.sqlite')
            a=b.reserve('gpt-6-luna','reader');b.failed(a,unbilled=True)
            self.assertEqual(b.summary()['accounted_upper_usd'],0)
            a=b.reserve('gpt-6-luna','reader')
            charged=b.settle(a,{'input_tokens':1000,'output_tokens':100,'input_tokens_details':{'cached_tokens':100}})
            self.assertAlmostEqual(charged,.00016375)
    def test_lossless_unicode_chunks(self):
        text='你好🌎'*10000
        values=list(chunks(text))
        self.assertEqual(''.join(values),text)
        self.assertTrue(all(len(v.encode())<=14000 for v in values))
    def test_literal_cannot_execute(self):
        self.assertEqual(read_json("{'a': [1, 2]}"),{'a':[1,2]})
        with self.assertRaises(ValueError):read_json("__import__('os').system('false')")
    def test_metrics_dedup_and_denominator(self):
        m=metrics(['a','a','x','b'],{'a':1,'b':1})
        self.assertEqual(m['recall_at_1'],.5)
        self.assertEqual(m['recall_at_5'],1)
        self.assertIsNone(metrics([],None))
    def test_context_budget(self):
        import tiktoken
        hit={'memory':{'content':'hello world '*500,'metadata':{'source_id':'a','part':0}}}
        text,_,cut=build_context([hit],{'context_limit_tokens':50,'top_k':10})
        self.assertLessEqual(len(tiktoken.get_encoding('o200k_base').encode(text)),50)
        self.assertTrue(cut)

if __name__=='__main__':unittest.main()

class RateTests(unittest.TestCase):
    def test_shared_rate_accounting(self):
        from rate import RateLimiter
        with tempfile.TemporaryDirectory() as tmp:
            budget=Budget(Path(tmp)/'budget.sqlite')
            a=RateLimiter(budget);b=RateLimiter(budget)
            units=a.estimate([{'role':'user','content':'Hello'}],4096)
            self.assertGreaterEqual(units,4097)
            a.acquire(units);b.acquire(units)
            with budget.connect() as db:
                count,total=db.execute('SELECT COUNT(*),SUM(units) FROM rate_events').fetchone()
            self.assertEqual(count,2);self.assertEqual(total,units*2)
            with self.assertRaises(ValueError):a.acquire(150001)
