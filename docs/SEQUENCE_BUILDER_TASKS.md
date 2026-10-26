# Web Sequence Builder Tasks for Agy

## S0 — Inspect and preserve current work

- [ ] S0.1 Read the sequence plan, requirements and specification.
- [ ] S0.2 Inspect `git status` and the existing uncommitted redesign diff. Preserve and build on it; do not reset, checkout, clean, or overwrite unrelated edits.
- [ ] S0.3 Trace sequence endpoints, current JSON templates, `job_definitions.SCRIPTS`, `custom_sequence_runner.py`, and the Tkinter builder for compatibility references.
- [ ] S0.4 Record any API/security gaps (especially filename collision/traversal) and propose the narrowest safe fix.

## S1 — Connect editor entry points

- [ ] S1.1 Wire the main create button and empty-state action to create mode.
- [ ] S1.2 Wire each card Edit action to load mode using `GET /api/sequences/{filename}`.
- [ ] S1.3 Add explicit editor state and preserve current sequence identity while editing.
- [ ] S1.4 Implement dirty-form detection and discard confirmation.

## S2 — Metadata and job steps

- [ ] S2.1 Implement create/edit metadata form and safe filename generation/validation.
- [ ] S2.2 Add job selection populated from existing backend job data.
- [ ] S2.3 Render editable parameters from selected job metadata, preserving defaults, current values, help and dynamic tokens.
- [ ] S2.4 Preserve unknown legacy parameter keys/fields on round trip where possible.

## S3 — Wait and ordered workflow management

- [ ] S3.1 Implement wait step add/edit with positive integer seconds and optional description.
- [ ] S3.2 Render concise numbered cards for both job and wait steps.
- [ ] S3.3 Add edit/remove/move-up/move-down controls with keyboard-accessible names and predictable focus.
- [ ] S3.4 Update count, order and accessible live announcement after changes.

## S4 — Validation and save

- [ ] S4.1 Validate required metadata, filename, at least one step, job existence, parameter values and wait duration.
- [ ] S4.2 Submit the existing save payload; check HTTP status and preserve entered state on error.
- [ ] S4.3 Prevent accidental overwrite on filename collision; add a narrow backend safeguard if necessary without changing the payload contract.
- [ ] S4.4 After successful save, refresh the sequence list and present accurate success feedback.

## S5 — Safe verification and documentation

- [ ] S5.1 Verify create-save-reopen-edit-save using a temporary fixture in a safe local test setup.
- [ ] S5.2 Verify a representative existing template round trip, including dynamic tokens and wait steps.
- [ ] S5.3 Verify invalid inputs, API failures, filename safety/collision, unsaved close and accessibility basics.
- [ ] S5.4 Check layouts at 375px, 768px and 1280px.
- [ ] S5.5 Do not execute sequences, SAP jobs, SAP login, or production SQL while verifying authoring.
- [ ] S5.6 Update task status and report exact commands/results, modified files and remaining risks. Do not commit/push unless the user separately asks.

## Definition of done

An operator can create and edit a sequence from the web UI, manage ordered job/wait steps, save runner-compatible JSON, and reopen it without data loss. Existing templates and execution contracts remain compatible, and authoring has no execution side effects.
