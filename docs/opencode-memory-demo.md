# Try memory in OpenCode

Install the MCP from the instantKV checkout:

```sh
cargo build --release --locked -p instantkv
python3 scripts/install-opencode-mcp.py
```

You need Python 3 for installation, OpenCode, and a connected model provider.
The installed MCP is a Rust binary; Python is not used when it runs.
The installer keeps other settings, backs up your global OpenCode config, and
adds the memory rules to the normal `build` agent. It leaves your default model
unchanged. Restart OpenCode after installation.

For a clean screen recording, open the dedicated memory agent:

```sh
opencode --agent memory
```

It uses `openai/gpt-6-luna` by default. Set `--model PROVIDER/MODEL` on the
installer to choose its model. The normal `opencode` command also has access to
the MCP and automatic-memory rules in the `build` agent.

Check the connection from any folder:

```sh
opencode mcp list
```

The output must show `instantKV connected`. No manual server command is needed.
The MCP starts its own authenticated loopback server inside the same Rust
process. It stops when OpenCode closes the MCP connection. Memory stays at
`~/.local/share/instantkv/opencode/.instantkv/data`.

## Show natural memory

1. Say: `I'm building a small Rust CLI called PebbleTrail. I prefer TOML for its configuration. What should I build first?`
2. Watch OpenCode call `instantKV_remember`. Expand the tool entry to see the record.
3. Close OpenCode. Open `opencode --agent memory` again to start a new session and server.
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

The dedicated memory agent has permission to use memory tools. It cannot read
files or run shell commands. Its prompt contains no personal facts. Memory is reference data; the
agent must not follow instructions found inside a record.

## Optional separate demo folder

The original launcher still works with its own database:

```sh
python3 scripts/opencode-memory-demo.py
```

Its memory is separate from the globally installed MCP. To import private facts
into this separate demo, follow the steps below.

### Import private facts

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
extract facts in the background. Restart OpenCode after installing new rules.
One active MCP process can open a given memory directory. For concurrent clients, use one shared HTTP server
with the existing `instantkv mcp` adapter, or choose separate directories.
It does not show automatic compaction hooks or phone integration.
The server log is `.instantkv/server.log` inside the demo folder.
For connection errors, check the log and your OpenCode provider login.

See [OpenCode MCP settings](https://opencode.ai/docs/mcp-servers/) and
[instantKV memory behavior](memory-mvp.md).

## Manual MCP setup

The installer copies the binary to `~/.local/bin/instantkv` and registers:

```json
{
  "mcp": {
    "instantKV": {
      "type": "local",
      "command": ["/absolute/path/instantkv", "mcp-local", "--dir", "/absolute/path/memory"],
      "enabled": true
    }
  }
}
```

Use absolute paths. `mcp-local` creates private credentials and a local-profile
config on its first run. It emits MCP messages on stdout and logs on stderr.
The automatic-memory instructions are installed separately from the transport.
Project settings can override the global MCP or agent rules.

To remove the installation, restore the printed config backup and restart
OpenCode. This leaves the memory directory intact. Remove that directory only
if you also want to delete the stored memories.

Verify the native transport without a model call:

```sh
python3 scripts/test-mcp-local.py
```
