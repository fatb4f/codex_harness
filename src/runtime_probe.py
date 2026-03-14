#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import queue
import subprocess
import sys
import threading
import time
from pathlib import Path

APP_SERVER_IO_TIMEOUT_SECS = 15.0
TURN_COMPLETION_TIMEOUT_SECS = 90.0
SHORT_DRAIN_TIMEOUT_SECS = 0.5

SOURCE_COMPONENTS = [
    {
        "name": "protocol",
        "role": "authoritative app-server request/response/event types",
        "source_path": "app-server-protocol",
        "notes": "Use this for schema and type authority; do not retype the protocol.",
    },
    {
        "name": "runtime_driver",
        "role": "reference process driver for app-server stdio sessions",
        "source_path": "app-server/tests/common/mcp_process.rs",
        "notes": "Use this as the source-lane reference; the runtime probe talks to the installed codex app-server binary directly.",
    },
    {
        "name": "scenario_library",
        "role": "existing app-server v2 scenario coverage",
        "source_path": "app-server/tests/suite/v2",
        "notes": "Reuse these scenarios as semantic references instead of inventing a new taxonomy.",
    },
    {
        "name": "persistence_layer",
        "role": "rollout and state readback validation",
        "source_path": "state",
        "notes": "Reserved for follow-up persistence packs.",
    },
]

SCENARIO_GROUPS = [
    {
        "name": "bootstrap",
        "purpose": "initialize, config read, collaboration discovery, and ephemeral thread bootstrap",
        "primary_sources": [
            "app-server/tests/suite/v2/initialize.rs",
            "app-server/tests/suite/v2/config_read.rs",
            "app-server/tests/suite/v2/collaboration_mode_list.rs",
            "app-server/tests/suite/v2/thread_start.rs",
        ],
    },
    {
        "name": "threads",
        "purpose": "thread lifecycle and persistence behavior",
        "primary_sources": [
            "app-server/tests/suite/v2/thread_start.rs",
            "app-server/tests/suite/v2/thread_resume.rs",
            "app-server/tests/suite/v2/thread_fork.rs",
            "app-server/tests/suite/v2/thread_read.rs",
        ],
    },
    {
        "name": "turns",
        "purpose": "turn lifecycle, plan items, and output shaping",
        "primary_sources": [
            "app-server/tests/suite/v2/turn_start.rs",
            "app-server/tests/suite/v2/turn_interrupt.rs",
            "app-server/tests/suite/v2/turn_steer.rs",
            "app-server/tests/suite/v2/plan_item.rs",
        ],
    },
    {
        "name": "collaboration",
        "purpose": "multi-agent lifecycle and collaboration modes",
        "primary_sources": [
            "app-server/tests/suite/v2/collaboration_mode_list.rs",
            "app-server/tests/suite/v2/turn_start.rs",
            "core/src/tools/handlers/multi_agents.rs",
        ],
    },
    {
        "name": "approvals",
        "purpose": "approval flows, permissioning, and user-input prompts",
        "primary_sources": [
            "app-server/tests/suite/v2/request_permissions.rs",
            "app-server/tests/suite/v2/request_user_input.rs",
            "app-server/tests/suite/v2/turn_start_zsh_fork.rs",
        ],
    },
    {
        "name": "persistence",
        "purpose": "rollout materialization and state readback consistency",
        "primary_sources": [
            "state",
            "app-server/tests/suite/v2/thread_read.rs",
            "app-server/tests/suite/v2/thread_metadata_update.rs",
        ],
    },
]

ARTIFACT_OUTPUTS = [
    {
        "name": "harness.run_summary.json",
        "purpose": "top-level execution result and coverage summary",
    },
    {
        "name": "harness.source_map.json",
        "purpose": "maps harness functions back to workspace crates and files",
    },
    {
        "name": "harness.scenario_results.json",
        "purpose": "per-scenario pass/fail with references",
    },
    {
        "name": "harness.event_matrix.json",
        "purpose": "request/notification coverage matrix",
    },
    {
        "name": "harness.persistence_findings.json",
        "purpose": "readback and rollout/state consistency findings",
    },
    {
        "name": "harness.review.md",
        "purpose": "human-readable final review and next steps",
    },
    {
        "name": "harness.stderr.log",
        "purpose": "captured app-server stderr diagnostics when present",
    },
]


class AppServerClient:
    def __init__(self, command: list[str]) -> None:
        self.command = command
        self.process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        if self.process.stdin is None or self.process.stdout is None or self.process.stderr is None:
            raise RuntimeError("spawned app-server target is missing stdio pipes")
        self.stdin = self.process.stdin
        self.messages: "queue.Queue[dict | Exception]" = queue.Queue()
        self._stderr_lines: list[str] = []
        self._stderr_lock = threading.Lock()
        self._thread = threading.Thread(target=self._read_stdout, daemon=True)
        self._thread.start()
        self._stderr_thread = threading.Thread(target=self._read_stderr, daemon=True)
        self._stderr_thread.start()

    def _read_stdout(self) -> None:
        assert self.process.stdout is not None
        for raw_line in self.process.stdout:
            line = raw_line.strip()
            if not line:
                continue
            try:
                self.messages.put(json.loads(line))
            except json.JSONDecodeError as exc:
                self.messages.put(RuntimeError(f"failed to parse JSON-RPC line {line!r}: {exc}"))
                break

    def _read_stderr(self) -> None:
        assert self.process.stderr is not None
        for raw_line in self.process.stderr:
            line = raw_line.rstrip("\n")
            if not line:
                continue
            with self._stderr_lock:
                self._stderr_lines.append(line)

    def send(self, payload: dict) -> None:
        self.stdin.write(json.dumps(payload))
        self.stdin.write("\n")
        self.stdin.flush()

    def read_message(self, timeout: float = APP_SERVER_IO_TIMEOUT_SECS) -> dict:
        try:
            message = self.messages.get(timeout=timeout)
        except queue.Empty as exc:
            raise RuntimeError(
                f"timed out waiting for app-server message after {timeout} seconds"
            ) from exc
        if isinstance(message, Exception):
            raise message
        return message

    def stderr_lines(self, max_lines: int = 200) -> list[str]:
        with self._stderr_lock:
            if max_lines <= 0:
                return list(self._stderr_lines)
            return list(self._stderr_lines[-max_lines:])

    def finish(self) -> None:
        try:
            self.stdin.close()
        except Exception:
            pass
        if self.process.poll() is None:
            self.process.kill()
        self.process.wait(timeout=5)


def list_sources() -> None:
    print(json.dumps(SOURCE_COMPONENTS, indent=2))


def list_scenarios() -> None:
    print(json.dumps(SCENARIO_GROUPS, indent=2))


def list_artifacts() -> None:
    print(json.dumps(ARTIFACT_OUTPUTS, indent=2))


def print_handoff() -> None:
    payload = {
        "target_surface": "codex-web / cloud-worker runtime validation",
        "workspace_root": ".",
        "runtime_probe": ".workspace/scripts/runtime_probe.sh",
        "runtime_probe_source": "src/runtime_probe.py",
        "baseline_run_command": [
            "./.workspace/scripts/runtime_probe.sh",
            "run-baseline",
            "--output-dir",
            "<output_dir>",
        ],
        "recommended_initial_scenarios": [group["name"] for group in SCENARIO_GROUPS],
        "expected_artifacts": ARTIFACT_OUTPUTS,
        "assumptions": [
            "The runtime-authoritative lane validates the installed codex app-server binary over stdio.",
            "The probe emits bounded JSON and Markdown artifacts without compiling codex-app-server from source.",
            "The workspace codex-app-server target remains a secondary comparison lane.",
        ],
    }
    print(json.dumps(payload, indent=2))


def run_baseline(output_dir: Path, scenario_groups: list[str], server_program: str) -> bool:
    allowed = {group["name"] for group in SCENARIO_GROUPS}
    unknown = [group for group in scenario_groups if group not in allowed]
    if unknown:
        raise SystemExit(f"unknown scenario groups: {', '.join(unknown)}")

    output_dir.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    command = [server_program, "app-server", "--listen", "stdio://"]
    codex_version = detect_codex_version(server_program)
    scenario_results = []
    event_observations = []
    scenario_findings: dict[str, list[str]] = {}
    scenario_runners = {
        "bootstrap": run_bootstrap,
        "threads": run_threads,
        "turns": run_turns,
        "collaboration": run_collaboration,
        "approvals": run_approvals,
        "persistence": run_persistence,
    }

    for group in scenario_groups:
        result, observation, findings = scenario_runners[group](command)
        scenario_results.append(result)
        event_observations.append(observation)
        scenario_findings[group] = findings

    completed = sum(1 for result in scenario_results if result["status"] == "passed")
    partial = sum(1 for result in scenario_results if result["status"] == "partial")
    not_executed = sum(1 for result in scenario_results if result["status"] == "not_executed")
    failed = sum(1 for result in scenario_results if result["status"] == "failed")
    has_failures = any(result["status"] == "failed" for result in scenario_results)
    stderr_log = build_stderr_log(event_observations)

    write_json(
        output_dir / "harness.run_summary.json",
        {
            "mode": "runtime_baseline",
            "server_mode": "installed",
            "server_command": command,
            "codex_version": codex_version,
            "selected_scenario_groups": scenario_groups,
            "completed_scenarios": completed,
            "partial_scenarios": partial,
            "not_executed_scenarios": not_executed,
            "failed_scenarios": failed,
            "has_failures": has_failures,
            "duration_ms": int((time.monotonic() - started) * 1000),
        },
    )
    write_json(output_dir / "harness.source_map.json", SOURCE_COMPONENTS)
    write_json(output_dir / "harness.scenario_results.json", scenario_results)
    write_json(
        output_dir / "harness.event_matrix.json",
        {
            "mode": "runtime_baseline",
            "server_mode": "installed",
            "observations": event_observations,
        },
    )
    write_json(
        output_dir / "harness.persistence_findings.json",
        build_persistence_summary(
            scenario_groups,
            scenario_results,
            scenario_findings.get("persistence", []),
        ),
    )
    (output_dir / "harness.review.md").write_text(
        build_review_markdown(command, codex_version, scenario_groups, scenario_results),
        encoding="utf-8",
    )
    if stderr_log:
        (output_dir / "harness.stderr.log").write_text(stderr_log, encoding="utf-8")
    return has_failures


def detect_codex_version(server_program: str) -> str:
    try:
        result = subprocess.run(
            [server_program, "--version"],
            check=True,
            capture_output=True,
            text=True,
        )
    except Exception as exc:
        return f"unavailable ({exc})"
    return result.stdout.strip() or result.stderr.strip() or "unknown"


def run_bootstrap(command: list[str]) -> tuple[dict, dict, list[str]]:
    started = time.monotonic()
    observation = make_observation("bootstrap")
    client: AppServerClient | None = None
    try:
        client, request_counter, initialize = start_initialized_client(command, observation)
        config_read = rpc_call(
            client, request_counter, "config/read", {"includeLayers": False}, observation
        )
        collaboration = rpc_call(
            client, request_counter, "collaborationMode/list", {}, observation
        )
        thread_start = rpc_call(
            client, request_counter, "thread/start", {"ephemeral": True}, observation
        )
        drain_messages(client, observation)

        user_agent = (
            initialize.get("result", {}).get("userAgent", "unknown")
            if isinstance(initialize, dict)
            else "unknown"
        )
        collaboration_count = len(collaboration.get("result", {}).get("data", []))
        thread_id = thread_start.get("result", {}).get("thread", {}).get("id", "unknown")
        has_config = "config" in config_read.get("result", {})
        detail = (
            "installed bootstrap passed. "
            f"userAgent={user_agent}, configRead={'yes' if has_config else 'no'}, "
            f"collaborationModes={collaboration_count}, threadId={thread_id}."
        )
        status = "passed"
    except Exception as exc:
        detail = build_failure_detail(
            command,
            f"installed-runtime bootstrap smoke failed: {exc}",
            client,
        )
        status = "failed"
    finally:
        if client is not None:
            capture_client_stderr(observation, client, "primary")
            client.finish()

    duration_ms = int((time.monotonic() - started) * 1000)
    observation["status"] = status
    return (
        {
            "group": "bootstrap",
            "status": status,
            "detail": detail,
            "duration_ms": duration_ms,
            "command": command,
        },
        observation,
        [],
    )


def wait_for_response(
    client: AppServerClient,
    request_id: int,
    observation: dict,
    method_name: str,
    timeout: float = APP_SERVER_IO_TIMEOUT_SECS,
) -> dict:
    deadline = time.monotonic() + timeout
    while True:
        message = read_before_deadline(client, deadline, method_name)
        method = message.get("method")
        if isinstance(method, str):
            if "id" in message:
                handle_server_request(client, message, observation)
                continue
            push_unique(observation["notification_methods"], method)
            continue
        if message.get("id") == request_id:
            if "error" in message:
                raise RuntimeError(
                    f"{method_name} returned JSON-RPC error: {json.dumps(message, indent=2)}"
                )
            return message


def wait_for_error_response(
    client: AppServerClient,
    request_id: int,
    observation: dict,
    method_name: str,
    timeout: float = APP_SERVER_IO_TIMEOUT_SECS,
) -> dict:
    deadline = time.monotonic() + timeout
    while True:
        message = read_before_deadline(client, deadline, method_name)
        method = message.get("method")
        if isinstance(method, str):
            if "id" in message:
                handle_server_request(client, message, observation)
                continue
            push_unique(observation["notification_methods"], method)
            continue
        if message.get("id") == request_id:
            if "error" not in message:
                raise RuntimeError(
                    f"{method_name} unexpectedly succeeded: {json.dumps(message, indent=2)}"
                )
            return message


def drain_messages(
    client: AppServerClient,
    observation: dict,
    timeout: float = SHORT_DRAIN_TIMEOUT_SECS,
) -> None:
    while True:
        try:
            message = client.read_message(timeout=timeout)
        except Exception:
            return
        method = message.get("method")
        if isinstance(method, str):
            if "id" in message:
                handle_server_request(client, message, observation)
                continue
            push_unique(observation["notification_methods"], method)


def read_before_deadline(
    client: AppServerClient, deadline: float, context: str
) -> dict:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise RuntimeError(f"timed out waiting for {context} before deadline")
    return client.read_message(timeout=remaining)


def make_observation(group: str) -> dict:
    return {
        "scenario_group": group,
        "status": "failed",
        "request_methods": [],
        "notification_methods": [],
        "server_request_methods": [],
        "notes": [],
        "stderr": [],
    }


def add_note(observation: dict, note: str) -> None:
    observation["notes"].append(note)


def build_failure_detail(command: list[str], message: str, client: AppServerClient | None) -> str:
    detail = f"{message} against '{' '.join(command)}'"
    if client is None:
        return detail
    stderr_lines = client.stderr_lines()
    if stderr_lines:
        detail += "\napp-server stderr:\n" + "\n".join(stderr_lines)
    return detail


def capture_client_stderr(observation: dict, client: AppServerClient, label: str) -> None:
    stderr_lines = client.stderr_lines()
    if not stderr_lines:
        return
    observation["stderr"].append({"label": label, "lines": stderr_lines})


def start_initialized_client(command: list[str], observation: dict) -> tuple[AppServerClient, list[int], dict]:
    client = AppServerClient(command)
    request_counter = [1]
    initialize = rpc_call(
        client,
        request_counter,
        "initialize",
        {
            "clientInfo": {
                "name": "codex_app_server_runtime_probe",
                "title": "Codex App Server Runtime Probe",
                "version": "0.1.0",
            },
            "capabilities": {
                "experimentalApi": True,
            },
        },
        observation,
    )
    client.send({"method": "initialized"})
    add_note(observation, "Sent initialized notification.")
    return client, request_counter, initialize


def rpc_call(
    client: AppServerClient,
    request_counter: list[int],
    method: str,
    params: dict,
    observation: dict,
    timeout: float = APP_SERVER_IO_TIMEOUT_SECS,
) -> dict:
    request_id = request_counter[0]
    request_counter[0] += 1
    push_unique(observation["request_methods"], method)
    client.send({"id": request_id, "method": method, "params": params})
    return wait_for_response(client, request_id, observation, method, timeout=timeout)


def rpc_call_expect_error(
    client: AppServerClient,
    request_counter: list[int],
    method: str,
    params: dict,
    observation: dict,
    timeout: float = APP_SERVER_IO_TIMEOUT_SECS,
) -> dict:
    request_id = request_counter[0]
    request_counter[0] += 1
    push_unique(observation["request_methods"], method)
    client.send({"id": request_id, "method": method, "params": params})
    return wait_for_error_response(client, request_id, observation, method, timeout=timeout)


def handle_server_request(client: AppServerClient, message: dict, observation: dict) -> None:
    method = message.get("method", "unknown")
    request_id = message.get("id")
    params = message.get("params", {})
    push_unique(observation["server_request_methods"], method)
    if method == "item/tool/requestUserInput":
        answers = {}
        for index, question in enumerate(params.get("questions", []), start=1):
            question_id = question.get("id") or f"question_{index}"
            options = question.get("options") or []
            first_label = "yes"
            if options and isinstance(options[0], dict):
                first_label = options[0].get("label") or first_label
            answers[question_id] = {"answers": [first_label]}
        client.send({"id": request_id, "result": {"answers": answers}})
        add_note(observation, "Auto-responded to item/tool/requestUserInput.")
        return
    if method == "item/permissions/requestApproval":
        client.send(
            {
                "id": request_id,
                "result": {
                    "permissions": {
                        "network": None,
                        "fileSystem": None,
                        "macos": None,
                    },
                    "scope": "turn",
                },
            }
        )
        add_note(observation, "Auto-responded to item/permissions/requestApproval with empty grant.")
        return
    if method == "item/commandExecution/requestApproval":
        client.send({"id": request_id, "result": {"decision": "decline"}})
        add_note(observation, "Auto-declined item/commandExecution/requestApproval.")
        return
    if method == "item/fileChange/requestApproval":
        client.send({"id": request_id, "result": {"decision": "decline"}})
        add_note(observation, "Auto-declined item/fileChange/requestApproval.")
        return
    client.send(
        {
            "id": request_id,
            "error": {
                "code": -32601,
                "message": f"runtime probe does not implement server request method {method}",
            },
        }
    )
    add_note(observation, f"Returned method-not-found for unexpected server request {method}.")


def wait_for_notification(
    client: AppServerClient,
    expected_method: str,
    observation: dict,
    timeout: float = APP_SERVER_IO_TIMEOUT_SECS,
) -> dict:
    deadline = time.monotonic() + timeout
    while True:
        message = read_before_deadline(client, deadline, expected_method)
        method = message.get("method")
        if isinstance(method, str):
            if "id" in message:
                handle_server_request(client, message, observation)
                continue
            push_unique(observation["notification_methods"], method)
            if method == expected_method:
                return message


def wait_for_turn_completed(client: AppServerClient, observation: dict) -> dict:
    return wait_for_notification(
        client,
        "turn/completed",
        observation,
        timeout=TURN_COMPLETION_TIMEOUT_SECS,
    )


def simple_text_input(text: str) -> list[dict]:
    return [{"type": "text", "text": text, "textElements": []}]


def read_config_model(config_read: dict) -> str | None:
    result = config_read.get("result", {})
    config = result.get("config", {})
    if isinstance(config, dict):
        model = config.get("model")
        if isinstance(model, str) and model:
            return model
    return None


def list_experimental_features(
    client: AppServerClient, request_counter: list[int], observation: dict
) -> list[dict]:
    features: list[dict] = []
    cursor = None
    while True:
        params = {"limit": 100}
        if cursor is not None:
            params["cursor"] = cursor
        response = rpc_call(
            client,
            request_counter,
            "experimentalFeature/list",
            params,
            observation,
        )
        result = response.get("result", {})
        features.extend(result.get("data", []))
        cursor = result.get("nextCursor")
        if not cursor:
            return features


def run_threads(command: list[str]) -> tuple[dict, dict, list[str]]:
    started = time.monotonic()
    observation = make_observation("threads")
    client: AppServerClient | None = None
    restarted_client: AppServerClient | None = None
    try:
        client, request_counter, _ = start_initialized_client(command, observation)
        thread_start = rpc_call(
            client, request_counter, "thread/start", {"ephemeral": False}, observation
        )
        thread_id = thread_start.get("result", {}).get("thread", {}).get("id")
        if not isinstance(thread_id, str):
            raise RuntimeError("thread/start did not return a thread id")
        drain_messages(client, observation)

        turn_start = rpc_call(
            client,
            request_counter,
            "turn/start",
            {
                "threadId": thread_id,
                "input": simple_text_input("Reply with the single word seeded."),
            },
            observation,
            timeout=TURN_COMPLETION_TIMEOUT_SECS,
        )
        wait_for_turn_completed(client, observation)
        materialized_turn_id = turn_start.get("result", {}).get("turn", {}).get("id", "unknown")
        client.finish()
        client = None

        restarted_client, request_counter, _ = start_initialized_client(command, observation)
        resume = rpc_call(
            restarted_client,
            request_counter,
            "thread/resume",
            {"threadId": thread_id},
            observation,
        )
        fork = rpc_call(
            restarted_client,
            request_counter,
            "thread/fork",
            {"threadId": thread_id},
            observation,
        )
        read = rpc_call(
            restarted_client,
            request_counter,
            "thread/read",
            {"threadId": thread_id, "includeTurns": False},
            observation,
        )
        loaded = rpc_call(
            restarted_client,
            request_counter,
            "thread/loaded/list",
            {},
            observation,
        )
        listed = rpc_call(
            restarted_client,
            request_counter,
            "thread/list",
            {"limit": 20},
            observation,
        )
        drain_messages(restarted_client, observation)

        resumed_thread_id = resume.get("result", {}).get("thread", {}).get("id")
        forked_thread_id = fork.get("result", {}).get("thread", {}).get("id")
        read_thread_id = read.get("result", {}).get("thread", {}).get("id")
        loaded_ids = loaded.get("result", {}).get("data", [])
        listed_data = listed.get("result", {}).get("data", [])
        listed_ids = [
            thread.get("id")
            for thread in listed_data
            if isinstance(thread, dict)
        ]
        if resumed_thread_id != thread_id:
            raise RuntimeError("thread/resume returned a different thread id")
        if read_thread_id != thread_id:
            raise RuntimeError("thread/read did not return the original thread id")
        if not isinstance(forked_thread_id, str) or forked_thread_id == thread_id:
            raise RuntimeError("thread/fork did not return a new thread id")
        if thread_id not in loaded_ids:
            raise RuntimeError("thread/loaded/list did not include the resumed thread id")
        if not isinstance(listed_data, list):
            raise RuntimeError("thread/list did not return a list payload")
        if thread_id not in listed_ids:
            add_note(
                observation,
                "thread/list first page did not include the materialized thread id; not treated as failure because installed runtimes may retain older ambient state.",
            )

        detail = (
            "persistent thread lifecycle passed. "
            f"threadId={thread_id}, materializedTurnId={materialized_turn_id}, "
            f"forkedThreadId={forked_thread_id}, loadedCount={len(loaded_ids)}, "
            f"listedCount={len(listed_ids)}."
        )
        status = "passed"
        findings = [
            f"Threads pack materialized thread {thread_id} with turn {materialized_turn_id}.",
            f"Threads pack resumed {thread_id} and forked {forked_thread_id}.",
        ]
    except Exception as exc:
        detail = build_failure_detail(
            command,
            f"installed-runtime threads pack failed: {exc}",
            restarted_client or client,
        )
        status = "failed"
        findings = []
    finally:
        if client is not None:
            capture_client_stderr(observation, client, "primary")
            client.finish()
        if restarted_client is not None:
            capture_client_stderr(observation, restarted_client, "restarted")
            restarted_client.finish()

    observation["status"] = status
    return (
        {
            "group": "threads",
            "status": status,
            "detail": detail,
            "duration_ms": int((time.monotonic() - started) * 1000),
            "command": command,
        },
        observation,
        findings,
    )


def run_turns(command: list[str]) -> tuple[dict, dict, list[str]]:
    started = time.monotonic()
    observation = make_observation("turns")
    client: AppServerClient | None = None
    try:
        client, request_counter, _ = start_initialized_client(command, observation)
        thread_start = rpc_call(
            client, request_counter, "thread/start", {"ephemeral": True}, observation
        )
        thread_id = thread_start.get("result", {}).get("thread", {}).get("id")
        if not isinstance(thread_id, str):
            raise RuntimeError("thread/start did not return a thread id")

        output_schema = {
            "type": "object",
            "properties": {
                "answer": {"type": "string"},
            },
            "required": ["answer"],
            "additionalProperties": False,
        }
        turn_start = rpc_call(
            client,
            request_counter,
            "turn/start",
            {
                "threadId": thread_id,
                "input": simple_text_input(
                    "Return a compact JSON object with a single answer field set to ok."
                ),
                "outputSchema": output_schema,
            },
            observation,
            timeout=TURN_COMPLETION_TIMEOUT_SECS,
        )
        completed = wait_for_turn_completed(client, observation)
        turn_id = turn_start.get("result", {}).get("turn", {}).get("id")
        if not isinstance(turn_id, str):
            raise RuntimeError("turn/start did not return a turn id")
        turn_status = (
            completed.get("params", {}).get("turn", {}).get("status", "unknown")
        )
        steer_error = rpc_call_expect_error(
            client,
            request_counter,
            "turn/steer",
            {
                "threadId": thread_id,
                "expectedTurnId": turn_id,
                "input": simple_text_input("steer"),
            },
            observation,
        )
        steer_code = steer_error.get("error", {}).get("code", "unknown")
        add_note(
            observation,
            "Runtime lane validates turn/start + outputSchema and the inactive-turn steer guard. "
            "Interrupt remains a source-lane reference because it requires a deterministic active turn.",
        )
        detail = (
            "turn lifecycle and output shaping passed. "
            f"threadId={thread_id}, turnId={turn_id}, turnStatus={turn_status}, "
            f"turnSteerErrorCode={steer_code}."
        )
        status = "passed"
    except Exception as exc:
        detail = build_failure_detail(
            command,
            f"installed-runtime turns pack failed: {exc}",
            client,
        )
        status = "failed"
    finally:
        if client is not None:
            capture_client_stderr(observation, client, "primary")
            client.finish()

    observation["status"] = status
    return (
        {
            "group": "turns",
            "status": status,
            "detail": detail,
            "duration_ms": int((time.monotonic() - started) * 1000),
            "command": command,
        },
        observation,
        [],
    )


def run_collaboration(command: list[str]) -> tuple[dict, dict, list[str]]:
    started = time.monotonic()
    observation = make_observation("collaboration")
    client: AppServerClient | None = None
    try:
        client, request_counter, _ = start_initialized_client(command, observation)
        config_read = rpc_call(
            client, request_counter, "config/read", {"includeLayers": False}, observation
        )
        collaboration = rpc_call(
            client, request_counter, "collaborationMode/list", {}, observation
        )
        features = list_experimental_features(client, request_counter, observation)

        config_model = read_config_model(config_read)
        modes = collaboration.get("result", {}).get("data", [])
        mode_names = [mode.get("name", "unknown") for mode in modes if isinstance(mode, dict)]
        feature_names = [feature.get("name", "unknown") for feature in features if isinstance(feature, dict)]
        enabled_features = [
            feature.get("name", "unknown")
            for feature in features
            if isinstance(feature, dict) and feature.get("enabled") is True
        ]
        plan_mask = next(
            (
                mode
                for mode in modes
                if isinstance(mode, dict) and mode.get("mode") == "plan"
            ),
            None,
        )
        plan_turn_id = None
        if config_model and isinstance(plan_mask, dict):
            thread_start = rpc_call(
                client,
                request_counter,
                "thread/start",
                {"ephemeral": True},
                observation,
            )
            thread_id = thread_start.get("result", {}).get("thread", {}).get("id")
            collaboration_mode = {
                "mode": "plan",
                "settings": {
                    "model": plan_mask.get("model") or config_model,
                    "reasoning_effort": plan_mask.get("reasoning_effort"),
                    "developer_instructions": None,
                },
            }
            turn_start = rpc_call(
                client,
                request_counter,
                "turn/start",
                {
                    "threadId": thread_id,
                    "input": simple_text_input("Reply with the single word plan."),
                    "collaborationMode": collaboration_mode,
                },
                observation,
                timeout=TURN_COMPLETION_TIMEOUT_SECS,
            )
            wait_for_turn_completed(client, observation)
            plan_turn_id = turn_start.get("result", {}).get("turn", {}).get("id")
        else:
            add_note(
                observation,
                "Skipped plan-mode turn because config/read did not expose a usable model or collaboration mode list lacked a plan entry.",
            )

        detail = (
            "collaboration discovery passed. "
            f"modes={mode_names}, enabledFeatures={enabled_features}, "
            f"planTurnId={plan_turn_id or 'not-run'}."
        )
        status = "passed"
    except Exception as exc:
        detail = build_failure_detail(
            command,
            f"installed-runtime collaboration pack failed: {exc}",
            client,
        )
        status = "failed"
    finally:
        if client is not None:
            capture_client_stderr(observation, client, "primary")
            client.finish()

    observation["status"] = status
    return (
        {
            "group": "collaboration",
            "status": status,
            "detail": detail,
            "duration_ms": int((time.monotonic() - started) * 1000),
            "command": command,
        },
        observation,
        [],
    )


def run_approvals(command: list[str]) -> tuple[dict, dict, list[str]]:
    started = time.monotonic()
    observation = make_observation("approvals")
    client: AppServerClient | None = None
    try:
        client, request_counter, _ = start_initialized_client(command, observation)
        config_read = rpc_call(
            client, request_counter, "config/read", {"includeLayers": True}, observation
        )
        features = list_experimental_features(client, request_counter, observation)
        thread_start = rpc_call(
            client, request_counter, "thread/start", {"ephemeral": True}, observation
        )
        thread_id = thread_start.get("result", {}).get("thread", {}).get("id")
        if not isinstance(thread_id, str):
            raise RuntimeError("thread/start did not return a thread id")
        turn_start = rpc_call(
            client,
            request_counter,
            "turn/start",
            {
                "threadId": thread_id,
                "input": simple_text_input(
                    "Use the request_user_input tool to ask exactly one yes/no question, "
                    "then after you receive an answer respond with the single word acknowledged."
                ),
            },
            observation,
            timeout=TURN_COMPLETION_TIMEOUT_SECS,
        )
        wait_for_turn_completed(client, observation)

        enabled_features = [
            feature.get("name", "unknown")
            for feature in features
            if isinstance(feature, dict) and feature.get("enabled") is True
        ]
        config_layers = config_read.get("result", {}).get("layers")
        tool_user_input_seen = "item/tool/requestUserInput" in observation["server_request_methods"]
        permissions_seen = "item/permissions/requestApproval" in observation["server_request_methods"]
        resolved_seen = "serverRequest/resolved" in observation["notification_methods"]
        turn_id = turn_start.get("result", {}).get("turn", {}).get("id", "unknown")
        saw_server_roundtrip = (tool_user_input_seen or permissions_seen) and resolved_seen
        saw_server_request_only = (tool_user_input_seen or permissions_seen) and not resolved_seen
        if saw_server_roundtrip:
            add_note(
                observation,
                "Observed a server-request approval or user-input roundtrip in the installed runtime.",
            )
            status = "passed"
            detail_prefix = "approval and user-input roundtrip validation passed"
        elif saw_server_request_only:
            add_note(
                observation,
                "Observed a server request, but no serverRequest/resolved notification was seen; treating this as partial coverage.",
            )
            status = "partial"
            detail_prefix = "approval and user-input surface validation was partial"
        else:
            add_note(
                observation,
                "No approval or request_user_input server request was emitted for the runtime prompt; "
                "treating this as partial surface discovery instead of a full approval validation pass.",
            )
            status = "partial"
            detail_prefix = "approval and user-input surface discovery was partial"

        detail = (
            f"{detail_prefix}. "
            f"threadId={thread_id}, turnId={turn_id}, enabledFeatures={enabled_features}, "
            f"serverRequests={observation['server_request_methods']}, "
            f"serverRequestResolved={'yes' if resolved_seen else 'no'}, "
            f"configLayers={'yes' if isinstance(config_layers, list) else 'no'}."
        )
    except Exception as exc:
        detail = build_failure_detail(
            command,
            f"installed-runtime approvals pack failed: {exc}",
            client,
        )
        status = "failed"
    finally:
        if client is not None:
            capture_client_stderr(observation, client, "primary")
            client.finish()

    observation["status"] = status
    return (
        {
            "group": "approvals",
            "status": status,
            "detail": detail,
            "duration_ms": int((time.monotonic() - started) * 1000),
            "command": command,
        },
        observation,
        [],
    )


def run_persistence(command: list[str]) -> tuple[dict, dict, list[str]]:
    started = time.monotonic()
    observation = make_observation("persistence")
    client: AppServerClient | None = None
    try:
        client, request_counter, _ = start_initialized_client(command, observation)
        thread_start = rpc_call(
            client, request_counter, "thread/start", {"ephemeral": False}, observation
        )
        thread_id = thread_start.get("result", {}).get("thread", {}).get("id")
        if not isinstance(thread_id, str):
            raise RuntimeError("thread/start did not return a thread id")
        metadata_branch = "runtime-probe/persistence"
        update = rpc_call(
            client,
            request_counter,
            "thread/metadata/update",
            {
                "threadId": thread_id,
                "gitInfo": {
                    "branch": metadata_branch,
                },
            },
            observation,
        )
        read_back = rpc_call(
            client,
            request_counter,
            "thread/read",
            {"threadId": thread_id, "includeTurns": False},
            observation,
        )
        drain_messages(client, observation)

        updated_branch = (
            update.get("result", {})
            .get("thread", {})
            .get("gitInfo", {})
            .get("branch")
        )
        read_branch = (
            read_back.get("result", {})
            .get("thread", {})
            .get("gitInfo", {})
            .get("branch")
        )
        if updated_branch != metadata_branch or read_branch != metadata_branch:
            raise RuntimeError(
                "thread metadata branch did not roundtrip through thread/metadata/update + thread/read"
            )

        detail = (
            "thread metadata persistence passed. "
            f"threadId={thread_id}, branch={metadata_branch}."
        )
        status = "passed"
        findings = [
            f"Persistence pack updated thread {thread_id} gitInfo.branch to {metadata_branch}.",
            f"Persistence pack read back thread {thread_id} with the same branch value.",
        ]
    except Exception as exc:
        detail = build_failure_detail(
            command,
            f"installed-runtime persistence pack failed: {exc}",
            client,
        )
        status = "failed"
        findings = []
    finally:
        if client is not None:
            capture_client_stderr(observation, client, "primary")
            client.finish()

    observation["status"] = status
    return (
        {
            "group": "persistence",
            "status": status,
            "detail": detail,
            "duration_ms": int((time.monotonic() - started) * 1000),
            "command": command,
        },
        observation,
        findings,
    )


def push_unique(items: list[str], value: str) -> None:
    if value not in items:
        items.append(value)


def build_review_markdown(
    command: list[str], codex_version: str, scenario_groups: list[str], scenario_results: list[dict]
) -> str:
    lines = [
        "# App Server Runtime Baseline Review",
        "",
        "## Runtime target",
        f"- command: `{' '.join(command)}`",
        f"- version: `{codex_version}`",
        "",
        "## Selected scenario groups",
    ]
    lines.extend(f"- `{group}`" for group in scenario_groups)
    lines.extend(["", "## Execution results"])
    lines.extend(
        f"- `{result['group']}`: **{result['status']}** ({result['duration_ms']} ms) — {result['detail']}"
        for result in scenario_results
    )
    lines.extend(
        [
            "",
            "## Notes",
            "- This runtime baseline validates the installed `codex app-server` surface over stdio.",
            "- Each pack uses the smallest installed-runtime path that is practical without compiling the workspace server from source.",
            "- Approval and user-input coverage is only marked `passed` when a real server-initiated request/response roundtrip is observed.",
            "- Partial results mean the runtime surface was discovered, but the deeper bidirectional flow was not fully exercised in the live run.",
        ]
    )
    return "\n".join(lines) + "\n"


def build_persistence_summary(
    scenario_groups: list[str], scenario_results: list[dict], persistence_findings: list[str]
) -> dict:
    persistence_result = next(
        (result for result in scenario_results if result["group"] == "persistence"),
        None,
    )
    if "persistence" not in scenario_groups:
        return {
            "mode": "runtime_baseline",
            "status": "not_selected",
            "findings": ["Persistence scenario group was not selected for this run."],
        }
    if persistence_result is None:
        return {
            "mode": "runtime_baseline",
            "status": "not_executed",
            "findings": ["Persistence scenario group was selected but did not execute."],
        }
    status = persistence_result["status"]
    if persistence_findings:
        findings = persistence_findings
    elif status == "passed":
        findings = ["Persistence scenario executed successfully but did not emit extra findings."]
    elif status == "partial":
        findings = ["Persistence scenario executed partially; inspect scenario results for details."]
    elif status == "not_executed":
        findings = ["Persistence scenario was selected but not executed."]
    else:
        findings = ["Persistence scenario needs review; inspect scenario results for failure details."]
    return {
        "mode": "runtime_baseline",
        "status": status if status in {"passed", "partial", "not_executed"} else "needs_review",
        "findings": findings,
    }


def build_stderr_log(event_observations: list[dict]) -> str:
    sections: list[str] = []
    for observation in event_observations:
        stderr_entries = observation.get("stderr") or []
        if not stderr_entries:
            continue
        sections.append(f"[{observation['scenario_group']}]")
        for entry in stderr_entries:
            label = entry.get("label", "unknown")
            sections.append(f"## {label}")
            sections.extend(entry.get("lines", []))
            sections.append("")
    return "\n".join(sections).strip() + ("\n" if sections else "")


def write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Minimal App Server runtime validation probe."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("list-sources")
    subparsers.add_parser("list-scenarios")
    subparsers.add_parser("list-artifacts")
    subparsers.add_parser("print-handoff")

    run_baseline_parser = subparsers.add_parser("run-baseline")
    run_baseline_parser.add_argument("--output-dir", required=True, type=Path)
    run_baseline_parser.add_argument(
        "--scenario-groups",
        nargs="+",
        default=[group["name"] for group in SCENARIO_GROUPS],
    )
    run_baseline_parser.add_argument("--server-program", default="codex")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "list-sources":
        list_sources()
        return 0
    if args.command == "list-scenarios":
        list_scenarios()
        return 0
    if args.command == "list-artifacts":
        list_artifacts()
        return 0
    if args.command == "print-handoff":
        print_handoff()
        return 0
    if args.command == "run-baseline":
        has_failures = run_baseline(args.output_dir, args.scenario_groups, args.server_program)
        return 1 if has_failures else 0
    parser.error(f"unknown command {args.command}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
