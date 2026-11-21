<script>
  import Button from "../design-system/Button.svelte";
  import Icon from "./Icon.svelte";
  import { ADR_STATUS, EPIC_STATUS, RULE_STATUS, STATUS } from "../lib/helpers.js";

  export let projects = [];
  export let projectId = '';
  export let busy = false;
  export let onproject = () => {};
  export let oncreateproject = () => {};
  export let oncreaterule = () => {};
  export let view = "specs";
  export let query = "";
  export let stage = "all";
  export let statusFilter = "all";
  export let counts = { specs: 0, epics: 0, adrs: 0, rules: 0 };
  export let onview = () => {};
  export let onquery = () => {};
  export let onstage = () => {};
  export let onstatus = () => {};
  export let ontoggleTheme = () => {};

  $: filterHelp =
    view === "specs"
      ? "Search tasks: auth, priority:P0, kind:bug, label:backend, status:verify, epic:03, adr:004, ai:on, blocked:on"
      : view === "epics"
        ? "Search epics: auth, status:open"
        : view === "rules"
          ? "Search project rules: review, status:active"
          : "Search ADRs: keycloak, status:proposed";
  $: placeholder = `Search ${view === "specs" ? "tasks" : view === "rules" ? "project rules" : view}…`;
  $: statuses = { epics: EPIC_STATUS, adrs: ADR_STATUS, rules: RULE_STATUS }[view];
</script>

<div class="bar">
  <span class="brand">Task<b>Queue</b></span><span class="sep"></span>
  <select class="btn" aria-label="Project" value={projectId} disabled={busy} onchange={(event) => onproject(event.currentTarget.value)}>
    {#each projects as project}<option value={project.id}>{project.name}</option>{/each}
  </select>
  <Button class="btn" disabled={busy} onclick={oncreateproject}><Icon name="add" /> Project</Button><span class="sep"></span>
  <div class="tabs" role="tablist" aria-label="Views">
    {#each [["specs", "Tasks"], ["epics", "Epics"], ["adrs", "ADRs"], ["rules", "Rules"]] as [key, label]}
      <Button variant="unstyled"
        class={"tab" + (view === key ? " on" : "")}
        role="tab"
        aria-selected={view === key}
        onclick={() => onview(key)}
      >
        {label} <i class="n">{counts[key]}</i>
      </Button>
    {/each}
  </div>
  <span class="sep"></span>
  {#if view === "specs"}
    <select
      class:on={stage !== "all"}
      class="btn"
      aria-label="Filter by stage"
      value={stage}
      onchange={(e) => onstage(e.currentTarget.value)}
    >
      <option value="all">Stage: All</option>
      {#each Object.entries(STATUS) as [status, label]}
        <option value={status}>Stage: {label}</option>
      {/each}
    </select>
  {:else}
    <select
      class:on={statusFilter !== "all"}
      class="btn"
      aria-label="Filter by status"
      value={statusFilter}
      onchange={(e) => onstatus(e.currentTarget.value)}
    >
      <option value="all">Status: All</option>
      {#each statuses as status}<option value={status}>Status: {status}</option
        >{/each}
    </select>
  {/if}
  <span style="flex: 1"></span>
  <Button
    class="btn"
    title="Toggle theme"
    aria-label="Toggle theme"
    onclick={ontoggleTheme}><Icon name="contrast" /></Button
  >
</div>
<div class="filter">
  <span class="lbl">Filter</span>
  <Button variant="unstyled" class="filter-help" type="button" aria-label={filterHelp} data-tooltip={filterHelp}>?</Button>
  <input
    class="mono"
    aria-label="Filter"
    {placeholder}
    value={query}
    oninput={(e) => onquery(e.currentTarget.value)}
  />
  {#if view === "rules"}
    <Button variant="primary" class="new-rule" disabled={busy || !projectId} onclick={oncreaterule}><Icon name="add" /> New rule</Button>
  {/if}
</div>
