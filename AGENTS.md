# AGENTS

This repo uses [project.manifest.json](./project.manifest.json) as its local instruction authority.

Read that file first before doing review, runtime, schema, or planning work in this repo.

## Required behavior

- treat this repo as harness-only; rollout and tier planning live outside this repo
- treat the extracted archive/workspace as the default review surface
- do not assume an installed `codex` runtime exists
- use the review contract under [.templates/reviews](./.templates/reviews)
- prefer machine-readable outputs first
- do not emit full review artifacts into chat UI
- write review artifacts to the internal `/mnt` workspace, archive them there, and return only the link plus a minimal status note in chat

## Review contract

Use these files:

- [project.manifest.json](./project.manifest.json)
- [artifact_review.schema.json](./.templates/reviews/artifact_review.schema.json)
- [codex_harness.review.schema.json](./.templates/reviews/codex_harness.review.schema.json)
- [review.schema.json](./.templates/reviews/review.schema.json)
- [review.json.template](./.templates/reviews/review.json.template)

If there is any conflict between ad hoc assumptions and the manifest, follow the manifest.
