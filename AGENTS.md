# AGENTS

This file is scaffolded from [project.manifest.json](./project.manifest.json) by [build_overrides.sh](./build_overrides.sh).

Read [project.manifest.json](./project.manifest.json) first before doing review, runtime, schema, or planning work in this repo.

Use [review_workspace_instructions.md](./docs/review_workspace_instructions.md) for the full review workflow and output contract.

Regenerate scaffolded files with [build_overrides.sh](./build_overrides.sh).

## Required behavior

- treat this repo as harness-only; rollout and tier planning live outside this repo
- read docs/review_workspace_instructions.md for the full review workflow and output contract
- regenerate scaffolded files with build_overrides.sh after scaffold or manifest changes
- use the project review contract under .templates/reviews

## Review contract

Use these files:

- [project.manifest.json](./project.manifest.json)
- [artifact_review.schema.json](./.templates/reviews/artifact_review.schema.json)
- [codex_harness.review.schema.json](./.templates/reviews/codex_harness.review.schema.json)
- [review.schema.json](./.templates/reviews/review.schema.json)
- [review.json.template](./.templates/reviews/review.json.template)

Template root: `.templates/reviews`
Project id: `codex_harness`

If there is any conflict between ad hoc assumptions and the manifest, follow the manifest.
