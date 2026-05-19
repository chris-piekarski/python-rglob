# ADR-0008 · Security model

**Status**: Draft (locked at Phase 3) · **Date**: 2026-05-14

## Context

`rglob` walks filesystems. The Phase 3 walker rewrite adds:

- `follow_symlinks=False` (default) → `True` (opt-in) symlink traversal
- a `realpath`-keyed memo to terminate symlink cycles
- `respect_gitignore` (Phase 5) reading `.gitignore` files top-down
- `on_error="ignore"|"warn"|"raise"` covering `PermissionError`,
  `OSError`, `UnicodeDecodeError`

Each of these is a small surface; together they are a security model worth
writing down so we don't drift.

## Threat model

**In scope**

- *Symlink escape*: a follow-enabled walk should never visit a path whose
  `realpath` lies outside the user-supplied `base`. Currently we **do not
  enforce this** by default; users opt into `follow_symlinks=True`
  knowing what it means. A future flag (`strict_base=True`) could enforce
  containment.
- *Symlink loops*: a `realpath` memo terminates `a → b → a` and longer
  cycles. The memo is scoped per `find()` call (no cross-call leaks) and
  uses `os.path.realpath` (not `Path.resolve(strict=True)`) so dangling
  links don't raise.
- *`.gitignore` containment*: `respect_gitignore` only reads
  `.gitignore` files **at or below** `base`. It never traverses upward.

**Out of scope**

- *TOCTOU between `scandir` and `lstat`*: the walker uses cached
  `DirEntry` metadata where possible; we do not snapshot the FS. A
  malicious local user racing the walk can cause it to surface or miss
  entries — this is inherent to filesystem walkers and not something we
  can fix without a kernel-side lock.
- *Arbitrary code execution*: `rglob` never executes content it discovers.
  Predicate callbacks (`lcount(..., func=...)`) run user code by design,
  not by accident.

## Mitigations

- Default `follow_symlinks=False`.
- Per-call `realpath` memo for cycle termination.
- `respect_gitignore` traversal is `base`-rooted, never upward.
- `on_error="warn"` (default) prints to `stderr` rather than terminating
  on unreadable entries; users opt into `"raise"` for strict pipelines.
- `tests/test_symlinks.py` builds a cycle and asserts termination.

## Reporting

Vulnerability reports go via the project's
[security policy](https://github.com/chris-piekarski/python-rglob/security/policy)
(GitHub private security advisories).
