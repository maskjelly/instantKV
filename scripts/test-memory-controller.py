#!/usr/bin/env python3
"""Focused lifecycle and transport risks; real-node smoke is a separate check."""

import copy
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
import urllib.error
import urllib.parse

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "examples"))
from memory_controller import (  # noqa: E402
    ConflictError, ControllerError, HTTPStore, MemoryController, RevisionConflict, StoreError,
)
from memory_controller.lifecycle import MAX_RECEIPTS  # noqa: E402
from memory_controller.store import json_bytes  # noqa: E402


def proposal(value="brief", source="turn-1", occurred=10, **extra):
    return {"entity": "user", "attribute": "response_style", "value": value,
            "kind": "preference", "operation": "assert",
            "source": {"id": source, "text": "Please be brief.", "role": "user",
                       "occurred_at_ms": occurred}, **extra}


class Node:
    """Fake native CAS and scoped query contract, not a lifecycle implementation."""

    def __init__(self):
        self.records, self.revision, self.writes = {}, 0, 0
        self.before_write = None
        self.page_hook = None
        self.calls = []
        self.expiry = None

    def get(self, namespace, key):
        return copy.deepcopy(self.records.get((namespace, key)))

    def remember(self, namespace, key, memory, *, if_revision=None):
        if self.before_write is not None:
            callback, self.before_write = self.before_write, None
            callback()
        previous = self.records.get((namespace, key))
        if (previous is not None and if_revision != previous["revision"]) or (previous is None and if_revision is not None):
            raise ConflictError("conflict", status=409)
        self.revision += 1
        self.writes += 1
        hit = {"key": key, "revision": self.revision, "written_at_ms": 100,
               "expires_at_ms": self.expiry,
               "memory": {"_instantkv_memory": 1, **copy.deepcopy(memory)}}
        self.records[(namespace, key)] = hit
        return copy.deepcopy(hit)

    def browse(self, namespace, *, topic, cursor=None, limit=20, max_bytes=65536):
        self.calls.append((namespace, topic, cursor))
        if self.page_hook:
            return self.page_hook(cursor)
        items = [copy.deepcopy(hit) for (ns, _), hit in self.records.items()
                 if ns == namespace and hit["memory"]["topic"] == topic]
        start = int(cursor or 0)
        return {"items": items[start:start + limit],
                "next_cursor": str(start + limit) if start + limit < len(items) else None}

    def search(self, namespace, query, **kwargs):
        return self.browse(namespace, **kwargs)


class LifecycleTests(unittest.TestCase):
    def test_lifecycle_freshness_restart_and_content_free_forget(self):
        node = Node()
        controller = MemoryController(node, clock=lambda: 100)
        original = proposal()
        created = controller.apply(original)
        reordered = dict(reversed(list(original.items())))
        self.assertTrue(controller.apply(reordered)["replayed"])
        self.assertEqual(node.writes, 1)
        with self.assertRaises(ControllerError) as reused:
            controller.apply(proposal("long", source="turn-1"))
        self.assertEqual(reused.exception.code, "source_reuse")
        # More than eight ordinary confirmations must not fill history.
        for index in range(10):
            controller.apply(proposal(source=f"confirm-{index}", occurred=20 + index))
        detail = controller.inspect(" USER ", "response_style")
        self.assertEqual(detail["history"], [])
        self.assertEqual(detail["source"]["id"], "turn-1")
        stale = controller.apply(proposal("long", source="old", occurred=15))
        self.assertEqual(stale["status"], "stale")
        self.assertEqual(len(controller.profile()["items"]), 1)
        conflict = controller.apply(proposal("long", source="new", occurred=30))
        self.assertEqual(conflict["status"], "conflict")
        self.assertEqual(controller.profile()["items"], [])
        self.assertEqual(controller.context("brief")["items"], [])
        correction = proposal("short bullets", source="correction", occurred=40,
                              operation="correct", expected_revision=conflict["revision"],
                              valid_until_ms=200)
        corrected = controller.apply(correction)
        self.assertTrue(controller.apply(correction)["replayed"])
        reopened = MemoryController(node, clock=lambda: 201)
        self.assertEqual(reopened.profile()["items"], [])
        self.assertTrue(reopened.inspect("user", "response_style")["expired"])
        with self.assertRaises(RevisionConflict):
            reopened.forget("user", "response_style", expected_revision=created["revision"])
        erased = reopened.forget("user", "response_style", expected_revision=corrected["revision"])
        self.assertTrue(reopened.forget("user", "response_style", expected_revision=corrected["revision"])["replayed"])
        raw = json_bytes(node.get("knowledge", erased["key"]))
        for secret in (b"short bullets", b"Please be brief", b"response_style", b"turn-1", b'"history"', b'"conflicts"'):
            self.assertNotIn(secret, raw)
        tombstone = reopened.inspect("user", "response_style")
        self.assertIsNone(tombstone["value"])
        self.assertEqual(tombstone["history"], [])
        with self.assertRaises(ControllerError) as forgotten:
            reopened.apply(original)
        self.assertEqual(forgotten.exception.code, "forgotten")

    def test_conflict_admission_and_finite_receipts_preserve_replay(self):
        node = Node()
        controller = MemoryController(node)
        first = proposal()
        controller.apply(first)
        for index in range(7):
            controller.apply(proposal(str(index), source=f"conflict-{index}", occurred=20 + index))
        before = copy.deepcopy(node.records)
        with self.assertRaises(ControllerError) as full:
            controller.apply(proposal("overflow", source="eighth", occurred=30))
        self.assertEqual(full.exception.code, "capacity")
        self.assertEqual(node.records, before)
        detail = controller.inspect("user", "response_style")
        fixed = controller.apply(proposal("resolved", source="resolution", occurred=40,
                                         operation="correct", expected_revision=detail["revision"]))
        self.assertEqual(fixed["status"], "corrected")
        self.assertEqual(len(controller.inspect("user", "response_style")["history"]), 8)
        node = Node()
        controller = MemoryController(node)
        controller.apply(first)
        for index in range(MAX_RECEIPTS - 1):
            controller.apply(proposal(source=f"same-{index}", occurred=20 + index))
        before = copy.deepcopy(node.records)
        with self.assertRaises(ControllerError):
            controller.apply(proposal(source="full", occurred=99))
        self.assertEqual(node.records, before)
        self.assertTrue(controller.apply(first)["replayed"])

    def test_concurrent_cas_and_uncertain_write(self):
        node = Node()
        first, second = MemoryController(node), MemoryController(node)
        node.before_write = lambda: second.apply(proposal("other", source="other"))
        result = first.apply(proposal())
        self.assertEqual(result["status"], "conflict")
        self.assertEqual(len(first.inspect("user", "response_style")["conflicts"]), 1)
        detail = first.inspect("user", "response_style")
        node.before_write = lambda: second.apply(proposal("third", source="third", occurred=20))
        with self.assertRaises(RevisionConflict):
            first.apply(proposal("correct", source="fix", occurred=30, operation="correct",
                                 expected_revision=detail["revision"]))
        uncertain = Node()
        remember = uncertain.remember
        def commit_then_disconnect(*args, **kwargs):
            remember(*args, **kwargs)
            raise StoreError("connection lost")
        uncertain.remember = commit_then_disconnect
        controller = MemoryController(uncertain)
        with self.assertRaises(StoreError):
            controller.apply(proposal())
        uncertain.remember = remember
        self.assertTrue(controller.apply(proposal())["replayed"])
        self.assertEqual(uncertain.writes, 1)

    def test_pagination_output_validation_and_native_ttl(self):
        node = Node()
        controller = MemoryController(node, max_pages=2, clock=lambda: 100)
        other = MemoryController(node, scope="unrelated")
        other.apply(proposal("private"))
        saved = controller.apply(proposal())
        hit = node.get("knowledge", saved["key"])
        node.page_hook = lambda cursor: {"items": [] if cursor is None else [hit],
                                         "next_cursor": "second" if cursor is None else None}
        self.assertEqual(len(controller.profile()["items"]), 1)
        self.assertTrue(all(topic == controller.topic for _, topic, _ in node.calls))
        bounded = controller.profile(max_bytes=128)
        self.assertTrue(bounded["truncated"])
        self.assertLessEqual(len(json_bytes(bounded)), 128)
        node.page_hook = lambda cursor: {"items": [], "next_cursor": str(int(cursor or 0) + 1)}
        self.assertTrue(controller.profile()["truncated"])
        self.assertEqual(len(node.calls[-2:]), 2)
        node.page_hook = None
        before = node.writes
        with self.assertRaises(ControllerError):
            controller.apply(proposal("x" * 1025))
        self.assertEqual(node.writes, before)
        node.records[("knowledge", saved["key"])]["memory"]["metadata"]["_memory_controller"]["version"] = 2
        with self.assertRaises(ControllerError) as malformed:
            controller.inspect("user", "response_style")
        self.assertEqual(malformed.exception.code, "malformed_record")
        ttl = Node()
        ttl.expiry = 200
        with self.assertRaises(ControllerError) as expires:
            MemoryController(ttl).apply(proposal())
        self.assertEqual(expires.exception.code, "native_ttl")
        self.assertIn("committed", str(expires.exception))
        self.assertEqual(ttl.writes, 1)


class TransportTests(unittest.TestCase):
    def test_native_http_grants_limits_and_safe_failures(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "credentials.env"
            token = "private-app-token-" + "x" * 32
            path.write_text("INSTANTKV_APP_TOKEN=" + token + "\n")
            path.chmod(0o600)
            store = HTTPStore("http://localhost:7777", path)
            self.assertEqual(store.url, "http://127.0.0.1:7777")
            class Transport:
                raw = b'{}'
                status = None
                def open(self, request, timeout):
                    self.request = request
                    if self.status:
                        raise urllib.error.HTTPError(request.full_url, self.status,
                                                     token, {}, io.BytesIO(token.encode()))
                    return io.BytesIO(self.raw)
            transport = Transport()
            store._opener = transport
            memory = {"content": "brief", "metadata": {}}
            store.remember("knowledge", "mc/key", memory)
            body = json.loads(transport.request.data)
            self.assertNotIn("if_revision", body)
            store.remember("knowledge", "mc/key", memory, if_revision=17)
            self.assertEqual(json.loads(transport.request.data)["if_revision"], 17)
            self.assertEqual(transport.request.get_header("Authorization"), "Bearer " + token)
            store.get("knowledge", "mc/key")
            self.assertTrue(transport.request.full_url.endswith("/memories/mc%2Fkey"))
            store.browse("knowledge", topic="scope-topic", cursor="opaque/+", max_bytes=65536)
            params = urllib.parse.parse_qs(urllib.parse.urlsplit(transport.request.full_url).query)
            self.assertEqual(params["topic"], ["scope-topic"])
            self.assertEqual(params["cursor"], ["opaque/+"])
            for status in (403, 302, 507, 409):
                transport.status = status
                with self.assertRaises(StoreError) as error:
                    store.remember("knowledge", "key", memory)
                self.assertEqual(error.exception.status, status)
                self.assertNotIn(token, str(error.exception))
            transport.status = 404
            self.assertIsNone(store.get("knowledge", "missing"))
            transport.status = None
            for raw in (b"x" * 65537, b'{"a":1,"a":2}', b'{"a":NaN}'):
                transport.raw = raw
                with self.assertRaises(StoreError):
                    store.get("knowledge", "key")
            for url in ("http://example.com", "https://127.0.0.1", "http://127.0.0.1/path"):
                with self.assertRaises(ValueError):
                    HTTPStore(url, path)
            path.chmod(0o644)
            with self.assertRaises(ValueError):
                HTTPStore("http://127.0.0.1", path)


if __name__ == "__main__":
    unittest.main()
