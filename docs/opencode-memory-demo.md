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

## Show a save and a recall

1. Ask: `Remember that I prefer short answers and build Rust systems.`
2. Watch OpenCode call `instantKV_remember`. Expand the tool entry to see the record.
3. Close OpenCode. Run the launcher again to start a new session and server.
4. Ask: `What do you know about my work and how I like answers?`
5. Watch `instantKV_recall` return the saved facts. The answer cites their keys.

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

This shows explicit persistence across sessions and server restarts.
It does not show automatic compaction hooks or phone integration.
The server log is `.instantkv/server.log` inside the demo folder.
For connection errors, check the log and your OpenCode provider login.

See [OpenCode MCP settings](https://opencode.ai/docs/mcp-servers/) and
[instantKV memory behavior](memory-mvp.md).
