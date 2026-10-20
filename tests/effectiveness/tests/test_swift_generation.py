import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from tests.effectiveness import swift_generation
from tests.effectiveness.swift_generation import (
    codex_args,
    plan,
    run_session,
    source_hash,
)
from tests.effectiveness.swift_generation_fixture import (
    PROMPTS,
    behavior_source,
    create_fixture,
    git,
)
from tests.effectiveness.swift_generation_report import patch, publish, verify_patch_coverage


def test_schedule_has_five_pairs_and_alternates_order():
    cells = plan()
    assert len(cells) == 20
    assert len({cell["label"] for cell in cells}) == 20
    for task_index, task in enumerate(PROMPTS):
        selected = [cell for cell in cells if cell["task"] == task]
        for repeat in range(1, 6):
            pair = [cell["arm"] for cell in selected if cell["repeat"] == repeat]
            assert pair == (["A", "B"] if (repeat - 1 + task_index) % 2 == 0 else ["B", "A"])


def test_identical_fixture_bytes_and_history(tmp_path):
    first = tmp_path / "cedar-one" / "CedarStore"
    second = tmp_path / "cedar-two" / "CedarStore"
    assert create_fixture(first) == create_fixture(second)
    assert source_hash(first) == source_hash(second)
    assert len(git(first, "log", "--format=%H").splitlines()) == 3
    assert not (first / ".chameleon").exists()
    assert not (first / ".claude").exists()


def test_organic_prompts_hold_back_method_and_grading():
    forbidden = (
        "eval",
        "test",
        "judge",
        "experiment",
        "rubric",
        "score",
        "compare",
        "benchmark",
        "candidate",
        "arena",
    )
    for prompt in PROMPTS.values():
        assert not any(word in prompt.lower() for word in forbidden)


def test_hidden_entry_points_match_requested_entry_points():
    assert "graph.quoteShipping.execute(orderID:" in behavior_source("shipping")
    assert "StoreGraph.quoteShipping.execute(orderID:)" in PROMPTS["shipping"]
    assert "graph.loadPickupLocations.execute(postcode:" in behavior_source("pickup")
    assert "StoreGraph.loadPickupLocations.execute(postcode:)" in PROMPTS["pickup"]


def test_both_arms_share_model_and_prompt_with_only_hook_difference():
    python = Path("/opt/cedar/python")
    root = Path("/tmp/cedar/CedarStore")
    off = codex_args(root, PROMPTS["shipping"], None, python)
    on = codex_args(root, PROMPTS["shipping"], Path("/tmp/cedar/state/delivery.jsonl"), python)
    assert off[-1] == on[-1]
    assert off[off.index("-m") + 1] == on[on.index("-m") + 1] == "gpt-6-astra"
    assert 'model_reasoning_effort="medium"' in off
    assert 'model_reasoning_effort="medium"' in on
    assert "hooks.SessionStart=" not in " ".join(off)
    assert "hooks.SessionStart=" in " ".join(on)
    assert "--ignore-user-config" in off and "--ignore-user-config" in on


def test_missing_completion_and_failed_turn_are_failures(tmp_path):
    script = "import json; print(json.dumps({'type':'turn.failed','error':{'message':'connection lost'}}))"
    session = run_session([sys.executable, "-c", script], tmp_path, os.environ.copy(), tmp_path, 10)
    assert session["terminal_reason"] == "failed"
    assert session["usage"] is None


def test_normal_turn_retains_usage_without_treating_hook_warning_as_failure(tmp_path):
    events = [
        {
            "type": "item.completed",
            "item": {
                "type": "error",
                "message": "`--dangerously-bypass-hook-trust` is enabled.",
            },
        },
        {"type": "turn.completed", "usage": {"input_tokens": 3, "output_tokens": 2}},
    ]
    script = "print(" + repr("\n".join(json.dumps(event) for event in events)) + ")"
    session = run_session([sys.executable, "-c", script], tmp_path, os.environ.copy(), tmp_path, 10)
    assert session["terminal_reason"] == "completed"
    assert session["usage"]["input_tokens"] == 3


def test_empty_stream_is_not_a_completed_turn(tmp_path):
    session = run_session([sys.executable, "-c", "pass"], tmp_path, os.environ.copy(), tmp_path, 10)
    assert session["terminal_reason"] == "missing_completion"


def test_full_patch_includes_package_and_new_model_written_tests(tmp_path):
    root = tmp_path / "CedarStore"
    create_fixture(root)
    target = root / "Tests/CedarStoreTests/ShippingQuoteTests.swift"
    target.parent.mkdir(parents=True)
    target.write_text("import Testing\n")
    manifest = root / "Package.swift"
    manifest.write_text(manifest.read_text() + "\n")
    covered = verify_patch_coverage(root, patch(root))
    assert "Package.swift" in covered
    assert "Tests/CedarStoreTests/ShippingQuoteTests.swift" in covered


def test_publication_refuses_a_patch_that_omits_generated_swift(tmp_path):
    root = tmp_path / "CedarStore"
    create_fixture(root)
    target = root / "Sources/CedarStore/Extra.swift"
    target.write_text("struct Extra {}\n")
    with pytest.raises(ValueError, match="Extra.swift"):
        verify_patch_coverage(root, "")


def test_profile_failure_is_a_recorded_cell_error(tmp_path, monkeypatch):
    monkeypatch.setattr(swift_generation, "cell_environment", lambda _state: {})

    def fail(*_args):
        raise RuntimeError("profile unavailable")

    monkeypatch.setattr(swift_generation, "derive", fail)
    cell = {"task": "shipping", "arm": "B", "repeat": 1, "label": "sample-01"}
    result = swift_generation.run_cell(
        cell,
        tmp_path / "CedarStore",
        tmp_path / "state",
        Path(sys.executable),
        "run",
        30,
    )
    assert result["status"] == "error"
    assert result["error"]["phase"] == "profile"
    assert result["session"]["terminal_reason"] == "not_started"
    assert result["success"] is False


def test_assessment_timeout_preserves_the_session_and_errors_the_cell(tmp_path, monkeypatch):
    monkeypatch.setattr(swift_generation, "cell_environment", lambda _state: {})
    session = {
        "terminal_reason": "completed",
        "duration_seconds": 1,
        "usage": {"input_tokens": 3},
        "errors": [],
        "tools": [],
    }
    monkeypatch.setattr(swift_generation, "run_session", lambda *_args: session)

    def timeout(*_args):
        raise subprocess.TimeoutExpired("swiftc", 120)

    monkeypatch.setattr(swift_generation, "assess", timeout)
    cell = {"task": "shipping", "arm": "A", "repeat": 1, "label": "sample-01"}
    result = swift_generation.run_cell(
        cell,
        tmp_path / "CedarStore",
        tmp_path / "state",
        Path(sys.executable),
        "run",
        30,
    )
    assert result["status"] == "error"
    assert result["error"]["phase"] == "assessment"
    assert result["error"]["type"] == "TimeoutExpired"
    assert result["session"]["usage"]["input_tokens"] == 3
    assert result["success"] is False


def test_authentication_stop_keeps_all_twenty_planned_cells(tmp_path, monkeypatch):
    def failed_cell(cell, root, *_args):
        return dict(
            cell,
            workspace=str(root),
            status="failed",
            success=False,
            delivered_context=False,
            session={"terminal_reason": "failed", "usage": None},
        )

    monkeypatch.setattr(swift_generation, "run_cell", failed_cell)
    monkeypatch.setattr(swift_generation, "authentication_failed", lambda *_args: True)
    monkeypatch.setattr(
        swift_generation,
        "command",
        lambda *_args: subprocess.CompletedProcess([], 0, stdout="local version"),
    )
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setattr(
        sys, "argv", ["cedar", "--mode", "run", "--run-dir", str(tmp_path / "record")]
    )
    assert swift_generation.main() == 1
    recorded = json.loads((tmp_path / "record/run.json").read_text())
    assert recorded["status"] == "authentication_blocked"
    assert recorded["planned_cells"] == 20
    assert len(recorded["cells"]) == 1
    assert sum(cell["status"] == "not_run" for cell in recorded["schedule"]) == 19


def test_publication_keeps_setup_errors_missing_workspaces_and_timeout_causes(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(swift_generation, "cell_environment", lambda _state: {})

    def fail(_root):
        raise OSError("fixture unavailable at " + str(Path.home()))

    monkeypatch.setattr(swift_generation, "create_fixture", fail)
    record = tmp_path / "record"
    record.mkdir()
    cells = [
        swift_generation.run_cell(
            cell,
            tmp_path / cell["label"] / "CedarStore",
            record / cell["label"],
            Path(sys.executable),
            "run",
            30,
        )
        for cell in plan()
    ]
    valid = tmp_path / "CedarStore"
    commit = create_fixture(valid)
    cells[1].update(
        workspace=str(valid),
        source_hash=source_hash(valid),
        fixture_commit=commit,
        error={"phase": "assessment", "type": "TimeoutExpired", "message": "swiftc timed out"},
    )
    cells[1]["session"]["terminal_reason"] = "completed"
    (record / "run.json").write_text(
        json.dumps(
            {
                "status": "completed",
                "cells": cells,
                "method": "native hooks",
                "model": "gpt-6-astra",
                "reasoning": "medium",
                "codex_version": "local",
                "swift_version": "6.4",
            }
        )
    )
    destination = tmp_path / "published"
    assert publish(record, destination)["cells"] == 20
    metrics = json.loads((destination / "metrics.json").read_text())
    assert metrics["planned_cells"] == 20
    assert metrics["prepared_cells"] == 1
    assert metrics["status_counts"] == {"error": 20}
    assert metrics["cells"][0]["error"]["phase"] == "setup"
    assert metrics["cells"][0]["workspace_available"] is False
    assert metrics["cells"][1]["error"]["type"] == "TimeoutExpired"
    assert metrics["cells"][1]["terminal_reason"] == "completed"
    assert str(Path.home()) not in (destination / "metrics.json").read_text()
    assert (destination / "blind" / cells[0]["label"] / "unavailable.txt").is_file()
