# Changelog

All notable changes to `rglob` will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0.0] – 2026-05-14

The 2.0 release lands a top-to-bottom modernization across six phases. See
[`docs/plans/modernization-roadmap.md`](docs/plans/modernization-roadmap.md)
for the full plan and [`docs/migrating-to-2.0.md`](docs/migrating-to-2.0.md)
for the one-line `str ↔ Path` migration.

### Changed — Breaking (Phase 6)
- **`rglob()` and `rglob_()` now return `list[Path]`** (was `list[str]` in
  1.x). Migration is one line: `[str(p) for p in rglob(...)]`. See
  [migrating-to-2.0.md](docs/migrating-to-2.0.md) and ADR-0003 for context.
- Version bumped to `2.0.0`; `Development Status` classifier raised to
  `6 - Mature`.

### Added (Phase 1 — Packaging hygiene)
- PEP 621 metadata in `pyproject.toml` with `hatchling` build backend.
- Single-source `__version__` in `src/rglob/__init__.py` (currently `2.0.0.dev0`).
- `src/` layout — package now lives at `src/rglob/`.
- `CHANGELOG.md`, `CONTRIBUTING.md`, `SECURITY.md`, `CODE_OF_CONDUCT.md`.
- Top-level ASCII banner in `README.md`; refreshed badges and sections.

### Changed (Phase 1)
- Minimum Python version raised from 3.5 to **3.11** (3.10 reaches EOL October
  2026 — the 2.0 release ships on a forward-looking floor).
- `setup.py` deleted; all metadata now in `pyproject.toml`.
- Trove classifiers refreshed (3.11–3.14, `Topic :: System :: Filesystems`,
  `Environment :: Console`, `Typing :: Typed`, `Development Status :: 5 - Production/Stable`).
- `.gitignore` expanded to cover modern Python dev artefacts (`dist/`, `.venv/`,
  `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`, coverage outputs, etc.).
- README rebuilt with an ASCII banner, badges row, refreshed sections, and the
  legacy `**`/sorted-paths disclaimers removed (both behaviours flip in Phase 3).

### Added (Phase 2 — Tooling overhaul)
- Ruff (lint + format) replaces pylint with a curated lint preset (`E`, `F`,
  `W`, `I`, `B`, `UP`, `SIM`, `RUF`, `PTH`, `PERF`, `D`).
- mypy `strict = true` on `src/rglob` with a `py.typed` marker.
- Pytest test suite ported from the Behave scenarios; `tests/` is now the
  primary suite. Behave runs in parallel (see ADR-0007).
- Aggregated 100% coverage gate (see ADR-0006): local enforces `--cov-fail-under=100`,
  CI per-job uses 95% with the Codecov merged report at 100%.
- New GitHub workflows: `ci.yml` (matrix 3.11–3.14 × ubuntu/macos/windows),
  `release.yml` (OIDC PyPI publishing), `docs.yml` (gh-pages deploy).
- MkDocs Material site with Mermaid support, mkdocstrings API page, ADR
  collection in `docs/decisions/`.
- `Makefile` with `help`, `build`, `lint`, `test`, `fmt`, `docs`, `docs-build`,
  `dev-setup`, and `clean` targets.
- `.pre-commit-config.yaml` (ruff, mypy, pyproject-fmt, hygiene hooks).
- `renovate.json` (weekly schedule, dependency dashboard).
- `[project.optional-dependencies]`: `dev`, `bdd`, `docs`, `gitignore`, `ext`,
  `bench`.

### Removed (Phase 2)
- `.coveragerc` (config moved to `[tool.coverage.*]` in `pyproject.toml`).
- `requirements-dev.txt` (replaced by optional extras).
- `.github/workflows/pylint.yml` (replaced by `ci.yml`).
- pylint sections in `pyproject.toml`.

### Added (Phase 3 — Core API on `os.scandir`)
- New canonical API: `find(base, patterns, *, exclude=(), max_depth=None,
  hidden=False, follow_symlinks=False, case_sensitive=None, sort=True,
  on_error="warn") -> Iterator[Path]` and `find_all(...) -> list[Path]`.
- `**` recursive glob support (`find_all("src", "**/*.py")`).
- Symlink loop detection via per-call `os.path.realpath` memo.
- Deterministic sort-by-default ordering; opt-out via `sort=False`.
- OS-default case sensitivity (`case_sensitive=None`): case-sensitive on
  Linux, case-insensitive on macOS/Windows.
- Error handling knob (`on_error="ignore"|"warn"|"raise"`) covers
  `PermissionError`, `OSError`, `UnicodeDecodeError`.
- Hypothesis property tests: cardinality vs `os.walk`, `max_depth`
  monotonicity, exclude commutativity, case-sensitive ⊆ case-insensitive.

### Changed (Phase 3)
- Walker internals rewritten on `os.scandir` (drops a `stat()` per entry by
  reading cached `DirEntry.d_type`).
- Legacy `rglob` / `rglob_` / `lcount` / `tsize` now thin wrappers over
  `find()` — return types unchanged (`list[str]` / `int` / `float`).
- Dropped `from __future__ import annotations` from `src/rglob/rglob.py`
  (PEP 604 unions work natively on the 3.11 floor).

### Added (Phase 4 — CLI overhaul on Typer + Rich)
- CLI rewritten on Typer; `find` / `lcount` / `tsize` keep their legacy
  flags (`--base`, `--no-empty`, `--no-comments`, `--unit`) byte-compatibly.
- New `find` filter flags: `-E/--exclude`, `-d/--max-depth`, `-H/--hidden`,
  `-L/--follow`, `-s/-i / --case-sensitive/--case-insensitive`,
  `--gitignore/--no-gitignore` (stub — full behaviour lands in Phase 5).
- New `find` output formats: `--json` (array), `--jsonl` (object per line),
  `-0/--null` (for `xargs -0`), `--format TEMPLATE` (mini-template with
  `path`, `rel`, `name`, `size`, `size_kb`, `size_mb` fields).
- Rich integration: coloured help, coloured warnings (e.g. shell
  pre-expansion detection). `NO_COLOR` is respected automatically by Rich.
- Multiple positional patterns on `find` are OR'd
  (`rglob find "*.py" "*.pyx"`).
- `rglob` now warns to stderr when called with multiple positional
  arguments that look pre-expanded by the shell.
- Shell completion via Typer:
  `rglob --install-completion {bash,zsh,fish,powershell}`.
- `docs/cli.md` now renders the auto-generated command tree via
  `mkdocs-typer2`.
- Snapshot tests via `syrupy` (`tests/test_cli.py`) cover the find /
  lcount / tsize golden outputs.

### Added (Phase 5 — Fun features)
- Tier 2 filters wired into both `find()` and the `find` CLI command:
    - `min_size`/`max_size` accepting `int | float | str` ("1K", "5MiB", etc.).
    - `newer_than`/`older_than` accepting `datetime | timedelta | str`
      ("7d", "2024-01-01", etc.).
    - `kinds: set[Literal["f","d","l","x"]]` (file/dir/symlink/executable).
- `.gitignore` awareness via the optional `pathspec` extra
  (`pip install rglob[gitignore]`). New `respect_gitignore: bool = False`
  kwarg on `find()`; `--gitignore/--no-gitignore` flag on `rglob find`.
- New CLI subcommands:
    - `rglob stats <pattern>` — summary table (count, size, extension breakdown).
    - `rglob tree <pattern>` — Rich-rendered Unicode tree (default depth 3).
    - `rglob top <pattern> -n N` — top-N largest files.
    - `rglob dupes <pattern>` — duplicate-file detection (size → 4-KiB hash
      → full hash). Uses `xxhash` when installed (`pip install rglob[ext]`),
      stdlib BLAKE2b otherwise.
- New `find` CLI flags: `-t/--type`, `--min-size`, `--max-size`,
  `--newer-than`, `--older-than`.
- New internal modules: `src/rglob/_filters.py` (size/time/kind parsers and
  predicates, `.gitignore` matcher) and `src/rglob/_dupes.py`
  (duplicate-finding pipeline).

### Added (Agent platform Phase 0 — Contract and schemas)
- ADR-0009 documents the SemVer-locked agent API contract for `rglob.agent`,
  structured CLI JSON, JSON Schemas, and MCP tools.
- ADR-0010 documents the read-only safety model for agent and MCP use:
  base containment, symlink behavior, content disclosure, binary files,
  unreadable paths, output limits, and cooperative timeouts.
- New frozen, slotted contract models in `src/rglob/agent/_models.py`:
  `FileMatch`, `LineMatch`, `Stats`, `Duplicate`, `ErrorInfo`, `ErrorCode`,
  concrete search result envelopes, capability reports, and option models.
- Runtime JSON Schema Draft 2020-12 generation from
  `src/rglob/agent/_models.py`, exposed through `rglob.agent.schema_for`,
  `rglob.agent.all_schemas`, `rglob schema <subcommand>`, and
  `rglob schema --all`.
- New machine-readable CLI endpoints:
  `rglob describe <subcommand>`, `rglob schema <subcommand>`,
  `rglob capabilities --json`, and `rglob agent-version`.
- `rglob find --json` now emits a `FileSearchResult` object instead of a
  string array. `rglob find --jsonl` emits the same result shape as one
  compact JSON object line.
- New shared golden fixture tree at `tests/fixtures/agent-tree/` for agent
  contract, binary, hidden-file, gitignore, unreadable-path, and duplicate
  scenarios.

### Added (Agent platform Phase 1 — Scope expansion)
- New `rglob grep` command and `src/rglob/_grep.py` content matcher returning
  `LineSearchResult` records.
- New `rglob count` command and structured `Stats` output for files, lines,
  and bytes.
- `find()` and `rglob find` gained `--perm`, `--uid`, `--gid`, and
  `--newer-than-file` predicates.
- `rglob grep` supports fixed strings, ignore-case, context, max-count,
  word, invert, encoding, binary-as-text, limits, and JSON / JSONL output.

### Added (Agent platform Phase 2 — Python API)
- New stable `rglob.agent` namespace exporting the agent dataclasses,
  `__agent_api_version__`, `search`, `search_all`, `grep`, `grep_all`,
  `count`, and `find_duplicates`.
- Agent API operational errors are represented as `ErrorInfo` records instead
  of raising for bad predicates, unreadable files, binary skips, and regex
  failures.

### Added (Agent platform Phase 3 — MCP)
- New optional `mcp` extra: `pip install "rglob[mcp]"`.
- New `rglob mcp` command and `src/rglob/agent/mcp.py` stdio MCP server.
- MCP tools: `find_files`, `grep_content`, `count_lines`,
  `find_duplicate_files`, and `describe_subcommand`.

### Added (Agent platform Phase 4 — Documentation)
- New `docs/agents/` pages for Python API usage, MCP setup, CLI recipes,
  stability, and safety.
- New `docs/examples/agent-recipes.md` with copy-paste agent workflows.
- `AGENTS.md` now includes consumer guidance for agents using `rglob`, in
  addition to contributor instructions for agents editing this repository.

## Historical releases (pre-2.0)

Earlier releases (`1.2`–`1.7`, plus a `v1.8` tag with no matching source bump)
were published to PyPI without a structured changelog. See the
[PyPI release history](https://pypi.org/project/rglob/#history) for the rough
timeline.
