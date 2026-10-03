"""Shared rolling request/token limiter for the verified project API limits."""
import time
import uuid
import tiktoken

class RateLimiter:
    def __init__(self,budget):
        self.budget=budget
        with budget.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS rate_events (id TEXT PRIMARY KEY, at REAL, units INTEGER)')
        self.encoding=tiktoken.get_encoding('o200k_base')
    def estimate(self,messages,max_output):
        units=max_output+128
        for message in messages:
            content=message['content']
            if isinstance(content,str):units+=len(self.encoding.encode(content,disallowed_special=()))
            else:
                for item in content:
                    if item.get('type')=='input_text':units+=len(self.encoding.encode(item['text'],disallowed_special=()))
                    elif item.get('type')=='input_image':units+=4096
        return units
    def acquire(self,units):
        # Headroom against the observed 500 RPM / 200K TPM account limits.
        if units>150000:raise ValueError('Single request exceeds conservative token-per-minute allocation')
        while True:
            now=time.time()
            with self.budget.connect() as db:
                db.execute('BEGIN IMMEDIATE')
                db.execute('DELETE FROM rate_events WHERE at<?',(now-61,))
                count,total=db.execute('SELECT COUNT(*),COALESCE(SUM(units),0) FROM rate_events').fetchone()
                if count<400 and total+units<=150000:
                    db.execute('INSERT INTO rate_events VALUES (?,?,?)',(str(uuid.uuid4()),now,units));return
            time.sleep(1)
