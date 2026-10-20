"""Bounded Swift repository detection for SPM, Tuist and Xcode."""

from __future__ import annotations

import os
from pathlib import Path

from chameleon_mcp._thresholds import threshold_int
from chameleon_mcp.extractors._base import ExtractorUnavailableError, ParseResult

_MANIFESTS = frozenset({"Package.swift", "Project.swift", "Workspace.swift", "Tuist.swift"})
_MARKER_MAX_DEPTH = 4


def _scan(repo_root: Path, *, first_only: bool) -> tuple[bool, int]:
    from chameleon_mcp.bootstrap.discovery import EXCLUDE_FROM_CLUSTERING_DIRS

    excluded = EXCLUDE_FROM_CLUSTERING_DIRS | {".build", ".swiftpm", "Pods", "Carthage"}
    marker = False
    count = 0
    visited = 0
    cap = threshold_int("SPEC_MARKER_GLOB_CAP")
    pending = [(repo_root, 0)]
    while pending:
        directory, depth = pending.pop()
        with os.scandir(directory) as entries:
            for entry in entries:
                visited += 1
                if visited > cap:
                    return marker, count
                if entry.is_symlink():
                    continue
                path = Path(entry.path)
                if entry.is_dir(follow_symlinks=False):
                    if entry.name not in excluded:
                        pending.append((path, depth + 1))
                    continue
                if not entry.is_file(follow_symlinks=False):
                    continue
                if depth <= _MARKER_MAX_DEPTH and (
                    entry.name in _MANIFESTS
                    or (entry.name == "project.pbxproj" and directory.suffix == ".xcodeproj")
                ):
                    marker = True
                if path.suffix.lower() == ".swift" and entry.name not in _MANIFESTS:
                    count += 1
                if first_only and marker and count:
                    return marker, count
    return marker, count


def source_count(repo_root: Path) -> int:
    return _scan(repo_root, first_only=False)[1]


class SwiftExtractor:
    """Detect Swift; parsing requires the pinned in-process grammar."""

    language = "swift"

    def can_handle(self, repo_root: Path) -> bool:
        try:
            marker, count = _scan(repo_root, first_only=True)
            return marker and count > 0
        except OSError:
            return False

    def parse_repo(
        self,
        repo_root: Path,
        glob: str = "**/*",
        limit: int | None = None,
        paths: list[Path] | None = None,
    ) -> ParseResult:
        raise ExtractorUnavailableError(
            "Swift requires the in-process tree-sitter backend; "
            "no dump-script fallback exists (grammar unavailable or CHAMELEON_TREE_SITTER=0)"
        )
