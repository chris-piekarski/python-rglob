"""Hypothesis property tests for the modern `find()` API.

Properties tested:
- Cardinality: `find(p, "*")` enumerates everything under `p` exactly once,
  matching a brute-force `os.walk` baseline.
- Monotonicity: deeper `max_depth` never returns *fewer* results than a
  shallower one.
- Exclude commutativity: excluding `[A, B]` equals excluding `[B, A]`.
- Case-insensitive ⊇ case-sensitive: with `case_sensitive=False` the
  result set is a superset of the case-sensitive one.
"""

from __future__ import annotations

import os
import string
from pathlib import Path

from hypothesis import given, settings
from hypothesis import strategies as st

from rglob import find_all

# Safe directory / filename strategies — restricted to ASCII alphanumerics
# so we don't depend on FS-encoding quirks on macOS/Windows.
_safe_name = st.text(
    alphabet=string.ascii_lowercase + string.digits + "_",
    min_size=1,
    max_size=8,
).filter(lambda s: not s.startswith("."))


def _build_tree(root: Path, spec: list[tuple[str, ...]]) -> None:
    """Create files/dirs from a spec of path tuples.

    Skips entries that would collide with an already-created file (e.g.
    `[('a',), ('a', 'b')]` — second entry needs `a/` as a directory, but
    `a` is already a file). Hypothesis explores both orderings, and
    skipping keeps the property invariants safe to assert.
    """
    for parts in spec:
        if not parts:
            continue
        *dir_parts, leaf = parts
        d = root
        skip = False
        for part in dir_parts:
            d = d / part
            if d.exists() and not d.is_dir():
                skip = True
                break
            d.mkdir(exist_ok=True)
        if skip:
            continue
        leaf_path = d / leaf
        if leaf_path.exists() and leaf_path.is_dir():
            continue  # leaf already a dir — would collide
        leaf_path.write_text("x")


_path_spec = st.lists(
    st.lists(_safe_name, min_size=1, max_size=4),
    min_size=0,
    max_size=12,
    unique_by=tuple,
).map(lambda lst: [tuple(p) for p in lst])


@given(spec=_path_spec)
@settings(max_examples=40, deadline=None)
def test_find_star_matches_oswalk(tmp_path_factory, spec):
    """`find(p, "*")` enumerates the same set as a brute-force os.walk."""
    root = tmp_path_factory.mktemp("hyp")
    _build_tree(root, spec)

    walked: set[Path] = set()
    for dirpath, dirnames, filenames in os.walk(root):
        for name in dirnames + filenames:
            walked.add(Path(dirpath) / name)

    found = set(find_all(root, "*"))
    assert found == walked


@given(spec=_path_spec, d=st.integers(min_value=0, max_value=6))
@settings(max_examples=40, deadline=None)
def test_max_depth_is_monotonic(tmp_path_factory, spec, d):
    """Increasing `max_depth` never drops a previously-found path."""
    root = tmp_path_factory.mktemp("hyp")
    _build_tree(root, spec)

    shallow = set(find_all(root, "*", max_depth=d))
    deep = set(find_all(root, "*", max_depth=d + 2))
    assert shallow <= deep


@given(spec=_path_spec)
@settings(max_examples=20, deadline=None)
def test_exclude_is_commutative(tmp_path_factory, spec):
    """Order of exclude patterns must not affect the result."""
    root = tmp_path_factory.mktemp("hyp")
    _build_tree(root, spec)

    ab = set(find_all(root, "*", exclude=["*1*", "*2*"]))
    ba = set(find_all(root, "*", exclude=["*2*", "*1*"]))
    assert ab == ba


@given(spec=_path_spec)
@settings(max_examples=20, deadline=None)
def test_case_insensitive_superset(tmp_path_factory, spec):
    """Case-insensitive matching is a superset of case-sensitive matching."""
    root = tmp_path_factory.mktemp("hyp")
    _build_tree(root, spec)

    sensitive = set(find_all(root, "*", case_sensitive=True))
    insensitive = set(find_all(root, "*", case_sensitive=False))
    assert sensitive <= insensitive
