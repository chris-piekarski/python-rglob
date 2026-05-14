# rglob

Lightweight recursive glob helpers for Python — find files, count lines, sum
sizes.

This is a small labor-of-love package. Modern Python has `pathlib.Path.rglob`
and tools like `fd`/`ripgrep` exist; `rglob` is small, easy to read, and ships
with friendly helpers for the two things you usually want next: count lines
and sum sizes.

## Installation

```bash
pip install rglob
```

## Quick start

```python
import rglob

files = rglob.rglob("/path/to/project", "*.py")
files_cwd = rglob.rglob_("*.py")

lines = rglob.lcount(
    "/path/to/project",
    "*.py",
    lambda line: bool(line.strip()) and not line.lstrip().startswith("#"),
)

mb = rglob.tsize("/path/to/photos", "*.jpg", rglob.megabytes)
```

The full modern API (`find` / `find_all` with filter flags) is described on
the [API page](api.md). For the command-line, see [CLI](cli.md). For design
context, see [Architecture](architecture.md) and the [decisions log](decisions/index.md).

## Where to go next

- [API reference](api.md)
- [CLI reference](cli.md)
- [Architecture](architecture.md) — package layout, walker call-graph
- [Decisions log](decisions/index.md) — ADRs for locked-in design choices
- [Modernization roadmap](plans/modernization-roadmap.md) — the six-phase plan
  currently shipping into 2.0
- [Changelog](changelog.md)
