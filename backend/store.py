"""Shared SQLite storage for REST and MCP."""
import json
import os
import re
import sqlite3
from graphlib import CycleError, TopologicalSorter
from pathlib import Path
from typing import get_args

from backend.contracts import (
    DEFAULT_PRIORITY, DEFAULT_TASK_KIND, PRIORITY_PATTERN, TASK_KIND_PATTERN, RuleStatus, TaskStatus,
)

DB_PATH = Path(os.environ.get("DATABASE_PATH", "data/task-queue.sqlite3"))
STATIC_PATH = os.environ.get("STATIC_PATH", "/app/dist")
KINDS = ("specs", "epics", "adrs", "rules")
TASK_METADATA = {
    "priority": (DEFAULT_PRIORITY, PRIORITY_PATTERN),
    "kind": (DEFAULT_TASK_KIND, TASK_KIND_PATTERN),
}
STATUSES = {
    "specs": get_args(TaskStatus),
    "epics": ("OPEN", "CLOSED"),
    "adrs": ("PROPOSED", "ACCEPTED", "SUPERSEDED", "DEPRECATED"),
    "rules": get_args(RuleStatus),
}
_change_listeners = set()


def add_change_listener(listener):
    _change_listeners.add(listener)


def notify_changed(project_id, revision):
    for listener in tuple(_change_listeners):
        listener(project_id, revision)


def connect():
    db = sqlite3.connect(DB_PATH, timeout=10)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    return db


def initialize():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with connect() as db:
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("BEGIN IMMEDIATE")
        db.execute("""
            CREATE TABLE IF NOT EXISTS projects (
                id TEXT PRIMARY KEY, name TEXT NOT NULL, revision INTEGER NOT NULL DEFAULT 0
            );
        """)
        version = db.execute("PRAGMA user_version").fetchone()[0]
        migrate_entities = version < 2 and db.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='entities'"
        ).fetchone()
        if migrate_entities:
            db.execute("ALTER TABLE entities RENAME TO entities_v1")
        db.execute("""
            CREATE TABLE IF NOT EXISTS entities (
                project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                kind TEXT NOT NULL CHECK(kind IN ('specs','epics','adrs','rules')),
                id TEXT NOT NULL, position INTEGER NOT NULL, payload TEXT NOT NULL,
                PRIMARY KEY(project_id,kind,id)
            );
        """)
        if migrate_entities:
            db.execute("INSERT INTO entities SELECT project_id, kind, id, position, payload FROM entities_v1")
            db.execute("DROP TABLE entities_v1")
        if version < 2:
            db.execute("PRAGMA user_version=2")
        db.execute("INSERT OR IGNORE INTO projects(id,name) VALUES ('default','Default project')")


def validate_state(state):
    if not isinstance(state, dict):
        raise ValueError("Expected a state object")
    indexes = {}
    for kind in KINDS:
        items = state.get(kind, [] if kind == "rules" else None)
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
            if item.get("s") not in STATUSES[kind]:
                raise ValueError(f"Invalid {kind} status")
            text_keys = ("ctx", "dec", "cons") if kind == "adrs" else ("d",)
            if any(not isinstance(item.get(key), str) for key in text_keys):
                raise ValueError("Invalid description fields")
            if kind == "specs":
                for field, (_, pattern) in TASK_METADATA.items():
                    if field in item and (
                        not isinstance(item[field], str) or not re.fullmatch(pattern, item[field])
                    ):
                        raise ValueError(f"Invalid task {field}")
                for key in ("l", "adrs", "bl"):
                    if not isinstance(item.get(key), list) or any(not isinstance(v, str) for v in item[key]):
                        raise ValueError(f"{key} must contain strings")
                dependencies = item.get("depends_on", [])
                if not isinstance(dependencies, list) or any(not isinstance(v, str) for v in dependencies):
                    raise ValueError("depends_on must contain task IDs")
                if len(dependencies) != len(set(dependencies)):
                    raise ValueError("Duplicate task dependency")
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
        item = json.loads(row["payload"])
        if row["kind"] == "specs":
            item.setdefault("depends_on", [])
            for field, (default, _) in TASK_METADATA.items():
                item.setdefault(field, default)
        state[row["kind"]].append(item)
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
    state.setdefault("rules", current["rules"])
    current_tasks = {task["id"]: task for task in current["specs"]}
    for task in state["specs"]:
        task.setdefault("depends_on", current_tasks.get(task["id"], {}).get("depends_on", []))
    validate_task_links(state["specs"])
    finished = {task["id"] for task in state["specs"] if task["s"] == "finished"}
    for task in state["specs"]:
        previous = current_tasks.get(task["id"], {})
        if task["s"] == "in_progress":
            dependencies = task["depends_on"]
            if previous.get("s") == "in_progress":
                dependencies = [task_id for task_id in dependencies if task_id not in previous["depends_on"]]
            require_finished_dependencies(dependencies, finished)
        for field, (default, _) in TASK_METADATA.items():
            task.setdefault(field, previous.get(field, default))
    db.execute("DELETE FROM entities WHERE project_id=?", (project_id,))
    for kind in KINDS:
        db.executemany("INSERT INTO entities VALUES (?,?,?,?,?)", [
            (project_id, kind, item["id"], i, json.dumps(item)) for i, item in enumerate(state[kind])
        ])
    db.execute("UPDATE projects SET revision=revision+1 WHERE id=?", (project_id,))
    revision = current["revision"] + 1
    return {"revision": revision}


def require_finished_dependencies(dependencies, finished):
    pending = [task_id for task_id in dependencies if task_id not in finished]
    if pending:
        raise StoreError(409, "Finish prerequisite tasks first: " + ", ".join(pending))


def validate_task_links(tasks):
    links = {task["id"]: task["depends_on"] for task in tasks}
    for task_id, dependencies in links.items():
        for dependency in dependencies:
            if dependency not in links:
                raise StoreError(400, f"Task {task_id} depends on missing task {dependency}")
    try:
        TopologicalSorter(links).prepare()
    except CycleError as error:
        raise StoreError(400, "Task dependency cycle: " + " → ".join(error.args[1])) from error


def put_state(project_id, state):
    with connect() as db:
        db.execute("BEGIN IMMEDIATE")
        result = write_state(db, project_id, state)
    notify_changed(project_id, result["revision"])
    return result


def mutate(project_id, operation):
    with connect() as db:
        db.execute("BEGIN IMMEDIATE")
        state = read_state(db, project_id)
        result = operation(state)
        revision = write_state(db, project_id, state)
    notify_changed(project_id, revision["revision"])
    return {**revision, "result": result}
