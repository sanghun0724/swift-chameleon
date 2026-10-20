"""Bounded Swift witness ages, following renames and ignoring formatting trivia.

The first substantive delta in Git traversal order supplies its commit time.
Comments and string contents remain exact bytes. This is token comparison, not
semantic normalization. Unknown ages never receive a filesystem-mtime boost.
Pure renames retain age. A rename combined with formatting depends on Git's
rename similarity heuristic and can appear as a new addition when it fails.
Only a bounded shortlist is refined. When the file cap applies, a bounded raw
history pass prioritizes recent path touches. Unvisited candidates report
file-limit and receive no recency boost.
"""

from __future__ import annotations

import os
import selectors
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from chameleon_mcp._thresholds import threshold_int


@dataclass(frozen=True)
class HistoryAge:
    epoch: int | None
    reason: str


@dataclass(frozen=True)
class HistoryLimits:
    seconds: float = 20
    output_bytes: int = 8_000_000
    files: int = 128
    commits: int = 512
    blob_bytes: int = 1_000_000
    nodes: int = 100_000


class _Unavailable(Exception):
    pass


class _Budget:
    def __init__(self, limits: HistoryLimits):
        self.deadline = time.monotonic() + limits.seconds
        self.remaining_bytes = limits.output_bytes
        self.remaining_commits = limits.commits
        self.remaining_nodes = limits.nodes

    def remaining(self) -> float:
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise _Unavailable("timeout")
        return remaining

    def git(self, root: Path, *args: str) -> bytes:
        self.remaining()
        if self.remaining_bytes <= 0:
            raise _Unavailable("output-limit")
        try:
            with subprocess.Popen(
                [
                    "git",
                    "--no-optional-locks",
                    "-c",
                    "core.fsmonitor=false",
                    "-c",
                    "log.showSignature=false",
                    "-C",
                    str(root),
                    *args,
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                env={
                    **os.environ,
                    "GIT_NO_REPLACE_OBJECTS": "1",
                    "GIT_TERMINAL_PROMPT": "0",
                    "GIT_NO_LAZY_FETCH": "1",
                },
            ) as proc:
                try:
                    chunks = []
                    with selectors.DefaultSelector() as selector:
                        selector.register(proc.stdout, selectors.EVENT_READ)
                        while selector.get_map():
                            if not selector.select(self.remaining()):
                                raise _Unavailable("timeout")
                            chunk = os.read(
                                proc.stdout.fileno(), min(65_536, self.remaining_bytes + 1)
                            )
                            self.remaining_bytes -= len(chunk)
                            if self.remaining_bytes < 0:
                                raise _Unavailable("output-limit")
                            if chunk:
                                chunks.append(chunk)
                            else:
                                selector.unregister(proc.stdout)
                    if proc.wait(timeout=self.remaining()) != 0:
                        raise _Unavailable("git-unavailable")
                    return b"".join(chunks)
                finally:
                    if proc.poll() is None:
                        proc.kill()
                        proc.wait()
        except subprocess.TimeoutExpired as exc:
            raise _Unavailable("timeout") from exc
        except (OSError, ValueError) as exc:
            raise _Unavailable("git-error") from exc


def _fingerprint(content: bytes, budget: _Budget, limits: HistoryLimits) -> tuple:
    if len(content) > limits.blob_bytes:
        raise _Unavailable("blob-limit")
    if b"\0" in content:
        return ("binary", content)
    try:
        from tree_sitter import Parser

        from chameleon_mcp.extractors.treesitter.grammars import grammar_for_path

        parser = Parser(grammar_for_path("witness.swift"))
        if hasattr(parser, "timeout_micros"):
            parser.timeout_micros = max(1, int(budget.remaining() * 1_000_000))
        tree = parser.parse(content)
    except _Unavailable:
        raise
    except Exception as exc:
        raise _Unavailable("grammar-unavailable") from exc
    budget.remaining()
    if tree is None:
        raise _Unavailable("parse-timeout")
    if tree.root_node.has_error:
        raise _Unavailable("malformed-history")
    tokens = []
    stack = [tree.root_node]
    while stack:
        budget.remaining()
        node = stack.pop()
        budget.remaining_nodes -= 1
        if budget.remaining_nodes < 0:
            raise _Unavailable("node-limit")
        if not node.child_count or "comment" in node.type or "string" in node.type:
            tokens.append((node.type, content[node.start_byte : node.end_byte]))
        else:
            stack.extend(reversed(node.children))
    return tuple(tokens)


def _changes(raw: bytes):
    """Read raw NUL records without interpreting filenames as header markers."""
    fields = raw.split(b"\0")
    epoch = None
    parents = False
    i = 0
    while i < len(fields):
        field = fields[i].lstrip(b"\n")
        i += 1
        if field.startswith(b"commit "):
            header = field.split()
            epoch = int(header[1])
            parents = len(header) > 2
        elif field.startswith(b":"):
            entry = field.split()
            if len(entry) != 5 or epoch is None:
                raise _Unavailable("invalid-history")
            old, new, status = entry[2:]
            path_count = 2 if status[:1] in (b"R", b"C") else 1
            path = os.fsdecode(fields[i + path_count - 1])
            i += path_count
            yield epoch, parents, old.decode("ascii"), new.decode("ascii"), path


def swift_history_ages(
    repo_root: Path,
    paths: list[str],
    *,
    limits: HistoryLimits | None = None,
) -> dict[str, HistoryAge]:
    """Return ages and explicit fallback reasons under one shared work budget.

    Non-Git, untracked and disabled paths retain the legacy mtime policy at the
    caller. Every other unknown is conservative. Both log output and retrieved
    historical blobs count against the same byte cap. History is defined
    by an explicit first-parent walk. Merge resolution deltas against the first
    parent count. The latest traversal delta wins even when epochs are not monotonic.
    """
    paths = list(dict.fromkeys(paths))
    if os.environ.get("CHAMELEON_CANONICAL_GIT_RECENCY") == "0":
        return dict.fromkeys(paths, HistoryAge(None, "disabled"))
    limits = limits or HistoryLimits(seconds=threshold_int("CANONICAL_GIT_LOG_TIMEOUT_SECONDS"))
    result = dict.fromkeys(paths, HistoryAge(None, "file-limit"))
    if not paths or limits.files == 0:
        return result
    budget = _Budget(limits)
    try:
        budget.git(repo_root, "rev-parse", "--show-toplevel")
    except _Unavailable as exc:
        return dict.fromkeys(
            paths, HistoryAge(None, "non-git" if str(exc) == "git-unavailable" else str(exc))
        )
    try:
        shallow = budget.git(repo_root, "rev-parse", "--is-shallow-repository").strip() == b"true"
        tracked = {
            os.fsdecode(p)
            for p in budget.git(repo_root, "ls-files", "-z", "--", ":(icase,glob)**/*.swift").split(
                b"\0"
            )
            if p
        }
        for path in paths:
            if path not in tracked:
                result[path] = HistoryAge(None, "untracked")
        candidates = [path for path in paths if path in tracked]
        if len(candidates) > limits.files:
            raw = budget.git(
                repo_root,
                "log",
                "--raw",
                "-z",
                "--no-renames",
                "--relative",
                "--no-ext-diff",
                "--no-textconv",
                "--first-parent",
                "--diff-merges=first-parent",
                "--format=commit %ct %P",
                f"--max-count={limits.commits}",
                "--",
                ":(icase,glob)**/*.swift",
            )
            touches = {}
            for epoch, _parents, _old, _new, path in _changes(raw):
                budget.remaining()
                touches.setdefault(path, epoch)
            candidates.sort(key=lambda path: (-touches.get(path, 0), path))
        candidates = candidates[: limits.files]
        fingerprints: dict[str, tuple] = {}

        def fingerprint(oid: str) -> tuple:
            if oid not in fingerprints:
                fingerprints[oid] = _fingerprint(
                    budget.git(repo_root, "cat-file", "blob", oid), budget, limits
                )
            return fingerprints[oid]

        for path in candidates:
            try:
                if budget.remaining_commits <= 0:
                    raise _Unavailable("commit-limit")
                raw = budget.git(
                    repo_root,
                    "log",
                    "--follow",
                    "--raw",
                    "-z",
                    "--no-abbrev",
                    "--no-ext-diff",
                    "--no-textconv",
                    "--first-parent",
                    "--diff-merges=first-parent",
                    "--format=commit %ct %P",
                    f"--max-count={budget.remaining_commits + 1}",
                    "--",
                    f":(literal){path}",
                )
                result[path] = HistoryAge(None, "shallow-history" if shallow else "no-history")
                for epoch, parents, old, new, _path in _changes(raw):
                    budget.remaining_commits -= 1
                    if budget.remaining_commits < 0:
                        raise _Unavailable("commit-limit")
                    if old == new:
                        continue
                    if not old.strip("0"):
                        if shallow and not parents:
                            raise _Unavailable("shallow-history")
                        result[path] = HistoryAge(epoch, "git-substantive")
                        break
                    if not new.strip("0"):
                        continue
                    if fingerprint(old) != fingerprint(new):
                        result[path] = HistoryAge(epoch, "git-substantive")
                        break
            except _Unavailable as exc:
                result[path] = HistoryAge(None, str(exc))
    except _Unavailable as exc:
        for path in paths:
            if result[path].reason == "file-limit":
                result[path] = HistoryAge(None, str(exc))
    return result
