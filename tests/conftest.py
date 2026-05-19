"""Shared pytest fixtures and helpers for rglob tests.

These mirror the Behave step helpers in `features/steps/steps.py` so the BDD
suite and the pytest suite share the same notion of "build a tree, count
things in it." The fixture style favours `tmp_path` so each test gets an
isolated tree.
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest


@pytest.fixture
def tree_builder(tmp_path: Path) -> Iterator[TreeBuilder]:
    """Yield a TreeBuilder rooted at tmp_path."""
    builder = TreeBuilder(tmp_path)
    yield builder


class TreeBuilder:
    """Build synthetic directory trees for tests.

    Mirrors the Behave `context.root` / `context.dirs` / `context.known_sizes`
    bookkeeping pattern so test logic ports 1:1 from the BDD suite.
    """

    def __init__(self, root: Path) -> None:
        """Initialise builder with an empty root directory."""
        self.root: Path = root
        self.dirs: list[Path] = []
        self.known_sizes: dict[str, list[int]] = {}

    def make_subdirs(self, n: int) -> list[Path]:
        """Create `n` subdirectories under every existing dir (or root if none)."""
        targets = list(self.dirs) if self.dirs else [self.root]
        created: list[Path] = []
        for parent in targets:
            for _ in range(n):
                sub = Path(tempfile.mkdtemp(prefix="subdir_", suffix="_rglob", dir=str(parent)))
                created.append(sub)
        self.dirs.extend(created)
        return created

    def make_files(self, n: int, ext: str, *, content: str | None = None) -> list[Path]:
        """Create `n` files with extension `ext` under every subdirectory."""
        created: list[Path] = []
        self.known_sizes.setdefault(ext, [])
        for d in self.dirs:
            for i in range(n):
                payload = content if content is not None else f"{i}: synthetic"
                path = Path(tempfile.mktemp(prefix="rglob_test_file", suffix=ext, dir=str(d)))
                path.write_text(payload, encoding="utf-8")
                self.known_sizes[ext].append(path.stat().st_size)
                created.append(path)
        return created

    def write_lines(self, ext: str, lines: int) -> None:
        """Overwrite every `*{ext}` file with `lines` lines of content."""
        for d in self.dirs:
            for p in d.iterdir():
                if p.suffix == ext:
                    p.write_text(
                        "".join(f"line {i + 1}\n" for i in range(lines)),
                        encoding="utf-8",
                    )

    def total_known_size(self, ext: str) -> int:
        """Sum the recorded sizes for files with the given extension."""
        return sum(self.known_sizes.get(ext, []))


@pytest.fixture
def chdir(monkeypatch: pytest.MonkeyPatch) -> object:
    """Return a helper to chdir using monkeypatch (auto-reverted)."""

    def _chdir(target: Path) -> None:
        monkeypatch.chdir(target)

    return _chdir


@pytest.fixture
def make_symlink_loop(tmp_path: Path) -> Path:
    """Create `a → b → a` symlink loop and return the entry point.

    Skips on platforms where symlink creation requires elevation (Windows
    without developer mode).
    """
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir()
    b.mkdir()
    try:
        (a / "to_b").symlink_to(b, target_is_directory=True)
        (b / "to_a").symlink_to(a, target_is_directory=True)
    except (OSError, NotImplementedError) as e:  # pragma: no cover - Windows-only
        pytest.skip(f"Symlink creation not permitted: {e}")
    return a


@pytest.fixture(autouse=True)
def _isolate_cwd(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Chdir to tmp_path by default so `rglob_()` tests don't escape isolation."""
    monkeypatch.chdir(tmp_path)
    _ = os.getcwd  # Touch to silence unused-import flake


@pytest.fixture
def case_sensitive_fs(tmp_path: Path) -> bool:
    """Return True iff the filesystem under tmp_path distinguishes file casing.

    APFS (macOS default) and NTFS (Windows default) treat ``README.MD`` and
    ``readme.md`` as the same path; tests that assume both can coexist as
    separate inodes must guard themselves with this fixture.
    """
    lower = tmp_path / "__case_probe"
    upper = tmp_path / "__CASE_PROBE"
    lower.write_text("lower")
    try:
        upper.write_text("upper")
    except OSError:
        lower.unlink(missing_ok=True)
        return False
    try:
        return not lower.samefile(upper)
    finally:
        lower.unlink(missing_ok=True)
        upper.unlink(missing_ok=True)
