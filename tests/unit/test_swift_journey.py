from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _git(repo: Path, *args: str, at: int = 1_700_000_000) -> None:
    subprocess.run(
        ["git", "-C", str(repo), *args],
        env={**os.environ, "GIT_AUTHOR_DATE": f"{at} +0000", "GIT_COMMITTER_DATE": f"{at} +0000"},
        capture_output=True,
        check=True,
        timeout=20,
    )


@pytest.fixture
def swift_repo(tmp_path, monkeypatch):
    from chameleon_mcp import tools

    monkeypatch.setenv("CHAMELEON_ALLOW_TMP_REPO", "1")
    monkeypatch.setenv("CHAMELEON_PLUGIN_DATA", str(tmp_path / "data"))
    monkeypatch.setenv("CHAMELEON_FETCH_PRODUCTION_REF", "0")
    monkeypatch.setenv("CHAMELEON_CONVENTIONS_MD", "0")
    repo = tmp_path / "swift-fixture"
    repo.mkdir()
    (repo / "Package.swift").write_text("// swift-tools-version: 6.0\nimport PackageDescription\n")
    src = repo / "Sources" / "App" / "Screens"
    src.mkdir(parents=True)
    for i in range(6):
        (src / f"Screen{i}ViewController.swift").write_text(
            f"import Foundation\nfinal class Screen{i}ViewController {{\n"
            '    func render() -> String { return "original" }\n}\n'
        )
        (src / f"Contract{i}ViewController.swift").write_text(
            f"import Foundation\nprotocol Contract{i}ViewController {{\n"
            "    func render() -> String\n}\n"
        )
        (src / f"Extension{i}ViewController.swift").write_text(
            f"import Foundation\nextension Screen{i}ViewController {{\n"
            '    func title() -> String { return "extension" }\n}\n'
        )
    _git(repo, "init", "-q")
    _git(repo, "config", "user.name", "SwiftChameleon fixture")
    _git(repo, "config", "user.email", "fixture@example.invalid")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "Add older Swift implementations")
    recent = src / "Screen5ViewController.swift"
    recent.write_text(recent.read_text().replace("original", "recent implementation"))
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "Update recent implementation", at=1_710_000_000)
    old = src / "Screen0ViewController.swift"
    old.write_text(old.read_text().replace("    func", "        func"))
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "Format an older implementation", at=1_720_000_000)
    protocol = src / "Contract5ViewController.swift"
    protocol.write_text(protocol.read_text().replace("func render()", "func display()"))
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "Update a different declaration role", at=1_730_000_000)
    result = tools.bootstrap_repo(str(repo), now=1_740_000_000)
    assert result["data"]["status"] == "success", result
    return repo, recent


def _trusted(repo: Path) -> None:
    from chameleon_mcp import tools

    result = tools.trust_profile(str(repo), repo.name)
    assert result["data"].get("status") in {"trusted", "success"}, result


def _context(repo: Path, file: Path) -> dict:
    from chameleon_mcp import tools

    return tools.get_pattern_context(str(file))["data"]


def test_swift_bootstrap_trust_and_recent_compatible_witness(swift_repo):
    repo, recent = swift_repo
    query = recent.with_name("Screen1ViewController.swift")
    untrusted = _context(repo, query)
    assert untrusted["archetype"]["archetype"] is None, untrusted
    _trusted(repo)
    context = _context(repo, query)
    encoded = json.dumps(context)
    assert recent.name in encoded, encoded
    assert "recent implementation" in encoded, encoded
    assert "protocol Contract" not in encoded, encoded
    assert "extension Screen" not in encoded, encoded


def test_swift_new_file_context_states_path_evidence(swift_repo):
    repo, recent = swift_repo
    _trusted(repo)
    context = _context(repo, recent.with_name("NewViewController.swift"))
    assert context["archetype"]["match_basis"] == "path_only", context
    assert context["archetype"]["file_exists"] is False, context


def _hook(payload: str, repo: Path, *, disabled: bool = False):
    env = {
        **os.environ,
        "CLAUDE_PLUGIN_ROOT": str(ROOT / "plugin"),
        "CHAMELEON_ALLOW_TMP_REPO": "1",
        "CHAMELEON_DISABLE": "1" if disabled else "0",
    }
    return subprocess.run(
        ["cmd", "/c", str(ROOT / "plugin/hooks/run-hook.cmd"), "preflight-and-advise"]
        if sys.platform == "win32"
        else ["bash", str(ROOT / "plugin/hooks/run-hook.cmd"), "preflight-and-advise"],
        input=payload,
        text=True,
        capture_output=True,
        cwd=repo,
        env=env,
        timeout=60,
    )


def test_swift_real_pre_edit_hook_delivers_witness(swift_repo):
    repo, recent = swift_repo
    _trusted(repo)
    proc = _hook(
        json.dumps(
            {
                "tool_name": "Edit",
                "tool_input": {"file_path": str(recent.with_name("Screen1ViewController.swift"))},
                "session_id": "swift-product-journey",
                "cwd": str(repo),
            }
        ),
        repo,
    )
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    context = payload.get("hookSpecificOutput", {}).get("additionalContext", "")
    assert "recent implementation" in context, payload
    assert recent.stem in context, payload


@pytest.mark.parametrize("payload", ["", "not-json", "null", '{"tool_input":null}'])
def test_swift_hook_malformed_payload_fails_open(swift_repo, payload):
    repo, _ = swift_repo
    proc = _hook(payload, repo)
    assert proc.returncode == 0, proc.stderr
    assert isinstance(json.loads(proc.stdout or "{}"), dict)


def test_swift_disabled_hook_emits_no_context(swift_repo):
    repo, recent = swift_repo
    _trusted(repo)
    proc = _hook(
        json.dumps(
            {
                "tool_name": "Edit",
                "tool_input": {"file_path": str(recent)},
                "session_id": "swift-disabled",
                "cwd": str(repo),
            }
        ),
        repo,
        disabled=True,
    )
    assert proc.returncode == 0, proc.stderr
    assert (
        not json.loads(proc.stdout or "{}").get("hookSpecificOutput", {}).get("additionalContext")
    )


def test_swift_context_through_real_mcp_stdio(swift_repo):
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    repo, recent = swift_repo
    _trusted(repo)

    async def exercise():
        params = StdioServerParameters(
            command=sys.executable,
            args=[
                "-c",
                "import faulthandler; "
                "faulthandler.dump_traceback_later(15, repeat=True); "
                "from chameleon_mcp.server import main; main()",
            ],
            env={**os.environ, "PYTHONPATH": str(ROOT / "plugin/mcp")},
        )
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(
                    "get_pattern_context",
                    {
                        "file_path": str(recent.with_name("Screen1ViewController.swift")),
                    },
                )
                assert not result.isError, result
                payload = json.loads(result.content[0].text)
                assert "recent implementation" in json.dumps(payload), payload

    asyncio.run(asyncio.wait_for(exercise(), timeout=45))


def test_swift_refresh_repairs_missing_profile_artifact(swift_repo):
    from chameleon_mcp import tools

    repo, recent = swift_repo
    _trusted(repo)
    (repo / ".chameleon/canonicals.json").unlink()
    damaged = _context(repo, recent)
    assert "recent implementation" not in json.dumps(damaged), damaged
    result = tools.refresh_repo(str(repo), force=True)
    assert result["data"].get("status") in {"success", "refreshed"}, result
    assert (repo / ".chameleon/canonicals.json").is_file()
    assert "recent implementation" in json.dumps(_context(repo, recent))


@pytest.mark.parametrize(
    "artifact",
    ["profile.json", "archetypes.json", "canonicals.json", "rules.json", "conventions.json"],
)
def test_swift_corrupt_profile_fails_open_and_refresh_repairs(swift_repo, artifact):
    from chameleon_mcp import tools

    repo, recent = swift_repo
    _trusted(repo)
    (repo / ".chameleon" / artifact).write_text("not-json")
    context = _context(repo, recent)
    assert "recent implementation" not in json.dumps(context), context
    repaired = tools.refresh_repo(str(repo), force=True)
    assert repaired["data"].get("status") in {"success", "refreshed"}, repaired
    assert "recent implementation" in json.dumps(_context(repo, recent))


def test_swift_uppercase_sources_bootstrap_and_keep_role_filter(swift_repo):
    from chameleon_mcp import tools

    repo, recent = swift_repo
    for path in list((repo / "Sources").rglob("*.swift")):
        _git(
            repo,
            "mv",
            str(path.relative_to(repo)),
            str(path.with_suffix(".SWIFT").relative_to(repo)),
        )
    _git(repo, "commit", "-qm", "Move to uppercase source extensions", at=1_735_000_000)
    result = tools.bootstrap_repo(str(repo), force=True, now=1_740_000_000)
    assert result["data"]["status"] == "success", result
    _trusted(repo)
    context = _context(repo, recent.with_name("Screen1ViewController.SWIFT"))
    assert context["canonical_excerpt"]["witness_path"].endswith("Screen5ViewController.SWIFT"), (
        context
    )
    assert "recent implementation" in context["canonical_excerpt"]["content"]
