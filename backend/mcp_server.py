"""Typed MCP boundary with structured results and actionable tool errors."""
import json
import os
import ipaddress
import sqlite3
from typing import Annotated, Literal

from mcp.server.fastmcp import Context, FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import CallToolResult, TextContent, ToolAnnotations

from starlette.requests import Request

from backend import store, operations
from backend.contracts import (
    Entity, EntityInput, Error, Project, ProjectList, ProjectState, ReleaseStatus, Result,
    Task, TestReport, entity_view, test_view, to_storage,
)

def transport_security():
    hosts = ["127.0.0.1:*", "localhost:*", "[::1]:*"]
    origins = ["http://127.0.0.1:*", "http://localhost:*", "http://[::1]:*"]
    configured_ip = os.environ.get("TASKQUEUE_IP")
    if configured_ip:
        address = ipaddress.ip_address(configured_ip)
        host = f"[{address}]" if address.version == 6 else str(address)
        hosts.append(f"{host}:5443")
        origins.append(f"https://{host}:5443")
    return TransportSecuritySettings(allowed_hosts=hosts, allowed_origins=origins)


mcp = FastMCP("Task Queue", stateless_http=True, json_response=True, streamable_http_path="/",
              instructions="For project-scoped tools, omit project_id when the client sends x-project-id.",
              transport_security=transport_security())
READ = ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=False)
WRITE = ToolAnnotations(readOnlyHint=False, destructiveHint=False, openWorldHint=False)


def resolve_project_id(project_id: str | None, ctx: Context) -> str:
    if project_id is None:
        request = ctx.request_context.request
        if isinstance(request, Request):
            project_id = request.headers.get("x-project-id")
    if project_id is None or not project_id.strip():
        raise store.StoreError(400, "Provide project_id or configure the x-project-id HTTP header")
    return project_id.strip()


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
def get_project(ctx: Context, project_id: str | None = None) -> Annotated[CallToolResult, Result[ProjectState]]:
    """Read project tasks, epics, ADRs and revision. Defaults to the x-project-id header."""
    def operation():
        selected_id = resolve_project_id(project_id, ctx)
        state = store.get_state(selected_id)
        return ProjectState(project_id=selected_id, tasks=[entity_view("specs", t) for t in state["specs"]],
                            epics=[entity_view("epics", e) for e in state["epics"]],
                            adrs=[entity_view("adrs", a) for a in state["adrs"]]), state["revision"]
    return respond(Result[ProjectState], operation)


@mcp.tool(annotations=WRITE)
def upsert_entity(entity: EntityInput, revision: int, ctx: Context,
                  project_id: str | None = None) -> Annotated[CallToolResult, Result[Entity]]:
    """Create or replace task/epic/adr editable fields at an expected project revision.

    Defaults to the x-project-id header. Use the current revision. Task assignment and history are
    server managed; use claim_task, report_test and release_task for AI work.
    """
    def operation():
        selected_id = resolve_project_id(project_id, ctx)
        kind, item = to_storage(entity)
        state = store.get_state(selected_id)
        current = next((e for e in state[kind] if e["id"] == item["id"]), None)
        if kind == "specs":
            item["log"] = list((current or {}).get("log", []))
            if current:
                for field, storage_key in (("priority", "priority"), ("task_kind", "kind"), ("depends_on", "depends_on")):
                    if field not in entity.model_fields_set:
                        item[storage_key] = current[storage_key]
            if current and current.get("ai"):
                item["ai"] = current["ai"]
                if item["s"] != "in_progress":
                    raise store.StoreError(409, "Use release_task to change a claimed task's status")
        result = operations.upsert_entity(selected_id, kind, item, revision)
        return entity_view(kind, result["result"]), result["revision"]
    return respond(Result[Entity], operation)


@mcp.tool(annotations=WRITE)
def claim_task(task_id: str, ctx: Context, agent: str = "ai-agent", step: str = "",
               project_id: str | None = None) -> Annotated[CallToolResult, Result[Task]]:
    """Claim a task after prerequisites finish and ADR blockers are accepted. Defaults to x-project-id."""
    def operation():
        result = operations.claim_task(resolve_project_id(project_id, ctx), task_id, agent, step)
        return entity_view("specs", result["result"]), result["revision"]
    return respond(Result[Task], operation)


@mcp.tool(annotations=WRITE)
def release_task(task_id: str, agent: str, ctx: Context, status: ReleaseStatus = "todo",
                 project_id: str | None = None) -> Annotated[CallToolResult, Result[Task]]:
    """Release your claim. Finishing requires passing tests. Defaults to the x-project-id header."""
    def operation():
        result = operations.release_task(resolve_project_id(project_id, ctx), task_id, agent, status)
        return entity_view("specs", result["result"]), result["revision"]
    return respond(Result[Task], operation)


@mcp.tool(annotations=WRITE)
def report_test(task_id: str, test_id: str, status: Literal["pending", "pass", "fail"], agent: str,
                ctx: Context, project_id: str | None = None) -> Annotated[CallToolResult, Result[TestReport]]:
    """Record a test result for your claimed task. Defaults to the x-project-id header."""
    def operation():
        result = operations.report_test(resolve_project_id(project_id, ctx), task_id, test_id, status, agent)
        return TestReport(task_id=task_id, test=test_view(result["result"])), result["revision"]
    return respond(Result[TestReport], operation)
