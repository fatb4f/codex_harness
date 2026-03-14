# Review Workspace Instructions

Use this file for the full review workflow. `AGENTS.md` and `project.manifest.json`
are entrypoint and contract surfaces, not the full operator instructions.

## Scaffolding Structure

- `project.manifest.json`
  Canonical project definitions, scaffold paths, and the project review contract.
- `build_overrides.sh`
  Idempotent scaffold generator for `AGENTS.md` and the project-specific review
  schema/template files.
- `AGENTS.md`
  Thin repo entrypoint that points to the manifest, this instructions file, and
  the scaffold generator.
- `.templates/reviews/*`
  Scaffolded review schema/template outputs for this project.

## Review Surface

Treat the uploaded archive and its extracted workspace as the primary review
surface.

Do not assume an installed `codex` runtime exists, and do not default to
runtime execution unless the required runtime is explicitly present and the task
asks for it.

Work in the same workspace where the archive is extracted.

## Priority Files

- `project.manifest.json`
- `build_overrides.sh`
- `docs/review_workspace_instructions.md`
- `runtime_probe.py`
- `README.md`
- `docs/app_server_validation_harness.md`
- `validation_samples/baseline/*`
- `.templates/reviews/*`

`planning/*.json` no longer belongs to this repo. Rollout planning lives in the
separate `codex_rollout` repo.

## Output Rules

- do not generate full review artifacts in chat UI
- write review outputs directly to file in the internal `/mnt` workspace
- archive the generated review artifacts there
- in chat, return only the download link or file link plus a minimal status note
- prefer machine-readable output first, prose second
- use the review template and validate against the review schema before finalizing

## Review Rules

- keep findings severity-ordered
- separate verified execution from static review and recommendation
- do not overclaim coverage
- if something was not executed, say so explicitly
- if the runtime is unavailable, state that as an execution boundary, not as a failure

## Execution States

- `passed`
- `partial`
- `failed`
- `not_executed`
- `not_selected`

For approvals and collaboration:

- `partial` is correct when the surface is discovered but the deeper bidirectional path was not observed

## Default Review Posture

- bugs
- brittle assumptions
- documentary overclaim
- missing evidence
- schema or contract drift

Findings first. Summary second.

## Schema and Template Changes

- keep the generic base schema reusable
- keep the `codex_harness` profile project-specific
- preserve compatibility when practical
- after scaffold changes, rerun `./build_overrides.sh`

Be concise and exact.
