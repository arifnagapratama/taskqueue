"""Typed MCP boundary with structured results and actionable tool errors."""
import json
import sqlite3
from typing import Annotated, Literal

from mcp.server.fastmcp import FastMCP
from mcp.types import CallToolResult, TextContent, ToolAnnotations

from backend import store, operations
from backend.contracts import (
    Entity, EntityInput, Error, Project, ProjectList, ProjectState, Result,
    Task, TestReport, entity_view, test_view, to_storage,
)

mcp = FastMCP("Task Queue", stateless_http=True, json_response=True, streamable_http_path="/")
READ = ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=False)
WRITE = ToolAnnotations(readOnlyHint=False, destructiveHint=False, openWorldHint=False)


def respond(result_type, operation):
    try:
        data, revision = operation()
        result = result_type(ok=True, data=data, revision=revision)
    except store.StoreError as error:
        code = {400: "invalid_input", 404: "not_found", 409: "conflict"}.get(error.status, "invalid_input")
        action = {"conflict": "Read get_project and retry with the latest revision or resolve the task precondition.",
                  "not_found": "Check the project and entity IDs using list_projects/get_project.",
                  "invalid_input": "Correct the input using the tool schema."}[code]
        result = result_type(ok=False, error=Error(code=code, message=error.message, suggested_action=action))
    except sqlite3.Error:
        result = result_type(ok=False, error=Error(code="storage_unavailable", message="Database unavailable",
                                                  suggested_action="Retry later; check the backend if the error persists."))
    payload = result.model_dump(mode="json")
    return CallToolResult(structuredContent=payload, isError=not result.ok,
                          content=[TextContent(type="text", text=json.dumps(payload, ensure_ascii=False))])


@mcp.tool(annotations=READ)
def list_projects() -> Annotated[CallToolResult, Result[ProjectList]]:
    """List projects with their IDs and current revisions."""
    return respond(Result[ProjectList], lambda: (ProjectList(projects=[
        Project(project_id=p["id"], name=p["name"], revision=p["revision"]) for p in store.list_projects()
    ]), None))


@mcp.tool(annotations=WRITE)
def create_project(project_id: str, name: str) -> Annotated[CallToolResult, Result[Project]]:
    """Create an empty project with a stable ID (letters, numbers, underscore or hyphen)."""
    def operation():
        p = store.create_project(project_id, name)
        return Project(project_id=p["id"], name=p["name"], revision=p["revision"]), p["revision"]
    return respond(Result[Project], operation)


@mcp.tool(annotations=READ)
def get_project(project_id: str) -> Annotated[CallToolResult, Result[ProjectState]]:
    """Read project tasks in priority order, epics, ADRs and revision. Timestamps are Unix milliseconds."""
    def operation():
        state = store.get_state(project_id)
        return ProjectState(project_id=project_id, tasks=[entity_view("specs", t) for t in state["specs"]],
                            epics=[entity_view("epics", e) for e in state["epics"]],
                            adrs=[entity_view("adrs", a) for a in state["adrs"]]), state["revision"]
    return respond(Result[ProjectState], operation)


@mcp.tool(annotations=WRITE)
def upsert_entity(project_id: str, entity: EntityInput, revision: int) -> Annotated[CallToolResult, Result[Entity]]:
    """Create or replace task/epic/adr editable fields at an expected project revision.

    Choose entity.kind. Read get_project first. Task assignment and history are
    server managed; use claim_task, report_test and release_task for AI work.
    """
    def operation():
        kind, item = to_storage(entity)
        state = store.get_state(project_id)
        current = next((e for e in state[kind] if e["id"] == item["id"]), None)
        if kind == "specs":
            item["log"] = list((current or {}).get("log", []))
            if current and current.get("ai"):
                item["ai"] = current["ai"]
                if item["s"] != "in_progress":
                    raise store.StoreError(409, "Use release_task to change a claimed task's status")
        result = operations.upsert_entity(project_id, kind, item, revision)
        return entity_view(kind, result["result"]), result["revision"]
    return respond(Result[Entity], operation)


@mcp.tool(annotations=WRITE)
def claim_task(project_id: str, task_id: str, agent: str = "ai-agent", step: str = "") -> Annotated[CallToolResult, Result[Task]]:
    """Atomically claim an unassigned task; rejects unresolved ADR blockers and finished tasks."""
    def operation():
        result = operations.claim_task(project_id, task_id, agent, step)
        return entity_view("specs", result["result"]), result["revision"]
    return respond(Result[Task], operation)


@mcp.tool(annotations=WRITE)
def release_task(project_id: str, task_id: str, agent: str,
                 status: Literal["todo", "finished"] = "todo") -> Annotated[CallToolResult, Result[Task]]:
    """Release your claim. Finishing requires all defined acceptance tests to pass."""
    def operation():
        result = operations.release_task(project_id, task_id, agent, status)
        return entity_view("specs", result["result"]), result["revision"]
    return respond(Result[Task], operation)


@mcp.tool(annotations=WRITE)
def report_test(project_id: str, task_id: str, test_id: str,
                status: Literal["pending", "pass", "fail"], agent: str) -> Annotated[CallToolResult, Result[TestReport]]:
    """Record an acceptance test result for a task claimed by this agent."""
    def operation():
        result = operations.report_test(project_id, task_id, test_id, status, agent)
        return TestReport(task_id=task_id, test=test_view(result["result"])), result["revision"]
    return respond(Result[TestReport], operation)
