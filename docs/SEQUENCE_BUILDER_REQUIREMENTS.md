# Web Sequence Builder Requirements

## Purpose

Allow operators to author and maintain custom SAP job workflows through the web UI without hand-editing JSON. The editor only configures a sequence; it must never execute jobs as a side effect of creating or saving.

## Functional requirements

### REQ-1 Entry points

- The main “Buat Template Sequence Baru” action opens a clean editor.
- The empty-state create action opens the same editor.
- Every sequence card’s Edit action opens that file's data in the editor.
- Closing the editor returns to the list and does not silently save.

### REQ-2 Sequence metadata

- Edit sequence name, description and `.json` filename.
- New filenames are sanitized to a basename within `custom_sequences/`, end in `.json`, and cannot traverse directories.
- Editing preserves the original file identity unless the operator intentionally changes the filename; a rename must not silently overwrite another sequence.

### REQ-3 Job steps

- Add a job step selected from backend-provided job definitions; do not hardcode a second job registry in JavaScript.
- Configure the selected job's supported parameters with labels/help/defaults and suitable controls where metadata permits.
- Preserve dynamic token strings such as `dynamic-today-ymd` and `dynamic-now-plus-1m` as literal JSON values for runtime resolution.
- Persist job steps as `{ "type": "job", "name": "<backend job name>", "params": { ... } }`.

### REQ-4 Wait steps

- Add a timed wait step with duration in seconds and optional description.
- Validate duration as a positive integer within a practical, documented maximum.
- Persist using the runner-compatible wait shape: `{ "type": "wait", "name": "...", "seconds": <integer>, "desc": "..." }`.

### REQ-5 Ordered step management

- Display an ordered numbered step list.
- Allow adding, editing, removing, and moving steps earlier/later.
- Reordering and removal must be usable by keyboard and have accessible labels.
- Update step numbers and count immediately after each change.

### REQ-6 Validation and persistence

- Require a non-empty name, valid filename, and at least one valid step.
- Validate selected job existence and parameter types/required values using backend metadata as far as available.
- Keep invalid content in the editor and show field/step-specific messages.
- Save through existing `POST /api/sequences/save` request contract `{ filename, content }` and retain current JSON schema.
- Surface HTTP errors; show success only after a successful response; refresh list and preserve edit context appropriately.
- Detect unsaved changes before close or switching sequences.

## Non-functional requirements

- Accessible labels, focus states, status feedback, dialog focus behavior and keyboard-only operation.
- Responsive at 375px, 768px and 1280px.
- No accidental job execution, SAP login, SQL write or schedule creation from editor actions.
- Do not display or store credentials in the editor.
- Preserve existing templates and support old wait aliases (`wait`, `delay`, `sleep`) on load where compatible.
- Work with current Windows/FastAPI deployment and existing static-serving arrangement.

## Acceptance criteria

1. Create, save, reopen, edit and save a new fixture sequence successfully.
2. Load an existing template, preserve its metadata, step order, job parameters, dynamic tokens and waits through a save round trip.
3. Add/edit/remove/reorder job and wait steps; errors are clear and accessible.
4. Invalid or empty sequences cannot be saved; no success toast appears on failure.
5. Filename input cannot escape `custom_sequences/`; collisions are explained and do not silently overwrite another file.
6. None of these flows execute SAP jobs or issue SQL operations.
7. Every current template remains listable and runnable through the existing runner unchanged.
