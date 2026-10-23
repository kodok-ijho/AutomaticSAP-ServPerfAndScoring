# Web Dashboard Redesign Specification

## 1. Purpose and scope

Define behavior and experience requirements for a more useful, interactive browser dashboard for the SAP RPA. Scope is the web client served by `web_dashboard.py` and its integration with the current backend. This document does not authorize changes to SAP automation or data processing behavior.

## 2. Users and core journeys

Primary user: an operations staff member who runs scheduled or ad hoc SAP reporting jobs and needs to see progress and diagnose failures. Secondary user: a maintainer configuring jobs, sequences, schedules and database connectivity.

Core journeys:

1. Open dashboard, understand SAP/application readiness, see running/recent jobs and choose the next action.
2. Find a job or daily pipeline, inspect its description and required parameters, validate inputs, run it and monitor streamed logs.
3. Stop a running job when supported, inspect its terminal state and retry after correcting the cause.
4. Review/create/edit sequences and schedules using existing behavior.
5. Update database connection settings using existing behavior, with secrets masked and explicit feedback.

## 3. Information architecture

- **Overview:** system status, running jobs, recent activity, prominent daily pipeline and shortcuts.
- **Jobs:** searchable/filterable catalog, job details and parameters, run action, output/expectations.
- **Activity:** active and recent executions; detail panel with live logs, timestamps, status and stop action where supported.
- **Sequences:** existing custom sequence builder/runner.
- **Schedules:** existing task scheduler manager and schedule state.
- **Settings:** database configuration and other existing dashboard preferences.

Navigation must show current location. On narrow screens it may collapse into an accessible menu. Keep help/status information discoverable.

## 4. Functional requirements

### FR-1 System status

Show application, SAP connection and database status only when supported by existing backend checks. Distinguish loading, connected/ready, unavailable, and unknown. Show last checked time when available. Never imply a successful SAP or database check from a missing response.

### FR-2 Job catalog and parameters

Render jobs from the existing job registry/API data; do not duplicate job definitions in frontend constants. Include search, useful categories, clear descriptions, required/optional parameter labels, defaults, validation messages, and run state. Disable or guard duplicate starts consistently with current backend behavior.

### FR-3 Run and monitor

Starting a job gives immediate feedback and creates a visible execution entry. Display status, start/end time when known, and logs streamed using the current SSE behavior. Log stream supports readable severity, autoscroll, pause/resume, and clear visual distinction between historical and new lines. On disconnect, indicate that live updates stopped and recover/reconnect using supported APIs. Stop action appears only where backend supports it and reports the result.

### FR-4 Outcome and errors

Show a concise success/failure/cancelled outcome with useful remediation derived from backend output. Preserve detailed logs. Errors must not silently disappear or show raw stack traces as the only explanation.

### FR-5 Sequences and schedules

Preserve current sequence and scheduling capabilities and payload contracts. Provide clear validation, unsaved-change indication, confirmation before destructive removal, and feedback after save/run. Do not change recurrence semantics.

### FR-6 Settings

Preserve current settings capability and backend contract. Mask password fields, avoid logging secrets, label required fields, indicate saving/saved/failed states, and do not persist credentials client-side beyond existing behavior.

### FR-7 Responsive and accessible interaction

Support keyboard navigation, visible focus, semantic headings/landmarks, form labels, dialog focus handling, non-color status cues, sufficient contrast, and reduced-motion preference. No critical task may require hover. Provide empty, loading, offline, validation, and failure states.

## 5. Visual and interaction requirements

- Modern operations-console aesthetic with strong hierarchy and restrained SAP-blue accent.
- Use consistent spacing, typography, borders, elevation and semantic status colors.
- Favor legible tables/cards and concise summaries over oversized hero sections or decorative data visualization.
- Provide interactive affordances for navigation, search/filter, execution, log inspection, sequence/schedule editing and settings.
- Animations must be brief, purposeful and respect `prefers-reduced-motion`.
- Responsive targets: 375px, 768px and 1280px viewport widths.

## 6. Technical constraints

- Backend remains Python/FastAPI; current routes, request/response shapes, SSE event behavior, and job semantics are compatibility constraints.
- Inspect `web_dashboard.py`, `static/`, and related job/scheduler modules before editing. Build a route/action inventory and map every current UI action to its redesigned home.
- No production frontend stack is currently declared. Do not add React or dependencies by assumption. If selected, justify the choice, pin dependencies, add build instructions, serve generated assets through current FastAPI deployment, and keep the built output reproducible.
- Do not introduce an external API, cloud dependency, telemetry, or CDN requirement for core operation.
- Do not commit `.env`, `job_config.json`, logs, SAP exports, or credentials.
- Preserve desktop Tkinter behavior and all RPA/ETL modules.

## 7. Acceptance criteria

1. Every existing web-dashboard action has a documented location and remains functional.
2. Job definitions, statuses and parameters shown in UI match the backend registry rather than drifting duplicated values.
3. Operator can run a job, observe streamed output, identify terminal state and see clear errors without refreshing the page.
4. Existing sequences, schedules and settings can be operated with their current backend contracts.
5. No sensitive configuration is exposed in browser storage, logs, or tracked artifacts.
6. At 375/768/1280px, content remains readable and controls remain reachable with no horizontal page overflow for primary flows.
7. Keyboard-only navigation and focus are usable across primary flows; forms and dialogs are labeled and status is conveyed in text.
8. FastAPI serves the UI using documented startup steps in the existing Windows environment.
9. Build/verification notes include actual commands and outcomes; any unsupported or blocked verification is stated explicitly.

## 8. Out of scope

Changing SAP transaction automation, report definitions, data transformations, SQL schema, scheduler recurrence behavior, adding user accounts/roles, remote multi-tenant access, or redesigning the Tkinter desktop app.
