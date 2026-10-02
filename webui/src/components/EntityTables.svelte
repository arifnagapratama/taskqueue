<script>
  import { ADR_STATUS, EPIC_STATUS, epicRollup, fmt } from "../lib/helpers.js";

  export let view = "epics";
  export let epics = [];
  export let adrs = [];
  export let specs = [];
  export let selected = null;
  export let query = "";
  export let statusFilter = "all";
  export let onselect = () => {};
  export let ongo = () => {};

  $: items =
    view === "epics"
      ? epics.filter((item) => matches(item, EPIC_STATUS))
      : adrs.filter((item) => matches(item, ADR_STATUS));
  function matches(item) {
    if (statusFilter !== "all" && item.s !== statusFilter) return false;
    const terms = query.toLowerCase().trim().split(/\s+/).filter(Boolean);
    return terms.every((term) => {
      const match = term.match(/^([a-z]+):(.*)$/);
      if (match?.[1] === "status") return item.s.includes(match[2]);
      return `${item.id} ${item.t}`
        .toLowerCase()
        .includes(match ? match[2] : term);
    });
  }
</script>

{#if view === "epics"}
  <table id="tblE">
    <colgroup
      ><col style="width:84px" /><col /><col style="width:90px" /><col
        style="width:260px"
      /><col style="width:100px" /><col style="width:130px" /></colgroup
    >
    <thead
      ><tr
        ><th>ID</th><th>Epic</th><th>Status</th><th>Tasks</th><th>Tests</th><th
          >Updated</th
        ></tr
      ></thead
    >
    <tbody>
      {#each items as epic (epic.id)}
        {@const rollup = epicRollup(epic, specs)}
        <tr
          class="row"
          class:sel={selected === epic.id}
          onclick={() => onselect(epic.id)}
        >
          <td class="mono">{epic.id}</td><td title={epic.t}>{epic.t}</td><td
            ><span class="pill p-{epic.s.toLowerCase()}">{epic.s}</span></td
          >
          <td class="mono"
            >{rollup.done} done · {rollup.active} active · {rollup.todo} todo{#if rollup.agents}<span
                class="ai"><i class="pulse"></i>{rollup.agents}</span
              >{/if}</td
          >
          <td class="mono"
            >{rollup.passed}/{rollup.totalTests}{#if rollup.failed}<span
                class="ft"
              >
                ✕{rollup.failed}</span
              >{/if}</td
          ><td class="mono lbl">{fmt(epic.u)}</td>
        </tr>
      {/each}
    </tbody>
  </table>
{:else}
  <table id="tblA">
    <colgroup
      ><col style="width:84px" /><col /><col style="width:100px" /><col
        style="width:100px"
      /><col style="width:140px" /><col style="width:300px" /></colgroup
    >
    <thead
      ><tr
        ><th>ID</th><th>Decision</th><th>Status</th><th>Date</th><th>Tasks</th
        ><th>Relations</th></tr
      ></thead
    >
    <tbody>
      {#each items as adr (adr.id)}
        {@const relatedSpecs = specs.filter((spec) =>
          spec.adrs.includes(adr.id),
        )}
        {@const blockers =
          adr.s === "ACCEPTED"
            ? 0
            : specs.filter((spec) => spec.bl.includes(adr.id)).length}
        {@const successor = adrs.find((candidate) => candidate.sup === adr.id)}
        <tr
          class="row"
          class:s-finished={adr.s === "SUPERSEDED" || adr.s === "DEPRECATED"}
          class:sel={selected === adr.id}
          onclick={() => onselect(adr.id)}
        >
          <td class="mono">{adr.id}</td><td title={adr.t}>{adr.t}</td><td
            ><span class="pill p-{adr.s.toLowerCase()}">{adr.s}</span></td
          >
          <td class="mono lbl">{fmt(adr.u).slice(0, 10)}</td><td class="mono"
            >{relatedSpecs.length}{#if blockers}<span class="blk"
                >⛔ {blockers} blocked</span
              >{/if}</td
          >
          <td
            >{#if adr.sup}<span class="lbl">supersedes</span>
              <button
                type="button"
                class="chip"
                onclick={(event) => {
                  event.stopPropagation();
                  ongo(adr.sup);
                }}>{adr.sup}</button
              >{/if}{#if successor}<span class="lbl">superseded by</span>
              <button
                type="button"
                class="chip"
                onclick={(event) => {
                  event.stopPropagation();
                  ongo(successor.id);
                }}>{successor.id}</button
              >{/if}</td
          >
        </tr>
      {/each}
    </tbody>
  </table>
{/if}
{#if !items.length}<div class="empty">No {view} match the filter.</div>{/if}
