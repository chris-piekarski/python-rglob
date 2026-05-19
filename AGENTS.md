# AGENTS.md

Instructions for AI coding assistants (Claude Code, Cursor, Aider, OpenAI
codex-style agents) working in this repository. This is a labor-of-love
hobby package — keep changes scoped, idiomatic, and small.

## Project at a glance

- **Name**: `rglob` — lightweight recursive glob helpers for Python.
- **Surface**: `find` / `find_all` (modern), `rglob` / `rglob_` / `lcount` /
  `tsize` (legacy), `rglob.agent` (stable agent API),
  `kilobytes` / `megabytes` / `gigabytes` / `terabytes` (unit helpers).
  CLI: `find`, `grep`, `count`, `lcount`, `tsize`, `stats`, `tree`, `top`,
  `dupes`, `describe`, `schema`, `capabilities`, `agent-version`, `mcp`.
- **Python**: 3.11+ (3.10 drops at the 2.0 release — see
  [ADR-0002](docs/decisions/0002-python-floor.md)).
- **Build backend**: hatchling. **CLI**: Typer + Rich.
- **Docs**: MkDocs Material → `https://chris-piekarski.github.io/python-rglob/`.

## Layout

```text
src/rglob/                  # the package
  __init__.py               # public re-exports + __version__
  rglob.py                  # find/find_all walker + legacy rglob/lcount/tsize
  cli.py                    # Typer CLI app
  _filters.py               # size/time/kind parsers and predicates (Phase 5)
  _dupes.py                 # duplicate-detection pipeline (Phase 5)
  agent/                    # stable agent dataclasses, schemas, MCP server
  py.typed                  # PEP 561 marker
tests/                      # primary suite — pytest + hypothesis + syrupy
features/                   # parallel BDD suite (behave) — shares helpers
docs/                       # MkDocs site source
  plans/                    # the modernization roadmap lives here
  decisions/                # ADRs (build backend, Python floor, etc.)
.github/workflows/          # ci.yml + release.yml + docs.yml
```

## Consumer guidance for agents using `rglob`

If you are an agent consuming this package in another project, prefer the
stable machine surfaces:

```bash
pip install rglob
rglob describe find
rglob schema grep
rglob schema --all
rglob capabilities --json
```

For Python integrations, import from `rglob.agent`, not private modules:

```python
from pathlib import Path

from rglob.agent import WalkOptions, search_all

result = search_all(WalkOptions(patterns=["*.py"], base=Path(".")))
```

For MCP hosts:

```bash
pip install "rglob[mcp]"
rglob mcp
```

Structured outputs are bounded with `--limit`, `--max-bytes`, and
`--max-file-size`; they report `truncated` and `truncated_reason` when a
limit is hit. Operational failures are returned as `ErrorInfo` records or a
stable error envelope. See `docs/agents/` for setup and safety details.

## Mandatory conventions

**All branches, PR titles, and commits MUST follow
[Conventional Commits](https://www.conventionalcommits.org/) v1.0.0.**

- **Commit / PR title**: `<type>[(scope)][!]: <description>`
  - Types in use: `feat`, `fix`, `refactor`, `perf`, `docs`, `test`,
    `build`, `ci`, `chore`, `style`, `revert`.
  - Append `!` after the type/scope when the change is breaking
    (`feat!: drop X`, `refactor(walker)!: ...`).
  - Description starts lowercase, no trailing period, imperative mood
    ("add", "drop", not "added", "drops").
  - Soft 72-char limit on the subject line.
- **Branch names**: matching prefixes — `feat/...`, `fix/...`,
  `refactor/...`, `docs/...`, `chore/...`, `release/...`. Use kebab-case
  after the slash (`feat/scandir-walker`, `release/2.0`, not
  `feat/Scandir_Walker`).
- **Body**: motivate the *why*; reference issues with `Closes #N`; record
  breaking changes under a `BREAKING CHANGE:` footer when the description
  alone isn't enough.

CI does not currently fail on a non-conventional title, but reviewers will
ask you to rename. The next-major changelog generator assumes the
convention.

## Developer workflow

```bash
make dev-setup       # one-time: installs [dev,bdd,docs,gitignore,ext,bench]
                     # plus `pre-commit install`
make help            # list all targets
make lint            # ruff check + ruff format --check + mypy --strict
make test            # pytest --cov-fail-under=100 + behave (both gating)
make bench           # pytest-benchmark walker benchmarks; rg comparison skips if absent
make fmt             # auto-format with ruff
make docs            # live MkDocs preview on :8000
make docs-build      # static site build (strict mode)
make build           # hatch build → dist/{sdist,wheel}
make publish         # hatch build + twine check/upload to PyPI
make clean           # remove caches and build outputs
```

Per-job CI uses `--cov-fail-under=95`; the **merged** Codecov report must
hit **100%**. Locally the gate is 100% on a single Linux run. See
[ADR-0006](docs/decisions/0006-aggregated-coverage.md).

## Style gates

- **Ruff** with `select = ["E","F","W","I","B","UP","SIM","RUF","PTH",
  "PERF","D"]`, Google docstring convention, 100-char lines. Config in
  `pyproject.toml`.
- **Mypy** `strict = true` on `src/rglob`. Ship `py.typed`.
- **`# pragma: no cover`** is reserved for genuinely unreachable lines
  (`if __name__ == "__main__":` guards, cross-platform branches that no
  matrix cell covers). Every pragma carries a one-line justification.

## Mermaid diagrams

`mkdocs build --strict` does **not** catch Mermaid syntax errors —
Mermaid renders client-side, so a broken diagram still produces a
clean static site that throws "Syntax error in text" only when a
visitor loads the page. To prevent regressions:

- Run `make lint-docs` (or `python3 scripts/lint_mermaid.py`) before
  pushing changes that touch any `.md` file. It extracts every
  ```mermaid block and validates each via `mmdc`. CI runs the same
  gate; the pre-commit hook fires it locally too.
- Install the CLI once with `npm install -g @mermaid-js/mermaid-cli`.

Mermaid 11 is strict about a few things that look harmless. The rules
worth knowing before writing a new diagram:

- **Flowchart node labels** that contain `(`, `)`, `'`, `|`, or other
  operator-looking characters must be double-quoted:
  `A["find(base, ...)"]`, not `A[find(base, ...)]`. The unquoted form
  trips the parser on `(`.
- **Sequence-diagram message text** (everything after `A->>B:`) stays
  ASCII-only. The parser rejects `[ ]`, `;`, em-dashes (`—`), and
  Unicode arrows (`→`) inside message bodies. Use plain prose: write
  "`/base/a is new`", not "`/base/a — new`"; "`a-slash and sym-to-base`",
  not "`[a/, sym → base]`".
- **Participant aliases** stay simple — no parens, no `:`, no
  brackets. `participant V as visited`, not
  `participant V as visited: set[str]`.
- **Generics** in class diagrams use paired tildes: `Iterator~Path~`,
  `list~list~Path~~`. Don't write `Callable~|None`; spell it
  `Callable` or `Optional~Callable~`.

## Where to look first

- **Roadmap**: [`docs/plans/modernization-roadmap.md`](docs/plans/modernization-roadmap.md)
  records the six-phase plan (plus the agent-platform sub-phases) that
  delivered 2.0. Useful as historical context when changing a subsystem.
- **Decisions log**: [`docs/decisions/`](docs/decisions/) captures the
  locked-in choices (build backend, Python floor, Path return, Typer
  rationale, coverage strategy, behave-as-parallel, security model).
- **Architecture**: [`docs/architecture.md`](docs/architecture.md) has
  Mermaid diagrams of the walker, CLI hierarchy, dupes pipeline,
  `.gitignore` flow, and the 2.0 public API.

## Working with the existing code

- The walker in `src/rglob/rglob.py` is the hot path. Changes there should
  preserve `os.scandir`'s cached `DirEntry.d_type` behaviour (don't add
  unnecessary `stat()` calls).
- The CLI in `src/rglob/cli.py` uses Typer; new subcommands go below the
  existing block. Shared filter `Annotated` aliases (`BaseOpt`,
  `ExcludeOpt`, etc.) are defined at the top of the module — reuse them.
- Behave step bodies (`features/steps/steps.py`) should call the same
  helpers `tests/conftest.py::TreeBuilder` exposes; the two suites must
  agree.

## Things to NOT do

- Don't add `from __future__ import annotations` to `src/rglob/*.py` —
  PEP 604 unions work natively on the 3.11 floor.
- Don't introduce `os.path` calls in new code; use `pathlib.Path`.
- Don't add new optional dependencies without a matching
  `[project.optional-dependencies]` extra in `pyproject.toml`.
- Don't bump the trove `Development Status` classifier without coordinating
  with the maintainer — it's currently `6 - Mature` post-2.0.
- Don't disable the 100% coverage gate. If a line is truly unreachable,
  use `# pragma: no cover` with a one-line justification; if it's
  reachable, write a test.
- Don't skip pre-commit / signed-commit hooks (`--no-verify`,
  `--no-gpg-sign`) without explicit maintainer instruction.

## Releases

The 2.0 release is the only release point so far. Future releases follow
SemVer; tags are `vMAJOR.MINOR.PATCH` and trigger
`.github/workflows/release.yml`, which builds with hatch and publishes via
PyPI OIDC trusted publishing. Source `__version__` is bumped before the
tag is pushed.
