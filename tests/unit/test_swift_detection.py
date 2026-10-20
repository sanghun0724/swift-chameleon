from __future__ import annotations

from pathlib import Path

import pytest

from chameleon_mcp.bootstrap.discovery import discover_files, discovery_stats
from chameleon_mcp.extractors._base import ExtractorUnavailableError
from chameleon_mcp.extractors.registry import select_extractor
from chameleon_mcp.extractors.spec_driven import SpecDrivenExtractor
from chameleon_mcp.extractors.swift import SwiftExtractor
from chameleon_mcp.language_support import capabilities_for, describe
from chameleon_mcp.lint_engine import detect_language, security_language


def _write(root: Path, relative: str, text: str = "") -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


@pytest.mark.parametrize(
    "marker",
    [
        "Package.swift",
        "Project.swift",
        "Modules/Feature/Project.swift",
        "App.xcodeproj/project.pbxproj",
        "Apps/Mobile/App.xcodeproj/project.pbxproj",
    ],
)
def test_marker_and_real_source_select_swift(tmp_path, marker):
    _write(tmp_path, marker)
    source = _write(tmp_path, "Sources/Model.swift", "struct Model {}")
    assert SwiftExtractor().can_handle(tmp_path)
    selected = select_extractor(tmp_path)
    assert selected is not None and selected.language == "swift"
    parsed = selected.parse_repo(tmp_path, paths=[source])
    assert len(parsed.files) == 1
    assert parsed.files[0].top_level_node_kinds == ("SwiftStructDeclaration",)


@pytest.mark.parametrize(
    "marker", ["Package.swift", "Project.swift", "App.xcodeproj/project.pbxproj"]
)
def test_manifests_alone_are_not_swift_application_source(tmp_path, marker):
    _write(tmp_path, marker)
    assert not SwiftExtractor().can_handle(tmp_path)


@pytest.mark.parametrize(
    "directory",
    ["vendor", ".build", "Tuist/.build", ".swiftpm", "Pods", "Carthage", "node_modules"],
)
def test_vendored_source_does_not_claim_a_repository(tmp_path, directory):
    _write(tmp_path, "Package.swift")
    _write(tmp_path, f"{directory}/Library.swift", "struct Library {}")
    assert not SwiftExtractor().can_handle(tmp_path)


def test_unmarked_swift_and_helpers_do_not_claim_python(tmp_path):
    _write(tmp_path, "vendor/Library.swift", "struct Library {}")
    _write(tmp_path, "pyproject.toml", "[project]\nname = 'python'\n")
    _write(tmp_path, "service.py", "def run(): pass")
    selected = select_extractor(tmp_path)
    assert selected is not None and selected.language == "python"


def test_swift_source_beats_python_helpers_with_manifests(tmp_path):
    _write(tmp_path, "Package.swift")
    for index in range(3):
        _write(tmp_path, f"Sources/S{index}.swift", f"struct S{index} {{}}")
    _write(tmp_path, "requirements.txt")
    _write(tmp_path, "scripts/build.py", "pass")
    assert select_extractor(tmp_path).language == "swift"


def test_python_manifest_and_larger_corpus_outrank_swift(tmp_path):
    _write(tmp_path, "Package.swift")
    _write(tmp_path, "Sources/Bridge.swift", "struct Bridge {}")
    _write(tmp_path, "pyproject.toml", "[project]\nname = 'python'\n")
    for index in range(3):
        _write(tmp_path, f"service/s{index}.py", "pass")
    assert select_extractor(tmp_path).language == "python"


def test_typescript_precedence_is_preserved(tmp_path):
    _write(tmp_path, "Package.swift")
    _write(tmp_path, "Sources/App.swift", "struct App {}")
    _write(tmp_path, "tsconfig.json", "{}")
    _write(tmp_path, "package.json", '{"devDependencies":{"typescript":"^5"}}')
    _write(tmp_path, "src/app.ts", "export const app = 1")
    assert select_extractor(tmp_path).language == "typescript"


def test_swift_is_detected_as_a_secondary_language(tmp_path):
    _write(tmp_path, "App.xcodeproj/project.pbxproj")
    _write(tmp_path, "Sources/App.swift", "struct App {}")
    assert "swift" in SpecDrivenExtractor.languages_present(tmp_path)
    assert "swift" not in SpecDrivenExtractor.languages_present(tmp_path, exclude="swift")


def test_marker_depth_and_entry_budget_are_bounded(tmp_path, monkeypatch):
    _write(tmp_path, "a/b/c/d/e/Project.swift")
    _write(tmp_path, "Sources/App.swift", "struct App {}")
    assert not SwiftExtractor().can_handle(tmp_path)
    _write(tmp_path, "Package.swift")
    monkeypatch.setenv("CHAMELEON_SPEC_MARKER_GLOB_CAP", "1")
    assert not SwiftExtractor().can_handle(tmp_path)


def test_directory_and_source_symlinks_do_not_claim_external_code(tmp_path):
    outside = tmp_path / "outside"
    _write(outside, "External.swift", "struct External {}")
    repo = tmp_path / "repo"
    _write(repo, "Package.swift")
    (repo / "Sources").symlink_to(outside, target_is_directory=True)
    (repo / "External.swift").symlink_to(outside / "External.swift")
    assert not SwiftExtractor().can_handle(repo)


def test_discovery_excludes_manifests_and_generated_checkouts(tmp_path):
    wanted = _write(tmp_path, "Sources/Actual.swift", "struct Actual {}")
    for path in (
        "Package.swift",
        "Project.swift",
        "Workspace.swift",
        "Tuist.swift",
        "Modules/Project.swift",
        "Tuist/.build/Checkout.swift",
        ".swiftpm/Source.swift",
        "Pods/Pod.swift",
        "Carthage/Library.swift",
    ):
        _write(tmp_path, path, "struct BuildConfiguration {}")
    assert discover_files(tmp_path, glob="**/*.swift") == [wanted]
    assert discovery_stats(tmp_path, glob="**/*.swift") == {
        "pre_exclusion": 10,
        "post_exclusion": 1,
    }


def test_disabled_tree_sitter_reports_unavailable_instead_of_an_empty_profile(
    tmp_path, monkeypatch
):
    _write(tmp_path, "Package.swift")
    _write(tmp_path, "Sources/App.swift", "struct App {}")
    monkeypatch.setenv("CHAMELEON_TREE_SITTER", "0")
    selected = select_extractor(tmp_path)
    assert selected is not None and selected.language == "swift"
    with pytest.raises(ExtractorUnavailableError, match="no dump-script fallback"):
        selected.parse_repo(tmp_path)


def test_swift_capabilities_and_security_are_explicit_without_lint():
    caps = capabilities_for("swift")
    assert caps is not None
    assert caps.tier == "extraction"
    assert caps.archetypes and caps.signatures and caps.imports and caps.conventions
    assert caps.security_lint
    assert not caps.lint_rules and not caps.cross_file_index and not caps.graded_call_edges
    assert "call edges (including same-file overload resolution)" in describe("swift")
    assert detect_language("Sources/App.swift") is None
    assert security_language("Sources/App.SWIFT") == "swift"
    assert security_language("README.md") is None
