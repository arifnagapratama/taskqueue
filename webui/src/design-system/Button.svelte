<script>
  let { variant = "secondary", size = "default", children, ...attributes } = $props();
</script>

<button
  type="button"
  {...attributes}
  class="ds-button ds-button--{variant} ds-button--{size} {attributes.class ?? ''}"
>{@render children?.()}</button>
