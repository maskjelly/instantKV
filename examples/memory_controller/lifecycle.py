"""Deterministic lifecycle beside the node, using one conditional record write.

Native remember supplies atomic record/index changes, not these app semantics.
Receipts are per slot. No multi-fact atomicity, model calls, summary cache or
physical-backup erasure is promised. A namespace without native TTL is required.
"""

import copy
import hashlib
import json
import time
import unicodedata

from .store import ConflictError, json_bytes

MAX_IDENTITY_BYTES = 128
MAX_VALUE_BYTES = 1024
MAX_SOURCE_BYTES = 512
MAX_SOURCE_ID_BYTES = 256
MAX_METADATA_BYTES = 8192
MAX_CONTENT_BYTES = 16384
MAX_QUERY_BYTES = 16384
MAX_OUTPUT_BYTES = 65536
MAX_HISTORY = 8
MAX_CONFLICTS = 8
MAX_RECEIPTS = 24
KINDS = frozenset(("fact", "preference", "decision", "event"))
OPERATIONS = frozenset(("assert", "correct"))
_MARKER = "_memory_controller"
_OUTCOMES = frozenset(("created", "duplicate", "stale", "conflict", "corrected"))


class ControllerError(ValueError):
    """Safe messages with a stable machine-readable code."""

    def __init__(self, message, *, code="invalid_proposal"):
        super().__init__(message)
        self.code = code


class RevisionConflict(ControllerError):
    def __init__(self, message="memory revision changed; inspect before correcting or forgetting"):
        super().__init__(message, code="revision_conflict")


def _text(value, limit, label):
    if (not isinstance(value, str) or not value.strip()
            or any(unicodedata.category(c) == "Cs" for c in value)
            or len(value.encode("utf-8")) > limit):
        raise ControllerError(f"{label} must be nonempty UTF-8 text within {limit} bytes")
    return value


def _identity(value):
    value = _text(value, MAX_IDENTITY_BYTES, "identity")
    value = unicodedata.normalize("NFC", value.strip()).casefold()
    if (len(value.encode()) > MAX_IDENTITY_BYTES
            or any(unicodedata.category(c).startswith("C") for c in value)):
        raise ControllerError("identity contains control characters or exceeds 128 bytes")
    return value


def _integer(value, label, *, positive=False):
    if type(value) is not int or not (1 if positive else 0) <= value <= 2**64 - 1:
        raise ControllerError(f"{label} must be a {'positive' if positive else 'nonnegative'} 64-bit integer")
    return value


def _digest(value):
    encoded = json.dumps(value, ensure_ascii=False, allow_nan=False,
                         sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _source(source):
    if not isinstance(source, dict) or set(source) != {"id", "text", "role", "occurred_at_ms"}:
        raise ControllerError("source requires id, text, role and occurred_at_ms only")
    _text(source["id"], MAX_SOURCE_ID_BYTES, "source id")
    _text(source["text"], MAX_SOURCE_BYTES, "source quote")
    if source["role"] != "user":
        raise ControllerError("only user sources may propose facts")
    _integer(source["occurred_at_ms"], "occurred_at_ms")
    return copy.deepcopy(source)


def _observation(value):
    if (not isinstance(value, dict)
            or set(value) != {"value", "kind", "source", "valid_until_ms"}):
        raise ControllerError("invalid observation fields")
    _text(value["value"], MAX_VALUE_BYTES, "value")
    if not isinstance(value["kind"], str) or value["kind"] not in KINDS:
        raise ControllerError("kind must be fact, preference, decision or event")
    source = _source(value["source"])
    expires = value["valid_until_ms"]
    if expires is not None:
        _integer(expires, "valid_until_ms")
        if expires <= source["occurred_at_ms"]:
            raise ControllerError("valid_until_ms must follow the source event time")
    return copy.deepcopy(value)


def validate_proposal(proposal):
    """Validate before any store access. Also usable by an optional extractor."""
    required = {"entity", "attribute", "value", "kind", "operation", "source"}
    if (not isinstance(proposal, dict) or not required <= set(proposal)
            or set(proposal) - required - {"valid_until_ms", "expected_revision"}):
        raise ControllerError("proposal has missing or unknown fields")
    result = dict(proposal)
    result["entity"] = _identity(result["entity"])
    result["attribute"] = _identity(result["attribute"])
    operation = result["operation"]
    if not isinstance(operation, str) or operation not in OPERATIONS:
        raise ControllerError("operation must be assert or correct")
    if operation == "correct":
        _integer(result.get("expected_revision"), "expected_revision", positive=True)
    elif "expected_revision" in result:
        raise ControllerError("expected_revision is only valid for correct")
    result.setdefault("valid_until_ms", None)
    observation = _observation({name: result[name] for name in ("value", "kind", "source", "valid_until_ms")})
    result.update(observation)
    return result


class MemoryController:
    """No retained facts between calls. Each mutation is create-only or CAS.

    Clock returns Unix milliseconds. Defaults bound one read to eight pages,
    100 returned facts and native 20-result / 64-KiB pages. Pages are not a
    snapshot across concurrent native writes. Limits may only be lowered.
    """

    def __init__(self, store, namespace="knowledge", scope="personal", *,
                 clock=None, max_pages=8, max_items=100, conflict_retries=3):
        self.store = store
        self.namespace = _text(namespace, 256, "namespace")
        self.scope = _identity(scope)
        self.topic = "mc-" + _digest(self.scope)[:61]
        self._clock = clock if clock is not None else lambda: time.time_ns() // 1_000_000
        for value, bound, label in ((max_pages, 8, "max_pages"),
                                    (max_items, 100, "max_items"),
                                    (conflict_retries, 3, "conflict_retries")):
            if type(value) is not int or not 1 <= value <= bound:
                raise ControllerError(f"{label} must be 1..{bound}", code="invalid_budget")
        self.max_pages = max_pages
        self.max_items = max_items
        self.conflict_retries = conflict_retries

    def _key(self, entity, attribute):
        return "mc/" + _digest([self.scope, entity, attribute])

    def _empty(self, entity, attribute):
        return {"version": 1, "scope": self.scope, "entity": entity,
                "attribute": attribute, "state": "active", "current": None,
                "history": [], "conflicts": [], "receipts": [], "last_confirmed_at_ms": None}

    @staticmethod
    def _content(data):
        if data["state"] == "forgotten":
            return "Forgotten memory."
        if data["state"] == "conflicted":
            return "Unresolved memory."
        return f'{data["entity"]} / {data["attribute"]}: {data["current"]["value"]}'

    def _memory(self, data):
        metadata = {_MARKER: data}
        if len(json_bytes(metadata)) > MAX_METADATA_BYTES:
            raise ControllerError("memory metadata is full; no write applied", code="capacity")
        content = self._content(data)
        if len(content.encode()) > MAX_CONTENT_BYTES:
            raise ControllerError("memory content is full; no write applied", code="capacity")
        current = data.get("current")
        return {"content": content, "topic": self.topic, "tags": [],
                "metadata": metadata,
                "occurred_at_ms": 0 if current is None else data["last_confirmed_at_ms"]}

    def _decode(self, hit, entity=None, attribute=None):
        try:
            if not isinstance(hit, dict):
                raise ControllerError("invalid hit")
            _integer(hit["revision"], "revision", positive=True)
            if hit.get("expires_at_ms") is not None:
                raise ControllerError(
                    "managed records cannot use native TTL; use a durable namespace without default or required TTL",
                    code="native_ttl")
            memory = hit["memory"]
            if (not isinstance(memory, dict) or type(memory.get("_instantkv_memory")) is not int
                    or memory["_instantkv_memory"] != 1):
                raise ControllerError("invalid native memory version")
            metadata = memory["metadata"]
            if not isinstance(metadata, dict) or set(metadata) != {_MARKER}:
                raise ControllerError("missing controller metadata")
            data = metadata[_MARKER]
            if (not isinstance(data, dict) or type(data.get("version")) is not int
                    or data["version"] != 1):
                raise ControllerError("unsupported controller version")
            if data.get("state") == "forgotten":
                fields = {"version", "state", "scope_hash", "slot_hash", "forgotten_revision"}
                slot_hash = data.get("slot_hash")
                if (set(data) != fields or not isinstance(slot_hash, str) or len(slot_hash) != 64
                        or any(c not in "0123456789abcdef" for c in slot_hash)
                        or data["scope_hash"] != _digest(self.scope)
                        or hit["key"] != "mc/" + data["slot_hash"]
                        or (entity is not None and hit["key"] != self._key(entity, attribute))):
                    raise ControllerError("invalid tombstone identity")
                _integer(data["forgotten_revision"], "forgotten_revision", positive=True)
                if data["forgotten_revision"] >= hit["revision"]:
                    raise ControllerError("invalid forgotten revision")
                expected = self._memory(data)
                if any(memory.get(field) != expected[field] for field in expected):
                    raise ControllerError("invalid tombstone content")
                return copy.deepcopy(data)
            fields = {"version", "scope", "entity", "attribute", "state", "current",
                      "history", "conflicts", "receipts", "last_confirmed_at_ms"}
            if not isinstance(data, dict) or set(data) != fields or type(data["version"]) is not int or data["version"] != 1:
                raise ControllerError("unsupported or malformed controller version")
            for name in ("scope", "entity", "attribute"):
                if _identity(data[name]) != data[name]:
                    raise ControllerError("noncanonical stored identity")
            if (data["scope"] != self.scope
                    or (entity is not None and data["entity"] != entity)
                    or (attribute is not None and data["attribute"] != attribute)
                    or hit["key"] != self._key(data["entity"], data["attribute"])):
                raise ControllerError("stored identity does not match this slot")
            if data["state"] not in ("active", "conflicted"):
                raise ControllerError("invalid state")
            for field, maximum in (("history", MAX_HISTORY), ("conflicts", MAX_CONFLICTS),
                                    ("receipts", MAX_RECEIPTS)):
                if not isinstance(data[field], list) or len(data[field]) > maximum:
                    raise ControllerError("invalid bounded stored list")
            _observation(data["current"])
            _integer(data["last_confirmed_at_ms"], "last_confirmed_at_ms")
            if data["last_confirmed_at_ms"] < data["current"]["source"]["occurred_at_ms"]:
                raise ControllerError("confirmation predates provenance")
            if (data["state"] == "conflicted") != bool(data["conflicts"]):
                raise ControllerError("state and conflicts disagree")
            for item in data["history"]:
                if (not isinstance(item, dict) or set(item) != {"status", "observation"}
                        or item["status"] not in ("duplicate", "stale", "superseded", "conflict")):
                    raise ControllerError("invalid history")
                _observation(item["observation"])
            for item in data["conflicts"]:
                _observation(item)
            source_ids = set()
            for receipt in data["receipts"]:
                if (not isinstance(receipt, dict) or set(receipt) != {"source", "payload", "status"}
                        or receipt["status"] not in _OUTCOMES):
                    raise ControllerError("invalid receipt")
                for field in ("source", "payload"):
                    digest = receipt[field]
                    if (not isinstance(digest, str) or len(digest) != 64
                            or any(c not in "0123456789abcdef" for c in digest)):
                        raise ControllerError("invalid receipt digest")
                if receipt["source"] in source_ids:
                    raise ControllerError("duplicate stored source receipt")
                source_ids.add(receipt["source"])
            expected = self._memory(data)
            if any(memory.get(field) != expected[field] for field in expected):
                raise ControllerError("record content and controller metadata disagree")
            return copy.deepcopy(data)
        except ControllerError as error:
            if error.code == "native_ttl":
                raise
            raise ControllerError("malformed or unsupported managed record; inspect with the native API before upgrading",
                                  code="malformed_record") from None
        except (KeyError, TypeError, ValueError, UnicodeError):
            raise ControllerError("malformed or unsupported managed record; inspect with the native API before upgrading",
                                  code="malformed_record") from None

    @staticmethod
    def _append(items, item, maximum, label):
        if len(items) >= maximum:
            raise ControllerError(f"{label} is full; no write applied", code="capacity")
        items.append(copy.deepcopy(item))

    @staticmethod
    def _receipt(key, revision, status, *, replayed=False):
        return {"key": key, "revision": revision, "status": status, "replayed": replayed}

    def _save(self, key, data, revision):
        memory = self._memory(data)  # Reject accumulation before mutation.
        hit = self.store.remember(self.namespace, key, memory, if_revision=revision)
        try:
            stored = self._decode(hit, data.get("entity"), data.get("attribute"))
            if hit["key"] != key or stored != data:
                raise ControllerError("write response does not match the submitted record", code="malformed_record")
        except ControllerError as error:
            if error.code == "native_ttl":
                raise ControllerError(
                    "write committed with native TTL; stop using this namespace and configure no default or required TTL",
                    code="native_ttl") from None
            raise
        return hit

    def apply(self, proposal):
        proposal = validate_proposal(proposal)
        entity, attribute = proposal["entity"], proposal["attribute"]
        key = self._key(entity, attribute)
        source_hash, payload_hash = _digest(proposal["source"]["id"]), _digest(proposal)
        incoming = {name: proposal[name] for name in ("value", "kind", "source", "valid_until_ms")}
        for _ in range(self.conflict_retries):
            hit = self.store.get(self.namespace, key)
            data = self._empty(entity, attribute) if hit is None else self._decode(hit, entity, attribute)
            revision = None if hit is None else hit["revision"]
            if data["state"] == "forgotten":
                raise ControllerError("slot was forgotten; default ingestion cannot restore it", code="forgotten")
            # Receipts precede revision checks: an uncertain correction can be
            # retried with its original expected_revision after it committed.
            for receipt in data["receipts"]:
                if receipt["source"] == source_hash:
                    if receipt["payload"] != payload_hash:
                        raise ControllerError("source id was already used with a different proposal", code="source_reuse")
                    return self._receipt(key, revision, receipt["status"], replayed=True)
            current = data["current"]
            if proposal["operation"] == "correct":
                if revision != proposal["expected_revision"]:
                    raise RevisionConflict()
                latest = max([data["last_confirmed_at_ms"]]
                             + [item["source"]["occurred_at_ms"] for item in data["conflicts"]])
                if incoming["source"]["occurred_at_ms"] < latest:
                    raise ControllerError("an older event cannot correct current truth; supply a current user correction")
                self._append(data["history"], {"status": "superseded", "observation": current}, MAX_HISTORY, "history")
                for conflict in data["conflicts"]:
                    self._append(data["history"], {"status": "conflict", "observation": conflict}, MAX_HISTORY, "history")
                data["current"], data["conflicts"], data["state"] = incoming, [], "active"
                data["last_confirmed_at_ms"] = incoming["source"]["occurred_at_ms"]
                status = "corrected"
            elif current is None:
                data["current"] = incoming
                data["last_confirmed_at_ms"] = incoming["source"]["occurred_at_ms"]
                status = "created"
            elif incoming["source"]["occurred_at_ms"] < data["last_confirmed_at_ms"]:
                status = "stale"
                self._append(data["history"], {"status": status, "observation": incoming}, MAX_HISTORY, "history")
            elif all(incoming[name] == current[name] for name in ("value", "kind", "valid_until_ms")):
                status = "duplicate"
                data["last_confirmed_at_ms"] = incoming["source"]["occurred_at_ms"]
            else:
                status = "conflict"
                self._append(data["conflicts"], incoming, MAX_CONFLICTS, "conflicts")
                data["state"] = "conflicted"
            self._append(data["receipts"], {"source": source_hash, "payload": payload_hash, "status": status},
                         MAX_RECEIPTS, "retry receipts")
            if data["state"] == "conflicted":
                # Reserve enough space to resolve to the existing evidence.
                # Larger future corrections still obey the aggregate byte cap.
                resolution = copy.deepcopy(data)
                self._append(resolution["history"], {"status": "superseded", "observation": current}, MAX_HISTORY, "correction history")
                for conflict in resolution["conflicts"]:
                    self._append(resolution["history"], {"status": "conflict", "observation": conflict}, MAX_HISTORY, "correction history")
                self._append(resolution["receipts"], {"source": "0" * 64, "payload": "0" * 64, "status": "corrected"}, MAX_RECEIPTS, "correction receipts")
                resolution["state"], resolution["conflicts"] = "active", []
                self._memory(resolution)
            try:
                saved = self._save(key, data, revision)
                return self._receipt(key, saved["revision"], status)
            except ConflictError:
                # Reread on a bounded retry. Correct never inherits a new
                # expected revision; only exact receipt replay may succeed.
                continue
        raise RevisionConflict("memory changed repeatedly; retry the same proposal after inspection")

    def _item(self, hit, data, entity=None, attribute=None):
        current = data.get("current")
        return {"key": hit["key"], "revision": hit["revision"],
                "entity": data.get("entity", entity), "attribute": data.get("attribute", attribute),
                "value": None if current is None else current["value"],
                "kind": None if current is None else current["kind"],
                "source": None if current is None else copy.deepcopy(current["source"]),
                "valid_until_ms": None if current is None else current["valid_until_ms"]}

    def _expired(self, data):
        current = data.get("current")
        return bool(current is not None and current["valid_until_ms"] is not None
                    and current["valid_until_ms"] <= self._clock())

    def inspect(self, entity, attribute):
        entity, attribute = _identity(entity), _identity(attribute)
        hit = self.store.get(self.namespace, self._key(entity, attribute))
        if hit is None:
            return None
        data = self._decode(hit, entity, attribute)
        return {**self._item(hit, data, entity, attribute), "scope": self.scope, "state": data["state"],
                "expired": self._expired(data), "history": data.get("history", []), "conflicts": data.get("conflicts", [])}

    def forget(self, entity, attribute, *, expected_revision):
        entity, attribute = _identity(entity), _identity(attribute)
        _integer(expected_revision, "expected_revision", positive=True)
        key = self._key(entity, attribute)
        hit = self.store.get(self.namespace, key)
        if hit is None:
            raise RevisionConflict("slot is missing; inspect before forgetting")
        data = self._decode(hit, entity, attribute)
        # A tombstone has no user facts and cannot be revived by this adapter;
        # retry of an uncertain forget may safely recognize the newer tombstone.
        if data["state"] == "forgotten":
            if expected_revision not in (data["forgotten_revision"], hit["revision"]):
                raise RevisionConflict()
            return self._receipt(key, hit["revision"], "forgotten", replayed=True)
        if hit["revision"] != expected_revision:
            raise RevisionConflict()
        tombstone = {"version": 1, "state": "forgotten", "scope_hash": _digest(self.scope),
                     "slot_hash": key[3:], "forgotten_revision": expected_revision}
        try:
            saved = self._save(key, tombstone, expected_revision)
        except ConflictError:
            raise RevisionConflict() from None
        return self._receipt(key, saved["revision"], "forgotten")

    def _read(self, query, max_bytes):
        if type(max_bytes) is not int or not 128 <= max_bytes <= MAX_OUTPUT_BYTES:
            raise ControllerError("max_bytes must be 128..65536", code="invalid_budget")
        result = {"items": [], "truncated": False}
        cursor, seen_cursors, seen_keys = None, set(), set()
        for page_index in range(self.max_pages):
            method = self.store.browse if query is None else self.store.search
            args = (self.namespace,) if query is None else (self.namespace, query)
            page = method(*args, topic=self.topic, cursor=cursor, limit=20, max_bytes=65536)
            if (not isinstance(page, dict) or not isinstance(page.get("items"), list)
                    or len(page["items"]) > 20 or "next_cursor" not in page):
                raise ControllerError("invalid memory page", code="malformed_record")
            if page.get("truncated", False):
                result["truncated"] = True
            for hit in page["items"]:
                data = self._decode(hit)
                if hit["key"] in seen_keys:
                    continue
                seen_keys.add(hit["key"])
                if data["state"] != "active" or self._expired(data):
                    continue
                if len(result["items"]) >= self.max_items:
                    result["truncated"] = True
                    return result
                item = self._item(hit, data)
                result["items"].append(item)
                # Reserve the longer false spelling when deciding the budget.
                if len(json_bytes({"items": result["items"], "truncated": False})) > max_bytes:
                    result["items"].pop()
                    result["truncated"] = True
                    return result
            next_cursor = page.get("next_cursor")
            if next_cursor is None:
                return result
            if (not isinstance(next_cursor, str) or not next_cursor
                    or len(next_cursor.encode()) > 16384 or next_cursor in seen_cursors):
                raise ControllerError("invalid or repeated pagination cursor", code="malformed_record")
            seen_cursors.add(next_cursor)
            cursor = next_cursor
            if page_index + 1 == self.max_pages:
                result["truncated"] = True
        return result

    def profile(self, max_bytes=8192):
        return self._read(None, max_bytes)

    def context(self, query, max_bytes=8192):
        _text(query, MAX_QUERY_BYTES, "query")
        return self._read(query, max_bytes)
