"""Public MCP contracts. Storage/UI abbreviations stay behind this boundary."""
from typing import Annotated, Generic, Literal, TypeVar
from pydantic import BaseModel, ConfigDict, Field


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AcceptanceTest(Model):
    test_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    status: Literal["pending", "pass", "fail"] = "pending"
    mode: Literal["auto", "manual"] = "manual"
    reference: str = ""
    steps: list[str] = Field(default_factory=list)
    last_run_at: int | None = None


class TaskInput(Model):
    kind: Literal["task"] = "task"
    task_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    status: Literal["todo", "in_progress", "finished"] = "todo"
    description: str = ""
    epic_id: str | None = None
    adr_ids: list[str] = Field(default_factory=list)
    blocked_by_adr_ids: list[str] = Field(default_factory=list)
    labels: list[str] = Field(default_factory=list)
    acceptance_tests: list[AcceptanceTest] = Field(default_factory=list)


class Assignment(Model):
    agent: str
    started_at: int
    step: str


class HistoryEntry(Model):
    timestamp: int
    actor: str
    message: str


class Task(TaskInput):
    updated_at: int
    assignment: Assignment | None = None
    history: list[HistoryEntry]


class EpicInput(Model):
    kind: Literal["epic"] = "epic"
    epic_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    status: Literal["OPEN", "CLOSED"] = "OPEN"
    description: str = ""


class Epic(EpicInput):
    updated_at: int


class AdrInput(Model):
    kind: Literal["adr"] = "adr"
    adr_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    status: Literal["PROPOSED", "ACCEPTED", "SUPERSEDED", "DEPRECATED"] = "PROPOSED"
    context: str = ""
    decision: str = ""
    consequences: str = ""
    supersedes_adr_id: str | None = None


class Adr(AdrInput):
    updated_at: int


EntityInput = Annotated[TaskInput | EpicInput | AdrInput, Field(discriminator="kind")]
Entity = Annotated[Task | Epic | Adr, Field(discriminator="kind")]


class Project(Model):
    project_id: str
    name: str
    revision: int


class ProjectList(Model):
    projects: list[Project]


class ProjectState(Model):
    project_id: str
    tasks: list[Task]
    epics: list[Epic]
    adrs: list[Adr]


class TestReport(Model):
    task_id: str
    test: AcceptanceTest


class Error(Model):
    code: Literal["invalid_input", "not_found", "conflict", "storage_unavailable"]
    message: str
    suggested_action: str


T = TypeVar("T")


class Result(Model, Generic[T]):
    ok: bool
    revision: int | None = None
    data: T | None = None
    error: Error | None = None


def test_view(test):
    return AcceptanceTest(test_id=test["id"], title=test["t"], status=test["st"], mode=test["mode"],
                          reference=test.get("ref", ""), steps=test["steps"], last_run_at=test.get("run"))


def entity_view(kind, item):
    common = {"title": item["t"], "status": item["s"], "updated_at": item.get("u", 0)}
    if kind == "epics":
        return Epic(epic_id=item["id"], description=item["d"], **common)
    if kind == "adrs":
        return Adr(adr_id=item["id"], context=item["ctx"], decision=item["dec"],
                   consequences=item["cons"], supersedes_adr_id=item.get("sup") or None, **common)
    ai = item.get("ai")
    return Task(task_id=item["id"], description=item["d"], epic_id=item.get("epic") or None,
                adr_ids=item["adrs"], blocked_by_adr_ids=item["bl"], labels=item["l"],
                acceptance_tests=[test_view(test) for test in item["ac"]],
                assignment=Assignment(agent=ai["agent"], started_at=ai["since"], step=ai["step"]) if ai else None,
                history=[HistoryEntry(timestamp=t, actor=actor, message=message) for t, actor, message in item["log"]], **common)


def to_storage(entity):
    common = {"t": entity.title, "s": entity.status}
    if isinstance(entity, EpicInput):
        return "epics", {"id": entity.epic_id, "d": entity.description, **common}
    if isinstance(entity, AdrInput):
        return "adrs", {"id": entity.adr_id, "ctx": entity.context, "dec": entity.decision,
                        "cons": entity.consequences, "sup": entity.supersedes_adr_id or "", **common}
    return "specs", {"id": entity.task_id, "d": entity.description, "epic": entity.epic_id or "",
                     "adrs": entity.adr_ids, "bl": entity.blocked_by_adr_ids, "l": entity.labels, "log": [],
                     "ac": [{"id": test.test_id, "t": test.title, "st": test.status, "mode": test.mode,
                             "ref": test.reference, "steps": test.steps, "run": test.last_run_at}
                            for test in entity.acceptance_tests], **common}
