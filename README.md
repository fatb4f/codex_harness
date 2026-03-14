# App Server Validation Harness

Standalone local repo for the installed-runtime App Server validation harness.

This repo owns:
- `runtime_probe.py`
- handoff and cloud-worker prompts
- checked-in baseline validation samples
- harness docs for the runtime-authoritative lane

It validates the installed `codex app-server` surface over stdio and treats the
upstream `codex-rs` tree as an external source/reference surface, not as the
home of the harness itself.

## Primary Commands

- `python3 runtime_probe.py list-sources`
- `python3 runtime_probe.py list-scenarios`
- `python3 runtime_probe.py list-artifacts`
- `python3 runtime_probe.py print-handoff`
- `python3 runtime_probe.py run-baseline --output-dir validation_samples/baseline`

## Scope

This repo is for:
- runtime discovery
- runtime validation
- artifact emission
- handoff packaging

This repo is not the upstream product source tree.
