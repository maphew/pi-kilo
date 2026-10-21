#!/usr/bin/env python3
"""Tests for the Kilo -> Pi session converter (no network, no credentials)."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import kilo_import as ki  # noqa: E402


def part(pid, ptype, **fields):
    base = {"id": pid, "messageID": "m1", "sessionID": "ses_test", "type": ptype}
    base.update(fields)
    return base


def message(mid, role, parts, created=1_700_000_000_000, **info):
    base = {
        "id": mid,
        "sessionID": "ses_test",
        "role": role,
        "time": {"created": created},
    }
    base.update(info)
    return {"info": base, "parts": parts}


def sample_export():
    return {
        "info": {
            "id": "ses_test",
            "title": "Test session",
            "directory": "/work/project",
            "model": {"id": "kilo-auto/efficient", "providerID": "kilo"},
            "time": {"created": 1_700_000_000_000},
        },
        "messages": [
            # Deliberately out of transcript order: the converter sorts by id.
            message(
                "msg_b",
                "assistant",
                [
                    part("p1", "reasoning", text="think"),
                    part("p2", "text", text="done"),
                    part(
                        "p3",
                        "tool",
                        tool="bash",
                        callID="call_1",
                        state={
                            "status": "completed",
                            "input": {"command": "true"},
                            "output": "ok",
                            "time": {"end": 1_700_000_002_000},
                        },
                    ),
                    part(
                        "p4",
                        "step-finish",
                        cost=0.5,
                        tokens={
                            "input": 10,
                            "output": 2,
                            "reasoning": 1,
                            "total": 12,
                            "cache": {"read": 3, "write": 4},
                        },
                    ),
                ],
                finish="tool-calls",
                modelID="meta/model",
                providerID="kilo",
            ),
            message(
                "msg_a",
                "user",
                [part("u1", "text", text="hello")],
                created=1_699_999_999_000,
            ),
        ],
    }


class ConvertTest(unittest.TestCase):
    def test_maps_messages_tools_and_results(self):
        entries, stats = ki.convert_export(sample_export(), "/work/project", "ses_test")
        self.assertEqual(entries[0]["type"], "session")
        self.assertEqual(entries[0]["version"], 3)
        self.assertEqual(entries[0]["cwd"], "/work/project")
        self.assertEqual(entries[1]["customType"], "kilo_import")
        self.assertEqual(entries[1]["data"]["sessionId"], "ses_test")

        messages = [e for e in entries if e["type"] == "message"]
        self.assertEqual([m["message"]["role"] for m in messages],
                         ["user", "assistant", "toolResult"])
        self.assertEqual(messages[0]["message"]["content"], "hello")
        assistant = messages[1]["message"]
        self.assertEqual([c["type"] for c in assistant["content"]],
                         ["thinking", "text", "toolCall"])
        self.assertEqual(assistant["stopReason"], "toolUse")
        self.assertEqual(assistant["model"], "meta/model")
        self.assertEqual(assistant["usage"]["input"], 10)
        self.assertEqual(assistant["usage"]["cacheRead"], 3)
        self.assertEqual(assistant["usage"]["cost"]["total"], 0.5)
        result = messages[2]["message"]
        self.assertEqual(result["role"], "toolResult")
        self.assertEqual(result["toolCallId"], "call_1")
        self.assertFalse(result["isError"])
        self.assertEqual(result["content"][0]["text"], "ok")
        self.assertEqual(stats["user"], 1)
        self.assertEqual(stats["assistant"], 1)
        self.assertEqual(stats["toolResult"], 1)

    def test_parent_chain_is_linear(self):
        entries, _ = ki.convert_export(sample_export(), "/work/project", "ses_test")
        previous = None
        for entry in entries[1:]:  # skip header
            if previous is not None:
                self.assertEqual(entry["parentId"], previous, entry)
            previous = entry["id"]

    def test_incomplete_tool_becomes_error_result(self):
        export = sample_export()
        export["messages"][0]["parts"][2]["state"] = {
            "status": "error",
            "input": {"command": "false"},
            "error": "exit 1",
        }
        entries, _ = ki.convert_export(export, "/work/project", "ses_test")
        result = [e for e in entries if e["type"] == "message"][-1]["message"]
        self.assertTrue(result["isError"])
        self.assertEqual(result["content"][0]["text"], "exit 1")

    def test_images_and_multiple_texts(self):
        export = sample_export()
        export["messages"][1]["parts"] = [
            part("u1", "text", text="one"),
            part("u2", "text", text="two"),
            part("u3", "file", url="data:image/png;base64,QUJD", mime="image/png"),
        ]
        entries, _ = ki.convert_export(export, "/work/project", "ses_test")
        content = [e for e in entries if e["type"] == "message"][0]["message"]["content"]
        self.assertEqual(
            content,
            [
                {"type": "text", "text": "one"},
                {"type": "text", "text": "two"},
                {"type": "image", "data": "QUJD", "mimeType": "image/png"},
            ],
        )

    def test_skips_unknown_parts_and_empty_messages(self):
        export = sample_export()
        export["messages"][0]["parts"] = [part("p1", "step-start")]
        entries, stats = ki.convert_export(export, "/work/project", "ses_test")
        self.assertEqual(
            [e["message"]["role"] for e in entries if e["type"] == "message"],
            ["user"],
        )
        self.assertEqual(stats["skipped-step-start"], 1)


class PlacementTest(unittest.TestCase):
    def test_export_url(self):
        self.assertEqual(
            ki.export_url("https://ingest.example", "ses_abc"),
            "https://ingest.example/api/session/ses_abc/export",
        )
        self.assertEqual(
            ki.export_url("https://ingest.example/", "3fa85f64-5717-4562-b3fc-2c963f66afa6"),
            "https://ingest.example/session/3fa85f64-5717-4562-b3fc-2c963f66afa6",
        )

    def test_writes_into_pi_session_dir(self):
        entries, _ = ki.convert_export(sample_export(), "/work/project", "ses_test")
        with tempfile.TemporaryDirectory() as tmp:
            import os

            old = os.environ.get("PI_CODING_AGENT_DIR")
            os.environ["PI_CODING_AGENT_DIR"] = tmp
            try:
                out = ki.write_session(entries, "/work/project", None)
            finally:
                if old is None:
                    del os.environ["PI_CODING_AGENT_DIR"]
                else:
                    os.environ["PI_CODING_AGENT_DIR"] = old
            self.assertEqual(out.parent.name, "--work-project--")
            self.assertTrue(out.name.endswith(f"_{entries[0]['id']}.jsonl"))
            lines = out.read_text().splitlines()
            self.assertEqual(json.loads(lines[0])["type"], "session")
            self.assertEqual(len(lines), len(entries))


if __name__ == "__main__":
    unittest.main()
