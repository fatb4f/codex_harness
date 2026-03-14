# AGENTS

This repo uses [project.manifest.json](/home/_404/src/codex_harness/project.manifest.json) as its local instruction authority.

Read that file first before doing review, runtime, schema, or planning work in this repo.

## Required behavior

- treat the extracted archive/workspace as the default review surface
- do not assume an installed `codex` runtime exists
- use the review contract under [.templates/reviews](/home/_404/src/codex_harness/.templates/reviews)
- prefer machine-readable outputs first
- do not emit full review artifacts into chat UI
- write review artifacts to the internal `/mnt` workspace, archive them there, and return only the link plus a minimal status note in chat

## Review contract

Use these files:

- [project.manifest.json](/home/_404/src/codex_harness/project.manifest.json)
- [artifact_review.schema.json](/home/_404/src/codex_harness/.templates/reviews/artifact_review.schema.json)
- [codex_harness.review.schema.json](/home/_404/src/codex_harness/.templates/reviews/codex_harness.review.schema.json)
- [review.schema.json](/home/_404/src/codex_harness/.templates/reviews/review.schema.json)
- [review.json.template](/home/_404/src/codex_harness/.templates/reviews/review.json.template)

If there is any conflict between ad hoc assumptions and the manifest, follow the manifest.
