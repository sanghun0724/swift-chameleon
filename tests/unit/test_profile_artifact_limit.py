from __future__ import annotations

import json
from pathlib import Path

import pytest

from chameleon_mcp import safe_open, tools
from chameleon_mcp.profile.loader import (
    ProfileLoadError,
    clear_profile_cache,
    load_profile_dir,
)
from chameleon_mcp.profile.trust import (
    hash_profile,
    is_material_change,
    trust_state_for,
)
from chameleon_mcp.safe_open import (
    FileTooLargeError,
    UnsafeFileError,
    profile_artifact_max_bytes,
    safe_read_profile_artifact,
    safe_read_profile_artifact_bytes,
)

MIB = 1024 * 1024
LIMIT_ENV = "CHAMELEON_PROFILE_ARTIFACT_MAX_BYTES"


@pytest.mark.parametrize("reader", [safe_read_profile_artifact, safe_read_profile_artifact_bytes])
def test_default_and_opt_in_limits_are_enforced(tmp_path: Path, monkeypatch, reader):
    path = tmp_path / "profile.json"
    monkeypatch.delenv(LIMIT_ENV, raising=False)
    path.write_bytes(b"x" * (5 * MIB))
    assert len(reader(path)) == 5 * MIB
    with path.open("ab") as stream:
        stream.write(b"x")
    with pytest.raises(FileTooLargeError):
        reader(path)

    monkeypatch.setenv(LIMIT_ENV, str(10 * MIB))
    with path.open("wb") as stream:
        stream.truncate(10 * MIB)
    assert len(reader(path)) == 10 * MIB
    with path.open("ab") as stream:
        stream.write(b"x")
    with pytest.raises(FileTooLargeError):
        reader(path)


@pytest.mark.parametrize("reader", [safe_read_profile_artifact, safe_read_profile_artifact_bytes])
def test_opt_in_hard_maximum_is_bounded(tmp_path: Path, monkeypatch, reader):
    path = tmp_path / "profile.json"
    monkeypatch.setenv(LIMIT_ENV, str(24 * MIB))
    with path.open("wb") as stream:
        stream.truncate(24 * MIB)
    assert len(reader(path)) == 24 * MIB
    with path.open("ab") as stream:
        stream.write(b"x")
    with pytest.raises(FileTooLargeError):
        reader(path)


@pytest.mark.parametrize(
    "value",
    ["", "0", "-1", "+6000000", "5.5", " 6000000", "25165825", "9" * 1000, "１２"],
)
def test_invalid_limit_uses_default(monkeypatch, value):
    monkeypatch.setenv(LIMIT_ENV, value)
    assert profile_artifact_max_bytes() == 5 * MIB


@pytest.mark.parametrize("reader", [safe_read_profile_artifact, safe_read_profile_artifact_bytes])
def test_explicit_limit_takes_precedence(tmp_path: Path, monkeypatch, reader):
    path = tmp_path / "profile.json"
    path.write_bytes(b"abcd")
    monkeypatch.setenv(LIMIT_ENV, str(24 * MIB))
    with pytest.raises(FileTooLargeError):
        reader(path, max_bytes=3)
    assert len(reader(path, max_bytes=4)) == 4
    monkeypatch.setenv(LIMIT_ENV, "1")
    assert len(reader(path, max_bytes=4)) == 4
    with pytest.raises(FileTooLargeError):
        reader(path)


def test_text_reader_keeps_universal_newline_behavior(tmp_path: Path):
    path = tmp_path / "profile.txt"
    path.write_bytes(b"a\r\nb\rc\n")
    assert safe_read_profile_artifact(path) == "a\nb\nc\n"
    assert safe_read_profile_artifact_bytes(path) == b"a\r\nb\rc\n"


@pytest.mark.parametrize("reader", [safe_read_profile_artifact, safe_read_profile_artifact_bytes])
def test_opt_in_does_not_allow_symlinks(tmp_path: Path, monkeypatch, reader):
    target = tmp_path / "target.json"
    target.write_text("{}")
    link = tmp_path / "link.json"
    link.symlink_to(target)
    monkeypatch.setenv(LIMIT_ENV, str(24 * MIB))
    with pytest.raises(UnsafeFileError):
        reader(link)


@pytest.mark.parametrize("reader", [safe_read_profile_artifact, safe_read_profile_artifact_bytes])
def test_growth_after_open_cannot_bypass_limit(tmp_path: Path, monkeypatch, reader):
    path = tmp_path / "profile.json"
    path.write_bytes(b"ab")
    original = safe_open._open_profile_artifact_fd

    def open_then_grow(file_path, max_bytes):
        fd, st = original(file_path, max_bytes)
        with file_path.open("ab") as stream:
            stream.write(b"cde")
        return fd, st

    monkeypatch.setattr(safe_open, "_open_profile_artifact_fd", open_then_grow)
    with pytest.raises(FileTooLargeError):
        reader(path, max_bytes=4)


def test_large_profile_load_and_trust_hash_use_same_limit(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("CHAMELEON_PLUGIN_DATA", str(tmp_path / "plugin-data"))
    monkeypatch.setenv("CHAMELEON_TRUST_REVALIDATE", "1")
    monkeypatch.setenv("CHAMELEON_ALLOW_TMP_REPO", "1")
    monkeypatch.delenv(LIMIT_ENV, raising=False)
    profile = tmp_path / "repo" / ".chameleon"
    profile.mkdir(parents=True)
    artifacts = {
        "profile.json": {"generation": 1, "language": "swift", "schema_version": 1},
        "archetypes.json": {"generation": 1, "archetypes": {}},
        "rules.json": {"generation": 1, "rules": []},
        "canonicals.json": {
            "generation": 1,
            "canonicals": {},
            "padding": "x" * (6 * MIB),
        },
    }
    for name, value in artifacts.items():
        (profile / name).write_text(json.dumps(value))
    (profile / "COMMITTED").touch()
    signatures = profile / "symbol_signatures.json"
    signatures.write_bytes(b"x" * (17 * MIB))

    clear_profile_cache()
    with pytest.raises(ProfileLoadError, match="exceeds"):
        load_profile_dir(profile)
    monkeypatch.setenv(LIMIT_ENV, str(24 * MIB))
    assert load_profile_dir(profile).profile["language"] == "swift"
    assert (
        tools.trust_profile(str(profile.parent), profile.parent.name)["data"]["status"] == "success"
    )
    repo_id = tools._compute_repo_id(profile.parent)
    record = trust_state_for(repo_id)
    assert record is not None
    original_hash = hash_profile(profile)
    assert record.profile_sha256 == original_hash
    assert not is_material_change(repo_id, profile)
    with signatures.open("r+b") as stream:
        stream.seek(17 * MIB - 1)
        stream.write(b"y")
    assert hash_profile(profile) != original_hash
    assert is_material_change(repo_id, profile)

    monkeypatch.delenv(LIMIT_ENV)
    with pytest.raises(ProfileLoadError, match="exceeds"):
        load_profile_dir(profile)
