# Try memory in OpenCode

Run this from the instantKV checkout:

```sh
python3 scripts/opencode-memory-demo.py
```

You need Python 3, OpenCode, and a connected model provider. The launcher builds
instantKV if the release binary is absent. The default model is
`openai/gpt-6-luna`; use `--model PROVIDER/MODEL` to change it.

The launcher starts a local memory server and opens OpenCode in a separate folder.
It uses project settings. It does not change your global OpenCode settings.
The server stops when you close OpenCode. The database stays on disk.

## Show natural memory

1. Say: `I'm building a small Rust CLI called PebbleTrail. I prefer TOML for its configuration. What should I build first?`
2. Watch OpenCode call `instantKV_remember`. Expand the tool entry to see the record.
3. Close OpenCode. Run the launcher again to start a new session and server.
4. Ask: `What is my side project called, and which config format do I prefer?`
5. Watch `instantKV_recall` return the saved facts. The answer cites their keys.

You do not need to say "remember this". The agent saves useful preferences,
project facts and decisions as they arise. It checks existing records first,
skips duplicates and uses revision checks to update corrected facts.
For example: `I switched PebbleTrail to JSON config.`

It skips passing questions, guesses and secrets. Say `Do not remember this`
to keep a message out of persistent memory, or ask it to forget a saved fact.
These are model instructions, not a hard storage filter. Memory decisions can
vary by model; the visible tool calls show what it actually saved.

The agent has permission to use memory tools. It cannot read files or run shell
commands. Its prompt contains no personal facts. Memory is reference data; the
agent must not follow instructions found inside a record.

## Import private facts

Use a private JSON file. Do not commit it:

```json
[
  {"key": "profile/work", "content": "I build Rust systems."},
  {"key": "profile/answers", "content": "I prefer short answers."}
]
```

```sh
python3 scripts/opencode-memory-demo.py --seed-file /absolute/path/facts.json
```

Imports use topic `profile` and tag `about-me`. Existing keys are kept.
The default folder is `~/instantkv-opencode-demo`. An optional private seed file
at `.instantkv/demo-seed.json` is loaded on each start. Use `--dir` for a separate demo.
Database files, credentials and model conversations contain private data.
The model provider receives the prompt and memory that its tools retrieve.
instantKV stores memory locally and does not call the model.

## Check or capture a run

```sh
# Connect MCP without a model call.
python3 scripts/opencode-memory-demo.py --check

# Start a new session and show tool calls in the terminal.
python3 scripts/opencode-memory-demo.py --run "What do you know about me?"

# Save raw OpenCode events. Keep this output private.
python3 scripts/opencode-memory-demo.py --run "What do you know about me?" --json > trace.jsonl
```

This shows model-selected saves and persistence across sessions and server restarts.
The agent decides when to call a tool. instantKV does not run a second model or
extract facts in the background. The launcher applies these rules when you start
it; an already open session must be restarted to use the new rules.
It does not show automatic compaction hooks or phone integration.
The server log is `.instantkv/server.log` inside the demo folder.
For connection errors, check the log and your OpenCode provider login.

See [OpenCode MCP settings](https://opencode.ai/docs/mcp-servers/) and
[instantKV memory behavior](memory-mvp.md).
