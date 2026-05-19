"""Walker and grep performance benchmarks.

Measures the in-process Python walker against the same task done with
``ripgrep`` for an external reference. Trees are built once per test
via ``tmp_path`` and the actual operation is wrapped in
``benchmark()`` so ``pytest-benchmark`` reports median timings and
operations-per-second.

Run via:

    .venv/bin/python -m pytest bench/ --benchmark-only --benchmark-columns=median,ops,rounds
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from rglob import find_all
from rglob.agent import GrepOptions, grep_all

# ─── Tree builders ────────────────────────────────────────────────────────────


def _build_tree(
    root: Path,
    *,
    dirs: int = 20,
    files_per_dir: int = 50,
    file_size: int = 64,
) -> int:
    """Build a synthetic tree and return the total file count."""
    body = ("print('x')\n" * max(1, file_size // 16))[:file_size] or "x\n"
    for dir_index in range(dirs):
        directory = root / f"pkg_{dir_index:03d}"
        directory.mkdir()
        for file_index in range(files_per_dir):
            suffix = ".py" if file_index % 2 == 0 else ".txt"
            (directory / f"module_{file_index:04d}{suffix}").write_text(body)
    return dirs * files_per_dir


def _seed_todos(root: Path, *, every: int = 5) -> int:
    """Replace every Nth `.py` file's content with a TODO line; return count."""
    count = 0
    for index, path in enumerate(sorted(root.rglob("*.py"))):
        if index % every == 0:
            path.write_text("alpha\nTODO: kept for grep benchmark\nbeta\n")
            count += 1
    return count


# ─── Walker benchmarks ───────────────────────────────────────────────────────


def test_find_unsorted_python_files(benchmark, tmp_path):
    """`find_all(..., sort=False)` over a 1k-file tree."""
    total = _build_tree(tmp_path)

    def run() -> list:
        return find_all(tmp_path, "*.py", sort=False)

    result = benchmark(run)
    assert len(result) == total // 2


def test_find_sorted_python_files(benchmark, tmp_path):
    """`find_all(..., sort=True)` is the default ordering mode."""
    total = _build_tree(tmp_path)

    def run() -> list:
        return find_all(tmp_path, "*.py", sort=True)

    result = benchmark(run)
    assert len(result) == total // 2


def test_find_all_files_star(benchmark, tmp_path):
    """`find_all(..., "*")` should hit the `*`-pattern fast path."""
    total = _build_tree(tmp_path)

    def run() -> list:
        return find_all(tmp_path, "*", sort=False)

    result = benchmark(run)
    # `*` matches everything: files (`total`) plus the `dirs` directories.
    assert len(result) >= total


def test_find_only_files_kind(benchmark, tmp_path):
    """`kinds={'f'}` should hit the kind fast-path (no stat() per entry)."""
    total = _build_tree(tmp_path)

    def run() -> list:
        return find_all(tmp_path, "*", sort=False, kinds={"f"})

    result = benchmark(run)
    assert len(result) == total


def test_find_only_dirs_kind(benchmark, tmp_path):
    """`kinds={'d'}` returns only directories."""
    _build_tree(tmp_path, dirs=20, files_per_dir=50)

    def run() -> list:
        return find_all(tmp_path, "*", sort=False, kinds={"d"})

    result = benchmark(run)
    assert len(result) == 20


def test_find_large_files(benchmark, tmp_path):
    """Walker cost should be dominated by entry count, not file content size."""
    total = _build_tree(tmp_path, dirs=10, files_per_dir=50, file_size=4096)

    def run() -> list:
        return find_all(tmp_path, "*.py", sort=False)

    result = benchmark(run)
    assert len(result) == total // 2


# ─── Grep benchmarks ─────────────────────────────────────────────────────────


def test_grep_todo_python(benchmark, tmp_path):
    """`grep_all(...)` over a tree with planted TODOs (no early termination)."""
    _build_tree(tmp_path)
    seeded = _seed_todos(tmp_path)

    opts = GrepOptions(pattern="TODO", paths=["*.py"], base=tmp_path)

    def run():
        return grep_all(opts)

    result = benchmark(run)
    assert result.total_files_searched == 500  # only `.py` files visited
    assert len(result.results) == seeded


def test_grep_todo_python_with_limit(benchmark, tmp_path):
    """`grep_all(..., limit=10)` should short-circuit after 10 matches."""
    _build_tree(tmp_path)
    _seed_todos(tmp_path)

    opts = GrepOptions(pattern="TODO", paths=["*.py"], base=tmp_path, limit=10)

    def run():
        return grep_all(opts)

    result = benchmark(run)
    assert result.truncated is True
    assert result.truncated_reason == "limit"
    assert len(result.results) == 10


def test_grep_todo_large_files_with_limit(benchmark, tmp_path):
    """Streaming early-break wins biggest on large files with a small limit."""
    # Larger files (~100 KB each) so the streaming branch fires.
    _build_tree(tmp_path, dirs=5, files_per_dir=10, file_size=100_000)
    _seed_todos(tmp_path, every=2)

    opts = GrepOptions(pattern="TODO", paths=["*.py"], base=tmp_path, limit=5)

    def run():
        return grep_all(opts)

    result = benchmark(run)
    assert len(result.results) == 5


def test_grep_files_with_matches(benchmark, tmp_path):
    """`files_with_matches=True` stops reading each file at the first match."""
    _build_tree(tmp_path, dirs=10, files_per_dir=20, file_size=10_000)
    _seed_todos(tmp_path, every=3)  # ~33 matching .py files

    opts = GrepOptions(pattern="TODO", paths=["*.py"], base=tmp_path, files_with_matches=True)

    def run():
        return grep_all(opts)

    result = benchmark(run)
    # Stub LineMatch per matching file (line_number=0, content="").
    assert all(m.line_number == 0 for m in result.results)
    assert len(result.results) > 0


def test_grep_count_only(benchmark, tmp_path):
    """`count_only=True` scans every file but builds one record per match group."""
    _build_tree(tmp_path, dirs=10, files_per_dir=20, file_size=10_000)
    _seed_todos(tmp_path, every=3)

    opts = GrepOptions(pattern="TODO", paths=["*.py"], base=tmp_path, count_only=True)

    def run():
        return grep_all(opts)

    result = benchmark(run)
    # One stub LineMatch per matching file with line_number = match count.
    assert all(m.line_number > 0 for m in result.results)


# ─── Ripgrep parity benchmarks ───────────────────────────────────────────────


@pytest.fixture(scope="module")
def _rg() -> str:
    """Locate ripgrep; skip the comparison benchmarks when it's missing."""
    binary = shutil.which("rg")
    if binary is None:
        pytest.skip("ripgrep is not installed")
    return binary


def test_rg_files_python_glob(benchmark, tmp_path, _rg):
    """Reference: `rg --files -g '*.py'` over the same tree."""
    total = _build_tree(tmp_path)

    def run():
        return subprocess.run(
            [_rg, "--files", "-g", "*.py", str(tmp_path)],
            check=True,
            capture_output=True,
            text=True,
        )

    result = benchmark(run)
    assert len(result.stdout.splitlines()) == total // 2


def test_rg_grep_todo(benchmark, tmp_path, _rg):
    """Reference: `rg --json TODO` against the same TODO-seeded tree."""
    _build_tree(tmp_path)
    seeded = _seed_todos(tmp_path)

    def run():
        return subprocess.run(
            [_rg, "--json", "-g", "*.py", "TODO", str(tmp_path)],
            check=True,
            capture_output=True,
            text=True,
        )

    result = benchmark(run)
    # Each rg JSON match record has `"type":"match"`.
    match_lines = [line for line in result.stdout.splitlines() if '"type":"match"' in line]
    assert len(match_lines) == seeded
