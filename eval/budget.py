"""Process-safe hard spending cap. API credentials never enter this ledger."""
import json
import sqlite3
import uuid
from contextlib import contextmanager
from pathlib import Path


class BudgetExceeded(RuntimeError):
    pass


class Budget:
    def __init__(self, path, cap=250.0):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.cap = cap
        with self.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS calls (id TEXT PRIMARY KEY, status TEXT, reserved REAL, charged REAL, model TEXT, role TEXT, usage TEXT)')
            db.execute('CREATE TABLE IF NOT EXISTS policy (id INTEGER PRIMARY KEY CHECK(id=1), cap REAL NOT NULL)')
            db.execute('INSERT OR IGNORE INTO policy VALUES (1,?)',(cap,))
            if db.execute('SELECT cap FROM policy WHERE id=1').fetchone()[0] != cap:
                raise ValueError('Shared ledger cap cannot change between runs')
        self.path.chmod(0o600)

    @contextmanager
    def connect(self):
        db=sqlite3.connect(self.path, timeout=60, isolation_level='IMMEDIATE')
        try:
            with db:
                yield db
        finally:
            db.close()

    def reserve(self, model, role, max_output=4096):
        if model != 'gpt-6-luna':
            raise ValueError('This campaign freezes gpt-6-luna; other models need separate pricing/config.')
        # Full model input window at conservative long-context/cache-write price.
        # This also bounds image token cost; callers cannot exceed the model window.
        ceiling = 1_050_000 * .25 / 1e6 + max_output * .75 / 1e6
        identity = str(uuid.uuid4())
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            used = db.execute("SELECT COALESCE(SUM(CASE WHEN status='reserved' THEN reserved ELSE charged END),0) FROM calls").fetchone()[0]
            if used + ceiling > self.cap:
                raise BudgetExceeded(f'Campaign budget exhausted: accounted ${used:.4f}, cap ${self.cap:.2f}')
            db.execute('INSERT INTO calls VALUES (?, ?, ?, ?, ?, ?, ?)', (identity, 'reserved', ceiling, 0, model, role, None))
        return identity

    def settle(self, identity, usage):
        data = usage.model_dump() if hasattr(usage, 'model_dump') else usage
        input_tokens = data['input_tokens']; output_tokens = data['output_tokens']
        cached = (data.get('input_tokens_details') or {}).get('cached_tokens', 0)
        long = input_tokens > 272000
        rates = (.25, .025, .75) if long else (.125, .0125, .50)
        # Upper estimate includes possible cache-write premium on all uncached input.
        # Published standard text estimate is retained separately in usage.
        charged = ((input_tokens-cached)*rates[0] + cached*rates[1] + output_tokens*rates[2])/1e6
        with self.connect() as db:
            reserved = db.execute('SELECT reserved FROM calls WHERE id=?', (identity,)).fetchone()[0]
            if charged > reserved + 1e-12:
                raise RuntimeError('Usage exceeded the conservative reservation; stop the campaign.')
            db.execute("UPDATE calls SET status='settled', charged=?, usage=? WHERE id=?", (charged, json.dumps(data), identity))
        return charged

    def failed(self, identity, unbilled=False):
        with self.connect() as db:
            db.execute("UPDATE calls SET status='failed', charged=CASE WHEN ? THEN 0 ELSE reserved END WHERE id=?", (unbilled, identity))

    def summary(self):
        with self.connect() as db:
            rows = db.execute('SELECT status,COUNT(*),SUM(charged),SUM(reserved) FROM calls GROUP BY status').fetchall()
        accounted = sum((reserved if status == 'reserved' else charged) or 0 for status, count, charged, reserved in rows)
        return {'cap_usd':self.cap,'accounted_upper_usd':accounted,'remaining_usd':self.cap-accounted,
                'statuses':{status:count for status,count,_,_ in rows},'pricing':'Conservative billed upper estimate, including potential cache-write premium; not an account invoice.'}
