# App Server Validation Harness

Standalone local repo for the installed-runtime App Server validation harness.

This repo owns:
- `src/runtime_probe.py`
- `.workspace/scripts/runtime_probe.sh`
- manifest-backed agent instructions
- dedicated review workspace instructions
- schema-backed review templates
- handoff and cloud-worker prompts under `src/prompts`
- checked-in baseline validation samples
- harness docs for the runtime-authoritative lane

It validates the installed `codex app-server` surface over stdio and treats the
upstream `codex-rs` tree as an external source/reference surface, not as the
home of the harness itself.

Rollout tiers, rollout DAGs, and rollout/harness overlay planning are kept in a
separate rollout repo on purpose. This repo stays focused on executable harness
artifacts and their review contract.

## Primary Commands

- `./.workspace/scripts/build_overrides.sh`
- `./.workspace/scripts/runtime_probe.sh list-sources`
- `./.workspace/scripts/runtime_probe.sh list-scenarios`
- `./.workspace/scripts/runtime_probe.sh list-artifacts`
- `./.workspace/scripts/runtime_probe.sh print-handoff`
- `./.workspace/scripts/runtime_probe.sh run-baseline --output-dir src/validation_samples/baseline`

Run `./.workspace/scripts/build_overrides.sh` after manifest changes to regenerate the scaffolded
agent instructions and project-specific review contract files.

Use `./.workspace/scripts/runtime_probe.sh` instead of calling Python directly
when you want `codex_harness` bytecode cache to stay outside the git worktree.

Use [.workspace/docs/review_workspace_instructions.md](./.workspace/docs/review_workspace_instructions.md)
for the full review workflow. `AGENTS.md` is intentionally only the repo
entrypoint.

## Scope

This repo is for:
- runtime discovery
- runtime validation
- artifact emission
- handoff packaging
- review templates and manifest-backed instructions

This repo is not the upstream product source tree.
