"""Explicit benchmark-only API calls. No service integration or secret logging."""
import time
from pathlib import Path
from openai import OpenAI, APIStatusError
from budget import Budget


class EvaluationAPI:
    def __init__(self, config, key_file, budget_file):
        self.config = config
        self.budget = Budget(budget_file, config['total_api_cap_usd'])
        self.client = OpenAI(api_key=Path(key_file).read_text().strip(), max_retries=0, timeout=180)

    def respond(self, messages, role):
        model = self.config[role+'_model']
        identity = self.budget.reserve(model, role, self.config['max_output_tokens'])
        started = time.perf_counter()
        try:
            result = self.client.responses.create(model=model, input=messages,
                reasoning={'effort':self.config['reasoning_effort']},
                max_output_tokens=self.config['max_output_tokens'],
                service_tier=self.config['service_tier'], store=False,
                extra_headers={'X-Client-Request-Id':identity})
        except APIStatusError as error:
            self.budget.failed(identity, unbilled=error.status_code in (400,401,403,404,429))
            raise RuntimeError(f'API HTTP {error.status_code}; evaluation call failed') from None
        except Exception:
            self.budget.failed(identity)
            raise RuntimeError('API transport failure; conservative request cost retained') from None
        charged = self.budget.settle(identity, result.usage)
        if result.status != 'completed' or not result.output_text.strip():
            raise RuntimeError('API output incomplete or empty; retain as evaluation failure')
        return {'text':result.output_text,'model':result.model,'usage':result.usage.model_dump(),
                'api_latency_ms':(time.perf_counter()-started)*1000,'charged_upper_usd':charged,
                'request_id':identity,'response_id':result.id}
