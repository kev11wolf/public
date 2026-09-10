# Contract Progress Tracker

A browser-based, JSON-portable contract progress tracker. It supports the hierarchy **program -> building -> contract -> activity**, contract budgets, rules of credit, live planned/forecast/actual progress, budget-weighted rollups, dated update history, and JSON import/export.

## Run it

Open `index.html` in a modern desktop browser, or publish the `progress_repo` folder through GitHub Pages. No build system or server is required for the local single-user version.

## Data handling

- The app persists the active dataset in browser local storage.
- Use **Export JSON** for portable backups and to move data between browsers/devices.
- Use **Import JSON** to load a validated exported dataset.
- The JSON editor is intended for controlled bulk changes; export a backup before applying edits.

## Rollup logic

Program, building, and contract dashboard results use budget-weighted values across activities:

`rolled-up progress = sum(activity budget x activity progress percent) / sum(activity budget)`

The current implementation stores planned, forecast, and actual percentages directly on every activity and preserves dated actual/forecast revisions in the progress-update history.

## Production next steps

For multi-user use, central record ownership, role-based access, attachments, and audit-grade change control, migrate the same JSON model to a managed backend such as Supabase/Postgres. Keep this static edition as an offline-capable planning and import/export client.
