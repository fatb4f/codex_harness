# AGENTS

This file is scaffolded from [.project.manifest.json](./.project.manifest.json) by [build_overrides.sh](./.workspace/scripts/build_overrides.sh).

Read [.project.manifest.json](./.project.manifest.json) first before doing review, runtime, schema, or planning work in this repo.

Use [review_workspace_instructions.md](./.workspace/docs/review_workspace_instructions.md) for the full review workflow and output contract.

Regenerate scaffolded files with [build_overrides.sh](./.workspace/scripts/build_overrides.sh).

## Required behavior

- treat this repo as harness-only; rollout and tier planning live outside this repo
- read .workspace/docs/review_workspace_instructions.md for the full review workflow and output contract
- regenerate scaffolded files with .workspace/scripts/build_overrides.sh after scaffold or manifest changes
- use the project review contract under .workspace/templates/reviews

## Review contract

Use these files:

- [.project.manifest.json](./.project.manifest.json)
- [artifact_review.schema.json](./.workspace/templates/reviews/artifact_review.schema.json)
- [codex_harness.review.schema.json](./.workspace/templates/reviews/codex_harness.review.schema.json)
- [review.schema.json](./.workspace/templates/reviews/review.schema.json)
- [review.json.template](./.workspace/templates/reviews/review.json.template)

Template root: `.workspace/templates/reviews`
Project id: `codex_harness`

If there is any conflict between ad hoc assumptions and the manifest, follow the manifest.
