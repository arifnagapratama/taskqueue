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
make up           # Start the published fullstack container
make logs         # Follow container logs
make down         # Stop the container; SQLite volume is preserved
```

Use `make dev-backend` and `make dev-frontend` in separate terminals if preferred.
`make serve` builds and serves the frontend through FastAPI on port 8080.
`make image`, `make restart`, `make status`, `make config`, and `make health`
cover container and service operations. Override executables when needed,
for example `make setup UV=/path/to/uv`.

## Deploy on the VPN server

Publish the application image to Docker Hub after `docker login docker.io`:

```sh
make publish                 # docker.io/tronton/taskqueue:latest
make publish TAG=1.0.0       # publish a specific tag
```

The target builds the image before pushing it. Override `IMAGE` if another
registry/repository is needed.

Requirements: Linux x86_64, Docker Engine with Compose, Python 3, and OpenSSL.
Copy `.env.example` to `.env` and set `TASKQUEUE_IP` to the static VPN IP.
The server only needs these files; preserve their relative paths:

```text
compose.yaml
.env.example
deploy/nginx.conf
scripts/init-deploy.py
```

Copy them into a dedicated deployment directory (no application source, Dockerfile,
Node.js, or uv required). Run from that directory after preparing `.env`:

```sh
sudo python3 scripts/init-deploy.py
docker compose pull
docker compose up -d
```

Initialization creates one random token, a local CA (`ca.crt`, `ca.key`) and a signed HTTPS certificate/key
(`server.crt`, `server.key`) in `deploy/private/`. Existing files are preserved on subsequent
runs. The certificate has the configured IP as its SAN and expires after 365
days. The token is readable by container UID 10001; initialization requires root
to set that ownership. `.env`, private files, and backups are ignored by Git
and excluded from the application image build context.

Open `https://IP_SERVER:5443/` and enter the token from `deploy/private/token`.
Trust `deploy/private/ca.crt` in the browser/OS before accessing the site.
REST and MCP requests require `x-api-token`; the UI shell remains available to
present the login screen. MCP endpoint: `https://IP_SERVER:5443/mcp/`.
Nginx terminates HTTPS and forwards REST, MCP streams, and WebSocket events.
SQLite lives at `/data/task-queue.sqlite3` in the named Compose volume.
`docker compose down` preserves data; `docker compose down -v` deletes it.

To rotate the token, update the contents of `deploy/private/token` while
preserving its owner and permissions. The application reads the file for each
request. Mounting the containing directory also supports atomic file replacement.
Users must enter the new token and MCP clients must restart with the new value.
For certificate renewal or an IP change, stop Compose, archive the existing
server certificate/key, move the server pair out of `deploy/private`, rerun
initialization, then start Compose. The CA is retained, so clients keep trusting
`ca.crt`. When replacing the CA itself, redistribute the new `ca.crt`. Keep
`ca.key` and `server.key` on the server; never copy them to clients.

Set `TASKQUEUE_TAG` in `.env` to the published version (default `latest`).
To update, run `docker compose pull` followed by `docker compose up -d`.
See [database loading instructions](docs/load-database.md) before the first
startup when migrating existing data.

### Codex CLI

Add this to `~/.codex/config.toml`, replacing `IP_SERVER`:

```toml
[mcp_servers.taskqueue]
url = "https://IP_SERVER:5443/mcp/"
env_http_headers = { "x-api-token" = "TASKQUEUE_TOKEN", "x-project-id" = "TASKQUEUE_PROJECT_ID" }
```

Before starting Codex, export the token securely from your local secret file
and trust the copied public certificate:

```sh
export TASKQUEUE_TOKEN="$(cat /absolute/path/taskqueue-token)"
export TASKQUEUE_PROJECT_ID=example
export TASKQUEUE_CERTS=/absolute/path/ca.crt
export CODEX_CA_CERTIFICATE="$TASKQUEUE_CERTS"
codex
```

Codex supports [headers from environment variables](https://learn.chatgpt.com/docs/extend/mcp)
and [custom PEM trust bundles](https://learn.chatgpt.com/docs/config-file/environment-variables).
`TASKQUEUE_CERTS` is our convenience variable; `CODEX_CA_CERTIFICATE` is the
Codex setting. TLS verification remains enabled. The client machine needs VPN
connectivity to the server.

Set `TASKQUEUE_PROJECT_ID` to an existing project ID. You can then omit
`project_id` from `get_project`, `upsert_entity`, `claim_task`,
`release_task`, and `report_test`, without calling a discovery tool to find
the project ID each run. An explicit `project_id` overrides the header.
Remove the header mapping if you prefer to pass the ID on every call.
`create_project` still takes the new project's ID explicitly, and
`upsert_entity` still requires the current project revision.

## Backup, migration, restore and rollback

Create a consistent snapshot from the local database (adjust the source path to
the database actually used by the running process):

```sh
mkdir -p backups
python3 scripts/backup.py data/task-queue.sqlite3 backups/migration.sqlite3
```

The script uses SQLite online backup, checks integrity and foreign keys, and
prints project revisions and entity counts. Existing destination files are
never overwritten. For final migration, stop writes on the source before taking
the snapshot and keep the source stopped until the new instance is verified.
Copy the snapshot securely to `backups/migration.sqlite3` on the server.

For a fresh destination, initialize deployment files, then restore while the
application is stopped:

```sh
docker compose stop
docker compose run --rm --no-deps --user root --entrypoint python \
  -v "$PWD/backups:/backups:ro" task-queue \
  -c 'import os; from backup import backup; backup("/backups/migration.sqlite3","/data/task-queue.sqlite3"); os.chown("/data/task-queue.sqlite3",10001,10001)'
docker compose up -d
```

Pull the published image first with `docker compose pull`. The restore command refuses
to overwrite an existing database. Check the project list, revisions and task
counts against the snapshot output, then verify reads and writes in the UI/MCP.
The existing application creates a `default` project at startup; migration does
not delete projects.

For recurring backups, use the utility bundled in the image to write a snapshot
into its data volume, then copy that completed snapshot to the host:

```sh
docker compose exec task-queue python /app/backup.py /data/task-queue.sqlite3 /data/snapshot.sqlite3
docker compose cp task-queue:/data/snapshot.sqlite3 backups/snapshot.sqlite3
```

Use unique snapshot names for later backups. Store copies outside the server;
scheduling and retention are operator-managed. To roll back a migration, stop
the new deployment before restarting the retained local instance. To restore a
backup over an existing deployment, stop Compose, archive the entire existing
data volume (including WAL files), and restore into a fresh volume using the
same procedure. Keep the old volume until verification succeeds.

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
`upsert_entity` takes `revision` and a typed `entity` with `kind: task | epic | adr`.
Pass `project_id` explicitly or configure the `x-project-id` header.
Every tool advertises input/output JSON Schema and returns:

```json
{
  "ok": true,
  "revision": 1,
  "data": { "project_id": "example", "name": "Example", "revision": 1 },
  "error": null
}
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
Set `TASKQUEUE_TOKEN_FILE` to enable token authentication. Without it, local development remains unauthenticated; use only a trusted development environment.

### Upgrade from the legacy self-signed server certificate

The old generator could produce `server.crt` with `CA:TRUE`. Rustls rejects
that certificate as an HTTPS end entity (`CaUsedAsEndEntity`). Update
`scripts/init-deploy.py`, then run from the deployment directory:

```sh
docker compose stop https
sudo mkdir -p deploy/legacy-tls
sudo mv deploy/private/server.crt deploy/private/server.key deploy/legacy-tls/
sudo python3 scripts/init-deploy.py
docker compose up -d https
```

Keep the existing token and database. Copy only `deploy/private/ca.crt` to
clients, trust it in the browser/OS, update `TASKQUEUE_CERTS` to that file, and
restart Codex. The server continues serving `server.crt`; clients trust `ca.crt`.

If CA inspection prints duplicate `Basic Constraints` or `Subject Key Identifier`
extensions, regenerate both CA and server pairs using the latest initializer.
Older OpenSSL configurations could contribute default extensions alongside
`-addext`. The updated initializer uses an explicit request configuration.
Stop HTTPS, archive `ca.crt`, `ca.key`, `server.crt`, and `server.key` outside
`deploy/private`, and rerun initialization. Preserve `token`. Restart HTTPS and
redistribute the new `ca.crt` to all clients.
