#!/usr/bin/env python3
"""One isolated real-node controller scenario; no model calls or retained outputs."""

import argparse
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
from urllib.parse import quote
from urllib.request import ProxyHandler, Request, build_opener


ROOT = Path(__file__).resolve().parents[1]


def proposal(value, source_id, text, occurred_at_ms, **changes):
    result = {
        "entity": "user", "attribute": "response_style", "value": value,
        "kind": "preference", "operation": "assert",
        "source": {"id": source_id, "text": text, "role": "user",
                   "occurred_at_ms": occurred_at_ms},
        "valid_until_ms": None,
    }
    result.update(changes)
    return result


def require(condition, step):
    if not condition:
        raise RuntimeError(step)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, default=ROOT / "target/release/instantkv")
    args = parser.parse_args(argv)
    binary = args.binary.resolve()
    if not binary.is_file():
        print("FAIL: binary missing; build instantkv or supply --binary.", file=sys.stderr)
        return 1
    environment = {key: value for key, value in os.environ.items()
                   if not key.startswith("INSTANTKV_")}
    environment["PYTHONPATH"] = str(ROOT / "examples")
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    step = "setup"
    try:
        with tempfile.TemporaryDirectory(prefix="instantkv-memory-product-") as folder:
            state = Path(folder) / "memory state"
            credentials = state / ".instantkv/credentials.env"
            with socket.socket() as reservation:
                reservation.bind(("127.0.0.1", 0))
                port = reservation.getsockname()[1]
            address = f"http://127.0.0.1:{port}"
            opener = build_opener(ProxyHandler({}))
            server = None

            def stop():
                nonlocal server
                if server is not None:
                    server.terminate()
                    try:
                        require(server.wait(timeout=10) == 0, "clean server stop")
                    finally:
                        if server.poll() is None:
                            server.kill()
                            server.wait(timeout=10)
                        server = None

            def start():
                nonlocal server
                server = subprocess.Popen(
                    [str(binary), "start", "--dir", str(state), "--bind", f"127.0.0.1:{port}"],
                    cwd=folder, env=environment, stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                for _ in range(100):
                    require(server.poll() is None, "server startup")
                    try:
                        with opener.open(address + "/healthz", timeout=1) as response:
                            if response.status == 200:
                                return
                    except OSError:
                        time.sleep(0.05)
                raise RuntimeError("server readiness timeout")

            def cli(*arguments, payload=None, success=True, secrets=None):
                result = subprocess.run(
                    [sys.executable, "-m", "memory_controller", "--url", address,
                     "--secrets-file", str(secrets or credentials), "--namespace", "knowledge",
                     "--scope", "smoke", *arguments],
                    input=json.dumps(payload) if payload is not None else "",
                    cwd=folder, env=environment, text=True, capture_output=True, timeout=20,
                )
                require((result.returncode == 0) == success, "CLI exit status")
                # Private input and credentials must never enter failure diagnostics.
                if result.returncode:
                    require(all(value not in result.stderr for value in private_values),
                            "private text in diagnostics")
                return json.loads(result.stdout) if result.stdout.strip() else None

            private_values = ["short bullets", "long paragraphs", "brief numbered points",
                              "Please use short bullets.", "I prefer long paragraphs.",
                              "Correction: use brief numbered points."]
            initial = proposal(private_values[0], "smoke/1", private_values[3], 1791504000000)
            conflicting = proposal(private_values[1], "smoke/2", private_values[4], 1791504001000)
            try:
                start()
                secrets = dict(line.split("=", 1) for line in credentials.read_text().splitlines()
                               if "=" in line and not line.startswith("#"))
                private_values.extend(secrets.values())
                reader_file = Path(folder) / "reader.env"
                descriptor = os.open(reader_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(descriptor, "w") as stream:
                    stream.write("INSTANTKV_APP_TOKEN=" + secrets["INSTANTKV_READER_TOKEN"] + "\n")

                step = "create and replay"
                created = cli("apply", payload=initial)
                require(created["status"] == "created" and not created["replayed"], step)
                replayed = cli("apply", payload=initial)
                require(replayed["replayed"] and replayed["revision"] == created["revision"], step)
                preview_replay = cli("apply", payload={"proposals": [initial], "applied": False})
                require(preview_replay["results"][0]["receipt"]["replayed"], "saved preview replay")

                step = "read-only credentials"
                detail = cli("inspect", "user", "response_style", secrets=reader_file)
                require(detail["value"] == initial["value"], step)
                require(len(cli("profile", secrets=reader_file)["items"]) == 1, step)
                require(len(cli("context", "bullets", secrets=reader_file)["items"]) == 1, step)
                cli("apply", payload=conflicting, success=False, secrets=reader_file)
                cli("forget", "user", "response_style", "--expected-revision",
                    str(detail["revision"]), success=False, secrets=reader_file)
                require(cli("inspect", "user", "response_style")["revision"] == created["revision"], step)

                step = "conflict and correction"
                conflict = cli("apply", payload=conflicting, success=False)
                require(conflict["status"] == "conflict", step)
                require(cli("profile")["items"] == [], "conflict excluded from profile")
                detail = cli("inspect", "user", "response_style")
                require(detail["conflicts"], "conflict provenance")
                correction = proposal(private_values[2], "smoke/3", private_values[5], 1791504002000,
                                      operation="correct", expected_revision=created["revision"])
                cli("apply", payload=correction, success=False)
                correction["expected_revision"] = detail["revision"]
                corrected = cli("apply", payload=correction)
                require(corrected["status"] == "corrected", step)
                detail = cli("inspect", "user", "response_style")
                require(detail["value"] == correction["value"] and detail["history"], step)
                profile = cli("profile")
                context = cli("context", "numbered points")
                require(profile["items"][0]["value"] == correction["value"] and not profile["truncated"], step)
                require(context["items"][0]["revision"] == corrected["revision"], step)

                step = "restart"
                original_credentials = credentials.read_bytes()
                stop()
                start()
                require(credentials.read_bytes() == original_credentials, "credentials retained")
                detail = cli("inspect", "user", "response_style")
                require(detail["value"] == correction["value"] and detail["revision"] == corrected["revision"], step)

                step = "forget and replay rejection"
                cli("forget", "user", "response_style", "--expected-revision",
                    str(created["revision"]), success=False)
                forgotten = cli("forget", "user", "response_style", "--expected-revision", str(detail["revision"]))
                require(forgotten["status"] == "forgotten", step)
                cli("apply", payload=initial, success=False)
                require(cli("profile")["items"] == [], step)
                require(cli("context", "numbered points")["items"] == [], step)
                tombstone = cli("inspect", "user", "response_style", secrets=reader_file)
                require(tombstone["state"] == "forgotten", step)
                route = address + "/v1/namespaces/knowledge/records/" + quote(forgotten["key"], safe="")
                request = Request(route, headers={"Authorization": "Bearer " + secrets["INSTANTKV_READER_TOKEN"]})
                with opener.open(request, timeout=5) as response:
                    raw = response.read(65537)
                require(len(raw) <= 65536, "bounded tombstone")
                require(all(value.encode() not in raw for value in private_values), "raw tombstone erase")
                require(all(field not in json.dumps(tombstone) for field in private_values), "inspection erase")
            finally:
                stop()
    except (OSError, RuntimeError, ValueError, KeyError, IndexError, subprocess.SubprocessError):
        print(f"FAIL: {step}. Check the integrated controller and binary; private diagnostics suppressed.", file=sys.stderr)
        return 1
    print("PASS: create, replay, read-only access, conflict, correction, profile/context, restart, forget and tombstone erase.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
