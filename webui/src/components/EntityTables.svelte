<script>
  import Button from "../design-system/Button.svelte";
  import Badge from "../design-system/Badge.svelte";
  import Icon from "./Icon.svelte";
  import { epicRollup, fmt, matchesEntity } from "../lib/helpers.js";

  export let view = "epics";
  export let epics = [];
  export let adrs = [];
  export let rules = [];
  export let hasRules = false;
  export let specs = [];
  export let selected = null;
  export let query = "";
  export let statusFilter = "all";
  export let onselect = () => {};
  export let ongo = () => {};

  $: items = view === "rules" ? rules : (view === "epics" ? epics : adrs)
    .filter((item) => matchesEntity(item, query, statusFilter));
</script>

{#if view === "epics"}
  <table id="tblE">
    <colgroup
      ><col style="width:116px" /><col style="width:320px" /><col style="width:152px" /><col
        style="width:405px"
      /><col style="width:168px" /><col style="width:188px" /></colgroup
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
        {@const taskSummary = `${rollup.done} done · ${rollup.active} active · ${rollup.verify} verify · ${rollup.todo} todo · ${rollup.deferred} deferred`}
        <tr
          class="row"
          class:sel={selected === epic.id}
          tabindex="0"
          onkeydown={(event) => event.key === "Enter" && onselect(epic.id)}
          onclick={() => onselect(epic.id)}
        >
          <td class="mono" title={epic.id}>{epic.id}</td><td title={epic.t}>{epic.t}</td><td
            ><Badge tone={epic.s === "CLOSED" ? "success" : "neutral"} class="p-{epic.s.toLowerCase()}">{epic.s}</Badge></td
          >
          <td class="mono" title={taskSummary}
            >{taskSummary}{#if rollup.agents}<span
                class="ai"><i class="pulse"></i>{rollup.agents}</span
              >{/if}</td
          >
          <td class="mono"
            >{rollup.passed}/{rollup.totalTests}{#if rollup.failed}<span
                class="ft" aria-label={`${rollup.failed} failed tests`}
              >
                <Icon name="close" />{rollup.failed}</span
              >{/if}</td
          ><td class="mono lbl" title={fmt(epic.u)}>{fmt(epic.u)}</td>
        </tr>
      {/each}
    </tbody>
  </table>
{:else if view === "adrs"}
  <table id="tblA">
    <colgroup
      ><col style="width:116px" /><col style="width:320px" /><col style="width:168px" /><col
        style="width:168px"
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
          tabindex="0"
          onkeydown={(event) => event.key === "Enter" && onselect(adr.id)}
          onclick={() => onselect(adr.id)}
        >
          <td class="mono" title={adr.id}>{adr.id}</td><td title={adr.t}>{adr.t}</td><td
            ><Badge tone={adr.s === "ACCEPTED" ? "success" : adr.s === "PROPOSED" ? "warning" : "neutral"} class="p-{adr.s.toLowerCase()}">{adr.s}</Badge></td
          >
          <td class="mono lbl">{fmt(adr.u).slice(0, 10)}</td><td class="mono"
            >{relatedSpecs.length}{#if blockers}<span class="blk"
                ><Icon name="block" /> {blockers} blocked</span
              >{/if}</td
          >
          <td
            >{#if adr.sup}<span class="lbl">supersedes</span>
              <Button variant="unstyled"
                type="button"
                class="chip"
                onclick={(event) => {
                  event.stopPropagation();
                  ongo(adr.sup);
                }}>{adr.sup}</Button
              >{/if}{#if successor}<span class="lbl">superseded by</span>
              <Button variant="unstyled"
                type="button"
                class="chip"
                onclick={(event) => {
                  event.stopPropagation();
                  ongo(successor.id);
                }}>{successor.id}</Button
              >{/if}</td
          >
        </tr>
      {/each}
    </tbody>
  </table>
{:else}
  <table id="tblR" aria-label="Project Rules">
    <colgroup>
      <col class="rule-id-col" /><col /><col class="rule-status-col" /><col class="rule-updated" />
    </colgroup>
    <thead><tr><th>ID</th><th>Rule</th><th>Status</th><th class="rule-updated">Updated</th></tr></thead>
    <tbody>
      {#each items as rule (rule.id)}
        <tr class="row" class:sel={selected === rule.id}>
          <td class="mono" title={rule.id}>{rule.id}</td>
          <td>
            <Button variant="unstyled" class="rule-title" title={rule.t}
              aria-current={selected === rule.id ? "true" : undefined}
              onclick={() => onselect(rule.id)}>{rule.t}</Button>
          </td>
          <td><Badge tone={rule.s === "ACTIVE" ? "success" : "neutral"}>{rule.s}</Badge></td>
          <td class="mono lbl rule-updated" title={fmt(rule.u)}>{fmt(rule.u)}</td>
        </tr>
      {/each}
    </tbody>
  </table>
{/if}
{#if !items.length}
  <div class="empty">{view === "rules" && !hasRules ? "No project rules yet." : `No ${view} match the filter.`}</div>
{/if}
