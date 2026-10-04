<script>
  import { onMount } from 'svelte';
  import Toolbar from './components/Toolbar.svelte';
  import SpecTable from './components/SpecTable.svelte';
  import EntityTables from './components/EntityTables.svelte';
  import DetailPanel from './components/DetailPanel.svelte';
  import { ADR_STATUS, blocked, matchesEntity, matchesSpec } from './lib/helpers.js';

  let specs = [];
  let epics = [];
  let adrs = [];
  let projects = [];
  let projectId = '';
  let revision = 0;
  let loading = true;
  let saving = false;
  let error = '';
  let failedSnapshot = null;
  let saveQueue = Promise.resolve();
  let view = 'specs';
  let selectedId = null;
  let query = '';
  let stage = 'all';
  let statusFilter = 'all';
  let collapsed = {};
  let theme = localStorageSafe('get');

  async function request(path, options = {}) {
    const response = await fetch(path, {
      ...options, headers: { 'Content-Type': 'application/json' },
    });
    const body = await response.json();
    if (!response.ok) throw new Error(body.error || `Request failed (${response.status})`);
    return body;
  }

  async function loadProject(id) {
    if (saving || failedSnapshot) return;
    loading = true;
    error = '';
    try {
      const state = await request(`/api/projects/${encodeURIComponent(id)}/state`);
      projectId = id;
      revision = state.revision;
      specs = state.specs;
      epics = state.epics;
      adrs = state.adrs;
      selectedId = null;
      collapsed = {};
    } catch (reason) {
      error = reason.message;
    } finally {
      loading = false;
    }
  }

  async function initialize() {
    try {
      projects = await request('/api/projects');
      await loadProject(projects[0].id);
    } catch (reason) {
      loading = false;
      error = reason.message;
    }
  }

  async function createProject() {
    const name = window.prompt('Project name');
    if (!name?.trim()) return;
    try {
      const project = await request('/api/projects', {
        method: 'POST', body: JSON.stringify({ id: crypto.randomUUID(), name: name.trim() }),
      });
      projects = [...projects, project];
      await loadProject(project.id);
    } catch (reason) {
      error = reason.message;
    }
  }

  function localStorageSafe(action, value) {
    try {
      if (action === 'get') return localStorage.getItem('task-queue-theme') || localStorage.getItem('spec-queue-theme') || '';
      if (action === 'set') localStorage.setItem('task-queue-theme', value);
    } catch {
      return '';
    }
    return '';
  }

  function persist() {
    const snapshot = JSON.stringify({ specs, epics, adrs });
    const id = projectId;
    saving = true;
    saveQueue = saveQueue.then(async () => {
      if (failedSnapshot) {
        failedSnapshot = snapshot;
        return;
      }
      try {
        const result = await request(`/api/projects/${encodeURIComponent(id)}/state`, {
          method: 'PUT', body: JSON.stringify({ ...JSON.parse(snapshot), revision }),
        });
        revision = result.revision;
        error = '';
      } catch (reason) {
        failedSnapshot = snapshot;
        error = reason.message;
      }
    });
    const currentQueue = saveQueue;
    currentQueue.then(() => { if (saveQueue === currentQueue) saving = false; });
  }

  function retrySave() {
    failedSnapshot = null;
    persist();
  }

  function refresh() {
    specs = [...specs];
    epics = [...epics];
    adrs = [...adrs];
    persist();
  }

  function updateDetail(message) {
    const item = selectedItem;
    if (!item) return;
    item.u = Date.now();
    if (view === 'specs') item.log.unshift([item.u, 'arif', message]);
    refresh();
  }

  $: selectedItem = view === 'specs'
    ? specs.find((item) => item.id === selectedId)
    : view === 'epics'
      ? epics.find((item) => item.id === selectedId)
      : adrs.find((item) => item.id === selectedId);
  $: visibleSpecs = specs.filter((spec) => matchesSpec(spec, query, stage, epics, adrs));
  $: visibleEpics = epics.filter((epic) => matchesEntity(epic, query, statusFilter));
  $: visibleAdrs = adrs.filter((adr) => matchesEntity(adr, query, statusFilter));
  $: counts = { specs: specs.length, epics: epics.length, adrs: adrs.length };
  $: statusText = `In progress ${specs.filter((spec) => spec.s === 'in_progress').length}  ·  Todo ${specs.filter((spec) => spec.s === 'todo').length}  ·  Finished ${specs.filter((spec) => spec.s === 'finished').length}  ·  Blocked ${specs.filter((spec) => blocked(spec, adrs).length).length}  ·  AI active ${specs.filter((spec) => spec.ai).length}  ·  Showing ${visibleSpecs.length}/${specs.length}`;

  function changeView(nextView, id = null) {
    view = nextView;
    selectedId = id;
    query = '';
    stage = 'all';
    statusFilter = 'all';
  }

  function go(id) {
    changeView(id.startsWith('EPIC-') ? 'epics' : id.startsWith('ADR-') ? 'adrs' : 'specs', id);
  }

  function toggleGroup(key) {
    collapsed = { ...collapsed, [key]: !collapsed[key] };
  }

  function reorder(direction) {
    if (view !== 'specs') return;
    const index = specs.findIndex((spec) => spec.id === selectedId);
    if (index < 0) return;
    const item = specs[index];
    let target = index + direction;
    while (target >= 0 && target < specs.length && specs[target].s !== item.s) target += direction;
    if (target < 0 || target >= specs.length) return;
    specs.splice(index, 1);
    specs.splice(target, 0, item);
    updateDetail(`priority ${direction < 0 ? 'raised' : 'lowered'}`);
  }

  function toggleTheme() {
    theme = theme === 'dark' ? 'light' : 'dark';
    document.documentElement.dataset.theme = theme;
    localStorageSafe('set', theme);
  }

  onMount(() => {
    initialize();
    if (theme) document.documentElement.dataset.theme = theme;
    const handleKey = (event) => {
      if (loading || failedSnapshot) return;
      if (/INPUT|TEXTAREA|SELECT/.test(document.activeElement?.tagName || '')) {
        if (event.key === 'Escape') document.activeElement.blur();
        return;
      }
      const list = view === 'specs' ? visibleSpecs : view === 'epics' ? visibleEpics : visibleAdrs;
      const index = list.findIndex((item) => item.id === selectedId);
      if (event.altKey && event.key === 'ArrowUp') {
        event.preventDefault(); reorder(-1);
      } else if (event.altKey && event.key === 'ArrowDown') {
        event.preventDefault(); reorder(1);
      } else if (event.key === 'j' || event.key === 'ArrowDown') {
        if (!list.length) return;
        event.preventDefault(); selectedId = list[Math.min(index + 1, list.length - 1)].id;
      } else if (event.key === 'k' || event.key === 'ArrowUp') {
        if (!list.length) return;
        event.preventDefault(); selectedId = list[Math.max(index - 1, 0)].id;
      } else if (event.key === 'Escape') {
        selectedId = null;
      }
    };
    document.addEventListener('keydown', handleKey);
    return () => document.removeEventListener('keydown', handleKey);
  });
</script>

<svelte:head><title>Task Queue</title></svelte:head>

<Toolbar
  {view} {query} {stage} {statusFilter} {counts}
  {projects} {projectId} busy={loading || saving || !!failedSnapshot}
  onproject={loadProject} oncreateproject={createProject}
  onview={changeView}
  onquery={(value) => query = value}
  onstage={(value) => stage = value}
  onstatus={(value) => statusFilter = value}
  ontoggleTheme={toggleTheme}
/>

{#if error}
  <div class="backend-message" role="alert">{error}
    {#if failedSnapshot}<button class="btn" onclick={retrySave}>Retry save</button><span>Unsaved changes retained. For a revision conflict, copy your edits before reloading.</span>
    {:else}<button class="btn" onclick={initialize}>Retry connection</button>{/if}
  </div>
{/if}
{#if loading}<div class="backend-message" role="status">Loading project…</div>{/if}
{#if !loading && projectId && !specs.length && !epics.length && !adrs.length}
  <div class="backend-message">This project is empty. Create entities through the API.</div>
{/if}
<div class="main" inert={loading || !!failedSnapshot}>
  <div class="list">
    {#if view === 'specs'}
      <SpecTable
        specs={visibleSpecs} {adrs} selected={selectedId} {collapsed}
        onselect={(id) => selectedId = id}
        ontoggle={toggleGroup}
        ongo={go}
      />
    {:else}
      <EntityTables {view} epics={visibleEpics} adrs={visibleAdrs} {specs} selected={selectedId} {query} {statusFilter} onselect={(id) => selectedId = id} ongo={go} />
    {/if}
  </div>
  <DetailPanel {view} item={selectedItem} {epics} {adrs} {specs} {theme} onclose={() => selectedId = null} onupdate={updateDetail} ongo={go} />
</div>

<div class="status mono">
  <span>{view === 'specs' ? statusText : view === 'epics' ? `Open ${epics.filter((item) => item.s === 'OPEN').length} · Closed ${epics.filter((item) => item.s === 'CLOSED').length} · Showing ${visibleEpics.length}/${epics.length}` : `${ADR_STATUS.map((status) => `${status} ${adrs.filter((item) => item.s === status).length}`).join(' · ')} · Showing ${visibleAdrs.length}/${adrs.length}`}</span>
  <span class="sp"></span><span><kbd>j</kbd><kbd>k</kbd> select</span><span><kbd>Alt</kbd>+<kbd>↑↓</kbd> priority</span><span><kbd>Esc</kbd> close</span><span role="status">{saving ? 'Saving…' : failedSnapshot ? 'Unsaved changes' : 'SQLite'}</span>
</div>
