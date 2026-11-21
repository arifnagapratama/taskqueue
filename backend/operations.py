"""MCP tools use the same transactions and validation as the UI API."""
import time
from typing import get_args

from backend import store
from backend.contracts import ReleaseStatus



def list_projects() -> list[dict]:
    """List tracked projects."""
    return store.list_projects()


def create_project(project_id: str, name: str) -> dict:
    """Create an empty project with a stable id."""
    return store.create_project(project_id, name)


def get_project(project_id: str) -> dict:
    """Read tasks in queue order, epics, ADRs, rules and the current project revision."""
    return store.get_state(project_id)


def upsert_entity(project_id: str, kind: str, entity: dict, revision: int) -> dict:
    """Create or update an entity using UI field names and an expected revision.

    Tasks need id,t,s,d,epic,adrs,bl,l,ac,log. Epics need id,t,s,d.
    ADRs need id,t,s,ctx,dec,cons,sup. Rules need id,t,s,d. Read get_project before writing.
    Use claim_task to start AI work so blockers and existing claims are checked.
    """
    if kind not in store.KINDS:
        raise store.StoreError(400, "Invalid entity kind")

    def operation(state):
        if state["revision"] != revision:
            raise store.StoreError(409, "Stale revision; read project again")
        current = next((item for item in state[kind] if item["id"] == entity.get("id")), None)
        if kind == "specs":
            if entity.get("ai") != (current or {}).get("ai"):
                raise store.StoreError(400, "Use claim_task/release_task to change AI assignment")
            if entity.get("s") == "in_progress" and entity.get("bl"):
                accepted = {adr["id"] for adr in state["adrs"] if adr["s"] == "ACCEPTED"}
                if any(id not in accepted for id in entity["bl"]):
                    raise store.StoreError(409, "Task has unresolved ADR blockers")
        updated = {**entity, "u": int(time.time() * 1000)}
        if kind == "specs":
            updated["log"].insert(0, [updated["u"], "ai-agent", "task created" if current is None else "task updated"])
        if current is None:
            state[kind].append(updated)
        else:
            state[kind][state[kind].index(current)] = updated
        return updated

    return store.mutate(project_id, operation)


def claim_task(project_id: str, task_id: str, agent: str = "ai-agent", step: str = "") -> dict:
    """Atomically claim an unassigned task that is neither blocked, deferred nor finished."""
    if not agent.strip():
        raise store.StoreError(400, "Agent name is required")

    def operation(state):
        task = find_task(state, task_id)
        accepted = {adr["id"] for adr in state["adrs"] if adr["s"] == "ACCEPTED"}
        if task.get("ai") or task["s"] in ("deferred", "finished") or any(id not in accepted for id in task["bl"]):
            raise store.StoreError(409, "Task is claimed, deferred, finished, or blocked")
        store.require_finished_dependencies(
            task["depends_on"], {item["id"] for item in state["specs"] if item["s"] == "finished"},
        )
        now = int(time.time() * 1000)
        task.update(s="in_progress", u=now, ai={"agent": agent, "since": now, "step": step})
        task["log"].insert(0, [now, agent, "AI claimed task"])
        return task

    return store.mutate(project_id, operation)


def find_task(state, task_id):
    task = next((item for item in state["specs"] if item["id"] == task_id), None)
    if task is None:
        raise store.StoreError(404, "Task not found")
    return task


def release_task(project_id: str, task_id: str, agent: str, status: ReleaseStatus = "todo") -> dict:
    """Release a claim and optionally send it to verification, defer it or finish it."""
    if status not in get_args(ReleaseStatus):
        raise store.StoreError(400, "Release status must be deferred, todo, verify, or finished")

    def operation(state):
        task = find_task(state, task_id)
        if not task.get("ai") or task["ai"]["agent"] != agent:
            raise store.StoreError(409, "Task belongs to another agent or has no claim")
        if status == "finished" and any(test["st"] != "pass" for test in task["ac"]):
            raise store.StoreError(409, "Acceptance tests must pass before completion")
        task.pop("ai", None)
        task.update(s=status, u=int(time.time() * 1000))
        task["log"].insert(0, [task["u"], agent, f"AI released task → {status}"])
        return task

    return store.mutate(project_id, operation)


def report_test(project_id: str, task_id: str, test_id: str, status: str, agent: str) -> dict:
    """Report a pending/pass/fail acceptance result for a task claimed by this agent."""
    if status not in ("pending", "pass", "fail"):
        raise store.StoreError(400, "Invalid test status")

    def operation(state):
        task = find_task(state, task_id)
        if not task.get("ai") or task["ai"]["agent"] != agent:
            raise store.StoreError(409, "Claim task before reporting tests")
        test = next((test for test in task["ac"] if test["id"] == test_id), None)
        if test is None:
            raise store.StoreError(404, "Acceptance test not found")
        now = int(time.time() * 1000)
        test.update(st=status, run=None if status == "pending" else now)
        task["u"] = now
        task["log"].insert(0, [now, agent, f"test {test_id} → {status}"])
        return test

    return store.mutate(project_id, operation)
