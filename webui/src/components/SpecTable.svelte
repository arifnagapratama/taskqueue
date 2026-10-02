<script>
  import { ORDER, STATUS, blocked, fmt, testPercent } from "../lib/helpers.js";
  export let specs = [];
  export let adrs = [];
  export let selected = null;
  export let collapsed = {};
  export let onselect = () => {};
  export let ontoggle = () => {};
  export let ongo = () => {};

  $: groups = ORDER.map((status) => ({
    key: status,
    label: STATUS[status],
    specs: specs.filter((spec) => spec.s === status),
  })).filter((item) => item.specs.length);
</script>

<table id="tbl">
  <colgroup id="cg"
    ><col style="width:44px" /><col style="width:76px" /><col
      style="width:380px"
    /><col style="width:92px" /><col style="width:132px" /><col
      style="width:96px"
    /><col style="width:150px" /><col style="width:130px" /></colgroup
  >
  <thead
    ><tr
      ><th style="text-align:right">#</th><th>ID</th><th>Task</th><th>Epic</th
      ><th>Status</th><th>Tests</th><th>Labels</th><th>Updated</th></tr
    ></thead
  >
  <tbody>
    {#each groups as section (section.key)}
      <tr class="grp" onclick={() => ontoggle(section.key)}
        ><td colspan="8"
          >{collapsed[section.key] ? "▸" : "▾"}
          {section.label}<span class="n">{section.specs.length}</span></td
        ></tr
      >
      {#if !collapsed[section.key]}
        {#each section.specs as spec, index (spec.id)}
          {@const pass = spec.ac.filter((test) => test.st === "pass").length}
          {@const fail = spec.ac.filter((test) => test.st === "fail").length}
          {@const blockedBy = blocked(spec, adrs)}
          <tr
            class="row s-{spec.s}"
            class:sel={selected === spec.id}
            class:ai-on={spec.ai}
            tabindex="0"
            onclick={() => onselect(spec.id)}
            onkeydown={(event) => event.key === "Enter" && onselect(spec.id)}
          >
            <td class="rank mono">{spec.s === "finished" ? "" : index + 1}</td>
            <td class="mono">{spec.id}</td>
            <td title={spec.t}>{spec.t}</td>
            <td
              >{#if spec.epic}<button
                  type="button"
                  class="chip"
                  onclick={(event) => {
                    event.stopPropagation();
                    ongo(spec.epic);
                  }}>{spec.epic}</button
                >{:else}<span class="lbl">—</span>{/if}</td
            >
            <td class="st"
              ><span class="pill p-{spec.s}">{STATUS[spec.s]}</span>
              {#if spec.ai}<span
                  class="ai"
                  title="{spec.ai.agent}: {spec.ai.step}"
                  ><i class="pulse"></i>AI</span
                >{/if}
              {#if blockedBy.length}<span
                  class="blk"
                  title="Blocked by {blockedBy.join(', ')} (not accepted)"
                  >⛔ {blockedBy[0]}{blockedBy.length > 1
                    ? ` +${blockedBy.length - 1}`
                    : ""}</span
                >{/if}
            </td>
            <td class="mono"
              ><span class="prog"
                ><i style={`width:${testPercent(spec)}%`}></i></span
              >{pass}/{spec.ac.length}{#if fail}<span class="ft">
                  ✕{fail}</span
                >{/if}</td
            >
            <td class="lbl">{spec.l.join(", ")}</td><td class="mono lbl"
              >{fmt(spec.u)}</td
            >
          </tr>
        {/each}
      {/if}
    {/each}
  </tbody>
</table>
{#if !groups.length}<div class="empty">No tasks match the filter.</div>{/if}
