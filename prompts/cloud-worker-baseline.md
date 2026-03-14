# Cloud Worker Runtime Baseline Prompt

Use the runtime probe already present in this workspace as the authoritative
entrypoint:

- `runtime_probe.py`

## Goal

Validate the installed `codex app-server` runtime first, using the harness that
already lives in this repo. Do not switch back to building `codex-app-server`
from source for the default lane.

## Scope

Stay within:

- `.`
- `docs/app_server_validation_harness.md`

You may read and reuse these existing workspace surfaces:

- `codex-rs/app-server-protocol`
- `codex-rs/app-server/tests/common`
- `codex-rs/app-server/tests/suite/v2`
- `codex-rs/core/tests/common`
- `codex-rs/state`
- `codex-rs/hooks`
- `codex-rs/otel`
- `codex-rs/utils/approval-presets`

## Requirements

1. Keep the harness native to the workspace.
2. Use the installed `codex app-server` runtime by default.
3. Keep the workspace `codex-app-server` target as a secondary comparison lane,
   not the default baseline lane.
4. Focus only on the initial scenario packs:
   - `bootstrap`
   - `threads`
   - `turns`
   - `collaboration`
   - `approvals`
   - `persistence`
5. If full scenario execution is too large for one pass, keep the minimal
   runner skeleton and at least one real executed scenario path against the
   installed runtime.

## Expected outputs

Make the repo changes needed so the harness can:

- list sources
- list scenarios
- list artifacts
- print the handoff contract
- execute a baseline run command
- write review-grade artifacts to disk

The baseline run should emit as many of these as are supported by the first
implementation:

- `harness.run_summary.json`
- `harness.source_map.json`
- `harness.scenario_results.json`
- `harness.event_matrix.json`
- `harness.persistence_findings.json`
- `harness.review.md`

## Validation

Run the narrowest useful checks for changed crates and include what you ran in
your final summary.

The default runtime check should look like:

- `python3 runtime_probe.py list-scenarios`
- `python3 runtime_probe.py run-baseline --output-dir <dir>`

If you changed the repo while doing this work:

- run `git status`
- commit the changes
- push the branch
- report the branch name and commit SHA in your final summary

## Constraints

- Prefer small, reviewable changes.
- Reuse existing workspace protocol and scenario references.
- Do not expand into plugins, realtime, or cloud-lane execution unless needed.
- Do not make the default baseline depend on compiling `codex-app-server`.
