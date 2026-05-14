<!-- markdownlint-disable MD033 MD041 -->

```text
                      __      __
   _________  _______/ /___  / /_
  / ___/ __ `/ ___/ / __ \/ __ \
 / /  / /_/ / /__/ / /_/ / /_/ /
/_/   \__, /\___/_/\____/_.___/
     /____/
```

<p align="center"><em>Lightweight recursive glob helpers for Python — find files, count lines, sum sizes.</em></p>

<p align="center">
  <a href="https://pypi.org/project/rglob/"><img alt="PyPI" src="https://img.shields.io/pypi/v/rglob.svg"></a>
  <a href="https://pypi.org/project/rglob/"><img alt="Python versions" src="https://img.shields.io/pypi/pyversions/rglob.svg"></a>
  <a href="https://github.com/chris-piekarski/python-rglob/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/chris-piekarski/python-rglob/actions/workflows/ci.yml/badge.svg"></a>
  <a href="https://codecov.io/gh/chris-piekarski/python-rglob"><img alt="Coverage" src="https://codecov.io/gh/chris-piekarski/python-rglob/branch/master/graph/badge.svg"></a>
  <a href="https://github.com/chris-piekarski/python-rglob/blob/master/LICENSE"><img alt="License" src="https://img.shields.io/badge/license-Apache--2.0-blue.svg"></a>
  <a href="https://github.com/astral-sh/ruff"><img alt="Ruff" src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json"></a>
  <a href="https://github.com/astral-sh/ruff"><img alt="Code style: ruff" src="https://img.shields.io/badge/code%20style-ruff-000000.svg"></a>
</p>

---

## Why use this?

Modern Python has `pathlib.Path.rglob` and `glob.glob(..., recursive=True)`, and
external tools like `fd` and `ripgrep` are blazingly fast. `rglob` predates
most of those and has stuck around because it's tiny, easy to read, and ships
with friendly helpers for the two things you usually want next: **count
lines** and **sum sizes**. The redundancy is part of the fun — this is a
labor-of-love package.

## Installation

```bash
pip install rglob
```

## Quick Start (Python API)

```python
import rglob

# Modern API — yields pathlib.Path, with filter kwargs
for p in rglob.find("/path/to/project", "*.py", exclude=".venv"):
    print(p)

# Eager variant
paths = rglob.find_all("/repo", "**/*.py", hidden=False, max_depth=4)

# OS-aware case sensitivity (`None` = OS default — case-sensitive on Linux,
# case-insensitive on macOS/Windows; pass True/False to force)
paths = rglob.find_all(".", "*.PY", case_sensitive=False)

# Legacy API still works
files = rglob.rglob("/path/to/project", "*.py")          # → list[str]
files_cwd = rglob.rglob_("*.py")                          # → list[str]

# Count non-empty, non-comment lines across matching files
non_empty_non_comment = rglob.lcount(
    "/path/to/project",
    "*.py",
    lambda line: bool(line.strip()) and not line.lstrip().startswith("#"),
)

# Total size of all JPGs in megabytes (use provided unit helpers)
total_mb = rglob.tsize("/path/to/photos", "*.jpg", rglob.megabytes)
```

Paths are sorted by default for deterministic output. Pass `sort=False` for
raw `scandir` order. Recursive `**` globs work
(`rglob.find_all("src", "**/*.py")`); symlink loops are detected and
terminated automatically.

> Upgrading from 1.x? `rglob()` now returns `list[Path]` instead of
> `list[str]`. See [migrating to 2.0](docs/migrating-to-2.0.md) for the
> one-line migration.

## Quick Start (CLI)

```bash
# Find files
rglob find "*.py"

# Multiple patterns are OR'd
rglob find "*.py" "*.pyx"

# Filter flags
rglob find "*.py" --base ./src --exclude .venv -d 3 --hidden

# Output formats
rglob find "*.py" --json | jq '.[]'
rglob find "*.py" --jsonl
rglob find "*.py" -0 | xargs -0 wc -l       # NUL-separated for xargs

# Mini-template formatter
rglob find "*.py" --format "{name}: {size_mb:.2f} MiB"

# Count lines, skipping empties and comment lines
rglob lcount "*.py" --no-empty --no-comments

# Sum total size in MB
rglob tsize "*.py" --unit mb

# Shell completion (one-time setup)
rglob --install-completion bash    # or zsh / fish / powershell
```

> **Quote your patterns!** Otherwise your shell pre-expands them before Python
> runs. Use `rglob find "*.py"`, not `rglob find *.py`. If `rglob find` receives
> multiple unquoted positional patterns it will warn you on stderr.

## Fun features

```bash
# Summary table: file count, total size, extension breakdown
rglob stats "*.py" --base ./src

# Unicode tree of matches (depth 3 by default)
rglob tree "*.py" --base ./src

# Top 10 largest files
rglob top "*" --base ~/Downloads

# Find duplicate files (size → 4-KiB hash → full hash)
rglob dupes "*" --base ~/Downloads --min-size 1M

# Respect .gitignore (requires `pip install rglob[gitignore]`)
rglob find "*" --gitignore

# Filter by kind / size / mtime
rglob find "*" -t f --min-size 1M --newer-than 7d
```

The duplicate detection uses `xxhash.xxh3_64` when the optional `[ext]`
extra is installed; it falls back to stdlib BLAKE2b otherwise — both are
fast enough that the difference rarely matters in 2026.

## Compatibility

| Python | Status |
| --- | --- |
| 3.11+ | Supported (`rglob` 2.0+) |
| 3.10  | Pin `rglob<2` — dropped at 2.0 (Python 3.10 EOL is October 2026) |
| 3.6–3.9 | Not supported |
| 2.7 | Final supported release is `1.4` (PyPI history: <https://pypi.org/project/rglob/1.4/>) |

## Documentation

Full docs (API reference, CLI reference, architecture diagrams, ADRs) live in
[`docs/`](docs/) and are published as a MkDocs Material site at
<https://chris-piekarski.github.io/python-rglob/>.

- [Modernization roadmap](docs/plans/modernization-roadmap.md) — the six-phase
  plan that delivered 2.0.
- [Migrating to 2.0](docs/migrating-to-2.0.md) — the `list[str]` → `list[Path]`
  return-type flip.
- [Architecture](docs/architecture.md) — package layout, walker call-graph,
  and (later) the CLI command hierarchy.
- [Decisions](docs/decisions/) — ADRs for the locked-in design choices.

## Development

```bash
git clone https://github.com/chris-piekarski/python-rglob.git
cd python-rglob
python -m venv .venv && source .venv/bin/activate
make dev-setup     # installs [dev,bdd,docs,gitignore] + pre-commit hooks
make test          # pytest + behave, gated at 100% local coverage
make lint          # ruff + mypy --strict
make docs          # live MkDocs preview at :8000
```

The legacy `pylint` workflow is being retired during Phase 2 of the roadmap.
Until then, `pylint src/rglob features` works as a fallback.

## License

Apache 2.0 — see [`LICENSE`](LICENSE).
