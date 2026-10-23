# Antigravity / Agy CLI Headless Prompt

Paste this into the Antigravity task/session. Run Agy in headless mode from the repository root and point it at this prompt file. Check the installed CLI's `agy --help` for the exact unattended flag syntax; do not guess flags or switch to an interactive GUI.

```text
You are implementing the SAP RPA web dashboard redesign in this repository.

Read these documents first:
- docs/WEB_DASHBOARD_REDESIGN_PLAN.md
- docs/WEB_DASHBOARD_REDESIGN_SPEC.md
- docs/WEB_DASHBOARD_REDESIGN_TASKS.md

Repository facts:
- This is a Python SAP GUI RPA application. The web server is FastAPI in web_dashboard.py.
- The existing web UI is static/index.html, static/style.css, static/app.js.
- A desktop Tkinter UI and SAP/ETL/scheduler code also exist and are out of scope.
- There is no declared React frontend toolchain today.

Execution instructions:
1. Work only in this repository and current branch. Inspect git status before editing; preserve any user changes.
2. First complete T0.1–T0.3: inspect API routes, SSE, all existing UI actions, deployment assumptions and frontend complexity. Write a concise audit/approach note to docs/WEB_DASHBOARD_REDESIGN_AUDIT.md.
3. Recommend vanilla JS or React based on evidence. Do not add React, dependencies, or a build pipeline until the audit justifies it. If React is justified, ensure FastAPI serves production build assets and document Windows build/start steps.
4. Implement the specification in small phases, keeping all current dashboard actions and backend request/response/SSE contracts intact. Do not change SAP automation, SQL/ETL logic, scheduler semantics, CLI arguments, or Tkinter.
5. Do not run SAP jobs, access production SAP/SQL, or expose credentials. Never read/print `.env` contents. Never commit `.env`, job_config.json, logs, exports, or secrets.
6. Keep design responsive at 375px, 768px, 1280px, accessible by keyboard, clear in all loading/offline/error states, and restrained in animation.
7. Follow repository instructions such as AGENTS.md if present. Do not commit or push unless separately instructed by the user.
8. Verification is authorized for this task: run relevant non-production checks, inspect responsive layouts and verify API compatibility. Avoid tests that trigger live SAP or production SQL. Report any verification that could not safely run.
9. Update docs/WEB_DASHBOARD_REDESIGN_TASKS.md as work is completed. End with a concise summary of decisions, files changed, verification commands/results and remaining issues.

Start with the audit; continue through implementation without waiting for clarification unless a concrete blocker prevents safe progress.
```

## Launch guidance

From the repository root, use the installed CLI's documented headless mode and pass this file as the task input. First inspect `agy --help` so the command matches the installed version. Keep execution on a reviewable branch and inspect the resulting diff before merging.
