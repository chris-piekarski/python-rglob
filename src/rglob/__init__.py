"""Public API for the `rglob` package.

The 2.0 surface exposes:

- :func:`find` / :func:`find_all` — the modern Path-yielding API
- :func:`rglob` / :func:`rglob_` — legacy wrappers that now return
  ``list[Path]`` at 2.0 (see ADR-0003)
- :func:`lcount` / :func:`tsize` — line-count and size aggregation helpers
- :func:`kilobytes` / :func:`megabytes` / :func:`gigabytes` / :func:`terabytes`
  — binary-prefix conversion helpers

The agent-facing API lives in :mod:`rglob.agent` (SemVer-locked, see
ADR-0009) and the CLI lives in :mod:`rglob.cli`.
"""

from rglob.rglob import (
    find,
    find_all,
    gigabytes,
    kilobytes,
    lcount,
    megabytes,
    rglob,
    rglob_,
    terabytes,
    tsize,
)

__version__ = "2.0.0"

__all__ = [
    "__version__",
    "find",
    "find_all",
    "gigabytes",
    "kilobytes",
    "lcount",
    "megabytes",
    "rglob",
    "rglob_",
    "terabytes",
    "tsize",
]
