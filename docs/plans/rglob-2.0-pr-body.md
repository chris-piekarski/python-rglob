# rglob 2.0 — PR Summary

This page mirrors the body of [PR #6](https://github.com/chris-piekarski/python-rglob/pull/6),
preserved in-repo for historical reference. The PR description on GitHub
uses repo-root paths; this page uses doc-tree-relative paths so it renders
correctly under MkDocs.

## Summary

Top-to-bottom modernization shipping **rglob 2.0**, delivered across six
phases per [`modernization-roadmap.md`](modernization-roadmap.md):

1. **Packaging hygiene** — PEP 621 + hatchling, single-sourced `__version__`,
   `src/` layout, full doc set (CHANGELOG / CONTRIBUTING / SECURITY /
   CODE_OF_CONDUCT / AGENTS), ASCII-banner README with badges.
2. **Tooling overhaul** — ruff (lint + format) replaces pylint, mypy
   `--strict` with `py.typed`, pytest as primary suite (behave kept as
   parallel BDD job per [ADR-0007](../decisions/0007-behave-parallel.md)),
   aggregated 100% coverage via Codecov
   ([ADR-0006](../decisions/0006-aggregated-coverage.md)),
   three GitHub workflows (`ci.yml` 3.11–3.14 × ubuntu/macos/windows,
   `release.yml` OIDC trusted publishing, `docs.yml` gh-pages), MkDocs
   Material site with Mermaid diagrams, Makefile, pre-commit hooks,
   renovate, codecov.
3. **Core API on `os.scandir`** — new `find()` / `find_all()` with filters
   for `exclude` / `max_depth` / `hidden` / `follow_symlinks` /
   `case_sensitive` / `sort` / `on_error`, `**` recursive globs,
   symlink-loop detection via realpath memo
   ([ADR-0008](../decisions/0008-security-model.md)),
   deterministic sort-by-default, OS-aware case sensitivity, hypothesis
   property tests.
4. **Typer + Rich CLI** — byte-compatible `find` / `lcount` / `tsize`,
   plus new filter flags (`-E`, `-d`, `-H`, `-L`, case toggle), output
   formats (`--json`, `--jsonl`, `-0`, `--format`), shell pre-expansion
   detection, `--install-completion`, syrupy snapshot tests.
5. **Fun features** — new `stats` / `tree` / `top` / `dupes` subcommands;
   duplicate detection (size → 4-KiB hash → full hash) using
   `xxhash.xxh3_64` with BLAKE2b fallback; `.gitignore` awareness via
   pathspec; `--type` / `--min-size` / `--max-size` / `--newer-than` /
   `--older-than` filters.
6. **2.0 cleanup** — `__version__ = "2.0.0"`, `Development Status :: 6 - Mature`,
   migration guide at [`migrating-to-2.0.md`](../migrating-to-2.0.md),
   final public-API class diagram.

## Breaking change

- **`rglob()` and `rglob_()` now return `list[Path]`** (was `list[str]` in
  1.x). One-line migration:

  ```python
  paths = [str(p) for p in rglob(base, pattern)]
  ```

  See [migrating-to-2.0](../migrating-to-2.0.md) and
  [ADR-0003](../decisions/0003-path-return.md) for full context.

## Decisions captured as ADRs

- [0001 — build backend (hatchling)](../decisions/0001-build-backend.md)
- [0002 — Python 3.11 floor](../decisions/0002-python-floor.md)
- [0003 — `list[Path]` return at 2.0](../decisions/0003-path-return.md)
- [0004 — Typer + Rich for the CLI](../decisions/0004-typer-rich.md)
- [0005 — single 2.0.0 release strategy](../decisions/0005-single-release.md)
- [0006 — aggregated 100% coverage](../decisions/0006-aggregated-coverage.md)
- [0007 — behave kept as parallel BDD](../decisions/0007-behave-parallel.md)
- [0008 — security model](../decisions/0008-security-model.md)

## Test plan

- [x] `make lint` — ruff (lint + format) + mypy `--strict` clean
- [x] `make test` — pytest 119/119 passed @ **100%** local coverage, behave
      7/7 scenarios
- [x] `make build` — `hatch build` produces `rglob-2.0.0.tar.gz` and
      `rglob-2.0.0-py3-none-any.whl`
- [x] `make docs-build` — `mkdocs build --strict` clean
- [x] End-to-end CLI smoke (`rglob find --json`, `rglob stats`,
      `rglob dupes` with planted duplicates) all return expected output
- [ ] CI matrix (3.11–3.14 × ubuntu/macos/windows) — to confirm on the PR
- [ ] Codecov merged report hits 100% — to confirm on the PR
- [ ] Docs site renders on gh-pages — to confirm post-merge
- [ ] Dry-run `release.yml` against TestPyPI — to confirm separately before
      cutting `v2.0.0`

## Notes

- No tag pushed; the actual `v2.0.0` release is a follow-up (per the
  single-release strategy in
  [ADR-0005](../decisions/0005-single-release.md)).
- Branch protection on `master` should be enabled in repo settings before
  merge (CONTRIBUTING.md documents the required checks).
