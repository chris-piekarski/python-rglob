# ADR-0006 · Aggregated 100% coverage

**Status**: Accepted · **Date**: 2026-05-14

## Context

The original plan said "`fail_under = 100`" applied to every CI job. With a
matrix of **4 Python versions × 3 OSes = 12 cells**, that constraint is
brittle:

- Phase 3 introduces `case_sensitive=None` (OS-dependent default), a
  `realpath`-memoised symlink loop check (POSIX-leaning), and an
  `on_error` branch for `PermissionError` on `/proc` (Linux-only).
- Forcing every cell to 100% pushes us toward sprinkling `# pragma: no
  cover` on legitimate platform branches or writing tests with elaborate
  `sys.platform` conditional skips.

Codecov's project-status gate already merges coverage across all matrix
cells. That merged report is the source of truth a reviewer would actually
look at.

## Decision

- **Local** (`make test`): `--cov-fail-under=100`. Single-OS runs see the
  full code surface (we always run on Linux locally), so 100% is achievable
  and enforced.
- **CI per-job**: `--cov-fail-under=95`. A regression on any single
  platform is loud but not catastrophic.
- **CI merged**: Codecov project status check enforces `target: 100%`
  on the aggregated report.
- **`# pragma: no cover`** is reserved for genuinely-unreachable lines
  (`if __name__ == "__main__":`, `if TYPE_CHECKING:`) and *cross-platform
  guards that no matrix cell covers*. Each pragma must have a one-line
  justification.

## Consequences

- A `if sys.platform == "win32":` branch is fine: covered by the Windows
  cell, contributing to the merged 100%.
- A `if sys.platform == "haiku":` branch is not fine: no matrix cell
  covers it. Either remove the branch or add a `# pragma: no cover —
  Haiku not in matrix` with reasoning.
- Codecov configuration (`codecov.yml`) lives at repo root — to be added
  alongside the Codecov badge.
