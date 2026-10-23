# Web Dashboard Redesign Plan

**Status:** Proposed  
**Product:** AutomaticSAP Service Performance & Scoring RPA  
**Target:** `web_dashboard.py` and `static/`

## Product direction

Turn the existing operator dashboard into a clear, modern operations console. Keep the Python automation engine, FastAPI API, job definitions, SAP GUI interaction, SQL behavior, scheduler, and existing SSE job logs as the source of truth. Redesign the web experience around the tasks operators perform: understand system readiness, start the correct work, monitor it, and recover from failures.

## Current state

- The repository is a Python application. The web server is FastAPI in `web_dashboard.py`.
- The browser UI is vanilla HTML/CSS/JavaScript in `static/index.html`, `static/style.css`, and `static/app.js`.
- There is also a desktop Tkinter dashboard in `dashboard.py`.
- The web dashboard already covers job execution, logs, sequences, scheduling, database settings, and SAP status. Preserve these capabilities and existing API contracts.
- No React toolchain or `package.json` is present. React is a possible implementation direction, not a prerequisite. First assess whether a polished vanilla implementation better fits deployment and maintenance constraints.

## Recommended UI pattern

Use an **operations control center** pattern: persistent navigation, a compact system-health header, a useful overview with status and recent activity, task-oriented job catalog, and focused detail views for live execution, sequences, schedules, and settings. Use progressive disclosure for advanced parameters. The visual language should be light, calm, data-dense, and professional, with SAP blue as an accent rather than a full-screen dark theme.

Interaction patterns: live status badges, streaming logs with pause/clear/filter, job search and category filters, run confirmation where an action is consequential, responsive navigation, empty/loading/error states, keyboard-accessible dialogs and controls, and toasts for short-lived feedback. Avoid decorative charts without real data and avoid novelty animation.

## Delivery phases

1. **Audit and baseline:** inventory routes, API payloads, existing UI actions, browser support and operator workflows. Record compatibility constraints and take screenshots of current views.
2. **Information architecture and design system:** define navigation, responsive layout, typography, spacing, colors, status semantics, reusable controls, and interaction prototypes.
3. **Overview and job catalog:** deliver at-a-glance service/SAP/database status, daily workflow entry point, job search/filter, clear job cards/rows and parameter forms.
4. **Execution and observability:** improve active-job list, live log stream, progress/status, cancellation, completion summaries and recoverable error presentation.
5. **Schedules, sequences and settings:** redesign existing features with validation, explicit save states, accessible dialogs, and clear operator feedback.
6. **Hardening and rollout:** verify the flows in a browser and against existing backend contracts; check responsive behavior, accessibility, performance, and Windows startup; document build/run steps and rollback.

## Product guardrails

- Do not change SAP transaction logic, ETL, SQL schemas/queries, job CLI arguments, scheduler semantics, or credential handling as part of visual redesign.
- Do not expose `.env` credentials in the browser, logs, screenshots, generated files, or Git.
- Reuse existing endpoints and SSE unless the audit identifies a necessary backend change; any API change needs a compatibility plan.
- Keep the web dashboard runnable in the supported Windows operator environment. If adding React/build tooling, document reproducible build output and ensure FastAPI serves the built UI without requiring a separate production web server.
- Treat operator clarity and predictable behavior as more important than visual effects.

## Success measures

- An operator can identify readiness, find a job, configure required inputs, start/stop it, and understand its outcome without reading source code.
- Existing schedule, sequence, database configuration, job execution and live logging workflows remain available.
- UI works at 1280px desktop, 768px tablet and 375px mobile widths; no critical action is hidden or clipped.
- Primary flows are keyboard accessible and provide visible focus, labels, status text and error recovery.
- No credentials or runtime configuration are added to version control.
- Startup and API compatibility are retained for the existing Windows deployment model.

## Open decisions for implementation

- Vanilla JS versus React: make the choice after mapping existing UI complexity and Windows deployment. Prefer the smallest maintainable stack that meets the interaction needs.
- Confirm which dashboard features operators use daily and which are rarely used; retain all current capabilities while prioritizing navigation.
- Establish supported browser versions and whether the dashboard is used only locally or on a shared network before changing security-sensitive behavior.
