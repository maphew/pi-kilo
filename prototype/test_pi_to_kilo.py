#!/usr/bin/env python3
"""Tests for the Pi -> Kilo converter and local-import planner (offline)."""
import json
import os
import sys
import tempfile
import unittest
import contextlib
import io
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import pi_to_kilo as p2k  # noqa: E402


def entry(kind, eid, parent, timestamp, **fields):
    base = {"type": kind, "id": eid, "parentId": parent, "timestamp": timestamp}
    base.update(fields)
    return base


def message(eid, parent, timestamp_ms, role, content, **fields):
    return entry(
        "message",
        eid,
        parent,
        "2026-10-20T10:00:00.000Z",
        message={"role": role, "content": content, "timestamp": timestamp_ms, **fields},
    )


def write_session(path: Path, cwd: str, entries: list[dict], session_id="pi-session-1"):
    header = {
        "type": "session",
        "version": 3,
        "id": session_id,
        "timestamp": "2026-10-20T10:00:00.000Z",
        "cwd": cwd,
    }
    path.write_text("\n".join(json.dumps(item) for item in [header, *entries]))


class ConvertTests(unittest.TestCase):
    def convert(self, entries, cwd="/tmp/project"):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "session.jsonl"
            write_session(path, cwd, entries)
            return p2k.convert_session(path)

    def test_basic_conversion(self):
        export, stats = self.convert(
            [
                entry("session_info", "e1", None, "2026-10-20T10:00:00.500Z", name="Named"),
                message("e2", "e1", 1000, "user", "hello"),
                message(
                    "e3",
                    "e2",
                    2000,
                    "assistant",
                    [
                        {"type": "thinking", "thinking": "think"},
                        {"type": "text", "text": "hi"},
                        {"type": "toolCall", "id": "call_1", "name": "bash", "arguments": {"command": "echo hi"}},
                    ],
                    provider="kilo",
                    model="kilo-auto/efficient",
                    usage={
                        "input": 10,
                        "output": 5,
                        "reasoning": 1,
                        "cacheRead": 2,
                        "cacheWrite": 0,
                        "totalTokens": 18,
                        "cost": {"total": 0.03},
                    },
                    stopReason="toolUse",
                ),
                message(
                    "e4",
                    "e3",
                    3000,
                    "toolResult",
                    [{"type": "text", "text": "hi\n"}],
                    toolCallId="call_1",
                    toolName="bash",
                    isError=False,
                ),
                message("e5", "e4", 4000, "assistant", [{"type": "text", "text": "done"}], stopReason="stop"),
            ]
        )

        info = export["info"]
        self.assertTrue(info["id"].startswith("ses_"))
        self.assertEqual(len(info["id"]), 30)
        self.assertEqual(info["title"], "Named")
        self.assertEqual(info["directory"], "/tmp/project")
        self.assertEqual(info["metadata"]["pi"]["sessionId"], "pi-session-1")

        self.assertEqual([m["info"]["role"] for m in export["messages"]], ["user", "assistant", "assistant"])
        user, assistant, final = export["messages"]
        self.assertEqual(user["parts"][0]["text"], "hello")
        self.assertEqual(user["info"]["model"], {"providerID": "kilo", "modelID": "kilo-auto/efficient"})
        self.assertEqual(assistant["info"]["parentID"], user["info"]["id"])
        self.assertEqual([part["type"] for part in assistant["parts"]], ["reasoning", "text", "tool"])
        tool = assistant["parts"][2]
        self.assertEqual(tool["state"]["status"], "completed")
        self.assertEqual(tool["state"]["output"], "hi\n")
        self.assertEqual(assistant["info"]["tokens"]["input"], 10)
        self.assertEqual(assistant["info"]["tokens"]["cache"]["read"], 2)
        self.assertEqual(assistant["info"]["cost"], 0.03)
        self.assertEqual(assistant["info"]["finish"], "tool-calls")
        self.assertEqual(final["info"]["finish"], "stop")
        self.assertEqual(stats["user"], 1)
        self.assertEqual(stats["assistant"], 2)
        self.assertEqual(stats["tool"], 1)

    def test_tool_without_result_is_error(self):
        export, _ = self.convert(
            [
                message("e1", None, 1000, "user", "run"),
                message(
                    "e2",
                    "e1",
                    2000,
                    "assistant",
                    [{"type": "toolCall", "id": "call_x", "name": "bash", "arguments": {"command": "sleep"}}],
                ),
            ]
        )
        tool = export["messages"][1]["parts"][0]
        self.assertEqual(tool["state"]["status"], "error")

    def test_failed_tool_result(self):
        export, _ = self.convert(
            [
                message("e1", None, 1000, "user", "run"),
                message(
                    "e2",
                    "e1",
                    2000,
                    "assistant",
                    [{"type": "toolCall", "id": "call_x", "name": "bash", "arguments": {"command": "false"}}],
                ),
                message(
                    "e3",
                    "e2",
                    3000,
                    "toolResult",
                    [{"type": "text", "text": "boom"}],
                    toolCallId="call_x",
                    toolName="bash",
                    isError=True,
                ),
            ]
        )
        tool = export["messages"][1]["parts"][0]
        self.assertEqual(tool["state"]["status"], "error")
        self.assertEqual(tool["state"]["error"], "boom")

    def test_active_leaf_skips_abandoned_branch(self):
        export, _ = self.convert(
            [
                message("e1", None, 1000, "user", "first"),
                message("e2", "e1", 2000, "assistant", [{"type": "text", "text": "a1"}]),
                message("e3", "e2", 3000, "user", "abandoned"),
                message("e4", "e3", 4000, "assistant", [{"type": "text", "text": "a2"}]),
                message("e5", "e1", 5000, "assistant", [{"type": "text", "text": "a1b"}]),
            ]
        )
        texts = [m["parts"][0]["text"] for m in export["messages"]]
        self.assertEqual(texts, ["first", "a1b"])
        self.assertEqual(export["info"]["title"], "first")

    def test_skips_system_compaction_and_custom(self):
        export, stats = self.convert(
            [
                message("e1", None, 1000, "system", ""),
                message("e2", "e1", 2000, "user", "hello"),
                entry(
                    "compaction",
                    "e3",
                    "e2",
                    "2026-10-20T10:00:02.000Z",
                    summary="old stuff",
                    firstKeptEntryId="e2",
                ),
                entry("custom", "e4", "e3", "2026-10-20T10:00:03.000Z", customType="x", data={}),
                message("e5", "e4", 4000, "assistant", [{"type": "text", "text": "ok"}]),
            ]
        )
        self.assertEqual([m["info"]["role"] for m in export["messages"]], ["user", "assistant"])
        self.assertEqual(stats["skipped-system"], 1)
        self.assertEqual(stats["skipped-compaction"], 1)
        self.assertEqual(stats["skipped-custom"], 1)

    def test_image_content(self):
        export, _ = self.convert(
            [
                message(
                    "e1",
                    None,
                    1000,
                    "user",
                    [
                        {"type": "text", "text": "look"},
                        {"type": "image", "data": "AAAA", "mimeType": "image/png"},
                    ],
                )
            ]
        )
        kinds = [part["type"] for part in export["messages"][0]["parts"]]
        self.assertEqual(kinds, ["text", "file"])
        image = export["messages"][0]["parts"][1]
        self.assertEqual(image["url"], "data:image/png;base64,AAAA")

    def test_ids_are_deterministic(self):
        entries = [
            message("e1", None, 1000, "user", "hello"),
            message("e2", "e1", 2000, "assistant", [{"type": "text", "text": "hi"}]),
        ]
        first, _ = self.convert(entries)
        second, _ = self.convert(entries)
        self.assertEqual(first["info"]["id"], second["info"]["id"])
        self.assertEqual(
            [m["info"]["id"] for m in first["messages"]],
            [m["info"]["id"] for m in second["messages"]],
        )
        self.assertEqual(
            [part["id"] for m in first["messages"] for part in m["parts"]],
            [part["id"] for m in second["messages"] for part in m["parts"]],
        )

    def test_ids_sort_in_transcript_order(self):
        generator = p2k.IdGen()
        message_ids = []
        part_ids = []
        for index in range(3):
            timestamp = 1000 + index
            message_ids.append(generator.next(p2k.KILO_MSG_PREFIX, timestamp, f"m{index}"))
            part_ids.append(generator.next(p2k.KILO_PART_PREFIX, timestamp, f"p{index}"))
        self.assertEqual(message_ids, sorted(message_ids))
        self.assertEqual(part_ids, sorted(part_ids))
        # Kilo sorts messages and parts as separate streams; ids only need to
        # order within each stream.
        self.assertTrue(all(a.startswith("msg_") for a in message_ids))
        self.assertTrue(all(a.startswith("prt_") for a in part_ids))

    def test_updated_is_not_before_created(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "s.jsonl"
            header = {
                "type": "session",
                "version": 3,
                "id": "x",
                "timestamp": "2026-10-20T10:00:00.000Z",
                "cwd": "/tmp/p",
            }
            path.write_text(json.dumps(header) + "\n")
            export, _ = p2k.convert_session(path)
        self.assertGreaterEqual(export["info"]["time"]["updated"], export["info"]["time"]["created"])


class DiscoveryTests(unittest.TestCase):
    def test_select_by_id_prefix_and_cwd(self):
        sessions = [
            {"path": Path("/a/one.jsonl"), "id": "abcdef", "cwd": "/work/a"},
            {"path": Path("/b/two.jsonl"), "id": "123456", "cwd": "/work/b"},
        ]
        self.assertEqual([s["id"] for s in p2k.select_sessions(sessions, "abc", None)], ["abcdef"])
        self.assertEqual([s["id"] for s in p2k.select_sessions(sessions, None, "/work/b")], ["123456"])

    def test_dry_run_writes_exports(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "sessions" / "--work-project--"
            root.mkdir(parents=True)
            project = Path(tmp) / "project"
            project.mkdir()
            write_session(
                root / "2026-10-20T10-00-00_test.jsonl",
                str(project),
                [
                    message("e1", None, 1000, "user", "hello"),
                    message("e2", "e1", 2000, "assistant", [{"type": "text", "text": "hi"}]),
                ],
            )
            out = Path(tmp) / "out"
            old = os.environ.get("PI_SESSIONS_DIR")
            os.environ["PI_SESSIONS_DIR"] = str(Path(tmp) / "sessions")
            try:
                with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                    code = p2k.main(["import", "--all", "--dry-run", "--out", str(out)])
            finally:
                if old is None:
                    os.environ.pop("PI_SESSIONS_DIR", None)
                else:
                    os.environ["PI_SESSIONS_DIR"] = old
            self.assertEqual(code, 0)
            files = list(out.glob("ses_*.json"))
            self.assertEqual(len(files), 1)
            export = json.loads(files[0].read_text())
            self.assertEqual(export["info"]["directory"], str(project))


class PublishPayloadTests(unittest.TestCase):
    def test_build_items_order(self):
        export = {
            "info": {"id": "ses_x", "title": "t"},
            "messages": [
                {"info": {"id": "msg_1", "role": "user"}, "parts": [{"id": "prt_1"}]},
                {"info": {"id": "msg_2", "role": "assistant"}, "parts": [{"id": "prt_2"}, {"id": "prt_3"}]},
            ],
        }
        items = p2k.build_publish_items(export)
        self.assertEqual(
            [item["type"] for item in items],
            ["kilo_meta", "session", "message", "part", "message", "part", "part", "session_status"],
        )

    def test_chunks_respect_item_limit(self):
        items = [{"type": "part", "data": {"id": f"prt_{index}"}} for index in range(300)]
        chunks = p2k.chunk_items(items)
        self.assertEqual(sum(len(chunk) for chunk in chunks), 300)
        self.assertTrue(all(len(chunk) <= p2k.INGEST_CHUNK_MAX_ITEMS for chunk in chunks))
        self.assertEqual([len(chunk) for chunk in chunks], [128, 128, 44])


if __name__ == "__main__":
    unittest.main()
