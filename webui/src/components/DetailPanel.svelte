<script>
  import Button from "../design-system/Button.svelte";
  import Badge from "../design-system/Badge.svelte";
  import Icon from "./Icon.svelte";
  import { onMount } from "svelte";
  import {
    ADR_STATUS,
    DEFAULT_PRIORITY,
    DEFAULT_TASK_KIND,
    EPIC_STATUS,
    STATUS,
    TASK_KINDS,
    blockingAdrs,
    blockingTasks,
    dependencyChoices,
    duration,
    epicRollup,
    fmt,
    taskStatusTone,
  } from "../lib/helpers.js";
  import MarkdownField from "./MarkdownField.svelte";

  export let view = "specs";
  export let item = null;
  export let epics = [];
  export let adrs = [];
  export let specs = [];
  export let taskById = new Map();
  export let theme = "";
  export let onclose = () => {};
  export let onupdate = () => {};
  export let ongo = () => {};

  let addingTest = false;
  let testTitle = "";
  let testSteps = "";
  let testMode = "auto";
  let testRef = "";
  let openTests = true;
  let openHistory = false;
  let openEpicSpecs = true;
  let openEpicAdrs = true;
  let openAdrDecision = true;
  let openAdrConsequences = true;
  let openAdrSpecs = true;
  let fullscreen = false;
  const taskFields = [
    { key: "priority", label: "Priority", fallback: DEFAULT_PRIORITY, pattern: "P(0|[1-9][0-9]*)", hint: "Use P0, P1, P2, or a higher number." },
    { key: "kind", label: "Kind", fallback: DEFAULT_TASK_KIND, pattern: "[a-z][a-z0-9]*(?:-[a-z0-9]+)*", hint: "Use lowercase letters, numbers, and hyphens, starting with a letter." },
  ];

  $: if (!item) fullscreen = false;

  onMount(() => {
    const handleFullscreenKey = (event) => {
      if (
        event.key !== "Escape" || !fullscreen ||
        document.querySelector(".mermaid-lightbox") ||
        /INPUT|TEXTAREA|SELECT/.test(document.activeElement?.tagName || "")
      ) return;
      event.preventDefault();
      event.stopImmediatePropagation();
      fullscreen = false;
    };
    window.addEventListener("keydown", handleFullscreenKey, true);
    return () => window.removeEventListener("keydown", handleFullscreenKey, true);
  });

  $: adrBlockers = view === "specs" && item ? blockingAdrs(item, adrs) : [];
  $: taskBlockers = view === "specs" && item ? blockingTasks(item, taskById) : [];
  $: availableDependencies = view === "specs" && item ? dependencyChoices(item, specs) : [];
  $: rollup = view === "epics" && item ? epicRollup(item, specs) : null;
  $: activeSpecs = rollup?.specs ?? [];
  $: relatedSpecs =
    view === "adrs" && item
      ? specs.filter((spec) => spec.adrs.includes(item.id))
      : [];

  function changed(message) {
    item.u = Date.now();
    onupdate(message);
  }

  function setStatus(value) {
    item.s = value;
    changed(`status → ${value}`);
  }

  function updateTaskField(event, field) {
    const input = event.currentTarget;
    input.value = input.value.trim();
    if (!input.validity.valid) {
      input.setAttribute("aria-invalid", "true");
      return;
    }
    input.removeAttribute("aria-invalid");
    if (input.value === (item[field.key] ?? field.fallback)) return;
    item[field.key] = input.value;
    changed(`${field.key} → ${input.value}`);
  }

  function setSupersedes(event) {
    item.sup = event.currentTarget.value;
    changed(`supersedes → ${item.sup || "none"}`);
  }

  function setSupersededBy(event) {
    const nextId = event.currentTarget.value;
    const previous = adrs.find((adr) => adr.sup === item.id);
    if (previous?.id === nextId) return;
    if (previous) {
      previous.sup = "";
      previous.u = Date.now();
    }
    const next = adrs.find((adr) => adr.id === nextId);
    if (next) {
      next.sup = item.id;
      next.u = Date.now();
    }
    changed(`superseded by → ${nextId || "none"}`);
  }

  function updateTitle(event) {
    item.t = event.currentTarget.value;
    changed("title changed");
  }

  function updateText(key, message, event) {
    item[key] = event.currentTarget.value;
    changed(message);
  }

  function updateLabels(event) {
    item.l = event.currentTarget.value
      .split(",")
      .map((label) => label.trim())
      .filter(Boolean);
    changed("labels changed");
  }

  function addAdr(event) {
    const id = event.currentTarget.value;
    if (!id) return;
    if (!item.adrs.includes(id)) item.adrs.push(id);
    changed(`adr linked: ${id}`);
  }

  function addBlock(event) {
    const id = event.currentTarget.value;
    if (!id) return;
    if (!item.bl.includes(id)) item.bl.push(id);
    if (!item.adrs.includes(id)) item.adrs.push(id);
    changed(`blocked by ${id} added`);
  }

  function removeAdr(id) {
    item.adrs = item.adrs.filter((value) => value !== id);
    item.bl = item.bl.filter((value) => value !== id);
    changed(`adr unlinked: ${id}`);
  }

  function removeBlock(id) {
    item.bl = item.bl.filter((value) => value !== id);
    changed(`blocked by ${id} removed`);
  }

  function addDependency(event) {
    const select = event.currentTarget;
    const id = select.value;
    select.value = "";
    if (!availableDependencies.some((task) => task.id === id)) return;
    item.depends_on = [...(item.depends_on ?? []), id];
    changed(`dependency added: ${id}`);
  }

  function removeDependency(id) {
    item.depends_on = item.depends_on.filter((value) => value !== id);
    changed(`dependency removed: ${id}`);
  }

  function setTestState(test, state) {
    test.st = state;
    test.run = state === "pending" ? null : Date.now();
    changed(
      `test ${test.id} ${state === "pass" ? "passed" : state === "fail" ? "failed" : "reset"}`,
    );
  }

  function addTest() {
    const title = testTitle.trim();
    const steps = testSteps
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean);
    if (!title || !steps.length) return;
    const next =
      item.ac.reduce(
        (max, test) => Math.max(max, Number(test.id.slice(3)) || 0),
        0,
      ) + 1;
    item.ac.push({
      id: `AT-${next}`,
      t: title,
      st: "pending",
      mode: testMode,
      ref: testRef.trim(),
      steps,
      run: null,
      open: false,
    });
    testTitle = "";
    testSteps = "";
    testRef = "";
    addingTest = false;
    changed(`test AT-${next} added: ${title}`);
  }

  function handleTestKeys(event) {
    if (event.key === "Escape") {
      addingTest = false;
    } else if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
      event.preventDefault();
      addTest();
    }
  }

  function removeTest(index) {
    const [test] = item.ac.splice(index, 1);
    changed(`test ${test.id} removed`);
  }
</script>

{#if item}
  <aside class="side open" class:fullscreen aria-label="{view} detail">
    <div class="sh">
      <span class="id mono">{item.id}</span><span class="sp"></span>
      <Button
        class="btn"
        aria-label={fullscreen ? "Exit fullscreen detail" : "Expand detail fullscreen"}
        title={fullscreen ? "Exit fullscreen (Esc)" : "Expand fullscreen"}
        aria-pressed={fullscreen}
        onclick={() => fullscreen = !fullscreen}
      ><Icon name={fullscreen ? "fullscreen_exit" : "fullscreen"} /></Button>
      <Button class="btn" aria-label="Close" onclick={onclose}><Icon name="close" /></Button>
    </div>

    {#if view === "specs"}
      {#if item.ai}
        <div class="aib" role="status">
          <i class="pulse"></i>
          <div class="m">
            <div><b>{item.ai.agent}</b> is working on this task</div>
            <div class="sub mono">
              since {fmt(item.ai.since)} · {duration(
                Date.now() - item.ai.since,
              )} · {item.ai.step}
            </div>
          </div>
        </div>
      {/if}
      {#if adrBlockers.length || taskBlockers.length}<div class="blkb" role="status">
          <Icon name="block" />
          {#if taskBlockers.length}Waiting for task{taskBlockers.length === 1 ? "" : "s"} {taskBlockers.join(", ")} to finish.{/if}
          {#if adrBlockers.length}Waiting for acceptance of {adrBlockers.join(", ")}.{/if}
          AI agents cannot claim this task.
        </div>{/if}
      <div class="sb">
        <div class="sec">
          <textarea rows="2"
            class="title"
            aria-label="Title"
            bind:value={item.t}
            onchange={updateTitle}
          ></textarea>
          <div class="kv">
            <label for="task-status">Status</label><select
              id="task-status"
              value={item.s}
              disabled={Boolean(item.ai)}
              title={item.ai ? "The assigned agent must release the task to change its status." : undefined}
              onchange={(e) => setStatus(e.currentTarget.value)}
              >{#each Object.entries(STATUS) as [status, label]}<option
                  value={status} disabled={status === "in_progress" && taskBlockers.length > 0}
                  >{label}</option
                >{/each}</select
            >
            {#key item.id}
              {#each taskFields as field}
                <label for="task-{field.key}">{field.label}</label>
                <div class="task-field">
                  <input
                    id="task-{field.key}"
                    class:mono={field.key === "priority"}
                    list={field.key === "kind" ? "task-kind-options" : undefined}
                    pattern={field.pattern}
                    required
                    spellcheck="false"
                    value={item[field.key] ?? field.fallback}
                    aria-describedby="task-{field.key}-hint"
                    onchange={(event) => updateTaskField(event, field)}
                  />
                  <span id="task-{field.key}-hint" class="task-field-error" role="alert">{field.hint}</span>
                </div>
              {/each}
            {/key}
            <datalist id="task-kind-options">
              {#each TASK_KINDS as kind}<option value={kind}></option>{/each}
            </datalist>
            <span>Labels</span><input
              class="mono"
              value={item.l.join(", ")}
              onchange={updateLabels}
            />
            <span>Updated</span><span class="mono" style="color:var(--tx)"
              >{fmt(item.u)}</span
            >
          </div>
        </div>
        <h3>Links</h3>
        <div class="sec kv">
          <span>Epic</span><select
            value={item.epic || ""}
            onchange={(e) => {
              item.epic = e.currentTarget.value;
              changed(`epic → ${item.epic || "none"}`);
            }}
            ><option value="">— none —</option>{#each epics as epic}<option
                value={epic.id}>{epic.id} · {epic.t}</option
              >{/each}</select
          >
          <span>ADRs</span>
          <div class="chips">
            {#each item.adrs as id}<Button variant="unstyled"
                type="button"
                class="chip c-{adrs.find((adr) => adr.id === id)?.s.toLowerCase() || ''}"
                onclick={() => ongo(id)}>{id}</Button
              ><Button variant="unstyled"
                type="button"
                class="rm cx"
                aria-label="Remove {id}"
                onclick={() => removeAdr(id)}><Icon name="close" /></Button
              >{/each}
            <select aria-label="Link ADR" onchange={addAdr}
              ><option value="">+ link ADR</option
              >{#each adrs.filter((adr) => !item.adrs.includes(adr.id)) as adr}<option
                  value={adr.id}>{adr.id} · {adr.t}</option
                >{/each}</select
            >
          </div>
          <span>Blocked by</span>
          <div class="chips">
            {#each item.bl as id}<Button variant="unstyled"
                type="button"
                class="chip c-{adrs.find((adr) => adr.id === id)?.s.toLowerCase() || ''}"
                onclick={() => ongo(id)}>{id}</Button
              ><Button variant="unstyled"
                type="button"
                class="rm cx"
                aria-label="Remove blocker {id}"
                onclick={() => removeBlock(id)}><Icon name="close" /></Button
              >{/each}
            <select aria-label="Add blocker" onchange={addBlock}
              ><option value="">+ block on ADR</option
              >{#each adrs.filter((adr) => !item.bl.includes(adr.id)) as adr}<option
                  value={adr.id}>{adr.id} · {adr.t}</option
                >{/each}</select
            >
          </div>
          <label for="task-dependency">Depends on</label>
          <div class="task-dependencies">
            {#each item.depends_on ?? [] as id (id)}
              {@const prerequisite = taskById.get(id)}
              <div class="task-dependency">
                <Button variant="unstyled" class="chip" onclick={() => ongo(id, "specs")}
                  title={prerequisite?.t} aria-label="Open task {id}">{id}</Button>
                <Badge tone={taskStatusTone(prerequisite?.s)}>{STATUS[prerequisite?.s] ?? "Missing"}</Badge>
                <Button variant="unstyled" class="rm cx" aria-label="Remove dependency {id}"
                  onclick={() => removeDependency(id)}><Icon name="close" /></Button>
              </div>
            {/each}
            <select id="task-dependency" aria-label="Add task dependency" onchange={addDependency}
              disabled={!availableDependencies.length}>
              <option value="">{availableDependencies.length ? "+ add task" : "No eligible tasks"}</option>
              {#each availableDependencies as task (task.id)}
                <option value={task.id}>{task.id} · {task.t}</option>
              {/each}
            </select>
          </div>
        </div>
        <h3>Description</h3>
        <div class="sec">
          <MarkdownField
            value={item.d}
            label="Edit"
            {theme}
            onchange={(value) => {
              item.d = value;
              changed("description changed");
            }}
          />
        </div>
        <h3 class="cl">
          <Button variant="unstyled"
            type="button"
            aria-expanded={openTests}
            onclick={() => (openTests = !openTests)}
            ><i class="chev"><Icon name={openTests ? "expand_more" : "chevron_right"} /></i> Acceptance tests ({item.ac.filter(
              (test) => test.st === "pass",
            ).length}/{item.ac.length} passing{item.ac.some(
              (test) => test.st === "fail",
            )
              ? ` · ${item.ac.filter((test) => test.st === "fail").length} failing`
              : ""})</Button
          >
        </h3>
        {#if openTests}<div class="sec">
            {#if !item.ac.length}<div class="lbl" style="padding:2px 0 6px">
                No tests yet. Describe how this task is verified as Given / When
                / Then steps.
              </div>{/if}
            {#each item.ac as test, index (test.id)}
              <div class="at at-{test.st}">
                <div
                  class="ath"
                  role="button"
                  tabindex="0"
                  aria-expanded={test.open ?? test.st === "fail"}
                  onclick={() =>
                    (test.open = !(test.open ?? test.st === "fail"))}
                  onkeydown={(e) =>
                    (e.key === "Enter" || e.key === " ") &&
                    (test.open = !(test.open ?? test.st === "fail"))}
                >
                  <i class="ico" role="img" aria-label={test.st === "pass" ? "Passed" : test.st === "fail" ? "Failed" : "Pending"}
                    ><Icon name={test.st === "pass" ? "check_circle" : test.st === "fail" ? "cancel" : "radio_button_unchecked"} /></i
                  ><span class="ti">{test.t}</span><span class="mode"
                    >{test.mode}</span
                  ><i class="chev"><Icon name={test.open ? "expand_more" : "chevron_right"} /></i>
                </div>
                {#if test.open ?? test.st === "fail"}<div class="atb">
                    <ul class="gh">
                      {#each test.steps as step}<li>{step}</li>{/each}
                    </ul>
                    <div class="atm">
                      <span>{test.ref || "No automation reference"}</span
                      >{#if test.run}<span>Last run: {fmt(test.run)}</span>{/if}
                    </div>
                    <div class="ata">
                      <Button
                        class="btn"
                        onclick={() => setTestState(test, "pass")}>Pass</Button
                      ><Button
                        class="btn"
                        onclick={() => setTestState(test, "fail")}>Fail</Button
                      ><Button
                        class="btn"
                        onclick={() => setTestState(test, "pending")}
                        >Reset</Button
                      ><Button variant="unstyled"
                        class="rm"
                        aria-label="Remove test"
                        onclick={() => removeTest(index)}><Icon name="close" /></Button
                      >
                    </div>
                  </div>{/if}
              </div>
            {/each}
            {#if addingTest}<div class="addt">
                <input
                  bind:value={testTitle}
                  onkeydown={handleTestKeys}
                  placeholder="Test title"
                  aria-label="Test title"
                /><textarea
                  bind:value={testSteps}
                  onkeydown={handleTestKeys}
                  placeholder="Given ...&#10;When ...&#10;Then ..."
                  aria-label="Scenario steps"
                ></textarea>
                <div class="r">
                  <select bind:value={testMode}
                    ><option value="auto">auto</option><option value="manual"
                      >manual</option
                    ></select
                  ><input
                    class="mono"
                    bind:value={testRef}
                    onkeydown={handleTestKeys}
                    placeholder="Automation ref (optional)"
                  />
                </div>
                <div class="r">
                  <Button variant="primary" class="btn pri" onclick={addTest}>Add test</Button
                  ><Button class="btn" onclick={() => (addingTest = false)}
                    >Cancel</Button
                  ><span class="lbl" style="align-self:center"
                    >Ctrl+Enter adds</span
                  >
                </div>
              </div>{:else}<Button
                class="btn"
                style="margin-top:4px"
                onclick={() => (addingTest = true)}>+ Test</Button
              >{/if}
          </div>{/if}
        <h3 class="cl">
          <Button variant="unstyled"
            type="button"
            aria-expanded={openHistory}
            onclick={() => (openHistory = !openHistory)}
            ><i class="chev"><Icon name={openHistory ? "expand_more" : "chevron_right"} /></i> History ({item.log
              .length})</Button
          >
        </h3>
        {#if openHistory}<div class="sec">
            <ul class="tl">
              {#each item.log as entry}<li>
                  <i class="dot"></i>
                  <div class="ts mono">{fmt(entry[0], true)}</div>
                  <div class="ev">
                    <span class="who">{entry[1]}</span><span>{entry[2]}</span>
                  </div>
                </li>{/each}
            </ul>
          </div>{/if}
      </div>
    {:else if view === "epics"}
      <div class="sb">
        <div class="sec">
          <textarea rows="2"
            class="title"
            aria-label="Title"
            bind:value={item.t}
            onchange={updateTitle}
          ></textarea>
          <div class="kv">
            <span>Status</span><select
              value={item.s}
              onchange={(e) => setStatus(e.currentTarget.value)}
              >{#each EPIC_STATUS as status}<option value={status}
                  >{status}</option
                >{/each}</select
            ><span>Updated</span><span class="mono">{fmt(item.u)}</span>
          </div>
        </div>
        <h3>Description</h3>
        <div class="sec">
          <MarkdownField
            value={item.d}
            label="Edit"
            {theme}
            onchange={(value) => {
              item.d = value;
              changed("description changed");
            }}
          />
        </div>
        {#if rollup}<div class="sec">
            <div class="kv mono">
              <span>Tasks</span><span
                >{rollup.done} finished · {rollup.active} in progress · {rollup.verify} verify · {rollup.todo} todo · {rollup.deferred} deferred</span
              ><span>Tests</span><span
                >{rollup.passed}/{rollup.totalTests} passing</span
              ><span>AI</span><span>{rollup.agents} active</span>
            </div>
          </div>
          <h3 class="cl">
            <Button variant="unstyled"
              type="button"
              aria-expanded={openEpicSpecs}
              onclick={() => (openEpicSpecs = !openEpicSpecs)}
              ><i class="chev"><Icon name={openEpicSpecs ? "expand_more" : "chevron_right"} /></i> Tasks ({activeSpecs.length})</Button
            >
          </h3>
          {#if openEpicSpecs}<div class="sec lst">
              {#each activeSpecs as spec}<div
                  class="lr"
                  role="button"
                  tabindex="0"
                  onclick={() => ongo(spec.id)}
                  onkeydown={(event) => event.key === "Enter" && ongo(spec.id)}
                >
                  <span class="mono lbl">{spec.id}</span><span class="ti"
                    >{spec.t}</span
                  ><Badge tone={taskStatusTone(spec.s)}>{STATUS[spec.s]}</Badge>
                </div>{/each}
            </div>{/if}
          {@const epicAdrs = [
            ...new Set(activeSpecs.flatMap((spec) => spec.adrs)),
          ]}
          <h3 class="cl">
            <Button variant="unstyled"
              type="button"
              aria-expanded={openEpicAdrs}
              onclick={() => (openEpicAdrs = !openEpicAdrs)}
              ><i class="chev"><Icon name={openEpicAdrs ? "expand_more" : "chevron_right"} /></i> ADRs referenced ({epicAdrs.length})</Button
            >
          </h3>
          {#if openEpicAdrs}<div class="sec">
              {#each epicAdrs as id}<Button variant="unstyled"
                  type="button"
                  class="chip"
                  onclick={() => ongo(id)}>{id}</Button
                >{/each}
            </div>{/if}{/if}
      </div>
    {:else}
      {@const blockers =
        item.s === "ACCEPTED"
          ? 0
          : specs.filter((spec) => spec.bl.includes(item.id)).length}
      <div class="sb">
        <div class="sec">
          <textarea rows="2"
            class="title"
            aria-label="Title"
            bind:value={item.t}
            onchange={updateTitle}
          ></textarea>
          <div class="kv">
            <span>Status</span><select
              value={item.s}
              onchange={(e) => setStatus(e.currentTarget.value)}
              >{#each ADR_STATUS as status}<option value={status}
                  >{status}</option
                >{/each}</select
            ><span>Date</span><span class="mono"
              >{fmt(item.u).slice(0, 10)}</span
            >
            <span>Supersedes</span><select
              aria-label="Supersedes ADR"
              value={item.sup || ""}
              onchange={setSupersedes}
              ><option value="">— none —</option
              >{#each adrs.filter((adr) => adr.id !== item.id && adr.sup !== item.id) as adr}<option
                  value={adr.id}>{adr.id} · {adr.t}</option
                >{/each}</select
            >
            <span>Superseded by</span><select
              aria-label="Superseded by ADR"
              value={adrs.find((adr) => adr.sup === item.id)?.id || ""}
              onchange={setSupersededBy}
              ><option value="">— none —</option
              >{#each adrs.filter((adr) => adr.id !== item.id && (!adr.sup || adr.sup === item.id)) as adr}<option
                  value={adr.id}>{adr.id} · {adr.t}</option
                >{/each}</select
            >
          </div>
          {#if blockers}<div class="blk" style="margin:6px 0 0">
              <Icon name="block" /> Blocking {blockers} spec{blockers > 1 ? "s" : ""} until this ADR
              is accepted.
            </div>{/if}
        </div>
        <h3>Context</h3>
        <div class="sec">
          <MarkdownField
            value={item.ctx}
            label="Edit"
            {theme}
            onchange={(value) => {
              item.ctx = value;
              changed("context changed");
            }}
          />
        </div>
        <h3 class="cl">
          <Button variant="unstyled"
            type="button"
            aria-expanded={openAdrDecision}
            onclick={() => (openAdrDecision = !openAdrDecision)}
            ><i class="chev"><Icon name={openAdrDecision ? "expand_more" : "chevron_right"} /></i> Decision</Button
          >
        </h3>
        {#if openAdrDecision}<div class="sec">
            <MarkdownField
              value={item.dec}
              label="Edit"
              {theme}
              onchange={(value) => {
                item.dec = value;
                changed("decision changed");
              }}
            />
          </div>{/if}
        <h3 class="cl">
          <Button variant="unstyled"
            type="button"
            aria-expanded={openAdrConsequences}
            onclick={() => (openAdrConsequences = !openAdrConsequences)}
            ><i class="chev"><Icon name={openAdrConsequences ? "expand_more" : "chevron_right"} /></i> Consequences</Button
          >
        </h3>
        {#if openAdrConsequences}<div class="sec">
            <MarkdownField
              value={item.cons}
              label="Edit"
              {theme}
              onchange={(value) => {
                item.cons = value;
                changed("consequences changed");
              }}
            />
          </div>{/if}
        <h3 class="cl">
          <Button variant="unstyled"
            type="button"
            aria-expanded={openAdrSpecs}
            onclick={() => (openAdrSpecs = !openAdrSpecs)}
            ><i class="chev"><Icon name={openAdrSpecs ? "expand_more" : "chevron_right"} /></i> Tasks ({relatedSpecs.length})</Button
          >
        </h3>
        {#if openAdrSpecs}<div class="sec lst">
            {#each relatedSpecs as spec}<div
                class="lr"
                role="button"
                tabindex="0"
                onclick={() => ongo(spec.id)}
                onkeydown={(event) => event.key === "Enter" && ongo(spec.id)}
              >
                <span class="mono lbl">{spec.id}</span><span class="ti"
                  >{spec.t}</span
                ><Badge tone={taskStatusTone(spec.s)}>{STATUS[spec.s]}</Badge>
              </div>{/each}
          </div>{/if}
      </div>
    {/if}
  </aside>
{/if}
