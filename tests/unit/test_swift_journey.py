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


def test_normal_refresh_rebuilds_legacy_swift_partition(swift_repo):
    from chameleon_mcp import tools
    from chameleon_mcp.signatures import SWIFT_BUCKET_VERSION

    repo, _ = swift_repo
    manifest = repo / ".chameleon/profile.json"
    data = json.loads(manifest.read_text())
    data.pop("swift_bucket_version", None)
    manifest.write_text(json.dumps(data))
    result = tools.refresh_repo(str(repo))["data"]
    assert result["status"] != "noop"
    assert json.loads(manifest.read_text())["swift_bucket_version"] == SWIFT_BUCKET_VERSION


@pytest.mark.parametrize("force", [False, True])
def test_refresh_does_not_downgrade_newer_swift_partition(swift_repo, force):
    from chameleon_mcp import tools
    from chameleon_mcp.signatures import SWIFT_BUCKET_VERSION

    repo, _ = swift_repo
    manifest = repo / ".chameleon/profile.json"
    data = json.loads(manifest.read_text())
    data["swift_bucket_version"] = SWIFT_BUCKET_VERSION + 1
    manifest.write_text(json.dumps(data))
    before = manifest.read_bytes()
    result = tools.refresh_repo(str(repo), force=force)["data"]
    assert result["status"] == "unsupported_swift_bucket_version"
    assert manifest.read_bytes() == before


def test_force_bootstrap_does_not_downgrade_newer_swift_partition(swift_repo):
    from chameleon_mcp import tools
    from chameleon_mcp.signatures import SWIFT_BUCKET_VERSION

    repo, _ = swift_repo
    manifest = repo / ".chameleon/profile.json"
    data = json.loads(manifest.read_text())
    data["swift_bucket_version"] = SWIFT_BUCKET_VERSION + 1
    manifest.write_text(json.dumps(data))
    before = manifest.read_bytes()
    assert (
        tools.bootstrap_repo(str(repo), force=True)["data"]["status"]
        == "unsupported_swift_bucket_version"
    )
    assert manifest.read_bytes() == before


def test_swift_safe_identifier_survives_bootstrap_and_live_excerpt_scan(swift_repo):
    from chameleon_mcp import codex_hooks, tools

    repo, recent = swift_repo
    name = "LongSwiftModel" + "A" * 26
    declaration = f"private let accessToken: {name}"
    recent.write_text(
        recent.read_text().replace("    func render", f"    {declaration}\n    func render")
    )
    assert (
        tools.bootstrap_repo(str(repo), force=True, now=1_740_000_000)["data"]["status"]
        == "success"
    )
    _trusted(repo)
    context = _context(repo, recent)
    assert declaration in context["canonical_excerpt"]["content"]
    excerpt = tools.get_canonical_excerpt(str(repo), context["archetype"]["archetype"])["data"]
    assert declaration in excerpt["content"]

    blob = "a1B2c3D4e5F6g7H8i9J0k1L2m3N4o5P6q7R8s9T0"
    recent.write_text(
        recent.read_text() + f'\nlet example = """\nprivate let accessToken: {blob}\n"""\n'
    )
    assert not _context(repo, recent)["canonical_excerpt"]["content"]
    excerpt = tools.get_canonical_excerpt(str(repo), context["archetype"]["archetype"])["data"]
    assert not excerpt["content"]
    patch = f"*** Begin Patch\n*** Update File: {recent}\n@@\n-old\n+new\n*** End Patch"
    assert codex_hooks.context_response(codex_hooks.HookRequest("PreToolUse", repo, patch)) == {}


@pytest.mark.parametrize("api", ["pattern_context", "canonical_excerpt"])
@pytest.mark.parametrize("failure", ["runtime_error", "import_error"])
def test_swift_scan_failure_withholds_witness_and_recovers(swift_repo, monkeypatch, api, failure):
    import builtins

    from chameleon_mcp import _excerpt_cache, codex_hooks, tools
    from chameleon_mcp.bootstrap import canonical_scanner

    repo, recent = swift_repo
    _trusted(repo)
    context = _context(repo, recent)
    archetype = context["archetype"]["archetype"]
    assert archetype
    assert "recent implementation" in context["canonical_excerpt"]["content"]

    def read_excerpt():
        if api == "pattern_context":
            return _context(repo, recent)["canonical_excerpt"]
        return tools.get_canonical_excerpt(str(repo), archetype)["data"]

    assert "recent implementation" in read_excerpt()["content"]
    _excerpt_cache.clear()
    with monkeypatch.context() as patch:
        if failure == "runtime_error":

            def broken_scan(*args, **kwargs):
                raise RuntimeError("scanner unavailable")

            patch.setattr(canonical_scanner, "is_safe_canonical", broken_scan)
        else:
            real_import = builtins.__import__

            def broken_import(name, *args, **kwargs):
                if name == "chameleon_mcp.bootstrap.canonical_scanner":
                    raise ImportError("scanner unavailable")
                return real_import(name, *args, **kwargs)

            patch.setattr(builtins, "__import__", broken_import)
        blocked = read_excerpt()
        assert not blocked["content"]
        assert blocked.get("witness_path") is None
        assert blocked.get("sha_hint") is None
        if api == "pattern_context":
            assert blocked["redacted_reason"] == "safety_scan_failed"
            patch_text = (
                f"*** Begin Patch\n*** Update File: {recent}\n@@\n-old\n+new\n*** End Patch"
            )
            assert (
                codex_hooks.context_response(
                    codex_hooks.HookRequest("PreToolUse", repo, patch_text)
                )
                == {}
            )
        else:
            assert blocked["status"] == "failed"
            assert "safety scan failed" in blocked["error"]

    assert "recent implementation" in read_excerpt()["content"]


@pytest.mark.parametrize("api", ["pattern_context", "canonical_excerpt"])
@pytest.mark.parametrize("failure", ["backend_raises", "backend_missing"])
def test_swift_backend_scan_error_does_not_disclose_witness(swift_repo, monkeypatch, api, failure):
    import builtins

    from detect_secrets.core import scan

    from chameleon_mcp import _excerpt_cache, tools
    from chameleon_mcp.bootstrap.canonical_scanner import is_safe_canonical

    repo, recent = swift_repo
    _trusted(repo)
    archetype = _context(repo, recent)["archetype"]["archetype"]
    url = "https://" + "alice" + ":" + "correctHorseBatteryStaple" + "@" + "example.com"
    poisoned = recent.read_text() + f'\nlet endpoint = "{url}"\n'
    assert not is_safe_canonical(poisoned, language="swift")
    recent.write_text(poisoned)
    _excerpt_cache.clear()

    if failure == "backend_raises":

        def broken_scan(*args, **kwargs):
            raise RuntimeError("detect-secrets unavailable")

        monkeypatch.setattr(scan, "scan_line", broken_scan)
    else:
        real_import = builtins.__import__

        def broken_import(name, *args, **kwargs):
            if name == "detect_secrets.core.scan":
                raise ImportError("detect-secrets unavailable")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", broken_import)
    if api == "pattern_context":
        blocked = _context(repo, recent)["canonical_excerpt"]
    else:
        blocked = tools.get_canonical_excerpt(str(repo), archetype)["data"]
    assert not blocked["content"]
    assert url not in json.dumps(blocked)


@pytest.mark.parametrize("api", ["pattern_context", "canonical_excerpt"])
def test_swift_incomplete_long_line_scan_withholds_witness(swift_repo, api):
    from chameleon_mcp import _excerpt_cache, tools
    from chameleon_mcp._thresholds import threshold_int

    repo, recent = swift_repo
    _trusted(repo)
    archetype = _context(repo, recent)["archetype"]["archetype"]
    benign = 'let title = "' + "a" * threshold_int("SECRET_SCAN_MAX_LINE_LEN") + '"\n'
    recent.write_text(recent.read_text() + "\n" + benign)
    _excerpt_cache.clear()
    if api == "pattern_context":
        blocked = _context(repo, recent)["canonical_excerpt"]
    else:
        blocked = tools.get_canonical_excerpt(str(repo), archetype)["data"]
    assert not blocked["content"]
    assert (
        blocked.get("redacted_reason") == "safety_scan_failed" or blocked.get("status") == "failed"
    )


@pytest.mark.parametrize("api", ["pattern_context", "canonical_excerpt"])
def test_swift_large_multiline_witness_remains_available(swift_repo, api):
    from chameleon_mcp import _excerpt_cache, tools
    from chameleon_mcp._thresholds import threshold_int

    repo, recent = swift_repo
    _trusted(repo)
    archetype = _context(repo, recent)["archetype"]["archetype"]
    lines = [f'let title{i} = "' + "abc" * 30 + '"' for i in range(30)]
    assert sum(len(line) for line in lines) > threshold_int("SECRET_SCAN_MAX_LINE_LEN")
    assert max(map(len, lines)) < threshold_int("SECRET_SCAN_MAX_LINE_LEN")
    recent.write_text(recent.read_text() + "\n" + "\n".join(lines) + "\n")
    _excerpt_cache.clear()
    if api == "pattern_context":
        result = _context(repo, recent)["canonical_excerpt"]
    else:
        result = tools.get_canonical_excerpt(str(repo), archetype)["data"]
    assert "let title29" in result["content"]


def _hook(payload: str, repo: Path, *, disabled: bool = False):
    env = {
        **os.environ,
        "CLAUDE_PLUGIN_ROOT": str(ROOT / "plugin"),
        "CHAMELEON_ALLOW_TMP_REPO": "1",
        "CHAMELEON_DISABLE": "1" if disabled else "0",
    }
    return subprocess.run(
        ["bash", str(ROOT / "plugin/hooks/run-hook.cmd"), "preflight-and-advise"],
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
            args=["-m", "chameleon_mcp.server"],
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
