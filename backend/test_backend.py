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


def test_mcp_project_header(client):
    store.create_project("header-project", "Header project")

    def rpc(method, params, project="header-project"):
        headers = {"Accept": "application/json, text/event-stream"}
        if project is not None:
            headers["X-Project-ID"] = project
        response = client.post("/mcp/", headers=headers, json={
            "jsonrpc": "2.0", "id": 3, "method": method, "params": params,
        })
        assert response.status_code == 200
        return response.json()["result"]

    def call(name, project="header-project", **arguments):
        return rpc("tools/call", {"name": name, "arguments": arguments}, project)["structuredContent"]

    tools = {tool["name"]: tool["inputSchema"] for tool in rpc("tools/list", {})["tools"]}
    for name in ("get_project", "upsert_entity", "claim_task", "release_task", "report_test"):
        assert "project_id" not in tools[name].get("required", [])
        assert "ctx" not in tools[name]["properties"]
    assert "project_id" in tools["create_project"]["required"]

    task = {"kind": "task", "task_id": "TASK-1", "title": "Header task",
            "priority": "P12", "task_kind": "bug",
            "acceptance_tests": [{"test_id": "AT-1", "title": "Check header project"}]}
    assert call("upsert_entity", revision=0, entity=task)["revision"] == 1
    assert call("claim_task", task_id="TASK-1")["ok"]
    assert call("report_test", task_id="TASK-1", test_id="AT-1", status="pass", agent="ai-agent")["ok"]
    verifying = call("release_task", task_id="TASK-1", agent="ai-agent", status="verify")
    assert verifying["data"]["status"] == "verify"
    assert verifying["data"]["assignment"] is None
    assert call("claim_task", task_id="TASK-1")["ok"]
    assert call("release_task", task_id="TASK-1", agent="ai-agent", status="finished")["ok"]
    snapshot = call("get_project")
    assert snapshot["data"]["project_id"] == "header-project"
    assert snapshot["data"]["tasks"][0]["priority"] == "P12"
    assert snapshot["data"]["tasks"][0]["task_kind"] == "bug"
    assert call("upsert_entity", revision=snapshot["revision"], entity={
        "kind": "task", "task_id": "TASK-1", "title": "Deferred task", "status": "deferred",
    })["data"]["priority"] == "P12"
    assert call("claim_task", task_id="TASK-1")["error"]["code"] == "conflict"
    assert call("get_project", project_id="default")["data"]["project_id"] == "default"
    assert call("get_project", project="unknown-project")["error"]["code"] == "not_found"
    assert call("get_project", project=None)["error"]["code"] == "invalid_input"


def test_task_metadata_rest_and_legacy_rows(client):
    import json

    store.create_project("legacy-task", "Legacy task")
    task = {"id": "TASK-1", "t": "Existing task", "s": "todo", "d": "",
            "adrs": [], "bl": [], "l": [], "log": [], "ac": []}
    with store.connect() as db:
        db.execute("INSERT INTO entities VALUES (?, ?, ?, ?, ?)",
                   ("legacy-task", "specs", task["id"], 0, json.dumps(task)))
    url = "/api/projects/legacy-task/state"
    state = client.get(url).json()
    saved_task = state["specs"][0]
    assert state["revision"] == 0
    assert (saved_task["priority"], saved_task["kind"]) == ("P2", "other")
    assert saved_task["depends_on"] == []

    saved_task.update(priority="P01", kind="feature", s="verify")
    assert client.put(url, json=state).status_code == 400
    saved_task.update(priority="P0", kind="two words")
    assert client.put(url, json=state).status_code == 400
    saved_task.update(priority="P0", kind="integration-test")
    assert client.put(url, json=state).json() == {"revision": 1}
    state.update(revision=1, specs=[dict(task, s="deferred")])
    assert client.put(url, json=state).json() == {"revision": 2}
    saved = client.get(url).json()["specs"][0]
    assert (saved["priority"], saved["kind"], saved["s"]) == ("P0", "integration-test", "deferred")


def test_task_dependencies_rest_and_mcp(client):
    store.create_project("dependencies", "Dependencies")
    url = "/api/projects/dependencies/state"
    base_task = {"t": "Task", "s": "todo", "d": "", "adrs": [], "bl": [], "l": [], "log": [], "ac": []}
    prerequisite = dict(base_task, id="A")
    dependent = dict(base_task, id="B", depends_on=["A"])
    state = {"revision": 0, "specs": [prerequisite, dependent], "adrs": [], "epics": []}
    assert client.put(url, json=state).json() == {"revision": 1}
    state["revision"] = 1

    for invalid_links in (["B"], ["A", "A"], ["missing"]):
        invalid = dict(state, specs=[prerequisite, dict(dependent, depends_on=invalid_links)])
        assert client.put(url, json=invalid).status_code == 400
    cycle = dict(state, specs=[dict(prerequisite, depends_on=["B"]), dependent])
    assert client.put(url, json=cycle).status_code == 400
    assert client.put(url, json=dict(state, specs=[dependent])).status_code == 400
    blocked = dict(state, specs=[prerequisite, dict(dependent, s="in_progress")])
    assert client.put(url, json=blocked).status_code == 409
    assert client.get(url).json()["revision"] == 1

    def call(name, **arguments):
        response = client.post("/mcp/", headers={"Accept": "application/json, text/event-stream"}, json={
            "jsonrpc": "2.0", "id": 42, "method": "tools/call",
            "params": {"name": name, "arguments": dict(arguments, project_id="dependencies")},
        })
        return response.json()["result"]["structuredContent"]

    assert call("claim_task", task_id="B")["error"]["code"] == "conflict"
    edited = call("upsert_entity", revision=1, entity={"kind": "task", "task_id": "B", "title": "Renamed"})
    assert edited["data"]["depends_on"] == ["A"]
    state["revision"] = edited["revision"]
    state["specs"] = [dict(prerequisite, s="finished"), dict(base_task, id="B")]
    assert client.put(url, json=state).json() == {"revision": 3}
    claimed = call("claim_task", task_id="B")
    assert claimed["data"]["depends_on"] == ["A"]
    assert claimed["data"]["status"] == "in_progress"
    assert call("release_task", task_id="B", agent="ai-agent")["ok"]
    cleared = call("upsert_entity", revision=5, entity={
        "kind": "task", "task_id": "B", "title": "Independent", "depends_on": [],
    })
    assert cleared["data"]["depends_on"] == []
    linked = call("upsert_entity", revision=6, entity={
        "kind": "task", "task_id": "B", "title": "Dependent", "depends_on": ["A"],
    })
    assert linked["data"]["depends_on"] == ["A"]
    reopened = client.get(url).json()
    reopened["specs"][0]["s"] = "verify"
    assert client.put(url, json=reopened).json() == {"revision": 8}
    conflict = call("claim_task", task_id="B")
    assert conflict["error"]["code"] == "conflict"
    assert "Finish prerequisite tasks first: A" in conflict["error"]["message"]


@pytest.mark.parametrize("path", ["/api/health", "/api/projects", "/mcp/", "/docs", "/openapi.json"])
def test_token_required(client, monkeypatch, tmp_path, path):
    token_file = tmp_path / "token"
    token_file.write_text("test-secret\n")
    monkeypatch.setenv("TASKQUEUE_TOKEN_FILE", str(token_file))
    assert client.get(path).status_code == 401
    assert client.get(path, headers={"x-api-token": "wrong"}).status_code == 401
    assert client.get(path, headers={"x-api-token": "test-secret"}).status_code != 401


def test_token_rotation_and_fail_closed(client, monkeypatch, tmp_path):
    token_file = tmp_path / "token"
    token_file.write_text("old")
    monkeypatch.setenv("TASKQUEUE_TOKEN_FILE", str(token_file))
    assert client.get("/api/health", headers={"x-api-token": "old"}).status_code == 200
    token_file.write_text("new")
    assert client.get("/api/health", headers={"x-api-token": "old"}).status_code == 401
    assert client.get("/api/health", headers={"x-api-token": "new"}).status_code == 200
    token_file.write_text("")
    assert client.get("/api/health", headers={"x-api-token": ""}).status_code == 401
    token_file.unlink()
    assert client.get("/api/health", headers={"x-api-token": "new"}).status_code == 401


def test_websocket_auth(client, monkeypatch, tmp_path):
    from starlette.websockets import WebSocketDisconnect
    token_file = tmp_path / "token"
    token_file.write_text("secret")
    monkeypatch.setenv("TASKQUEUE_TOKEN_FILE", str(token_file))
    with client.websocket_connect("/api/events?project_id=default") as socket:
        socket.send_json({"token": "wrong"})
        with pytest.raises(WebSocketDisconnect) as error:
            socket.receive_json()
        assert error.value.code == 4401
    with client.websocket_connect("/api/events") as socket:
        socket.send_json({"token": "secret"})
        with pytest.raises(WebSocketDisconnect) as error:
            socket.receive_json()
        assert error.value.code == 1008  # authenticated; missing project rejected separately


def test_mcp_deployment_host_allowlist(monkeypatch):
    from backend.mcp_server import transport_security
    from mcp.server.transport_security import TransportSecurityMiddleware
    monkeypatch.setenv("TASKQUEUE_IP", "10.20.30.40")
    security = TransportSecurityMiddleware(transport_security())
    assert security._validate_host("10.20.30.40:5443")
    assert security._validate_origin("https://10.20.30.40:5443")
    assert not security._validate_host("10.20.30.41:5443")
    assert not security._validate_origin("https://untrusted.example:5443")
    monkeypatch.setenv("TASKQUEUE_IP", "invalid")
    with pytest.raises(ValueError):
        transport_security()
