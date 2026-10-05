"""FastAPI application with shared REST, MCP and frontend hosting."""
import os
import sqlite3
import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from backend import store
from backend.mcp_server import mcp

mcp_app = mcp.streamable_http_app()


@asynccontextmanager
async def lifespan(app):
    store.initialize()
    async with mcp.session_manager.run():
        yield


app = FastAPI(title="Task Queue", lifespan=lifespan)
subscribers = {}
subscriber_loop = None


def broadcast_change(project_id, revision):
    if subscriber_loop is None:
        return
    def deliver():
        for queue in tuple(subscribers.get(project_id, ())):
            if queue.full():
                queue.get_nowait()
            queue.put_nowait({"project_id": project_id, "revision": revision})
    subscriber_loop.call_soon_threadsafe(deliver)


store.add_change_listener(broadcast_change)


@app.exception_handler(store.StoreError)
async def store_error(request, error):
    return JSONResponse({"error": error.message}, status_code=error.status)


@app.exception_handler(sqlite3.Error)
async def database_error(request, error):
    return JSONResponse({"error": "Database unavailable"}, status_code=503)


@app.middleware("http")
async def body_limit(request: Request, call_next):
    if request.url.path.startswith("/api/") and request.method in ("POST", "PUT"):
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > 5_000_000:
                return JSONResponse({"error": "Request body exceeds 5 MB"}, status_code=413)
        request._body = bytes(body)
    response = await call_next(request)
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response


class ProjectInput(BaseModel):
    id: str
    name: str


@app.get("/api/health")
def health():
    with store.connect() as db:
        db.execute("SELECT 1")
    return {"status": "ok"}


@app.get("/api/projects")
def projects():
    return store.list_projects()


@app.post("/api/projects", status_code=201)
def create_project(body: ProjectInput):
    return store.create_project(body.id, body.name)


@app.get("/api/projects/{project_id}/state")
def get_state(project_id: str):
    return store.get_state(project_id)


@app.put("/api/projects/{project_id}/state")
def put_state(project_id: str, body: dict):
    return store.put_state(project_id, body)


@app.websocket("/api/events")
async def project_events(websocket: WebSocket):
    global subscriber_loop
    project_id = websocket.query_params.get("project_id", "")
    await websocket.accept()
    if not project_id:
        await websocket.close(code=1008)
        return
    subscriber_loop = asyncio.get_running_loop()
    queue = asyncio.Queue(maxsize=1)
    subscribers.setdefault(project_id, set()).add(queue)
    try:
        while True:
            await websocket.send_json(await queue.get())
    except WebSocketDisconnect:
        pass
    finally:
        project_subscribers = subscribers.get(project_id)
        if project_subscribers:
            project_subscribers.discard(queue)
            if not project_subscribers:
                subscribers.pop(project_id, None)


app.mount("/mcp", mcp_app)
static_path = Path(os.environ.get("STATIC_PATH", "webui/dist"))
if static_path.is_dir():
    app.mount("/", StaticFiles(directory=static_path, html=True), name="frontend")
