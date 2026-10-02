let mermaidPromise;
let renderQueue = Promise.resolve();
let diagramId = 0;

function getMermaid() {
  if (!mermaidPromise) {
    mermaidPromise = import("mermaid").then(({ default: mermaid }) => mermaid);
  }
  return mermaidPromise;
}

export function renderMermaid(source, dark) {
  const render = renderQueue.then(async () => {
    const mermaid = await getMermaid();
    mermaid.initialize({
      startOnLoad: false,
      securityLevel: "strict",
      theme: dark ? "dark" : "default",
    });
    const { svg } = await mermaid.render(`taskqueue-diagram-${++diagramId}`, source);
    return svg;
  });
  renderQueue = render.catch(() => {});
  return render;
}
