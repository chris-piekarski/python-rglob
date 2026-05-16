"""Tests for the public `rglob.agent` API."""

from __future__ import annotations

from pathlib import Path

import pytest

from rglob.agent import (
    CountOptions,
    ErrorCode,
    FileMatch,
    GrepOptions,
    WalkOptions,
    __agent_api_version__,
    all_schemas,
    count,
    find_duplicates,
    grep,
    grep_all,
    schema_for,
    search,
    search_all,
)


def test_agent_exports_version_and_types():
    """The stable agent namespace exposes versioned contract members."""
    assert __agent_api_version__ == "1.0"
    assert FileMatch.__name__ == "FileMatch"
    assert schema_for("walk_options")["title"] == "WalkOptions"
    assert "walk_options" in all_schemas()


def test_search_and_search_all(tmp_path):
    """Agent search helpers return FileMatch records."""
    (tmp_path / "a.py").write_text("", encoding="utf-8")
    (tmp_path / "b.txt").write_text("", encoding="utf-8")

    opts = WalkOptions(patterns=["*.py"], base=tmp_path)
    result = search_all(opts)
    streamed = list(search(opts))

    assert result.results[0].relative_path == "a.py"
    assert streamed[0].relative_path == "a.py"


def test_search_all_converts_bad_predicate_to_error(tmp_path):
    """Operational predicate errors become ErrorInfo records."""
    result = search_all(WalkOptions(patterns=["*"], base=tmp_path, perm="nope"))
    assert result.results == []
    assert result.errors[0].code == ErrorCode.BAD_PREDICATE


def test_search_all_strict_base_rejects_symlink_escape(tmp_path):
    """Default strict_base skips symlinks resolving outside the base."""
    base = tmp_path / "base"
    base.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    target = outside / "secret.py"
    target.write_text("", encoding="utf-8")
    try:
        (base / "secret.py").symlink_to(target)
    except (OSError, NotImplementedError):  # pragma: no cover - Windows-only
        pytest.skip("symlinks not permitted")

    result = search_all(WalkOptions(patterns=["*.py"], base=base))

    assert result.results == []
    assert result.errors[0].code == ErrorCode.PERM


def test_search_all_timeout_is_truncated(monkeypatch, tmp_path):
    """timeout_seconds is honored by the public search API."""
    (tmp_path / "a.py").write_text("", encoding="utf-8")
    ticks = iter([0.0, 1.0])
    monkeypatch.setattr("rglob.agent._runtime.time.monotonic", lambda: next(ticks))

    result = search_all(WalkOptions(patterns=["*.py"], base=tmp_path, timeout_seconds=0.1))

    assert result.truncated is True
    assert result.truncated_reason == "timeout"
    assert result.errors[0].code == ErrorCode.TIMEOUT


def test_grep_and_grep_all(tmp_path):
    """Agent grep helpers return LineMatch records."""
    (tmp_path / "notes.txt").write_text("TODO\n", encoding="utf-8")

    opts = GrepOptions(pattern="TODO", paths=["*.txt"], base=tmp_path)
    result = grep_all(opts)
    streamed = list(grep(opts))

    assert result.results[0].content == "TODO"
    assert streamed[0].line_number == 1


def test_grep_all_timeout_is_error(monkeypatch, tmp_path):
    """timeout_seconds is honored by the public grep API."""
    (tmp_path / "notes.txt").write_text("TODO\n", encoding="utf-8")
    ticks = iter([0.0, 1.0])
    monkeypatch.setattr("rglob.agent._runtime.time.monotonic", lambda: next(ticks))

    result = grep_all(
        GrepOptions(pattern="TODO", paths=["*.txt"], base=tmp_path, timeout_seconds=0.1)
    )

    assert result.truncated is True
    assert result.truncated_reason == "timeout"
    assert result.errors[0].code == ErrorCode.TIMEOUT


def test_grep_all_converts_operational_error(monkeypatch, tmp_path):
    """Unexpected grep errors are converted into LineSearchResult errors."""

    def boom(_opts):
        raise ValueError("bad")

    monkeypatch.setattr("rglob._grep.grep_all", boom)
    result = grep_all(GrepOptions(pattern="TODO", paths=["*.txt"], base=tmp_path))
    assert result.errors[0].code == ErrorCode.BAD_PREDICATE


def test_count_and_count_error(tmp_path):
    """Agent count returns Stats and converts bad predicates."""
    (tmp_path / "a.py").write_text("x\n", encoding="utf-8")

    good = count(CountOptions(patterns=["*.py"], base=tmp_path))
    bad = count(CountOptions(patterns=["*.py"], base=tmp_path, newer_than_file=Path("missing")))

    assert good.files == 1
    assert good.lines == 1
    assert bad.errors[0].code == ErrorCode.UNREADABLE


def test_count_timeout_is_error(monkeypatch, tmp_path):
    """timeout_seconds is honored by the public count API."""
    (tmp_path / "a.py").write_text("x\n", encoding="utf-8")
    ticks = iter([0.0, 1.0])
    monkeypatch.setattr("rglob.agent._runtime.time.monotonic", lambda: next(ticks))

    result = count(CountOptions(patterns=["*.py"], base=tmp_path, timeout_seconds=0.1))

    assert result.truncated is True
    assert result.truncated_reason == "timeout"
    assert result.errors[0].code == ErrorCode.TIMEOUT


def test_count_converts_permission_error(monkeypatch, tmp_path):
    """Permission errors map to the PERM error code."""

    def boom(_opts):
        raise PermissionError("denied")

    monkeypatch.setattr("rglob._count.count_all", boom)
    result = count(CountOptions(patterns=["*.py"], base=tmp_path))
    assert result.errors[0].code == ErrorCode.PERM


def test_find_duplicates_agent_result(tmp_path):
    """Duplicate API returns structured duplicate groups."""
    payload = b"same"
    (tmp_path / "a.bin").write_bytes(payload)
    (tmp_path / "b.bin").write_bytes(payload)
    (tmp_path / "c.bin").write_bytes(b"other")

    result = find_duplicates(WalkOptions(patterns=["*.bin"], base=tmp_path, limit=1))

    assert len(result.results) == 1
    assert {path.name for path in result.results[0].paths} == {"a.bin", "b.bin"}


def test_find_duplicates_limit_reports_truncation(tmp_path):
    """Duplicate result limits set truncation metadata."""
    (tmp_path / "a.bin").write_bytes(b"one")
    (tmp_path / "b.bin").write_bytes(b"one")
    (tmp_path / "c.bin").write_bytes(b"two")
    (tmp_path / "d.bin").write_bytes(b"two")

    result = find_duplicates(WalkOptions(patterns=["*.bin"], base=tmp_path, limit=1))

    assert len(result.results) == 1
    assert result.truncated is True
    assert result.truncated_reason == "limit"


def test_find_duplicates_handles_stat_error_in_record(monkeypatch, tmp_path):
    """Duplicate records fall back to size 0 when stat fails."""
    missing_a = tmp_path / "missing-a.bin"
    missing_b = tmp_path / "missing-b.bin"

    def fake_groups(_paths, *, timeout_check=None):
        return [[missing_a, missing_b]]

    monkeypatch.setattr("rglob._dupes.find_duplicates", fake_groups)
    result = find_duplicates(WalkOptions(patterns=["*.bin"], base=tmp_path))

    assert result.results[0].size == 0


def test_find_duplicates_handles_empty_group(monkeypatch, tmp_path):
    """A defensive empty duplicate group still serializes."""

    def fake_groups(_paths, *, timeout_check=None):
        return [[]]

    monkeypatch.setattr("rglob._dupes.find_duplicates", fake_groups)
    result = find_duplicates(WalkOptions(patterns=["*.bin"], base=tmp_path))

    assert result.results[0].paths == []
    assert result.results[0].size == 0


def test_find_duplicates_converts_errors(tmp_path):
    """Duplicate API is non-raising for bad predicates."""
    result = find_duplicates(WalkOptions(patterns=["*"], base=tmp_path, perm="nope"))
    assert result.errors[0].code == ErrorCode.BAD_PREDICATE


def test_find_duplicates_strict_base_rejects_symlink_escape(tmp_path):
    """Duplicate search does not hash linked dirs that resolve outside strict base."""
    base = tmp_path / "base"
    base.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    target = outside / "secret.bin"
    target.write_bytes(b"same")
    try:
        (base / "linked").symlink_to(outside, target_is_directory=True)
    except (OSError, NotImplementedError):  # pragma: no cover - Windows-only
        pytest.skip("symlinks not permitted")

    result = find_duplicates(WalkOptions(patterns=["*.bin"], base=base, follow_symlinks=True))

    assert result.results == []
    assert result.errors[0].code == ErrorCode.PERM


def test_find_duplicates_strict_base_can_suppress_error(tmp_path):
    """Duplicate strict-base errors respect include_errors=False."""
    base = tmp_path / "base"
    base.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    target = outside / "secret.bin"
    target.write_bytes(b"same")
    try:
        (base / "linked").symlink_to(outside, target_is_directory=True)
    except (OSError, NotImplementedError):  # pragma: no cover - Windows-only
        pytest.skip("symlinks not permitted")

    result = find_duplicates(
        WalkOptions(
            patterns=["*.bin"],
            base=base,
            follow_symlinks=True,
            include_errors=False,
        )
    )

    assert result.results == []
    assert result.errors == []


def test_find_duplicates_timeout_is_error(monkeypatch, tmp_path):
    """timeout_seconds is honored by duplicate search."""
    (tmp_path / "a.bin").write_bytes(b"same")
    ticks = iter([0.0, 1.0])
    monkeypatch.setattr("rglob.agent._runtime.time.monotonic", lambda: next(ticks))

    result = find_duplicates(WalkOptions(patterns=["*.bin"], base=tmp_path, timeout_seconds=0.1))

    assert result.truncated is True
    assert result.truncated_reason == "timeout"
    assert result.errors[0].code == ErrorCode.TIMEOUT


def test_find_duplicates_timeout_during_hashing(monkeypatch, tmp_path):
    """Duplicate hashing receives the public timeout deadline."""
    (tmp_path / "a.bin").write_bytes(b"same")
    ticks = iter([0.0, 0.0, 1.0])
    monkeypatch.setattr("rglob.agent._runtime.time.monotonic", lambda: next(ticks))

    def fake_groups(_paths, *, timeout_check=None):
        assert timeout_check is not None
        timeout_check()
        return []

    monkeypatch.setattr("rglob._dupes.find_duplicates", fake_groups)

    result = find_duplicates(WalkOptions(patterns=["*.bin"], base=tmp_path, timeout_seconds=0.1))

    assert result.truncated is True
    assert result.truncated_reason == "timeout"
    assert result.total_files_searched == 1
    assert result.errors[0].code == ErrorCode.TIMEOUT


def test_find_duplicates_timeout_can_suppress_error(monkeypatch, tmp_path):
    """Duplicate timeout errors respect include_errors=False."""
    (tmp_path / "a.bin").write_bytes(b"same")
    ticks = iter([0.0, 1.0])
    monkeypatch.setattr("rglob.agent._runtime.time.monotonic", lambda: next(ticks))

    result = find_duplicates(
        WalkOptions(
            patterns=["*.bin"],
            base=tmp_path,
            timeout_seconds=0.1,
            include_errors=False,
        )
    )

    assert result.truncated is True
    assert result.truncated_reason == "timeout"
    assert result.errors == []
