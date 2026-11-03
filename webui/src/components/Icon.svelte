<script>
  import "@fontsource/material-icons/400.css";
  export let name;
</script>

<span class="app-icon" aria-hidden="true">{name}</span>

<style>
  :global(.app-icon) {
    font-family: "Material Icons";
    font-weight: normal;
    font-style: normal;
    font-size: 18px;
    line-height: 1;
    letter-spacing: normal;
    text-transform: none;
    display: inline-flex;
    white-space: nowrap;
    word-wrap: normal;
    direction: ltr;
    font-feature-settings: "liga";
    -webkit-font-smoothing: antialiased;
    vertical-align: middle;
    flex-shrink: 0;
  }
</style>
