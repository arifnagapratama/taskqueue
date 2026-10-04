# Task Queue frontend

Svelte + Vite UI. Run `npm ci` then `npm run dev` here. Start the FastAPI
backend separately from the repository root with
`uv run uvicorn backend.main:app --port 8080 --reload`.
Vite proxies `/api` requests to that backend. `npm run build` creates `dist/`.

Tasks and project data are stored in SQLite through REST; theme preferences stay
in browser storage. Deployment, MCP tools and backend instructions: [../README.md](../README.md).
