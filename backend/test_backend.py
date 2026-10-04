import pytest
from fastapi.testclient import TestClient

from backend import store
from backend.main import app
from backend.operations import claim_task, release_task, report_test, upsert_entity


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    store.DB_PATH = tmp_path_factory.mktemp("queue") / "queue.sqlite3"
    with TestClient(app, base_url="http://localhost:8080") as client:
        yield client


def test_state_persistence_and_isolation(client):
    state = {"revision": 0, "specs": [], "adrs": [], "epics": [
        {"id": "EPIC-1", "t": "Saved", "s": "OPEN", "d": "Description"}
    ]}
    assert client.get("/api/health").status_code == 200
    assert client.put("/api/projects/default/state", json=state).json() == {"revision": 1}
    assert client.put("/api/projects/default/state", json=state).status_code == 409
    assert client.post("/api/projects", json={"id": "other", "name": "Other"}).status_code == 201
    assert client.get("/api/projects/other/state").json()["epics"] == []
    store.initialize()
    assert client.get("/api/projects/default/state").json()["epics"] == state["epics"]
    state["revision"] = 1
    state["epics"][0]["s"] = "invalid"
    assert client.put("/api/projects/default/state", json=state).status_code == 400
    assert client.get("/api/projects/default/state").json()["revision"] == 1


def test_mcp_workflow(client):
    store.create_project("workflow", "Workflow")
    task = {"id": "TASK-1", "t": "Task", "s": "todo", "d": "", "epic": "", "adrs": ["ADR-1"],
            "bl": ["ADR-1"], "l": [], "log": [], "ac": [
                {"id": "AT-1", "t": "Check", "st": "pending", "mode": "auto", "steps": ["Given a task"], "ref": "", "run": None}
            ]}
    adr = {"id": "ADR-1", "t": "Decision", "s": "PROPOSED", "ctx": "", "dec": "", "cons": "", "sup": ""}
    upsert_entity("workflow", "adrs", adr, 0)
    upsert_entity("workflow", "specs", task, 1)
    with pytest.raises(store.StoreError, match="blocked"):
        claim_task("workflow", "TASK-1")
    adr["s"] = "ACCEPTED"
    upsert_entity("workflow", "adrs", adr, 2)
    claim_task("workflow", "TASK-1")
    with pytest.raises(store.StoreError):
        claim_task("workflow", "TASK-1", "second-agent")
    with pytest.raises(store.StoreError):
        release_task("workflow", "TASK-1", "ai-agent", "finished")
    report_test("workflow", "TASK-1", "AT-1", "pass", "ai-agent")
    release_task("workflow", "TASK-1", "ai-agent", "finished")
    result = client.get("/api/projects/workflow/state").json()["specs"][0]
    assert result["s"] == "finished" and not result.get("ai")
    assert result["ac"][0]["st"] == "pass"


def test_mcp_http_tools(client):
    response = client.post("/mcp/", headers={"Accept": "application/json, text/event-stream"}, json={
        "jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}
    })
    assert response.status_code == 200
    names = {tool["name"] for tool in response.json()["result"]["tools"]}
    assert {"get_project", "upsert_entity", "claim_task", "report_test", "release_task"} <= names



def test_mcp_typed_contracts(client):
    import json
    from jsonschema import validate

    def rpc(method, params):
        response = client.post("/mcp/", headers={"Accept": "application/json, text/event-stream"},
                               json={"jsonrpc": "2.0", "id": 2, "method": method, "params": params})
        assert response.status_code == 200
        return response.json()["result"]

    tools = {tool["name"]: tool for tool in rpc("tools/list", {})["tools"]}
    for tool in tools.values():
        assert tool["outputSchema"] and tool["annotations"]["openWorldHint"] is False

    def call(name, arguments):
        result = rpc("tools/call", {"name": name, "arguments": arguments})
        payload = result["structuredContent"]
        validate(payload, tools[name]["outputSchema"])
        assert json.loads(result["content"][0]["text"]) == payload
        assert result.get("isError", False) == (not payload["ok"])
        return payload

    call("create_project", {"project_id": "typed", "name": "Typed"})
    created = call("upsert_entity", {"project_id": "typed", "revision": 0,
                                    "entity": {"kind": "task", "task_id": "TASK-1", "title": "Typed task"}})
    assert created["revision"] == 1
    assert created["data"]["task_id"] == "TASK-1"
    assert "t" not in created["data"] and "log" not in created["data"]
    claimed = call("claim_task", {"project_id": "typed", "task_id": "TASK-1"})
    assert claimed["data"]["assignment"]["agent"] == "ai-agent"
    conflict = call("claim_task", {"project_id": "typed", "task_id": "TASK-1"})
    assert conflict["error"]["code"] == "conflict" and conflict["error"]["suggested_action"]
    stale = call("upsert_entity", {"project_id": "typed", "revision": 0,
                                  "entity": {"kind": "epic", "epic_id": "EPIC-1", "title": "Stale"}})
    assert stale["error"]["code"] == "conflict"
    snapshot = call("get_project", {"project_id": "typed"})
    assert snapshot["revision"] == claimed["revision"]
    assert snapshot["data"]["tasks"][0]["history"]
    missing = call("get_project", {"project_id": "missing"})
    assert missing["error"]["code"] == "not_found"
    malformed = rpc("tools/call", {"name": "upsert_entity", "arguments": {
        "project_id": "typed", "revision": 2,
        "entity": {"kind": "task", "task_id": "TASK-2", "title": "Bad", "status": "invalid"}
    }})
    assert malformed["isError"] is True
    assert store.get_state("typed")["revision"] == 2
