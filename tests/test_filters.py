"""Tests for the Phase 5 filter additions: kinds, size, mtime, gitignore."""

from __future__ import annotations

import os
import time
from datetime import UTC, datetime, timedelta

import pytest

from rglob import find_all
from rglob._filters import (
    kinds_match,
    mtime_predicate,
    owner_predicate,
    parse_perm,
    parse_size,
    parse_time,
    perm_predicate,
    size_predicate,
)

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


# ─── parse_perm ──────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("644", (0o644, "exact")),
        ("0o755", (0o755, "exact")),
        ("-111", (0o111, "all")),
        ("/222", (0o222, "any")),
        (0o600, (0o600, "exact")),
    ],
)
def test_parse_perm(value, expected):
    assert parse_perm(value) == expected


def test_parse_perm_invalid():
    with pytest.raises(ValueError, match="unparseable permission mode"):
        parse_perm("nope")


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


def test_default_entry_predicates_pass(tmp_path):
    """Inactive entry predicates remain explicit pass-through helpers."""
    target = tmp_path / "a.txt"
    target.write_text("")
    with os.scandir(tmp_path) as entries:
        entry = next(item for item in entries if item.name == target.name)

        assert kinds_match(entry, ())
        assert kinds_match(entry, ("f",))  # exercises _entry_kind() via legacy path
        assert size_predicate(None, None)(entry)
        assert mtime_predicate(None, None)(entry)
        assert perm_predicate(None)(entry)
        assert owner_predicate(None, None)(entry)


def test_kinds_predicate_empty_set_is_match_all():
    """`kinds_predicate(())` returns a match-everything closure."""
    from rglob._filters import kinds_predicate

    pred = kinds_predicate(())
    # The closure must accept any input and return truthy; it's only
    # called by the walker when no other filter has fired.
    assert pred(object()) is True  # type: ignore[arg-type]


def test_kinds_predicate_multi_kind_uses_union(tmp_path):
    """A multi-kind set falls back to `_entry_kind` union semantics.

    Includes a symlink so the `tags.add("l")` branch in `_entry_kind`
    is exercised — single-kind paths bypass that helper entirely now.
    """
    (tmp_path / "file.txt").write_text("")
    (tmp_path / "sub").mkdir()
    target = tmp_path / "target.txt"
    target.write_text("")
    try:
        (tmp_path / "link.txt").symlink_to(target)
    except (OSError, NotImplementedError):  # pragma: no cover - Windows-only
        pytest.skip("symlinks not permitted on this host")
    out = find_all(tmp_path, "*", kinds={"f", "d", "l"})
    names = {p.name for p in out}
    assert names == {"file.txt", "sub", "target.txt", "link.txt"}


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


def test_newer_than_file_filter(tmp_path):
    """`newer_than_file` compares mtimes against a reference file."""
    reference = tmp_path / "reference.ref"
    reference.write_text("")
    ref_mtime = time.time() - 86400
    os.utime(reference, (ref_mtime, ref_mtime))
    old = tmp_path / "old.txt"
    old.write_text("")
    old_mtime = time.time() - 86400 * 2
    os.utime(old, (old_mtime, old_mtime))
    new = tmp_path / "new.txt"
    new.write_text("")

    out = find_all(tmp_path, "*.txt", newer_than_file=reference)
    assert {p.name for p in out} == {"new.txt"}


# ─── find(1)-style permission / owner filters ────────────────────────────────


def test_perm_exact_filter(tmp_path):
    """`perm='600'` matches exact POSIX mode bits."""
    private = tmp_path / "private.txt"
    private.write_text("")
    private.chmod(0o600)
    public = tmp_path / "public.txt"
    public.write_text("")
    public.chmod(0o644)

    out = find_all(tmp_path, "*.txt", perm="600")
    assert {p.name for p in out} == {"private.txt"}


def test_perm_all_and_any_filters(tmp_path):
    """Leading '-' and '/' implement all-bits and any-bits matching."""
    executable = tmp_path / "run.sh"
    executable.write_text("")
    executable.chmod(0o755)
    plain = tmp_path / "plain.sh"
    plain.write_text("")
    plain.chmod(0o644)

    assert {p.name for p in find_all(tmp_path, "*.sh", perm="-111")} == {"run.sh"}
    assert {p.name for p in find_all(tmp_path, "*.sh", perm="/111")} == {"run.sh"}


def test_uid_gid_filters(tmp_path):
    """POSIX uid/gid filters match the current process owner."""
    if os.name != "posix":
        pytest.skip("uid/gid filters are POSIX-only")
    target = tmp_path / "owned.txt"
    target.write_text("")
    out = find_all(tmp_path, "*.txt", uid=os.getuid(), gid=os.getgid())
    assert {p.name for p in out} == {"owned.txt"}


def test_uid_filter_rejects_non_matching_owner(tmp_path):
    """A non-matching uid excludes otherwise matching files."""
    if os.name != "posix":
        pytest.skip("uid/gid filters are POSIX-only")
    target = tmp_path / "owned.txt"
    target.write_text("")
    out = find_all(tmp_path, "*.txt", uid=os.getuid() + 1)
    assert out == []


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
