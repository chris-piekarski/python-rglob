"""Generate basic repository stats and update OVERVIEW.md.

Outputs a Markdown section with a Mermaid pie chart and summary tables
between markers in OVERVIEW.md:

    <!-- BEGIN: REPO-STATS -->
    ... generated ...
    <!-- END: REPO-STATS -->

Run via the Makefile:

    make repo-stats

Or directly:

    python -m scripts.generate_repo_stats
"""

from collections.abc import Iterable
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
OVERVIEW_PATH = REPO_ROOT / "OVERVIEW.md"
PACKAGE_DIR = REPO_ROOT / "src" / "rglob"

# Top-level directories that count as their own "area". Anything else falls
# into "other".
KNOWN_AREAS = {"src", "tests", "features", "docs", "scripts", "bench"}

# Directories pruned from the scan entirely.
IGNORE_DIRS = {
    ".git",
    ".venv",
    "venv",
    "env",
    "build",
    "dist",
    "site",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".idea",
    ".vscode",
    "__pycache__",
    "htmlcov",
    "node_modules",
}

# File extensions counted, with their comment prefix (used so "code lines"
# excludes blank lines and comment-only lines).
COMMENT_PREFIX: dict[str, str] = {
    ".py": "#",
    ".sh": "#",
    ".bash": "#",
    ".yml": "#",
    ".yaml": "#",
    ".toml": "#",
    ".ini": ";",
    ".cfg": "#",
    ".feature": "#",
}

# Extensions where "non-blank line" is the closest analogue to "code".
CONSIDER_EXTS: set[str] = set(COMMENT_PREFIX) | {".md", ".txt", ".json"}


def is_ignored(path: Path) -> bool:
    """Return True when path lies under an ignored directory."""
    return any(part in IGNORE_DIRS for part in path.parts)


def count_file(path: Path) -> tuple[int, int]:
    """Return ``(total_lines, code_lines)`` for ``path``.

    ``code_lines`` excludes blank lines and lines whose first non-whitespace
    character matches the language's comment prefix. For markup/data
    formats (md/json/txt), every non-blank line counts as code.
    """
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return 0, 0

    total = 0
    code = 0
    prefix = COMMENT_PREFIX.get(path.suffix.lower())

    for raw in text.splitlines():
        total += 1
        line = raw.strip()
        if not line:
            continue
        if prefix and line.startswith(prefix):
            continue
        code += 1
    return total, code


def iter_repo_files(root: Path) -> Iterable[Path]:
    """Yield considered files under ``root`` excluding ignored paths."""
    for p in root.rglob("*"):
        if p.is_dir() or is_ignored(p):
            continue
        if p.suffix.lower() in CONSIDER_EXTS:
            yield p


def aggregate_stats() -> dict[str, dict[str, dict[str, int]] | dict[str, int]]:
    """Aggregate stats by top-level area and by `src/rglob` submodule."""
    by_area: dict[str, dict[str, int]] = {}
    by_module_py: dict[str, dict[str, int]] = {}

    def bump(bucket: dict[str, dict[str, int]], key: str, total: int, code: int) -> None:
        d = bucket.setdefault(key, {"total": 0, "code": 0})
        d["total"] += total
        d["code"] += code

    for f in iter_repo_files(REPO_ROOT):
        total, code = count_file(f)
        parts = f.relative_to(REPO_ROOT).parts
        area = parts[0] if parts else "other"
        if area not in KNOWN_AREAS:
            area = "other"
        bump(by_area, area, total, code)

        # Module breakdown: Python files under `src/rglob/`. Files directly
        # under the package root land in "root"; everything else groups by
        # immediate child (file or subdir).
        try:
            rel = f.relative_to(PACKAGE_DIR)
        except ValueError:
            continue
        if f.suffix == ".py":
            mod = rel.parts[0] if len(rel.parts) > 1 else "root"
            bump(by_module_py, mod, total, code)

    return {
        "by_area": by_area,
        "by_module_py": by_module_py,
        "overall": {
            "total": sum(v["total"] for v in by_area.values()),
            "code": sum(v["code"] for v in by_area.values()),
        },
    }


def format_number(n: int) -> str:
    """Format ``n`` with thousands separators for Markdown output."""
    return f"{n:,}"


def generate_markdown(stats: dict[str, dict[str, dict[str, int]] | dict[str, int]]) -> str:
    """Render repository statistics as a Markdown section."""
    by_area: dict[str, dict[str, int]] = stats["by_area"]  # type: ignore[assignment]
    by_module_py: dict[str, dict[str, int]] = stats["by_module_py"]  # type: ignore[assignment]
    overall: dict[str, int] = stats["overall"]  # type: ignore[assignment]

    pie_lines = ["```mermaid", "pie title Code LOC by Area"]
    for name, data in sorted(by_area.items(), key=lambda kv: kv[1]["code"], reverse=True):
        if data["code"] == 0:
            continue
        pie_lines.append(f'  "{name}" : {data["code"]}')
    pie_lines.append("```")

    top_n = 8
    sorted_mods = sorted(by_module_py.items(), key=lambda kv: kv[1]["code"], reverse=True)
    module_pie_lines = ["```mermaid", "pie title Code LOC by Module (src/rglob, Python only)"]
    other_sum = sum(v["code"] for _, v in sorted_mods[top_n:])
    for name, data in sorted_mods[:top_n]:
        if data["code"] == 0:
            continue
        module_pie_lines.append(f'  "{name}" : {data["code"]}')
    if other_sum > 0:
        module_pie_lines.append(f'  "other" : {other_sum}')
    module_pie_lines.append("```")

    area_rows = ["| Area | Code LOC | Total Lines |", "|------|----------|-------------|"]
    for name, data in sorted(by_area.items(), key=lambda kv: kv[1]["code"], reverse=True):
        area_rows.append(
            f"| {name} | {format_number(data['code'])} | {format_number(data['total'])} |"
        )

    module_rows = [
        "| Module (src/rglob, .py only) | Code LOC | Total Lines |",
        "|------------------------------|----------|-------------|",
    ]
    for name, data in sorted_mods[:10]:
        module_rows.append(
            f"| {name} | {format_number(data['code'])} | {format_number(data['total'])} |"
        )

    md: list[str] = [
        "## Repository Stats",
        "",
        f"- Code LOC (approx): {format_number(overall['code'])}",
        f"- Total lines (tracked files): {format_number(overall['total'])}",
        "",
        *pie_lines,
        "",
        "### LOC by Area",
        *area_rows,
        "",
        "### Code LOC by Module (Python only)",
        *module_pie_lines,
        "",
        "### Top Python Modules (src/rglob)",
        *module_rows,
        "",
        "_Note: LOC approximates non-blank, non-comment lines. Module "
        "breakdown counts only Python files._",
    ]
    return "\n".join(md)


def update_overview(new_section: str) -> None:
    """Insert or append the generated stats section in ``OVERVIEW.md``."""
    begin = "<!-- BEGIN: REPO-STATS -->"
    end = "<!-- END: REPO-STATS -->"
    generated = f"{begin}\n\n{new_section}\n\n{end}\n"

    if not OVERVIEW_PATH.exists():
        OVERVIEW_PATH.write_text(
            "# rglob — Repository Overview\n\n"
            "Auto-generated repository stats live below; everything outside\n"
            "the `REPO-STATS` markers is hand-written.\n\n" + generated,
            encoding="utf-8",
        )
        return

    content = OVERVIEW_PATH.read_text(encoding="utf-8")
    if begin in content and end in content:
        pre, _, rest = content.partition(begin)
        _, _, post = rest.partition(end)
        OVERVIEW_PATH.write_text(pre + generated + post, encoding="utf-8")
    else:
        OVERVIEW_PATH.write_text(content.rstrip() + "\n\n---\n\n" + generated, encoding="utf-8")


def main() -> None:
    """Generate current stats and persist them to ``OVERVIEW.md``."""
    stats = aggregate_stats()
    md = generate_markdown(stats)
    update_overview(md)
    print(f"Updated {OVERVIEW_PATH.relative_to(REPO_ROOT)} with repository stats section.")


if __name__ == "__main__":
    main()
