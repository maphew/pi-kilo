#!/usr/bin/env python3
"""Import a Kilo session into Pi and continue it locally (pi-kilo-er5).

Fetches a Kilo cloud session export (the same export `kilo --session <id>
--cloud-fork` uses), converts messages/parts to Pi's session JSONL format, and
optionally execs `pi --session <file>` so the conversation continues with Pi's
own tools, permissions, and model.

Usage:
  pi-kilo ses_eb5d...                                           # installed CLI
  python3 prototype/kilo_import.py ses_eb5...                      # import + exec pi
  python3 prototype/kilo_import.py --session ses_eb5... --cloud-fork
  python3 prototype/kilo_import.py ses_eb5... --cwd ~/dev/x -- --model kilo/x
  python3 prototype/kilo_import.py ses_eb5... --import-only --out /tmp/x.jsonl
  python3 prototype/kilo_import.py --export-json saved.json --cwd ~/dev/x --import-only

Auth:
  Reads the Kilo OAuth access token from ~/.local/share/kilo/auth.json
  (override with --auth-file or KILO_AUTH_FILE). No token is logged or written.

Honest boundaries:
  - One-way history import at a point in time, not live integration. The Pi
    session has its own identity; Kilo does not see its new turns.
  - Linked Kilo branches resolve to the newest path; alternatives are dropped
    and reported. Classic root-user-turn exports are imported in full.
  - Kilo compaction summaries become Pi compaction entries with the retained
    tail mapped from tail_start_id.
  - Kilo's runtime state (pending permissions, provider metadata, snapshots,
    patches, private reasoning signatures) is not migrated beyond history text,
    tool calls, and tool results.
  - Local file state is whatever is in --cwd now; Kilo's cloud workspace restore
    (sessionDiff) is intentionally not applied.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import shutil
import sys
import urllib.error
import urllib.request
import uuid
from collections import Counter
from pathlib import Path

DEFAULT_INGEST = os.environ.get(
    "KILO_SESSION_INGEST_URL", "https://ingest.kilosessions.ai"
)
DEFAULT_AUTH = Path.home() / ".local" / "share" / "kilo" / "auth.json"


# ---------- Kilo auth + fetch -------------------------------------------------


def read_kilo_token(auth_file: Path) -> str:
    """Return the Kilo OAuth access token; fail with a actionable message."""
    try:
        data = json.loads(auth_file.read_text())
    except FileNotFoundError:
        sys.exit(
            f"error: no Kilo credentials at {auth_file}\n"
            "run `kilo auth login` first (or pass --auth-file)"
        )
    except (OSError, json.JSONDecodeError) as err:
        sys.exit(f"error: cannot read {auth_file}: {err}")
    token = (data.get("kilo") or {}).get("access")
    if not token:
        sys.exit(
            f"error: no Kilo access token in {auth_file}\n"
            "run `kilo auth login` first"
        )
    return token


def export_url(ingest: str, session_id: str) -> str:
    # Mirrors @kilocode/kilo-gateway: UUID sessions use /session/<id>, Kilo
    # `ses_...` ids use /api/session/<id>/export.
    uuid_re = re.compile(
        r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I
    )
    base = ingest.rstrip("/")
    if uuid_re.match(session_id):
        return f"{base}/session/{session_id}"
    return f"{base}/api/session/{session_id}/export"


def fetch_export(token: str, session_id: str, ingest: str) -> dict:
    url = export_url(ingest, session_id)
    # The gateway gates on a Kilo-like User-Agent (a default Python UA is
    # rejected with 403), and Kilo sets the editor header on every request.
    request = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "User-Agent": "opencode-kilo-provider",
            "X-KILOCODE-EDITORNAME": "Kilo CLI",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response)
    except urllib.error.HTTPError as err:
        if err.code == 404:
            sys.exit(f"error: Kilo session {session_id} not found in the cloud")
        if err.code in (401, 403):
            sys.exit(
                f"error: Kilo cloud rejected the request ({err.code})\n"
                "run `kilo auth login` to refresh credentials"
            )
        sys.exit(f"error: Kilo cloud export failed ({err.code})")
    except (urllib.error.URLError, TimeoutError) as err:
        sys.exit(f"error: cannot reach {url}: {err}")


# ---------- conversion --------------------------------------------------------


def _iso(ms: float | int | None) -> str:
    if not ms:
        return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    return dt.datetime.fromtimestamp(ms / 1000, dt.timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%S.%f"
    )[:-3] + "Z"


def _usage(parts: list[dict]) -> dict:
    """Sum Kilo step-finish token/cost data into Pi's Usage shape."""
    totals = Counter()
    cost = 0.0
    for part in parts:
        if part.get("type") != "step-finish":
            continue
        tokens = part.get("tokens") or {}
        cache = tokens.get("cache") or {}
        totals["input"] += tokens.get("input") or 0
        totals["output"] += tokens.get("output") or 0
        totals["reasoning"] += tokens.get("reasoning") or 0
        totals["total"] += tokens.get("total") or 0
        totals["cacheRead"] += cache.get("read") or 0
        totals["cacheWrite"] += cache.get("write") or 0
        cost += part.get("cost") or 0
    return {
        "input": totals["input"],
        "output": totals["output"],
        "cacheRead": totals["cacheRead"],
        "cacheWrite": totals["cacheWrite"],
        "reasoning": totals["reasoning"],
        "totalTokens": totals["total"],
        "cost": {
            "input": 0,
            "output": 0,
            "cacheRead": 0,
            "cacheWrite": 0,
            "total": cost,
        },
    }


def _stop_reason(info: dict, content: list[dict]) -> str:
    finish = info.get("finish")
    if finish == "tool-calls" or any(c["type"] == "toolCall" for c in content):
        return "toolUse"
    return {
        "stop": "stop",
        "length": "length",
        "error": "error",
        "aborted": "aborted",
    }.get(finish or "stop", "stop")


def _info(message: dict) -> dict:
    return message.get("info") or {}


def _message_id(message: dict) -> str:
    return _info(message).get("id") or ""


def _parent_id(message: dict) -> str | None:
    return _info(message).get("parentID")


def _ordered_messages(messages: list[dict]) -> list[dict]:
    # Kilo's own importer orders by ascending message id, which is transcript
    # order for cloud exports (the export lists ingest order).
    return sorted(messages, key=_message_id)


def _owner_user(message: dict, by_id: dict[str, dict]) -> str | None:
    """Return the user message that owns this assistant message, if linked."""
    current = _parent_id(message)
    seen: set[str] = set()
    while current and current not in seen:
        seen.add(current)
        parent = by_id.get(current)
        if not parent:
            return None
        if _info(parent).get("role") == "user":
            return current
        current = _parent_id(parent)
    return None


def _select_active_messages(messages: list[dict]) -> tuple[list[dict], dict]:
    """Follow the active Kilo branch while preserving classic linear exports.

    Kilo normally stores every user turn as a root and links assistant steps to
    their user message. That is linear, so all messages are kept. When a cloud
    export does link user turns into a parent tree (forks/regenerations), pick
    the branch whose newest descendant is latest and drop the alternatives.
    """
    ordered = _ordered_messages(messages)
    by_id = {_message_id(message): message for message in ordered}
    users = [message for message in ordered if _info(message).get("role") == "user"]
    user_ids = {_message_id(message) for message in users}
    index = {_message_id(message): position for position, message in enumerate(ordered)}

    owner: dict[str, str] = {}
    for message in ordered:
        if _info(message).get("role") != "assistant":
            continue
        user_id = _owner_user(message, by_id)
        if user_id:
            owner[_message_id(message)] = user_id

    # Defensive fallback for exports with unlinked assistant messages: attach
    # them to the closest preceding user turn rather than losing their output.
    for message in ordered:
        message_id = _message_id(message)
        if _info(message).get("role") != "assistant" or message_id in owner:
            continue
        position = index[message_id]
        preceding = [
            user for user in users if index[_message_id(user)] < position
        ]
        if preceding:
            owner[message_id] = _message_id(preceding[-1])

    turn_parent: dict[str, str] = {}
    for user in users:
        user_id = _message_id(user)
        parent_id = _parent_id(user)
        if not parent_id:
            continue
        if parent_id in user_ids:
            turn_parent[user_id] = parent_id
        elif parent_id in owner:
            turn_parent[user_id] = owner[parent_id]

    if not turn_parent:
        return ordered, {"branches": 0, "branchTurnsDropped": 0}

    children: dict[str, list[dict]] = {}
    roots: list[dict] = []
    for user in users:
        parent = turn_parent.get(_message_id(user))
        if parent:
            children.setdefault(parent, []).append(user)
        else:
            roots.append(user)

    assistants_by_owner: dict[str, list[str]] = {}
    for message_id, user_id in owner.items():
        assistants_by_owner.setdefault(user_id, []).append(message_id)

    latest: dict[str, int] = {}

    def subtree_latest(user: dict) -> int:
        user_id = _message_id(user)
        if user_id not in latest:
            best = index[user_id]
            for assistant_id in assistants_by_owner.get(user_id, []):
                best = max(best, index[assistant_id])
            for child in children.get(user_id, []):
                best = max(best, subtree_latest(child))
            latest[user_id] = best
        return latest[user_id]

    active: set[str] = set()

    def include_branch(user: dict) -> None:
        user_id = _message_id(user)
        active.add(user_id)
        candidates = children.get(user_id, [])
        if candidates:
            include_branch(max(candidates, key=subtree_latest))

    for root in roots:
        include_branch(root)

    selected = []
    for message in ordered:
        role = _info(message).get("role")
        message_id = _message_id(message)
        if role == "user" and message_id in active:
            selected.append(message)
        elif role == "assistant" and owner.get(message_id) in active:
            selected.append(message)

    return selected, {
        "branches": len(turn_parent),
        "branchTurnsDropped": len(users) - len(active),
    }


def _compaction_part(message: dict) -> dict | None:
    for part in message.get("parts") or []:
        if part.get("type") == "compaction":
            return part
    return None


def _compaction_summary(
    compaction: dict, messages: list[dict]
) -> dict | None:
    """Find the assistant message that carries Kilo's compaction summary."""
    compaction_id = _message_id(compaction)
    candidates = [
        message
        for message in messages
        if _info(message).get("role") == "assistant"
        and _parent_id(message) == compaction_id
        and _info(message).get("summary")
    ]
    return max(candidates, key=_message_id) if candidates else None


def _tool_result(part: dict, call: dict, timestamp: int) -> dict:
    state = part.get("state") or {}
    completed = state.get("status") == "completed"
    if completed:
        output = state.get("output", "")
        text = output if isinstance(output, str) else json.dumps(output)
        return {
            "role": "toolResult",
            "toolCallId": call["id"],
            "toolName": call["name"],
            "content": [{"type": "text", "text": text}],
            "isError": False,
            "timestamp": timestamp,
        }
    error = state.get("error") or state.get("status") or "tool did not complete"
    return {
        "role": "toolResult",
        "toolCallId": call["id"],
        "toolName": call["name"],
        "content": [{"type": "text", "text": str(error)}],
        "isError": True,
        "timestamp": timestamp,
    }


def convert_export(export: dict, cwd: str, kilo_session_id: str) -> tuple[list[dict], dict]:
    """Convert a Kilo session export into Pi session entries.

    Returns (entries, stats). Entries include the session header.
    """
    info = export.get("info") or {}
    messages = export.get("messages") or []
    stats: Counter = Counter()
    entries: list[dict] = []

    session_uuid = str(uuid.uuid4())
    created = (info.get("time") or {}).get("created")
    entries.append(
        {
            "type": "session",
            "version": 3,
            "id": session_uuid,
            "timestamp": _iso(created),
            "cwd": cwd,
        }
    )
    entries.append(
        {
            "type": "custom",
            "id": "kilo-import",
            "parentId": None,
            "timestamp": _iso(created),
            "customType": "kilo_import",
            "data": {
                "sessionId": kilo_session_id,
                "title": info.get("title"),
                "directory": info.get("directory"),
                "model": info.get("model"),
                "importedAt": dt.datetime.now(dt.timezone.utc).isoformat(),
            },
        }
    )
    parent = "kilo-import"
    if info.get("title"):
        entries.append(
            {
                "type": "session_info",
                "id": "kilo-title",
                "parentId": parent,
                "timestamp": _iso(created),
                "name": f"{info['title']} (Kilo {kilo_session_id})",
            }
        )
        parent = "kilo-title"

    # Follow the active branch when the export links user turns into a tree.
    # Classic Kilo exports keep every user turn at the root and are unchanged.
    selected_messages, branch_stats = _select_active_messages(messages)
    for key, value in branch_stats.items():
        stats[key] = value

    # Map a Kilo message id to the first Pi entry we emit for it. Compaction
    # summaries point at the retained tail with firstKeptEntryId.
    message_entry_ids: dict[str, str] = {}
    summary_by_compaction: dict[str, dict] = {}
    consumed_summaries: set[str] = set()
    for message in selected_messages:
        if _info(message).get("role") != "user" or not _compaction_part(message):
            continue
        summary = _compaction_summary(message, selected_messages)
        if summary:
            summary_by_compaction[_message_id(message)] = summary
            consumed_summaries.add(_message_id(summary))

    last_tokens_before = 0
    for message in selected_messages:
        meta = _info(message)
        role = meta.get("role")
        message_id = _message_id(message)
        timestamp = (meta.get("time") or {}).get("created")
        parts = sorted(message.get("parts") or [], key=lambda p: p.get("id", ""))

        if message_id in consumed_summaries:
            # The assistant summary is represented by Pi's compaction entry.
            stats["skipped-compaction-summary"] += 1
            continue

        compaction = _compaction_part(message) if role == "user" else None
        if compaction:
            summary = summary_by_compaction.get(message_id)
            summary_parts = sorted(
                (summary or {}).get("parts") or [], key=lambda p: p.get("id", "")
            )
            summary_text = "\n\n".join(
                part.get("text") or ""
                for part in summary_parts
                if part.get("type") == "text" and part.get("text")
            )
            if not summary_text:
                summary_text = (
                    "Kilo compaction summary was unavailable "
                    f"(source compaction {meta.get('id')})."
                )
            entry_id = f"kilo-compaction-{message_id}"
            tail_id = compaction.get("tail_start_id")
            first_kept = message_entry_ids.get(tail_id) if tail_id else None
            if tail_id and not first_kept:
                stats["compaction-tail-missing"] += 1
            entry = {
                "type": "compaction",
                "id": entry_id,
                "parentId": parent,
                "timestamp": _iso(timestamp),
                "summary": summary_text,
                "firstKeptEntryId": first_kept or entry_id,
                "tokensBefore": last_tokens_before,
                "details": {
                    "source": "kilo",
                    "compactionPartId": compaction.get("id"),
                    "auto": compaction.get("auto"),
                    "overflow": compaction.get("overflow"),
                    "tailStartId": tail_id,
                },
            }
            if summary:
                entry["usage"] = _usage(summary_parts)
            entries.append(entry)
            parent = entry_id
            message_entry_ids[message_id] = entry_id
            stats["compaction"] += 1
            continue

        if role == "user":
            texts: list[str] = []
            images: list[dict] = []
            for part in parts:
                if part.get("type") == "text":
                    texts.append(part.get("text") or "")
                    stats["text"] += 1
                elif part.get("type") == "file":
                    match = re.match(
                        r"data:(.*?);base64,(.*)", part.get("url") or "", re.S
                    )
                    if match:
                        images.append(
                            {
                                "type": "image",
                                "data": match.group(2),
                                "mimeType": match.group(1),
                            }
                        )
                else:
                    stats[f"skipped-{part.get('type')}"] += 1
            if len(texts) == 1 and not images:
                content: object = texts[0]
            else:
                content = [
                    {"type": "text", "text": text} for text in texts if text
                ] + images
            entry_id = f"kilo-{message_id}"
            entries.append(
                {
                    "type": "message",
                    "id": entry_id,
                    "parentId": parent,
                    "timestamp": _iso(timestamp),
                    "message": {
                        "role": "user",
                        "content": content,
                        "timestamp": timestamp,
                    },
                }
            )
            parent = entry_id
            message_entry_ids[message_id] = entry_id
            stats["user"] += 1
            continue

        if role != "assistant":
            stats[f"skipped-role-{role}"] += 1
            continue

        content = []
        results = []
        for part in parts:
            kind = part.get("type")
            if kind == "text":
                if part.get("text"):
                    content.append({"type": "text", "text": part["text"]})
                    stats["text"] += 1
            elif kind == "reasoning":
                if part.get("text"):
                    content.append({"type": "thinking", "thinking": part["text"]})
                    stats["thinking"] += 1
            elif kind == "tool":
                state = part.get("state") or {}
                call = {
                    "type": "toolCall",
                    "id": part.get("callID") or part.get("id"),
                    "name": part.get("tool") or "unknown",
                    "arguments": state.get("input")
                    if isinstance(state.get("input"), dict)
                    else {},
                }
                content.append(call)
                result_time = (state.get("time") or {}).get("end") or timestamp
                results.append(_tool_result(part, call, result_time))
                stats["tool"] += 1
            else:
                # step-start/step-finish/patch and future parts
                stats[f"skipped-{kind}"] += 1

        if not content:
            continue

        usage = _usage(parts)
        last_tokens_before = usage.get("totalTokens") or last_tokens_before
        model = meta.get("modelID") or (info.get("model") or {}).get("id") or "imported"
        entry_id = f"kilo-{message_id}"
        entries.append(
            {
                "type": "message",
                "id": entry_id,
                "parentId": parent,
                "timestamp": _iso(timestamp),
                "message": {
                    "role": "assistant",
                    "content": content,
                    "api": "openai-completions",
                    "provider": meta.get("providerID") or "kilo",
                    "model": model,
                    "usage": usage,
                    "stopReason": _stop_reason(meta, content),
                    "timestamp": timestamp,
                },
            }
        )
        parent = entry_id
        message_entry_ids[message_id] = entry_id
        stats["assistant"] += 1

        for index, result in enumerate(results):
            result_id = f"kilo-{message_id}-result-{index}"
            entries.append(
                {
                    "type": "message",
                    "id": result_id,
                    "parentId": parent,
                    "timestamp": _iso(result["timestamp"]),
                    "message": result,
                }
            )
            parent = result_id
            stats["toolResult"] += 1

    return entries, dict(stats)


# ---------- Pi session placement ----------------------------------------------


def resolve_pi() -> str:
    """Find the pi binary without depending on the caller's PATH."""
    candidates = [
        os.environ.get("PI_BIN"),
        shutil.which("pi"),
        "/home/linuxbrew/.linuxbrew/bin/pi",
        str(Path.home() / ".pi" / "agent" / "bin" / "pi"),
    ]
    for candidate in candidates:
        if candidate and os.access(candidate, os.X_OK):
            return candidate
    sys.exit("error: pi not found; set PI_BIN or put pi on PATH")


def resolve_node(pi_path: str) -> str | None:
    """Find node so pi's `#!/usr/bin/env node` shebang works after exec."""
    candidates = [
        shutil.which("node"),
        str(Path(pi_path).parent / "node"),
        "/home/linuxbrew/.linuxbrew/bin/node",
        "/usr/local/bin/node",
        "/usr/bin/node",
    ]
    for candidate in candidates:
        if candidate and os.access(candidate, os.X_OK):
            return candidate
    return None


def pi_session_dir(cwd: str) -> Path:
    """Match Pi's default session directory for a project path."""
    slug = re.sub(r"[/\\:]", "-", cwd.lstrip("/\\"))
    agent_dir = os.environ.get("PI_CODING_AGENT_DIR") or str(
        Path.home() / ".pi" / "agent"
    )
    return Path(agent_dir) / "sessions" / f"--{slug}--"


def write_session(entries: list[dict], cwd: str, out: Path | None) -> Path:
    if out is None:
        directory = pi_session_dir(cwd)
        directory.mkdir(parents=True, exist_ok=True)
        stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H-%M-%S-%f")[:-3] + "Z"
        out = directory / f"{stamp}_{entries[0]['id']}.jsonl"
    else:
        out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as handle:
        for entry in entries:
            handle.write(json.dumps(entry, separators=(",", ":")) + "\n")
    return out


# ---------- main --------------------------------------------------------------


def load_export(args: argparse.Namespace) -> dict:
    if args.export_json:
        try:
            return json.loads(Path(args.export_json).read_text())
        except (OSError, json.JSONDecodeError) as err:
            sys.exit(f"error: cannot read export {args.export_json}: {err}")
    token = read_kilo_token(Path(args.auth_file).expanduser())
    return fetch_export(token, args.session, args.ingest)


def main(argv: list[str] | None = None) -> int:
    raw = list(sys.argv[1:] if argv is None else argv)
    # Reverse direction (Pi -> Kilo) lives in pi_to_kilo.py. Dispatch only on
    # explicit subcommands so `pi-kilo ses_...` keeps working unchanged.
    if raw and raw[0] in {"import", "publish"}:
        from pi_to_kilo import main as reverse_main

        return reverse_main(raw)
    parser = argparse.ArgumentParser(
        description="Import a Kilo cloud session into Pi and optionally continue it"
    )
    parser.add_argument("session", nargs="?", help="Kilo session id, e.g. ses_...")
    parser.add_argument(
        "--session",
        dest="session_opt",
        help="Kilo session id (Kilo-compatible spelling of the positional)",
    )
    parser.add_argument(
        "--cloud-fork",
        action="store_true",
        help="Kilo-compatible marker: fetch the cloud session and continue locally",
    )
    parser.add_argument(
        "--import-only",
        action="store_true",
        help="write the Pi session but do not exec pi",
    )
    parser.add_argument("--cwd", default=os.getcwd(), help="Pi project directory")
    parser.add_argument("--out", help="write the Pi session here instead of Pi's session dir")
    parser.add_argument(
        "--export-json",
        help="convert a previously saved Kilo export instead of fetching",
    )
    parser.add_argument(
        "--auth-file",
        default=str(DEFAULT_AUTH),
        help=f"Kilo auth.json (default: {DEFAULT_AUTH})",
    )
    parser.add_argument(
        "--ingest",
        default=DEFAULT_INGEST,
        help=f"Kilo session ingest base URL (default: {DEFAULT_INGEST})",
    )
    # Split passthrough args at a literal `--` so option parsing stays strict
    # (`--out` after a trailing REMAINDER positional would be swallowed).
    raw = list(sys.argv[1:] if argv is None else argv)
    if "--" in raw:
        split = raw.index("--")
        raw, passthrough = raw[:split], raw[split + 1:]
    else:
        passthrough = []
    args = parser.parse_args(raw)

    if args.session and args.session_opt:
        parser.error("pass the session id once (positional or --session)")
    session = args.session or args.session_opt
    if not session and not args.export_json:
        parser.error("a Kilo session id is required (or pass --export-json)")
    if args.cloud_fork and not session:
        parser.error("--cloud-fork requires --session (matching Kilo's CLI)")
    if not args.import_only and args.export_json:
        parser.error("--export-json cannot continue a live session; add --import-only")

    args.session = session
    cwd = str(Path(args.cwd).expanduser().resolve())
    export = load_export(args)
    info = export.get("info") or {}
    session_id = session or info.get("id") or "unknown"

    kilo_directory = info.get("directory")
    if kilo_directory and Path(kilo_directory).resolve() != Path(cwd):
        print(
            f"warning: Kilo recorded cwd {kilo_directory!r}; importing into {cwd!r}.\n"
            "         File state is whatever exists in the target directory now.\n",
            file=sys.stderr,
        )

    entries, stats = convert_export(export, cwd, session_id)
    out = write_session(entries, cwd, Path(args.out).expanduser() if args.out else None)

    print(f"Kilo session : {session_id} ({info.get('title') or 'untitled'})")
    print(f"Pi session   : {out}")
    print(
        "Imported     : "
        + ", ".join(
            f"{stats.get(k, 0)} {k}"
            for k in ("user", "assistant", "tool", "toolResult", "compaction")
        )
    )
    if stats.get("branchTurnsDropped"):
        print(
            "Branches     : "
            f"{stats.get('branches', 0)} linked turn(s), "
            f"kept the newest path and dropped {stats['branchTurnsDropped']} turn(s)"
        )
    skipped = {k: v for k, v in stats.items() if str(k).startswith("skipped-")}
    if skipped:
        print("Skipped parts: " + ", ".join(f"{k[8:]}={v}" for k, v in sorted(skipped.items())))

    extra = passthrough
    if args.import_only:
        print(f"\nContinue with: pi --session {out}")
        return 0

    pi = resolve_pi()
    argv_pi = [pi, "--session", str(out), *extra]
    # Some environments (pixi, wrappers) hand us a PATH that lacks the dirs pi
    # and its node shebang need; add them explicitly for the new process.
    env = dict(os.environ)
    bin_dirs = [str(Path(pi).parent)]
    node = resolve_node(pi)
    if node:
        bin_dirs.append(str(Path(node).parent))
    env["PATH"] = os.pathsep.join(bin_dirs + [env.get("PATH", "")])
    print(f"\nExec: {' '.join(argv_pi)}", flush=True)
    os.execve(pi, argv_pi, env)
    return 0  # unreachable


if __name__ == "__main__":
    raise SystemExit(main())
