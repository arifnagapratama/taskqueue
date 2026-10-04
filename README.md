# Task Queue

Prototype for tracking coding tasks across projects through a Svelte UI and MCP.
Backend: Python, FastAPI, uv, SQLite. Frontend styles are maintained in `webui`.

```text
backend/          FastAPI, shared SQLite storage, MCP tools, tests
webui/            Svelte + Vite frontend
pyproject.toml    Python dependencies managed by uv
uv.lock           Locked Python dependencies
Dockerfile        One fullstack image
compose.yaml      Service and persistent SQLite volume
```

## Operation shortcuts

Run `make help` from the repository root for all shortcuts.

```sh
make setup        # Install dependencies from lockfiles
make dev          # Backend :8080 and Vite :5173 together
make test         # Backend and MCP tests
make up           # Build and start the fullstack container
make logs         # Follow container logs
make down         # Stop the container; SQLite volume is preserved
```

Use `make dev-backend` and `make dev-frontend` in separate terminals if preferred.
`make serve` builds and serves the frontend through FastAPI on port 8080.
`make image`, `make restart`, `make status`, `make config`, and `make health`
cover container and service operations. Override executables when needed,
for example `make setup UV=/path/to/uv`.

## Run the fullstack image

From the repository root:

```sh
docker compose up --build -d
```

UI: http://localhost:8080. REST docs: http://localhost:8080/docs.
MCP Streamable HTTP: http://localhost:8080/mcp/.
SQLite lives at `/data/task-queue.sqlite3` in the Compose named volume.
Keep the volume when replacing the container. `docker compose down -v` removes data.

## Develop

```sh
uv sync --frozen
uv run uvicorn backend.main:app --host 0.0.0.0 --port 8080 --reload
```

Run `npm ci` and `npm run dev` from `webui` for the Vite frontend on port 5173.
Vite proxies `/api` to port 8080. Alternatively build with `npm run build`, then
restart the backend to serve `webui/dist` on port 8080.
Tests: `uv run pytest backend`.

Environment variables: `DATABASE_PATH` (default `data/task-queue.sqlite3`),
`STATIC_PATH` (default `webui/dist`). The container listens on port 8080.

## Tracking and MCP

Create a project with the UI or `create_project`. Projects start empty;
sample data can be loaded explicitly through the UI. Agents can list/read
projects and use `upsert_entity` to create or update tasks, epics and ADRs.
Read the project revision before editing: stale writes are rejected.
Use `claim_task` to start work; unresolved ADR blockers, existing claims and
finished tasks prevent claiming. `report_test` records acceptance results.
`release_task` clears the claim; finishing requires all defined tests to pass.
Generic agent names default to `ai-agent`. MCP and REST share the same database.

MCP uses descriptive field names (`task_id`, `title`, `status`, `description`,
`blocked_by_adr_ids`, `acceptance_tests`, `assignment`, `history`).
`upsert_entity` accepts `project_id`, `revision` and a typed `entity` with
`kind: task | epic | adr`. This replaces the earlier raw UI-field MCP contract.
Every tool advertises input/output JSON Schema and returns:

```json
{"ok": true, "revision": 1, "data": {"project_id": "example", "name": "Example", "revision": 1}, "error": null}
```

Results are sent in `structuredContent`, plus matching JSON text for compatibility.
Domain failures set `isError: true`, `ok: false`, with `error.code`, `error.message`
and `error.suggested_action`. Codes: `invalid_input`, `not_found`, `conflict`,
`storage_unavailable`. SDK input validation errors also return `isError: true`.
Tool annotations identify reads and writes. All timestamps are Unix milliseconds.
Task history and AI assignment are server managed. Editable fields are replaced
by upsert, so read the task before editing to preserve fields you want to keep.
The REST/storage field names remain compatible with the UI.

See the [MCP tool specification](https://modelcontextprotocol.io/specification/2025-11-25/server/tools)
for structured output and error semantics.

## Storage and API

One SQLite database holds all projects. Composite entity keys contain project id,
kind and entity id; IDs can repeat across projects. Existing SQLite schema and
data from the earlier backend remain compatible. WAL and atomic transactions
protect writes; revision checks prevent overwrites between browser and MCP.

REST: `GET /api/health`, `GET/POST /api/projects`,
`GET/PUT /api/projects/{id}/state`. PUT atomically replaces a project and requires
`revision`, `specs`, `epics`, `adrs`. API request bodies are limited to 5 MB.
Failed UI saves retain pending changes. For conflicts, preserve your changes,
reload the latest state and reapply. Browser demo data is not imported automatically.

Run one container per local SQLite volume. Back up with SQLite's online backup
API or stop the container and copy the complete volume including WAL files.
No authentication is included; use a trusted network or authenticated reverse proxy.
