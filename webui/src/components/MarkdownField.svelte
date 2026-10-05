<script>
  import { onMount, tick } from "svelte";
  import { renderMermaid } from "../lib/mermaid.js";

  export let value = "";
  export let label = "Edit";
  export let theme = "";
  export let onchange = () => {};
  let editing = false;
  let content;
  let renderId = 0;
  let expandedSource = "";
  let fullscreenContainer;
  let expandedRenderId = 0;
  let markdown;
  let DOMPurify;
  let hljs;

  onMount(async () => {
    const [markdownModule, purifierModule, highlightModule] = await Promise.all([
      import("markdown-it"),
      import("dompurify"),
      import("highlight.js/lib/common"),
    ]);
    const MarkdownIt = markdownModule.default;
    DOMPurify = purifierModule.default;
    hljs = highlightModule.default;
    markdown = new MarkdownIt({
      html: false,
      linkify: true,
      breaks: false,
      highlight(code, language) {
        if (language === "mermaid") return "";
        if (language && hljs.getLanguage(language)) {
          try {
            return hljs.highlight(code, { language }).value;
          } catch {
            /* Use escaped source below. */
          }
        }
        return "";
      },
    });
    markdown.renderer.rules.fence = (tokens, index, options, env) => {
      const token = tokens[index];
      const language = token.info.trim().split(/\s+/)[0];
      if (language === "mermaid") {
        const diagramIndex = env.diagrams.push(token.content) - 1;
        return `<div class="mermaid" data-diagram-index="${diagramIndex}"></div>`;
      }
      const highlighted = markdown.options.highlight(token.content, language);
      const code = highlighted || markdown.utils.escapeHtml(token.content);
      const className = language
        ? ` class="language-${markdown.utils.escapeHtml(language)}"`
        : "";
      return `<pre><code${className}>${code}</code></pre>`;
    };
  });
  function renderMarkdown(source) {
    if (!markdown || !DOMPurify) return { html: "", diagrams: [] };
    const env = { diagrams: [] };
    const html = DOMPurify.sanitize(markdown.render(source || "", env), {
      ADD_ATTR: ["target", "rel", "data-diagram-index"],
    });
    return { html, diagrams: env.diagrams };
  }
  $: rendered = renderMarkdown(value);
  $: html = rendered.html;
  $: rendered, theme, editing, renderDiagrams();
  $: expandedSource, theme, fullscreenContainer, renderExpandedDiagram();

  function handleKeydown(event) {
    if (expandedSource && event.key === "Escape") expandedSource = "";
  }

  function focusDialog(node) {
    const previous = document.activeElement;
    node.focus();
    return { destroy: () => previous?.isConnected && previous.focus() };
  }

  function handleDialogKeydown(event) {
    event.stopPropagation();
    handleKeydown(event);
    if (event.key === "Tab") {
      event.preventDefault();
      event.currentTarget.querySelector("button")?.focus();
    }
  }

  async function renderDiagrams() {
    const currentRun = ++renderId;
    const sources = rendered.diagrams;
    const dark = theme === "dark" ||
      (!theme && window.matchMedia("(prefers-color-scheme: dark)").matches);
    await tick();
    if (currentRun !== renderId || !content || editing) return;
    const nodes = [...content.querySelectorAll("[data-diagram-index]")];
    if (!nodes.length) return;
    try {
      if (currentRun === renderId) {
        for (const node of nodes) {
          const source = sources[Number(node.dataset.diagramIndex)];
          if (source === undefined) continue;
          const svg = await renderMermaid(source, dark);
          if (currentRun !== renderId || !node.isConnected) return;
          node.innerHTML = svg;
          const button = document.createElement("button");
          button.type = "button";
          button.className = "mermaid-expand";
          button.dataset.expandMermaid = "true";
          button.setAttribute("aria-label", "Expand diagram fullscreen");
          button.title = "Expand fullscreen";
          button.textContent = "⛶";
          button.addEventListener("click", () => {
            expandedSource = source;
          });
          node.append(button);
        }
      }
    } catch (error) {
      console.warn("Unable to render Mermaid diagram", error);
    }
  }

  async function renderExpandedDiagram() {
    const currentRun = ++expandedRenderId;
    const currentSource = expandedSource;
    await tick();
    if (!currentSource || currentSource !== expandedSource || !fullscreenContainer) return;
    const dark =
      theme === "dark" ||
      (!theme && window.matchMedia("(prefers-color-scheme: dark)").matches);
    try {
      const svg = await renderMermaid(currentSource, dark);
      if (currentRun === expandedRenderId && fullscreenContainer && expandedSource === currentSource) {
        fullscreenContainer.innerHTML = svg;
      }
    } catch (error) {
      console.warn("Unable to render fullscreen Mermaid diagram", error);
    }
  }
</script>

<svelte:window onkeydown={handleKeydown} />

<div class="md-field">
  <div class="md-actions">
    <button class="btn" onclick={() => (editing = !editing)}
      >{editing ? "Preview" : label}</button
    >
  </div>
  {#if editing}
    <textarea
      aria-label={label}
      {value}
      oninput={(event) => onchange(event.currentTarget.value)}
    ></textarea>
  {:else if html}
    <div class="markdown" bind:this={content}>{@html html}</div>
  {:else}
    <div class="markdown empty-md">No content.</div>
  {/if}
  {#if expandedSource}
    <div class="mermaid-lightbox" role="dialog" aria-modal="true" aria-label="Mermaid diagram fullscreen" tabindex="-1" use:focusDialog onkeydown={handleDialogKeydown}>
      <button class="mermaid-close" aria-label="Close fullscreen diagram" onclick={() => (expandedSource = "")}>✕</button>
      <div class="mermaid-fullscreen" bind:this={fullscreenContainer}></div>
    </div>
  {/if}
</div>
