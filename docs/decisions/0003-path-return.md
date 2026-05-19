# ADR-0003 · `rglob` returns `list[Path]` at 2.0

**Status**: Accepted · **Date**: 2026-05-14

## Context

Today `rglob.rglob()` returns `list[str]`. The Python ecosystem standardised
on `pathlib.Path` years ago; `os.scandir` (Phase 3's walker) is most
naturally consumed as `Path` instances; and downstream filters
(`min_size`, `--gitignore`) want `Path` semantics. The legacy `str` return
is a friction point in every example.

## Decision

At 2.0, `rglob()` and `rglob_()` return **`list[Path]`** instead of
`list[str]`. The new `find()` / `find_all()` family also yields/returns
`Path`. This is the **only intentional breaking change** in the 2.0
release.

## Consequences

- One-line migration for users:
  ```python
  paths = [str(p) for p in rglob("/tmp", "*.txt")]
  ```
- Phase 6 includes a dedicated "Migrating to 2.0" docs page and CHANGELOG
  call-out.
- Internally the wrappers stop doing `Path → str` coercion; everything is
  `Path` end-to-end.
- We considered shipping a `rglob_str()` alias for migration but rejected
  it — adds a forever-deprecated symbol for a one-line wrap.
