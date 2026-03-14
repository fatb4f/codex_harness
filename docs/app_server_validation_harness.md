# App Server Validation Harness

## Purpose

This harness exists to validate and map the Codex App Server surfaces in a way
that can be executed reproducibly by a cloud worker.

It is not a greenfield test system. It is a thin harness layer assembled from
existing workspace components.

The default validation lane is runtime-authoritative:

- run the Python runtime probe in this repo
- drive the installed `codex app-server` binary
- emit artifacts against the runtime users actually run

The upstream `codex-rs` tree remains a secondary source-authoritative lane for
branch or regression comparison. This repo owns the runtime probe and handoff
surface, not the product source tree.

This repo also intentionally excludes rollout tiers, rollout DAGs, and
cross-surface rollout planning. Those planning artifacts belong in a separate
rollout repo so the harness archive stays focused on executable validation
inputs, outputs, and review contracts.

## Design Rule

Reuse the repo's native components wherever possible:

- protocol from `app-server-protocol`
- process/runtime driver from `app-server/tests/common`
- scenario coverage from `app-server/tests/suite/v2`
- fixture and mock support from `core/tests/common`
- persistence validation from `state`
- hook/event validation from `hooks`
- telemetry and trace correlation from `otel`
- approval policy permutations from `utils/approval-presets`
- cloud-lane extensions from `cloud-tasks-client` and `cloud-requirements`

Do not rebuild those pieces inside this harness repo. Reuse them as external
reference surfaces from a checked out `codex-rs` tree when needed.

## Core Components

### 1. Protocol layer

Authoritative source:

- `app-server-protocol`

Purpose:

- request/response/event typing
- JSON Schema and TypeScript schema generation
- experimental surface gating

### 2. Runtime/process driver

Authoritative source:

- `app-server/tests/common/mcp_process.rs`
- `src/runtime_probe.py`

Purpose:

- spawn and drive `app-server` targets
- initialize the connection
- send typed requests
- capture notifications
- drive protocol-level scenarios

In the harness implementation, the Python probe is the runtime-authoritative
entrypoint. `mcp_process.rs` remains the source reference for how the workspace
drives App Server over stdio.

### 3. Scenario library

Authoritative source:

- `app-server/tests/suite/v2`

Purpose:

- define real scenario groups already validated by the workspace
- keep the harness aligned with upstream behavior

### 4. Fixture and mock layer

Authoritative source:

- `core/tests/common`
- `app-server/tests/common/mock_model_server.rs`
- `app-server/tests/common/responses.rs`

Purpose:

- deterministic SSE fixtures
- mock backend behavior
- repeatable protocol exercises

### 5. Persistence and readback layer

Authoritative source:

- `state`

Purpose:

- rollout metadata extraction
- thread metadata mirroring
- local SQLite-backed persistence checks
- readback consistency validation

### 6. Event and hook layer

Authoritative source:

- `hooks`

Purpose:

- inspect hook event types
- validate control-plane interception points
- compare hook semantics against external policy/hook designs

### 7. Trace and metrics layer

Authoritative source:

- `otel`

Purpose:

- capture W3C trace context
- produce trace-linked validation artifacts
- correlate runtime and protocol observations

### 8. Approval matrix layer

Authoritative source:

- `utils/approval-presets`

Purpose:

- run the same scenarios under multiple approval/sandbox policies
- avoid hard-coding policy permutations in the harness

### 9. Cloud-lane extension

Authoritative source:

- `cloud-tasks-client`
- `cloud-requirements`

Purpose:

- validate cloud task submission/retrieval semantics
- validate cloud-managed config requirement effects

This is a secondary lane, not the primary App Server harness base.

## Scenario Groups

The first baseline runner focuses on these initial packs:

1. `bootstrap`
   - initialize
   - initialized
   - config read
   - collaboration mode list
   - ephemeral thread start

2. `threads`
   - thread start
   - thread resume
   - thread fork
   - thread read

3. `turns`
   - turn start
   - turn interrupt
   - turn steer
   - plan item
   - output schema

4. `collaboration`
   - feature flag enablement
   - collaboration mode list
   - multi-agent lifecycle primitives

5. `approvals`
   - request permissions
   - request user input
   - zsh fork subcommand approvals

6. `persistence`
   - rollout materialization
   - state readback
   - thread metadata update consistency

The runtime baseline now executes a real installed-runtime path for every pack.
The `threads`, `turns`, and `persistence` packs perform live protocol flows
against the installed `codex app-server`, while `collaboration` and
`approvals` stay runtime-safe and discovery-oriented unless the installed model
actually emits deeper server-request behavior.

The default server target is:

- runtime probe: `python3 src/runtime_probe.py`
- command: `codex app-server --listen stdio://`

The optional comparison target is:

- external `codex-rs` checkout plus workspace `codex-app-server`
- command: `cargo run -q -p codex-app-server -- --listen stdio://` from that checkout

## Output Artifacts

Baseline runs emit this bounded artifact family:

- `harness.run_summary.json`
- `harness.source_map.json`
- `harness.scenario_results.json`
- `harness.event_matrix.json`
- `harness.persistence_findings.json`
- `harness.review.md`
- `harness.stderr.log` when the runtime emits stderr diagnostics

Future extensions can add trace and cloud-lane artifacts, but they are
intentionally out of scope for the first baseline runner.

Status reporting is execution-derived:

- `passed` = the scenario flow was exercised successfully
- `partial` = the runtime surface was discovered, but a deeper bidirectional path was not observed
- `failed` = the scenario flow failed
- `not_executed` = selected but not actually run
- `not_selected` = outside the current run scope

## Cloud Worker Entrypoint

The cloud worker should not invent its own discovery path.

It should:

1. run the Python runtime probe
2. use the installed `codex app-server` runtime by default
3. run one or more scenario groups
4. emit the artifact set
5. return those artifacts as the review payload

## CLI Surface

The runtime probe now supports:

- `python3 src/runtime_probe.py list-sources`
- `python3 src/runtime_probe.py list-scenarios`
- `python3 src/runtime_probe.py list-artifacts`
- `python3 src/runtime_probe.py print-handoff`
- `python3 src/runtime_probe.py run-baseline --output-dir <dir> [--scenario-groups bootstrap threads] [--server-program /path/to/codex]`

`run-baseline` writes review-grade JSON and Markdown artifacts into the
caller-provided output directory with no Rust build step.

## Codex Web Handoff Readiness

The harness should also be consumable as a Codex Web handoff package.

That means:

- no reliance on ad hoc local shell history
- no implicit workspace discovery
- explicit build and run commands
- explicit scenario selection
- explicit artifact paths and names
- bounded JSON and Markdown outputs suitable for remote review

The Codex Web handoff contract should include:

- workspace root
- runtime probe path
- run command
- scenario listing command
- artifact contract
- initial scenario packs
- constraints and assumptions

The runtime probe exposes this through `print-handoff` so a cloud worker or
Codex Web task can consume one stable handoff object instead of reverse-
engineering the repo layout.

## Initial Scope

The first usable version should implement:

- `bootstrap`
- `threads`
- `turns`
- `collaboration`
- `approvals`
- `persistence`

It should validate the installed runtime first. Only after that lane is stable
should the harness be expanded to compare against the workspace
`codex-app-server` target.

Leave `realtime`, `plugins`, and `cloud-lane` as expansion packs.

## Workspace Scaffold

The runtime-authoritative entrypoint for this harness is:

- `src/runtime_probe.py`

Discovery and validation should stay on the Python probe until there is a clear
need to compare against an external `codex-rs` checkout's `codex-app-server`
target.
