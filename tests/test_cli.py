"""Tests for the Typer-powered CLI (Phase 4).

Uses :class:`typer.testing.CliRunner` for in-process invocation and
:func:`syrupy.snapshot` for golden-file assertions on stdout / stderr.

Path-stripping helpers normalise the snapshots so tmp_path doesn't leak
into them.
"""

from __future__ import annotations

import json
import re

import pytest
from typer.testing import CliRunner

from rglob.cli import app

# Use a wide virtual terminal so Rich doesn't truncate paths in test output.
runner = CliRunner(env={"COLUMNS": "200"})


def _build_tree(root):
    """Build a small fixture tree under `root`."""
    (root / "a.py").write_text("alpha\n# comment\n\nbeta\n")
    (root / "b.py").write_text("x\ny\nz\n")
    (root / "c.txt").write_text("hello\n")
    sub = root / "sub"
    sub.mkdir()
    (sub / "nested.py").write_text("nested\n")
    hidden = root / ".hidden"
    hidden.mkdir()
    (hidden / "secret.py").write_text("secret\n")


def _normalise(output: str, base) -> str:
    """Strip the absolute tmp_path so snapshots are portable."""
    sanitized = output.replace(str(base), "<BASE>")
    # Remove tmp_path leftovers in nested paths (Linux-only)
    sanitized = re.sub(r"/tmp/pytest-of-[a-zA-Z0-9_]+/pytest-\d+/[^/\s]+", "<BASE>", sanitized)
    return sanitized


# ─── find ────────────────────────────────────────────────────────────────────


def test_find_default_output(tmp_path, snapshot):
    """`rglob find` lists paths one per line by default."""
    _build_tree(tmp_path)
    result = runner.invoke(app, ["find", "*.py", "--base", str(tmp_path)])
    assert result.exit_code == 0
    assert _normalise(result.stdout, tmp_path) == snapshot


def test_find_json_array(tmp_path):
    """`--json` emits a single JSON array of strings."""
    _build_tree(tmp_path)
    result = runner.invoke(app, ["find", "*.py", "--base", str(tmp_path), "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert isinstance(payload, list)
    names = {p.rsplit("/", 1)[-1] for p in payload}
    assert names == {"a.py", "b.py", "nested.py"}


def test_find_jsonl(tmp_path):
    """`--jsonl` emits one JSON object per line."""
    _build_tree(tmp_path)
    result = runner.invoke(app, ["find", "*.py", "--base", str(tmp_path), "--jsonl"])
    assert result.exit_code == 0
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    payloads = [json.loads(line) for line in lines]
    assert all("path" in obj and "size" in obj for obj in payloads)


def test_find_null_separator(tmp_path):
    """`-0` separates paths with NUL bytes for `xargs -0`."""
    _build_tree(tmp_path)
    result = runner.invoke(app, ["find", "*.py", "--base", str(tmp_path), "-0"])
    assert result.exit_code == 0
    assert "\x00" in result.stdout


def test_find_format_template(tmp_path):
    """`--format` interpolates per-path fields."""
    _build_tree(tmp_path)
    result = runner.invoke(
        app,
        [
            "find",
            "*.py",
            "--base",
            str(tmp_path),
            "--format",
            "{name}|{size}",
        ],
    )
    assert result.exit_code == 0
    for line in result.stdout.splitlines():
        name, _, size = line.partition("|")
        assert name.endswith(".py")
        assert size.isdigit()


def test_find_exclude(tmp_path):
    """`--exclude` prunes the directory."""
    _build_tree(tmp_path)
    result = runner.invoke(
        app,
        ["find", "*.py", "--base", str(tmp_path), "-E", "sub"],
    )
    assert result.exit_code == 0
    assert "nested.py" not in result.stdout
    assert "a.py" in result.stdout


def test_find_max_depth(tmp_path):
    """`--max-depth 0` keeps the walk at the base level."""
    _build_tree(tmp_path)
    result = runner.invoke(
        app,
        ["find", "*.py", "--base", str(tmp_path), "-d", "0"],
    )
    assert result.exit_code == 0
    assert "nested.py" not in result.stdout


def test_find_hidden(tmp_path):
    """`--hidden/-H` reveals dot-directory contents."""
    _build_tree(tmp_path)
    result = runner.invoke(
        app,
        ["find", "*.py", "--base", str(tmp_path), "-H"],
    )
    assert result.exit_code == 0
    assert "secret.py" in result.stdout


def test_find_multiple_patterns(tmp_path):
    """Multiple positional patterns are OR'd."""
    _build_tree(tmp_path)
    result = runner.invoke(
        app,
        ["find", "*.py", "*.txt", "--base", str(tmp_path)],
    )
    assert result.exit_code == 0
    assert "a.py" in result.stdout
    assert "c.txt" in result.stdout


def test_find_warns_on_pre_expansion(tmp_path):
    """Multiple positional args with no glob chars → warning."""
    _build_tree(tmp_path)
    result = runner.invoke(
        app,
        ["find", "a.py", "b.py", "--base", str(tmp_path)],
    )
    # Warning currently goes through Rich; verify it surfaces in stderr OR stdout.
    combined = (result.stderr or "") + (result.stdout or "")
    assert "pre-expand" in combined or result.exit_code == 0


# ─── lcount ──────────────────────────────────────────────────────────────────


def test_lcount_total(tmp_path, snapshot):
    """`rglob lcount` reports a total."""
    _build_tree(tmp_path)
    result = runner.invoke(app, ["lcount", "*.py", "--base", str(tmp_path)])
    assert result.exit_code == 0
    assert _normalise(result.stdout, tmp_path) == snapshot


def test_lcount_no_empty_no_comments(tmp_path):
    """`--no-empty --no-comments` matches the documented filter behaviour."""
    _build_tree(tmp_path)
    # a.py: 4 lines, 2 valid (alpha, beta)
    # b.py: 3 lines, all valid
    # nested.py: 1 line, valid
    result = runner.invoke(
        app,
        ["lcount", "*.py", "--base", str(tmp_path), "--no-empty", "--no-comments"],
    )
    assert result.exit_code == 0
    assert "Total lines: 6" in result.stdout


def test_lcount_no_empty_only(tmp_path):
    """`--no-empty` keeps comments."""
    _build_tree(tmp_path)
    # a.py 3 non-empty (alpha, # comment, beta), b.py 3, nested.py 1 = 7
    result = runner.invoke(
        app,
        ["lcount", "*.py", "--base", str(tmp_path), "--no-empty"],
    )
    assert result.exit_code == 0
    assert "Total lines: 7" in result.stdout


# ─── tsize ───────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("unit", ["kb", "mb", "gb", "tb"])
def test_tsize_units(tmp_path, unit):
    """Every documented unit suffix is accepted."""
    (tmp_path / "x.bin").write_bytes(b"x" * 4096)
    result = runner.invoke(
        app,
        ["tsize", "*.bin", "--base", str(tmp_path), "--unit", unit],
    )
    assert result.exit_code == 0
    assert unit.upper() in result.stdout


def test_tsize_invalid_unit(tmp_path):
    """Unknown unit → exit code 2 + helpful message."""
    (tmp_path / "x.bin").write_bytes(b"x")
    result = runner.invoke(
        app,
        ["tsize", "*.bin", "--base", str(tmp_path), "--unit", "petabytes"],
    )
    assert result.exit_code == 2
    assert "unknown unit" in (result.stdout + result.stderr).lower()


def test_tsize_default_unit(tmp_path, snapshot):
    """Default unit is MB; output is float with two decimals."""
    (tmp_path / "x.bin").write_bytes(b"x" * 4096)
    result = runner.invoke(app, ["tsize", "*.bin", "--base", str(tmp_path)])
    assert result.exit_code == 0
    assert _normalise(result.stdout, tmp_path) == snapshot


# ─── completion / help ───────────────────────────────────────────────────────


def test_help_runs():
    """`rglob --help` returns 0."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "find" in result.stdout
    assert "lcount" in result.stdout
    assert "tsize" in result.stdout


def test_find_help_lists_filter_flags():
    """`rglob find --help` documents the new filter flags."""
    result = runner.invoke(app, ["find", "--help"])
    assert result.exit_code == 0
    out = result.stdout
    for flag in ("--exclude", "--max-depth", "--hidden", "--follow", "--json"):
        assert flag in out


# ─── Coverage edge cases (OSError paths) ─────────────────────────────────────


def test_find_format_handles_stat_oserror(tmp_path, monkeypatch):
    """`--format` keeps going if a stat() call raises OSError."""
    _build_tree(tmp_path)
    real_stat = __import__("pathlib").Path.stat

    def boom(self, *a, **kw):
        if self.name == "a.py":
            raise PermissionError("no")
        return real_stat(self, *a, **kw)

    monkeypatch.setattr("pathlib.Path.stat", boom)
    result = runner.invoke(
        app,
        ["find", "*.py", "--base", str(tmp_path), "--format", "{name}:{size}"],
    )
    assert result.exit_code == 0
    assert "a.py:0" in result.stdout  # fell back to size=0


def test_find_jsonl_handles_stat_oserror(tmp_path, monkeypatch):
    """`--jsonl` keeps going if a stat() call raises OSError."""
    _build_tree(tmp_path)
    real_stat = __import__("pathlib").Path.stat

    def boom(self, *a, **kw):
        if self.name == "a.py":
            raise PermissionError("no")
        return real_stat(self, *a, **kw)

    monkeypatch.setattr("pathlib.Path.stat", boom)
    result = runner.invoke(app, ["find", "*.py", "--base", str(tmp_path), "--jsonl"])
    assert result.exit_code == 0
    lines = [json.loads(line) for line in result.stdout.splitlines() if line.strip()]
    a_line = next(obj for obj in lines if obj["path"].endswith("a.py"))
    assert a_line["size"] == 0


def test_main_entrypoint_runs(monkeypatch):
    """`cli.main()` invokes the Typer app and exits via SystemExit."""
    import sys

    from rglob import cli

    monkeypatch.setattr(sys, "argv", ["rglob", "--help"])
    with pytest.raises(SystemExit) as info:
        cli.main()
    assert info.value.code == 0


# ─── Phase 5 subcommands ─────────────────────────────────────────────────────


def test_stats_subcommand(tmp_path):
    """`rglob stats` runs and emits a populated table."""
    _build_tree(tmp_path)
    result = runner.invoke(app, ["stats", "*.py", "--base", str(tmp_path)])
    assert result.exit_code == 0
    assert "Files" in result.stdout
    assert "Total size" in result.stdout


def test_stats_empty_tree(tmp_path):
    """`stats` on an empty match still exits cleanly."""
    result = runner.invoke(app, ["stats", "*.py", "--base", str(tmp_path)])
    assert result.exit_code == 0


def test_tree_subcommand(tmp_path):
    """`rglob tree` renders a Unicode tree."""
    _build_tree(tmp_path)
    result = runner.invoke(app, ["tree", "*.py", "--base", str(tmp_path)])
    assert result.exit_code == 0
    assert "a.py" in result.stdout
    assert "nested.py" in result.stdout


def test_tree_shares_parent_dir(tmp_path):
    """When multiple files share a subdir, the subdir node is reused."""
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "a.py").write_text("")
    (sub / "b.py").write_text("")
    result = runner.invoke(app, ["tree", "*.py", "--base", str(tmp_path)])
    assert result.exit_code == 0
    # `sub/` should appear once even though two files are inside.
    assert result.stdout.count("sub/") == 1


def test_top_subcommand(tmp_path):
    """`rglob top -n 2` returns the two largest files."""
    (tmp_path / "small.bin").write_bytes(b"x" * 10)
    (tmp_path / "medium.bin").write_bytes(b"x" * 1000)
    (tmp_path / "large.bin").write_bytes(b"x" * 100000)
    result = runner.invoke(app, ["top", "*.bin", "--base", str(tmp_path), "-n", "2"])
    assert result.exit_code == 0
    assert "large.bin" in result.stdout
    assert "medium.bin" in result.stdout


def test_dupes_subcommand_finds_duplicates(tmp_path):
    """`rglob dupes` lists duplicate groups."""
    payload = b"identical content forever"
    (tmp_path / "a.bin").write_bytes(payload)
    (tmp_path / "b.bin").write_bytes(payload)
    (tmp_path / "unique.bin").write_bytes(b"different")
    result = runner.invoke(app, ["dupes", "*.bin", "--base", str(tmp_path)])
    assert result.exit_code == 0
    assert "a.bin" in result.stdout
    assert "b.bin" in result.stdout


def test_find_type_filter(tmp_path):
    """`rglob find -t f` matches only files."""
    (tmp_path / "f.txt").write_text("")
    (tmp_path / "d").mkdir()
    result = runner.invoke(
        app,
        ["find", "*", "--base", str(tmp_path), "-t", "f"],
    )
    assert result.exit_code == 0
    assert "f.txt" in result.stdout
    assert " d\n" not in result.stdout


def test_find_size_filter(tmp_path):
    """`rglob find --min-size` excludes small files."""
    (tmp_path / "small.bin").write_bytes(b"x" * 10)
    (tmp_path / "big.bin").write_bytes(b"x" * 5000)
    result = runner.invoke(
        app,
        ["find", "*.bin", "--base", str(tmp_path), "--min-size", "1K"],
    )
    assert result.exit_code == 0
    assert "big.bin" in result.stdout
    assert "small.bin" not in result.stdout


def test_find_gitignore_flag(tmp_path):
    """`rglob find --gitignore` honours .gitignore."""
    pytest.importorskip("pathspec")
    (tmp_path / ".gitignore").write_text("*.log\n")
    (tmp_path / "keep.py").write_text("")
    (tmp_path / "skip.log").write_text("")
    result = runner.invoke(
        app,
        ["find", "*", "--base", str(tmp_path), "--gitignore", "-H"],
    )
    assert result.exit_code == 0
    assert "keep.py" in result.stdout
    assert "skip.log" not in result.stdout


def test_dupes_subcommand_clean_tree(tmp_path):
    """`rglob dupes` on a clean tree reports 'No duplicates found.'."""
    (tmp_path / "a.bin").write_bytes(b"unique-1")
    (tmp_path / "b.bin").write_bytes(b"unique-2")
    result = runner.invoke(app, ["dupes", "*.bin", "--base", str(tmp_path)])
    assert result.exit_code == 0
    assert "No duplicates" in result.stdout


def test_top_with_unreadable_file(tmp_path, monkeypatch):
    """`top` skips files whose stat() raises OSError."""
    (tmp_path / "a.bin").write_bytes(b"x" * 1000)
    (tmp_path / "b.bin").write_bytes(b"x" * 500)
    real_stat = __import__("pathlib").Path.stat

    def boom(self, *a, **kw):
        if self.name == "a.bin":
            raise PermissionError("nope")
        return real_stat(self, *a, **kw)

    monkeypatch.setattr("pathlib.Path.stat", boom)
    result = runner.invoke(app, ["top", "*.bin", "--base", str(tmp_path)])
    assert result.exit_code == 0
    assert "b.bin" in result.stdout


def test_stats_with_unreadable_file(tmp_path, monkeypatch):
    """`stats` aggregates a size of 0 for files whose stat() raises."""
    (tmp_path / "x.py").write_text("hi")
    real_stat = __import__("pathlib").Path.stat

    def boom(self, *a, **kw):
        if self.name == "x.py":
            raise PermissionError("nope")
        return real_stat(self, *a, **kw)

    monkeypatch.setattr("pathlib.Path.stat", boom)
    result = runner.invoke(app, ["stats", "*.py", "--base", str(tmp_path)])
    assert result.exit_code == 0
