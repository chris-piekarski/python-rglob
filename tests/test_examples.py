"""Runnable harness for `docs/examples/*.md`.

Walks every example file, extracts fenced code blocks that carry a
magic header line (`<!-- example: name=foo runner=bash -->` or
`<!-- example: name=foo runner=python -->`), and executes them. The
results land in pytest so `make test` fails if a published recipe rots.

Untagged blocks are treated as documentation-only and are skipped.

Recipes that need a sample tree reference the env var `RGLOB_FIXTURE`,
which the harness points at `tests/fixtures/agent-tree/` (the same
golden fixture the agent-contract tests use). This keeps recipes
portable across CI hosts without leaking developer paths into the
docs.

Supported tag attributes (space-separated, all on one HTML comment):
- `name=<identifier>` — required; used in the pytest test name.
- `runner=bash|python` — required; selects the execution backend.
- `expected_substring=<str>` — optional; substring that must appear in
  stdout. Quote with single quotes if it contains spaces. Multiple
  `expected_substring=` attributes can appear.
- `expected_exit_code=<int>` — optional; default 0.

Example:

    <!-- example: name=find_py_files runner=bash expected_substring='alpha.py' -->
    ```bash
    rglob find "*.py" --base "$RGLOB_FIXTURE" --json
    ```
"""

from __future__ import annotations

import os
import re
import shlex
import subprocess
import sys
import textwrap
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
EXAMPLES_DIR = REPO_ROOT / "docs" / "examples"
FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures" / "agent-tree"

_TAG_RE = re.compile(
    r"<!--\s*example:\s*(?P<attrs>.+?)\s*-->\s*\n```(?P<lang>\w+)?\s*\n(?P<body>.*?)\n```",
    re.DOTALL,
)
# Tokens are `key=value` pairs; value may be bare or single-quoted.
_ATTR_RE = re.compile(r"(?P<key>\w+)=(?:'(?P<qval>[^']*)'|(?P<val>\S+))")


@dataclass(frozen=True)
class Example:
    """A single runnable example extracted from a Markdown file."""

    source: Path
    name: str
    runner: str
    body: str
    expected_substrings: tuple[str, ...]
    expected_exit_code: int

    @property
    def test_id(self) -> str:
        """Pytest parametrization id."""
        return f"{self.source.stem}::{self.name}"


def _parse_attrs(raw: str) -> dict[str, list[str]]:
    """Parse the magic-comment attribute string into a dict of lists."""
    out: dict[str, list[str]] = {}
    for match in _ATTR_RE.finditer(raw):
        key = match.group("key")
        value = match.group("qval") if match.group("qval") is not None else match.group("val")
        out.setdefault(key, []).append(value)
    return out


def _iter_examples(md_path: Path) -> Iterator[Example]:
    """Yield every tagged example block from a Markdown file."""
    text = md_path.read_text(encoding="utf-8")
    for match in _TAG_RE.finditer(text):
        attrs = _parse_attrs(match.group("attrs"))
        if "name" not in attrs or "runner" not in attrs:
            continue
        yield Example(
            source=md_path,
            name=attrs["name"][0],
            runner=attrs["runner"][0],
            body=match.group("body"),
            expected_substrings=tuple(attrs.get("expected_substring", ())),
            expected_exit_code=int(attrs.get("expected_exit_code", ["0"])[0]),
        )


def _discover() -> list[Example]:
    """Walk `docs/examples/` and collect every tagged example."""
    if not EXAMPLES_DIR.exists():
        return []
    return [ex for md in sorted(EXAMPLES_DIR.glob("*.md")) for ex in _iter_examples(md)]


_EXAMPLES = _discover()


def _run_bash(example: Example) -> subprocess.CompletedProcess[str]:
    """Run a bash-tagged example in a subprocess with `RGLOB_FIXTURE` set.

    Prepends the active Python's `bin/` (typically the project's `.venv`)
    to PATH so the freshly-installed `rglob` entry point wins over any
    stale user-wide shim.
    """
    python_bin = Path(sys.executable).parent
    env = {
        **os.environ,
        "PATH": f"{python_bin}{os.pathsep}{os.environ.get('PATH', '')}",
        "RGLOB_FIXTURE": str(FIXTURE_DIR),
    }
    return subprocess.run(
        ["bash", "-c", textwrap.dedent(example.body)],
        capture_output=True,
        text=True,
        env=env,
        cwd=REPO_ROOT,
        check=False,
        timeout=30,
    )


def _run_python(example: Example) -> subprocess.CompletedProcess[str]:
    """Run a python-tagged example in a subprocess for isolation."""
    env = {**os.environ, "RGLOB_FIXTURE": str(FIXTURE_DIR)}
    return subprocess.run(
        [sys.executable, "-c", textwrap.dedent(example.body)],
        capture_output=True,
        text=True,
        env=env,
        cwd=REPO_ROOT,
        check=False,
        timeout=30,
    )


_RUNNERS = {"bash": _run_bash, "python": _run_python}


@pytest.mark.parametrize("example", _EXAMPLES, ids=lambda ex: ex.test_id)
def test_runnable_example(example: Example) -> None:
    """Run a tagged example and validate stdout / exit code."""
    runner = _RUNNERS.get(example.runner)
    if runner is None:
        pytest.skip(f"unknown runner: {example.runner!r}")
    if example.runner == "bash" and not _has_bash():
        pytest.skip("bash not available on this host")

    result = runner(example)

    assert result.returncode == example.expected_exit_code, (
        f"{example.test_id} exited with {result.returncode} "
        f"(expected {example.expected_exit_code})\n"
        f"--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}"
    )
    for needle in example.expected_substrings:
        assert needle in result.stdout, (
            f"{example.test_id} stdout missing {needle!r}\n--- stdout ---\n{result.stdout}"
        )


def _has_bash() -> bool:
    """Return whether a working `bash` is on PATH.

    Windows ships a `bash.exe` shim in System32 that forwards to WSL; on
    CI runners without a WSL distro installed that shim exists but exits
    non-zero. Require a zero exit from `bash -c true` so the stub falls
    through and the bash-tagged examples are skipped instead of failing.
    """
    try:
        result = subprocess.run(
            ["bash", "-c", "true"],
            capture_output=True,
            check=False,
            timeout=5,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return False
    return result.returncode == 0


_ = shlex  # kept for future quoting helpers; silence unused-import lint
