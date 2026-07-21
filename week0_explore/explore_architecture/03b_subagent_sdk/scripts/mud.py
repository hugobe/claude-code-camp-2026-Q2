#!/usr/bin/env python3
"""
Persistent telnet client for playing a MUD (tbaMUD/CircleMUD) turn-by-turn.

A MUD session is stateful: your character stays in the world, in combat,
in a shop menu, etc. between commands. Reconnecting for every command would
mean logging back in each time and losing that state (and possibly dying in
combat while disconnected). So this script runs a small background daemon
that holds ONE persistent socket open to the MUD, and a lightweight CLI
that talks to that daemon over a local Unix socket to send commands and
fetch new output. The daemon keeps running across many CLI invocations.

Usage:
    mud.py start                  # connect + auto-login, start the daemon
    mud.py send "look"            # send a command, wait briefly, print new output
    mud.py send "north" --wait 2  # custom wait time (seconds) for slow responses
    mud.py read                   # print any new output since the last read (no send)
    mud.py status                 # is the daemon running / connected?
    mud.py stop                   # disconnect and kill the daemon

Configuration (env vars, all optional, defaults match the target MUD):
    MUD_HOST   default "localhost"
    MUD_PORT   default 4000
    MUD_USER   default "dummy"       (also "smarty" is a known second character)
    MUD_PASS   default "helloworld"  ("goodbyemoon" for smarty)
    MUD_STATE_DIR  default "/tmp/mud-skill-<port>-<project-hash>-<user>"
"""
import argparse
import hashlib
import json
import os
import re
import select
import signal
import socket
import subprocess
import sys
import threading
import time

HOST = os.environ.get("MUD_HOST", "localhost")
PORT = int(os.environ.get("MUD_PORT", "4000"))
USERNAME = os.environ.get("MUD_USER", "dummy")
PASSWORD = os.environ.get("MUD_PASS", "helloworld")

# Keyed by project path (not just port) so that separate checkouts/copies of
# this tool (e.g. a skill and an agent adapted from it) pointed at the same
# MUD port don't share one daemon and silently steal each other's connection.
# Also keyed by username so two characters (e.g. "dummy" and "smarty") played
# from the same project can each hold their own persistent connection at the
# same time instead of one stealing the other's daemon/socket.
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_PROJECT_TAG = hashlib.sha1(_PROJECT_ROOT.encode()).hexdigest()[:8]
STATE_DIR = os.environ.get("MUD_STATE_DIR", f"/tmp/mud-skill-{PORT}-{_PROJECT_TAG}-{USERNAME}")

PID_FILE = os.path.join(STATE_DIR, "daemon.pid")
SOCK_FILE = os.path.join(STATE_DIR, "control.sock")
LOG_FILE = os.path.join(STATE_DIR, "session.log")
OFFSET_FILE = os.path.join(STATE_DIR, "read.offset")
DAEMON_STDERR = os.path.join(STATE_DIR, "daemon.stderr.log")

ANSI_RE = re.compile(rb"\x1b\[[0-9;]*[a-zA-Z]")

# --- Telnet protocol negotiation (IAC handling) -----------------------------
IAC, DONT, DO, WONT, WILL, SB, SE = 255, 254, 253, 252, 251, 250, 240


def strip_telnet(data: bytes, sock: socket.socket) -> bytes:
    """Strip telnet IAC negotiation sequences from a chunk of socket data,
    replying WONT/DONT to any option requests so the server doesn't stall
    waiting for a negotiation response. Returns the remaining plain text."""
    out = bytearray()
    i, n = 0, len(data)
    while i < n:
        b = data[i]
        if b == IAC and i + 1 < n:
            cmd = data[i + 1]
            if cmd in (DO, DONT, WILL, WONT) and i + 2 < n:
                opt = data[i + 2]
                try:
                    if cmd == DO:
                        sock.sendall(bytes([IAC, WONT, opt]))
                    elif cmd == WILL:
                        sock.sendall(bytes([IAC, DONT, opt]))
                except OSError:
                    pass
                i += 3
                continue
            elif cmd == SB:
                j = i + 2
                while j + 1 < n and not (data[j] == IAC and data[j + 1] == SE):
                    j += 1
                i = j + 2
                continue
            else:
                i += 2
                continue
        out.append(b)
        i += 1
    return bytes(out)


# --- Daemon -------------------------------------------------------------


def daemon_main():
    os.makedirs(STATE_DIR, exist_ok=True)
    if os.path.exists(SOCK_FILE):
        os.remove(SOCK_FILE)

    mud_sock = socket.create_connection((HOST, PORT), timeout=10)
    mud_sock.settimeout(None)

    log_f = open(LOG_FILE, "ab", buffering=0)

    lock = threading.Lock()
    state = {"connected": True}

    def append_log(chunk: bytes):
        if not chunk:
            return
        with lock:
            log_f.write(chunk)

    def recv_for(seconds: float) -> bytes:
        """Collect data from mud_sock for up to `seconds`, returning cleaned text."""
        deadline = time.time() + seconds
        buf = bytearray()
        mud_sock.settimeout(0.2)
        while time.time() < deadline:
            try:
                chunk = mud_sock.recv(4096)
                if chunk == b"":
                    state["connected"] = False
                    break
                buf.extend(strip_telnet(chunk, mud_sock))
            except socket.timeout:
                continue
            except OSError:
                state["connected"] = False
                break
        mud_sock.settimeout(None)
        return bytes(buf)

    def wait_for_pattern(pattern: re.Pattern, timeout: float) -> bool:
        deadline = time.time() + timeout
        while time.time() < deadline:
            chunk = recv_for(min(1.0, max(0.1, deadline - time.time())))
            if chunk:
                append_log(chunk)
                if pattern.search(chunk):
                    return True
            if not state["connected"]:
                return False
        return False

    # Scripted login: tbaMUD/CircleMUD ask for a name, then a password.
    # If the server's flow differs, this simply falls through to relay mode
    # and the calling agent can finish login manually via `send`, using the
    # raw output from `read`/`status` to see what prompt is showing.
    if wait_for_pattern(re.compile(rb"name", re.I), 8):
        mud_sock.sendall(USERNAME.encode() + b"\r\n")
        if wait_for_pattern(re.compile(rb"assword", re.I), 8):
            mud_sock.sendall(PASSWORD.encode() + b"\r\n")
            # swallow a bit more output (MOTD / "press return" prompts)
            append_log(recv_for(2))

    def cleanup_and_exit():
        try:
            mud_sock.close()
        except OSError:
            pass
        for p in (SOCK_FILE, PID_FILE):
            try:
                os.remove(p)
            except OSError:
                pass
        os._exit(0)

    def reader_loop():
        mud_sock.settimeout(None)
        while True:
            try:
                chunk = mud_sock.recv(4096)
            except OSError:
                break
            if chunk == b"":
                append_log(b"\r\n*** Connection closed by remote host ***\r\n")
                break
            append_log(strip_telnet(chunk, mud_sock))
        # The server (or network) closed the connection. Mark it dead and tear
        # the daemon down so its PID_FILE/SOCK_FILE don't linger: a stale daemon
        # with a dead socket makes the next `mud.py start` report "Already
        # running" and replay old log output, which looks like a live session
        # (a logged-in character) when nothing is actually connected.
        state["connected"] = False
        cleanup_and_exit()

    threading.Thread(target=reader_loop, daemon=True).start()

    ctrl = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    ctrl.bind(SOCK_FILE)
    ctrl.listen(8)

    def handle_client(conn):
        with conn:
            data = conn.makefile("rb").readline()
            if not data:
                return
            try:
                req = json.loads(data)
            except json.JSONDecodeError:
                conn.sendall(b'{"ok": false, "error": "bad request"}\n')
                return
            cmd = req.get("cmd")
            if cmd == "send":
                text = req.get("text", "")
                try:
                    mud_sock.sendall(text.encode() + b"\r\n")
                    conn.sendall(b'{"ok": true}\n')
                except OSError as e:
                    conn.sendall(json.dumps({"ok": False, "error": str(e)}).encode() + b"\n")
            elif cmd == "ping":
                conn.sendall(json.dumps({"ok": True, "connected": state["connected"]}).encode() + b"\n")
            elif cmd == "stop":
                conn.sendall(b'{"ok": true}\n')
                try:
                    mud_sock.sendall(b"quit\r\n")
                    time.sleep(0.3)
                except OSError:
                    pass
                cleanup_and_exit()
            else:
                conn.sendall(b'{"ok": false, "error": "unknown cmd"}\n')

    signal.signal(signal.SIGTERM, lambda *_: cleanup_and_exit())

    with open(PID_FILE, "w") as f:
        f.write(str(os.getpid()))

    while True:
        readable, _, _ = select.select([ctrl], [], [], 1.0)
        if readable:
            conn, _ = ctrl.accept()
            handle_client(conn)


# --- CLI ------------------------------------------------------------------


def _daemon_running() -> bool:
    if not os.path.exists(PID_FILE):
        return False
    try:
        with open(PID_FILE) as f:
            pid = int(f.read().strip())
        os.kill(pid, 0)
        return True
    except (OSError, ValueError):
        return False


def _control_request(req: dict, timeout: float = 5.0) -> dict:
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
        s.settimeout(timeout)
        s.connect(SOCK_FILE)
        s.sendall(json.dumps(req).encode() + b"\n")
        resp = s.makefile("rb").readline()
    return json.loads(resp) if resp else {"ok": False, "error": "no response"}


def _daemon_connected() -> bool:
    """A daemon is only *usable* if it's running AND its socket to the MUD is
    still alive. A daemon whose connection dropped (server kicked us, network
    blip) may briefly linger before it tears itself down; treat it as unusable
    so callers reconnect instead of talking to a dead socket."""
    if not _daemon_running():
        return False
    try:
        return bool(_control_request({"cmd": "ping"}, timeout=3.0).get("connected"))
    except OSError:
        return False


def _kill_daemon():
    """Best-effort teardown of an existing daemon and its state files, so a
    fresh `start` can reconnect cleanly."""
    if os.path.exists(PID_FILE):
        try:
            pid = int(open(PID_FILE).read().strip())
            os.kill(pid, signal.SIGTERM)
            deadline = time.time() + 3
            while time.time() < deadline:
                try:
                    os.kill(pid, 0)
                    time.sleep(0.1)
                except OSError:
                    break
        except (OSError, ValueError):
            pass
    for p in (SOCK_FILE, PID_FILE):
        try:
            os.remove(p)
        except OSError:
            pass


def _read_new_output() -> str:
    if not os.path.exists(LOG_FILE):
        return ""
    offset = 0
    if os.path.exists(OFFSET_FILE):
        try:
            offset = int(open(OFFSET_FILE).read().strip())
        except ValueError:
            offset = 0
    with open(LOG_FILE, "rb") as f:
        f.seek(offset)
        data = f.read()
        new_offset = f.tell()
    with open(OFFSET_FILE, "w") as f:
        f.write(str(new_offset))
    text = ANSI_RE.sub(b"", data).decode("utf-8", errors="replace")
    return text


def cmd_start(args):
    if _daemon_running():
        if _daemon_connected():
            print(f"Already running (pid file: {PID_FILE}). Reading any pending output:")
            print(_read_new_output() or "(none)")
            return
        # Daemon process is alive but its MUD socket is dead (e.g. the server
        # closed the connection). Tear it down and reconnect, rather than
        # replaying stale log output that looks like a live session.
        print("Stale daemon found (socket disconnected). Restarting…")
        _kill_daemon()
    os.makedirs(STATE_DIR, exist_ok=True)
    for p in (LOG_FILE, OFFSET_FILE, SOCK_FILE, PID_FILE):
        if os.path.exists(p):
            os.remove(p)

    with open(DAEMON_STDERR, "wb") as errf:
        subprocess.Popen(
            [sys.executable, os.path.abspath(__file__), "_run_daemon"],
            stdout=subprocess.DEVNULL,
            stderr=errf,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
        )

    deadline = time.time() + 10
    while time.time() < deadline and not os.path.exists(SOCK_FILE):
        time.sleep(0.1)
    if not os.path.exists(SOCK_FILE):
        print("Daemon failed to start. Check:", DAEMON_STDERR, file=sys.stderr)
        sys.exit(1)

    # Give the daemon time to run the scripted login before we read output.
    time.sleep(6)
    print(f"Connected to {HOST}:{PORT} as {USERNAME!r}. Output so far:")
    print(_read_new_output() or "(none yet)")


def cmd_send(args):
    if not _daemon_running():
        print("Daemon not running. Run `mud.py start` first.", file=sys.stderr)
        sys.exit(1)
    resp = _control_request({"cmd": "send", "text": args.text})
    if not resp.get("ok"):
        print(f"send failed: {resp.get('error')}", file=sys.stderr)
        sys.exit(1)
    time.sleep(args.wait)
    print(_read_new_output() or "(no new output)")


def cmd_read(args):
    if not os.path.exists(STATE_DIR):
        print("No session yet. Run `mud.py start` first.", file=sys.stderr)
        sys.exit(1)
    print(_read_new_output() or "(no new output)")


def cmd_status(args):
    running = _daemon_running()
    print(f"daemon running: {running}")
    if running:
        try:
            resp = _control_request({"cmd": "ping"})
            print(f"mud connected: {resp.get('connected')}")
        except OSError as e:
            print(f"control socket error: {e}")
    print(f"state dir: {STATE_DIR}")


def cmd_stop(args):
    if not _daemon_running():
        print("Not running.")
        return
    try:
        _control_request({"cmd": "stop"}, timeout=3.0)
    except OSError:
        pass
    print("Stopped.")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="action", required=True)

    sub.add_parser("_run_daemon")  # internal, spawned by `start`

    sub.add_parser("start", help="Connect to the MUD and log in.")

    p_send = sub.add_parser("send", help="Send a command and print the resulting output.")
    p_send.add_argument("text", help="Command text to send, e.g. 'look', 'north', 'kill rat'")
    p_send.add_argument("--wait", type=float, default=1.0, help="Seconds to wait for a response before reading (default 1.0)")

    sub.add_parser("read", help="Print any new output since the last read/send, without sending anything.")
    sub.add_parser("status", help="Show whether the daemon is running and connected.")
    sub.add_parser("stop", help="Send 'quit' and shut down the daemon.")

    args = parser.parse_args()

    if args.action == "_run_daemon":
        daemon_main()
    elif args.action == "start":
        cmd_start(args)
    elif args.action == "send":
        cmd_send(args)
    elif args.action == "read":
        cmd_read(args)
    elif args.action == "status":
        cmd_status(args)
    elif args.action == "stop":
        cmd_stop(args)


if __name__ == "__main__":
    main()
