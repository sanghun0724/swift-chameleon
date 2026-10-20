from __future__ import annotations

import os
import subprocess
import sys
import time
from dataclasses import replace

import pytest

from chameleon_mcp.bootstrap import canonical, swift_history
from chameleon_mcp.bootstrap.clustering import cluster_files
from chameleon_mcp.bootstrap.swift_history import HistoryLimits, swift_history_ages
from chameleon_mcp.extractors._base import ParsedFile
from chameleon_mcp.extractors.treesitter import grammars

OLD = 1_600_000_000
RECENT = OLD + 400 * 86400
NOW = RECENT + 86400


def git(root, *args, at=OLD):
    return subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=True,
        env={**os.environ, "GIT_AUTHOR_DATE": f"{at} +0000", "GIT_COMMITTER_DATE": f"{at} +0000"},
    ).stdout


@pytest.fixture
def repo(tmp_path):
    git(tmp_path, "init", "-q")
    git(tmp_path, "config", "user.email", "test@example.com")
    git(tmp_path, "config", "user.name", "Test")
    return tmp_path


def commit(repo, at=OLD):
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "fixture", at=at)


def write(repo, name, content="struct Witness { func value() -> Int { 1 } }\n"):
    path = repo / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return path


def age(repo, path, **kwargs):
    return swift_history_ages(repo, [path], **kwargs)[path]


def selected(repo, names, *, now=NOW):
    files = [
        ParsedFile(
            path=repo / name,
            content_first_200_bytes="",
            top_level_node_kinds=("SwiftStructDeclaration",),
            default_export_kind=None,
            named_export_count=1,
            import_specifiers=(),
            has_jsx=False,
        )
        for name in names
    ]
    clusters = cluster_files(files, repo, min_cluster_size=2).clusters
    result = canonical.select_canonicals(clusters, repo, now=now)
    return {s.witness_path.name for s in result.selections.values()}, result


def test_formatting_and_line_wrapping_do_not_renew_age(repo):
    write(repo, "a.swift")
    commit(repo)
    write(repo, "z.swift", "struct Recent { func value() -> Int { 2 } }\n")
    commit(repo, RECENT)
    write(repo, "a.swift", "struct Witness {\n\n    func value() -> Int {\n        1\n    }\n}\n")
    commit(repo, RECENT + 100)
    assert age(repo, "a.swift").epoch == OLD
    witnesses, result = selected(repo, ["a.swift", "z.swift"])
    assert witnesses == {"z.swift"}
    assert result.swift_history["a.swift"].reason == "git-substantive"


@pytest.mark.parametrize("rename_change", [False, True])
def test_rename_follows_old_age_and_rename_with_change_renews(repo, rename_change):
    write(repo, "old.swift")
    commit(repo)
    git(repo, "mv", "old.swift", "new.swift")
    if rename_change:
        write(repo, "new.swift", "struct Witness { func value() -> Int { 2 } }\n")
    commit(repo, RECENT)
    assert age(repo, "new.swift").epoch == (RECENT if rename_change else OLD)


@pytest.mark.parametrize(
    "before,after",
    [
        ('struct A { let x = "a b" }\n', 'struct A { let x = "ab" }\n'),
        ("struct A {} // first\n", "struct A {} // second\n"),
        ("struct A {} // first\n", "struct A {} // fi rst\n"),
        ("struct First {}\n", "struct Second {}\n"),
    ],
)
def test_string_contents_comments_and_identifier_changes_are_substantive(repo, before, after):
    write(repo, "a.swift", before)
    commit(repo)
    write(repo, "a.swift", after)
    commit(repo, RECENT)
    assert age(repo, "a.swift").epoch == RECENT


@pytest.mark.parametrize("name", ["a space.swift", "café 한글.swift", "commit 123\n:thing.swift"])
def test_legal_filename_delimiters_and_subroot(repo, name):
    write(repo, "workspace/" + name)
    commit(repo)
    write(repo, "workspace/" + name, "struct Witness {\n  func value() -> Int { 1 }\n}\n")
    commit(repo, RECENT)
    assert age(repo / "workspace", name).epoch == OLD


def test_same_commit_and_clock_ties_are_deterministic(repo):
    write(repo, "a.swift")
    write(repo, "z.swift")
    commit(repo)
    assert selected(repo, ["z.swift", "a.swift"])[0] == {"a.swift"}
    assert selected(repo, ["a.swift", "z.swift"])[0] == {"a.swift"}


def test_latest_is_traversal_order_not_maximum_epoch(repo):
    write(repo, "a.swift")
    commit(repo, RECENT)
    write(repo, "a.swift", "struct Changed {}\n")
    commit(repo, OLD)
    assert age(repo, "a.swift").epoch == OLD


def test_shallow_boundary_unknown_does_not_promote_clone_mtime(repo, tmp_path_factory):
    write(repo, "a.swift")
    commit(repo)
    write(repo, "a.swift", "struct Witness {\n func value() -> Int { 1 }\n}\n")
    write(repo, "z.swift", "struct Recent {}\n")
    commit(repo, RECENT)
    clone = tmp_path_factory.mktemp("clone") / "checkout"
    git(repo, "clone", "-q", "--depth=1", repo.as_uri(), str(clone))
    # Both boundary additions have unknown age, independent of fresh clone mtime.
    assert age(clone, "a.swift").reason == "shallow-history"
    assert age(clone, "a.swift").epoch is None
    _, result = selected(clone, ["a.swift", "z.swift"], now=time.time() + 1)
    assert all(a.reason == "shallow-history" for a in result.swift_history.values())


def test_known_change_above_shallow_boundary_is_usable(repo, tmp_path_factory):
    write(repo, "a.swift")
    commit(repo)
    write(repo, "a.swift", "struct Changed {}\n")
    commit(repo, RECENT)
    git(repo, "commit", "--allow-empty", "-qm", "empty", at=RECENT + 10)
    clone = tmp_path_factory.mktemp("clone") / "checkout"
    git(repo, "clone", "-q", "--depth=2", repo.as_uri(), str(clone))
    # The actual change is the shallow boundary and cannot prove its parent.
    assert age(clone, "a.swift").reason == "shallow-history"
    write(clone, "a.swift", "struct ChangedAgain {}\n")
    git(clone, "config", "user.email", "test@example.com")
    git(clone, "config", "user.name", "Test")
    commit(clone, RECENT + 20)
    assert age(clone, "a.swift").epoch == RECENT + 20


def test_non_git_untracked_and_disabled_have_explicit_legacy_fallback(
    repo, tmp_path_factory, monkeypatch
):
    plain = tmp_path_factory.mktemp("plain")
    write(plain, "a.swift")
    assert age(plain, "a.swift").reason == "non-git"
    write(repo, "tracked.swift")
    commit(repo)
    write(repo, "a.swift")
    assert age(repo, "a.swift").reason == "untracked"
    monkeypatch.setenv("CHAMELEON_CANONICAL_GIT_RECENCY", "0")
    assert age(repo, "tracked.swift").reason == "disabled"


@pytest.mark.parametrize(
    "limit,reason",
    [
        ({"commits": 0}, "commit-limit"),
        ({"files": 0}, "file-limit"),
        ({"output_bytes": 1}, "output-limit"),
        ({"seconds": 0}, "timeout"),
        ({"blob_bytes": 1}, "blob-limit"),
        ({"nodes": 1}, "node-limit"),
    ],
)
def test_history_limits_are_explicit(repo, limit, reason):
    write(repo, "a.swift")
    commit(repo)
    write(repo, "a.swift", "struct Changed {}\n")
    commit(repo, RECENT)
    assert age(repo, "a.swift", limits=replace(HistoryLimits(), **limit)).reason == reason


def test_total_commit_budget_shared_across_candidates(repo):
    write(repo, "a.swift")
    write(repo, "z.swift")
    commit(repo)
    ages = swift_history_ages(repo, ["a.swift", "z.swift"], limits=HistoryLimits(commits=1))
    assert ages["a.swift"].epoch == OLD
    assert ages["z.swift"].reason == "commit-limit"


def test_unknown_tracked_age_does_not_use_mtime(repo, monkeypatch):
    write(repo, "a.swift")
    write(repo, "z.swift")
    commit(repo)
    monkeypatch.setattr(
        canonical,
        "swift_history_ages",
        lambda root, paths: {
            "a.swift": swift_history.HistoryAge(None, "timeout"),
            "z.swift": swift_history.HistoryAge(OLD, "git-substantive"),
        },
    )
    assert selected(repo, ["a.swift", "z.swift"], now=time.time() + 1)[0] == {"z.swift"}


def test_running_subprocess_is_killed_at_shared_deadline(tmp_path, monkeypatch):
    original = subprocess.Popen
    monkeypatch.setattr(
        swift_history.subprocess,
        "Popen",
        lambda *args, **kwargs: original(
            [sys.executable, "-c", "import time; time.sleep(30)"], **kwargs
        ),
    )
    budget = swift_history._Budget(HistoryLimits(seconds=0.1))
    with pytest.raises(swift_history._Unavailable, match="timeout"):
        budget.git(tmp_path, "ignored")
    with pytest.raises(swift_history._Unavailable, match="timeout"):
        budget.git(tmp_path, "ignored")


def test_streaming_output_cap_stops_unbounded_producer(tmp_path, monkeypatch):
    original = subprocess.Popen
    monkeypatch.setattr(
        swift_history.subprocess,
        "Popen",
        lambda *args, **kwargs: original(
            [sys.executable, "-c", "import os\nwhile True: os.write(1, b'x' * 8192)"], **kwargs
        ),
    )
    budget = swift_history._Budget(HistoryLimits(output_bytes=1000))
    with pytest.raises(swift_history._Unavailable, match="output-limit"):
        budget.git(tmp_path, "ignored")


def test_merge_resolution_delta_is_substantive(repo):
    write(repo, "a.swift", "struct Initial {}\n")
    commit(repo)
    git(repo, "checkout", "-qb", "feature")
    write(repo, "a.swift", "struct Feature {}\n")
    commit(repo, OLD + 10)
    git(repo, "checkout", "-q", "-")
    write(repo, "a.swift", "struct Main {}\n")
    commit(repo, OLD + 20)
    subprocess.run(["git", "-C", str(repo), "merge", "--no-commit", "feature"], capture_output=True)
    write(repo, "a.swift", "struct Resolution {}\n")
    commit(repo, RECENT)
    assert age(repo, "a.swift").epoch == RECENT


def test_empty_merge_does_not_renew_age(repo):
    write(repo, "a.swift")
    commit(repo)
    git(repo, "checkout", "-qb", "feature")
    write(repo, "other.txt", "unrelated")
    commit(repo, OLD + 10)
    git(repo, "checkout", "-q", "-")
    git(repo, "merge", "--no-ff", "-qm", "merge", "feature", at=RECENT)
    assert age(repo, "a.swift").epoch == OLD


def test_malformed_historical_source_has_no_invented_timestamp(repo):
    write(repo, "a.swift", "struct Broken {")
    commit(repo)
    write(repo, "a.swift", "struct Fixed {}\n")
    commit(repo, RECENT)
    assert age(repo, "a.swift").reason == "malformed-history"


def test_missing_grammar_has_explicit_unknown_age(repo, monkeypatch):
    write(repo, "a.swift")
    commit(repo)
    write(repo, "a.swift", "struct Changed {}\n")
    commit(repo, RECENT)
    monkeypatch.delitem(grammars._EXTENSION_GRAMMARS, ".swift")
    assert age(repo, "a.swift").reason == "grammar-unavailable"


def test_real_tracked_log_failure_does_not_become_non_git_fallback(repo, monkeypatch):
    write(repo, "a.swift")
    commit(repo)
    original = swift_history._Budget.git

    def fail_log(self, root, *args):
        if args[0] == "log":
            raise swift_history._Unavailable("git-unavailable")
        return original(self, root, *args)

    monkeypatch.setattr(swift_history._Budget, "git", fail_log)
    assert age(repo, "a.swift").reason == "git-unavailable"


def test_bounded_shortlist_prioritizes_recent_candidate_beyond_lexical_cap(repo):
    names = [f"a{i:03}.swift" for i in range(130)]
    for name in names:
        write(repo, name)
    commit(repo)
    write(repo, "z_recent.swift", "struct Recent {}\n")
    commit(repo, RECENT)
    ages = swift_history_ages(repo, names + ["z_recent.swift"])
    assert ages["z_recent.swift"].epoch == RECENT
    assert ages["a129.swift"].reason == "file-limit"
    assert sum(a.epoch is not None for a in ages.values()) == 128
    assert selected(repo, names + ["z_recent.swift"])[0] == {"z_recent.swift"}


def test_small_requested_batch_preserves_priority_order(repo):
    write(repo, "a.swift")
    write(repo, "z.swift")
    commit(repo)
    ages = swift_history_ages(repo, ["z.swift", "a.swift"], limits=HistoryLimits(commits=1))
    assert ages["z.swift"].epoch == OLD
    assert ages["a.swift"].reason == "commit-limit"


def test_binary_delta_is_substantive_without_interpreting_bytes(repo):
    (repo / "a.swift").write_bytes(b"first\x00payload")
    commit(repo)
    (repo / "a.swift").write_bytes(b"second\x00payload")
    commit(repo, RECENT)
    assert age(repo, "a.swift").epoch == RECENT
