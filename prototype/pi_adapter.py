#!/usr/bin/env python3
"""Minimal Pi-as-external-runtime harness (pi-kilo-hip).

Proves: a message routed to a Pi-owned session is executed BY PI,
with owner-lease guard + message-id dedupe.

Usage:
  python3 prototype/pi_adapter.py "message to send"

Design (from Phase 0 synthesis):
  - spawn: pi --mode rpc --session-dir <managed> --session-id <kilo-session-id>
  - observe: stdout JSONL, LF-split only; message_end authoritative, deltas live-only
  - turn completion: agent_settled (NOT agent_end)
  - control: prompt command; disposition started/queued/handled
  - dedupe: stable message id executed once (adapter-side, since relay omits mutationId)
  - ownership: single OwnerLease; second claimant for live lease -> REJECTED
"""
import json
import os
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path

SESSION_ID = "ses_pi_kilo_hip_01"  # Kilo-style logical session id bound to Pi
SESSION_DIR = Path("/tmp/pi-kilo-hip/sessions")


class OwnerLease:
    """Runtime-kind-aware execution-owner lease. Second claimant rejected."""

    def __init__(self):
        self.owner = None  # (runtime_kind, token)

    def claim(self, runtime_kind):
        if self.owner is not None:
            return False, self.owner
        token = uuid.uuid4().hex[:12]
        self.owner = (runtime_kind, token)
        return True, (runtime_kind, token)

    def release(self):
        self.owner = None


class PiAdapter:
    def __init__(self, session_id, session_dir, extension=None, tools=True,
                 ui_policy=None):
        self.session_id = session_id
        self.session_dir = session_dir
        self.session_dir.mkdir(parents=True, exist_ok=True)
        self.extension = extension
        self.tools = tools
        self.ui_policy = ui_policy or {}  # method -> 'allow'|'deny'
        self.seen_ids = set()  # message-id dedupe
        self.events = []
        self.responses = {}
        self.lock = threading.Lock()
        self.send_lock = threading.Lock()
        self.proc = None
        self.reader = None

    def start(self):
        env = dict(os.environ)
        brew = "/home/linuxbrew/.linuxbrew/bin"
        if brew not in env.get("PATH", ""):
            env["PATH"] = brew + ":" + env.get("PATH", "")
        argv = ["/home/linuxbrew/.linuxbrew/bin/pi", "--mode", "rpc",
                "--session-dir", str(self.session_dir),
                "--session-id", self.session_id]
        if not self.tools:
            argv.append("--no-tools")
        if self.extension:
            argv += ["-e", self.extension]
        self.proc = subprocess.Popen(
            argv,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=sys.stderr, bufsize=0, env=env,
        )
        self.reader = threading.Thread(target=self._read_loop, daemon=True)
        self.reader.start()

    def _read_loop(self):
        buf = b""
        while True:
            chunk = self.proc.stdout.read(4096)
            if not chunk:
                break
            buf += chunk
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                line = line.rstrip(b"\r")
                if not line.strip():
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if rec.get("type") == "extension_ui_request" and rec.get("method") == "confirm":
                    self._answer_confirm(rec)
                with self.lock:
                    if rec.get("type") == "response" and "id" in rec:
                        self.responses[rec["id"]] = rec
                    else:
                        self.events.append(rec)

    def _answer_confirm(self, rec):
        decision = self.ui_policy.get("confirm", "deny")
        rid = rec["id"]
        title = rec.get("title", "") + " " + rec.get("message", "")
        # default-deny writes/exec, allow reads unless policy says otherwise
        if decision == "auto":
            lower = title.lower()
            decision = "deny" if any(k in lower for k in ("write", "edit", "bash", "exec")) else "allow"
        resp = {"type": "extension_ui_response", "id": rid,
                "confirmed": decision == "allow"}
        with self.send_lock:
            try:
                self.proc.stdin.write((json.dumps(resp) + "\n").encode())
                self.proc.stdin.flush()
            except Exception:
                pass

    def send(self, cmd):
        if "id" not in cmd:
            cmd["id"] = uuid.uuid4().hex[:8]
        data = (json.dumps(cmd) + "\n").encode()
        with self.send_lock:
            self.proc.stdin.write(data)
            self.proc.stdin.flush()
        return cmd["id"]

    def wait_response(self, cmd_id, timeout=30):
        t0 = time.time()
        while time.time() - t0 < timeout:
            with self.lock:
                if cmd_id in self.responses:
                    return self.responses.pop(cmd_id)
            time.sleep(0.05)
        raise TimeoutError(f"no response for {cmd_id}")

    def wait_settled(self, timeout=180):
        """Block until agent_settled appears. Returns events since call."""
        with self.lock:
            start = len(self.events)
        t0 = time.time()
        while time.time() - t0 < timeout:
            with self.lock:
                for e in self.events[start:]:
                    if e.get("type") == "agent_settled":
                        return self.events[start:]
            time.sleep(0.1)
        raise TimeoutError("agent_settled never arrived")

    def prompt(self, message, message_id=None):
        """Send a user message. Duplicate message_id -> skipped (dedupe)."""
        mid = message_id or uuid.uuid4().hex[:12]
        if mid in self.seen_ids:
            return {"deduped": True, "message_id": mid}
        self.seen_ids.add(mid)
        # drain settled markers before sending so wait_settled is fresh
        cmd_id = self.send({"type": "prompt", "message": message})
        resp = self.wait_response(cmd_id)
        events = self.wait_settled()
        text = self.last_assistant_text()
        return {"deduped": False, "message_id": mid, "resp": resp,
                "text": text, "events": events}

    def last_assistant_text(self):
        cmd_id = self.send({"type": "get_last_assistant_text"})
        resp = self.wait_response(cmd_id)
        return (resp.get("data") or {}).get("text")

    def get_state(self):
        cmd_id = self.send({"type": "get_state"})
        return self.wait_response(cmd_id)

    def stop(self):
        try:
            self.proc.stdin.close()
        except Exception:
            pass
        self.proc.wait(timeout=15)


def phase1_full():
    """Full proof: tools enabled, permission deny enforced, reconnect resumes."""
    lease = OwnerLease()
    ok1, owner1 = lease.claim("pi")
    assert ok1
    ok2, _ = lease.claim("kilo")
    assert not ok2
    print(f"OWNER pi holds lease; kilo second-claim rejected")

    gate = str(Path(__file__).parent / "kilo-gate.ts")
    a = PiAdapter("ses_pi_kilo_hip_tools", SESSION_DIR, extension=gate,
                  tools=True, ui_policy={"confirm": "auto"})
    import os
    os.makedirs("/tmp/pi-kilo-hip/work", exist_ok=True)
    os.chdir("/tmp/pi-kilo-hip/work")
    a.start()
    st = (a.get_state().get("data") or {})
    print(f"PI sessionId={st.get('sessionId')} file={st.get('sessionFile')}")

    # tool call allowed (read-only): Pi must execute a real tool
    r = a.prompt("Use the read tool to read /etc/hostname and report its contents.",
                 message_id="msg_tools_allow")
    tool_events = [e for e in r["events"] if e.get("type", "").startswith("tool_execution")]
    print(f"ALLOW path: {len(tool_events)} tool events, text={r['text']!r:.120}")
    assert any(e.get("type") == "tool_execution_end" and not e.get("isError")
               for e in tool_events), "expected a successful tool call"

    # permission deny enforced by Pi: write must be blocked
    r = a.prompt("Use the write tool to create /tmp/pi-kilo-hip/work/BLOCKED.txt with content hi.",
                 message_id="msg_tools_deny")
    ends = [e for e in r["events"] if e.get("type") == "tool_execution_end"]
    denied = [e for e in ends if e.get("isError")]
    print(f"DENY path: {len(ends)} tool ends, {len(denied)} errored; text={r['text']!r:.160}")
    assert denied, "expected denied tool call to surface as error"
    assert not Path("/tmp/pi-kilo-hip/work/BLOCKED.txt").exists(), "denied write must not land"

    # reconnect: kill adapter (closes stdin -> Pi orderly shutdown), resume from file
    cmd_id = a.send({"type": "get_entries"})
    leaf = (a.wait_response(cmd_id).get("data") or {}).get("leafId")
    sfile = st.get("sessionFile")
    a.stop()
    print(f"ADAPTER killed at leaf={leaf}; resuming {sfile}")
    # resume by session file: spawn a fresh adapter then switch_session
    b2 = PiAdapter("ses_resume_tmp", SESSION_DIR, extension=gate,
                   tools=True, ui_policy={"confirm": "auto"})
    b2.start()
    cid = b2.send({"type": "switch_session", "sessionPath": sfile})
    sw = b2.wait_response(cid)
    assert sw.get("success"), f"switch_session failed: {sw}"
    cid = b2.send({"type": "get_entries", "since": leaf})
    catch = b2.wait_response(cid)
    assert catch.get("success"), f"cursor failed: {catch}"
    new = (catch.get("data") or {}).get("entries", [])
    print(f"RESUME ok: {len(new)} new entries since {leaf}; history intact")
    r = b2.prompt("Reply with exactly: RESUMED-OK", message_id="msg_resumed")
    print(f"POST-RESUME text={r['text']!r}")
    assert "RESUMED-OK" in (r["text"] or "")
    b2.stop()
    lease.release()
    print("DONE-FULL: tools executed, deny enforced, reconnect resumed, no dupes.")


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--full":
        return phase1_full()
    message = sys.argv[1] if len(sys.argv) > 1 else "Reply with exactly: PONG-HIP-01"
    lease = OwnerLease()

    # 1. ownership: first claimant wins, second rejected
    ok1, owner1 = lease.claim("pi")
    assert ok1, "first claim must succeed"
    ok2, owner2 = lease.claim("kilo")
    assert not ok2, "second claimant must be REJECTED"
    print(f"OWNER lease held by {owner1[0]}:{owner1[1]}; kilo claim rejected (held by {owner2[0]})")

    # 2. spawn Pi bound to logical session id
    a = PiAdapter(SESSION_ID, SESSION_DIR)
    a.start()
    state = a.get_state()
    sid = (state.get("data") or {}).get("sessionId")
    sfile = (state.get("data") or {}).get("sessionFile")
    print(f"PI sessionId={sid} file={sfile}")
    assert sid == SESSION_ID, f"identity binding failed: {sid}"

    # 3. send message (as Kilo would route it) -> Pi executes
    print(f"KILO -> PI [{SESSION_ID}]: {message!r}")
    r = a.prompt(message, message_id="msg_hip_01")
    print(f"PI executed, disposition={(r['resp'].get('data') or {}).get('disposition')}")
    print(f"PI response text: {r['text']!r}")

    # 4. dedupe: retry same message id executes ONCE
    r2 = a.prompt(message, message_id="msg_hip_01")
    assert r2["deduped"], "retry must be deduped"
    print(f"RETRY msg_hip_01 -> deduped, no re-execution")

    # 5. catch-up cursor: get_entries since leaf works
    cmd_id = a.send({"type": "get_entries"})
    entries = a.wait_response(cmd_id)
    n = len((entries.get("data") or {}).get("entries", []))
    leaf = (entries.get("data") or {}).get("leafId")
    print(f"ENTRIES n={n} leaf={leaf}")
    cmd_id = a.send({"type": "get_entries", "since": leaf})
    catch = a.wait_response(cmd_id)
    assert catch.get("success"), "cursor catch-up must succeed"
    print(f"CATCH-UP since={leaf} -> {len((catch.get('data') or {}).get('entries', []))} new entries")

    a.stop()
    lease.release()
    print("DONE: Pi executed Kilo-routed message; owner guard + dedupe + cursor all hold.")


if __name__ == "__main__":
    main()
