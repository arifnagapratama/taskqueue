# UI design system

The application adopts the Splunk-inspired component language from
`simple-design-system` (shared primitives and Task Queue showcase 1). Its
navigation, project model, table columns and detail-panel interactions remain
those of Task Queue. This is a local implementation of that reference, not an
installation of the official Splunk React component library.

## Layers

- `webui/src/design-system/tokens.css`: semantic colors, typography and theme
  values. Both explicit themes and the system color preference are supported.
- `webui/src/design-system/components.css`: shared controls, button variants,
  badges, focus and disabled states.
- `Button.svelte` and `Badge.svelte` in that directory: reusable primitives.
- `webui/src/app.css`: application layout, tables, detail sections and responsive
  rules. Keep application positioning out of the primitives.
- `webui/src/components/Icon.svelte`: bundled Material Icons, hidden from
  assistive technology when the surrounding control provides its label.

## Usage

Use `Button` for actions, supplying an accessible name for icon-only buttons.
Use primary for the main action, secondary for ordinary actions, tertiary for
low-emphasis actions, danger for destructive actions, and unstyled only when the
surrounding component owns its interaction styling (tabs or collapsible headers).
Keep native inputs and selects for their built-in keyboard behavior.

Status badges use semantic tones and a visible text label. Color alone must not
communicate status. Tables may scroll horizontally; status labels and dates
must fit their columns. Long titles may use ellipsis in lists with the full
value available through a title or the detail view. Detail text and labels wrap
within the panel. Preserve visible keyboard focus and reduced-motion support.

## Verification

Run `npm --prefix webui run build` and
`npm --prefix webui run test:markdown`. For visual changes inspect Tasks, Epics,
ADRs, detail/fullscreen panels and login in light/dark themes, including narrow
viewports. Use a temporary database for preview data.
