"""Bounded loopback transport for the existing structured-memory HTTP API.

The server owns namespace grants and conditional-write transactions. This adapter
does not infer grants from a token and never falls back to another credential.
"""

import ipaddress
import json
import os
import stat
import urllib.error
import urllib.parse
import urllib.request


class StoreError(RuntimeError):
    """A safe transport error; messages contain no server body or credentials."""

    def __init__(self, message, *, status=None):
        super().__init__(message)
        self.status = status


class ConflictError(StoreError):
    """The native create/revision condition failed."""


def json_bytes(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False,
                      separators=(",", ":")).encode("utf-8")


def _object(pairs):
    result = {}
    for name, value in pairs:
        if name in result:
            raise ValueError("duplicate JSON field")
        result[name] = value
    return result


def _constant(value):
    raise ValueError("nonfinite JSON number")


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class HTTPStore:
    """HTTPStore(url, secrets_file); credentials are NAME=value, never shell code.

    Optional timeout and response_limit only lower bounded resource use. Managed
    records require a durable namespace without native default or required TTL.
    """

    def __init__(self, url, secrets_file, *, timeout=5.0, response_limit=65536):
        try:
            parsed = urllib.parse.urlsplit(url)
            host = parsed.hostname
            loopback = host == "localhost" or ipaddress.ip_address(host).is_loopback
            port = parsed.port
        except (ValueError, TypeError):
            raise ValueError("use a loopback HTTP origin") from None
        if (parsed.scheme != "http" or not loopback or parsed.username is not None
                or parsed.password is not None or parsed.path not in ("", "/")
                or parsed.query or parsed.fragment or port == 0):
            raise ValueError("use a loopback HTTP origin without a path or credentials")
        if (isinstance(timeout, bool) or not isinstance(timeout, (int, float))
                or not 0 < timeout <= 30):
            raise ValueError("timeout must be within 0..30 seconds")
        if type(response_limit) is not int or not 1024 <= response_limit <= 65536:
            raise ValueError("response_limit must be 1024..65536 bytes")
        # Pin the accepted hostname so DNS cannot redirect a later request.
        if host == "localhost":
            self.url = "http://127.0.0.1" + (f":{port}" if port is not None else "")
        else:
            self.url = url.rstrip("/")
        self.timeout = timeout
        self.response_limit = response_limit
        self._token = self._credentials(secrets_file)
        self._opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({}), _NoRedirect())

    @staticmethod
    def _credentials(path):
        try:
            with open(path, "rb") as handle:
                info = os.fstat(handle.fileno())
                if (not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077
                        or info.st_uid != os.getuid()):
                    raise ValueError("credentials must be a private file owned by you; chmod 600")
                raw = handle.read(65537)
            if len(raw) > 65536:
                raise ValueError("credentials file exceeds 65536 bytes")
            entries = {}
            for line in raw.decode("utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                name, sep, value = line.partition("=")
                name, value = name.strip(), value.strip()
                if not sep or name in entries:
                    raise ValueError("credentials require unique NAME=value lines")
                entries[name] = value
            token = entries.get("INSTANTKV_APP_TOKEN", "")
            if not 32 <= len(token) <= 4096 or any(ord(c) < 33 or ord(c) > 126 for c in token):
                raise ValueError("credentials need a valid INSTANTKV_APP_TOKEN")
            return token
        except (OSError, UnicodeError):
            raise ValueError("cannot read private credentials file") from None

    @staticmethod
    def _path(namespace, key=None):
        if not isinstance(namespace, str) or not namespace or len(namespace.encode()) > 256:
            raise ValueError("invalid namespace")
        path = "/v1/namespaces/" + urllib.parse.quote(namespace, safe="")
        if key is not None:
            if not isinstance(key, str) or not key or len(key.encode()) > 256:
                raise ValueError("invalid memory key")
            path += "/memories/" + urllib.parse.quote(key, safe="")
        return path

    def _request(self, method, path, body=None):
        data = None if body is None else json_bytes(body)
        if data is not None and len(data) > 65536:
            raise ValueError("HTTP request exceeds 65536 bytes")
        request = urllib.request.Request(
            self.url + path, data=data, method=method,
            headers={"Authorization": "Bearer " + self._token,
                     "Content-Type": "application/json", "Accept": "application/json"})
        try:
            with self._opener.open(request, timeout=self.timeout) as response:
                raw = response.read(self.response_limit + 1)
                if len(raw) > self.response_limit:
                    raise StoreError("memory response exceeds the configured byte limit")
            result = json.loads(raw, object_pairs_hook=_object, parse_constant=_constant)
            if not isinstance(result, dict):
                raise StoreError("invalid memory response; expected a JSON object")
            return result
        except urllib.error.HTTPError as error:
            status = error.code
            error.close()
            if status == 409:
                raise ConflictError("memory revision changed; inspect and retry", status=status) from None
            if status in (401, 403):
                message = "memory access denied; check credentials and namespace grants"
            elif status == 507:
                message = "memory quota exhausted; ask the operator to review the quota"
            elif status == 404:
                message = "memory or namespace not found"
            elif 300 <= status < 400:
                message = "memory redirects are disabled; use the loopback node origin"
            else:
                message = "memory request failed; inspect node availability and request limits"
            raise StoreError(message, status=status) from None
        except (OSError, urllib.error.URLError):
            raise StoreError("memory connection failed; a write may have committed, retry the same proposal") from None
        except (ValueError, UnicodeError, RecursionError):
            raise StoreError("invalid JSON memory response; inspect the node") from None

    def get(self, namespace, key):
        # Native 404 also covers missing namespaces. A subsequent create remains
        # conditional and fails rather than pretending the namespace was created.
        try:
            return self._request("GET", self._path(namespace, key))
        except StoreError as error:
            if error.status == 404:
                return None
            raise

    def remember(self, namespace, key, memory, *, if_revision=None):
        self._path(namespace, key)
        if (not isinstance(memory, dict) or not isinstance(memory.get("content"), str)
                or not memory["content"].strip() or len(memory["content"].encode()) > 16384
                or not isinstance(memory.get("metadata", {}), dict)
                or len(json_bytes(memory.get("metadata", {}))) > 8192):
            raise ValueError("memory requires content within 16384 bytes and object metadata within 8192 bytes")
        body = {"key": key, "memory": memory}
        if if_revision is not None:
            if type(if_revision) is not int or if_revision <= 0:
                raise ValueError("if_revision must be a positive integer")
            body["if_revision"] = if_revision
        return self._request("POST", self._path(namespace) + "/memories", body)

    def browse(self, namespace, *, topic, cursor=None, limit=20, max_bytes=65536):
        self._query_bounds(topic, cursor, limit, max_bytes)
        params = {"topic": topic, "limit": limit, "max_bytes": max_bytes}
        if cursor is not None:
            params["cursor"] = cursor
        return self._request("GET", self._path(namespace) + "/memories?"
                             + urllib.parse.urlencode(params))

    def search(self, namespace, query, *, topic, cursor=None, limit=20, max_bytes=65536):
        self._query_bounds(topic, cursor, limit, max_bytes)
        if not isinstance(query, str) or not query.strip() or len(query.encode()) > 16384:
            raise ValueError("search query must use 1..16384 bytes")
        body = {"query": query, "topic": topic, "limit": limit, "max_bytes": max_bytes}
        if cursor is not None:
            body["cursor"] = cursor
        return self._request("POST", self._path(namespace) + "/search", body)

    @staticmethod
    def _query_bounds(topic, cursor, limit, max_bytes):
        if (not isinstance(topic, str) or not topic.strip() or len(topic.encode()) > 64
                or any(ord(c) < 32 or ord(c) == 127 for c in topic)):
            raise ValueError("topic must use 1..64 bytes without controls")
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("query limit must be 1..100")
        if type(max_bytes) is not int or not 1024 <= max_bytes <= 65536:
            raise ValueError("query max_bytes must be 1024..65536")
        if cursor is not None and (not isinstance(cursor, str) or len(cursor.encode()) > 16384):
            raise ValueError("query cursor exceeds 16384 bytes")
