# App Server Validation Harness Prompts

This directory is the canonical home for prompts used to hand off or drive the
runtime probe in this repo.

Use it for:

- Codex Web handoff prompts
- cloud-worker execution prompts
- scenario-specific validation prompts
- regression-check prompts for a narrowed scenario pack

Do not scatter harness prompts across random docs or issue comments.

Recommended prompt files:

- `codex-web-handoff.md`
- `cloud-worker-baseline.md`
- `cloud-worker-baseline-validation.md`
- `scenario-collaboration.md`
- `scenario-approvals.md`
- `scenario-persistence.md`

The machine-readable handoff contract is produced by:

```bash
python3 src/runtime_probe.py print-handoff
```

That command gives the structured execution contract. The prompt files in this
directory provide the human task framing layered on top of it.

Current default flow:

- run `python3 src/runtime_probe.py run-baseline`
- validate the installed `codex app-server` runtime first

Use the workspace `codex-app-server` target only for explicit source-lane
comparison work.
