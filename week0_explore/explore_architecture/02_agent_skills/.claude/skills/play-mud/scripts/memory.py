#!/usr/bin/env python3
"""
Structured, queryable memory for a MUD character, replacing the old
data/player.md + data/world.md prose files with two small SQLite
databases:

  data/player.db  - this character's goal, live stats, task queue,
                     inventory, milestones, and a running observation log.
  data/world.db   - facts about the game world itself: rooms, exits,
                     shops, NPCs/monsters, unresolved leads.

Why two databases instead of one, and why SQLite instead of markdown:

- Two files because "what this character is trying to do" and "what the
  world looks like" are different kinds of fact with different owners
  and different lifetimes - world.db could in principle be shared across
  multiple characters/sessions playing the same MUD, while player.db is
  tied to one character's progress.
- SQLite instead of markdown because prose doesn't scale: a growing
  room/NPC/shop list turns into a wall of text nobody re-reads carefully,
  there's no way to ask "what's the shortest known path from here to the
  swamp troll" without a human/model re-deriving it by eye each time, and
  two sessions writing to the same .md file at once can silently clobber
  each other's edits. SQLite gives indexed lookups, a real graph query
  for pathing (see `path`), and - via WAL journaling plus a busy timeout
  - safe concurrent writers instead of a last-write-wins race.

Every subcommand prints a short human-readable confirmation or listing;
nothing here requires parsing its own output, so it's safe to call
liberally and often (that's the point - task priorities and the
observation log are meant to be updated continuously as play happens,
not batched up and written once at the end of a session).

Run `memory.py --help` or `memory.py <command> --help` for full usage.
Start any new session with `memory.py dump` to see everything at once.
"""
import argparse
import json
import os
import sqlite3
import sys
from collections import deque
from datetime import datetime, timezone

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
PLAYER_DB = os.path.join(DATA_DIR, "player.db")
WORLD_DB = os.path.join(DATA_DIR, "world.db")

PLAYER_SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT
);
CREATE TABLE IF NOT EXISTS player_snapshot (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    level INTEGER, title TEXT,
    hp_cur INTEGER, hp_max INTEGER,
    mana_cur INTEGER, mana_max INTEGER,
    move_cur INTEGER, move_max INTEGER,
    exp INTEGER, exp_to_next INTEGER,
    gold INTEGER, alignment INTEGER,
    location_room TEXT,
    updated_at TEXT
);
CREATE TABLE IF NOT EXISTS persona (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    playstyle TEXT,
    exploration_style TEXT CHECK (exploration_style IN ('thorough','efficient','opportunistic')),
    risk_tolerance TEXT CHECK (risk_tolerance IN ('low','medium','high')),
    notes TEXT,
    updated_at TEXT
);
CREATE TABLE IF NOT EXISTS inventory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slot TEXT NOT NULL,
    item_name TEXT NOT NULL,
    notes TEXT,
    updated_at TEXT
);
CREATE TABLE IF NOT EXISTS milestones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    description TEXT NOT NULL,
    achieved_at TEXT
);
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    subject TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('active','pending','blocked','done')) DEFAULT 'pending',
    priority REAL NOT NULL,
    reason TEXT,
    created_at TEXT,
    updated_at TEXT
);
CREATE TABLE IF NOT EXISTS observations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT NOT NULL,
    room TEXT,
    raw_text TEXT NOT NULL,
    recorded_at TEXT NOT NULL
);
"""

WORLD_SCHEMA = """
CREATE TABLE IF NOT EXISTS rooms (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    area TEXT,
    notable TEXT,
    first_seen_at TEXT
);
CREATE TABLE IF NOT EXISTS exits (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_room_id INTEGER NOT NULL REFERENCES rooms(id),
    direction TEXT NOT NULL,
    to_room_id INTEGER REFERENCES rooms(id),
    visit_count INTEGER NOT NULL DEFAULT 0,
    last_traversed_at TEXT,
    UNIQUE(from_room_id, direction)
);
CREATE TABLE IF NOT EXISTS shops (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    room_id INTEGER REFERENCES rooms(id),
    notes TEXT
);
CREATE TABLE IF NOT EXISTS shop_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    shop_id INTEGER NOT NULL REFERENCES shops(id),
    item_name TEXT NOT NULL,
    price INTEGER,
    notes TEXT
);
CREATE TABLE IF NOT EXISTS npcs_monsters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    kind TEXT NOT NULL CHECK (kind IN ('npc','monster')),
    room_id INTEGER REFERENCES rooms(id),
    danger TEXT,
    loot TEXT,
    notes TEXT,
    UNIQUE(name, room_id)
);
CREATE TABLE IF NOT EXISTS leads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    description TEXT NOT NULL,
    resolved INTEGER NOT NULL DEFAULT 0
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _connect(path: str) -> sqlite3.Connection:
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(path, timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=10000")
    conn.row_factory = sqlite3.Row
    return conn


def _pconn() -> sqlite3.Connection:
    return _connect(PLAYER_DB)


def _wconn() -> sqlite3.Connection:
    return _connect(WORLD_DB)


def init_dbs():
    with _pconn() as c:
        c.executescript(PLAYER_SCHEMA)
    with _wconn() as c:
        c.executescript(WORLD_SCHEMA)


# --- player.db helpers -----------------------------------------------------


def _goal_line(conn) -> str:
    row = conn.execute("SELECT value FROM meta WHERE key='goal'").fetchone()
    return row["value"] if row else "(none set yet)"


PERSONA_FIELDS = {"playstyle", "exploration_style", "risk_tolerance", "notes"}
PERSONA_EXPLORATION_STYLES = {"thorough", "efficient", "opportunistic"}
PERSONA_RISK_TOLERANCES = {"low", "medium", "high"}


def _persona_lines(conn):
    row = conn.execute("SELECT * FROM persona WHERE id=1").fetchone()
    if not row:
        return ["(not set — defaulting to balanced/opportunistic/medium; see `persona set`)"]
    lines = [f"{k}: {row[k]}" for k in row.keys() if k not in ("id", "updated_at") and row[k] is not None]
    return lines or ["(not set — defaulting to balanced/opportunistic/medium; see `persona set`)"]


def _task_add(conn, subject, status=None, priority=None, reason=None, urgent=False, before=None):
    rows = conn.execute(
        "SELECT id, priority FROM tasks WHERE status != 'done' ORDER BY priority ASC"
    ).fetchall()
    if urgent:
        new_priority = (rows[0]["priority"] - 1.0) if rows else 0.0
        status = "active"
        conn.execute("UPDATE tasks SET status='pending', updated_at=? WHERE status='active'", (_now(),))
    elif before is not None:
        target = conn.execute("SELECT priority FROM tasks WHERE id=?", (before,)).fetchone()
        if not target:
            raise ValueError(f"no task with id {before}")
        prev = conn.execute(
            "SELECT priority FROM tasks WHERE priority < ? AND status != 'done' ORDER BY priority DESC LIMIT 1",
            (target["priority"],),
        ).fetchone()
        new_priority = (prev["priority"] + target["priority"]) / 2 if prev else target["priority"] - 1.0
        status = status or "pending"
    elif priority is not None:
        new_priority = priority
        status = status or "pending"
    else:
        new_priority = (rows[-1]["priority"] + 1.0) if rows else 0.0
        status = status or "pending"
    cur = conn.execute(
        "INSERT INTO tasks (subject, status, priority, reason, created_at, updated_at) VALUES (?,?,?,?,?,?)",
        (subject, status, new_priority, reason, _now(), _now()),
    )
    return cur.lastrowid, status, new_priority


def _task_lines(conn, status=None):
    q = "SELECT * FROM tasks"
    params = []
    if status:
        q += " WHERE status=?"
        params.append(status)
    q += " ORDER BY CASE status WHEN 'active' THEN 0 ELSE 1 END, priority ASC"
    rows = conn.execute(q, params).fetchall()
    lines = []
    for r in rows:
        reason = f" — {r['reason']}" if r["reason"] else ""
        lines.append(f"#{r['id']} [{r['status']}] (p={r['priority']:.2f}) {r['subject']}{reason}")
    return lines


def _task_next_line(conn):
    row = conn.execute(
        "SELECT * FROM tasks WHERE status IN ('active','pending') "
        "ORDER BY CASE status WHEN 'active' THEN 0 ELSE 1 END, priority ASC LIMIT 1"
    ).fetchone()
    if not row:
        return "(no actionable task — queue is empty or everything is blocked)"
    reason = f" — {row['reason']}" if row["reason"] else ""
    return f"#{row['id']} [{row['status']}] {row['subject']}{reason}"


def _snapshot_lines(conn):
    row = conn.execute("SELECT * FROM player_snapshot WHERE id=1").fetchone()
    if not row:
        return ["(no snapshot yet)"]
    return [f"{k}: {row[k]}" for k in row.keys() if k not in ("id",) and row[k] is not None]


def _inventory_lines(conn):
    rows = conn.execute("SELECT * FROM inventory ORDER BY slot, item_name").fetchall()
    if not rows:
        return ["(empty)"]
    lines = []
    for r in rows:
        note = f" ({r['notes']})" if r["notes"] else ""
        lines.append(f"[{r['slot']}] {r['item_name']}{note}")
    return lines


def _milestone_lines(conn, limit=20):
    rows = conn.execute("SELECT * FROM milestones ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    if not rows:
        return ["(none yet)"]
    return [f"[{r['achieved_at']}] {r['description']}" for r in rows]


def _observation_lines(conn, category=None, room=None, limit=20):
    q = "SELECT * FROM observations"
    conds, params = [], []
    if category:
        conds.append("category=?")
        params.append(category)
    if room:
        conds.append("room=?")
        params.append(room)
    if conds:
        q += " WHERE " + " AND ".join(conds)
    q += " ORDER BY id DESC LIMIT ?"
    params.append(limit)
    rows = conn.execute(q, params).fetchall()
    if not rows:
        return ["(none)"]
    lines = []
    for r in rows:
        room_s = f" @ {r['room']}" if r["room"] else ""
        lines.append(f"[{r['recorded_at']}] ({r['category']}){room_s}: {r['raw_text']}")
    return lines


# --- world.db helpers --------------------------------------------------


def _get_or_create_room(conn, name, area=None, notable=None):
    row = conn.execute("SELECT id FROM rooms WHERE name=?", (name,)).fetchone()
    if row:
        if area or notable:
            conn.execute(
                "UPDATE rooms SET area=COALESCE(?,area), notable=COALESCE(?,notable) WHERE id=?",
                (area, notable, row["id"]),
            )
        return row["id"]
    cur = conn.execute(
        "INSERT INTO rooms (name, area, notable, first_seen_at) VALUES (?,?,?,?)",
        (name, area, notable, _now()),
    )
    return cur.lastrowid


def _room_map_lines(conn, area=None):
    q = "SELECT * FROM rooms"
    params = []
    if area:
        q += " WHERE area=?"
        params.append(area)
    q += " ORDER BY area, name"
    rooms = conn.execute(q, params).fetchall()
    if not rooms:
        return ["(no rooms recorded yet)"]
    lines = []
    for room in rooms:
        exits = conn.execute(
            "SELECT e.direction, r.name AS to_name FROM exits e "
            "LEFT JOIN rooms r ON r.id = e.to_room_id WHERE e.from_room_id=? ORDER BY e.direction",
            (room["id"],),
        ).fetchall()
        exit_s = ", ".join(f"{e['direction']}->{e['to_name'] or '?'}" for e in exits)
        area_s = f"[{room['area']}] " if room["area"] else ""
        notable_s = f" — {room['notable']}" if room["notable"] else ""
        lines.append(f"{area_s}{room['name']}: {exit_s}{notable_s}")
    return lines


def _shop_lines(conn):
    shops = conn.execute("SELECT * FROM shops ORDER BY name").fetchall()
    if not shops:
        return ["(none recorded yet)"]
    lines = []
    for s in shops:
        room = conn.execute("SELECT name FROM rooms WHERE id=?", (s["room_id"],)).fetchone() if s["room_id"] else None
        items = conn.execute("SELECT item_name, price FROM shop_items WHERE shop_id=? ORDER BY item_name", (s["id"],)).fetchall()
        items_s = ", ".join(f"{i['item_name']} ({i['price']}g)" for i in items)
        room_s = f" @ {room['name']}" if room else ""
        lines.append(f"{s['name']}{room_s}" + (f": {items_s}" if items_s else ""))
    return lines


def _npc_lines(conn, room=None, kind=None):
    q = "SELECT n.*, r.name AS room_name FROM npcs_monsters n LEFT JOIN rooms r ON r.id = n.room_id"
    conds, params = [], []
    if room:
        conds.append("r.name=?")
        params.append(room)
    if kind:
        conds.append("n.kind=?")
        params.append(kind)
    if conds:
        q += " WHERE " + " AND ".join(conds)
    q += " ORDER BY n.kind, n.name"
    rows = conn.execute(q, params).fetchall()
    if not rows:
        return ["(none recorded yet)"]
    lines = []
    for r in rows:
        extra = ", ".join(x for x in (r["danger"], r["loot"]) if x)
        loc = f" @ {r['room_name']}" if r["room_name"] else ""
        lines.append(f"[{r['kind']}] {r['name']}{loc}" + (f" ({extra})" if extra else ""))
    return lines


def _lead_lines(conn, unresolved_only=False):
    q = "SELECT * FROM leads"
    if unresolved_only:
        q += " WHERE resolved=0"
    q += " ORDER BY id"
    rows = conn.execute(q).fetchall()
    if not rows:
        return ["(none)"]
    return [f"[{'x' if r['resolved'] else ' '}] #{r['id']} {r['description']}" for r in rows]


# --- CLI handlers ------------------------------------------------------


def cmd_init(args):
    init_dbs()
    print(f"Initialized {PLAYER_DB} and {WORLD_DB}")


def cmd_goal_get(args):
    print(_goal_line(_pconn()))


def cmd_goal_set(args):
    conn = _pconn()
    with conn:
        conn.execute(
            "INSERT INTO meta(key,value) VALUES('goal',?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (args.text,),
        )
    print(f"goal set: {args.text}")


def cmd_persona_show(args):
    for line in _persona_lines(_pconn()):
        print(line)


def cmd_persona_set(args):
    updates = {}
    for kv in args.pairs:
        if "=" not in kv:
            print(f"Bad key=value pair: {kv!r}", file=sys.stderr)
            sys.exit(1)
        k, v = kv.split("=", 1)
        if k not in PERSONA_FIELDS:
            print(f"Unknown persona field: {k} (valid: {', '.join(sorted(PERSONA_FIELDS))})", file=sys.stderr)
            sys.exit(1)
        if k == "exploration_style" and v not in PERSONA_EXPLORATION_STYLES:
            print(f"exploration_style must be one of: {', '.join(sorted(PERSONA_EXPLORATION_STYLES))}", file=sys.stderr)
            sys.exit(1)
        if k == "risk_tolerance" and v not in PERSONA_RISK_TOLERANCES:
            print(f"risk_tolerance must be one of: {', '.join(sorted(PERSONA_RISK_TOLERANCES))}", file=sys.stderr)
            sys.exit(1)
        updates[k] = v
    if not updates:
        print("No key=value pairs given.", file=sys.stderr)
        sys.exit(1)
    conn = _pconn()
    with conn:
        conn.execute("INSERT OR IGNORE INTO persona (id) VALUES (1)")
        set_clause = ", ".join(f"{k}=?" for k in updates)
        conn.execute(
            f"UPDATE persona SET {set_clause}, updated_at=? WHERE id=1",
            (*updates.values(), _now()),
        )
    print("persona updated: " + ", ".join(f"{k}={v}" for k, v in updates.items()))


SNAPSHOT_FIELDS = {
    "level", "title", "hp_cur", "hp_max", "mana_cur", "mana_max", "move_cur", "move_max",
    "exp", "exp_to_next", "gold", "alignment", "location_room",
}


def cmd_snapshot_show(args):
    for line in _snapshot_lines(_pconn()):
        print(line)


def cmd_snapshot_set(args):
    updates = {}
    for kv in args.pairs:
        if "=" not in kv:
            print(f"Bad key=value pair: {kv!r}", file=sys.stderr)
            sys.exit(1)
        k, v = kv.split("=", 1)
        if k not in SNAPSHOT_FIELDS:
            print(f"Unknown snapshot field: {k} (valid: {', '.join(sorted(SNAPSHOT_FIELDS))})", file=sys.stderr)
            sys.exit(1)
        updates[k] = v
    if not updates:
        print("No key=value pairs given.", file=sys.stderr)
        sys.exit(1)
    conn = _pconn()
    with conn:
        conn.execute("INSERT OR IGNORE INTO player_snapshot (id) VALUES (1)")
        set_clause = ", ".join(f"{k}=?" for k in updates)
        conn.execute(
            f"UPDATE player_snapshot SET {set_clause}, updated_at=? WHERE id=1",
            (*updates.values(), _now()),
        )
    print("snapshot updated: " + ", ".join(f"{k}={v}" for k, v in updates.items()))


def cmd_inventory_add(args):
    conn = _pconn()
    with conn:
        conn.execute(
            "INSERT INTO inventory (slot, item_name, notes, updated_at) VALUES (?,?,?,?)",
            (args.slot, args.item, args.notes, _now()),
        )
    print(f"inventory: added [{args.slot}] {args.item}")


def cmd_inventory_remove(args):
    conn = _pconn()
    with conn:
        cur = conn.execute("DELETE FROM inventory WHERE item_name=?", (args.item,))
    print(f"inventory: removed {cur.rowcount} entr{'y' if cur.rowcount == 1 else 'ies'} matching {args.item!r}")


def cmd_inventory_list(args):
    for line in _inventory_lines(_pconn()):
        print(line)


def cmd_milestone_add(args):
    conn = _pconn()
    with conn:
        cur = conn.execute("INSERT INTO milestones (description, achieved_at) VALUES (?,?)", (args.text, _now()))
    print(f"milestone #{cur.lastrowid} logged.")


def cmd_milestone_list(args):
    for line in _milestone_lines(_pconn(), args.limit):
        print(line)


def cmd_task_add(args):
    conn = _pconn()
    with conn:
        try:
            task_id, status, priority = _task_add(
                conn, args.subject, status=args.status, priority=args.priority,
                reason=args.reason, urgent=args.urgent, before=args.before,
            )
        except ValueError as e:
            print(str(e), file=sys.stderr)
            sys.exit(1)
    print(f"task #{task_id} added: [{status}] {args.subject} (priority {priority:.2f})")


def cmd_task_list(args):
    for line in _task_lines(_pconn(), args.status):
        print(line)


def cmd_task_next(args):
    print(_task_next_line(_pconn()))


def cmd_task_update(args):
    fields, vals = [], []
    if args.status:
        fields.append("status=?")
        vals.append(args.status)
    if args.priority is not None:
        fields.append("priority=?")
        vals.append(args.priority)
    if args.reason is not None:
        fields.append("reason=?")
        vals.append(args.reason)
    if args.subject is not None:
        fields.append("subject=?")
        vals.append(args.subject)
    if not fields:
        print("Nothing to update — pass --status/--priority/--reason/--subject.", file=sys.stderr)
        sys.exit(1)
    fields.append("updated_at=?")
    vals.append(_now())
    vals.append(args.id)
    conn = _pconn()
    with conn:
        cur = conn.execute(f"UPDATE tasks SET {', '.join(fields)} WHERE id=?", vals)
    if cur.rowcount == 0:
        print(f"No task with id {args.id}", file=sys.stderr)
        sys.exit(1)
    print(f"task #{args.id} updated.")


def cmd_task_done(args):
    conn = _pconn()
    row = conn.execute("SELECT subject FROM tasks WHERE id=?", (args.id,)).fetchone()
    if not row:
        print(f"No task with id {args.id}", file=sys.stderr)
        sys.exit(1)
    note = args.note or row["subject"]
    with conn:
        conn.execute("INSERT INTO milestones (description, achieved_at) VALUES (?,?)", (note, _now()))
        conn.execute("DELETE FROM tasks WHERE id=?", (args.id,))
    print(f"task #{args.id} done -> milestone: {note}")


def cmd_observation_add(args):
    conn = _pconn()
    with conn:
        cur = conn.execute(
            "INSERT INTO observations (category, room, raw_text, recorded_at) VALUES (?,?,?,?)",
            (args.category, args.room, args.text, _now()),
        )
    print(f"observation #{cur.lastrowid} logged.")


def cmd_observation_list(args):
    for line in _observation_lines(_pconn(), args.category, args.room, args.limit):
        print(line)


def cmd_room_add(args):
    conn = _wconn()
    with conn:
        rid = _get_or_create_room(conn, args.name, args.area, args.notable)
    print(f"room #{rid}: {args.name}")


def cmd_room_exit(args):
    conn = _wconn()
    with conn:
        from_id = _get_or_create_room(conn, args.from_room)
        to_id = _get_or_create_room(conn, args.to_room) if args.to_room else None
        conn.execute(
            "INSERT INTO exits (from_room_id, direction, to_room_id, visit_count, last_traversed_at) "
            "VALUES (?,?,?,1,?) "
            "ON CONFLICT(from_room_id, direction) DO UPDATE SET "
            "to_room_id=COALESCE(excluded.to_room_id, exits.to_room_id), "
            "visit_count=exits.visit_count+1, last_traversed_at=excluded.last_traversed_at",
            (from_id, args.direction, to_id, _now()),
        )
    print(f"exit recorded: {args.from_room} --{args.direction}--> {args.to_room or '?'}")


def cmd_room_show(args):
    conn = _wconn()
    room = conn.execute("SELECT * FROM rooms WHERE name=?", (args.name,)).fetchone()
    if not room:
        print("(unknown room)")
        return
    print(room["name"] + (f" ({room['area']})" if room["area"] else ""))
    if room["notable"]:
        print(f"  notable: {room['notable']}")
    exits = conn.execute(
        "SELECT e.direction, r.name AS to_name, e.visit_count FROM exits e "
        "LEFT JOIN rooms r ON r.id = e.to_room_id WHERE e.from_room_id=? ORDER BY e.direction",
        (room["id"],),
    ).fetchall()
    for e in exits:
        print(f"  exit {e['direction']} -> {e['to_name'] or '?'} (visited {e['visit_count']}x)")
    for n in conn.execute("SELECT name, kind, danger, loot FROM npcs_monsters WHERE room_id=?", (room["id"],)).fetchall():
        extra = ", ".join(x for x in (n["danger"], n["loot"]) if x)
        print(f"  {n['kind']}: {n['name']}" + (f" ({extra})" if extra else ""))
    shop = conn.execute("SELECT name FROM shops WHERE room_id=?", (room["id"],)).fetchone()
    if shop:
        print(f"  shop: {shop['name']}")


def cmd_room_list(args):
    for line in _room_map_lines(_wconn(), args.area):
        print(line)


def cmd_path(args):
    conn = _wconn()
    start = conn.execute("SELECT id FROM rooms WHERE name=?", (args.from_room,)).fetchone()
    goal = conn.execute("SELECT id FROM rooms WHERE name=?", (args.to_room,)).fetchone()
    if not start or not goal:
        print("(unknown room name — check `room list`)")
        return
    edges = conn.execute("SELECT from_room_id, direction, to_room_id FROM exits WHERE to_room_id IS NOT NULL").fetchall()
    graph = {}
    for e in edges:
        graph.setdefault(e["from_room_id"], []).append((e["direction"], e["to_room_id"]))
    q = deque([(start["id"], [])])
    seen = {start["id"]}
    while q:
        node, path = q.popleft()
        if node == goal["id"]:
            if not path:
                print("(already there)")
                return
            names = {r["id"]: r["name"] for r in conn.execute("SELECT id, name FROM rooms").fetchall()}
            print("directions: " + " -> ".join(d for d, _ in path))
            print("route: " + args.from_room + " -> " + " -> ".join(names[n] for _, n in path))
            return
        for direction, nxt in graph.get(node, []):
            if nxt not in seen:
                seen.add(nxt)
                q.append((nxt, path + [(direction, nxt)]))
    print("(no known path — some connecting exits may not be recorded yet)")


def cmd_shop_add(args):
    conn = _wconn()
    with conn:
        room_id = _get_or_create_room(conn, args.room) if args.room else None
        conn.execute(
            "INSERT INTO shops (name, room_id, notes) VALUES (?,?,?) "
            "ON CONFLICT(name) DO UPDATE SET "
            "room_id=COALESCE(excluded.room_id, shops.room_id), "
            "notes=COALESCE(excluded.notes, shops.notes)",
            (args.name, room_id, args.notes),
        )
    print(f"shop: {args.name}")


def cmd_shop_item(args):
    conn = _wconn()
    with conn:
        shop = conn.execute("SELECT id FROM shops WHERE name=?", (args.shop,)).fetchone()
        shop_id = shop["id"] if shop else conn.execute("INSERT INTO shops (name) VALUES (?)", (args.shop,)).lastrowid
        conn.execute(
            "INSERT INTO shop_items (shop_id, item_name, price, notes) VALUES (?,?,?,?)",
            (shop_id, args.item, args.price, args.notes),
        )
    print(f"shop item: {args.shop} sells {args.item} for {args.price}g")


def cmd_shop_show(args):
    conn = _wconn()
    shop = conn.execute("SELECT * FROM shops WHERE name=?", (args.name,)).fetchone()
    if not shop:
        print("(unknown shop)")
        return
    room = conn.execute("SELECT name FROM rooms WHERE id=?", (shop["room_id"],)).fetchone() if shop["room_id"] else None
    print(shop["name"] + (f" ({room['name']})" if room else ""))
    for item in conn.execute("SELECT * FROM shop_items WHERE shop_id=? ORDER BY item_name", (shop["id"],)).fetchall():
        note = f" — {item['notes']}" if item["notes"] else ""
        print(f"  {item['item_name']}: {item['price']}g{note}")


def cmd_npc_add(args):
    conn = _wconn()
    with conn:
        room_id = _get_or_create_room(conn, args.room) if args.room else None
        conn.execute(
            "INSERT INTO npcs_monsters (name, kind, room_id, danger, loot, notes) VALUES (?,?,?,?,?,?) "
            "ON CONFLICT(name, room_id) DO UPDATE SET "
            "danger=COALESCE(excluded.danger, npcs_monsters.danger), "
            "loot=COALESCE(excluded.loot, npcs_monsters.loot), "
            "notes=COALESCE(excluded.notes, npcs_monsters.notes)",
            (args.name, args.kind, room_id, args.danger, args.loot, args.notes),
        )
    print(f"{args.kind}: {args.name}")


def cmd_npc_list(args):
    for line in _npc_lines(_wconn(), args.room, args.kind):
        print(line)


def cmd_lead_add(args):
    conn = _wconn()
    with conn:
        cur = conn.execute("INSERT INTO leads (description) VALUES (?)", (args.text,))
    print(f"lead #{cur.lastrowid} added.")


def cmd_lead_list(args):
    for line in _lead_lines(_wconn(), args.unresolved):
        print(line)


def cmd_lead_resolve(args):
    conn = _wconn()
    with conn:
        cur = conn.execute("UPDATE leads SET resolved=1 WHERE id=?", (args.id,))
    print(f"lead #{args.id} resolved." if cur.rowcount else f"No lead with id {args.id}")


def cmd_dump(args):
    pconn, wconn = _pconn(), _wconn()
    if args.json:
        data = {
            "goal": _goal_line(pconn),
            "persona": _persona_lines(pconn),
            "tasks": _task_lines(pconn),
            "snapshot": _snapshot_lines(pconn),
            "inventory": _inventory_lines(pconn),
            "milestones": _milestone_lines(pconn),
            "observations": _observation_lines(pconn),
            "map": _room_map_lines(wconn),
            "shops": _shop_lines(wconn),
            "npcs_monsters": _npc_lines(wconn),
            "leads": _lead_lines(wconn),
        }
        print(json.dumps(data, indent=2))
        return

    def section(title, lines):
        print(f"\n{title}:")
        for line in lines:
            print(f"  {line}")

    print("=" * 60)
    print("PLAYER MEMORY")
    print("=" * 60)
    print(f"\nGoal: {_goal_line(pconn)}")
    section("Persona", _persona_lines(pconn))
    section("Task Queue", _task_lines(pconn))
    section("Character Snapshot", _snapshot_lines(pconn))
    section("Inventory & Equipment", _inventory_lines(pconn))
    section("Milestones (latest 15)", _milestone_lines(pconn, 15))
    section("Recent Observations (latest 10)", _observation_lines(pconn, limit=10))

    print("\n" + "=" * 60)
    print("WORLD MEMORY")
    print("=" * 60)
    section("Map", _room_map_lines(wconn))
    section("Shops", _shop_lines(wconn))
    section("NPCs & Monsters", _npc_lines(wconn))
    section("Unresolved Leads", _lead_lines(wconn, unresolved_only=True))


# --- argparse wiring -----------------------------------------------------


def build_parser():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init", help="Create/upgrade both databases (idempotent).").set_defaults(func=cmd_init)
    dump = sub.add_parser("dump", help="Print everything: goal, tasks, snapshot, inventory, milestones, map, shops, NPCs, leads.")
    dump.add_argument("--json", action="store_true", help="Emit JSON instead of a human-readable report.")
    dump.set_defaults(func=cmd_dump)

    goal = sub.add_parser("goal", help="This character's current goal.")
    goal_sub = goal.add_subparsers(dest="goal_cmd", required=True)
    goal_sub.add_parser("get", help="Show the current goal.").set_defaults(func=cmd_goal_get)
    gs = goal_sub.add_parser("set", help="Set/replace the current goal.")
    gs.add_argument("text")
    gs.set_defaults(func=cmd_goal_set)

    persona = sub.add_parser("persona", help="How this player prefers to play - steers in-game decisions.")
    persona_sub = persona.add_subparsers(dest="persona_cmd", required=True)
    persona_sub.add_parser("show", help="Show the current persona.").set_defaults(func=cmd_persona_show)
    ps = persona_sub.add_parser("set", help="Set one or more fields, e.g. `persona set risk_tolerance=low exploration_style=thorough`.")
    ps.add_argument("pairs", nargs="+", help=(
        "key=value pairs. playstyle: free text (e.g. 'aggressive melee', 'cautious completionist'). "
        f"exploration_style: {'/'.join(sorted(PERSONA_EXPLORATION_STYLES))}. "
        f"risk_tolerance: {'/'.join(sorted(PERSONA_RISK_TOLERANCES))}. notes: free text."
    ))
    ps.set_defaults(func=cmd_persona_set)

    snap = sub.add_parser("snapshot", help="Live character stats (level, HP, gold, location, ...).")
    snap_sub = snap.add_subparsers(dest="snapshot_cmd", required=True)
    snap_sub.add_parser("show", help="Show the current snapshot.").set_defaults(func=cmd_snapshot_show)
    ss = snap_sub.add_parser("set", help="Update one or more fields, e.g. `snapshot set level=4 gold=42`.")
    ss.add_argument("pairs", nargs="+", help="key=value pairs; valid keys: " + ", ".join(sorted(SNAPSHOT_FIELDS)))
    ss.set_defaults(func=cmd_snapshot_set)

    inv = sub.add_parser("inventory", help="Carried/worn/wielded items.")
    inv_sub = inv.add_subparsers(dest="inventory_cmd", required=True)
    inv_sub.add_parser("list", help="List inventory.").set_defaults(func=cmd_inventory_list)
    ia = inv_sub.add_parser("add", help="Add an item.")
    ia.add_argument("item")
    ia.add_argument("--slot", required=True, choices=["wielded", "held", "worn", "carrying"])
    ia.add_argument("--notes")
    ia.set_defaults(func=cmd_inventory_add)
    ir = inv_sub.add_parser("remove", help="Remove an item by exact name.")
    ir.add_argument("item")
    ir.set_defaults(func=cmd_inventory_remove)

    mile = sub.add_parser("milestone", help="Permanent log of completed achievements.")
    mile_sub = mile.add_subparsers(dest="milestone_cmd", required=True)
    ma = mile_sub.add_parser("add", help="Log a milestone.")
    ma.add_argument("text")
    ma.set_defaults(func=cmd_milestone_add)
    ml = mile_sub.add_parser("list", help="List recent milestones.")
    ml.add_argument("--limit", type=int, default=20)
    ml.set_defaults(func=cmd_milestone_list)

    task = sub.add_parser("task", help="The dynamic task queue — update priorities continuously as play happens.")
    task_sub = task.add_subparsers(dest="task_cmd", required=True)
    ta = task_sub.add_parser("add", help="Add a task.")
    ta.add_argument("subject")
    ta.add_argument("--status", choices=["active", "pending", "blocked", "done"])
    ta.add_argument("--priority", type=float, help="Lower = more urgent. Omit to append to the end of the queue.")
    ta.add_argument("--reason", help="Why it matters, or why it's blocked.")
    ta.add_argument("--urgent", action="store_true",
                     help="Insert ahead of everything, mark active, and demote the current active task back to pending.")
    ta.add_argument("--before", type=int, metavar="ID", help="Insert with a priority just ahead of task ID.")
    ta.set_defaults(func=cmd_task_add)
    tl = task_sub.add_parser("list", help="List tasks, most urgent first.")
    tl.add_argument("--status", choices=["active", "pending", "blocked", "done"])
    tl.set_defaults(func=cmd_task_list)
    task_sub.add_parser("next", help="Show the single task to work on right now.").set_defaults(func=cmd_task_next)
    tu = task_sub.add_parser("update", help="Update a task's status/priority/reason/subject.")
    tu.add_argument("id", type=int)
    tu.add_argument("--status", choices=["active", "pending", "blocked", "done"])
    tu.add_argument("--priority", type=float)
    tu.add_argument("--reason")
    tu.add_argument("--subject")
    tu.set_defaults(func=cmd_task_update)
    td = task_sub.add_parser("done", help="Mark complete: folds it into milestones and removes it from the queue.")
    td.add_argument("id", type=int)
    td.add_argument("--note", help="Milestone text (defaults to the task's subject).")
    td.set_defaults(func=cmd_task_done)

    obs = sub.add_parser("observation", help="Raw, timestamped log of notable game output — log liberally.")
    obs_sub = obs.add_subparsers(dest="observation_cmd", required=True)
    oa = obs_sub.add_parser("add", help="Log an observation.")
    oa.add_argument("text")
    oa.add_argument("--category", default="other", choices=["room", "combat", "npc", "system", "other"])
    oa.add_argument("--room")
    oa.set_defaults(func=cmd_observation_add)
    ol = obs_sub.add_parser("list", help="List recent observations.")
    ol.add_argument("--category", choices=["room", "combat", "npc", "system", "other"])
    ol.add_argument("--room")
    ol.add_argument("--limit", type=int, default=20)
    ol.set_defaults(func=cmd_observation_list)

    room = sub.add_parser("room", help="Known rooms and their exits (the map).")
    room_sub = room.add_subparsers(dest="room_cmd", required=True)
    ra = room_sub.add_parser("add", help="Record/update a room.")
    ra.add_argument("name")
    ra.add_argument("--area")
    ra.add_argument("--notable")
    ra.set_defaults(func=cmd_room_add)
    re_ = room_sub.add_parser("exit", help="Record a traversed/observed exit (auto-creates both rooms).")
    re_.add_argument("from_room")
    re_.add_argument("direction")
    re_.add_argument("to_room", nargs="?", help="Omit if the destination hasn't been confirmed yet.")
    re_.set_defaults(func=cmd_room_exit)
    rs = room_sub.add_parser("show", help="Show a room's exits, NPCs, and shop.")
    rs.add_argument("name")
    rs.set_defaults(func=cmd_room_show)
    rl = room_sub.add_parser("list", help="List all known rooms with their exits.")
    rl.add_argument("--area")
    rl.set_defaults(func=cmd_room_list)

    path = sub.add_parser("path", help="Shortest known route between two rooms (BFS over recorded exits).")
    path.add_argument("from_room")
    path.add_argument("to_room")
    path.set_defaults(func=cmd_path)

    shop = sub.add_parser("shop", help="Shops and what they buy/sell.")
    shop_sub = shop.add_subparsers(dest="shop_cmd", required=True)
    sa = shop_sub.add_parser("add", help="Record a shop.")
    sa.add_argument("name")
    sa.add_argument("--room")
    sa.add_argument("--notes")
    sa.set_defaults(func=cmd_shop_add)
    si = shop_sub.add_parser("item", help="Record an item a shop sells.")
    si.add_argument("shop")
    si.add_argument("item")
    si.add_argument("price", type=int)
    si.add_argument("--notes")
    si.set_defaults(func=cmd_shop_item)
    sh = shop_sub.add_parser("show", help="Show a shop's stock.")
    sh.add_argument("name")
    sh.set_defaults(func=cmd_shop_show)

    npc = sub.add_parser("npc", help="NPCs and monsters.")
    npc_sub = npc.add_subparsers(dest="npc_cmd", required=True)
    na = npc_sub.add_parser("add", help="Record an NPC or monster.")
    na.add_argument("name")
    na.add_argument("--kind", required=True, choices=["npc", "monster"])
    na.add_argument("--room")
    na.add_argument("--danger")
    na.add_argument("--loot")
    na.add_argument("--notes")
    na.set_defaults(func=cmd_npc_add)
    nl = npc_sub.add_parser("list", help="List NPCs/monsters.")
    nl.add_argument("--room")
    nl.add_argument("--kind", choices=["npc", "monster"])
    nl.set_defaults(func=cmd_npc_list)

    lead = sub.add_parser("lead", help="Unexplored/unresolved leads worth following up.")
    lead_sub = lead.add_subparsers(dest="lead_cmd", required=True)
    la = lead_sub.add_parser("add", help="Add a lead.")
    la.add_argument("text")
    la.set_defaults(func=cmd_lead_add)
    ll = lead_sub.add_parser("list", help="List leads.")
    ll.add_argument("--unresolved", action="store_true")
    ll.set_defaults(func=cmd_lead_list)
    lr = lead_sub.add_parser("resolve", help="Mark a lead resolved.")
    lr.add_argument("id", type=int)
    lr.set_defaults(func=cmd_lead_resolve)

    return p, sub


def main():
    parser, _sub = build_parser()
    args = parser.parse_args()
    init_dbs()
    args.func(args)


if __name__ == "__main__":
    main()
