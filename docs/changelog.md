# Changelog

The canonical changelog lives at [`CHANGELOG.md`][src] in the repo root and
follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) /
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

[src]: https://github.com/chris-piekarski/python-rglob/blob/master/CHANGELOG.md

## What's accreting toward 2.0

The 2.0 release accumulates across the six modernization phases described in
the [roadmap](plans/modernization-roadmap.md). At a glance:

- **Phase 1** — Packaging hygiene: PEP 621 metadata, `src/` layout, single-sourced
  `__version__`, `.gitignore`, refreshed docs.
- **Phase 2** — Tooling: Ruff/Mypy/Pytest, 100% aggregated coverage, MkDocs
  Material, three GitHub workflows, `Makefile`.
- **Phase 3** — `find()` / `find_all()` on `os.scandir`, `**` globbing,
  symlink-loop detection, hypothesis property tests.
- **Phase 4** — Typer + Rich CLI rewrite with filter flags and output formats.
- **Phase 5** — Fun features: `stats` / `tree` / `top` / `dupes`,
  `.gitignore` awareness.
- **Phase 6** — Breaking change: `rglob()` / `rglob_()` return `list[Path]`.
  Final v2.0.0 release.

For per-phase detail, see [`CHANGELOG.md`][src] at the repo root.
