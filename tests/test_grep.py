"""Tests for the structured grep and count helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from rglob._count import count_all
from rglob._grep import grep_all
from rglob.agent._models import CountOptions, GrepOptions


def test_grep_all_regex_with_context(tmp_path):
    """Regex grep returns line matches with before/after context."""
    path = tmp_path / "notes.txt"
    path.write_text("before\nTODO: one\nafter\n", encoding="utf-8")

    result = grep_all(GrepOptions(pattern="TODO", paths=["*.txt"], base=tmp_path, context=1))

    assert result.truncated is False
    assert result.total_files_searched == 1
    assert result.results[0].line_number == 2
    assert result.results[0].before == ["before"]
    assert result.results[0].after == ["after"]


def test_grep_all_after_context_spans_multiple_lines(tmp_path):
    """`--after 2` keeps the match pending until two trailing lines arrive.

    Exercises the streaming branch where `_PendingMatch.feed` returns
    False (still needs more lines) and the match goes back to the
    pending list rather than into results.
    """
    path = tmp_path / "notes.txt"
    path.write_text("alpha\nTODO: one\nfollow1\nfollow2\nfollow3\n", encoding="utf-8")

    result = grep_all(GrepOptions(pattern="TODO", paths=["*.txt"], base=tmp_path, after=2))

    assert result.results[0].after == ["follow1", "follow2"]


def test_grep_all_after_context_invert(tmp_path):
    """`--invert` works on the after-context branch too."""
    path = tmp_path / "notes.txt"
    path.write_text("keep\nTODO\nkeep2\n", encoding="utf-8")

    result = grep_all(
        GrepOptions(pattern="TODO", paths=["*.txt"], base=tmp_path, after=1, invert=True)
    )

    # invert=True means non-TODO lines match. With after=1 each match
    # captures the next line.
    contents = [m.content for m in result.results]
    assert "keep" in contents


def test_grep_all_after_context_limit_terminates(tmp_path):
    """`--limit` short-circuits the after-context loop when the budget is met."""
    path = tmp_path / "notes.txt"
    path.write_text("TODO one\nfollow1\nTODO two\nfollow2\n", encoding="utf-8")

    result = grep_all(GrepOptions(pattern="TODO", paths=["*.txt"], base=tmp_path, after=1, limit=1))

    assert result.truncated is True
    assert result.truncated_reason == "limit"
    assert len(result.results) == 1


def test_grep_all_after_context_max_count_terminates(tmp_path):
    """`--max-count` works on the after-context branch."""
    path = tmp_path / "notes.txt"
    path.write_text("TODO one\nfollow1\nTODO two\nfollow2\n", encoding="utf-8")

    result = grep_all(
        GrepOptions(pattern="TODO", paths=["*.txt"], base=tmp_path, after=1, max_count=1)
    )

    assert result.truncated is True
    assert result.truncated_reason == "max_count"
    assert len(result.results) == 1


def test_grep_all_after_context_line_timeout(monkeypatch, tmp_path):
    """A line-level timeout is reported correctly in the after-context branch."""
    path = tmp_path / "notes.txt"
    path.write_text("TODO\nfollow\n", encoding="utf-8")

    from rglob import _grep

    call_count = {"n": 0}
    real_check = _grep.check_timeout

    def maybe_timeout(deadline) -> None:
        call_count["n"] += 1
        if call_count["n"] >= 2:  # let the file-open check pass; trip at first line
            raise TimeoutError
        real_check(deadline)

    monkeypatch.setattr(_grep, "check_timeout", maybe_timeout)
    result = grep_all(GrepOptions(pattern="TODO", paths=["*.txt"], base=tmp_path, after=1))

    assert result.truncated is True
    assert result.truncated_reason == "timeout"
    assert any(err.code == "TIMEOUT" for err in result.errors)


def test_grep_all_after_context_line_timeout_silent(monkeypatch, tmp_path):
    """`include_errors=False` suppresses the line-level timeout error envelope."""
    path = tmp_path / "notes.txt"
    path.write_text("TODO\nfollow\n", encoding="utf-8")

    from rglob import _grep

    call_count = {"n": 0}
    real_check = _grep.check_timeout

    def maybe_timeout(deadline) -> None:
        call_count["n"] += 1
        if call_count["n"] >= 2:
            raise TimeoutError
        real_check(deadline)

    monkeypatch.setattr(_grep, "check_timeout", maybe_timeout)
    result = grep_all(
        GrepOptions(pattern="TODO", paths=["*.txt"], base=tmp_path, after=1, include_errors=False)
    )

    assert result.truncated is True
    assert result.truncated_reason == "timeout"
    assert result.errors == []


def test_grep_files_with_matches_returns_one_per_file(tmp_path):
    """`files_with_matches=True` emits one stub LineMatch per matching file."""
    (tmp_path / "a.txt").write_text("TODO one\nTODO two\nfine\n")
    (tmp_path / "b.txt").write_text("nope\n")
    (tmp_path / "c.txt").write_text("TODO three\n")

    result = grep_all(
        GrepOptions(pattern="TODO", paths=["*.txt"], base=tmp_path, files_with_matches=True)
    )

    paths = sorted(m.path.name for m in result.results)
    assert paths == ["a.txt", "c.txt"]
    # Stubs carry no content / line_number / context — the agent learns
    # only that the file matched.
    for stub in result.results:
        assert stub.line_number == 0
        assert stub.content == ""
        assert stub.before == []
        assert stub.after == []


def test_grep_files_with_matches_respects_limit(tmp_path):
    """`--limit` bounds the number of matching FILES emitted."""
    for i in range(5):
        (tmp_path / f"f{i}.txt").write_text("TODO\n")

    result = grep_all(
        GrepOptions(
            pattern="TODO", paths=["*.txt"], base=tmp_path, files_with_matches=True, limit=2
        )
    )

    assert len(result.results) == 2
    assert result.truncated is True
    assert result.truncated_reason == "limit"


def test_grep_count_only_emits_per_file_counts(tmp_path):
    """`count_only=True` emits one stub per file with `line_number` = match count."""
    (tmp_path / "a.txt").write_text("TODO\nTODO\nfine\nTODO\n")
    (tmp_path / "b.txt").write_text("nothing here\n")
    (tmp_path / "c.txt").write_text("TODO\n")

    result = grep_all(GrepOptions(pattern="TODO", paths=["*.txt"], base=tmp_path, count_only=True))

    counts = {m.path.name: m.line_number for m in result.results}
    assert counts == {"a.txt": 3, "c.txt": 1}


def test_grep_count_only_respects_limit(tmp_path):
    """`--limit` bounds the number of FILES with non-zero counts."""
    for i in range(5):
        (tmp_path / f"f{i}.txt").write_text("TODO\nTODO\n")

    result = grep_all(
        GrepOptions(pattern="TODO", paths=["*.txt"], base=tmp_path, count_only=True, limit=2)
    )

    assert len(result.results) == 2
    assert result.truncated is True
    assert result.truncated_reason == "limit"


def test_grep_iter_yields_matches(tmp_path):
    """`grep_iter` yields the same LineMatch records that grep_all returns."""
    from rglob._grep import grep_iter

    (tmp_path / "a.txt").write_text("alpha\nTODO\nbeta\n")
    matches = list(grep_iter(GrepOptions(pattern="TODO", paths=["*.txt"], base=tmp_path)))
    assert len(matches) == 1
    assert matches[0].content == "TODO"


def test_grep_all_streams_large_text_file(tmp_path):
    """Files larger than the streaming threshold use TextIOWrapper iteration."""
    big = tmp_path / "big.txt"
    # > 64 KiB so we cross _STREAM_THRESHOLD_BYTES; sprinkle a TODO at the top.
    big.write_text("TODO at top\n" + ("filler\n" * 12_000), encoding="utf-8")

    result = grep_all(GrepOptions(pattern="TODO", paths=["*.txt"], base=tmp_path))

    assert len(result.results) == 1
    assert result.results[0].line_number == 1
    assert result.bytes_read >= 64 * 1024


def test_grep_all_streams_large_binary_file_is_skipped(tmp_path):
    """A large binary file is detected by the head probe and skipped."""
    big = tmp_path / "big.bin"
    # 100 KB, with NULs in the first KB so binary detection short-circuits
    # before we instantiate TextIOWrapper at all.
    big.write_bytes(b"\x00\x00TODO\x00\x00" + b"x" * 100_000)

    result = grep_all(GrepOptions(pattern="TODO", paths=["*.bin"], base=tmp_path))

    assert result.results == []
    assert result.errors[0].code == "BINARY"


def test_grep_all_streams_large_binary_silent(tmp_path):
    """`include_errors=False` suppresses the BINARY envelope on the streaming path."""
    big = tmp_path / "big.bin"
    big.write_bytes(b"\x00\x00TODO\x00\x00" + b"x" * 100_000)

    result = grep_all(
        GrepOptions(pattern="TODO", paths=["*.bin"], base=tmp_path, include_errors=False)
    )

    assert result.results == []
    assert result.errors == []


def test_grep_all_outer_timeout_fires_before_first_file(monkeypatch, tmp_path):
    """A timeout at the outer per-file check produces a global TIMEOUT envelope."""
    (tmp_path / "a.txt").write_text("TODO\n", encoding="utf-8")
    from rglob import _grep

    def always_timeout(_deadline) -> None:
        raise TimeoutError

    monkeypatch.setattr(_grep, "check_timeout", always_timeout)
    result = grep_all(GrepOptions(pattern="TODO", paths=["*.txt"], base=tmp_path))

    assert result.truncated is True
    assert result.truncated_reason == "timeout"
    assert result.errors[0].code == "TIMEOUT"
    # Path is None on the outer timeout (no file in flight).
    assert result.errors[0].path is None


def test_grep_all_fixed_ignore_case_word_and_invert(tmp_path):
    """Literal, ignore-case, word, and invert modes are supported."""
    path = tmp_path / "data.txt"
    path.write_text("alpha\ncatalog\nALPHA\n", encoding="utf-8")

    word_result = grep_all(
        GrepOptions(
            pattern="alpha",
            paths=["*.txt"],
            base=tmp_path,
            fixed_string=True,
            ignore_case=True,
            word=True,
        )
    )
    invert_result = grep_all(
        GrepOptions(pattern="alpha", paths=["*.txt"], base=tmp_path, fixed_string=True, invert=True)
    )

    assert [match.line_number for match in word_result.results] == [1, 3]
    assert [match.content for match in invert_result.results] == ["catalog", "ALPHA"]


def test_grep_all_bad_regex_is_error_result(tmp_path):
    """Regex compile errors are reported instead of raised."""
    result = grep_all(GrepOptions(pattern="[", paths=["*.txt"], base=tmp_path))
    assert result.results == []
    assert result.errors[0].code == "REGEX"


def test_grep_all_binary_skip_and_text_override(tmp_path):
    """Binary files are skipped by default and searchable with text=True."""
    binary = tmp_path / "binary.bin"
    binary.write_bytes(b"\x00TODO\x00")

    skipped = grep_all(GrepOptions(pattern="TODO", paths=["*.bin"], base=tmp_path))
    as_text = grep_all(GrepOptions(pattern="TODO", paths=["*.bin"], base=tmp_path, text=True))

    assert skipped.results == []
    assert skipped.errors[0].code == "BINARY"
    assert as_text.results[0].content == "\x00TODO\x00"


def test_grep_all_limit_max_count_and_max_bytes(tmp_path):
    """Grep reports truncation reasons for result and byte limits."""
    path = tmp_path / "many.txt"
    path.write_text("TODO one\nTODO two\n", encoding="utf-8")

    limited = grep_all(GrepOptions(pattern="TODO", paths=["*.txt"], base=tmp_path, limit=1))
    max_counted = grep_all(GrepOptions(pattern="TODO", paths=["*.txt"], base=tmp_path, max_count=1))
    byte_limited = grep_all(
        GrepOptions(pattern="TODO", paths=["*.txt"], base=tmp_path, max_bytes=1)
    )

    assert limited.truncated_reason == "limit"
    assert max_counted.truncated_reason == "max_count"
    assert byte_limited.truncated_reason == "max_bytes"


def test_grep_all_max_bytes_checks_size_before_read(monkeypatch, tmp_path):
    """max_bytes prevents opening a file that already exceeds the cap."""
    path = tmp_path / "large.txt"
    path.write_text("TODO\n", encoding="utf-8")

    def fail_open(_self, *_args, **_kwargs):
        raise AssertionError("Path.open should not be called when max_bytes trips first")

    monkeypatch.setattr(Path, "open", fail_open)
    result = grep_all(GrepOptions(pattern="TODO", paths=["*.txt"], base=tmp_path, max_bytes=1))

    assert result.truncated is True
    assert result.truncated_reason == "max_bytes"


def test_grep_all_strict_base_rejects_symlink_escape(tmp_path):
    """Grep does not read linked dirs that resolve outside strict base."""
    base = tmp_path / "base"
    base.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    target = outside / "secret.txt"
    target.write_text("TODO\n", encoding="utf-8")
    try:
        (base / "linked").symlink_to(outside, target_is_directory=True)
    except (OSError, NotImplementedError):  # pragma: no cover - Windows-only
        pytest.skip("symlinks not permitted")

    result = grep_all(GrepOptions(pattern="TODO", paths=["*.txt"], base=base, follow_symlinks=True))

    assert result.results == []
    assert result.errors[0].code == "PERM"


def test_grep_all_strict_base_can_suppress_error(tmp_path):
    """Grep strict-base errors respect include_errors=False."""
    base = tmp_path / "base"
    base.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.txt").write_text("TODO\n", encoding="utf-8")
    try:
        (base / "linked").symlink_to(outside, target_is_directory=True)
    except (OSError, NotImplementedError):  # pragma: no cover - Windows-only
        pytest.skip("symlinks not permitted")

    result = grep_all(
        GrepOptions(
            pattern="TODO",
            paths=["*.txt"],
            base=base,
            follow_symlinks=True,
            include_errors=False,
        )
    )

    assert result.results == []
    assert result.errors == []


def test_grep_all_unreadable_file(monkeypatch, tmp_path):
    """Read errors are collected as ErrorInfo records."""
    path = tmp_path / "bad.txt"
    path.write_text("TODO\n", encoding="utf-8")
    real_open = Path.open

    def boom(self, *args, **kwargs):
        if self == path:
            raise PermissionError("nope")
        return real_open(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", boom)
    result = grep_all(GrepOptions(pattern="TODO", paths=["*.txt"], base=tmp_path))

    assert result.errors[0].code == "UNREADABLE"


def test_grep_all_unstatable_file(monkeypatch, tmp_path):
    """Stat errors are collected before file reads."""
    path = tmp_path / "bad.txt"
    path.write_text("TODO\n", encoding="utf-8")
    real_stat = Path.stat

    def boom(self, *args, **kwargs):
        if self == path:
            raise PermissionError("no stat")
        return real_stat(self, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", boom)
    result = grep_all(GrepOptions(pattern="TODO", paths=["*.txt"], base=tmp_path))

    assert result.errors[0].code == "UNREADABLE"


def test_grep_all_unstatable_file_can_suppress_error(monkeypatch, tmp_path):
    """Stat errors respect include_errors=False."""
    path = tmp_path / "bad.txt"
    path.write_text("TODO\n", encoding="utf-8")
    real_stat = Path.stat

    def boom(self, *args, **kwargs):
        if self == path:
            raise PermissionError("no stat")
        return real_stat(self, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", boom)
    result = grep_all(
        GrepOptions(pattern="TODO", paths=["*.txt"], base=tmp_path, include_errors=False)
    )

    assert result.errors == []


def test_grep_all_can_suppress_unreadable_and_binary_errors(monkeypatch, tmp_path):
    """include_errors=False suppresses read and binary errors."""
    bad = tmp_path / "bad.txt"
    bad.write_text("TODO\n", encoding="utf-8")
    binary = tmp_path / "binary.bin"
    binary.write_bytes(b"\x00TODO\x00")
    real_open = Path.open

    def boom(self, *args, **kwargs):
        if self == bad:
            raise PermissionError("nope")
        return real_open(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", boom)

    unreadable = grep_all(
        GrepOptions(pattern="TODO", paths=["*.txt"], base=tmp_path, include_errors=False)
    )
    skipped_binary = grep_all(
        GrepOptions(pattern="TODO", paths=["*.bin"], base=tmp_path, include_errors=False)
    )

    assert unreadable.errors == []
    assert skipped_binary.errors == []


def test_grep_all_timeout_can_suppress_error(monkeypatch, tmp_path):
    """File-level timeout truncation respects include_errors=False."""
    (tmp_path / "notes.txt").write_text("TODO\n", encoding="utf-8")
    ticks = iter([0.0, 1.0])
    monkeypatch.setattr("rglob.agent._runtime.time.monotonic", lambda: next(ticks))

    result = grep_all(
        GrepOptions(
            pattern="TODO",
            paths=["*.txt"],
            base=tmp_path,
            timeout_seconds=0.1,
            include_errors=False,
        )
    )

    assert result.truncated_reason == "timeout"
    assert result.errors == []


def test_grep_all_line_timeout_reports_path(monkeypatch, tmp_path):
    """Line-level timeout reports the file being processed."""
    path = tmp_path / "notes.txt"
    path.write_text("TODO\n", encoding="utf-8")
    ticks = iter([0.0, 0.05, 1.0])
    monkeypatch.setattr("rglob.agent._runtime.time.monotonic", lambda: next(ticks))

    result = grep_all(
        GrepOptions(pattern="TODO", paths=["*.txt"], base=tmp_path, timeout_seconds=0.1)
    )

    assert result.truncated_reason == "timeout"
    assert result.errors[0].code == "TIMEOUT"
    assert result.errors[0].path == path


def test_grep_all_line_timeout_can_suppress_error(monkeypatch, tmp_path):
    """Line-level timeout respects include_errors=False."""
    path = tmp_path / "notes.txt"
    path.write_text("TODO\n", encoding="utf-8")
    ticks = iter([0.0, 0.05, 1.0])
    monkeypatch.setattr("rglob.agent._runtime.time.monotonic", lambda: next(ticks))

    result = grep_all(
        GrepOptions(
            pattern="TODO",
            paths=["*.txt"],
            base=tmp_path,
            timeout_seconds=0.1,
            include_errors=False,
        )
    )

    assert result.truncated_reason == "timeout"
    assert result.errors == []


def test_count_all_counts_files_lines_and_bytes(tmp_path):
    """CountOptions produce structured Stats."""
    (tmp_path / "a.py").write_text("x\n\n# comment\ny\n", encoding="utf-8")
    (tmp_path / "b.py").write_text("z\n", encoding="utf-8")

    result = count_all(
        CountOptions(patterns=["*.py"], base=tmp_path, no_empty=True, no_comments=True)
    )

    assert result.files == 2
    assert result.lines == 3
    assert result.bytes > 0


def test_count_all_limit_max_bytes_and_unreadable(monkeypatch, tmp_path):
    """Count truncation and unreadable files are reported."""
    a = tmp_path / "a.py"
    a.write_text("x\n", encoding="utf-8")
    b = tmp_path / "b.py"
    b.write_text("y\n", encoding="utf-8")

    limited = count_all(CountOptions(patterns=["*.py"], base=tmp_path, limit=1))
    byte_limited = count_all(CountOptions(patterns=["*.py"], base=tmp_path, max_bytes=1))

    real_read = Path.read_bytes

    def boom(self):
        if self == a:
            raise PermissionError("nope")
        return real_read(self)

    monkeypatch.setattr(Path, "read_bytes", boom)
    unreadable = count_all(CountOptions(patterns=["*.py"], base=tmp_path))

    assert limited.truncated_reason == "limit"
    assert byte_limited.truncated_reason == "max_bytes"
    assert unreadable.errors[0].code == "UNREADABLE"


def test_count_all_unstatable_file(monkeypatch, tmp_path):
    """Stat errors are collected before file reads."""
    path = tmp_path / "bad.py"
    path.write_text("x\n", encoding="utf-8")
    real_stat = Path.stat

    def boom(self, *args, **kwargs):
        if self == path:
            raise PermissionError("no stat")
        return real_stat(self, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", boom)
    result = count_all(CountOptions(patterns=["*.py"], base=tmp_path))

    assert result.errors[0].code == "UNREADABLE"


def test_count_all_unstatable_file_can_suppress_error(monkeypatch, tmp_path):
    """Stat errors respect include_errors=False."""
    path = tmp_path / "bad.py"
    path.write_text("x\n", encoding="utf-8")
    real_stat = Path.stat

    def boom(self, *args, **kwargs):
        if self == path:
            raise PermissionError("no stat")
        return real_stat(self, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", boom)
    result = count_all(CountOptions(patterns=["*.py"], base=tmp_path, include_errors=False))

    assert result.errors == []


def test_count_all_max_bytes_checks_size_before_read(monkeypatch, tmp_path):
    """max_bytes prevents reading a file that already exceeds the cap."""
    path = tmp_path / "large.py"
    path.write_text("x\n", encoding="utf-8")

    def fail_read(_self):
        raise AssertionError("read_bytes should not be called")

    monkeypatch.setattr(Path, "read_bytes", fail_read)
    result = count_all(CountOptions(patterns=["*.py"], base=tmp_path, max_bytes=1))

    assert result.truncated is True
    assert result.truncated_reason == "max_bytes"


def test_count_all_strict_base_rejects_symlink_escape(tmp_path):
    """Count does not read linked dirs that resolve outside strict base."""
    base = tmp_path / "base"
    base.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    target = outside / "secret.py"
    target.write_text("x\n", encoding="utf-8")
    try:
        (base / "linked").symlink_to(outside, target_is_directory=True)
    except (OSError, NotImplementedError):  # pragma: no cover - Windows-only
        pytest.skip("symlinks not permitted")

    result = count_all(CountOptions(patterns=["*.py"], base=base, follow_symlinks=True))

    assert result.files == 0
    assert result.errors[0].code == "PERM"


def test_count_all_strict_base_can_suppress_error(tmp_path):
    """Count strict-base errors respect include_errors=False."""
    base = tmp_path / "base"
    base.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.py").write_text("x\n", encoding="utf-8")
    try:
        (base / "linked").symlink_to(outside, target_is_directory=True)
    except (OSError, NotImplementedError):  # pragma: no cover - Windows-only
        pytest.skip("symlinks not permitted")

    result = count_all(
        CountOptions(
            patterns=["*.py"],
            base=base,
            follow_symlinks=True,
            include_errors=False,
        )
    )

    assert result.files == 0
    assert result.errors == []


def test_count_all_can_suppress_unreadable_errors(monkeypatch, tmp_path):
    """include_errors=False suppresses read errors."""
    path = tmp_path / "a.py"
    path.write_text("x\n", encoding="utf-8")

    def boom(_self):
        raise PermissionError("nope")

    monkeypatch.setattr(Path, "read_bytes", boom)
    result = count_all(CountOptions(patterns=["*.py"], base=tmp_path, include_errors=False))

    assert result.errors == []


def test_count_all_timeout_can_suppress_error(monkeypatch, tmp_path):
    """File-level timeout truncation respects include_errors=False."""
    (tmp_path / "a.py").write_text("x\n", encoding="utf-8")
    ticks = iter([0.0, 1.0])
    monkeypatch.setattr("rglob.agent._runtime.time.monotonic", lambda: next(ticks))

    result = count_all(
        CountOptions(
            patterns=["*.py"],
            base=tmp_path,
            timeout_seconds=0.1,
            include_errors=False,
        )
    )

    assert result.truncated_reason == "timeout"
    assert result.errors == []


def test_count_all_line_timeout_reports_path(monkeypatch, tmp_path):
    """Line-level timeout reports the file being processed."""
    path = tmp_path / "a.py"
    path.write_text("x\n", encoding="utf-8")
    ticks = iter([0.0, 0.05, 1.0])
    monkeypatch.setattr("rglob.agent._runtime.time.monotonic", lambda: next(ticks))

    result = count_all(CountOptions(patterns=["*.py"], base=tmp_path, timeout_seconds=0.1))

    assert result.truncated_reason == "timeout"
    assert result.errors[0].code == "TIMEOUT"
    assert result.errors[0].path == path


def test_count_all_line_timeout_can_suppress_error(monkeypatch, tmp_path):
    """Line-level timeout respects include_errors=False."""
    path = tmp_path / "a.py"
    path.write_text("x\n", encoding="utf-8")
    ticks = iter([0.0, 0.05, 1.0])
    monkeypatch.setattr("rglob.agent._runtime.time.monotonic", lambda: next(ticks))

    result = count_all(
        CountOptions(
            patterns=["*.py"],
            base=tmp_path,
            timeout_seconds=0.1,
            include_errors=False,
        )
    )

    assert result.truncated_reason == "timeout"
    assert result.errors == []
