"""Tests for the agent contract models and golden fixture."""

from __future__ import annotations

import os
from dataclasses import FrozenInstanceError, is_dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from rglob.agent import all_schemas, schema_for
from rglob.agent._introspection import _schema_for_type
from rglob.agent._models import (
    CapabilityReport,
    ErrorCode,
    ErrorInfo,
    FileMatch,
    FileSearchResult,
    error_envelope,
    to_json_dict,
)
from rglob.agent._runtime import _strict_base_error, collect_file_search, file_match

FIXTURE = Path(__file__).parent / "fixtures" / "agent-tree"


def test_agent_fixture_shape():
    """The committed golden fixture contains all required test surfaces."""
    required = {
        ".gitignore",
        "src/main.py",
        "src/utils/helper.py",
        "docs/notes.txt",
        "binary.bin",
        "unreadable/.keep",
        "duplicates/a.txt",
        "duplicates/b.txt",
        "hidden/.secret.py",
    }
    assert {path.as_posix() for path in required_paths(FIXTURE)} >= required
    assert (FIXTURE / "duplicates" / "a.txt").read_bytes() == (
        FIXTURE / "duplicates" / "b.txt"
    ).read_bytes()
    with pytest.raises(UnicodeDecodeError):
        (FIXTURE / "binary.bin").read_text(encoding="utf-8")


def required_paths(root: Path) -> set[Path]:
    """Return fixture paths relative to root."""
    return {path.relative_to(root) for path in root.rglob("*") if path.is_file()}


def test_file_match_is_frozen_and_slotted():
    """Contract dataclasses are frozen, slotted dataclasses."""
    match = FileMatch(
        path=FIXTURE / "src" / "main.py",
        relative_path="src/main.py",
        size=10,
        mtime=datetime(2026, 5, 15, tzinfo=UTC),
        kinds=["f"],
        errors=[],
    )

    assert is_dataclass(match)
    assert not hasattr(match, "__dict__")
    with pytest.raises(FrozenInstanceError):
        match.size = 11  # type: ignore[misc]


def test_to_json_dict_serializes_wire_types():
    """Path, datetime, StrEnum, and nested dataclasses become JSON-safe."""
    error = ErrorInfo(ErrorCode.UNREADABLE, "cannot read", FIXTURE / "unreadable")
    result = FileSearchResult(
        results=[
            FileMatch(
                path=FIXTURE / "src" / "main.py",
                relative_path="src/main.py",
                size=123,
                mtime=datetime(2026, 5, 15, 12, 30, tzinfo=UTC),
                kinds=["f"],
                errors=[error],
            )
        ],
        truncated=False,
        total_files_searched=1,
        bytes_read=123,
        errors=[error],
        truncated_reason=None,
    )

    payload = to_json_dict(result)

    assert isinstance(payload, dict)
    # to_json_dict serialises Path via str(), which uses the host's native
    # separator — so the suffix probe must use the same separator.
    assert payload["results"][0]["path"].endswith(str(Path("src") / "main.py"))
    assert payload["results"][0]["mtime"] == "2026-05-15T12:30:00Z"
    assert payload["errors"][0]["code"] == "UNREADABLE"
    assert to_json_dict(object()).startswith("<object object at ")


def test_error_envelope_shape():
    """The stable error envelope is JSON-safe and machine-readable."""
    payload = error_envelope(ErrorInfo(ErrorCode.REGEX, "bad pattern", None))
    assert payload == {
        "ok": False,
        "error": {"code": "REGEX", "message": "bad pattern", "path": None},
    }


def test_capability_report_shape_matches_contract():
    """Capability reports carry the locked top-level keys."""
    report = CapabilityReport(
        agent_api_version="1.0",
        schema_version="1.0",
        package_version="2.0.0",
        extras={"mcp": False, "gitignore": True, "ext": False},
        predicates={
            "perm": "supported",
            "uid": "POSIX-only",
            "gid": "POSIX-only",
            "newer_than": "supported",
            "respect_gitignore": "supported",
        },
        mcp={"available": False, "transport": "stdio"},
    )
    payload = to_json_dict(report)
    assert set(payload) == {
        "agent_api_version",
        "schema_version",
        "package_version",
        "extras",
        "predicates",
        "mcp",
    }


def test_agent_schemas_are_generated_from_contract_models():
    """Generated schemas advertise Draft 2020-12 and the locked version."""
    schemas = all_schemas()
    assert set(schemas) >= {
        "file_search_result",
        "line_search_result",
        "duplicate_search_result",
        "walk_options",
        "grep_options",
        "count_options",
    }
    for payload in schemas.values():
        assert payload["$schema"] == "https://json-schema.org/draft/2020-12/schema"
        assert payload["version"] == "1.0"

    walk = schema_for("walk_options")
    assert walk == schemas["walk_options"]
    assert walk["title"] == "WalkOptions"
    assert walk["properties"]["base"]["format"] == "path"


def test_schema_generator_handles_open_ended_types():
    """Fallback schema branches remain deterministic."""
    assert _schema_for_type(Any) == {}
    assert _schema_for_type(object) == {"type": "string"}
    with pytest.raises(ValueError, match="unknown schema: missing"):
        schema_for("missing")


def test_file_match_handles_paths_outside_base(tmp_path):
    """Relative paths fall back to the basename when strict base is not applied."""
    outside = tmp_path / "outside.txt"
    base = tmp_path / "base"
    base.mkdir()
    outside.write_text("outside")

    match = file_match(outside, base, include_errors=True)

    assert match.relative_path == "outside.txt"


def test_file_match_reports_dir_symlink_and_executable_kinds(tmp_path):
    """FileMatch kind detection covers dirs, symlinks, files, and executables."""
    directory = tmp_path / "dir"
    directory.mkdir()
    executable = tmp_path / "run.sh"
    executable.write_text("#!/bin/sh\n")
    executable.chmod(0o755)

    dir_match = file_match(directory, tmp_path, include_errors=True)
    exe_match = file_match(executable, tmp_path, include_errors=True)

    assert "d" in dir_match.kinds
    assert "f" in exe_match.kinds
    if os.name == "posix":
        # NTFS does not honour Path.chmod() for executable bits, so the
        # `x` tag is only reliably present on POSIX hosts.
        assert "x" in exe_match.kinds

    try:
        link = tmp_path / "run-link.sh"
        link.symlink_to(executable)
    except (OSError, NotImplementedError):  # pragma: no cover - Windows-only
        pytest.skip("symlinks not permitted")

    link_match = file_match(link, tmp_path, include_errors=True)
    assert "l" in link_match.kinds


def test_file_match_can_suppress_stat_errors(tmp_path):
    """include_errors=False keeps OSErrors out of the match record."""
    match = file_match(tmp_path / "missing.txt", tmp_path, include_errors=False)
    assert match.size == 0
    assert match.errors == []


def test_collect_file_search_max_bytes_truncates(tmp_path):
    """max_bytes truncates before emitting a record that would exceed it."""
    path = tmp_path / "a.txt"
    path.write_text("hello")

    result = collect_file_search(
        [path],
        base=tmp_path,
        limit=None,
        max_bytes=1,
        include_errors=True,
    )

    assert result.results == []
    assert result.truncated is True
    assert result.truncated_reason == "max_bytes"


def test_collect_file_search_timeout_can_suppress_error(monkeypatch, tmp_path):
    """Timeout truncation respects include_errors=False."""
    path = tmp_path / "a.txt"
    path.write_text("hello")
    ticks = iter([0.0, 1.0])
    monkeypatch.setattr("rglob.agent._runtime.time.monotonic", lambda: next(ticks))

    result = collect_file_search(
        [path],
        base=tmp_path,
        limit=None,
        max_bytes=None,
        include_errors=False,
        timeout_seconds=0.1,
    )

    assert result.truncated_reason == "timeout"
    assert result.errors == []


def test_collect_file_search_strict_base_can_suppress_error(tmp_path):
    """Strict-base containment skips escaped paths without errors when requested."""
    outside = tmp_path / "outside.txt"
    outside.write_text("hello")
    base = tmp_path / "base"
    base.mkdir()

    result = collect_file_search(
        [outside],
        base=base,
        limit=None,
        max_bytes=None,
        include_errors=False,
        strict_base=True,
    )

    assert result.results == []
    assert result.errors == []


def test_timeout_floor_is_bad_predicate(tmp_path):
    """Timeouts below the supported floor are rejected by the agent API."""
    from rglob.agent import WalkOptions, search_all

    result = search_all(WalkOptions(patterns=["*"], base=tmp_path, timeout_seconds=0.01))
    assert result.errors[0].code == ErrorCode.BAD_PREDICATE


def test_strict_base_error_accepts_relative_path():
    """The strict-base error helper handles relative paths lexically."""
    error = _strict_base_error(Path("outside.txt"), Path.cwd())
    assert error.path == Path.cwd() / "outside.txt"
