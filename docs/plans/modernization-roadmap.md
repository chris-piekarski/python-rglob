# `python-rglob` Modernization & Feature Expansion

## Context

`python-rglob` is a ~120-LOC hobby package Chris built ~5–6 years ago when Python 2 had no decent recursive-glob story. It was upgraded to Python 3 but otherwise hasn't evolved: hand-rolled recursion via `glob.iglob`, no `pathlib`, lists not generators, no type generics, no symlink/hidden/`.gitignore` handling, argparse CLI, pylint-only CI, behave BDD tests with no pytest, `setup.py`-driven metadata, committed `egg-info`, and a `1.7` source / `v1.8` tag drift. Modern alternatives exist (`pathlib.Path.rglob`, `fd`, `wcmatch`), and that's fine — this repo is a labor of love, and the redundancy is the point.

The goal is to (a) drag the project up to current best practices and (b) borrow the popular features that make `fd`/`ripgrep`/`wcmatch` fun to use, while keeping each phase small enough to enjoy on a weekend. Each phase ships independently and leaves `main` releasable.

**Decisions locked in**: Python **3.11 floor** (3.10 reaches EOL in October 2026 — bumping ahead of EOL keeps us forward-looking); `rglob()` returns `list[Path]` at 2.0; Typer + Rich for the CLI; full six-phase scope; **single version bump to `2.0.0` after all six phases land** (no intermediate PyPI releases). During development the source version stays at PEP 440 `"2.0.0.dev0"` so installs are clearly marked as work-in-progress.

**Sensible defaults applied without asking**: Ruff replaces pylint; skip async; keep `behave` as a parallel BDD job (it's charming, with the understood maintenance cost that scenarios will rot first — call out in a decisions ADR); `hatchling` build backend; `src/` layout; MkDocs Material; Renovate over Dependabot; Codecov for coverage (aggregated across the matrix — see Phase 2 coverage notes); OIDC trusted publishing to PyPI.

---

## Phase 1 — Packaging hygiene

Pure plumbing. Zero behaviour change. Clears the runway for everything else.

**Tasks**
- Migrate metadata from `setup.py` to PEP 621 `[project]` in `pyproject.toml`; build backend = `hatchling`. Delete `setup.py`.
- Single-source `__version__ = "2.0.0.dev0"` in `src/rglob/__init__.py`; `[tool.hatch.version] path = "src/rglob/__init__.py"`. Closes the 1.7/v1.8 drift and signals WIP until Phase 6.
- Bump `requires-python = ">=3.11"`; refresh trove classifiers (drop 3.5, add 3.11–3.14, add `Topic :: System :: Filesystems`, `Environment :: Console`, `Typing :: Typed`).
- Repo layout: `git mv rglob/ src/rglob/`. Update import paths in `features/steps/steps.py` (no change needed — it imports the installed package).
- `git rm -r --cached rglob.egg-info/`. Update `.gitignore` to also list `dist/`, `build/`, `.venv/`, `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`, `.coverage*`, `htmlcov/`.
- Add `CHANGELOG.md` (Keep a Changelog format with a single `[Unreleased]` section that accretes through Phases 1–5), `CONTRIBUTING.md` (install/test/lint; reference `src/rglob` paths only — no `setup.py` left to mention), `SECURITY.md` (one-line: GitHub private advisories, expanded with the symlink/path-traversal threat model in Phase 3), `CODE_OF_CONDUCT.md` (Contributor Covenant 2.1 drop-in).
- README overhaul (the README is a first-class artifact, kept accurate through every phase):
  - **Top-level ASCII banner** at the very top — a `figlet`/`pyfiglet`-style "rglob" banner in a fenced code block (font: `slant` or `ANSI Shadow`; pick whichever reads best in a GitHub-rendered monospace block).
  - Tagline + badges row directly under the banner: PyPI / Python versions / CI / Codecov / license / ruff / "code style: ruff".
  - Accuracy pass: drop or rewrite anything that's wrong post-modernization (today's README claims `**` isn't supported and "paths are not guaranteed to be sorted" — both flip in Phase 3; update with each phase that touches the API).
  - Sections: Why use this? (lean into "modern alternatives exist — that's part of the fun"), Install, Quick Start (Python API), Quick Start (CLI), Compatibility, Links to full docs (`docs/`), Development, License.
  - Add a "Documentation" section linking to the MkDocs site (set up in Phase 2) and to `docs/architecture.md`.

**Critical files**: `pyproject.toml`, `src/rglob/__init__.py`, `.gitignore`, `CHANGELOG.md`, `README.md`.

**Acceptance**: `pip install -e .` works; `python -c "import rglob; print(rglob.__version__)"` prints `2.0.0.dev0`; existing pylint CI still passes (we replace it in Phase 2). No tag, no PyPI release.

---

## Phase 2 — Tooling overhaul

Build the dev loop you'll want to live in for the rest of the phases. `release.yml` is wired up here but no tag is cut until Phase 6.

**Tasks**
- Replace pylint with **ruff** (lint + format) in `pyproject.toml`:
  - `[tool.ruff.lint] select = ["E","F","W","I","B","UP","SIM","RUF","PTH","PERF","D"]`, pydocstyle convention `"google"`.
  - Delete the pylint `[tool.pylint.*]` sections; uninstall pylint.
- Add **mypy** with `strict = true` on `src/rglob`; ship a `src/rglob/py.typed` marker.
- Add `.pre-commit-config.yaml`: ruff, mypy, check-yaml, check-toml, end-of-file-fixer, trailing-whitespace, pyproject-fmt.
- Add **pytest** in `tests/`: port the behave step logic into pytest functions using `tmp_path` and `monkeypatch`. Keep `features/` as a parallel BDD suite; have its steps call the same helpers `tests/` use.
- Coverage via `coverage[toml]` configured in `pyproject.toml` (delete `.coveragerc` — Phase 1 hangover). **Target 100% on the *aggregated* report (Codecov merges all matrix jobs).** Per-job `fail_under` is set to **95%** so any single-OS regression is loud but doesn't false-alarm on platform-conditional branches; the *merged* report is what must be 100% green (enforced via the Codecov `target: 100%` project gate). Use `# pragma: no cover` only for genuinely un-coverable lines (e.g., `if __name__ == "__main__":` guards, `if sys.platform == "win32"` blocks that the corresponding OS job *does* cover but Linux runs can't see). Every pragma must have a one-line justification comment. Codecov upload + badge.
- Replace `.github/workflows/pylint.yml` with three workflows:
  - `ci.yml`: matrix `python-version: [3.11, 3.12, 3.13, 3.14]` × `os: [ubuntu, macos, windows]`. Steps: `uv sync --all-extras --dev` (or fallback `uv pip install -e .[dev,bdd,docs,gitignore]`), `ruff check`, `ruff format --check`, `mypy --strict src/rglob`, `pytest --cov --cov-fail-under=95`, `behave`, upload coverage to Codecov. **All steps are gating** — a failure on any of lint / type / test / per-job-coverage blocks merge. The Codecov *project* status check enforces the 100% aggregated bar.
  - `release.yml` (on `v*` tag): `hatch build` → PyPI via OIDC trusted publishing → GitHub Release from CHANGELOG slice.
  - `docs.yml` (on push to main): MkDocs Material build + deploy to `gh-pages`.
- **Enforce lint + tests via GitHub branch protection on `master`**: required status checks include all matrix `ci / test (*)` jobs and `ci / lint`; require PRs (no direct push); require linear history; require up-to-date branches before merging. One-time setup in repo settings → Branches (document the exact settings in `CONTRIBUTING.md`).
- `pre-commit install` is the local first line of defence — ruff, mypy, and a `pytest -x --no-cov` quick run on staged-file-related tests so lint/test failures get caught before push.
- Add `renovate.json` (preset `config:base`, schedule weekly).
- Add MkDocs Material skeleton with **Mermaid support** enabled:
  - `mkdocs.yml` — theme `material`, navigation, and `markdown_extensions: [pymdownx.superfences]` with a `mermaid` custom fence so ` ```mermaid ` blocks render natively.
  - `docs/index.md` — landing page mirroring README (without the duplicated banner).
  - `docs/api.md` — auto-generated from docstrings via `mkdocstrings[python]`.
  - `docs/cli.md` — placeholder; gets real content via `mkdocs-typer2` (the actively-maintained Typer doc plugin; the older `mkdocs-click` bridge required `typer.main.get_command()` and is now redundant) once CLI migrates in Phase 4.
  - `docs/architecture.md` — design overview seeded with Mermaid diagrams in this phase, expanded in each later phase (see "Architecture diagrams" below).
  - `docs/decisions/` — lightweight ADR-style notes capturing the decisions locked in this plan (build backend, Python 3.11 floor, Path return at 2.0, Typer + Rich, single-release strategy, aggregated 100% coverage target, behave-as-parallel-suite trade-off).
  - `docs/contributing.md` — includes `CONTRIBUTING.md` via `mkdocs` snippet plugin (single source of truth).
  - `docs/plans/` — this plan lives here; later plans can land alongside it.
- **Architecture diagrams in `docs/architecture.md`** (added incrementally per phase; all in Mermaid so they render on GitHub and the docs site):
  - **Phase 2**: package layout (`graph TD` of `src/rglob/`, `tests/`, `features/`, `docs/`, `.github/workflows/`) showing module relationships and CI flow.
  - **Phase 3**: walker call-graph (`flowchart` of `find` → scandir → match → filter → yield) and symlink-loop detection sequence diagram.
  - **Phase 4**: CLI command hierarchy (`graph TD` of `rglob` → subcommands → shared filter options); rendered Rich output layout.
  - **Phase 5**: `dupes` pipeline (`flowchart LR`: size bucket → 4 KB hash bucket → full hash bucket); `.gitignore` pruning sequence.
  - **Phase 6**: public API surface (Mermaid `classDiagram`) showing the final 2.0 shape.
- Rewrite `Makefile` with the user-required quartet plus a few essentials. Default goal is `help` (typing bare `make` prints the menu):
  - `make help` — auto-discovered list of targets with one-line descriptions (using `## ` doc-comment convention parsed by an awk one-liner).
  - `make build` — `hatch build` produces sdist + wheel into `dist/`.
  - `make lint` — `ruff check .` and `ruff format --check .` and `mypy --strict src/rglob` (gating; non-zero exit on any failure).
  - `make test` — `pytest --cov --cov-fail-under=100` and `behave` (gating; the local run sees a full single-OS profile, so 100% is enforced locally — CI relaxes per-job to 95% because the matrix splits coverage across OSes).
  - `make fmt` — `ruff format .` and `ruff check --fix .`.
  - `make docs` — `mkdocs serve` (live preview on `:8000`); `make docs-build` for a static build.
  - `make dev-setup` — installs `.[dev,bdd,docs,gitignore]` and runs `pre-commit install`.
  - `make clean` — removes `dist/`, `build/`, `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`, `htmlcov/`, `.coverage*`, `site/` (mkdocs).
- Refresh `requirements-dev.txt` → `[project.optional-dependencies]` in `pyproject.toml`: `dev`, `bdd`, `docs`, `gitignore` (Phase 5), `ext` (Phase 6 stretch) as separate extras.

**Critical files**: `pyproject.toml`, `.pre-commit-config.yaml`, `.github/workflows/{ci,release,docs}.yml`, `tests/test_*.py` (new), `mkdocs.yml`, `docs/architecture.md` (new, with Mermaid), `docs/index.md`, `docs/api.md`, `docs/cli.md`, `docs/contributing.md`, `docs/decisions/*.md`, `Makefile`, `README.md`.

**Acceptance**: `make help` lists every target with descriptions; `make lint test build docs` all green locally with **100% local coverage**; CI matrix green on PRs; **aggregated coverage = 100%** on Codecov merged report with every `# pragma: no cover` justified; branch protection on `master` blocks a PR with a failing test or lint; docs site at `https://chris-piekarski.github.io/python-rglob/` renders Mermaid diagrams correctly (verify by viewing `architecture.md`); one round-trip dry-run of `release.yml` against **TestPyPI** confirms OIDC config (no tag pushed to real PyPI yet).

---

## Phase 3 — Core API additions (additive only)

Rewrite internals on `os.scandir`; keep `rglob(base, pattern) -> list[str]` byte-compatible with today's signature; introduce the new `find()` family. Tier 1 features only. All changes accrete into the `[Unreleased]` section of CHANGELOG.

**Tasks**
- Rewrite the walker in `src/rglob/rglob.py` on `os.scandir` with recursion. `os.scandir` returns `is_dir()`/`is_symlink()` from cached `dirent.d_type` — drops a `stat()` per entry. Drop `_get_dirs` + `glob.iglob`.
- Keep existing functions working unchanged: `rglob(base, pattern) -> list[str]`, `rglob_(pattern) -> list[str]`, `lcount`, `tsize`, `kilobytes`/`megabytes`/`gigabytes`/`terabytes`. These become thin wrappers that coerce `Path → str` and `list(generator)`.
- New canonical API in `src/rglob/rglob.py`:
  - `find(base, patterns, *, exclude=(), max_depth=None, hidden=False, follow_symlinks=False, case_sensitive=None, sort=True, on_error="warn") -> Iterator[Path]`
  - `find_all(...) -> list[Path]` (just `list(find(...))`)
  - Accept `str | os.PathLike[str]` for `base`; accept `str | Sequence[str]` for `patterns`.
- `**` recursive glob support: per-component `fnmatch` matching instead of relying on `glob.glob`. Today's README disclaims `**` — flip that.
- Symlink loop detection via a visited-`os.path.realpath` memo. Realpath (not `Path.resolve(strict=True)`) so we don't choke on dangling links; symlink loops terminate; the memo is scoped per `find()` call to avoid cross-call leaks. Add a security ADR in `docs/decisions/` describing the threat model: in-scope = symlink-escape and traversal *outside* the user-supplied `base`; out-of-scope = TOCTOU between `scandir` and `lstat`; mitigations = `follow_symlinks=False` default, realpath memo, `respect_gitignore` never reads files outside `base`. Add a unit test that builds a symlink cycle and asserts termination.
- Deterministic ordering: `sort=True` by default (current behaviour is undocumented "whatever scandir returns" — flip to documented "sorted by path"). README today warns "not guaranteed sorted"; we promise sorted, opt-out via `sort=False`.
- `case_sensitive=None` follows the OS (case-insensitive on Windows/macOS by default), matching `pathlib.PurePath.match` in 3.12+.
- Error handling: `on_error: Literal["ignore","warn","raise"] = "warn"`. Catches `PermissionError`, `OSError`, `UnicodeDecodeError` on entry names. Today's code would explode on `/proc` or a permission-denied dir.
- Modern type hints: PEP 604 unions, `collections.abc` for `Iterable`/`Iterator`/`Sequence`. Drop `from __future__ import annotations` — with the 3.11 floor, PEP 604 unions and built-in generics work natively at runtime, so the future-import is just dead weight. (Typer-compat concerns from older versions no longer apply; Typer ≥0.9 handles stringified annotations correctly.)
- Update `src/rglob/__init__.py` to export `find`, `find_all` alongside the legacy names.
- Hypothesis property tests in `tests/test_properties.py`:
  - `find(p, "*")` cardinality matches a brute-force `os.walk` reference.
  - Monotonicity in `max_depth`.
  - Exclude-pattern commutativity.
  - `case_sensitive=False` set ⊇ `case_sensitive=True` set.
- Docs: new "Modern API" page; mark old API as "legacy (still supported)"; expand `docs/architecture.md` with the walker call-graph + symlink-loop sequence diagrams in Mermaid.
- README: update Quick Start examples to feature `find()`/`find_all()` alongside the legacy `rglob()`; remove the "`**` is not supported" disclaimer; flip the "paths not guaranteed sorted" note to "paths sorted by default; pass `sort=False` for raw scandir order".

**Critical files**: `src/rglob/rglob.py`, `src/rglob/__init__.py`, `tests/test_find.py` (new), `tests/test_properties.py` (new), `docs/api.md`, `docs/architecture.md`, `README.md`.

**Acceptance**: every existing behave scenario still passes unchanged; new pytest+hypothesis tests cover the new flags; **aggregated coverage stays at 100%** (new code is fully exercised); `find()` benchmark on a 10k-file synthetic tree (10 dirs × 1000 files, mean depth 3, **warm FS cache**, 5 runs, comparing `pytest-benchmark` *median*) is **≥2× faster** than the legacy `rglob()` on Linux ext4/tmpfs (scandir win — the relevant scenario for everyday use); `mypy --strict` clean; README + architecture diagrams reflect the new API.

---

## Phase 4 — CLI overhaul

Migrate argparse → **Typer + Rich**. Keep existing subcommand surface byte-compatible; layer on all the new Phase 3 filters.

**Tasks**
- Rewrite `src/rglob/cli.py` on Typer. Keep `find`, `lcount`, `tsize` subcommands and their existing flags (`--base`, `--no-empty`, `--no-comments`, `--unit`).
- Add filter flags mirroring the core: `--exclude/-E` (multi), `--max-depth/-d`, `--hidden/-H`, `--follow/-L`, `--type/-t {f,d,l,x}`, `--size +1M -10M` (fd-style range), `--newer-than`/`--older-than` (accept `7d`, `2024-01-01`, etc.), `--gitignore/--no-gitignore` (stub for Phase 5), `--case-sensitive/-s`.
- Output formats: default one-path-per-line (unchanged); `--json` / `--jsonl`; `-0`/`--null` for `xargs -0` safety; `--format` mini-template (`"{path} {size:human}"`).
- Rich integration: colored help, colored output, auto-progress bar on stderr if walk >0.5s and TTY-attached. Respect `NO_COLOR`.
- Auto-detect "this pattern looks pre-expanded by the shell" (positional has no `*`/`?` and multiple positionals) and emit a friendly warning. Keep the current epilog quoting note.
- Snapshot tests with `syrupy` covering `find`, `lcount`, `tsize`, and the new output formats.
- Shell completion: document `rglob --install-completion {bash,zsh,fish,powershell}`.
- Update `pyproject.toml` deps: add `typer`, `rich`. Update `docs/cli.md` to use **`mkdocs-typer2`** (`::: mkdocs-typer2` directive pointed at the Typer app; no Click bridge required).
- README: rewrite the CLI section with the new flags, output formats, and a section on shell completion. Keep the legacy CLI examples working — they still do.
- Extend `docs/architecture.md` with the CLI command hierarchy diagram (Mermaid `graph TD`).

**Critical files**: `src/rglob/cli.py`, `tests/test_cli.py` (new, syrupy-based), `docs/cli.md`, `docs/architecture.md`, `pyproject.toml`, `README.md`.

**Acceptance**: every existing CLI invocation in the README produces identical stdout (regression check); new flags work; `rglob find "*.py" --json | jq` round-trips; snapshot suite covers all subcommand × format combinations; shell completion installs and tab-completes flags; **aggregated coverage stays at 100%**.

---

## Phase 5 — Fun features

The labor-of-love payoff. Each subcommand is a self-contained mini-project.

**Tasks**
- Tier 2 core filters wired into both `find()` and CLI:
  - `min_size`/`max_size` accepting `int | str` ("1M", "10K"). Tiny size-string parser; reuse existing `kilobytes`/`megabytes`/`gigabytes`/`terabytes` for the math.
  - `newer_than`/`older_than` accepting `datetime | timedelta | str` ("7d", "2024-01-01").
  - `kinds: set[Literal["f","d","l","x"]]` (file/dir/symlink/executable).
- `.gitignore` awareness: optional dep on `pathspec` (mature, small). `respect_gitignore: bool = False`. Walk `.gitignore` files top-down, merge into per-directory `PathSpec`, prune at `scandir` time. `pyproject.toml`: `[project.optional-dependencies] gitignore = ["pathspec"]`. CLI flag promoted from Phase 4 stub.
- New subcommands:
  - **`stats`**: combined count + total size + line-count + extension breakdown in a `rich.table`.
  - **`tree`**: ASCII/Unicode tree built on `rich.tree`, honours all filters.
  - **`top`**: top-N largest files (default N=10), table output.
  - **`dupes`**: duplicate-file detection. Strategy: bucket by size → bucket by `xxhash.xxh3_64` of first 4KB → full `xxh3_64` of survivors. Optional dep on `xxhash` (under the `[ext]` extra); fallback to `hashlib.file_digest(..., "blake2b")` when `xxhash` isn't installed (stdlib, no extra dep, fast enough to be a credible default in 2026). Output groups in a table.
- Benchmarks suite with `pytest-benchmark`: synthetic 10k-file tree, measure walk time, `--gitignore` overhead, `dupes` runtime. Upload as CI artifact (don't gate).
- Docs page per new subcommand with screenshots/asciinema; extend `docs/architecture.md` with the `dupes` pipeline (`flowchart LR`) and `.gitignore` pruning sequence diagrams in Mermaid.
- README: add a "Fun features" section showcasing `stats`/`tree`/`top`/`dupes` with example output snippets.

**Critical files**: `src/rglob/rglob.py` (filters), `src/rglob/cli.py` (new subcommands), `src/rglob/_filters.py` (new size/time parsers), `src/rglob/_dupes.py` (new), `tests/test_dupes.py`, `tests/test_filters.py`, `bench/test_walk.py` (new), `docs/cli/*.md`, `docs/architecture.md`, `README.md`.

**Acceptance**: each new subcommand has a docs page, snapshot tests, and a benchmark entry; `--gitignore` round-trips against a real `.gitignore` from this repo (it's a fun dogfood); **aggregated coverage stays at 100%** (every branch in `_dupes.py` and the new filters exercised).

---

## Phase 6 — 2.0 cleanup & release

The only release point. Everything from Phases 1–5 ships in one `2.0.0` PyPI publish.

**Tasks**
- **Breaking**: `rglob()` and `rglob_()` now return `list[Path]` (was `list[str]`). One-line migration: `[str(p) for p in rglob(...)]`. Document loudly in CHANGELOG + a "Migrating to 2.0" page.
- Remove any deprecation shims accumulated in Phases 3–5.
- Optional Tier 3 stretch (only if still fun): `wcmatch`-style extended globs (`+(...)`, `@(...)`, `!(...)`) gated behind `extended: bool = False` and `pip install rglob[ext]`.
- Bump trove classifier to `Development Status :: 6 - Mature`.
- Flip `__version__` from `"2.0.0.dev0"` → `"2.0.0"`.
- Convert the `[Unreleased]` CHANGELOG section to `[2.0.0] – <date>`; add the "Migrating to 2.0" docs page.
- Extend `docs/architecture.md` with the final public-API class diagram (Mermaid `classDiagram`) showing the 2.0 surface.
- README: final accuracy pass — Quick Start, API reference link, CLI reference link, "Migrating to 2.0" link, refreshed badges (e.g., bump PyPI badge to point at 2.0).
- Tag `v2.0.0` → `release.yml` workflow does the PyPI publish + GitHub Release.

**Critical files**: `src/rglob/rglob.py`, `src/rglob/__init__.py`, `CHANGELOG.md`, `docs/migrating-to-2.0.md`, `docs/architecture.md`, `README.md`.

**Acceptance**: clean `mypy --strict`; all tests pass; **aggregated coverage = 100%**; `pip install rglob==2.0.0` from PyPI works; `from rglob import rglob; rglob("/tmp", "*")` returns `list[Path]`; README banner + badges + content all reflect the shipped 2.0 surface.

---

## Critical files (cross-phase quick reference)

- `pyproject.toml` — focal point of Phases 1, 2, 4, 5 (PEP 621 metadata; hatch; ruff/mypy/pytest/coverage config; `[project.optional-dependencies]` for `dev`/`bdd`/`gitignore`/`ext`/`docs`; Typer + Rich + xxhash + pathspec deps)
- `src/rglob/rglob.py` — rewritten in Phase 3 onto `os.scandir`; gains `find`/`find_all`; new filters in Phases 3 & 5; legacy `rglob`/`rglob_`/`lcount`/`tsize` become wrappers
- `src/rglob/cli.py` — Phase 4 Typer migration; Phase 5 new subcommands (`stats`/`tree`/`top`/`dupes`)
- `src/rglob/__init__.py` — version single-source (Phase 1); export `find`/`find_all` (Phase 3); prune deprecated aliases (Phase 6)
- `.github/workflows/` — replace `pylint.yml` with `ci.yml` + `release.yml` + `docs.yml` (Phase 2); all gating
- `features/` — kept as parallel BDD suite; `features/steps/steps.py` refactored in Phase 2 to share helpers with `tests/`
- `tests/` — new dir in Phase 2; grows each phase; 100%-coverage discipline enforced locally via `--cov-fail-under=100` and on CI via the Codecov merged-report gate (per-job floor 95%)
- `docs/` — new in Phase 2; `index.md`, `api.md`, `cli.md`, `architecture.md` (Mermaid diagrams accreting per phase), `decisions/`, `contributing.md`, `plans/` (this file lives here)
- `README.md` — refreshed every phase; never goes stale
- `Makefile` — `help` (default), `build`, `lint`, `test`, `fmt`, `docs`, `dev-setup`, `clean`

**Existing code worth reusing**:
- `kilobytes`/`megabytes`/`gigabytes`/`terabytes` in `src/rglob/rglob.py:11-32` — reuse directly for the Phase 5 size-string parser.
- The behave scenarios in `features/rglob.feature` — port their assertions into pytest in Phase 2; the existing fixture pattern (`create_root_dir`, `create_subdirectories`, `create_files`) translates cleanly to `tmp_path` fixtures.

---

## Verification

End-to-end checks per phase. No PyPI publishes happen until Phase 6; everything before that is verified locally and in CI only.

**Phase 1**: `pip install -e . && python -c "import rglob; print(rglob.__version__)"` → `2.0.0.dev0`. `git status` clean of `egg-info`. `CODE_OF_CONDUCT.md` exists (required by `pyproject.toml` sdist `include`). `README.md` opens with an ASCII banner that renders cleanly in a GitHub-flavoured markdown preview.

**Phase 2**: `make help` prints every target with descriptions; `make lint test build docs` green locally. PR shows CI matrix green across `3.11–3.14` × `ubuntu/macos/windows`. Codecov merged report shows **100%** coverage; the local `--cov-fail-under=100` gate fails a deliberately-broken test that drops a line uncovered. Branch protection blocks a PR with a failing test. Docs site at `https://chris-piekarski.github.io/python-rglob/` renders Mermaid diagrams on `architecture.md`. Dry-run `release.yml` against TestPyPI.

**Phase 3**: Every existing behave scenario passes unchanged (`behave`). New pytest+hypothesis suite passes (`pytest`). Coverage still 100%. Benchmark: `pytest bench/ --benchmark-only` shows `find()` ≥2× faster than legacy `rglob()` on a 10k-file tree. `mypy --strict src/rglob` clean. README Quick Start now demonstrates `find()` and the `**` recursive form actually works.

**Phase 4**: Every README CLI example produces identical stdout (regression check). `rglob find "*.py" --json | jq '.[] | .path'` round-trips. `rglob --install-completion bash && exec bash && rglob f<TAB>` completes to `find`. Snapshot suite (`pytest tests/test_cli.py`) green. Coverage still 100%. Architecture diagram for CLI hierarchy renders on the docs site.

**Phase 5**: `rglob stats "*.py"` shows a populated `rich.table`. `rglob tree --max-depth 3` renders a tree. `rglob dupes ~/Downloads` correctly groups two intentionally-duplicated test files. `rglob find "*" --gitignore` against this repo excludes `dist/`, `.venv/`, etc. Aggregated coverage still 100% — every branch in `_dupes.py` and the new filters is exercised. README "Fun features" section showcases each new subcommand with copy-paste-able examples.

**Phase 6**: `pip install rglob==2.0.0 && python -c "from rglob import rglob; from pathlib import Path; assert all(isinstance(p, Path) for p in rglob('.', '*'))"` passes. Migration docs page exists at `https://chris-piekarski.github.io/python-rglob/migrating-to-2.0/`. Final aggregated coverage report is 100%. README banner + badges + content reflect the shipped 2.0 surface. PyPI listing shows v2.0.0.
