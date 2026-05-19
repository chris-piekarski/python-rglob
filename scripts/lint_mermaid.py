"""Validate Mermaid diagrams embedded in Markdown files via `mmdc`.

`mkdocs build --strict` does NOT catch Mermaid syntax errors — Mermaid
renders client-side, so a broken diagram still produces a clean static
site that throws "Syntax error in text" only when a visitor loads the
page. This validator closes that gap by extracting every ```mermaid
fenced block in the repo and running it through the official mermaid
CLI (`mmdc`).

Usage:
    python3 scripts/lint_mermaid.py                # scan the whole repo
    python3 scripts/lint_mermaid.py path/to/x.md   # validate listed files

Exit code 0 on success, 1 on any diagram failure. If `mmdc` is missing,
the script prints a hint and exits 0 (so contributors without Node
tooling aren't blocked — CI installs it).
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MERMAID_RE = re.compile(r"```mermaid\n(.*?)\n```", re.DOTALL)


def _block_line(source: str, block: str) -> int:
    """Return the 1-based line number of the ```mermaid fence in source."""
    idx = source.find(block)
    return source.count("\n", 0, idx) if idx >= 0 else 0


def _find_md_files(paths: list[Path]) -> list[Path]:
    """Expand the input into a sorted list of *.md files under REPO_ROOT."""
    if paths:
        return sorted({p for p in paths if p.suffix == ".md" and p.is_file()})
    return sorted(REPO_ROOT.rglob("*.md"))


def validate(files: list[Path]) -> int:
    """Validate every mermaid block in `files`. Return process exit code."""
    if shutil.which("mmdc") is None:
        print(
            "lint_mermaid: `mmdc` not found on PATH; skipping. "
            "Install with `npm install -g @mermaid-js/mermaid-cli` to enable.",
            file=sys.stderr,
        )
        return 0

    failures: list[tuple[Path, int, str]] = []
    checked = 0

    with tempfile.TemporaryDirectory() as tmp:
        for md in files:
            text = md.read_text(encoding="utf-8")
            for n, block in enumerate(MERMAID_RE.findall(text), 1):
                checked += 1
                mmd = Path(tmp) / f"{md.stem}-{n}.mmd"
                mmd.write_text(block, encoding="utf-8")
                proc = subprocess.run(
                    ["mmdc", "-i", str(mmd), "-o", str(mmd.with_suffix(".svg"))],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                if proc.returncode != 0:
                    msg = proc.stderr or proc.stdout
                    failures.append((md, _block_line(text, block), msg.strip()))

    if not checked:
        print("lint_mermaid: no mermaid blocks found.")
        return 0

    if failures:
        print(f"lint_mermaid: {len(failures)} / {checked} block(s) failed:\n")
        for path, line, err in failures:
            rel = path.relative_to(REPO_ROOT) if path.is_relative_to(REPO_ROOT) else path
            print(f"  {rel}:{line}")
            for ln in err.splitlines():
                print(f"      {ln}")
            print()
        return 1

    print(f"lint_mermaid: {checked} block(s) validated cleanly.")
    return 0


def main() -> int:
    """Entrypoint — accept optional file args (used by pre-commit)."""
    args = [Path(p) for p in sys.argv[1:]]
    return validate(_find_md_files(args))


if __name__ == "__main__":
    raise SystemExit(main())
