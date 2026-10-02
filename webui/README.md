# Task Queue frontend prototype

This is a Svelte + Vite app. From this directory, run `npm install` once and then `npm run dev`. `npm run build` creates the static production build in `dist/`.

The UI uses bundled sample data because MCP and the backend are not connected yet. Changes are saved in browser `localStorage` under `task-queue-demo-v1`; remove that key in browser storage to restore the sample data. MCP supplies and creates tasks; the UI is for tracking status, priority, acceptance tests, and Epic/ADR links.
