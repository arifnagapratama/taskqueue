<script>
  let { tone = "neutral", children, ...attributes } = $props();
</script>

<span {...attributes} class="ds-badge ds-badge--{tone} pill {attributes.class ?? ''}">
  <span class="ds-badge__dot" aria-hidden="true"></span>{@render children?.()}
</span>
