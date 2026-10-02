<script>
  import { ADR_STATUS, EPIC_STATUS } from "../lib/helpers.js";

  export let view = "specs";
  export let query = "";
  export let stage = "all";
  export let statusFilter = "all";
  export let counts = { specs: 0, epics: 0, adrs: 0 };
  export let onview = () => {};
  export let onquery = () => {};
  export let onstage = () => {};
  export let onstatus = () => {};
  export let ontoggleTheme = () => {};

  $: filterHelp =
    view === "specs"
      ? "Search tasks: auth, label:backend, status:todo, epic:03, adr:004, ai:on, blocked:on"
      : view === "epics"
        ? "Search epics: auth, status:open"
        : "Search ADRs: keycloak, status:proposed";
  $: placeholder = `Search ${view === "specs" ? "tasks" : view}…`;
  $: statuses = view === "epics" ? EPIC_STATUS : ADR_STATUS;
</script>

<div class="bar">
  <span class="brand">Task<b>Queue</b></span><span class="sep"></span>
  <select class="btn" aria-label="Project">
    <option>bancakan-portal</option><option>packem-api</option>
  </select><span class="sep"></span>
  <div class="tabs" role="tablist" aria-label="Views">
    {#each [["specs", "Tasks"], ["epics", "Epics"], ["adrs", "ADRs"]] as [key, label]}
      <button
        class:on={view === key}
        class="tab"
        role="tab"
        aria-selected={view === key}
        onclick={() => onview(key)}
      >
        {label} <i class="n">{counts[key]}</i>
      </button>
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
      <option value="all">Stage: All</option><option value="in_progress"
        >Stage: In progress</option
      ><option value="todo">Stage: Todo</option><option value="finished"
        >Stage: Finished</option
      >
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
  <button
    class="btn"
    title="Toggle theme"
    aria-label="Toggle theme"
    onclick={ontoggleTheme}>◐</button
  >
</div>
<div class="filter">
  <span class="lbl">Filter</span>
  <span class="filter-help" tabindex="0" aria-label={filterHelp} data-tooltip={filterHelp}>?</span>
  <input
    class="mono"
    aria-label="Filter"
    {placeholder}
    value={query}
    oninput={(e) => onquery(e.currentTarget.value)}
  />
</div>
