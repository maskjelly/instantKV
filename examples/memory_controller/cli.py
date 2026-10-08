"""Source-only memory controller commands. No model imports outside capture."""

import argparse
import json
from pathlib import Path
import sys
import time


MAX_INPUT_BYTES = 65536
MAX_CAPTURE_BYTES = 16384
MAX_PROPOSALS = 8


class InputError(ValueError):
    """Invalid or oversized command input."""


def positive_integer(value):
    try:
        number = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError("use a positive integer") from None
    if number <= 0:
        raise argparse.ArgumentTypeError("use a positive integer")
    return number


def timestamp(value):
    try:
        number = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError("use nonnegative epoch milliseconds") from None
    if number < 0:
        raise argparse.ArgumentTypeError("use nonnegative epoch milliseconds")
    return number


def read_input(filename, limit=MAX_INPUT_BYTES):
    """Read at most one bounded UTF-8 input; never include it in an error."""
    try:
        if filename is None or str(filename) == "-":
            data = sys.stdin.buffer.read(limit + 1)
        else:
            with Path(filename).open("rb") as stream:
                data = stream.read(limit + 1)
    except OSError:
        raise InputError("input_unreadable") from None
    if len(data) > limit:
        raise InputError("capture_too_large" if limit == MAX_CAPTURE_BYTES else "input_too_large")
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        raise InputError("input_encoding") from None


def read_proposal(filename):
    def pairs(entries):
        result = {}
        for key, value in entries:
            if key in result:
                raise InputError("invalid_json")
            result[key] = value
        return result

    def reject_constant(_):
        raise InputError("invalid_json")

    try:
        proposal = json.loads(read_input(filename), object_pairs_hook=pairs,
                              parse_constant=reject_constant)
    except (json.JSONDecodeError, RecursionError):
        raise InputError("invalid_json") from None
    if not isinstance(proposal, dict):
        raise InputError("invalid_json")
    return proposal


def recovery(error):
    """Map trusted categories to fixed messages; never echo exception text."""
    code = getattr(error, "code", None)
    if isinstance(error, InputError):
        code = str(error)
    messages = {
        "input_unreadable": "Cannot read input. Check the file or pipe UTF-8 input on stdin.",
        "input_too_large": "Input exceeds 65536 bytes. Supply one smaller proposal or user turn.",
        "capture_too_large": "User turn exceeds 16384 bytes. Supply a shorter turn for capture.",
        "input_encoding": "Input is not UTF-8. Save the file as UTF-8 and retry.",
        "invalid_json": "Invalid proposal JSON. Supply one object with unique fields and finite values.",
        "invalid_preview": "Invalid preview. Use exactly proposals (at most 8 objects) and applied:false from capture; review before applying.",
    }
    if code in messages:
        return code, messages[code]
    if code == "invalid_proposal":
        return code, "Invalid proposal. Check required fields and byte limits in the guide; source.text must be a grounded user quote."
    if code == "source_reuse":
        return code, "Source ID already has another payload in this slot. Retry the original JSON, or use a new ID for a new observation."
    if code == "capacity":
        return code, "Slot history, conflicts, receipts or metadata are full. Inspect it; no provenance was dropped. Review limits in the guide."
    if code == "invalid_budget":
        return code, "Invalid read budget. Use --max-bytes between 128 and 65536 and a query of at most 16384 UTF-8 bytes."
    if code == "malformed_record":
        return code, "Managed record is incompatible or malformed. Check its format and source version; do not overwrite it unconditionally."
    if code == "native_ttl":
        return code, "Namespace TTL rejected. Disable default/required TTL in a durable namespace. A submitted write may already be saved."
    status = getattr(error, "status", None)
    if status in {401, 403}:
        return "permission_denied", "Check the private credentials file and namespace grants; writes need put, reads need get and list."
    if status == 409:
        return "revision_conflict", "Concurrent change. Inspect the slot, review it, then retry with the observed revision."
    if status == 507:
        return "quota", "Memory quota is full. Review node capacity and unused records before retrying."
    if status in {400, 413}:
        return "node_limit", "Node rejected the request. Check namespace admission and request/query limits before retrying."
    if type(error).__name__ == "ModelError":
        return "model_unavailable", "Start local Ollama with an already installed model, or use apply with reviewed JSON."
    if type(error).__name__ == "ExtractionError":
        return "extraction_invalid", "Capture input or output was rejected. Check the turn, source ID and model; use apply with grounded JSON."
    if isinstance(error, ValueError) and code is None:
        # Exact fixed transport messages, never interpolated into diagnostics.
        if str(error) in {"use a loopback HTTP origin", "use a loopback HTTP origin without a path or credentials"}:
            return "loopback_required", "Use a loopback HTTP origin, such as http://127.0.0.1:8080, without a path."
        if str(error) in {"credentials must be a private file owned by you; chmod 600",
                          "credentials file exceeds 65536 bytes",
                          "credentials require unique NAME=value lines",
                          "credentials need a valid INSTANTKV_APP_TOKEN",
                          "cannot read private credentials file"}:
            return "credentials", "Check the private credentials file, its ownership and chmod 600; it must contain INSTANTKV_APP_TOKEN."
    if code == "revision_conflict":
        return "revision_conflict", "Revision changed. Inspect the slot, review it, then use its current revision."
    if code == "forgotten":
        return "forgotten", "This slot was forgotten. Replay cannot restore it; explicit restoration is outside this milestone."
    if isinstance(error, ValueError):
        return "validation", "Check input limits and use a loopback HTTP origin without a path. Inspect before correction or forgetting."
    if isinstance(error, (RuntimeError, OSError)):
        return "unavailable", "Check the loopback HTTP origin, running node and private credentials. A write may be saved; inspect or retry identical input after recovery."
    return "failed", "Command failed. Check the source setup and node; no private error details were printed."


def emit(value):
    print(json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2))


def validate_batch(proposals):
    if not isinstance(proposals, list) or len(proposals) > MAX_PROPOSALS:
        raise InputError("invalid_preview")
    from .lifecycle import validate_proposal

    return [validate_proposal(proposal) for proposal in proposals]


def apply_batch(controller, proposals):
    outcomes, failed = [], False
    for index, item in enumerate(proposals):
        try:
            receipt = controller.apply(item)
            failed |= receipt["status"] == "conflict"
            outcomes.append({"index": index, "receipt": receipt})
        except Exception as error:
            code, message = recovery(error)
            outcomes.append({"index": index, "error": code, "next_action": message})
            failed = True
    emit({"results": outcomes, "applied": True})
    if failed:
        print("Some proposals were rejected or conflicted. Inspect affected slots; retry the saved preview JSON after recovery.", file=sys.stderr)
    return 1 if failed else 0


def parser():
    root = argparse.ArgumentParser(description=__doc__)
    root.add_argument("--url", default="http://127.0.0.1:8080")
    root.add_argument("--secrets-file", type=Path, default=Path(".instantkv/credentials.env"))
    root.add_argument("--namespace", default="knowledge")
    root.add_argument("--scope", default="personal")
    commands = root.add_subparsers(dest="command", required=True)
    apply = commands.add_parser("apply", help="apply a reviewed proposal or capture preview")
    apply.add_argument("--file", type=Path, help="UTF-8 JSON file; default stdin; - means stdin")
    inspect = commands.add_parser("inspect", help="show current state and provenance")
    inspect.add_argument("entity")
    inspect.add_argument("attribute")
    profile = commands.add_parser("profile", help="read live resolved facts")
    profile.add_argument("--max-bytes", type=positive_integer, default=8192)
    context = commands.add_parser("context", help="find live facts with BM25")
    context.add_argument("query")
    context.add_argument("--max-bytes", type=positive_integer, default=8192)
    forget = commands.add_parser("forget", help="forget using the inspected revision")
    forget.add_argument("entity")
    forget.add_argument("attribute")
    forget.add_argument("--expected-revision", required=True, type=positive_integer)
    capture = commands.add_parser("capture", help="preview proposals from an installed local model")
    capture.add_argument("--file", type=Path, help="UTF-8 user turn; default stdin; - means stdin")
    capture.add_argument("--source-id", required=True)
    capture.add_argument("--occurred-at-ms", type=timestamp, help="historical epoch milliseconds; default current time")
    capture.add_argument("--model", required=True, help="already installed Ollama model")
    capture.add_argument("--ollama-url", default="http://127.0.0.1:11434")
    capture.add_argument("--apply", action="store_true", help="explicitly apply proposed assertions")
    return root


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        proposals = None
        if args.command == "capture":
            from .extraction import extract_proposals

            occurred_at_ms = args.occurred_at_ms
            if occurred_at_ms is None:
                occurred_at_ms = time.time_ns() // 1_000_000
            proposals = extract_proposals(read_input(args.file, MAX_CAPTURE_BYTES), args.source_id,
                                          occurred_at_ms, args.model,
                                          ollama_url=args.ollama_url)
            if not args.apply:
                emit({"proposals": proposals, "applied": False})
                return 0
            proposals = validate_batch(proposals)
        proposal = read_proposal(args.file) if args.command == "apply" else None
        if proposal is not None and ("proposals" in proposal or "applied" in proposal):
            if set(proposal) != {"proposals", "applied"} or proposal["applied"] is not False:
                raise InputError("invalid_preview")
            proposals = validate_batch(proposal["proposals"])
        from . import HTTPStore, MemoryController

        controller = MemoryController(HTTPStore(args.url, args.secrets_file),
                                      namespace=args.namespace, scope=args.scope)
        if proposals is not None:
            return apply_batch(controller, proposals)
        if args.command == "apply":
            result = controller.apply(proposal)
        elif args.command == "inspect":
            result = controller.inspect(args.entity, args.attribute)
            if result is None:
                print("Memory not found. Check entity, attribute and scope, or apply a new proposal.", file=sys.stderr)
                return 1
        elif args.command == "profile":
            result = controller.profile(max_bytes=args.max_bytes)
        elif args.command == "context":
            result = controller.context(args.query, max_bytes=args.max_bytes)
        else:
            result = controller.forget(args.entity, args.attribute,
                                       expected_revision=args.expected_revision)
        emit(result)
        if args.command == "apply" and result["status"] == "conflict":
            print("Conflicting fact saved for review. Inspect the slot, then correct with its current revision.", file=sys.stderr)
            return 1
        return 0
    except Exception as error:
        _, message = recovery(error)
        print(message, file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Interrupted. Inspect the slot before retrying identical input.", file=sys.stderr)
        return 130
