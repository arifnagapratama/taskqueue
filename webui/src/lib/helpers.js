export const STATUS = {
  in_progress: "IN PROGRESS",
  todo: "TODO",
  finished: "FINISHED",
};

export const ORDER = ["in_progress", "todo", "finished"];
export const EPIC_STATUS = ["OPEN", "CLOSED"];
export const ADR_STATUS = ["PROPOSED", "ACCEPTED", "SUPERSEDED", "DEPRECATED"];

export function fmt(value, seconds = false) {
  const date = new Date(value);
  const pad = (n) => String(n).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}${seconds ? `:${pad(date.getSeconds())}` : ""}`;
}

export function duration(ms) {
  const minutes = Math.floor(ms / 60000);
  const hours = Math.floor(minutes / 60);
  return hours
    ? `${hours}h ${String(minutes % 60).padStart(2, "0")}m`
    : `${minutes}m`;
}

export function blocked(spec, adrs) {
  return (spec.bl || []).filter(
    (id) => adrs.find((adr) => adr.id === id)?.s !== "ACCEPTED",
  );
}

export function parseFilter(query) {
  return query
    .toLowerCase()
    .trim()
    .split(/\s+/)
    .filter(Boolean)
    .map((term) => {
      const match = term.match(/^([a-z]+):(.*)$/);
      return match
        ? { key: match[1], value: match[2] }
        : { key: "", value: term };
    });
}

export function matchesSpec(spec, query, stage, epics, adrs) {
  if (stage !== "all" && spec.s !== stage) return false;
  return parseFilter(query).every(({ key, value }) => {
    if (!key)
      return `${spec.t} ${spec.id} ${spec.epic || ""} ${(spec.adrs || []).join(" ")} ${(spec.l || []).join(" ")}`
        .toLowerCase()
        .includes(value);
    if (key === "label")
      return (spec.l || []).some((label) =>
        label.toLowerCase().includes(value),
      );
    if (key === "status") return spec.s.includes(value);
    if (key === "ai") return value === "off" ? !spec.ai : Boolean(spec.ai);
    if (key === "blocked")
      return value === "off"
        ? !blocked(spec, adrs).length
        : Boolean(blocked(spec, adrs).length);
    if (key === "epic")
      return `${spec.epic || "none"} ${epics.find((e) => e.id === spec.epic)?.t || ""}`
        .toLowerCase()
        .includes(value);
    if (key === "adr")
      return (spec.adrs || []).some((id) => id.toLowerCase().includes(value));
    if (key === "id") return spec.id.toLowerCase().includes(value);
    return true;
  });
}

export function matchesEntity(entity, query, status) {
  if (status !== "all" && entity.s !== status) return false;
  const haystack = `${entity.id} ${entity.t}`.toLowerCase();
  return parseFilter(query).every(({ key, value }) =>
    key === "status" ? entity.s.includes(value) : haystack.includes(value),
  );
}

export function epicRollup(epic, specs) {
  const linked = specs.filter((spec) => spec.epic === epic.id);
  const tests = linked.flatMap((spec) => spec.ac || []);
  return {
    specs: linked,
    done: linked.filter((spec) => spec.s === "finished").length,
    active: linked.filter((spec) => spec.s === "in_progress").length,
    todo: linked.filter((spec) => spec.s === "todo").length,
    passed: tests.filter((test) => test.st === "pass").length,
    failed: tests.filter((test) => test.st === "fail").length,
    totalTests: tests.length,
    agents: linked.filter((spec) => spec.ai).length,
  };
}

export function testPercent(spec) {
  const tests = spec.ac || [];
  return tests.length
    ? Math.round(
        (tests.filter((test) => test.st === "pass").length / tests.length) *
          100,
      )
    : 0;
}
