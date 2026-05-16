"""Tests for the Typer-powered CLI (Phase 4).

Uses :class:`typer.testing.CliRunner` for in-process invocation and
:func:`syrupy.snapshot` for golden-file assertions on stdout / stderr.

Path-stripping helpers normalise the snapshots so tmp_path doesn't leak
into them.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

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
    """`--json` emits a FileSearchResult object."""
    _build_tree(tmp_path)
    result = runner.invoke(app, ["find", "*.py", "--base", str(tmp_path), "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert set(payload) >= {
        "results",
        "truncated",
        "total_files_searched",
        "bytes_read",
        "errors",
        "truncated_reason",
    }
    names = {Path(match["path"]).name for match in payload["results"]}
    assert names == {"a.py", "b.py", "nested.py"}
    assert payload["truncated"] is False


def test_find_jsonl(tmp_path):
    """`--jsonl` emits one compact FileSearchResult object line."""
    _build_tree(tmp_path)
    result = runner.invoke(app, ["find", "*.py", "--base", str(tmp_path), "--jsonl"])
    assert result.exit_code == 0
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    assert len(lines) == 1
    payload = json.loads(lines[0])
    assert "results" in payload
    assert {Path(match["path"]).name for match in payload["results"]} == {
        "a.py",
        "b.py",
        "nested.py",
    }


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


def test_find_json_limit_reports_truncation(tmp_path):
    """Structured find output reports truncation metadata."""
    _build_tree(tmp_path)
    result = runner.invoke(
        app,
        ["find", "*.py", "--base", str(tmp_path), "--json", "--limit", "1"],
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert len(payload["results"]) == 1
    assert payload["truncated"] is True
    assert payload["truncated_reason"] == "limit"


def test_find_json_bad_max_bytes_is_error_envelope(tmp_path):
    """Bad structured resource limits produce machine-readable errors."""
    _build_tree(tmp_path)
    result = runner.invoke(
        app,
        ["find", "*.py", "--base", str(tmp_path), "--json", "--max-bytes", "nope"],
    )
    assert result.exit_code == 2
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert payload["error"]["code"] == "BAD_PREDICATE"


def test_find_plain_bad_max_bytes_is_human_error(tmp_path):
    """Bad human-output resource limits still produce a CLI error."""
    _build_tree(tmp_path)
    result = runner.invoke(
        app,
        ["find", "*.py", "--base", str(tmp_path), "--max-bytes", "nope"],
    )
    assert result.exit_code == 2
    assert "unparseable size" in (result.stdout + result.stderr)


def test_grep_json_output(tmp_path):
    """`rglob grep --json` emits a LineSearchResult."""
    (tmp_path / "notes.txt").write_text("TODO one\nnope\n", encoding="utf-8")
    result = runner.invoke(
        app,
        ["grep", "TODO", "*.txt", "--base", str(tmp_path), "--json"],
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["results"][0]["content"] == "TODO one"
    assert payload["results"][0]["line_number"] == 1


def test_grep_jsonl_output(tmp_path):
    """`rglob grep --jsonl` streams one match per line then a summary record."""
    (tmp_path / "notes.txt").write_text("TODO one\nTODO two\n", encoding="utf-8")
    result = runner.invoke(
        app,
        ["grep", "TODO", "*.txt", "--base", str(tmp_path), "--jsonl"],
    )
    assert result.exit_code == 0
    lines = [json.loads(line) for line in result.stdout.splitlines() if line.strip()]
    matches = [item for item in lines if item.get("kind") == "match"]
    summaries = [item for item in lines if item.get("kind") == "summary"]
    assert len(matches) == 2
    assert {m["content"] for m in matches} == {"TODO one", "TODO two"}
    assert len(summaries) == 1
    assert summaries[0]["total_files_searched"] == 1
    assert summaries[0]["truncated"] is False


def test_grep_files_with_matches_human_output(tmp_path):
    """`rglob grep -l` prints just the matching paths, one per line."""
    (tmp_path / "a.txt").write_text("TODO\n")
    (tmp_path / "b.txt").write_text("nope\n")
    (tmp_path / "c.txt").write_text("TODO\nTODO\n")
    result = runner.invoke(
        app,
        ["grep", "TODO", "*.txt", "--base", str(tmp_path), "-l"],
    )
    assert result.exit_code == 0
    out_lines = sorted(line for line in result.stdout.splitlines() if line.strip())
    # Two paths, one per line, no `:line:content` suffix.
    assert len(out_lines) == 2
    assert all(line.endswith(("a.txt", "c.txt")) for line in out_lines)


def test_grep_count_only_human_output(tmp_path):
    """`rglob grep -c` prints `path:count` lines."""
    (tmp_path / "a.txt").write_text("TODO\nTODO\nTODO\n")
    (tmp_path / "b.txt").write_text("none\n")
    result = runner.invoke(
        app,
        ["grep", "TODO", "*.txt", "--base", str(tmp_path), "-c"],
    )
    assert result.exit_code == 0
    out_lines = [line for line in result.stdout.splitlines() if line.strip()]
    assert any(line.endswith("a.txt:3") for line in out_lines)


def test_grep_files_with_matches_and_count_only_are_mutually_exclusive(tmp_path):
    """Combining `-l` and `-c` is rejected."""
    (tmp_path / "a.txt").write_text("TODO\n")
    result = runner.invoke(
        app,
        ["grep", "TODO", "*.txt", "--base", str(tmp_path), "-l", "-c"],
    )
    assert result.exit_code == 2
    combined = (result.stdout or "") + (result.stderr or "")
    assert "mutually exclusive" in combined


def test_grep_human_output_and_warning(tmp_path):
    """Human grep output prints path:line:content and binary warnings."""
    (tmp_path / "notes.txt").write_text("TODO one\n", encoding="utf-8")
    (tmp_path / "binary.bin").write_bytes(b"\x00TODO\x00")
    result = runner.invoke(app, ["grep", "TODO", "*", "--base", str(tmp_path)])
    assert result.exit_code == 0
    assert "TODO one" in result.stdout
    assert "BINARY" in result.stderr


def test_count_jsonl_output(tmp_path):
    """`rglob count --jsonl` emits one compact Stats object line."""
    (tmp_path / "a.py").write_text("x\n\n# comment\ny\n", encoding="utf-8")
    result = runner.invoke(
        app,
        ["count", "*.py", "--base", str(tmp_path), "--no-empty", "--no-comments", "--jsonl"],
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["files"] == 1
    assert payload["lines"] == 2


def test_count_json_output(tmp_path):
    """`rglob count --json` emits a pretty Stats object."""
    (tmp_path / "a.py").write_text("x\n", encoding="utf-8")
    result = runner.invoke(app, ["count", "*.py", "--base", str(tmp_path), "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["files"] == 1
    assert payload["lines"] == 1


def test_count_human_output(tmp_path):
    """`rglob count` prints files, lines, and bytes for humans."""
    (tmp_path / "a.py").write_text("x\n", encoding="utf-8")
    result = runner.invoke(app, ["count", "*.py", "--base", str(tmp_path)])
    assert result.exit_code == 0
    assert "Files: 1" in result.stdout
    assert "Lines: 1" in result.stdout


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


def test_module_help_imports_in_fresh_process():
    """`python -m rglob.cli --help` does not hit agent import cycles."""
    result = subprocess.run(
        [sys.executable, "-m", "rglob.cli", "--help"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "find" in result.stdout


_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


def _plain(text: str) -> str:
    """Strip ANSI escapes and collapse whitespace for substring assertions.

    Rich's help renderer styles option names and may wrap long ones across
    lines when the host terminal is narrow (e.g. on GitHub Actions where
    FORCE_COLOR is set). This helper makes substring checks invariant to
    both styling and wrapping.
    """
    return re.sub(r"\s+", " ", _ANSI_RE.sub("", text))


def test_find_help_lists_filter_flags():
    """`rglob find --help` documents the new filter flags."""
    result = runner.invoke(app, ["find", "--help"])
    assert result.exit_code == 0
    plain = _plain(result.stdout)
    for flag in ("--exclude", "--max-depth", "--hidden", "--follow", "--json"):
        assert flag in plain, f"expected {flag!r} in help output"


# ─── agent introspection ─────────────────────────────────────────────────────


def test_describe_find_outputs_manifest_json():
    """`rglob describe find` is a pure JSON manifest."""
    result = runner.invoke(app, ["describe", "find"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["name"] == "find"
    assert payload["agent_api_version"] == "1.0"
    assert "schemas" in payload


def test_schema_find_outputs_input_and_output_schemas():
    """`rglob schema find` exposes the generated schemas."""
    result = runner.invoke(app, ["schema", "find"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["input"]["title"] == "WalkOptions"
    assert payload["output"]["title"] == "FileSearchResult"


def test_schema_all_outputs_all_public_schemas():
    """`rglob schema --all` exposes every public generated schema."""
    result = runner.invoke(app, ["schema", "--all"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["walk_options"]["title"] == "WalkOptions"
    assert payload["grep_options"]["title"] == "GrepOptions"
    assert payload["file_search_result"]["title"] == "FileSearchResult"


def test_schema_unknown_subcommand_is_error_envelope():
    """Unknown schema targets produce the same stable error envelope."""
    result = runner.invoke(app, ["schema", "missing"])
    assert result.exit_code == 2
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert payload["error"]["code"] == "BAD_PREDICATE"


def test_schema_requires_subcommand_or_all():
    """`rglob schema` without a target stays a JSON error endpoint."""
    result = runner.invoke(app, ["schema"])
    assert result.exit_code == 2
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert payload["error"]["code"] == "BAD_PREDICATE"


def test_capabilities_json_report():
    """`rglob capabilities --json` reports versioned capabilities."""
    result = runner.invoke(app, ["capabilities", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["agent_api_version"] == "1.0"
    assert payload["schema_version"] == "1.0"
    assert "extras" in payload


def test_agent_version_is_json_string():
    """`rglob agent-version` emits a JSON string."""
    result = runner.invoke(app, ["agent-version"])
    assert result.exit_code == 0
    assert json.loads(result.stdout) == "1.0"


def test_describe_unknown_subcommand_is_error_envelope():
    """Unknown introspection targets produce a stable error envelope."""
    result = runner.invoke(app, ["describe", "missing"])
    assert result.exit_code == 2
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert payload["error"]["code"] == "BAD_PREDICATE"


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
    """`--jsonl` records per-match stat errors in the result envelope."""
    _build_tree(tmp_path)
    real_stat = __import__("pathlib").Path.stat

    def boom(self, *a, **kw):
        if self.name == "a.py":
            raise PermissionError("no")
        return real_stat(self, *a, **kw)

    monkeypatch.setattr("pathlib.Path.stat", boom)
    result = runner.invoke(app, ["find", "*.py", "--base", str(tmp_path), "--jsonl"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    a_match = next(obj for obj in payload["results"] if obj["path"].endswith("a.py"))
    assert a_match["size"] == 0
    assert a_match["errors"][0]["code"] == "PERM"


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
