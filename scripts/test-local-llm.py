#!/usr/bin/env python3
"""Contract tests for the local model tool loop; no inference is simulated as evidence."""
import copy
import importlib.util
import json
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('local_llm',Path(__file__).resolve().parents[1]/'examples/local-llm.py')
example = importlib.util.module_from_spec(spec)
spec.loader.exec_module(example)


class Bridge:
    tools = []
    def __init__(self): self.calls = []
    def invoke(self,name,args):
        self.calls.append((name,args))
        if name == 'recall':
            return {'items':[{'memory':{'content':'Prefer Rust'}}]}
        return {'error':'quota_exceeded'}


class ToolLoopTests(unittest.TestCase):
    def test_real_tool_results_and_failures_are_returned_to_the_model(self):
        bridge = Bridge()
        payloads = []
        def chat(payload):
            payloads.append(copy.deepcopy(payload))
            if len(payloads)==1:
                return {'role':'assistant','content':'','tool_calls':[
                    {'function':{'name':'recall','arguments':{'topic':'preferences'}}},
                    {'function':{'name':'remember','arguments':{'content':'another preference'}}},
                ]}
            self.assertEqual(json.loads(payload['messages'][-2]['content'])['items'][0]['memory']['content'],'Prefer Rust')
            self.assertEqual(json.loads(payload['messages'][-1]['content'])['error'],'quota_exceeded')
            return {'role':'assistant','content':'Rust is preferred. The new save failed.'}
        self.assertIn('save failed',example.run_chat('local-model','Recall preferences',bridge,chat))
        self.assertEqual(len(bridge.calls),2)
        self.assertEqual(payloads[0]['messages'][-1]['content'],'Recall preferences')

    def test_each_invocation_starts_with_fresh_context(self):
        payloads=[]
        def chat(payload):
            payloads.append(copy.deepcopy(payload))
            return {'role':'assistant','content':'Done'}
        for prompt in ['Session one','Session two']:
            example.run_chat('local-model',prompt,Bridge(),chat)
        self.assertEqual(len(payloads[1]['messages']),2)
        self.assertNotIn('Session one',json.dumps(payloads[1]))

    def test_unending_model_tool_calls_are_bounded(self):
        def chat(_):
            return {'role':'assistant','tool_calls':[{'function':{'name':'browse','arguments':{}}}]}
        with self.assertRaisesRegex(RuntimeError,'tool rounds'):
            example.run_chat('local-model','Browse',Bridge(),chat,max_rounds=2)


if __name__ == '__main__': unittest.main()
