# Cloud Worker Baseline Validation Prompt

Use the committed runtime probe already present in this workspace as the
authoritative baseline:

- `runtime_probe.py`

## Goal

Validate the runtime-authoritative `run-baseline` flow in a proper cloud
environment, capture the emitted artifact set, and return the result through a
repo diff rather than UI-only task output.

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

## Required workflow

1. Execute the current runtime probe.
2. Persist a reviewable sample of the emitted artifacts back into the repo.
3. Write a concise validation report into the repo.
4. If you changed the repo, `git status`, commit the changes, and push the branch before finishing.

## Required commands

Run the narrowest useful checks first:

- `python3 runtime_probe.py list-scenarios`
- `python3 runtime_probe.py print-handoff`
- `command -v codex`

Then execute:

- `python3 runtime_probe.py run-baseline --output-dir <repo-local-output-dir> --server-program "$(command -v codex)"`

Use a repo-local output directory so the results can return as a diff. Put the
sample under:

- `validation_samples/baseline/`

## Expected outputs

The repo diff should include:

1. The emitted artifact sample under:
   - `validation_samples/baseline/`
2. A short validation note at:
   - `validation_samples/baseline/validation_report.md`

The report must state:

- whether `run-baseline` completed successfully
- which artifacts were emitted
- whether the bootstrap smoke path completed cleanly
- whether the runtime cost is acceptable or still too heavy
- the resolved `codex` binary path used for the run
- exactly what commands were run
- whether a git commit was created and pushed

## If the baseline runner fails or is too heavy

If the committed baseline mode does not complete cleanly, you may make one
minimal follow-up improvement, but only if it is clearly justified by the run.

Allowed fixes:

- reduce bootstrap validation cost
- make artifact emission more observable/reviewable
- tighten the baseline report output

Do not broaden the harness beyond baseline validation in this pass.

## Constraints

- Keep changes small and reviewable.
- Do not redesign the harness.
- Do not expand into plugins, realtime, or cloud-lane execution.
- Prefer validating the current baseline over adding new scenario packs.
- Do not switch the default runtime lane back to compiling `codex-app-server`.
- If `command -v codex` is empty, stop and report the missing runtime instead of committing invalid baseline sample artifacts.
- If the repo changed, do not stop at a local commit: push the branch and report the branch name and commit SHA.
