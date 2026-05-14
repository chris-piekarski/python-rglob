"""Typer-powered command-line interface for `rglob`.

This is the Phase 4 rewrite. The subcommand surface (`find`, `lcount`,
`tsize`) and their legacy flags (`--base`, `--no-empty`, `--no-comments`,
`--unit`) are byte-compatible with the 1.x argparse CLI. New filter and
output flags are layered on top per the modernization roadmap.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from rglob import find as _find
from rglob.rglob import (
    gigabytes,
    kilobytes,
    megabytes,
    terabytes,
)
from rglob.rglob import (
    lcount as _lcount,
)
from rglob.rglob import (
    tsize as _tsize,
)

_console = Console()
_err = Console(stderr=True)

app = typer.Typer(
    no_args_is_help=True,
    rich_markup_mode="rich",
    pretty_exceptions_enable=False,
    help="Recursive file operations: find, lcount, tsize.",
    epilog=(
        "Quote your patterns so the shell doesn't pre-expand them.\n"
        'Example: rglob find "*.py" (not rglob find *.py).'
    ),
)


# ─── Shared filter options ────────────────────────────────────────────────────

# Repeated as Annotated aliases so each command can opt in selectively without
# stringly-typed `**kwargs` plumbing.
BaseOpt = Annotated[Path, typer.Option("--base", help="Base directory to walk.")]
ExcludeOpt = Annotated[
    list[str],
    typer.Option("-E", "--exclude", help="Glob(s) to exclude (and prune from descent)."),
]
MaxDepthOpt = Annotated[
    int | None,
    typer.Option("-d", "--max-depth", min=0, help="Maximum recursion depth (None=unbounded)."),
]
HiddenOpt = Annotated[
    bool,
    typer.Option("-H", "--hidden", help="Include dotfiles and dot-directories."),
]
FollowOpt = Annotated[
    bool,
    typer.Option("-L", "--follow", help="Follow symlinks (cycles are auto-detected)."),
]
CaseSensitiveOpt = Annotated[
    bool | None,
    typer.Option(
        "-s/-i",
        "--case-sensitive/--case-insensitive",
        help="Force case sensitivity (default: follow host OS).",
    ),
]
GitignoreOpt = Annotated[
    bool,
    typer.Option(
        "--gitignore/--no-gitignore",
        help="Honour .gitignore files (lands fully in Phase 5).",
    ),
]


def _detect_pre_expansion(patterns: Iterable[str]) -> None:
    """Warn if the shell appears to have pre-expanded glob patterns."""
    pats = list(patterns)
    if len(pats) > 1 and not any(any(c in p for c in "*?[") for p in pats):
        _err.print(
            "[yellow]warning:[/yellow] received multiple patterns with no "
            "glob metacharacters — did your shell pre-expand them? Quote "
            'with "..." to avoid this.',
            highlight=False,
        )


def _resolve_case_sensitive(value: bool | None) -> bool | None:
    """Pass-through; kept as a seam in case future flags want to override."""
    return value


def _format_path(path: Path, fmt: str | None, base: Path) -> str:
    """Render a path according to the optional `--format` template."""
    if fmt is None:
        return str(path)
    try:
        size = path.stat().st_size if path.is_file() else 0
    except OSError:
        size = 0
    return fmt.format(
        path=path,
        rel=path.relative_to(base) if path.is_absolute() else path,
        name=path.name,
        size=size,
        size_kb=kilobytes(size),
        size_mb=megabytes(size),
    )


# ─── find ─────────────────────────────────────────────────────────────────────


@app.command(help="List paths matching one or more glob patterns.")
def find(
    patterns: Annotated[
        list[str],
        typer.Argument(
            help='Glob pattern(s). Quote them, e.g. "*.py".',
            show_default=False,
        ),
    ],
    base: BaseOpt = Path.cwd(),
    exclude: ExcludeOpt = [],
    max_depth: MaxDepthOpt = None,
    hidden: HiddenOpt = False,
    follow: FollowOpt = False,
    case_sensitive: CaseSensitiveOpt = None,
    gitignore: GitignoreOpt = False,
    kind: Annotated[
        list[str],
        typer.Option(
            "-t",
            "--type",
            help='Match only "f"=file, "d"=dir, "l"=symlink, "x"=executable. Repeatable.',
        ),
    ] = [],
    min_size: Annotated[
        str | None,
        typer.Option("--min-size", help='Minimum file size, e.g. "1K", "5MiB".'),
    ] = None,
    max_size: Annotated[
        str | None,
        typer.Option("--max-size", help="Maximum file size."),
    ] = None,
    newer_than: Annotated[
        str | None,
        typer.Option("--newer-than", help='ISO date or duration like "7d".'),
    ] = None,
    older_than: Annotated[
        str | None,
        typer.Option("--older-than", help='ISO date or duration like "30d".'),
    ] = None,
    json_out: Annotated[bool, typer.Option("--json", help="Emit a JSON array of paths.")] = False,
    jsonl: Annotated[
        bool,
        typer.Option(
            "--jsonl",
            help="Emit one JSON object per line ({'path': ..., 'size': ...}).",
        ),
    ] = False,
    null: Annotated[
        bool,
        typer.Option("-0", "--null", help="Separate paths with NUL bytes (xargs -0)."),
    ] = False,
    fmt: Annotated[
        str | None,
        typer.Option(
            "--format",
            help='Mini-template, e.g. "{path} {size_mb:.2f} MiB".',
        ),
    ] = None,
) -> None:
    """Print paths under ``base`` matching ``patterns``."""
    _detect_pre_expansion(patterns)
    from typing import cast

    from rglob._filters import Kind

    matches = _find(
        base,
        patterns,
        exclude=tuple(exclude),
        max_depth=max_depth,
        hidden=hidden,
        follow_symlinks=follow,
        case_sensitive=_resolve_case_sensitive(case_sensitive),
        on_error="warn",
        kinds=cast("list[Kind]", kind),
        min_size=min_size,
        max_size=max_size,
        newer_than=newer_than,
        older_than=older_than,
        respect_gitignore=gitignore,
    )

    if json_out:
        paths = [str(p) for p in matches]
        _console.print_json(json.dumps(paths))
        return

    if jsonl:
        for path in matches:
            try:
                size = path.stat().st_size if path.is_file() else 0
            except OSError:
                size = 0
            sys.stdout.write(json.dumps({"path": str(path), "size": size}) + "\n")
        return

    if null:
        for path in matches:
            sys.stdout.write(str(path) + "\0")
        return

    for path in matches:
        print(_format_path(path, fmt, base))


# ─── lcount ───────────────────────────────────────────────────────────────────


def _line_filter(no_empty: bool, no_comments: bool) -> Callable[[str], bool]:
    """Build the line predicate used by `lcount`."""
    predicates: list[Callable[[str], bool]] = []
    if no_empty:
        predicates.append(lambda line: bool(line.strip()))
    if no_comments:
        predicates.append(lambda line: not line.strip().startswith("#"))
    if not predicates:
        return lambda _line: True
    return lambda line: all(p(line) for p in predicates)


@app.command(help="Count lines across files matching a glob pattern.")
def lcount(
    pattern: Annotated[str, typer.Argument(help='Glob pattern, e.g. "*.py".')],
    base: BaseOpt = Path.cwd(),
    no_empty: Annotated[bool, typer.Option("--no-empty", help="Skip empty lines.")] = False,
    no_comments: Annotated[
        bool,
        typer.Option("--no-comments", help="Skip lines starting with `#`."),
    ] = False,
) -> None:
    """Print the total line count."""
    count = _lcount(str(base), pattern, func=_line_filter(no_empty, no_comments))
    print(f"Total lines: {count}")


# ─── tsize ────────────────────────────────────────────────────────────────────

_UNIT_FUNCS: dict[str, Callable[[float], float]] = {
    "kb": kilobytes,
    "mb": megabytes,
    "gb": gigabytes,
    "tb": terabytes,
}


@app.command(help="Sum the total size of files matching a glob pattern.")
def tsize(
    pattern: Annotated[str, typer.Argument(help='Glob pattern, e.g. "*.py".')],
    base: BaseOpt = Path.cwd(),
    unit: Annotated[
        str,
        typer.Option("--unit", help="Unit (kb/mb/gb/tb).", case_sensitive=False),
    ] = "mb",
) -> None:
    """Print the total size in the chosen unit."""
    unit_key = unit.lower()
    if unit_key not in _UNIT_FUNCS:
        _err.print(
            f"[red]error:[/red] unknown unit '{unit}' (expected one of: {', '.join(_UNIT_FUNCS)})"
        )
        raise typer.Exit(code=2)
    total = _tsize(str(base), pattern, func=_UNIT_FUNCS[unit_key])
    print(f"Total size: {total:.2f} {unit_key.upper()}")


# ─── stats / tree / top / dupes (Phase 5 fun features) ────────────────────────


@app.command(help="Summarise a glob result: count, total size, extension breakdown.")
def stats(
    pattern: Annotated[str, typer.Argument(help='Glob pattern, e.g. "*.py".')] = "*",
    base: BaseOpt = Path.cwd(),
    hidden: HiddenOpt = False,
    follow: FollowOpt = False,
) -> None:
    """Print a Rich summary table for the matching files."""
    from collections import Counter

    from rich.table import Table

    paths = list(
        _find(
            base,
            pattern,
            hidden=hidden,
            follow_symlinks=follow,
            kinds=("f",),
            on_error="warn",
        )
    )
    total_bytes = 0
    ext_counter: Counter[str] = Counter()
    ext_bytes: Counter[str] = Counter()
    for p in paths:
        try:
            size = p.stat().st_size
        except OSError:
            size = 0
        ext = p.suffix.lower() or "(none)"
        total_bytes += size
        ext_counter[ext] += 1
        ext_bytes[ext] += size

    summary = Table(title=f"stats: {pattern!r} under {base}")
    summary.add_column("Metric", style="cyan")
    summary.add_column("Value", justify="right")
    summary.add_row("Files", str(len(paths)))
    summary.add_row("Total size", f"{megabytes(total_bytes):.2f} MiB")
    summary.add_row("Largest extension", ext_counter.most_common(1)[0][0] if ext_counter else "—")
    _console.print(summary)

    if ext_counter:
        breakdown = Table(title="By extension")
        breakdown.add_column("Ext", style="green")
        breakdown.add_column("Count", justify="right")
        breakdown.add_column("Size (MiB)", justify="right")
        for ext, count in ext_counter.most_common():
            breakdown.add_row(ext, str(count), f"{megabytes(ext_bytes[ext]):.2f}")
        _console.print(breakdown)


@app.command(help="Render a Unicode tree of matches (depth-limited by default).")
def tree(
    pattern: Annotated[str, typer.Argument(help='Glob pattern, e.g. "*".')] = "*",
    base: BaseOpt = Path.cwd(),
    max_depth: MaxDepthOpt = 3,
    hidden: HiddenOpt = False,
) -> None:
    """Print a Rich tree of matching paths under ``base``."""
    from rich.tree import Tree

    paths = sorted(
        _find(
            base,
            pattern,
            max_depth=max_depth,
            hidden=hidden,
            on_error="warn",
        )
    )

    root = Tree(f"[bold]{base}[/bold]")
    nodes: dict[Path, Tree] = {base: root}
    for path in paths:
        parents: list[Path] = []
        cur = path.parent
        while cur != base and cur.parent != cur:
            parents.append(cur)
            cur = cur.parent
        parents.reverse()
        for parent in parents:
            if parent not in nodes:
                nodes[parent] = nodes[parent.parent].add(f"[blue]{parent.name}/[/blue]")
        marker = "📁" if path.is_dir() else "📄"
        nodes[path] = nodes[path.parent].add(f"{marker} {path.name}")
    _console.print(root)


@app.command(help="Show the top-N largest files matching a pattern.")
def top(
    pattern: Annotated[str, typer.Argument(help='Glob pattern, e.g. "*.log".')] = "*",
    base: BaseOpt = Path.cwd(),
    n: Annotated[int, typer.Option("-n", "--n", min=1, help="Number of entries.")] = 10,
    hidden: HiddenOpt = False,
) -> None:
    """Print a Rich table of the N largest files."""
    from rich.table import Table

    sized: list[tuple[int, Path]] = []
    for p in _find(base, pattern, hidden=hidden, kinds=("f",), on_error="warn"):
        try:
            sized.append((p.stat().st_size, p))
        except OSError:
            continue
    sized.sort(reverse=True)
    top_n = sized[:n]

    table = Table(title=f"Top {n} largest files matching {pattern!r}")
    table.add_column("Rank", justify="right", style="cyan")
    table.add_column("Size (MiB)", justify="right")
    table.add_column("Path", style="green")
    for rank, (size, path) in enumerate(top_n, start=1):
        table.add_row(str(rank), f"{megabytes(size):.3f}", str(path))
    _console.print(table)


@app.command(help="Find groups of duplicate files (by content hash).")
def dupes(
    pattern: Annotated[str, typer.Argument(help='Glob pattern, e.g. "*".')] = "*",
    base: BaseOpt = Path.cwd(),
    min_size: Annotated[
        str | None,
        typer.Option(
            "--min-size",
            help='Ignore files smaller than this (e.g. "1K").',
        ),
    ] = None,
    hidden: HiddenOpt = False,
) -> None:
    """Print groups of duplicate files under ``base``."""
    from rich.table import Table

    from rglob._dupes import find_duplicates

    files = list(
        _find(
            base,
            pattern,
            kinds=("f",),
            hidden=hidden,
            min_size=min_size,
            on_error="warn",
        )
    )
    groups = find_duplicates(files)
    if not groups:
        _console.print("[green]No duplicates found.[/green]")
        return

    table = Table(title=f"Duplicate groups: {len(groups)}")
    table.add_column("Group", justify="right", style="cyan")
    table.add_column("Size (MiB)", justify="right")
    table.add_column("Paths", style="green")
    for idx, group in enumerate(groups, start=1):
        try:
            size = group[0].stat().st_size
        except OSError:  # pragma: no cover - races between scan and display
            size = 0
        table.add_row(str(idx), f"{megabytes(size):.3f}", "\n".join(str(p) for p in group))
    _console.print(table)


# ─── Entry point ──────────────────────────────────────────────────────────────


def main() -> None:
    """Entry point referenced by `[project.scripts] rglob` in pyproject.toml."""
    app()


if __name__ == "__main__":  # pragma: no cover - guarded `python -m` entry
    main()
