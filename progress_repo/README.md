# Contract Progress Tracker

A production-quality, browser-based Contract Progress Tracker for construction / life-science
project controls. Tracks progress and performance through a
**Program &rarr; Building &rarr; Contract &rarr; Activity &rarr; Gate** hierarchy, and rolls it back up
**Activity &rarr; Contract &rarr; Building &rarr; Program**.

## Status

This is the **major upgrade** of the initial foundation build (branch `feature/progress-tracker-pwa`,
commit `7d2b7f9`). The single-file `app.js` + `localStorage` prototype has been replaced with a
modular architecture, IndexedDB persistence, rules-of-credit gates, actual-hours tracking,
SPI/LPI performance metrics, and reporting-period locking/snapshots.

## Architecture

```
progress_repo/
  index.html          Shell markup, loads app.js as an ES module
  styles.css           Professional project-controls visual system
  app.js               Bootstraps the app (loads dataset, mounts UI)
  curve_generator.html Original standalone curve tool (kept for reference)
  src/
    schema.js          Data model, entity factories, defaults, validation
    calculations.js    Curves, planned/forecast/actual %, EV/PV, SPI/LPI, rollups
    periods.js         Weekly (Sun-Sat) / monthly period bucketing & lifecycle
    store.js            IndexedDB persistence (localStorage fallback) + JSON import/export
    charts.js            Canvas S-curve rendering + accessible data-table alternative
    ui.js                All screens/tabs, forms, and event wiring
    sample-data.js        Realistic sample dataset generator for demos/testing
  README.md
```

No external runtime dependencies — pure HTML/CSS/JS, deployable as static files via GitHub Pages.

## Data model

```
Program
 └─ Building
     └─ Contract (budget, authorized hours, baseline/forecast dates, type)
         └─ Activity (code/WBS, budget, hours, baseline+forecast dates & curves,
                       optional forecast/actual overrides)
             └─ Gate (name, weight %, completion %, status date, notes, updatedBy)
```

Actual labor hours are entered as dated records tied to an Activity and the currently open
reporting period. Every gate edit, override, hour entry, and period transition creates an
**audit event** (`entityType`, `entityId`, `eventType`, `before`, `after`, `reason`, `performedBy`,
`timestamp`).

## Calculations

- **Gate earned credit** = gate weight % × (gate completion % / 100)
- **Activity calculated actual %** = sum of gate earned credit (gate weights must total 100%,
  ±0.05 tolerance)
- **Planned %** = curve fraction between baseline start/finish, evaluated at the status date
- **Forecast %** = curve fraction between forecast start/finish, unless manually overridden
- **Earned Value** = budget × actual %  |  **Planned Value** = budget × planned %
- **Earned Hours** = planned hours × actual %  |  **Actual Hours** = sum of dated hour records
- **SPI** = earned value / planned value (period and cumulative)
- **LPI** = earned hours / actual hours (period and cumulative)
- **Rollups never average ratios.** At every level (activity → contract → building → program),
  numerators and denominators are summed first, then divided. A zero denominator renders as
  `—`, never `0` or `Infinity`.

Supported progress curves: **Linear, Standard S-Curve, Front-Loaded, Back-Loaded** (native Canvas
rendering, no chart library).

## Reporting periods

- **Weekly**: Sunday 12:01 AM through Saturday 11:59 PM, local project time zone.
- **Monthly**: 1st 12:01 AM through the last day of the month, 11:59 PM.
- Only one period is **Open** at a time. All gate/hour/forecast/actual edits attach to the open
  period.
- **Closing** a period validates it, writes a locked **snapshot** (planned value, earned value,
  earned/actual hours, period & cumulative SPI/LPI, full rollups, timestamp, administrator), marks
  it Closed, and opens the next period.
- **Reopening** a closed period requires a mandatory reason from the named administrator and logs
  an audit event; subsequent edits are expected to be followed by re-closing to regenerate the
  snapshot.

## Storage & data portability

- **IndexedDB** is the primary browser database (single object store holding the full dataset),
  with a **localStorage** fallback if IndexedDB is unavailable.
- **JSON import/export is the authoritative backup and transfer format.** The Settings screen
  always prompts for an export before destructive actions (import replace, sample-data load, or
  full reset).
- Dataset shape includes `schemaVersion`, `settings` (adminName, reportingCurrency, locale,
  timeZone, reportingPeriod, statusDate), and arrays for programs, buildings, contracts,
  activities, gates, actualHours, auditEvents, periods, and snapshots.

## Currency & formatting

`reportingCurrency` defaults to `USD` and can be changed to any ISO currency code. This only
changes **display/entry formatting** via `Intl.NumberFormat` — no exchange-rate conversion is ever
applied to existing values.

## Running locally / deploying

1. Serve the `progress_repo/` folder with any static file server (or open `index.html` directly —
   ES modules require `http(s)://`, so a simple server such as `npx serve` or the VS Code "Live
   Server" extension is recommended for local development).
2. For GitHub Pages: enable Pages on this repository pointed at this branch/folder (or merge to
   `main` and point Pages at `/progress_repo`).
3. On first load, the app creates an empty dataset. Use **Settings / Data → Load Sample Data** to
   explore a populated example, or start building your Program/Building/Contract/Activity
   structure directly.

## Manual test checklist (performed prior to this commit)

- [x] Add Program → Building → Contract → Activity.
- [x] Add several gates totaling 100% (validated live in the Activity Detail screen).
- [x] Partial completion on one gate correctly recalculates earned actual % (verified in Node:
      15+20+28+5 = 68% for a 4-gate example).
- [x] Actual hours entry updates earned hours and LPI.
- [x] SPI computed from earned value / planned value at activity and rollup levels.
- [x] Rollup SPI/LPI sum numerator & denominator across activities rather than averaging ratios
      (verified in Node: two activities individually earn 80/100 and 220/200 roll up to exactly
      300/300 = 1.00, not an average of the two ratios).
- [x] Zero-denominator SPI/LPI renders as `—`.
- [x] Weekly bucketing for 2026-09-10 (a Thursday) resolves to 2026-09-06 → 2026-09-12
      (Sunday–Saturday).
- [x] Monthly bucketing for 2026-09-10 resolves to 2026-09-01 → 2026-09-30.
- [x] Closing a period blocks new hour entries dated before the new open period's start via the
      Hours screen's period check, and creates a snapshot; reopening requires a typed reason and
      is recorded as an audit event.
- [x] JSON export/import round-trips the full dataset (schema-validated on import, with a
      confirmation prompt before replacing local data).

## Roadmap

- Optional backend (Supabase/Postgres) for authentication, multi-user roles, file attachments,
  and centralized audit control — the current version is intentionally single-user with one named
  local administrator and no real security.
- Deeper drag-and-drop gate reordering (currently up/down buttons) and per-contract rules-of-credit
  templates that can be copied into new activities as a starting point.
