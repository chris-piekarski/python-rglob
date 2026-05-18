"""Tests for the new `find()` / `find_all()` modern API (Phase 3)."""

from __future__ import annotations

import os
import sys
import warnings
from pathlib import Path

import pytest

from rglob import find, find_all

# ─── Basic matching ──────────────────────────────────────────────────────────


def test_find_returns_iterator(tmp_path):
    """`find` is a lazy iterator, not a list."""
    (tmp_path / "a.txt").write_text("a")
    result = find(tmp_path, "*.txt")
    assert iter(result) is result or hasattr(result, "__next__")


def test_find_all_returns_list_of_paths(tmp_path):
    """`find_all` materialises into `list[Path]`."""
    (tmp_path / "a.txt").write_text("a")
    (tmp_path / "b.txt").write_text("b")
    out = find_all(tmp_path, "*.txt")
    assert isinstance(out, list)
    assert all(isinstance(p, Path) for p in out)
    assert {p.name for p in out} == {"a.txt", "b.txt"}


def test_find_basename_pattern_matches_recursively(tmp_path):
    """Basename patterns recurse: `*.py` matches at any depth."""
    (tmp_path / "top.py").write_text("")
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "nested.py").write_text("")
    assert {p.name for p in find_all(tmp_path, "*.py")} == {"top.py", "nested.py"}


def test_find_double_star_matches_any_depth(tmp_path):
    """`**/*.py` matches Python files at any depth."""
    (tmp_path / "top.py").write_text("")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "nested.py").write_text("")
    (tmp_path / "sub" / "deep").mkdir()
    (tmp_path / "sub" / "deep" / "deeper.py").write_text("")
    assert {p.name for p in find_all(tmp_path, "**/*.py")} == {
        "top.py",
        "nested.py",
        "deeper.py",
    }


def test_find_path_pattern_matches_subdir_prefix(tmp_path):
    """Patterns with `/` match against the relative path."""
    (tmp_path / "a").mkdir()
    (tmp_path / "a" / "x.txt").write_text("")
    (tmp_path / "b").mkdir()
    (tmp_path / "b" / "x.txt").write_text("")
    out = find_all(tmp_path, "a/*.txt")
    assert {p.name for p in out} == {"x.txt"}
    assert all("a" in p.parts for p in out)


def test_find_multiple_patterns(tmp_path):
    """Sequence of patterns acts as OR."""
    (tmp_path / "a.py").write_text("")
    (tmp_path / "b.txt").write_text("")
    (tmp_path / "c.md").write_text("")
    out = find_all(tmp_path, ["*.py", "*.txt"])
    assert {p.name for p in out} == {"a.py", "b.txt"}


def test_find_default_pattern_matches_everything(tmp_path):
    """No pattern → match all entries."""
    (tmp_path / "a").mkdir()
    (tmp_path / "a" / "x.txt").write_text("")
    (tmp_path / "b.py").write_text("")
    out = {p.name for p in find_all(tmp_path)}
    assert out == {"a", "x.txt", "b.py"}


# ─── Exclude ─────────────────────────────────────────────────────────────────


def test_exclude_prunes_directory(tmp_path):
    """Excluded directories are not descended into."""
    (tmp_path / "keep").mkdir()
    (tmp_path / "keep" / "x.py").write_text("")
    (tmp_path / "skip").mkdir()
    (tmp_path / "skip" / "y.py").write_text("")
    out = find_all(tmp_path, "*.py", exclude="skip")
    assert {p.name for p in out} == {"x.py"}


def test_exclude_multiple_patterns(tmp_path):
    """Multiple exclude patterns are OR'd."""
    (tmp_path / "a.tmp").write_text("")
    (tmp_path / "b.bak").write_text("")
    (tmp_path / "c.py").write_text("")
    out = find_all(tmp_path, "*", exclude=["*.tmp", "*.bak"])
    assert {p.name for p in out} == {"c.py"}


# ─── max_depth ───────────────────────────────────────────────────────────────


def test_max_depth_zero(tmp_path):
    """`max_depth=0` limits to direct children of base."""
    (tmp_path / "top.txt").write_text("")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "nested.txt").write_text("")
    out = find_all(tmp_path, "*.txt", max_depth=0)
    assert {p.name for p in out} == {"top.txt"}


def test_max_depth_one(tmp_path):
    """`max_depth=1` includes one level of subdir."""
    (tmp_path / "top.txt").write_text("")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "nested.txt").write_text("")
    (tmp_path / "sub" / "deep").mkdir()
    (tmp_path / "sub" / "deep" / "deeper.txt").write_text("")
    out = find_all(tmp_path, "*.txt", max_depth=1)
    assert {p.name for p in out} == {"top.txt", "nested.txt"}


def test_max_depth_none_unbounded(tmp_path):
    """`max_depth=None` (default) walks arbitrarily deep."""
    chain = tmp_path
    for i in range(5):
        chain = chain / f"d{i}"
        chain.mkdir()
    (chain / "deep.txt").write_text("")
    assert {p.name for p in find_all(tmp_path, "*.txt")} == {"deep.txt"}


# ─── hidden ──────────────────────────────────────────────────────────────────


def test_hidden_skipped_by_default(tmp_path):
    """Dotfiles are skipped unless `hidden=True`."""
    (tmp_path / "visible.py").write_text("")
    (tmp_path / ".hidden.py").write_text("")
    (tmp_path / ".dotdir").mkdir()
    (tmp_path / ".dotdir" / "x.py").write_text("")
    out = {p.name for p in find_all(tmp_path, "*.py")}
    assert out == {"visible.py"}


def test_hidden_included_when_enabled(tmp_path):
    """`hidden=True` reveals dotfiles and dot-directory contents."""
    (tmp_path / "visible.py").write_text("")
    (tmp_path / ".hidden.py").write_text("")
    (tmp_path / ".dotdir").mkdir()
    (tmp_path / ".dotdir" / "x.py").write_text("")
    out = {p.name for p in find_all(tmp_path, "*.py", hidden=True)}
    assert out == {"visible.py", ".hidden.py", "x.py"}


# ─── case_sensitive ──────────────────────────────────────────────────────────


def test_case_sensitive_true(tmp_path):
    """Case-sensitive `True` rejects mismatched casing."""
    (tmp_path / "README.MD").write_text("")
    assert find_all(tmp_path, "*.md", case_sensitive=True) == []
    assert len(find_all(tmp_path, "*.MD", case_sensitive=True)) == 1


def test_case_sensitive_false(tmp_path, case_sensitive_fs):
    """Case-sensitive `False` accepts either casing."""
    if not case_sensitive_fs:
        # APFS/NTFS collapse README.MD and readme.md to one inode; the
        # case-insensitive matching contract is exercised by
        # test_case_sensitive_none_follows_os on those hosts.
        pytest.skip("filesystem is case-insensitive; cannot create both casings")
    (tmp_path / "README.MD").write_text("")
    (tmp_path / "readme.md").write_text("")
    out = find_all(tmp_path, "*.md", case_sensitive=False)
    assert {p.name for p in out} == {"README.MD", "readme.md"}


def test_case_sensitive_none_follows_os(tmp_path):
    """Default `None` matches the host OS convention."""
    (tmp_path / "README.MD").write_text("")
    if sys.platform in ("win32", "darwin"):
        # Case-insensitive default: lowercase pattern still matches.
        assert len(find_all(tmp_path, "*.md")) == 1
    else:
        # Linux: case-sensitive default.
        assert find_all(tmp_path, "*.md") == []


# ─── sort ────────────────────────────────────────────────────────────────────


def test_sort_default_lexical(tmp_path):
    """Default order is lexically sorted within each directory."""
    for name in ("c", "a", "b"):
        (tmp_path / f"{name}.txt").write_text("")
    out = [p.name for p in find_all(tmp_path, "*.txt")]
    assert out == ["a.txt", "b.txt", "c.txt"]


def test_sort_false_raw_order(tmp_path):
    """`sort=False` returns scandir's native order (we just don't assert ordering)."""
    for name in ("c", "a", "b"):
        (tmp_path / f"{name}.txt").write_text("")
    out = find_all(tmp_path, "*.txt", sort=False)
    assert {p.name for p in out} == {"a.txt", "b.txt", "c.txt"}


# ─── performance-sensitive fast paths ────────────────────────────────────────


def test_find_avoids_pathlib_relative_to_per_entry(tmp_path, monkeypatch):
    """The walker carries relative strings instead of recomputing Path.relative_to."""
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "mod.py").write_text("")

    def boom(self, *other):
        raise AssertionError(f"relative_to should not be called for {self!s} / {other!r}")

    monkeypatch.setattr(Path, "relative_to", boom)

    out = find_all(tmp_path, "**/*.py")

    assert [path.name for path in out] == ["mod.py"]


def test_find_avoids_realpath_when_not_following_symlinks(tmp_path, monkeypatch):
    """Cycle detection realpath work is only needed when following symlinks."""
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "mod.py").write_text("")

    def boom(_path):
        raise AssertionError("realpath should not be called unless follow_symlinks=True")

    monkeypatch.setattr(os.path, "realpath", boom)

    out = find_all(tmp_path, "*.py")

    assert [path.name for path in out] == ["mod.py"]


# ─── on_error ────────────────────────────────────────────────────────────────


def test_on_error_raise_propagates(tmp_path, monkeypatch):
    """`on_error='raise'` re-raises OSError from scandir."""

    def boom(_path):
        raise PermissionError("nope")

    monkeypatch.setattr(os, "scandir", boom)
    with pytest.raises(PermissionError):
        list(find(tmp_path, "*", on_error="raise"))


def test_on_error_warn_emits_warning(tmp_path, monkeypatch):
    """`on_error='warn'` (default) emits a RuntimeWarning."""

    def boom(_path):
        raise PermissionError("nope")

    monkeypatch.setattr(os, "scandir", boom)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        out = list(find(tmp_path, "*", on_error="warn"))
    assert out == []
    assert any(issubclass(w.category, RuntimeWarning) for w in caught)


def test_on_error_ignore_silences(tmp_path, monkeypatch):
    """`on_error='ignore'` swallows OSError entirely."""

    def boom(_path):
        raise PermissionError("nope")

    monkeypatch.setattr(os, "scandir", boom)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        out = list(find(tmp_path, "*", on_error="ignore"))
    assert out == []
    assert not caught


# ─── follow_symlinks + loop detection ────────────────────────────────────────


def test_symlinks_not_followed_by_default(tmp_path):
    """Default `follow_symlinks=False` skips symlinked directories."""
    target = tmp_path / "real"
    target.mkdir()
    (target / "x.py").write_text("")
    try:
        (tmp_path / "link").symlink_to(target, target_is_directory=True)
    except (OSError, NotImplementedError):  # pragma: no cover - Windows-only
        pytest.skip("symlinks not permitted")
    out = {p.name for p in find_all(tmp_path, "*.py")}
    assert out == {"x.py"}  # Only via the real path, not the link.


def test_symlinks_followed_when_enabled(tmp_path):
    """`follow_symlinks=True` traverses symlinked directories."""
    target = tmp_path / "real"
    target.mkdir()
    (target / "x.py").write_text("")
    try:
        (tmp_path / "link").symlink_to(target, target_is_directory=True)
    except (OSError, NotImplementedError):  # pragma: no cover - Windows-only
        pytest.skip("symlinks not permitted")
    out = find_all(tmp_path, "*.py", follow_symlinks=True)
    # x.py via /real/x.py — the realpath memo prevents double-yield via /link/x.py.
    assert len(out) == 1
    assert out[0].name == "x.py"


def test_symlink_loop_terminates(make_symlink_loop):
    """A `a → b → a` cycle does not infinitely recurse."""
    entry = make_symlink_loop
    # Should terminate quickly without exhausting recursion limits.
    out = find_all(entry, "*", follow_symlinks=True)
    # We don't assert exact contents — just that the walk terminated.
    assert isinstance(out, list)


# ─── Path / PathLike input ───────────────────────────────────────────────────


def test_base_accepts_str_and_pathlike(tmp_path):
    """`base` accepts both str and Path."""
    (tmp_path / "a.txt").write_text("")
    via_str = find_all(str(tmp_path), "*.txt")
    via_path = find_all(tmp_path, "*.txt")
    assert via_str == via_path


# ─── Pattern edge cases ──────────────────────────────────────────────────────


def test_slash_doublestar_at_end(tmp_path):
    """`dir/**` matches anything under `dir/`."""
    (tmp_path / "keep").mkdir()
    (tmp_path / "keep" / "x.py").write_text("")
    (tmp_path / "keep" / "deep").mkdir()
    (tmp_path / "keep" / "deep" / "y.py").write_text("")
    (tmp_path / "other.py").write_text("")
    out = {p.name for p in find_all(tmp_path, "keep/**")}
    # Should include everything under keep/, plus the keep dir itself if
    # it matches; behaviour we want is "everything *inside* keep".
    assert "x.py" in out
    assert "y.py" in out
    assert "other.py" not in out


def test_bare_doublestar(tmp_path):
    """Bare `**` matches every path."""
    (tmp_path / "a").mkdir()
    (tmp_path / "a" / "x.py").write_text("")
    (tmp_path / "b.txt").write_text("")
    out = {p.name for p in find_all(tmp_path, "**")}
    assert out == {"a", "x.py", "b.txt"}


def test_is_dir_error_handled(tmp_path, monkeypatch):
    """When `DirEntry.is_dir()` raises, on_error is called and we move on."""
    (tmp_path / "a").mkdir()
    (tmp_path / "a" / "x.py").write_text("")
    (tmp_path / "b.py").write_text("")

    real_scandir = os.scandir

    class BrokenEntry:
        """Wrap a real DirEntry but make is_dir raise."""

        def __init__(self, inner):
            self._inner = inner
            self.name = inner.name
            self.path = inner.path

        def is_dir(self, follow_symlinks=True):
            if self.name == "a":
                raise PermissionError("simulated")
            return self._inner.is_dir(follow_symlinks=follow_symlinks)

        def is_symlink(self):
            return self._inner.is_symlink()

    class FakeScandirCM:
        def __init__(self, real_cm):
            self._real_cm = real_cm
            self._real_it = None

        def __enter__(self):
            self._real_it = self._real_cm.__enter__()
            return (BrokenEntry(e) for e in self._real_it)

        def __exit__(self, *args):
            return self._real_cm.__exit__(*args)

    def fake_scandir(path):
        return FakeScandirCM(real_scandir(path))

    monkeypatch.setattr(os, "scandir", fake_scandir)
    # With on_error='ignore' the bad entry is silently skipped.
    out = {p.name for p in find_all(tmp_path, "*.py", on_error="ignore")}
    # `a/x.py` should be missing (we couldn't recurse), `b.py` should be present.
    assert "b.py" in out
    assert "x.py" not in out
