"""Tests for the Phase 5 filter additions: kinds, size, mtime, gitignore."""

from __future__ import annotations

import os
import time
from datetime import UTC, datetime, timedelta

import pytest

from rglob import find_all
from rglob._filters import parse_size, parse_time

# ─── parse_size ───────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (1024, 1024),
        ("1024", 1024),
        ("1K", 1024),
        ("1KB", 1024),
        ("1KiB", 1024),
        ("2.5M", int(2.5 * 2**20)),
        ("1G", 2**30),
        ("100 kb", 100 * 1024),
        (1024.5, 1024),
    ],
)
def test_parse_size(value, expected):
    assert parse_size(value) == expected


def test_parse_size_invalid():
    with pytest.raises(ValueError, match="unparseable size"):
        parse_size("nope")


# ─── parse_time ───────────────────────────────────────────────────────────────


def test_parse_time_datetime_passthrough():
    now = datetime.now(UTC)
    assert parse_time(now) == now


def test_parse_time_naive_datetime_gets_utc():
    naive = datetime(2024, 1, 1)
    parsed = parse_time(naive)
    assert parsed.tzinfo is not None


def test_parse_time_timedelta_is_relative():
    parsed = parse_time(timedelta(hours=1))
    now = datetime.now(UTC)
    assert (now - parsed) >= timedelta(minutes=55)


def test_parse_time_duration_string():
    parsed = parse_time("7d")
    now = datetime.now(UTC)
    assert (now - parsed) >= timedelta(days=6, hours=23)


def test_parse_time_iso_date():
    parsed = parse_time("2024-01-15")
    assert parsed.year == 2024
    assert parsed.month == 1
    assert parsed.day == 15


def test_parse_time_invalid():
    with pytest.raises(ValueError, match="unparseable time"):
        parse_time("not-a-time")


# ─── kinds ───────────────────────────────────────────────────────────────────


def test_kinds_file_only(tmp_path):
    """`kinds={'f'}` returns only regular files."""
    (tmp_path / "a.txt").write_text("")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "b.txt").write_text("")
    out = find_all(tmp_path, "*", kinds={"f"})
    assert all(p.is_file() for p in out)
    assert {p.name for p in out} == {"a.txt", "b.txt"}


def test_kinds_dir_only(tmp_path):
    """`kinds={'d'}` returns only directories."""
    (tmp_path / "a.txt").write_text("")
    (tmp_path / "sub").mkdir()
    out = find_all(tmp_path, "*", kinds={"d"})
    assert {p.name for p in out} == {"sub"}


def test_kinds_executable(tmp_path):
    """`kinds={'x'}` matches files with the exec bit set."""
    pytest.importorskip("os")  # always available; just to make linter happy
    script = tmp_path / "run.sh"
    script.write_text("#!/bin/sh\n")
    script.chmod(0o755)
    plain = tmp_path / "data.txt"
    plain.write_text("")
    out = find_all(tmp_path, "*", kinds={"x"})
    names = {p.name for p in out}
    assert "run.sh" in names
    assert "data.txt" not in names


def test_kinds_symlink(tmp_path):
    """`kinds={'l'}` matches symbolic links."""
    real = tmp_path / "real.txt"
    real.write_text("hi")
    try:
        (tmp_path / "link.txt").symlink_to(real)
    except (OSError, NotImplementedError):  # pragma: no cover - Windows-only
        pytest.skip("symlinks not permitted")
    out = find_all(tmp_path, "*", kinds={"l"})
    assert {p.name for p in out} == {"link.txt"}


# ─── size filters ────────────────────────────────────────────────────────────


def test_min_size_filters_small_files(tmp_path):
    """`min_size='1K'` excludes files under 1 KiB."""
    (tmp_path / "tiny.bin").write_bytes(b"x" * 100)
    (tmp_path / "big.bin").write_bytes(b"x" * 2048)
    out = find_all(tmp_path, "*.bin", min_size="1K")
    assert {p.name for p in out} == {"big.bin"}


def test_max_size_filters_large_files(tmp_path):
    """`max_size=500` excludes files over 500 bytes."""
    (tmp_path / "tiny.bin").write_bytes(b"x" * 100)
    (tmp_path / "big.bin").write_bytes(b"x" * 2048)
    out = find_all(tmp_path, "*.bin", max_size=500)
    assert {p.name for p in out} == {"tiny.bin"}


def test_size_filter_range(tmp_path):
    """Combining `min_size` and `max_size` works as a closed range."""
    (tmp_path / "small.bin").write_bytes(b"x" * 100)
    (tmp_path / "mid.bin").write_bytes(b"x" * 1000)
    (tmp_path / "big.bin").write_bytes(b"x" * 5000)
    out = find_all(tmp_path, "*.bin", min_size=500, max_size=2000)
    assert {p.name for p in out} == {"mid.bin"}


# ─── mtime filters ───────────────────────────────────────────────────────────


def test_newer_than_filter(tmp_path):
    """`newer_than` only yields files modified after the cutoff."""
    old = tmp_path / "old.txt"
    old.write_text("")
    old_mtime = time.time() - 86400 * 7  # 7 days ago
    os.utime(old, (old_mtime, old_mtime))
    new = tmp_path / "new.txt"
    new.write_text("")
    out = find_all(tmp_path, "*.txt", newer_than="1d")
    assert {p.name for p in out} == {"new.txt"}


def test_older_than_filter(tmp_path):
    """`older_than` only yields files modified before the cutoff."""
    old = tmp_path / "old.txt"
    old.write_text("")
    old_mtime = time.time() - 86400 * 7
    os.utime(old, (old_mtime, old_mtime))
    new = tmp_path / "new.txt"
    new.write_text("")
    out = find_all(tmp_path, "*.txt", older_than="1d")
    assert {p.name for p in out} == {"old.txt"}


# ─── .gitignore awareness ────────────────────────────────────────────────────


def test_respect_gitignore(tmp_path):
    """`respect_gitignore=True` honours .gitignore patterns."""
    pytest.importorskip("pathspec")
    (tmp_path / ".gitignore").write_text("*.log\nbuild/\n")
    (tmp_path / "keep.py").write_text("")
    (tmp_path / "skip.log").write_text("")
    (tmp_path / "build").mkdir()
    (tmp_path / "build" / "artifact.bin").write_text("")
    out = find_all(tmp_path, "*", respect_gitignore=True, hidden=True)
    names = {p.name for p in out}
    assert "keep.py" in names
    assert "skip.log" not in names
    # build/ itself or its contents should be ignored
    assert "artifact.bin" not in names


def test_size_filter_passes_directories(tmp_path):
    """Size filters always pass directories (they have no inherent file size)."""
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "child.bin").write_bytes(b"x" * 5000)
    out = find_all(tmp_path, "*", min_size="1K")
    names = {p.name for p in out}
    # The dir entry should still be in the results despite having no "size".
    assert "sub" in names
    assert "child.bin" in names


def test_no_gitignore_by_default(tmp_path):
    """Without `respect_gitignore`, gitignored files are still listed."""
    (tmp_path / ".gitignore").write_text("*.log\n")
    (tmp_path / "keep.py").write_text("")
    (tmp_path / "skip.log").write_text("")
    out = find_all(tmp_path, "*", hidden=True)
    names = {p.name for p in out}
    assert "skip.log" in names
