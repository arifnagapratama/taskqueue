"""Shared SQLite storage for REST and MCP."""
import json
import os
import re
import sqlite3
from pathlib import Path

DB_PATH = Path(os.environ.get("DATABASE_PATH", "data/task-queue.sqlite3"))
STATIC_PATH = os.environ.get("STATIC_PATH", "/app/dist")
KINDS = ("specs", "epics", "adrs")


def connect():
    db = sqlite3.connect(DB_PATH, timeout=10)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    return db


def initialize():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with connect() as db:
        db.execute("PRAGMA journal_mode=WAL")
        db.executescript("""
            CREATE TABLE IF NOT EXISTS projects (
                id TEXT PRIMARY KEY, name TEXT NOT NULL, revision INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS entities (
                project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                kind TEXT NOT NULL CHECK(kind IN ('specs','epics','adrs')),
                id TEXT NOT NULL, position INTEGER NOT NULL, payload TEXT NOT NULL,
                PRIMARY KEY(project_id,kind,id)
            );
            PRAGMA user_version=1;
        """)
        db.execute("INSERT OR IGNORE INTO projects(id,name) VALUES ('default','Default project')")


def validate_state(state):
    if not isinstance(state, dict):
        raise ValueError("Expected a state object")
    indexes = {}
    for kind in KINDS:
        items = state.get(kind)
        if not isinstance(items, list):
            raise ValueError(f"{kind} must be an array")
        indexes[kind] = set()
        for item in items:
            if not isinstance(item, dict) or not isinstance(item.get("id"), str) or not item["id"]:
                raise ValueError("Each entity needs an id")
            if item["id"] in indexes[kind]:
                raise ValueError("Duplicate entity id")
            indexes[kind].add(item["id"])
            if not isinstance(item.get("t"), str) or not item["t"].strip():
                raise ValueError("Each entity needs a title")
            statuses = {"specs": ("todo", "in_progress", "finished"), "epics": ("OPEN", "CLOSED"),
                        "adrs": ("PROPOSED", "ACCEPTED", "SUPERSEDED", "DEPRECATED")}
            if item.get("s") not in statuses[kind]:
                raise ValueError(f"Invalid {kind} status")
            text_keys = {"specs": ("d",), "epics": ("d",), "adrs": ("ctx", "dec", "cons")}
            if any(not isinstance(item.get(key), str) for key in text_keys[kind]):
                raise ValueError("Invalid description fields")
            if kind == "specs":
                for key in ("l", "adrs", "bl"):
                    if not isinstance(item.get(key), list) or any(not isinstance(v, str) for v in item[key]):
                        raise ValueError(f"{key} must contain strings")
                if not isinstance(item.get("log"), list) or not isinstance(item.get("ac"), list):
                    raise ValueError("Tasks need history and acceptance tests")
                for test in item["ac"]:
                    if not isinstance(test, dict) or not isinstance(test.get("id"), str) or not isinstance(test.get("t"), str) or test.get("st") not in ("pending", "pass", "fail") or test.get("mode") not in ("auto", "manual") or not isinstance(test.get("steps"), list) or any(not isinstance(v, str) for v in test["steps"]):
                        raise ValueError("Invalid acceptance test")
    for item in state["specs"]:
        if item.get("epic") and item["epic"] not in indexes["epics"]:
            raise ValueError("Unknown epic reference")
        if any(v not in indexes["adrs"] for v in item["adrs"] + item["bl"]):
            raise ValueError("Unknown ADR reference")
    superseded = set()
    links = {item["id"]: item.get("sup", "") for item in state["adrs"]}
    for item_id, target in links.items():
        if target and (target not in indexes["adrs"] or target in superseded):
            raise ValueError("Invalid supersedes reference")
        if target:
            superseded.add(target)
        visited = {item_id}
        while target:
            if target in visited:
                raise ValueError("Supersedes cycle")
            visited.add(target)
            target = links[target]


class StoreError(Exception):
    def __init__(self, status, message):
        self.status, self.message = status, message
        super().__init__(message)


def list_projects():
    with connect() as db:
        return [dict(row) for row in db.execute("SELECT * FROM projects ORDER BY name")]


def create_project(project_id, name):
    if not isinstance(project_id, str) or not re.fullmatch(r"[a-zA-Z0-9_-]{1,80}", project_id) or not isinstance(name, str) or not name.strip() or len(name) > 200:
        raise StoreError(400, "Provide a valid project id and name")
    try:
        with connect() as db:
            db.execute("INSERT INTO projects(id,name) VALUES (?,?)", (project_id, name.strip()))
    except sqlite3.IntegrityError:
        raise StoreError(409, "Project id already exists") from None
    return {"id": project_id, "name": name.strip(), "revision": 0}


def read_state(db, project_id):
    project = db.execute("SELECT revision FROM projects WHERE id=?", (project_id,)).fetchone()
    if project is None:
        raise StoreError(404, "Project not found")
    state = {kind: [] for kind in KINDS}
    state["revision"] = project["revision"]
    for row in db.execute("SELECT kind,payload FROM entities WHERE project_id=? ORDER BY position", (project_id,)):
        state[row["kind"]].append(json.loads(row["payload"]))
    return state


def get_state(project_id):
    with connect() as db:
        db.execute("BEGIN")
        return read_state(db, project_id)


def write_state(db, project_id, state):
    try:
        validate_state(state)
    except (ValueError, TypeError, KeyError) as error:
        raise StoreError(400, str(error)) from error
    if type(state.get("revision")) is not int:
        raise StoreError(400, "revision must be an integer")
    current = read_state(db, project_id)
    if state["revision"] != current["revision"]:
        raise StoreError(409, "Project changed in another session. Reload before editing.")
    db.execute("DELETE FROM entities WHERE project_id=?", (project_id,))
    for kind in KINDS:
        db.executemany("INSERT INTO entities VALUES (?,?,?,?,?)", [
            (project_id, kind, item["id"], i, json.dumps(item)) for i, item in enumerate(state[kind])
        ])
    db.execute("UPDATE projects SET revision=revision+1 WHERE id=?", (project_id,))
    return {"revision": current["revision"] + 1}


def put_state(project_id, state):
    with connect() as db:
        db.execute("BEGIN IMMEDIATE")
        return write_state(db, project_id, state)


def mutate(project_id, operation):
    with connect() as db:
        db.execute("BEGIN IMMEDIATE")
        state = read_state(db, project_id)
        result = operation(state)
        revision = write_state(db, project_id, state)
        return {**revision, "result": result}
