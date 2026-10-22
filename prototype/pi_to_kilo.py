#!/usr/bin/env python3
"""Make Pi sessions available in Kilo, locally by default (pi-kilo-5fm).

Two explicit steps, mirroring Kilo's own local-vs-cloud behavior:

  import   Pi JSONL -> Kilo export JSON -> local Kilo session store
           (runs `kilo import` with KILO_DISABLE_SESSION_INGEST=1)
  publish  Read a local Kilo session back out of its SQLite store and POST
           the history to the Kilo ingest API (opt-in; requires --post)

Importing never contacts Kilo Cloud. Publishing uploads history only: it does
not make the session live, and messages sent from Kilo still execute in Kilo,
not Pi. See PiToKilo.md for the boundaries.

Usage:
  pi-kilo import --all
  pi-kilo import --session 01a1338f
  pi-kilo import --cwd ~/dev/project
  pi-kilo import --all --dry-run --out /tmp/kilo-exports
  pi-kilo publish --list
  pi-kilo publish ses_...            # prints what would be sent
  pi-kilo publish ses_... --post     # actually uploads history
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

# ---------- shared helpers ----------------------------------------------------

B62 = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
KILO_MSG_PREFIX = "msg"
KILO_PART_PREFIX = "prt"
KILO_SESSION_PREFIX = "ses"

# Cloud ingest limits (services/session-ingest/src/util/ingest-limits.ts).
INGEST_CHUNK_MAX_BYTES = 4 * 1024 * 1024
INGEST_CHUNK_MAX_ITEMS = 128


def _b62_suffix(stable_key: str, length: int = 14) -> str:
    digest = hashlib.sha256(stable_key.encode("utf-8")).digest()
    return "".join(B62[byte % 62] for byte in digest[:length])


def kilo_id(prefix: str, timestamp_ms: int, stable_key: str, counter: int = 0) -> str:
    """Mirror Kilo's Identifier.ascending: 12 hex time chars + 14 base62.

    The suffix is derived from `stable_key` instead of crypto randomness so a
    re-import produces the same ids and stays idempotent.
    """
    value = (int(timestamp_ms) * 0x1000 + int(counter)) & ((1 << 48) - 1)
    return f"{prefix}_{value:012x}{_b62_suffix(stable_key)}"


class IdGen:
    """Kilo-compatible ascending ids, deterministic and monotonic per session."""

    def __init__(self) -> None:
        self.last_ts = 0
        self.counter = 0

    def next(self, prefix: str, timestamp_ms: int, stable_key: str) -> str:
        ts = int(timestamp_ms)
        if ts < self.last_ts:
            ts = self.last_ts
        if ts != self.last_ts:
            self.last_ts = ts
            self.counter = 0
        self.counter += 1
        return kilo_id(prefix, ts, stable_key, self.counter)


def _iso_to_ms(value: str | None) -> int | None:
    if not value:
        return None
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return int(parsed.timestamp() * 1000)


def _entry_ms(entry: dict) -> int:
    message = entry.get("message") or {}
    if isinstance(message.get("timestamp"), (int, float)):
        return int(message["timestamp"])
    return _iso_to_ms(entry.get("timestamp")) or 0


def _text_of(content) -> str:
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    chunks = []
    for block in content:
        if isinstance(block, dict) and block.get("type") == "text":
            chunks.append(block.get("text") or "")
    return "\n\n".join(chunk for chunk in chunks if chunk)


# ---------- Pi session discovery ---------------------------------------------


def pi_agent_dir() -> Path:
    return Path(os.environ.get("PI_CODING_AGENT_DIR") or Path.home() / ".pi" / "agent")


def pi_sessions_root() -> Path:
    return Path(os.environ.get("PI_SESSIONS_DIR") or pi_agent_dir() / "sessions")


def read_header(path: Path) -> dict:
    try:
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                record = json.loads(line)
                if record.get("type") == "session":
                    return record
                return {}
    except (OSError, json.JSONDecodeError):
        return {}
    return {}


def load_entries(path: Path) -> tuple[dict, list[dict]]:
    header: dict = {}
    entries: list[dict] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if record.get("type") == "session" and not header:
                header = record
            elif record.get("id"):
                entries.append(record)
    return header, entries


def discover_sessions() -> list[dict]:
    root = pi_sessions_root()
    found: list[dict] = []
    if not root.is_dir():
        return found
    for path in sorted(root.glob("*/*.jsonl")):
        header = read_header(path)
        found.append(
            {
                "path": path,
                "id": header.get("id") or path.stem.split("_")[-1],
                "cwd": header.get("cwd"),
                "timestamp": header.get("timestamp"),
                "mtime": path.stat().st_mtime,
            }
        )
    return found


def select_sessions(
    sessions: list[dict], wanted: str | None, cwd: str | None
) -> list[dict]:
    selected = sessions
    if wanted:
        wanted_path = str(Path(wanted).expanduser())
        selected = [
            item
            for item in selected
            if item["id"] == wanted
            or item["id"].startswith(wanted)
            or str(item["path"]) == wanted_path
            or item["path"].name == wanted
        ]
    if cwd:
        cwd_resolved = str(Path(cwd).expanduser().resolve())
        selected = [item for item in selected if item.get("cwd") == cwd_resolved]
    return selected


# ---------- Pi -> Kilo export conversion -------------------------------------


def active_chain(entries: list[dict]) -> list[dict]:
    """Return root->leaf for the file's current leaf.

    Pi appends entries and records the active leaf implicitly as the last entry
    written. Walking parentId from there yields the active branch, so abandoned
    `/tree` branches are not imported.
    """
    if not entries:
        return []
    by_id = {entry["id"]: entry for entry in entries}
    leaf = entries[-1]
    chain: list[dict] = []
    seen: set[str] = set()
    current = leaf
    while current and current.get("id") not in seen:
        seen.add(current.get("id"))
        chain.append(current)
        parent_id = current.get("parentId")
        current = by_id.get(parent_id) if parent_id else None
    chain.reverse()
    return chain


def _session_title(chain: list[dict], header: dict) -> str:
    for entry in reversed(chain):
        if entry.get("type") == "session_info" and entry.get("name"):
            return str(entry["name"])
    for entry in chain:
        if entry.get("type") != "message":
            continue
        message = entry.get("message") or {}
        if message.get("role") != "user":
            continue
        text = _text_of(message.get("content")).strip().splitlines()
        if text and text[0]:
            line = text[0].strip()
            return line[:80] + ("…" if len(line) > 80 else "")
    return f"Pi session {header.get('id', '')[:8]}"


def _model_for_user(chain: list[dict], position: int, fallback: dict) -> dict:
    for entry in chain[position + 1 :]:
        if entry.get("type") != "message":
            continue
        message = entry.get("message") or {}
        if message.get("role") == "assistant" and message.get("model"):
            return {
                "providerID": message.get("provider") or fallback["providerID"],
                "modelID": message.get("model") or fallback["modelID"],
            }
    return fallback


def _tool_results(chain: list[dict]) -> dict[str, dict]:
    results: dict[str, dict] = {}
    for entry in chain:
        if entry.get("type") != "message":
            continue
        message = entry.get("message") or {}
        if message.get("role") == "toolResult":
            call_id = message.get("toolCallId")
            if call_id:
                results[call_id] = message
    return results


def _tool_part(
    ids: IdGen,
    *,
    session_id: str,
    message_id: str,
    timestamp: int,
    entry_id: str,
    index: int,
    call: dict,
    result: dict | None,
) -> dict:
    args = call.get("arguments")
    if not isinstance(args, dict):
        args = {"value": args}
    tool_name = call.get("name") or "unknown"
    call_id = call.get("id") or f"{entry_id}-call-{index}"
    part_id = ids.next(KILO_PART_PREFIX, timestamp, f"{entry_id}:tool:{index}")
    start = timestamp
    if result is None:
        state = {
            "status": "error",
            "input": args,
            "error": "tool call did not complete in the Pi session",
            "time": {"start": start, "end": start},
        }
    else:
        end = _entry_ms({"message": result}) or start
        text = _text_of(result.get("content"))
        is_error = bool(result.get("isError"))
        if is_error:
            state = {
                "status": "error",
                "input": args,
                "error": text or "tool failed",
                "time": {"start": start, "end": max(start, end)},
            }
        else:
            title = tool_name
            preview = args.get("command") or args.get("filePath") or args.get("path")
            if isinstance(preview, str) and preview:
                title = f"{tool_name}: {preview[:60]}"
            state = {
                "status": "completed",
                "input": args,
                "output": text,
                "title": title,
                "metadata": {},
                "time": {"start": start, "end": max(start, end)},
            }
    return {
        "id": part_id,
        "sessionID": session_id,
        "messageID": message_id,
        "type": "tool",
        "callID": call_id,
        "tool": tool_name,
        "state": state,
    }


def _image_part(
    ids: IdGen,
    *,
    session_id: str,
    message_id: str,
    timestamp: int,
    entry_id: str,
    index: int,
    block: dict,
) -> dict:
    mime = block.get("mimeType") or "application/octet-stream"
    data = block.get("data") or ""
    return {
        "id": ids.next(KILO_PART_PREFIX, timestamp, f"{entry_id}:image:{index}"),
        "sessionID": session_id,
        "messageID": message_id,
        "type": "file",
        "mime": mime,
        "url": f"data:{mime};base64,{data}",
    }


def convert_session(
    path: Path,
    *,
    cwd: str | None = None,
    kilo_version: str = "0.0.0",
) -> tuple[dict, dict]:
    """Convert one Pi session file into a Kilo `{info, messages}` export."""
    header, entries = load_entries(path)
    chain = active_chain(entries)
    stats: dict[str, int] = {}

    def bump(key: str) -> None:
        stats[key] = stats.get(key, 0) + 1

    pi_session_id = header.get("id") or path.stem.split("_")[-1]
    directory = str(Path(cwd or header.get("cwd") or os.getcwd()).expanduser().resolve())
    created = _iso_to_ms(header.get("timestamp")) or (
        _entry_ms(chain[0]) if chain else int(dt.datetime.now().timestamp() * 1000)
    )
    updated = _entry_ms(chain[-1]) if chain else created
    updated = max(updated, created)
    title = _session_title(chain, header)

    # Session-scoped model fallback for user messages.
    default_model = {"providerID": "pi", "modelID": "unknown"}
    for entry in chain:
        if entry.get("type") == "message":
            message = entry.get("message") or {}
            if message.get("role") == "assistant" and message.get("model"):
                default_model = {
                    "providerID": message.get("provider") or "pi",
                    "modelID": message["model"],
                }
                break

    ids = IdGen()
    session_id = kilo_id(KILO_SESSION_PREFIX, created, f"pi-session:{pi_session_id}")
    info = {
        "id": session_id,
        "slug": f"pi-{pi_session_id[:8]}",
        "projectID": "global",
        "directory": directory,
        "title": title,
        "version": kilo_version,
        "agent": "pi",
        "model": {"id": default_model["modelID"], "providerID": default_model["providerID"]},
        "time": {"created": created, "updated": updated},
        "metadata": {
            "pi": {
                "sessionId": pi_session_id,
                "path": str(path),
                "importedAt": dt.datetime.now(dt.timezone.utc).isoformat(),
            }
        },
    }
    messages: list[dict] = []
    tool_results = _tool_results(chain)
    consumed: set[str] = set()
    last_user_id: str | None = None

    for position, entry in enumerate(chain):
        kind = entry.get("type")
        if kind in {"compaction", "branch_summary", "context_edit", "label", "custom",
                    "custom_message", "model_change", "thinking_level_change",
                    "session_info", "usage"}:
            bump(f"skipped-{kind}")
            continue
        if kind != "message":
            bump(f"skipped-{kind}")
            continue

        message = entry.get("message") or {}
        role = message.get("role")
        entry_id = entry["id"]
        timestamp = _entry_ms(entry)

        if role == "system":
            bump("skipped-system")
            continue
        if role == "toolResult":
            # Represented by the owning tool part's state.
            consumed.add(message.get("toolCallId") or "")
            continue
        if role not in {"user", "assistant"}:
            bump(f"skipped-role-{role}")
            continue

        message_id = ids.next(KILO_MSG_PREFIX, timestamp, f"{pi_session_id}:{entry_id}")

        if role == "user":
            content = message.get("content")
            blocks = content if isinstance(content, list) else [{"type": "text", "text": content or ""}]
            parts: list[dict] = []
            for index, block in enumerate(blocks):
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "text" and block.get("text"):
                    parts.append(
                        {
                            "id": ids.next(KILO_PART_PREFIX, timestamp, f"{entry_id}:text:{index}"),
                            "sessionID": session_id,
                            "messageID": message_id,
                            "type": "text",
                            "text": block["text"],
                        }
                    )
                    bump("text")
                elif block.get("type") == "image":
                    parts.append(
                        _image_part(
                            ids,
                            session_id=session_id,
                            message_id=message_id,
                            timestamp=timestamp,
                            entry_id=entry_id,
                            index=index,
                            block=block,
                        )
                    )
                    bump("image")
                else:
                    bump(f"skipped-content-{block.get('type')}")
            if not parts:
                bump("skipped-empty-user")
                continue
            model = _model_for_user(chain, position, default_model)
            messages.append(
                {
                    "info": {
                        "id": message_id,
                        "sessionID": session_id,
                        "role": "user",
                        "time": {"created": timestamp},
                        "agent": "pi",
                        "model": model,
                    },
                    "parts": parts,
                }
            )
            last_user_id = message_id
            bump("user")
            continue

        # Assistant
        content = message.get("content")
        blocks = content if isinstance(content, list) else []
        parts = []
        for index, block in enumerate(blocks):
            if not isinstance(block, dict):
                continue
            block_type = block.get("type")
            if block_type == "text" and block.get("text"):
                parts.append(
                    {
                        "id": ids.next(KILO_PART_PREFIX, timestamp, f"{entry_id}:text:{index}"),
                        "sessionID": session_id,
                        "messageID": message_id,
                        "type": "text",
                        "text": block["text"],
                    }
                )
                bump("text")
            elif block_type == "thinking" and block.get("thinking"):
                parts.append(
                    {
                        "id": ids.next(KILO_PART_PREFIX, timestamp, f"{entry_id}:thinking:{index}"),
                        "sessionID": session_id,
                        "messageID": message_id,
                        "type": "reasoning",
                        "text": block["thinking"],
                        "time": {"start": timestamp},
                    }
                )
                bump("thinking")
            elif block_type == "toolCall":
                call_id = block.get("id") or ""
                result = tool_results.get(call_id)
                parts.append(
                    _tool_part(
                        ids,
                        session_id=session_id,
                        message_id=message_id,
                        timestamp=timestamp,
                        entry_id=entry_id,
                        index=index,
                        call=block,
                        result=result,
                    )
                )
                bump("tool")
            else:
                bump(f"skipped-content-{block_type}")

        if not parts:
            bump("skipped-empty-assistant")
            continue

        usage = message.get("usage") or {}
        cost = (usage.get("cost") or {}).get("total")
        if cost is None:
            cost = 0.0
        tokens = {
            "input": usage.get("input") or 0,
            "output": usage.get("output") or 0,
            "reasoning": usage.get("reasoning") or 0,
            "cache": {
                "read": usage.get("cacheRead") or 0,
                "write": usage.get("cacheWrite") or 0,
            },
        }
        if usage.get("totalTokens"):
            tokens["total"] = usage["totalTokens"]
        stop = message.get("stopReason")
        finish = {
            "toolUse": "tool-calls",
            "stop": "stop",
            "length": "length",
            "error": "error",
            "aborted": "aborted",
        }.get(stop or "stop", "stop")
        provider = message.get("provider") or default_model["providerID"]
        model = message.get("model") or default_model["modelID"]
        messages.append(
            {
                "info": {
                    "id": message_id,
                    "sessionID": session_id,
                    "role": "assistant",
                    "time": {"created": timestamp, "completed": timestamp},
                    "parentID": last_user_id or "",
                    "modelID": model,
                    "providerID": provider,
                    "mode": "pi",
                    "agent": "pi",
                    "path": {"cwd": directory, "root": directory},
                    "cost": float(cost),
                    "tokens": tokens,
                    "finish": finish,
                },
                "parts": parts,
            }
        )
        bump("assistant")

    # A tool result with no matching call is a Pi-side artifact; report it.
    unmatched = 0
    for call_id in tool_results:
        if call_id and call_id not in consumed:
            unmatched += 1
    if unmatched:
        stats["unmatched-tool-results"] = unmatched

    stats["messages"] = len(messages)
    return {"info": info, "messages": messages}, stats


# ---------- local Kilo import -------------------------------------------------


def kilo_bin() -> str:
    candidates = [
        os.environ.get("KILO_BIN"),
        shutil.which("kilo"),
        "/home/linuxbrew/.linuxbrew/bin/kilo",
        "/opt/homebrew/bin/kilo",
        "/usr/local/bin/kilo",
        str(Path.home() / ".local" / "bin" / "kilo"),
    ]
    for candidate in candidates:
        if candidate and os.access(candidate, os.X_OK):
            return candidate
    sys.exit("error: kilo not found; set KILO_BIN or put kilo on PATH")


def kilo_version(kilo: str) -> str:
    try:
        result = subprocess.run(
            [kilo, "--version"], capture_output=True, text=True, timeout=20, check=False
        )
    except (OSError, subprocess.TimeoutExpired):
        return "0.0.0"
    match = re.search(r"\d+\.\d+\.\d+", result.stdout or "")
    return match.group(0) if match else "0.0.0"


def kilo_db_path() -> Path:
    if os.environ.get("KILO_DB"):
        return Path(os.environ["KILO_DB"]).expanduser()
    data_home = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
    return data_home / "kilo" / "kilo.db"


def local_session_exists(session_id: str, db_path: Path | None = None) -> bool:
    path = db_path or kilo_db_path()
    if not path.is_file():
        return False
    try:
        connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        try:
            row = connection.execute(
                "select 1 from session where id = ?", (session_id,)
            ).fetchone()
            return row is not None
        finally:
            connection.close()
    except sqlite3.Error:
        return False


def local_session_shared(session_id: str, db_path: Path | None = None) -> bool:
    path = db_path or kilo_db_path()
    storage_root = Path(
        os.environ.get("KILO_STORAGE_DIR") or path.parent / "storage"
    )
    if (storage_root / "session_share" / f"{session_id}.json").is_file():
        return True
    if not path.is_file():
        return False
    try:
        connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        try:
            row = connection.execute(
                "select share_url from session where id = ?", (session_id,)
            ).fetchone()
            return bool(row and row[0])
        finally:
            connection.close()
    except sqlite3.Error:
        return False


def write_export(export: dict, out_dir: Path, session_id: str) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{session_id}.json"
    with path.open("w", encoding="utf-8") as handle:
        json.dump(export, handle, ensure_ascii=False, indent=2)
    return path


def run_kilo_import(export_path: Path, cwd: str, kilo: str) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    # Local-only: suppress KiloSessions.bootstrap/share/remote for this process.
    env["KILO_DISABLE_SESSION_INGEST"] = "1"
    env["KILO_DISABLE_SHARE"] = "1"
    return subprocess.run(
        [kilo, "import", str(export_path)],
        cwd=cwd,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def run_kilo_delete(session_id: str, cwd: str, kilo: str) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["KILO_DISABLE_SESSION_INGEST"] = "1"
    env["KILO_DISABLE_SHARE"] = "1"
    return subprocess.run(
        [kilo, "session", "delete", session_id],
        cwd=cwd,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


# ---------- publish (opt-in, history only) -----------------------------------


def read_local_session(db_path: Path, session_id: str) -> dict:
    connection = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        row = connection.execute(
            "select * from session where id = ?", (session_id,)
        ).fetchone()
        if row is None:
            raise KeyError(f"Kilo session not found locally: {session_id}")
        info = {
            "id": row["id"],
            "projectID": row["project_id"],
            "slug": row["slug"],
            "directory": row["directory"],
            "title": row["title"],
            "version": row["version"],
            "time": {"created": row["time_created"], "updated": row["time_updated"]},
            "cost": row["cost"],
            "tokens": {
                "input": row["tokens_input"],
                "output": row["tokens_output"],
                "reasoning": row["tokens_reasoning"],
                "cache": {
                    "read": row["tokens_cache_read"],
                    "write": row["tokens_cache_write"],
                },
            },
        }
        for column, key in (("path", "path"), ("agent", "agent"), ("parent_id", "parentID")):
            if row[column]:
                info[key] = row[column]
        if row["metadata"]:
            info["metadata"] = json.loads(row["metadata"])
        if row["model"]:
            info["model"] = json.loads(row["model"])
        if row["share_url"]:
            info["share"] = {"url": row["share_url"]}

        messages = []
        for message_row in connection.execute(
            "select id, data from message where session_id = ? order by time_created, id",
            (session_id,),
        ):
            message = json.loads(message_row["data"])
            message.setdefault("id", message_row["id"])
            message.setdefault("sessionID", session_id)
            parts = []
            for part_row in connection.execute(
                "select id, data from part where message_id = ? order by time_created, id",
                (message_row["id"],),
            ):
                part = json.loads(part_row["data"])
                part.setdefault("id", part_row["id"])
                part.setdefault("messageID", message_row["id"])
                part.setdefault("sessionID", session_id)
                parts.append(part)
            messages.append({"info": message, "parts": parts})
        return {"info": info, "messages": messages}
    finally:
        connection.close()


def imported_sessions(db_path: Path) -> list[str]:
    if not db_path.is_file():
        return []
    connection = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        found = []
        for session_id, metadata in connection.execute(
            "select id, metadata from session where metadata is not null"
        ):
            try:
                parsed = json.loads(metadata)
            except (TypeError, ValueError):
                continue
            if isinstance(parsed, dict) and isinstance(parsed.get("pi"), dict):
                found.append(session_id)
        return found
    finally:
        connection.close()


def build_publish_items(export: dict, *, platform: str = "cli") -> list[dict]:
    info = export["info"]
    items: list[dict] = [
        {"type": "kilo_meta", "data": {"platform": platform}},
        {"type": "session", "data": info},
    ]
    for message in export["messages"]:
        items.append({"type": "message", "data": message["info"]})
        items.extend({"type": "part", "data": part} for part in message["parts"])
    items.append({"type": "session_status", "data": {"status": "idle"}})
    return items


def chunk_items(items: list[dict]) -> list[list[dict]]:
    chunks: list[list[dict]] = []
    current: list[dict] = []
    current_bytes = 0
    for item in items:
        size = len(json.dumps(item, separators=(",", ":")).encode("utf-8"))
        if current and (
            len(current) >= INGEST_CHUNK_MAX_ITEMS
            or current_bytes + size > INGEST_CHUNK_MAX_BYTES
        ):
            chunks.append(current)
            current = []
            current_bytes = 0
        current.append(item)
        current_bytes += size
    if current:
        chunks.append(current)
    return chunks


def _kilo_auth(auth_file: str | None = None, ingest: str | None = None) -> tuple[str, str]:
    # Imported lazily to avoid a circular import with kilo_import's dispatcher.
    from kilo_import import DEFAULT_AUTH, DEFAULT_INGEST, read_kilo_token

    token = read_kilo_token(Path(auth_file or DEFAULT_AUTH).expanduser())
    return token, ingest or DEFAULT_INGEST


def _post_json(url: str, body: dict, token: str) -> dict:
    request = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "opencode-kilo-provider",
            "X-KILOCODE-EDITORNAME": "Kilo CLI",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.load(response)
    except urllib.error.HTTPError as err:
        detail = err.read().decode("utf-8", "replace")[:500]
        raise RuntimeError(f"HTTP {err.code}: {detail}") from err
    except (urllib.error.URLError, TimeoutError) as err:
        raise RuntimeError(f"cannot reach {url}: {err}") from err


def publish_session(export: dict, *, token: str, ingest: str, post: bool) -> dict:
    session_id = export["info"]["id"]
    items = build_publish_items(export)
    chunks = chunk_items(items)
    plan = {
        "sessionID": session_id,
        "items": len(items),
        "chunks": len(chunks),
        "bytes": sum(
            len(json.dumps(item, separators=(",", ":")).encode("utf-8"))
            for item in items
        ),
        "posted": False,
    }
    if not post:
        return plan

    base = ingest.rstrip("/")
    _post_json(f"{base}/api/session", {"sessionId": session_id}, token)
    ingest_path = f"{base}/api/session/{session_id}/ingest"
    for index, chunk in enumerate(chunks, start=1):
        result = _post_json(f"{ingest_path}?v=2", {"data": chunk}, token)
        if result.get("success") is False:
            raise RuntimeError(f"ingest chunk {index} rejected: {result}")
    plan["posted"] = True
    plan["shareUrl"] = f"https://app.kilo.ai/cloud/sessions/{session_id}"
    return plan


# ---------- commands ----------------------------------------------------------


def cmd_import(args: argparse.Namespace) -> int:
    sessions = discover_sessions()
    if not sessions:
        print(f"No Pi sessions found under {pi_sessions_root()}", file=sys.stderr)
        return 1
    selected = select_sessions(sessions, args.session, args.cwd)
    if not selected:
        print("No Pi sessions matched the filter.", file=sys.stderr)
        return 1

    kilo = None if args.dry_run else kilo_bin()
    version = "0.0.0" if args.dry_run else kilo_version(kilo or "")
    db_path = Path(args.db).expanduser() if args.db else kilo_db_path()
    out_dir = Path(args.out).expanduser() if args.out else Path(tempfile.mkdtemp(prefix="pi-kilo-"))
    ok = 0
    skipped = 0
    failed = 0
    for item in selected:
        try:
            export, stats = convert_session(
                item["path"], cwd=item.get("cwd"), kilo_version=version
            )
        except Exception as err:  # noqa: BLE001 - per-source isolation
            print(f"FAIL {item['path']}: {err}", file=sys.stderr)
            failed += 1
            continue

        session_id = export["info"]["id"]
        if not export["messages"]:
            print(f"SKIP {item['path']}: no importable messages")
            skipped += 1
            continue
        target_cwd = export["info"]["directory"]
        if not Path(target_cwd).is_dir():
            fallback = str(Path.cwd())
            print(
                f"WARN {item['path']}: recorded cwd {target_cwd!r} is missing; "
                f"importing into {fallback!r}",
                file=sys.stderr,
            )
            export, stats = convert_session(
                item["path"], cwd=fallback, kilo_version=version
            )
            target_cwd = fallback
        label = f"{export['info']['title']} ({session_id})"
        exists = local_session_exists(session_id, db_path)
        if exists and not args.replace:
            print(f"SKIP {label}: already in Kilo (use --replace to re-import)")
            skipped += 1
            continue
        if exists and args.replace:
            if local_session_shared(session_id, db_path):
                print(
                    f"FAIL {label}: local session is shared/published; "
                    "unshare it before --replace",
                    file=sys.stderr,
                )
                failed += 1
                continue
            deleted = run_kilo_delete(session_id, target_cwd, kilo or "")
            if deleted.returncode != 0:
                print(f"FAIL {label}: could not delete old local session", file=sys.stderr)
                failed += 1
                continue

        export_path = write_export(export, out_dir, session_id)
        if args.dry_run:
            print(
                f"DRY  {label} -> {export_path} "
                f"({stats.get('user', 0)} user, {stats.get('assistant', 0)} assistant, "
                f"{stats.get('tool', 0)} tool)"
            )
            ok += 1
            continue

        result = run_kilo_import(export_path, target_cwd, kilo or "")
        if result.returncode != 0:
            print(f"FAIL {label}", file=sys.stderr)
            detail = (result.stderr or result.stdout or "").strip()
            if detail:
                print(detail, file=sys.stderr)
            failed += 1
            continue
        print(
            f"OK   {label} "
            f"({stats.get('user', 0)} user, {stats.get('assistant', 0)} assistant, "
            f"{stats.get('tool', 0)} tool) -> local only"
        )
        ok += 1

    print(
        f"\nImported {ok}, skipped {skipped}, failed {failed}. "
        "Nothing was sent to Kilo Cloud."
    )
    return 0 if failed == 0 else 1


def cmd_publish(args: argparse.Namespace) -> int:
    db_path = Path(args.db).expanduser() if args.db else kilo_db_path()
    if args.list:
        found = imported_sessions(db_path)
        if not found:
            print("No Pi-imported Kilo sessions found in the local DB.", file=sys.stderr)
            return 1
        for session_id in found:
            try:
                export = read_local_session(db_path, session_id)
                print(f"{session_id}  {export['info']['title']}")
            except (KeyError, sqlite3.Error) as err:
                print(f"{session_id}  (unreadable: {err})")
        return 0

    if not args.sessions:
        print("error: pass one or more Kilo session ids, or --list", file=sys.stderr)
        return 2

    if args.post:
        token, ingest = _kilo_auth(args.auth_file, args.ingest)
    else:
        token, ingest = "", os.environ.get(
            "KILO_SESSION_INGEST_URL", "https://ingest.kilosessions.ai"
        )
    failed = 0
    for session_id in args.sessions:
        try:
            export = read_local_session(db_path, session_id)
        except (KeyError, sqlite3.Error) as err:
            print(f"FAIL {session_id}: {err}", file=sys.stderr)
            failed += 1
            continue
        try:
            plan = publish_session(export, token=token, ingest=ingest, post=args.post)
        except RuntimeError as err:
            print(f"FAIL {session_id}: {err}", file=sys.stderr)
            failed += 1
            continue
        verb = "PUBLISHED" if plan["posted"] else "WOULD PUBLISH"
        print(
            f"{verb} {session_id}: {plan['items']} items in {plan['chunks']} chunk(s), "
            f"{plan['bytes']} bytes"
        )
        if plan.get("shareUrl"):
            print(f"  {plan['shareUrl']}")
    if not args.post:
        print("\nNothing was uploaded. Re-run with --post to publish history.")
    return 0 if failed == 0 else 1


def main(argv: list[str] | None = None) -> int:
    raw = list(sys.argv[1:] if argv is None else argv)
    parser = argparse.ArgumentParser(
        prog="pi-kilo",
        description="Make Pi sessions available in Kilo (local by default)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    imp = sub.add_parser(
        "import",
        help="convert Pi sessions and import them into Kilo's local store",
    )
    imp.add_argument("--all", action="store_true", help="import every discovered session (default)")
    imp.add_argument("--session", help="Pi session id, id prefix, or path")
    imp.add_argument("--cwd", help="only sessions recorded for this project directory")
    imp.add_argument("--replace", action="store_true", help="re-import an existing local session (refused if published)")
    imp.add_argument("--dry-run", action="store_true", help="write export JSON but do not run kilo import")
    imp.add_argument("--out", help="directory for generated Kilo export JSON")
    imp.add_argument("--db", help=f"Kilo SQLite path (default: {kilo_db_path()})")
    imp.set_defaults(func=cmd_import)

    pub = sub.add_parser(
        "publish",
        help="upload imported history to Kilo Cloud (opt-in, history only)",
    )
    pub.add_argument("sessions", nargs="*", help="Kilo session ids to publish")
    pub.add_argument("--list", action="store_true", help="list locally imported Pi sessions")
    pub.add_argument("--post", action="store_true", help="actually upload; without it, print the plan")
    pub.add_argument("--db", help=f"Kilo SQLite path (default: {kilo_db_path()})")
    pub.add_argument("--auth-file", help="Kilo auth.json (default: ~/.local/share/kilo/auth.json)")
    pub.add_argument("--ingest", help="Kilo session ingest base URL")
    pub.set_defaults(func=cmd_publish)

    args = parser.parse_args(raw)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
