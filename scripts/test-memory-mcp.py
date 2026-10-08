#!/usr/bin/env python3
"""Focused MCP, managed-child and isolated-installer checks. No model or global config."""

import io
import json
import os
from pathlib import Path
import runpy
import select
import signal
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "examples"))
from memory_controller import MemoryController, StoreError  # noqa: E402
from memory_controller.mcp import MCPServer, MAX_MESSAGE_BYTES, STARTUP_TIMEOUT_SECONDS  # noqa: E402

# Reuse the existing fake native CAS contract, not another lifecycle implementation.
fixtures = runpy.run_path(str(ROOT / "scripts/test-memory-controller.py"))
Node, proposal = fixtures["Node"], fixtures["proposal"]


def request(method, params=None, identifier=1):
    return {"jsonrpc": "2.0", "id": identifier, "method": method, "params": params or {}}


def initialize(server):
    return server.handle(request("initialize", {"protocolVersion": "2025-06-18"}))


def call(server, name, arguments=None):
    response = server.handle(request("tools/call", {"name": name, "arguments": arguments or {}}))
    if "error" in response:
        return response
    result = response["result"]
    envelope = json.loads(result["content"][0]["text"])
    assert result["structuredContent"] == envelope
    assert type(envelope["observed_at_ms"]) is int and envelope["observed_at_ms"] > 0
    return envelope["result"], result["isError"]


class ProtocolTests(unittest.TestCase):
    def test_wire_bounds_and_invalid_requests_never_mutate(self):
        node = Node()
        server = MCPServer(MemoryController(node))
        self.assertIn("error", server.handle(request("tools/list")))
        self.assertEqual(initialize(server)["result"]["capabilities"], {"tools": {"listChanged": False}})
        names = {item["name"] for item in server.handle(request("tools/list"))["result"]["tools"]}
        self.assertEqual(names, {"apply", "inspect", "profile", "context", "forget"})
        invalid = [
            ("profile", {"scope": "another"}), ("profile", {"namespace": "another"}),
            ("profile", {"max_bytes": True}), ("context", {"query": "é" * 9000}),
            ("forget", {"entity": "user", "attribute": "response_style", "expected_revision": 0}),
            ("apply", {"proposal": proposal(source="x", source_extra="no")}),
        ]
        for name, arguments in invalid:
            result = call(server, name, arguments)
            self.assertTrue(isinstance(result, dict) or result[1])
        bad_role = proposal()
        bad_role["source"]["role"] = "assistant"
        self.assertIn("error", call(server, "apply", {"proposal": bad_role}))
        notification = request("tools/call", {"name": "apply", "arguments": {"proposal": proposal()}})
        del notification["id"]
        self.assertIsNone(server.handle(notification))
        self.assertEqual(node.writes, 0)
        output = io.BytesIO()
        raw = b'{"jsonrpc":"2.0","id":1,"id":2,"method":"ping"}\n' + b'{"x":NaN}\n'
        server.serve(io.BytesIO(raw), output)
        self.assertEqual(len(output.getvalue().splitlines()), 2)
        self.assertTrue(all(json.loads(line)["error"]["code"] == -32700 for line in output.getvalue().splitlines()))
        output = io.BytesIO()
        server.serve(io.BytesIO(b"x" * (MAX_MESSAGE_BYTES + 1) + b"\n" + json.dumps(notification).encode()), output)
        self.assertEqual(len(output.getvalue().splitlines()), 1)
        self.assertEqual(node.writes, 0)

    def test_lifecycle_receipts_and_errors_keep_exact_retry_contract(self):
        node = Node()
        server = MCPServer(MemoryController(node))
        initialize(server)
        original = proposal()
        saved, failed = call(server, "apply", {"proposal": original})
        self.assertFalse(failed)
        replay, _ = call(server, "apply", {"proposal": original})
        self.assertTrue(replay["replayed"])
        conflict, failed = call(server, "apply", {"proposal": proposal("long", source="turn-2", occurred=20)})
        self.assertTrue(failed)
        self.assertEqual(conflict["status"], "conflict")
        self.assertEqual(call(server, "profile")[0]["items"], [])
        detail, _ = call(server, "inspect", {"entity": "user", "attribute": "response_style"})
        corrected, failed = call(server, "apply", {"proposal": proposal("short", source="turn-3", occurred=30,
                               operation="correct", expected_revision=detail["revision"])})
        self.assertFalse(failed)
        _, failed = call(server, "forget", {"entity": "user", "attribute": "response_style", "expected_revision": saved["revision"]})
        self.assertTrue(failed)
        forgotten, failed = call(server, "forget", {"entity": "user", "attribute": "response_style", "expected_revision": corrected["revision"]})
        self.assertFalse(failed)
        self.assertEqual(forgotten["status"], "forgotten")
        self.assertTrue(call(server, "apply", {"proposal": original})[1])
        secret = "private credential and user input"
        count = 0
        def disconnected(*_args, **_kwargs):
            nonlocal count
            count += 1
            raise StoreError(secret)
        node.get = disconnected
        error, failed = call(server, "apply", {"proposal": original})
        self.assertTrue(failed)
        self.assertNotIn(secret, json.dumps(error))
        self.assertEqual(count, 1)


FAKE_NATIVE = '''#!/usr/bin/env python3
import argparse, json, os
from pathlib import Path
from http.server import BaseHTTPRequestHandler, HTTPServer
p = argparse.ArgumentParser()
p.add_argument('command')
p.add_argument('--dir', type=Path)
p.add_argument('--bind')
a = p.parse_args()
a.dir.mkdir(parents=True, exist_ok=True)
(a.dir / 'fake.pid').write_text(str(os.getpid()))
private = a.dir / '.instantkv'
private.mkdir(exist_ok=True)
secrets = private / 'credentials.env'
secrets.write_text('INSTANTKV_APP_TOKEN=' + 'x'*64 + '\\n')
secrets.chmod(0o600)
print('native secret should never reach MCP stdout', flush=True)
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'{}')
    def log_message(self, *_): pass
host, port = a.bind.split(':')
HTTPServer((host, int(port)), Handler).serve_forever()
'''


def executable(path, contents):
    path.write_text(contents)
    path.chmod(0o755)
    return path


def wait_for(path):
    deadline = time.monotonic() + STARTUP_TIMEOUT_SECONDS + 4
    while time.monotonic() < deadline:
        if path.exists():
            return
        time.sleep(0.03)
    raise AssertionError("child did not start within test bound")


class ManagedTests(unittest.TestCase):
    def test_eof_signal_and_competing_owner_close_child(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            binary = executable(base / "native", FAKE_NATIVE.replace("#!/usr/bin/env python3", "#!" + sys.executable))
            state = base / "state"
            command = [sys.executable, "-m", "memory_controller.mcp", "--binary", str(binary), "--dir", str(state)]
            environment = {**os.environ, "PYTHONPATH": str(ROOT / "examples")}
            for end_with_signal in (False, True):
                (state / "fake.pid").unlink(missing_ok=True)
                child = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                         stderr=subprocess.PIPE, env=environment)
                try:
                    child.stdin.write((json.dumps(request("initialize", {"protocolVersion": "2025-06-18"})) + "\n").encode())
                    child.stdin.flush()
                    wait_for(state / "fake.pid")
                    native_pid = int((state / "fake.pid").read_text())
                    # The bridge permits eight seconds for startup. A five-second
                    # test deadline incorrectly failed a permitted slower start.
                    readable, _, _ = select.select(
                        [child.stdout], [], [], STARTUP_TIMEOUT_SECONDS + 4)
                    self.assertTrue(readable, "MCP initialization deadline")
                    self.assertIn("serverInfo", json.loads(child.stdout.readline())["result"])
                    other = subprocess.run(command, input=b"", capture_output=True, env=environment, timeout=12)
                    self.assertNotEqual(other.returncode, 0)
                    self.assertEqual(other.stdout, b"")
                    self.assertIn(b"one owner", other.stderr)
                    if end_with_signal:
                        child.send_signal(signal.SIGTERM)
                    else:
                        child.stdin.close()
                        child.stdin = None
                    stdout, stderr = child.communicate(timeout=12)
                    self.assertEqual(child.returncode, 0, stderr)
                    for line in stdout.splitlines():
                        self.assertIn("jsonrpc", json.loads(line))
                    self.assertNotIn(b"native secret", stdout + stderr)
                    with self.assertRaises(ProcessLookupError):
                        os.kill(native_pid, 0)
                finally:
                    if child.poll() is None:
                        child.terminate()
                        try:
                            child.wait(timeout=8)
                        except subprocess.TimeoutExpired:
                            child.kill()
                            child.wait()
                    for stream in (child.stdin, child.stdout, child.stderr):
                        if stream is not None:
                            stream.close()


class InstallerTests(unittest.TestCase):
    def test_isolated_install_preserves_settings_state_and_private_backups(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            bin_dir = base / "executables"
            bin_dir.mkdir()
            executable(bin_dir / "opencode", "#!/bin/sh\nprintf '1.18.35\\n'\n")
            native = executable(bin_dir / "native", "#!/bin/sh\nexit 0\n")
            config = base / "opencode.json"
            state = base / "existing-state"
            state.mkdir()
            sentinel = state / "native-db-sentinel"
            sentinel.write_bytes(b"existing database must remain unchanged")
            original = {"model": "configured/default", "provider": {"custom": {"options": {"baseURL": "preserved"}}},
                        "mcp": {"other": {"type": "local", "command": ["other"]},
                                "instantKV": {"type": "local", "enabled": True, "command": ["native", "mcp-local", "--dir", str(state)]}},
                        "agent": {"memory": {"model": "openai/gpt-6-luna", "permission": {"bash": "deny", "read": {"*": "deny"}}, "tools": {"bash": False}},
                                  "build": {"prompt": "Keep my build policy.\n<instantkv-memory-policy>\nOld native policy\n</instantkv-memory-policy>\n", "permission": {"bash": "allow", "instantKV_remember": "allow"}}}}
            config.write_text(json.dumps(original))
            config.chmod(0o644)
            before = config.read_bytes()
            install, library = base / "installed", base / "library"
            command = [sys.executable, str(ROOT / "scripts/install-opencode-controller.py"),
                       "--config", str(config), "--binary", str(native), "--install-dir", str(install), "--lib-dir", str(library)]
            environment = {**os.environ, "PATH": str(bin_dir) + os.pathsep + os.defpath}
            dry = subprocess.run([*command, "--dry-run"], capture_output=True, env=environment)
            self.assertEqual(dry.returncode, 0, dry.stderr)
            self.assertEqual(config.read_bytes(), before)
            self.assertFalse(install.exists())
            self.assertFalse(library.exists())
            for _ in range(2):
                result = subprocess.run(command, capture_output=True, env=environment)
                self.assertEqual(result.returncode, 0, result.stderr)
            current = json.loads(config.read_text())
            self.assertEqual(current["model"], original["model"])
            self.assertEqual(current["provider"], original["provider"])
            self.assertEqual(current["mcp"]["other"], original["mcp"]["other"])
            self.assertFalse(current["mcp"]["instantKV"]["enabled"])
            self.assertEqual(current["agent"]["memory"]["model"], "openai/gpt-6-luna")
            self.assertEqual(current["agent"]["memory"]["steps"], 8)
            self.assertEqual(current["agent"]["memory"]["permission"]["read"], "deny")
            self.assertEqual(current["agent"]["memory"]["tools"]["bash"], False)
            self.assertEqual(current["agent"]["build"]["permission"]["bash"], "allow")
            self.assertEqual(current["agent"]["build"]["permission"]["instantKV_remember"], "deny")
            self.assertEqual(current["agent"]["build"]["prompt"].count("<instantkv-memory-policy>"), 1)
            self.assertIn("Keep my build policy.", current["agent"]["build"]["prompt"])
            self.assertEqual(sentinel.read_bytes(), b"existing database must remain unchanged")
            self.assertEqual(config.stat().st_mode & 0o777, 0o600)
            backups = sorted(base.glob("opencode.json.backup-*"))
            self.assertEqual(backups[0].read_bytes(), before)
            self.assertTrue(all(path.stat().st_mode & 0o777 == 0o600 for path in backups))
            adapter = current["mcp"]["instantKVMemory"]["command"]
            self.assertNotIn(str(ROOT), json.dumps(adapter))
            self.assertEqual(adapter[adapter.index("--dir") + 1], str(state.resolve()))
            help_result = subprocess.run([*adapter, "--help"], capture_output=True, cwd=base, timeout=10)
            self.assertEqual(help_result.returncode, 0, help_result.stderr)

    def test_v2_malformed_policy_and_external_credentials_are_safe(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            native = executable(base / "native", "#!/bin/sh\nexit 0\n")
            executable(base / "opencode", "#!/bin/sh\nprintf '1.18.35\\n'\n")
            config, install = base / "opencode.json", base / "installed"
            command = [sys.executable, str(ROOT / "scripts/install-opencode-controller.py"),
                       "--config", str(config), "--binary", str(native), "--install-dir", str(install), "--lib-dir", str(base / "lib")]
            environment = {**os.environ, "PATH": str(base) + os.pathsep + os.defpath}
            for value in ({"mcp": {"servers": {}}}, {"agent": {"build": {"prompt": "\n<instantkv-memory-policy>\nunfinished"}}}):
                config.write_text(json.dumps(value))
                before = config.read_bytes()
                result = subprocess.run(command, capture_output=True, env=environment)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(config.read_bytes(), before)
                self.assertFalse(install.exists())
            config.write_text('{}')
            # Nonexistent credentials prove install never accesses token files.
            result = subprocess.run([*command, "--url", "http://127.0.0.1:8877", "--secrets-file", str(base / "unreadable")], capture_output=True, env=environment)
            self.assertEqual(result.returncode, 0, result.stderr)
            adapter = json.loads(config.read_text())["mcp"]["instantKVMemory"]["command"]
            self.assertIn("--url", adapter)
            self.assertNotIn("--dir", adapter)


if __name__ == "__main__":
    unittest.main()
