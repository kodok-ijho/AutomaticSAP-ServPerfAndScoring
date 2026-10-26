# Web Sequence Builder Plan

**Status:** Ready for implementation  
**Scope:** Custom sequence/workflow authoring in the FastAPI web dashboard

## Goal

Let an operator create, inspect, edit, order, and save a multi-step job sequence in the web dashboard. The saved JSON must remain compatible with `custom_sequence_runner.py` and the existing `/api/sequences` endpoints.

## Current findings

- The web UI already has a sequence page, editor modal, step controls, list API, detail API, save API, and sequence JSON format.
- The “Buat Template Sequence Baru” button has no working listener; the empty-state button calls an app method that is not exported.
- The card “Edit” action only displays a toast. The editor's add-step and save handlers are referenced but are not implemented/exported.
- The Tkinter dashboard has a separate functioning sequence builder. Its core behavior can inform the web workflow, but do not modify Tkinter.
- This repository also contains pre-existing uncommitted web dashboard changes. Preserve them; inspect and integrate with the current worktree instead of resetting/replacing it.

## Operator experience

Use an explicit sequence editor with two modes: create new and edit existing. Provide name, filename, description, and an ordered step list. Steps can be SAP jobs (selected from backend job registry with editable parameters) or timed waits. Each step can be removed and moved up/down; drag-and-drop may be added only if keyboard-accessible reordering is also provided. Show an at-a-glance summary and validation errors before save.

## Phases

1. Audit the current dirty worktree, current sequence UI and API contracts; identify implementation conflicts and avoid reverting unrelated work.
2. Connect navigation/list/create/edit actions to the sequence editor and load saved templates via the detail endpoint.
3. Implement a data-driven step editor using job metadata from the backend. Support job parameters including dynamic tokens already accepted by `custom_sequence_runner.py`; preserve them as literal strings.
4. Implement wait-step editing, deletion, keyboard-friendly ordering, validation and unsaved-change handling.
5. Save through the existing API and JSON shape, refresh the list, and provide clear errors/success feedback.
6. Verify create/edit round trips with non-production fixture data and ensure no SAP/SQL execution is triggered by authoring.

## Boundaries

- Do not run a saved sequence or any SAP job while verifying the editor.
- Do not change job execution, SAP scripting, ETL/SQL, scheduler semantics, Tkinter, dynamic-token semantics, or sequence runner behavior.
- Do not replace backend contracts without documenting compatibility and preserving existing templates.
- Never expose or commit credentials, `.env`, `job_config.json`, logs, exports, or real user data.
