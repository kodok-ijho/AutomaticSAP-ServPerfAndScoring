# Web Dashboard Redesign Tasks

Use these as implementation issues or a staged work queue. Complete in order unless discovery shows a dependency should change.

## Epic 0 — Audit and baseline

- [ ] **T0.1 Inventory the current UI.** Map each view, modal, action, API endpoint, SSE event and backend handler. Record which actions mutate state and whether stop/reconnect is supported.
- [ ] **T0.2 Record baseline and constraints.** Capture current desktop/mobile screenshots; verify startup command, supported browser assumptions, static serving path and deployment packaging.
- [ ] **T0.3 Recommend frontend approach.** Compare vanilla JS and React for current UI complexity, deployment, maintainability and build requirements. Document decision before adding dependencies.

## Epic 1 — Product design foundation

- [ ] **T1.1 Define information architecture.** Map all existing capabilities to Overview, Jobs, Activity, Sequences, Schedules and Settings, adjusting names to fit operator language.
- [ ] **T1.2 Define responsive design system.** Specify tokens for color, type, spacing, borders, focus and status; implement shared navigation, buttons, fields, badges, cards, tables, toasts and dialogs.
- [ ] **T1.3 Define interaction/state designs.** Cover empty/loading/offline/error/validation/success states, narrow navigation, keyboard behavior and reduced motion.

## Epic 2 — Overview and job discovery

- [ ] **T2.1 Build the overview.** Show trustworthy SAP/application/database state and running/recent activity from existing APIs.
- [ ] **T2.2 Build the job catalog.** Use backend registry data, search/filter, descriptions and status; ensure all jobs remain discoverable.
- [ ] **T2.3 Build job parameter details.** Render fields from backend metadata, validate inputs, show defaults and preserve existing CLI argument construction.
- [ ] **T2.4 Add daily pipeline entry point.** Expose the existing daily sequence clearly without changing its stages or behavior.

## Epic 3 — Execution and observability

- [ ] **T3.1 Build active/recent execution views.** Present status, timestamps, selected job and actionable state.
- [ ] **T3.2 Improve streaming log viewer.** Preserve SSE contract; add severity styling, pause/resume, autoscroll control, readable wrapping and disconnect/reconnect state.
- [ ] **T3.3 Improve completion and recovery.** Provide success/failure summary and clear next steps while preserving detailed logs.
- [ ] **T3.4 Implement stop interaction.** Only if current backend supports it; provide pending/result state and prevent misleading controls.

## Epic 4 — Existing operator tools

- [ ] **T4.1 Redesign sequences.** Preserve builder and runner features, payload shape and sequence semantics.
- [ ] **T4.2 Redesign schedules.** Preserve existing scheduler integration and recurrence semantics; clarify save, run and removal outcomes.
- [ ] **T4.3 Redesign settings.** Preserve settings API, mask secrets and provide explicit save/error state.

## Epic 5 — Verification and rollout

- [ ] **T5.1 Check responsive layouts.** Verify primary flows at 375px, 768px and 1280px.
- [ ] **T5.2 Check accessibility.** Keyboard traverse primary flows; verify focus, semantics, labels, contrast cues, dialogs and reduced motion.
- [ ] **T5.3 Check backend compatibility.** Compare every frontend request/event to the existing contracts and test the read/run/log/stop/configuration paths in an appropriate safe environment.
- [ ] **T5.4 Check deployment.** Confirm Windows startup, FastAPI asset serving, dependency/build instructions and clean checkout behavior.
- [ ] **T5.5 Document release and rollback.** Summarize changed files, commands/outcomes, known gaps and rollback steps.

## Completion rule

Do not mark a task done based only on visual implementation. Include evidence from inspection or a safe functional walkthrough. Never execute SAP jobs or write to production SQL as part of UI verification without an explicitly approved test environment.
