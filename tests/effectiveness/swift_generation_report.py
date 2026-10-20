"""Publish explicit, credential-free artifacts from a completed Swift run."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
from collections import Counter
from pathlib import Path

from tests.effectiveness.swift_generation import dump
from tests.effectiveness.swift_generation_fixture import PROMPTS


def patch(root: Path) -> str:
    def git(*args: str) -> subprocess.CompletedProcess:
        return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, check=False)

    result = git("diff", "HEAD", "--", ".", ":!.chameleon", ":!.claude", ":!.codex").stdout
    for relative in git("ls-files", "--others", "--exclude-standard").stdout.splitlines():
        path = root / relative
        if (
            path.parts[len(root.parts)] in {".chameleon", ".claude", ".codex"}
            or path.stat().st_size > 200_000
        ):
            continue
        try:
            path.read_text(encoding="utf-8")
        except (UnicodeError, OSError):
            continue
        result += git("diff", "--no-index", "--", "/dev/null", relative).stdout
    return result


def verify_patch_coverage(root: Path, text: str) -> list[str]:
    def paths(*args: str) -> list[str]:
        result = subprocess.run(
            ["git", *args], cwd=root, capture_output=True, text=True, check=True
        )
        return result.stdout.splitlines()

    expected = {
        name
        for name in paths("diff", "--name-only", "HEAD")
        + paths("ls-files", "--others", "--exclude-standard")
        if name.endswith(".swift") and not name.startswith((".chameleon/", ".claude/", ".codex/"))
    }
    present = set(re.findall(r"^\+\+\+ b/(.+)$", text, re.MULTILINE))
    deleted = set(re.findall(r"^--- a/(.+)$", text, re.MULTILINE))
    missing = expected - present - deleted
    if missing:
        raise ValueError("missing changed Swift files from full patch: " + repr(sorted(missing)))
    return sorted(expected)


def publish(run_dir: Path, destination: Path) -> dict:
    run = json.loads((run_dir / "run.json").read_text())
    if run["status"] != "completed" or len(run["cells"]) != 20:
        raise ValueError("publication requires the complete registered run")
    prepared = [
        cell for cell in run["cells"] if cell.get("source_hash") and cell.get("fixture_commit")
    ]
    if (
        len({cell["source_hash"] for cell in prepared}) > 1
        or len({cell["fixture_commit"] for cell in prepared}) > 1
    ):
        raise ValueError("generation cells did not start from identical source and history")
    if destination.exists():
        raise ValueError("destination already exists")
    destination.mkdir(parents=True)
    provenance = destination / "provenance"
    provenance.mkdir()
    provenance_hashes = {}
    for filename in (
        "protocol.json",
        "adapter-sha256.txt",
        "codex_hooks.py",
        "swift_generation.py",
        "swift_generation_fixture.py",
        "generation-design.md",
    ):
        if (run_dir / filename).exists():
            original = (run_dir / filename).read_bytes()
            sanitized = original.decode().replace(str(Path.home()), "/home/runner").encode()
            (provenance / filename).write_bytes(sanitized)
            provenance_hashes[filename] = {
                "original_sha256": hashlib.sha256(original).hexdigest(),
                "published_sha256": hashlib.sha256(sanitized).hexdigest(),
            }
    dump(provenance / "hashes.json", provenance_hashes)
    (provenance / "README.md").write_text(
        "# Frozen run provenance\n\n"
        "The protocol hashes identify the original private run artifacts. "
        "Published source snapshots replace the developer home with `/home/runner`. "
        "hashes.json records original and published hashes separately. "
        "The original private artifacts remain unchanged.\n"
    )
    bundle = destination / "blind"
    bundle.mkdir()
    mapping = []
    metrics = []
    all_context = Counter()
    for cell in run["cells"]:
        label = cell["label"]
        state = run_dir / label
        root = Path(cell["workspace"])
        available = bool(
            (root / ".git").is_dir() and cell.get("source_hash") and cell.get("fixture_commit")
        )
        expanded_patch = patch(root) if available else ""
        covered = verify_patch_coverage(root, expanded_patch) if available else []
        if state.is_dir():
            (state / "complete.patch").write_text(expanded_patch)
        output = bundle / label
        output.mkdir()
        (output / "change.patch").write_text(expanded_patch)
        (output / "request.txt").write_text(PROMPTS[cell["task"]] + "\n")
        for folder in ("Sources", "Tests"):
            if (root / folder).exists():
                shutil.copytree(root / folder, output / folder)
        if (root / "Package.swift").is_file():
            shutil.copyfile(root / "Package.swift", output / "Package.swift")
        if not available:
            (output / "unavailable.txt").write_text(
                "No complete package was produced for this registered output.\n"
            )
        evidence = destination / "evidence" / label
        evidence.mkdir(parents=True)
        replacements = {
            str(root): "/workspace/CedarStore",
            str(state): "/state",
            str(run_dir): "/record",
            str(Path.home()): "/home/runner",
        }
        for filename in (
            "session.jsonl",
            "session.stderr",
            "delivery.jsonl",
            "compile.stdout",
            "compile.stderr",
            "behavior.stdout",
            "behavior.stderr",
        ):
            source = state / filename
            if source.exists():
                text = source.read_text()
                for old, new in replacements.items():
                    text = text.replace(old, new)
                (evidence / filename).write_text(text)
        mapping.append({key: cell[key] for key in ("label", "task", "repeat", "arm")})
        session = cell["session"]
        pretool = [
            delivery for delivery in cell["deliveries"] if delivery.get("event") == "PreToolUse"
        ]
        delivered_pretool = [
            delivery
            for delivery in pretool
            if delivery.get("response", {}).get("hookSpecificOutput", {}).get("additionalContext")
        ]
        launch_command = []
        for arg in session.get("command", []):
            for old, new in replacements.items():
                arg = arg.replace(old, new)
            launch_command.append(arg)
        metric = {
            **mapping[-1],
            "success": cell["success"],
            "empty_output": cell["empty_output"],
            "checks": cell["checks"],
            "terminal_reason": session["terminal_reason"],
            "duration_seconds": session["duration_seconds"],
            "usage": session["usage"],
            "source_hash": cell["source_hash"],
            "fixture_commit": cell["fixture_commit"],
            "delivered_context": cell["delivered_context"],
            "pretool_invocations": len(pretool),
            "pretool_deliveries": len(delivered_pretool),
            "tool_events": len(session["tools"]),
            "full_patch_swift_files": covered,
            "launch_command": launch_command,
            "status": cell.get("status", "ok" if cell["success"] else "failed"),
            "error": cell.get("error"),
            "collection_error": cell.get("collection_error"),
            "session_errors": session.get("errors", []),
            "workspace_available": available,
        }
        rendered_metric = json.dumps(metric)
        for old, new in replacements.items():
            rendered_metric = rendered_metric.replace(old, new)
        metrics.append(json.loads(rendered_metric))
        all_context[cell["arm"]] += bool(cell["delivered_context"])
    dump(destination / "mapping.json", mapping)
    dump(
        destination / "metrics.json",
        {
            "method": run["method"],
            "model": run["model"],
            "reasoning": run["reasoning"],
            "codex_version": run["codex_version"],
            "swift_version": run["swift_version"],
            "planned_cells": 20,
            "prepared_cells": len(prepared),
            "status_counts": dict(Counter(cell["status"] for cell in metrics)),
            "cells": metrics,
        },
    )
    (bundle / "instructions.md").write_text("""# Independent Swift review

Review every labeled output on the same scale. The labels are opaque. Do not
infer configuration from them. The request is in each request.txt, and the
complete generated package and patch are in that label's directory.

For each label, assign 0 to 4 separately for correctness, maintainability,
consistency with current repository examples, and scope control. A 4 means no
material problem, 3 means a minor problem, 2 means a meaningful fix is needed,
1 means major problems, and 0 means missing or unusable work. Give concrete
source evidence and any uncertainty. Prioritize correctness over convention.

Look for protocol-based repository boundaries and constructor injection,
preservation of existing result/domain types, reuse of shared conversion and
collection helpers, and changes restricted to the requested feature and useful
support. A correct equivalent implementation may earn full correctness even
when it differs in convention. New tests are optional; do not reward verbosity
or punish their absence. Check shipping zero/invalid amounts, failure mapping,
blank inputs without API calls, unchanged identifiers, and pickup filtering,
first-eligible deduplication and deterministic sorting.

Read every output. Return one JSON object with a `samples` array containing
`label`, the four numeric dimensions, `evidence`, and `uncertainty`. Do not rank
an entire arm; you do not have the mapping. End with any systematic rubric
ambiguity or reviewer limitation. Do not edit any output.
""")
    lines = [
        "# Codex Swift generation results",
        "",
        "All 20 registered cells are included. No cell was retried.",
        "",
        "| Task | Arm | Cells | Behavior pass | DI / domain / helper proxies | Exact scope proxy | Context delivered |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for task in PROMPTS:
        for arm in ("A", "B"):
            cells = [cell for cell in metrics if cell["task"] == task and cell["arm"] == arm]
            structure = [
                sum(cell["checks"]["structure"][key] for cell in cells)
                for key in ("protocol_injection", "domain_types", "shared_conversion")
            ]
            lines.append(
                f"| {task} | {arm} | {len(cells)} | {sum(cell['success'] for cell in cells)}/5 | {' / '.join(map(str, structure))} of 5 each | {sum(cell['checks']['structure']['scope_preserved'] for cell in cells)}/5 | {sum(cell['delivered_context'] for cell in cells)}/5 |"
            )
    lines += [
        "",
        "A is unaided. B uses the native SwiftChameleon context adapter.",
        "",
        "The exact scope proxy flags any pre-existing Swift file change outside composition, including a useful Package.swift test-target addition. It is not a semantic scope score and is reported separately. Independent review can disagree with it.",
        "",
        "The exact requested model is gpt-6-astra with medium reasoning. The Codex JSON stream does not expose resolved model/provider fields. Authentication uses the ChatGPT subscription. Token usage is recorded; dollar spend is unavailable.",
        "",
        "These two small tasks and ten paired runs do not establish general Swift quality. Independent blinded review is recorded separately. Raw transcripts and hook deliveries accompany every output. Candidate-created tests are preserved, but only the held external executable checks determine the behavior column.",
    ]
    (destination / "run.md").write_text("\n".join(lines) + "\n")
    return {
        "published": str(destination),
        "cells": len(metrics),
        "success": sum(cell["success"] for cell in metrics),
        "context": dict(all_context),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    print(json.dumps(publish(args.run_dir, args.destination)))


if __name__ == "__main__":
    main()
