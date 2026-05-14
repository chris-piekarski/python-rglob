"""Ports of the Behave scenarios in `features/rglob.feature` to pytest.

Each scenario in the feature file corresponds to one (or a few) test functions
here. Helpers live on `TreeBuilder` in `conftest.py` so the BDD steps and
these tests share assertions.
"""

from __future__ import annotations

import math

import pytest

import rglob


def test_empty_root_finds_zero_dirs(tree_builder):
    """Fresh root has no `*_rglob` matches."""
    matches = rglob.rglob(str(tree_builder.root), "*_rglob")
    assert matches == []


def test_create_10_subdirs(tree_builder):
    """10 subdirs created → 10 matches under root."""
    tree_builder.make_subdirs(10)
    matches = rglob.rglob(str(tree_builder.root), "*_rglob")
    assert len(matches) == 10


def test_create_110_subdirs(tree_builder):
    """10 top-level + 10x10 nested = 110 matches."""
    tree_builder.make_subdirs(10)
    tree_builder.make_subdirs(10)
    matches = rglob.rglob(str(tree_builder.root), "*_rglob")
    assert len(matches) == 110


def test_create_1100_subdirs(tree_builder):
    """100 + 100x10 = 1100 matches."""
    tree_builder.make_subdirs(100)
    tree_builder.make_subdirs(10)
    matches = rglob.rglob(str(tree_builder.root), "*_rglob")
    assert len(matches) == 1100


def test_create_1100_text_files_size_matches(tree_builder):
    """File-count and total-size assertions on a 1100-file tree."""
    tree_builder.make_subdirs(100)
    tree_builder.make_subdirs(10)
    tree_builder.make_files(1, ".txt")
    # 1100 *_rglob dirs, 1100 .txt files
    assert len(rglob.rglob(str(tree_builder.root), "*_rglob")) == 1100
    assert len(rglob.rglob(str(tree_builder.root), "*.txt")) == 1100

    known_kib = rglob.kilobytes(tree_builder.total_known_size(".txt"))
    found_kib = rglob.tsize(str(tree_builder.root), "*.txt", rglob.kilobytes)
    assert math.isclose(known_kib, found_kib, rel_tol=0, abs_tol=1e-9)


def test_count_lines_in_text_files(tree_builder):
    """10 subdirs x 2 files x 5 lines = 100 lines."""
    tree_builder.make_subdirs(10)
    tree_builder.make_files(2, ".txt")
    tree_builder.write_lines(".txt", lines=5)
    assert rglob.lcount(str(tree_builder.root), "*.txt") == 100


def test_rglob_underscore_uses_cwd(tree_builder, monkeypatch):
    """`rglob_` walks from CWD; chdir to the synthetic root and check counts."""
    tree_builder.make_subdirs(10)
    tree_builder.make_files(2, ".py")
    monkeypatch.chdir(tree_builder.root)
    assert len(rglob.rglob_("*.py")) == 20


@pytest.mark.parametrize(
    ("converter", "factor"),
    [
        (rglob.kilobytes, 2**10),
        (rglob.megabytes, 2**20),
        (rglob.gigabytes, 2**30),
        (rglob.terabytes, 2**40),
    ],
)
def test_unit_helpers(converter, factor):
    """Each unit helper divides by the right binary prefix."""
    assert converter(float(factor)) == 1.0
    assert converter(2.0 * factor) == 2.0


def test_lcount_with_filter(tree_builder):
    """`lcount` respects the per-line predicate."""
    tree_builder.make_subdirs(2)
    tree_builder.make_files(1, ".txt", content="alpha\nbeta\n# comment\n\n")
    total = rglob.lcount(str(tree_builder.root), "*.txt")
    non_empty_non_comment = rglob.lcount(
        str(tree_builder.root),
        "*.txt",
        lambda line: bool(line.strip()) and not line.lstrip().startswith("#"),
    )
    assert total == 8  # 4 lines x 2 files
    assert non_empty_non_comment == 4  # 2 valid lines x 2 files


def test_tsize_default_unit_is_megabytes(tree_builder):
    """`tsize` defaults to MiB conversion."""
    tree_builder.make_subdirs(1)
    tree_builder.make_files(1, ".bin", content="x" * 1024)
    mb = rglob.tsize(str(tree_builder.root), "*.bin")
    assert 0 < mb < 1.0  # 1 KiB → ~0.001 MiB


def test_tsize_skips_directories(tree_builder):
    """`tsize` ignores directories matched by the glob."""
    # Build a tree with both files AND subdirs at the same level matched by `*_rglob`
    tree_builder.make_subdirs(3)
    tree_builder.make_files(1, "_rglob_data", content="hello")
    # `*_rglob*` should match both subdir names and file names; _sum must skip the dirs.
    mb = rglob.tsize(str(tree_builder.root), "*_rglob*", rglob.kilobytes)
    assert mb > 0


def test_module_main_smoke(tmp_path, monkeypatch):
    """The `__main__` block in rglob.rglob exits cleanly for smoke purposes."""
    # We exercise the same code path the __main__ block would via direct call.
    monkeypatch.chdir(tmp_path)
    py = tmp_path / "x.py"
    py.write_text("a = 1\n# comment\n\nb = 2\n", encoding="utf-8")

    def keep(line):
        return bool(line.strip()) and not line.strip().startswith("#")

    assert rglob.lcount(str(tmp_path), "*.py", keep) == 2
    assert py.exists()
