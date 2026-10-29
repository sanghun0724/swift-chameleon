from __future__ import annotations

import io
import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from tests.unit.test_swift_journey import swift_repo as swift_repo

from chameleon_mcp import codex_hooks as hooks


def _patch(*lines):
    return "\n".join(["*** Begin Patch", *lines, "*** End Patch"])


@pytest.mark.parametrize("raw", ["", "null", "[]", "garbage", "{}", '{"cwd":null}'])
def test_bad_payload_returns_no_request(raw):
    assert hooks.read_request(io.StringIO(raw)) is None


def test_large_payload_is_rejected():
    assert hooks.read_request(io.StringIO(" " * (hooks.MAX_INPUT_BYTES + 1))) is None


def test_native_patch_paths_preserve_moves_and_ignore_added_text():
    patch = _patch(
        "*** Add File: Sources/New.swift",
        "+*** Add File: fake.swift",
        "*** Update File: Sources/Old.swift",
        "*** Move to: Sources/Moved.swift",
        "@@",
        "-old",
        "+new",
        "*** End of File",
        "*** Delete File: Sources/Gone.swift",
    )
    assert [(p.operation, p.path) for p in hooks.parse_patch_paths(patch)] == [
        ("Add File", "Sources/New.swift"),
        ("Update File", "Sources/Old.swift"),
        ("Move to", "Sources/Moved.swift"),
        ("Delete File", "Sources/Gone.swift"),
    ]


@pytest.mark.parametrize(
    "patch",
    [
        "*** Begin Patch\n*** Add File: a.swift",
        _patch("*** Move to: a.swift"),
        _patch("*** Add File: "),
        _patch("*** Add File: a\x00.swift"),
        _patch("*** Unknown File: a.swift"),
    ],
)
def test_incomplete_or_invalid_patch_has_no_targets(patch):
    assert hooks.parse_patch_paths(patch) == ()


def test_patch_path_count_is_bounded():
    assert (
        hooks.parse_patch_paths(
            _patch(*[f"*** Add File: {i}.swift" for i in range(hooks.MAX_PATCH_PATHS + 1)])
        )
        == ()
    )


def test_targets_resolve_from_subdirectory_without_escape(tmp_path):
    root = tmp_path / "repo"
    cwd = root / "Sources"
    cwd.mkdir(parents=True)
    assert hooks.resolve_target(root, cwd, "New.swift") == cwd / "New.swift"
    assert hooks.resolve_target(root, cwd, "../../outside.swift") is None
    assert hooks.resolve_target(root, cwd, str(tmp_path / "outside.swift")) is None
    assert hooks.resolve_target(root, cwd, "../.env/config.swift") is None


def test_targets_refuse_symlinks_for_existing_and_new_files(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "Secret.swift").write_text("struct Secret {}")
    link = root / "link"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("Symlinks unavailable")
    assert hooks.resolve_target(root, root, "link/Secret.swift") is None
    assert hooks.resolve_target(root, root, "link/New.swift") is None


def _trust(repo):
    from chameleon_mcp import tools

    assert tools.trust_profile(str(repo), repo.name)["data"]["status"] in {"trusted", "success"}


def test_native_startup_requires_trust_and_supplies_real_canonicals(swift_repo):
    repo, recent = swift_repo
    request = hooks.HookRequest("SessionStart", repo)
    assert hooks.context_response(request) == {}
    _trust(repo)
    response = hooks.context_response(request)
    context = response["hookSpecificOutput"]["additionalContext"]
    assert "recent implementation" in context
    assert recent.name in context
    assert response["hookSpecificOutput"]["hookEventName"] == "SessionStart"
    assert len(context) <= hooks.MAX_CONTEXT_CHARS
    assert not (repo / ".claude").exists()


def test_startup_warns_about_trusted_legacy_swift_project_profile(tmp_path, monkeypatch):
    from chameleon_mcp import tools
    from chameleon_mcp.profile import loader

    path = "Projects/Feature/Market/Sources/Scenes/WriteForm/NA/FormInteractor.swift"
    loaded = SimpleNamespace(
        archetypes={
            "archetypes": {"old": {"paths_pattern": "swift/Projects/Feature/Market/unknown:swift"}}
        },
        canonicals={"canonicals": {"old": [{"witness": {"path": path}}]}},
    )
    monkeypatch.setattr(
        tools, "get_pattern_context", lambda _: {"data": {"repo": {"trust_state": "trusted"}}}
    )
    monkeypatch.setattr(loader, "load_profile_dir", lambda _: loaded)
    monkeypatch.setattr(loader, "find_repo_root", lambda _: tmp_path)
    monkeypatch.setattr(hooks, "_startup_targets", lambda _: ())
    response = hooks.context_response(hooks.HookRequest("SessionStart", tmp_path))
    context = response["hookSpecificOutput"]["additionalContext"]
    assert "refresh_repo" in context
    assert "force" in context


def test_startup_does_not_warn_for_current_or_untrusted_profile(tmp_path, monkeypatch):
    from chameleon_mcp import tools
    from chameleon_mcp.profile import loader
    from chameleon_mcp.signatures import path_pattern_bucket_for

    path = "Projects/Feature/Market/Sources/Scenes/WriteForm/NA/FormInteractor.swift"
    bucket, _ = path_pattern_bucket_for(path, include_extension=True)
    loaded = SimpleNamespace(
        archetypes={"archetypes": {"current": {"paths_pattern": bucket}}},
        canonicals={"canonicals": {"current": [{"witness": {"path": path}}]}},
    )
    monkeypatch.setattr(loader, "load_profile_dir", lambda _: loaded)
    monkeypatch.setattr(
        tools, "get_pattern_context", lambda _: {"data": {"repo": {"trust_state": "trusted"}}}
    )
    assert not hooks._startup_needs_refresh(tmp_path)
    loaded.archetypes["archetypes"]["current"]["paths_pattern"] = (
        "swift/Projects/Feature/Market/unknown:swift"
    )
    monkeypatch.setattr(
        tools, "get_pattern_context", lambda _: {"data": {"repo": {"trust_state": "untrusted"}}}
    )
    assert not hooks._startup_needs_refresh(tmp_path)


def test_startup_warns_for_legacy_non_project_swift_role(tmp_path, monkeypatch):
    from chameleon_mcp import tools
    from chameleon_mcp.profile import loader

    path = "Sources/Accounts/AccountInteractor.swift"
    loaded = SimpleNamespace(
        archetypes={
            "archetypes": {"old": {"paths_pattern": "swift/Sources/Accounts/unknown:swift"}}
        },
        canonicals={"canonicals": {"old": [{"witness": {"path": path}}]}},
    )
    monkeypatch.setattr(loader, "load_profile_dir", lambda _: loaded)
    monkeypatch.setattr(
        tools, "get_pattern_context", lambda _: {"data": {"repo": {"trust_state": "trusted"}}}
    )
    assert hooks._startup_needs_refresh(tmp_path)


def test_startup_warns_for_legacy_swift_profile_without_witnesses(tmp_path, monkeypatch):
    from chameleon_mcp import tools
    from chameleon_mcp.profile import loader

    loaded = SimpleNamespace(
        profile={"language": "swift"},
        archetypes={
            "archetypes": {"old": {"paths_pattern": "swift/Sources/Accounts/unknown:swift"}}
        },
        canonicals={"canonicals": {}},
    )
    monkeypatch.setattr(loader, "load_profile_dir", lambda _: loaded)
    monkeypatch.setattr(
        tools, "get_pattern_context", lambda _: {"data": {"repo": {"trust_state": "trusted"}}}
    )
    assert hooks._startup_needs_refresh(tmp_path)


def test_startup_refresh_check_skips_sample_archetypes_before_limit(tmp_path, monkeypatch):
    from chameleon_mcp import tools
    from chameleon_mcp.profile import loader

    sample = "Projects/Sample/Market/Sources/SampleView.swift"
    production = "Sources/Accounts/AccountInteractor.swift"
    names = [f"a{i:04}" for i in range(hooks.MAX_STARTUP_ARCHETYPES)]
    archetypes = {
        name: {"paths_pattern": "swift/Projects/Sample/Market/Sources/view:swift"} for name in names
    }
    canonicals = {name: [{"witness": {"path": sample}}] for name in names}
    archetypes["z-old"] = {"paths_pattern": "swift/Sources/Accounts/unknown:swift"}
    canonicals["z-old"] = [{"witness": {"path": production}}]
    loaded = SimpleNamespace(
        archetypes={"archetypes": archetypes}, canonicals={"canonicals": canonicals}
    )
    monkeypatch.setattr(loader, "load_profile_dir", lambda _: loaded)
    monkeypatch.setattr(
        tools, "get_pattern_context", lambda _: {"data": {"repo": {"trust_state": "trusted"}}}
    )
    assert hooks._startup_needs_refresh(tmp_path)


def test_startup_does_not_inject_samples_or_let_them_hide_production(tmp_path, monkeypatch):
    from chameleon_mcp import tools
    from chameleon_mcp.profile import loader

    sample = tmp_path / "Projects/Sample/Market/Sources/Example.swift"
    production = tmp_path / "Projects/Feature/Market/Sources/MarketView.swift"
    for path in (sample, production):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("struct Example {}")
    entries = {
        f"a{i:02}": [{"witness": {"path": sample.relative_to(tmp_path).as_posix()}}]
        for i in range(hooks.MAX_STARTUP_ARCHETYPES)
    }
    entries["z-production"] = [{"witness": {"path": production.relative_to(tmp_path).as_posix()}}]
    monkeypatch.setattr(
        tools, "get_pattern_context", lambda _: {"data": {"repo": {"trust_state": "trusted"}}}
    )
    monkeypatch.setattr(
        loader, "load_profile_dir", lambda _: SimpleNamespace(canonicals={"canonicals": entries})
    )
    assert hooks._startup_targets(tmp_path) == (production,)


def test_startup_continues_past_empty_excerpts(tmp_path, monkeypatch):
    from chameleon_mcp import tools
    from chameleon_mcp.profile import loader

    entries = {}
    for i in range(hooks.MAX_CONTEXTS + 1):
        path = tmp_path / f"Sources/App/Screen{i}View.swift"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("struct Screen {}")
        entries[f"a{i}"] = [{"witness": {"path": path.relative_to(tmp_path).as_posix()}}]
    loaded = SimpleNamespace(canonicals={"canonicals": entries})
    monkeypatch.setattr(loader, "load_profile_dir", lambda _: loaded)
    monkeypatch.setattr(loader, "find_repo_root", lambda _: tmp_path)

    def context(path):
        name = Path(path).stem
        return {
            "data": {
                "repo": {"trust_state": "trusted"},
                "archetype": {"archetype": name},
                "canonical_excerpt": {"content": "struct Safe {}" if name == "Screen6View" else ""},
            }
        }

    monkeypatch.setattr(tools, "get_pattern_context", context)
    results = hooks._collect_context(hooks._startup_targets(tmp_path), None)
    assert len(results) == 1
    assert results[0]["canonical_excerpt"]["content"] == "struct Safe {}"


def test_native_edit_uses_real_context_and_respects_disabled(swift_repo, monkeypatch):
    repo, recent = swift_repo
    _trust(repo)
    request = hooks.HookRequest(
        "PreToolUse",
        repo,
        _patch(
            "*** Update File: Sources/App/Screens/Screen1ViewController.swift",
            "@@",
            "+value",
        ),
    )
    response = hooks.context_response(request)
    assert "recent implementation" in json.dumps(response)
    monkeypatch.setenv("CHAMELEON_DISABLE", "1")
    assert hooks.context_response(request) == {}
    assert not (repo / ".claude").exists()


def test_native_patch_with_escaping_move_emits_nothing(swift_repo):
    repo, _ = swift_repo
    _trust(repo)
    request = hooks.HookRequest(
        "PreToolUse",
        repo,
        _patch(
            "*** Update File: Sources/App/Screens/Screen1ViewController.swift",
            "*** Move to: ../outside.swift",
            "@@",
            "+value",
        ),
    )
    assert hooks.context_response(request) == {}


def test_startup_ignores_forged_outside_canonical(swift_repo):
    repo, _ = swift_repo
    _trust(repo)
    path = repo / ".chameleon/canonicals.json"
    data = json.loads(path.read_text())
    for entries in data["canonicals"].values():
        for entry in entries:
            entry["witness"]["path"] = "../outside.swift"
    path.write_text(json.dumps(data))
    assert hooks.context_response(hooks.HookRequest("SessionStart", repo)) == {}


def test_native_hook_real_subprocess_and_trace(swift_repo, tmp_path):
    repo, _ = swift_repo
    _trust(repo)
    trace = tmp_path / "delivery.jsonl"
    payload = {"hook_event_name": "SessionStart", "cwd": str(repo), "session_id": "native"}
    proc = subprocess.run(
        [sys.executable, "-m", "chameleon_mcp.codex_hooks", "--trace", str(trace)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=30,
        env={**os.environ},
        cwd=repo,
    )
    assert proc.returncode == 0, proc.stderr
    response = json.loads(proc.stdout)
    assert "recent implementation" in json.dumps(response)
    assert json.loads(trace.read_text())["response"] == response
    assert not (repo / ".claude").exists()


def test_native_startup_respects_repo_skip(swift_repo):
    repo, _ = swift_repo
    _trust(repo)
    (repo / ".chameleon/.skip").touch()
    assert hooks.context_response(hooks.HookRequest("SessionStart", repo)) == {}


def test_native_payload_preserves_session_identity(tmp_path):
    payload = {
        "hook_event_name": "PreToolUse",
        "cwd": str(tmp_path),
        "session_id": "native-id",
        "tool_name": "apply_patch",
        "tool_input": {"command": _patch("*** Add File: New.swift", "+struct New {}")},
    }
    request = hooks.read_request(io.StringIO(json.dumps(payload)))
    assert request is not None
    assert request.session_id == "native-id"
    assert request.command == payload["tool_input"]["command"]


@pytest.mark.parametrize("suppression", ["skip", "session"])
def test_parent_cwd_respects_nested_repo_suppression(swift_repo, suppression):
    from chameleon_mcp import tools
    from chameleon_mcp.optouts import write_session_disable

    repo, _ = swift_repo
    _trust(repo)
    parent = repo.parent
    subprocess.run(["git", "-C", str(parent), "init", "-q"], check=True)
    request = hooks.HookRequest(
        "PreToolUse",
        parent,
        _patch(
            f"*** Update File: {repo.name}/Sources/App/Screens/Screen1ViewController.swift",
            "@@",
            "+value",
        ),
        session_id="nested-session",
    )
    assert hooks.context_response(request)
    if suppression == "skip":
        (repo / ".chameleon/.skip").touch()
    else:
        write_session_disable(tools._compute_repo_id(repo), request.session_id)
    assert hooks.context_response(request) == {}


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="FIFO unavailable")
def test_trace_fifo_does_not_delay_hook_response(tmp_path):
    fifo = tmp_path / "trace.fifo"
    os.mkfifo(fifo)
    proc = subprocess.run(
        [
            sys.executable,
            "-c",
            "from chameleon_mcp.codex_hooks import main; raise SystemExit(main())",
            "--trace",
            str(fifo),
        ],
        input="{}",
        capture_output=True,
        text=True,
        timeout=5,
    )
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout) == {}


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="FIFO unavailable")
def test_trace_refuses_fifo_even_when_reader_is_available(tmp_path):
    fifo = tmp_path / "trace.fifo"
    os.mkfifo(fifo)
    reader = os.open(fifo, os.O_RDONLY | os.O_NONBLOCK)
    try:
        proc = subprocess.run(
            [
                sys.executable,
                "-c",
                "from chameleon_mcp.codex_hooks import main; raise SystemExit(main())",
                "--trace",
                str(fifo),
            ],
            input="{}",
            capture_output=True,
            text=True,
            timeout=5,
        )
        assert proc.returncode == 0, proc.stderr
        assert json.loads(proc.stdout) == {}
        assert os.read(reader, 1) == b""
    finally:
        os.close(reader)
