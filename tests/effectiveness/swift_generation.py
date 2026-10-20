"""Run isolated Codex Swift generation cells with held executable checks."""

from __future__ import annotations

import argparse
import atexit
import hashlib
import json
import os
import random
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from tests.effectiveness.swift_generation_fixture import (
    PROMPTS,
    behavior_source,
    create_fixture,
    git,
)

ROOT = Path(__file__).resolve().parents[2]
MODEL = "gpt-6-astra"


def command(args: list[str], cwd: Path, **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True, check=False, **kwargs)


def dump(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def source_hash(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*.swift")):
        if ".build" in path.parts:
            continue
        digest.update(str(path.relative_to(root)).encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def cell_environment(state: Path) -> dict[str, str]:
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("CHAMELEON_", "CLAUDE_", "CODEX_"))
    }
    state.mkdir(parents=True, exist_ok=True)
    home = state / "codex"
    home.mkdir()
    auth = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))) / "auth.json"
    if auth.is_file():
        shutil.copyfile(auth, home / "auth.json")
        (home / "auth.json").chmod(0o600)
        atexit.register((home / "auth.json").unlink, missing_ok=True)
    temporary = state / "tmp"
    temporary.mkdir()
    env.update(
        CODEX_HOME=str(home),
        CHAMELEON_PLUGIN_DATA=str(state / "storage"),
        CHAMELEON_HMAC_KEY_PATH=str(state / "key"),
        CHAMELEON_ALLOW_TMP_REPO="1",
        CHAMELEON_FETCH_PRODUCTION_REF="0",
        CHAMELEON_CONVENTIONS_MD="0",
        CHAMELEON_HOOK_ERROR_LOG=str(state / "hook-errors.log"),
        TMPDIR=str(temporary),
    )
    return env


def derive(root: Path, env: dict[str, str], python: Path, state: Path) -> dict:
    script = """import json,sys
from pathlib import Path
from chameleon_mcp.tools import bootstrap_repo, _compute_repo_id
from chameleon_mcp.profile.trust import grant_trust
root=Path(sys.argv[1])
response=bootstrap_repo(str(root))
if (response.get("data") or {}).get("status") not in {"success","already_bootstrapped"}:
    raise RuntimeError(response)
profile=root/".chameleon"
config=profile/"config.json"
data=json.loads(config.read_text()) if config.exists() else {}
data.update(production_ref=None,auto_refresh={"enabled":False,"fetch_production_ref":False})
data["enforcement"]={"mode":"shadow","correctness_judge":False,"duplication_review":False,"idiom_review":False}
config.write_text(json.dumps(data))
grant_trust(_compute_repo_id(root),profile)
print(json.dumps(response))
"""
    result = command([str(python), "-c", script, str(root)], root, env=env, timeout=180)
    (state / "profile.stdout").write_text(result.stdout)
    (state / "profile.stderr").write_text(result.stderr)
    if result.returncode:
        raise RuntimeError("profile derivation failed: " + result.stderr[-2000:])
    if (root / ".claude").exists():
        raise RuntimeError("profile derivation unexpectedly wrote Claude settings or mirror")
    return json.loads(result.stdout)


def codex_args(root: Path, prompt: str, trace: Path | None, python: Path) -> list[str]:
    args = [
        "codex",
        "exec",
        "--ignore-user-config",
        "--ignore-rules",
        "--ephemeral",
        "--dangerously-bypass-approvals-and-sandbox",
        "-C",
        str(root),
        "-m",
        MODEL,
        "-c",
        'model_reasoning_effort="medium"',
        "-c",
        "project_doc_max_bytes=0",
        "-c",
        "features.multi_agent=false",
        "--json",
        "--color",
        "never",
    ]
    if trace:
        import shlex

        hook = shlex.join([str(python), "-m", "chameleon_mcp.codex_hooks", "--trace", str(trace)])
        entry = (
            '{ hooks = [{ type = "command", command = '
            + json.dumps(hook)
            + ", timeout = 30, additionalContextLimit = 24000 }] }"
        )
        edit_entry = entry.replace("{ hooks", '{ matcher = "^apply_patch$", hooks', 1)
        args += [
            "--dangerously-bypass-hook-trust",
            "-c",
            "features.hooks=true",
            "-c",
            "hooks.SessionStart=[" + entry + "]",
            "-c",
            "hooks.PreToolUse=[" + edit_entry + "]",
        ]
    args.append(prompt)
    return args


def run_session(
    args: list[str], root: Path, env: dict[str, str], state: Path, timeout: int
) -> dict:
    started = time.monotonic()
    with (
        (state / "session.jsonl").open("w") as out,
        (state / "session.stderr").open("w") as err,
    ):
        process = subprocess.Popen(
            args,
            cwd=root,
            env=env,
            text=True,
            stdout=out,
            stderr=err,
            start_new_session=True,
        )
        timed_out = False
        try:
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
    events = []
    for line in (state / "session.jsonl").read_text().splitlines():
        try:
            events.append(json.loads(line))
        except ValueError:
            continue
    completed = [event for event in events if event.get("type") == "turn.completed"]
    failures = [
        event
        for event in events
        if event.get("type") == "turn.failed"
        or (
            event.get("type") == "error"
            and "--dangerously-bypass-hook-trust enabled" not in str(event.get("message", ""))
        )
    ]
    messages = [
        event["item"].get("text", "")
        for event in events
        if event.get("type") == "item.completed"
        and event.get("item", {}).get("type") == "agent_message"
    ]
    tools = [
        event["item"]
        for event in events
        if event.get("type") == "item.completed"
        and event.get("item", {}).get("type")
        in {"command_execution", "file_change", "mcp_tool_call"}
    ]
    return {
        "command": args,
        "returncode": process.returncode,
        "timeout": timed_out,
        "duration_seconds": round(time.monotonic() - started, 3),
        "terminal_reason": "timeout"
        if timed_out
        else "failed"
        if failures or process.returncode
        else "completed"
        if completed
        else "missing_completion",
        "usage": completed[-1].get("usage") if completed else None,
        "errors": failures,
        "messages": messages,
        "tools": tools,
        "requested_model": MODEL,
        "requested_reasoning": "medium",
        "actual_model_observed": None,
        "model_limit": "Codex JSON events do not expose the resolved model. The same exact CLI model identifier is supplied in every cell.",
        "money_limit": "ChatGPT subscription authentication. The CLI exposes tokens, not dollar cost.",
    }


def assess(root: Path, original: dict[str, str], task: str, state: Path) -> dict:
    staging = state / "compiled"
    staging.mkdir()
    sources = sorted((root / "Sources").rglob("*.swift"))
    for index, source in enumerate(sources):
        shutil.copyfile(source, staging / f"source{index}.swift")
    (staging / "Main.swift").write_text(behavior_source(task))
    output = staging / "CedarStore"
    compile_result = command(
        [
            "swiftc",
            "-swift-version",
            "6",
            "-parse-as-library",
            *map(str, sorted(staging.glob("*.swift"))),
            "-o",
            str(output),
        ],
        staging,
        timeout=120,
    )
    (state / "compile.stdout").write_text(compile_result.stdout)
    (state / "compile.stderr").write_text(compile_result.stderr)
    runtime = (
        command([str(output)], staging, timeout=30) if compile_result.returncode == 0 else None
    )
    if runtime:
        (state / "behavior.stdout").write_text(runtime.stdout)
        (state / "behavior.stderr").write_text(runtime.stderr)
    changes = {
        str(path.relative_to(root)): path.read_text()
        for path in sources
        if original.get(str(path.relative_to(root))) != path.read_text()
    }
    new_text = "\n".join(value for key, value in changes.items() if "/Composition/" not in key)
    import re

    unrelated = [
        key
        for key, value in original.items()
        if "/Composition/" not in key
        and (not (root / key).is_file() or (root / key).read_text() != value)
    ]
    checks = {
        "protocol_injection": bool(re.search(r"protocol\s+\w*Repository\b", new_text))
        and bool(re.search(r"repository\s*:\s*(?:any\s+)?\w*Repository\b", new_text)),
        "domain_types": "ShopResult<" in new_text
        and ("ShippingQuote" if task == "shipping" else "PickupLocation") in new_text,
        "shared_conversion": ".domain" in new_text
        and (task != "pickup" or "PickupCatalog.available" in new_text),
        "scope_preserved": not unrelated,
    }
    return {
        "compiled": compile_result.returncode == 0,
        "behavior": runtime is not None and runtime.returncode == 0,
        "structure": checks,
        "unrelated_changes": unrelated,
        "changed_files": sorted(changes),
    }


def save_patch(root: Path, state: Path) -> str:
    patch = git(root, "diff", "HEAD", "--", "Sources", "Package.swift", "README.md")
    untracked = git(
        root, "ls-files", "--others", "--exclude-standard", "--", "Sources"
    ).splitlines()
    for path in untracked:
        result = command(["git", "diff", "--no-index", "--", "/dev/null", path], root)
        patch += result.stdout
    (state / "change.patch").write_text(patch)
    return patch


def plan() -> list[dict]:
    cells = []
    for task_index, task in enumerate(PROMPTS):
        for repeat in range(5):
            arms = ["A", "B"] if (repeat + task_index) % 2 == 0 else ["B", "A"]
            for arm in arms:
                cells.append({"task": task, "repeat": repeat + 1, "arm": arm})
    labels = list(range(1, len(cells) + 1))
    random.Random(20261021).shuffle(labels)
    return [
        dict(cell, label=f"sample-{label:02d}") for cell, label in zip(cells, labels, strict=True)
    ]


def run_cell(cell: dict, root: Path, state: Path, python: Path, mode: str, timeout: int) -> dict:
    result = dict(
        cell,
        workspace=str(root),
        status="error",
        success=False,
        source_hash=None,
        fixture_commit=None,
        empty_output=True,
        deliveries=[],
        delivered_context=False,
        checks={
            "compiled": False,
            "behavior": False,
            "structure": {
                "protocol_injection": False,
                "domain_types": False,
                "shared_conversion": False,
                "scope_preserved": False,
            },
            "unrelated_changes": [],
            "changed_files": [],
        },
        session={
            "terminal_reason": "not_started",
            "duration_seconds": 0,
            "usage": None,
            "errors": [],
            "tools": [],
        },
    )
    phase = "setup"
    try:
        state.mkdir()
        env = cell_environment(state)
        result["fixture_commit"] = create_fixture(root)
        result["source_hash"] = source_hash(root)
        original = {str(path.relative_to(root)): path.read_text() for path in root.rglob("*.swift")}
        phase = "profile"
        if cell["arm"] == "B":
            result["profile"] = derive(root, env, python, state)
        elif (root / ".chameleon").exists() or (root / ".claude").exists():
            raise RuntimeError("baseline contains plugin context")
        if mode == "prepare":
            result.update(prepared=True, status="prepared")
            (state / "Main.swift").write_text(behavior_source("shipping"))
            return result
        phase = "session"
        trace = state / "delivery.jsonl" if cell["arm"] == "B" else None
        prompt = PROMPTS[cell["task"]] if mode == "run" else "Read README.md and reply with ready."
        session = run_session(codex_args(root, prompt, trace, python), root, env, state, timeout)
        result["session"] = session
        phase = "collection"
        result["empty_output"] = not save_patch(root, state).strip()
        if trace and trace.exists():
            result["deliveries"] = [json.loads(line) for line in trace.read_text().splitlines()]
        result["delivered_context"] = any(
            item.get("response", {}).get("hookSpecificOutput", {}).get("additionalContext")
            for item in result["deliveries"]
        )
        phase = "assessment"
        if mode == "run":
            result["checks"] = assess(root, original, cell["task"], state)
            result["success"] = (
                session["terminal_reason"] == "completed"
                and not result["empty_output"]
                and result["checks"]["behavior"]
            )
        else:
            result["success"] = (
                session["terminal_reason"] == "completed" and result["delivered_context"]
            )
        result["status"] = "ok" if result["success"] else "failed"
    except Exception as error:
        result["error"] = {
            "phase": phase,
            "type": type(error).__name__,
            "message": str(error),
        }
    finally:
        (state / "codex" / "auth.json").unlink(missing_ok=True)
        if (root / "Sources").is_dir():
            try:
                save_patch(root, state)
                shutil.copytree(root / "Sources", state / "source")
            except Exception as error:
                result["collection_error"] = str(error)
    return result


def authentication_failed(result: dict, state: Path) -> bool:
    text = json.dumps(result["session"]["errors"]).lower()
    stderr = state / "session.stderr"
    if stderr.exists():
        text += stderr.read_text().lower()
    return any(needle in text for needle in ("authentication", "unauthorized", "invalid api key"))


def main() -> int:
    if sys.platform != "darwin":
        raise SystemExit("This study requires macOS and a locally installed Swift 6 compiler.")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["prepare", "pilot", "run"], default="prepare")
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--python", type=Path, default=Path(sys.executable))
    parser.add_argument("--timeout", type=int, default=360)
    args = parser.parse_args()
    if (args.run_dir / "run.json").exists():
        raise SystemExit("Use a fresh run directory to preserve the existing record.")
    args.run_dir.mkdir(parents=True, exist_ok=True)
    workbase = Path(tempfile.mkdtemp(prefix="cedar-shop-", dir="/private/tmp"))
    run = {
        "method": "Codex native SwiftChameleon context hooks",
        "model": MODEL,
        "reasoning": "medium",
        "planned_cells": 20,
        "prompts": PROMPTS,
        "cells": [],
        "workspace": str(workbase),
        "status": "preparing",
    }
    run["codex_version"] = command(["codex", "--version"], ROOT).stdout.strip()
    run["swift_version"] = command(["swiftc", "--version"], ROOT).stdout.strip()
    targets = (
        [{"task": "shipping", "arm": "B", "repeat": 0, "label": "pilot"}]
        if args.mode != "run"
        else plan()
    )
    run["planned_cells"] = len(targets)
    run["schedule"] = [dict(cell, status="not_run") for cell in targets]
    dump(args.run_dir / "mapping.json", targets)
    dump(args.run_dir / "run.json", run)
    for index, cell in enumerate(targets):
        state = args.run_dir / cell["label"]
        root = workbase / f"shop-{index + 1:02d}" / "CedarStore"
        result = run_cell(cell, root, state, args.python, args.mode, args.timeout)
        run["cells"].append(result)
        run["schedule"][index]["status"] = result["status"]
        if args.mode == "prepare":
            run["status"] = "prepared" if result["status"] == "prepared" else "error"
            dump(args.run_dir / "run.json", run)
            return 0 if run["status"] == "prepared" else 1
        session = result["session"]
        run["status"] = "running"
        dump(args.run_dir / "run.json", run)
        print(
            json.dumps(
                {
                    "label": cell["label"],
                    "task": cell["task"],
                    "arm": cell["arm"],
                    "success": result["success"],
                    "terminal_reason": session["terminal_reason"],
                    "context": result["delivered_context"],
                    "usage": session["usage"],
                }
            ),
            flush=True,
        )
        if authentication_failed(result, state):
            run["status"] = "authentication_blocked"
            for pending in run["schedule"][index + 1 :]:
                pending["reason"] = "stopped_after_authentication_failure"
            break
    else:
        run["status"] = "completed"
    dump(args.run_dir / "run.json", run)
    return 0 if run["status"] == "completed" else 1


if __name__ == "__main__":
    sys.exit(main())
