<h1 align="center">rglob</h1>

Lightweight recursive glob helpers for Python. Find files recursively, count lines, and sum sizes with simple functions.

Python 3 users should install the latest release. For Python 2, the final supported version is 1.4 (links below).

—

## Installation

```bash
pip install rglob
```

## Quick Start

```python
import rglob

# List all Python files under a base directory
files = rglob.rglob("/path/to/project", "*.py")

# Same, starting from the current working directory
files_cwd = rglob.rglob_("*.py")

# Count non-empty, non-comment lines across matching files
non_empty_non_comment = rglob.lcount(
    "/path/to/project",
    "*.py",
    lambda line: bool(line.strip()) and not line.lstrip().startswith("#"),
)

# Total size of all JPGs in megabytes (use provided unit helpers)
total_mb = rglob.tsize("/path/to/photos", "*.jpg", rglob.megabytes)
```

Note: When invoking from a shell, quote or escape glob patterns so your shell doesn’t expand them before Python runs, e.g. `"*.py"`.

## API

- `rglob.rglob(base: str, pattern: str) -> list[str]`: Recursively returns a list of paths matching `pattern` under `base`.
- `rglob.rglob_(pattern: str) -> list[str]`: Same as `rglob`, using the current working directory as `base`.
- `rglob.lcount(base: str, pattern: str, func: Callable[[str], bool] = lambda _: True) -> int`: Counts lines across all matching files, applying `func` as a per-line predicate.
- `rglob.tsize(base: str, pattern: str, func: Callable[[float], float] = rglob.megabytes) -> float`: Sums sizes (in bytes) of matching files, then converts using `func`.
- Unit helpers: `rglob.kilobytes`, `rglob.megabytes`, `rglob.gigabytes`, `rglob.terabytes`.

### Tips

- Paths returned are not guaranteed to be sorted; call `sorted(...)` if ordering matters.
- Patterns use Python’s `glob` syntax (e.g., `"*.py"`, `"**/*.py"` is not supported here; recursion is handled by `rglob`).
- Line counting opens files in text mode; ensure your files are decodable with the system default encoding.

## Compatibility

- Python 3: Use the latest release (e.g., 1.7+ on PyPI).
- Python 2: Final supported release is 1.4.

Links:

- PyPI (Py3): https://pypi.org/project/rglob/1.7/
- PyPI (Py2): https://pypi.org/project/rglob/1.4/

## Development

```bash
git clone https://github.com/chris-piekarski/python-rglob.git
cd python-rglob
python -m venv .venv && source .venv/bin/activate
pip install -e .
```

### Running examples/tests

This repo includes legacy BDD tests using `lettuce`.

```bash
pip install lettuce
lettuce
```

Note: The legacy tests were originally written for Python 2 and may require tweaks for modern Python. The core library supports Python 3 (see `setup.py`).

## Why use this?

`rglob` predates `glob.glob(..., recursive=True)` and offers a tiny, easy-to-read implementation with convenient helpers for line counting and size aggregation. It’s useful for quick scripts and small utilities where pulling in heavier tools is unnecessary.

## License

Apache 2.0 — see `LICENSE`.
