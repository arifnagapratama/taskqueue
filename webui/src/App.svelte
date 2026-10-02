<script>
  import { onMount } from 'svelte';
  import Toolbar from './components/Toolbar.svelte';
  import SpecTable from './components/SpecTable.svelte';
  import EntityTables from './components/EntityTables.svelte';
  import DetailPanel from './components/DetailPanel.svelte';
  import { createDemoData } from './lib/data.js';
  import { ADR_STATUS, blocked, matchesEntity, matchesSpec } from './lib/helpers.js';

  const STORAGE_KEY = 'task-queue-demo-v1';
  const initial = loadData();
  let specs = initial.specs;
  let epics = initial.epics;
  let adrs = initial.adrs;
  let view = 'specs';
  let selectedId = 'TASK-12';
  let query = '';
  let stage = 'all';
  let statusFilter = 'all';
  let collapsed = {};
  let theme = localStorageSafe('get');

  function loadData() {
    const demo = createDemoData();
    try {
      const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || localStorage.getItem('spec-queue-demo-v1'));
      if (saved && Array.isArray(saved.specs) && Array.isArray(saved.epics) && Array.isArray(saved.adrs)) {
        return { specs: saved.specs, epics: saved.epics, adrs: saved.adrs };
      }
    } catch {
      // Start with the bundled example data if browser storage is empty or invalid.
    }
    return demo;
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
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify({ specs, epics, adrs }));
    } catch {
      // Keep the current session usable if storage is unavailable.
    }
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
    if (theme) document.documentElement.dataset.theme = theme;
    const handleKey = (event) => {
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
  onview={changeView}
  onquery={(value) => query = value}
  onstage={(value) => stage = value}
  onstatus={(value) => statusFilter = value}
  ontoggleTheme={toggleTheme}
/>

<div class="main">
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
  <span>{view === 'specs' ? statusText : view === 'epics' ? `Open ${epics.filter((item) => item.s === 'open').length} · Closed ${epics.filter((item) => item.s === 'closed').length} · Showing ${visibleEpics.length}/${epics.length}` : `${ADR_STATUS.map((status) => `${status} ${adrs.filter((item) => item.s === status).length}`).join(' · ')} · Showing ${visibleAdrs.length}/${adrs.length}`}</span>
  <span class="sp"></span><span><kbd>j</kbd><kbd>k</kbd> select</span><span><kbd>Alt</kbd>+<kbd>↑↓</kbd> priority</span><span><kbd>Esc</kbd> close</span><span>MCP: frontend demo</span>
</div>
