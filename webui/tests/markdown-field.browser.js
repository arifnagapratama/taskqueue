import { createClassComponent } from "svelte/legacy";
import MarkdownField from "../src/components/MarkdownField.svelte";

const assert = (condition, message) => { if (!condition) throw new Error(message); };
const waitFor = async (predicate) => {
  for (let i = 0; i < 100; i++) {
    if (predicate()) return;
    await new Promise(resolve => setTimeout(resolve, 20));
  }
};
async function run() {
try {
  const target = document.createElement("div");
  document.body.append(target);
  const component = createClassComponent({ component: MarkdownField, target, props: {
    value: "# First description\n\n```javascript\nconst answer = 42;\n```", theme: "light",
  }});
  await waitFor(() => target.querySelector("h1"));
  assert(target.querySelector("h1")?.textContent === "First description",
    "First mount stayed empty after async Markdown imports with unchanged value");
  assert(target.querySelector("code .hljs-keyword"), "Code highlighting missing");
  component.$set({ value: "## Updated description\n\n<img src=x onerror=alert(1)>\n\n[unsafe](javascript:alert(1))" });
  await waitFor(() => target.querySelector("h2"));
  assert(target.querySelector("h2")?.textContent === "Updated description", "Value update did not render");
  assert(!target.querySelector("img, script, [onerror], a[href^='javascript:']"), "Unsafe HTML reached DOM");
  component.$set({ value: "```mermaid\ngraph TD\nA[Start] --> B[End]\n```" });
  await waitFor(() => target.querySelector(".mermaid svg"));
  assert(target.querySelector(".mermaid svg"), "Mermaid did not render");
  assert(target.querySelector("[data-expand-mermaid]"), "Mermaid expansion button missing");
  component.$destroy();
  document.body.textContent = "PASS: first mount, value update, sanitization, highlighting, Mermaid";
} catch (error) {
  document.body.textContent = `FAIL: ${error.message}`;
}
}
run();
