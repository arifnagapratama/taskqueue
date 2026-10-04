---
name: task-queue-mcp
description: Use the Task Queue MCP to inspect and maintain projects, tasks, epics, ADRs, acceptance tests, and AI task claims. Use when the user asks to read or update Task Queue data or coordinate work recorded there.
---

# Task Queue MCP

Use the connected **Task Queue** MCP tools directly: `list_projects`, `create_project`, `get_project`, `upsert_entity`, `claim_task`, `report_test`, and `release_task`.

If these tools are unavailable, the MCP server is not connected in this Codex environment. This server exposes Streamable HTTP at `http://localhost:8080/mcp/`; start it from the Task Queue project with `make serve` or `make up`, then connect the MCP client to that endpoint. Do not substitute direct database edits or invent tool results.

## Select and read a project

1. Call `list_projects` and select the project the user means. Use the returned `project_id` exactly. If asked to create a project, call `create_project` with a stable ID containing only letters, numbers, `_`, or `-`, plus a readable name.
2. Call `get_project(project_id)` before editing. It returns all tasks, epics, ADRs, and the current project `revision`.
3. Pass that revision to `upsert_entity`. If a write returns `conflict`, call `get_project` again, reconcile against the latest state, and retry with the new revision. Never blindly repeat a stale write.

## Create or edit entities

`upsert_entity` takes `project_id`, `revision`, and a typed `entity`. It replaces editable fields, so read the existing entity first and include all desired editable values when changing only one field.

- Task: `kind: "task"`, `task_id`, `title`, `status` (`todo`, `in_progress`, `finished`), `description`, optional `epic_id`, `adr_ids`, `blocked_by_adr_ids`, `labels`, and `acceptance_tests`.
- Epic: `kind: "epic"`, `epic_id`, `title`, `status` (`OPEN` or `CLOSED`), and `description`.
- ADR: `kind: "adr"`, `adr_id`, `title`, `status` (`PROPOSED`, `ACCEPTED`, `SUPERSEDED`, `DEPRECATED`), `context`, `decision`, `consequences`, and optional `supersedes_adr_id`.

Each task acceptance test has `test_id`, `title`, `status` (`pending`, `pass`, `fail`), `mode` (`auto`, `manual`), `reference`, and `steps`.

Task `assignment` and `history` are server-managed. Do not set them through `upsert_entity`, and do not change the status of a claimed task there. Use the task coordination tools.

## Coordinate task work

1. Call `claim_task(project_id, task_id, agent, step)` before starting work. `agent` defaults to `ai-agent`; use a stable identity. A claim can be rejected when the task is already claimed, finished, or blocked by unresolved ADRs. Follow the returned error and resolve its precondition.
2. Call `report_test(project_id, task_id, test_id, status, agent)` for acceptance test results. Use the exact `test_id` from the task and a status of `pending`, `pass`, or `fail`.
3. Call `release_task(project_id, task_id, agent, status)` when finished or stopping. Use `todo` for incomplete work. Use `finished` only after every defined acceptance test passes.

## Handle results and errors

Results have a structured envelope with `ok`, optional `revision`, `data`, and `error`. Confirm `ok: true` before reporting a mutation as successful. For `not_found`, verify IDs through `list_projects` or `get_project`. For `invalid_input`, follow the tool schema. For `conflict`, refresh state before retrying. For `storage_unavailable`, retry later and report it if it persists.

The MCP and REST API share the same database. Timestamps are Unix milliseconds.
