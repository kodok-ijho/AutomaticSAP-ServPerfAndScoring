# Web Sequence Builder Specification

## 1. Data contract

Sequence document:

```json
{
  "name": "Daily example",
  "description": "Optional operator-facing explanation",
  "items": [
    {
      "type": "job",
      "name": "<exact key from job_definitions.SCRIPTS>",
      "params": { "periode": "dynamic-today-ymd" }
    },
    {
      "type": "wait",
      "name": "Wait",
      "seconds": 60,
      "desc": "Wait for the SAP background job"
    }
  ]
}
```

The schema above is illustrative. Inspect actual templates and runner behavior before implementing. Existing values must round-trip without loss. Unknown legacy fields should be retained where practical instead of silently discarded.

## 2. Editor states

- **Closed:** sequence list is visible.
- **Create:** blank metadata and steps; suggested `.json` filename may derive from entered name.
- **Loading:** edit template fetched from `GET /api/sequences/{filename}`; controls disabled with clear loading state.
- **Editing:** metadata and ordered steps editable.
- **Dirty:** changes made since last successful load/save; close or switch asks whether to discard.
- **Saving:** prevent duplicate submissions and show progress.
- **Saved:** show confirmation, refresh list, close or remain editing with saved state.
- **Load/save error:** retain user-entered values and present actionable feedback.

## 3. Layout

1. Dialog/page title states “Create sequence” or “Edit sequence”.
2. Metadata group: sequence name, safe filename, description.
3. Ordered workflow timeline/list. Each step shows type, selected job or wait summary, essential parameter summary, and controls for edit, move, and remove.
4. Add controls: “Add job” and “Add wait”.
5. Footer: cancel/close and primary save action. Save disabled only while invalid/saving; validation explains why.

For narrow widths, stack metadata fields and step actions. Avoid requiring horizontal scrolling.

## 4. Job step editor

- Job selection uses exact names supplied by existing `/api/jobs` data.
- Once selected, render that job's parameter metadata (argument key, label, type, default, help) rather than a static list.
- Preserve current values when editing a step. Handle unknown legacy params visibly and preserve them if the user does not change them.
- Provide an option to enter supported dynamic tokens as literal values; do not resolve dates/times in the browser.
- Serialize only runner-compatible job-step structure and values.

## 5. Wait step editor

- Duration input is integer seconds; description is optional.
- Display duration in human-readable form in the step summary while preserving integer seconds in JSON.
- Preserve legacy aliases when loading if needed; newly created waits use `type: "wait"`.

## 6. Actions and API use

- List: existing `GET /api/sequences`.
- Read: existing `GET /api/sequences/{filename}`.
- Save: existing `POST /api/sequences/save` with `{ "filename": string, "content": object }`.
- Refresh list after successful save. Check `response.ok` before reporting success.
- Do not call `/api/sequences/execute` from the editor.
- Inspect path handling and filename collision behavior. If backend safeguards are needed, add narrow validation and preserve payload compatibility; explicitly call out any security-relevant backend change in implementation notes.

## 7. Accessibility and interaction

- Use semantic dialog or page structure, a visible title, associated labels, and focus placed inside the editor on open.
- Escape/close behavior must honor unsaved-change confirmation.
- Add, remove, move and edit controls have explicit accessible names; do not rely on icons alone.
- After add/remove/reorder, announce step-list changes through a polite live region and keep focus predictable.
- Validation errors connect to relevant inputs and are conveyed in text, not color alone.

## 8. Verification scenarios

- Create a fixture with one job and one wait, save, reopen and compare serialized structure.
- Edit an existing fixture with dynamic parameter tokens and verify no token/value/order loss.
- Exercise invalid filename, duplicate filename, missing name, no steps, missing job, malformed wait duration, API error and unsaved close.
- Verify at 375px, 768px and 1280px and with keyboard-only navigation.
- Use mocked/local fixture data. Do not execute workflows or connect to production SAP/SQL during verification.
