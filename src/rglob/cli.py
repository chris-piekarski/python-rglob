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
from typing import Annotated, NoReturn

import typer
from rich.console import Console

from rglob import find as _find
from rglob._count import count_all
from rglob._grep import grep_all
from rglob.agent._introspection import (
    all_schemas,
    capability_report,
    command_schema,
    describe_command,
    json_ready,
    unknown_command_envelope,
)
from rglob.agent._models import (
    AGENT_API_VERSION,
    CountOptions,
    ErrorCode,
    ErrorInfo,
    GrepOptions,
    to_json_dict,
)
from rglob.agent._runtime import collect_file_search
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


def _emit_json(payload: object) -> None:
    """Write stable JSON to stdout without Rich styling."""
    sys.stdout.write(json.dumps(json_ready(payload), indent=2, sort_keys=True) + "\n")


def _emit_jsonl(payload: object) -> None:
    """Write one compact JSON object line."""
    sys.stdout.write(json.dumps(json_ready(payload), sort_keys=True) + "\n")


def _emit_grep_jsonl_stream(opts: GrepOptions) -> None:
    """Stream grep matches as JSONL records, then a final summary line.

    Each match emits as a compact JSON object on its own line (so agents
    can begin processing without buffering the whole result). When the
    search completes, a final summary line is emitted with `truncated`,
    `truncated_reason`, `total_files_searched`, `bytes_read`, and
    `errors` so the consumer knows the stream is complete and how much
    work happened. Each record carries a `kind` field (``"match"`` or
    ``"summary"``) for easy dispatch.
    """
    # Single pass over the underlying search; we iterate the materialised
    # results list so future refactors that make `grep_iter` truly lazy
    # can swap in here without changing the wire format.
    result = grep_all(opts)
    for match in result.results:
        # `json_ready` returns a JsonValue union; for a dataclass input
        # it's always a dict. The cast keeps mypy strict happy without
        # narrowing the return-type contract of `json_ready` itself.
        from typing import cast

        match_payload = cast("dict[str, object]", json_ready(match))
        sys.stdout.write(json.dumps({"kind": "match", **match_payload}, sort_keys=True) + "\n")
        sys.stdout.flush()
    sys.stdout.write(
        json.dumps(
            {
                "kind": "summary",
                "truncated": result.truncated,
                "truncated_reason": result.truncated_reason,
                "total_files_searched": result.total_files_searched,
                "bytes_read": result.bytes_read,
                "errors": [json_ready(e) for e in result.errors],
            },
            sort_keys=True,
        )
        + "\n"
    )


def _exit_bad_predicate(message: str, *, structured: bool) -> NoReturn:
    """Exit with either a machine-readable or human-readable predicate error."""
    if structured:
        _emit_json(
            {
                "ok": False,
                "error": to_json_dict(ErrorInfo(ErrorCode.BAD_PREDICATE, message, None)),
            }
        )
        raise typer.Exit(code=2)
    _err.print(f"[red]error:[/red] {message}")
    raise typer.Exit(code=2)


def _parse_size_option(value: str | None, *, structured: bool) -> int | None:
    """Parse a size option for structured commands."""
    if value is None:
        return None
    from rglob._filters import parse_size

    try:
        return parse_size(value)
    except ValueError as exc:
        _exit_bad_predicate(str(exc), structured=structured)


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
    newer_than_file: Annotated[
        Path | None,
        typer.Option("--newer-than-file", help="Only entries newer than this file."),
    ] = None,
    perm: Annotated[
        str | None,
        typer.Option("--perm", help='POSIX mode filter, e.g. "644", "-111", "/222".'),
    ] = None,
    uid: Annotated[
        int | None,
        typer.Option("--uid", help="POSIX owner uid filter."),
    ] = None,
    gid: Annotated[
        int | None,
        typer.Option("--gid", help="POSIX owner gid filter."),
    ] = None,
    json_out: Annotated[
        bool,
        typer.Option("--json", help="Emit a FileSearchResult JSON object."),
    ] = False,
    jsonl: Annotated[
        bool,
        typer.Option(
            "--jsonl",
            help="Emit one compact FileSearchResult JSON object line.",
        ),
    ] = False,
    limit: Annotated[
        int | None,
        typer.Option("--limit", min=1, help="Maximum structured records to emit."),
    ] = None,
    max_bytes: Annotated[
        str | None,
        typer.Option("--max-bytes", help="Maximum structured output bytes."),
    ] = None,
    max_file_size: Annotated[
        str | None,
        typer.Option("--max-file-size", help="Skip files larger than this."),
    ] = None,
    include_errors: Annotated[
        bool,
        typer.Option(
            "--include-errors/--no-include-errors",
            help="Include per-record errors in structured output.",
        ),
    ] = True,
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

    max_bytes_value = _parse_size_option(max_bytes, structured=json_out or jsonl)

    matches = _find(
        base,
        patterns,
        exclude=tuple(exclude),
        max_depth=max_depth,
        hidden=hidden,
        follow_symlinks=follow,
        case_sensitive=_resolve_case_sensitive(case_sensitive),
        on_error="ignore" if json_out or jsonl else "warn",
        kinds=cast("list[Kind]", kind),
        min_size=min_size,
        max_size=max_file_size or max_size,
        newer_than=newer_than,
        older_than=older_than,
        newer_than_file=newer_than_file,
        perm=perm,
        uid=uid,
        gid=gid,
        respect_gitignore=gitignore,
    )

    if json_out:
        _emit_json(
            collect_file_search(
                matches,
                base=base,
                limit=limit,
                max_bytes=max_bytes_value,
                include_errors=include_errors,
            )
        )
        return

    if jsonl:
        _emit_jsonl(
            collect_file_search(
                matches,
                base=base,
                limit=limit,
                max_bytes=max_bytes_value,
                include_errors=include_errors,
            )
        )
        return

    if null:
        for path in matches:
            sys.stdout.write(str(path) + "\0")
        return

    for path in matches:
        print(_format_path(path, fmt, base))


# ─── grep / count ────────────────────────────────────────────────────────────


@app.command(help="Search file contents for a regex or fixed string.")
def grep(
    pattern: Annotated[str, typer.Argument(help="Regex or fixed string to search for.")],
    files_or_globs: Annotated[
        list[str],
        typer.Argument(help='File glob(s) to search, e.g. "src/**/*.py".'),
    ] = [],
    base: BaseOpt = Path.cwd(),
    exclude: ExcludeOpt = [],
    max_depth: MaxDepthOpt = None,
    hidden: HiddenOpt = False,
    follow: FollowOpt = False,
    case_sensitive: CaseSensitiveOpt = None,
    gitignore: GitignoreOpt = False,
    fixed_string: Annotated[
        bool,
        typer.Option("-F", "--fixed-string", help="Treat pattern as a literal string."),
    ] = False,
    ignore_case: Annotated[
        bool,
        typer.Option("-i", "--ignore-case", help="Match content case-insensitively."),
    ] = False,
    context: Annotated[int, typer.Option("-C", "--context", min=0, help="Context lines.")] = 0,
    before: Annotated[int, typer.Option("-B", "--before", min=0, help="Lines before.")] = 0,
    after: Annotated[int, typer.Option("-A", "--after", min=0, help="Lines after.")] = 0,
    max_count: Annotated[
        int | None,
        typer.Option("-m", "--max-count", min=1, help="Maximum matches to return."),
    ] = None,
    word: Annotated[bool, typer.Option("-w", "--word", help="Match whole words.")] = False,
    invert: Annotated[bool, typer.Option("-v", "--invert", help="Invert the match.")] = False,
    encoding: Annotated[str, typer.Option("--encoding", help="Text encoding.")] = "utf-8",
    text: Annotated[
        bool,
        typer.Option("-a", "--text", help="Search binary files as text."),
    ] = False,
    limit: Annotated[
        int | None,
        typer.Option("--limit", min=1, help="Maximum structured matches to emit."),
    ] = None,
    max_bytes: Annotated[
        str | None,
        typer.Option("--max-bytes", help="Maximum bytes to read."),
    ] = None,
    max_file_size: Annotated[
        str | None,
        typer.Option("--max-file-size", help="Skip files larger than this."),
    ] = None,
    files_with_matches_flag: Annotated[
        bool,
        typer.Option(
            "-l",
            "--files-with-matches",
            help="Emit one record per matching file, no per-line content.",
        ),
    ] = False,
    count_only_flag: Annotated[
        bool,
        typer.Option(
            "-c",
            "--count-only",
            help="Emit one record per matching file with the match count.",
        ),
    ] = False,
    json_out: Annotated[bool, typer.Option("--json", help="Emit a LineSearchResult.")] = False,
    jsonl: Annotated[
        bool,
        typer.Option(
            "--jsonl",
            help="Stream one LineMatch per line, then a final summary line.",
        ),
    ] = False,
) -> None:
    """Search matching files and print content matches."""
    if files_with_matches_flag and count_only_flag:
        _err.print(
            "[red]error:[/red] --files-with-matches and --count-only are mutually exclusive",
            highlight=False,
        )
        raise typer.Exit(code=2)
    structured = json_out or jsonl
    opts = GrepOptions(
        pattern=pattern,
        paths=files_or_globs or ["*"],
        base=base,
        exclude=exclude,
        max_depth=max_depth,
        hidden=hidden,
        follow_symlinks=follow,
        case_sensitive=_resolve_case_sensitive(case_sensitive),
        respect_gitignore=gitignore,
        fixed_string=fixed_string,
        ignore_case=ignore_case,
        context=context,
        before=before,
        after=after,
        max_count=max_count,
        word=word,
        invert=invert,
        encoding=encoding,
        text=text,
        limit=limit,
        max_bytes=_parse_size_option(max_bytes, structured=structured),
        max_file_size=_parse_size_option(max_file_size, structured=structured),
        files_with_matches=files_with_matches_flag,
        count_only=count_only_flag,
    )

    # Streaming JSONL emits each match as it's found, then a final
    # summary record so consumers don't have to buffer the whole result.
    if jsonl:
        _emit_grep_jsonl_stream(opts)
        return

    result = grep_all(opts)

    if json_out:
        _emit_json(result)
        return

    if files_with_matches_flag:
        for match in result.results:
            print(match.path)
    elif count_only_flag:
        for match in result.results:
            print(f"{match.path}:{match.line_number}")
    else:
        for match in result.results:
            print(f"{match.path}:{match.line_number}:{match.content}")
    for error in result.errors:
        _err.print(f"[yellow]warning:[/yellow] {error.code}: {error.message}", highlight=False)


@app.command(help="Count files, lines, and bytes for matching files.")
def count(
    patterns: Annotated[
        list[str],
        typer.Argument(help='Glob pattern(s), e.g. "*.py".', show_default=False),
    ],
    base: BaseOpt = Path.cwd(),
    exclude: ExcludeOpt = [],
    max_depth: MaxDepthOpt = None,
    hidden: HiddenOpt = False,
    follow: FollowOpt = False,
    case_sensitive: CaseSensitiveOpt = None,
    gitignore: GitignoreOpt = False,
    no_empty: Annotated[bool, typer.Option("--no-empty", help="Skip empty lines.")] = False,
    no_comments: Annotated[
        bool,
        typer.Option("--no-comments", help="Skip lines starting with `#`."),
    ] = False,
    encoding: Annotated[str, typer.Option("--encoding", help="Text encoding.")] = "utf-8",
    limit: Annotated[
        int | None,
        typer.Option("--limit", min=1, help="Maximum files to count."),
    ] = None,
    max_bytes: Annotated[
        str | None,
        typer.Option("--max-bytes", help="Maximum bytes to read."),
    ] = None,
    max_file_size: Annotated[
        str | None,
        typer.Option("--max-file-size", help="Skip files larger than this."),
    ] = None,
    json_out: Annotated[bool, typer.Option("--json", help="Emit a Stats object.")] = False,
    jsonl: Annotated[
        bool,
        typer.Option("--jsonl", help="Emit one compact Stats object line."),
    ] = False,
) -> None:
    """Print structured file, line, and byte counts."""
    structured = json_out or jsonl
    opts = CountOptions(
        patterns=patterns,
        base=base,
        exclude=exclude,
        max_depth=max_depth,
        hidden=hidden,
        follow_symlinks=follow,
        case_sensitive=_resolve_case_sensitive(case_sensitive),
        respect_gitignore=gitignore,
        no_empty=no_empty,
        no_comments=no_comments,
        encoding=encoding,
        limit=limit,
        max_bytes=_parse_size_option(max_bytes, structured=structured),
        max_file_size=_parse_size_option(max_file_size, structured=structured),
    )
    result = count_all(opts)

    if json_out:
        _emit_json(result)
        return
    if jsonl:
        _emit_jsonl(result)
        return

    print(f"Files: {result.files}")
    print(f"Lines: {result.lines}")
    print(f"Bytes: {result.bytes}")


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
        table.add_row(str(rank), f"{megabytes(size):.3f}", path.name)
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
        table.add_row(str(idx), f"{megabytes(size):.3f}", "\n".join(p.name for p in group))
    _console.print(table)


# ─── Agent introspection ─────────────────────────────────────────────────────


@app.command(help="Describe a subcommand as a stable JSON manifest.")
def describe(
    subcommand: Annotated[str, typer.Argument(help="Subcommand to describe.")],
) -> None:
    """Print a machine-readable command manifest."""
    try:
        _emit_json(describe_command(subcommand))
    except ValueError:
        _emit_json(unknown_command_envelope(subcommand))
        raise typer.Exit(code=2) from None


@app.command(help="Print input and output JSON Schemas for a subcommand.")
def schema(
    subcommand: Annotated[str | None, typer.Argument(help="Subcommand to inspect.")] = None,
    all_: Annotated[
        bool,
        typer.Option("--all", help="Print every public agent JSON Schema."),
    ] = False,
) -> None:
    """Print a command's input and output schemas."""
    if all_:
        _emit_json(all_schemas())
        return
    if subcommand is None:
        _emit_json(unknown_command_envelope("<missing>"))
        raise typer.Exit(code=2) from None
    try:
        _emit_json(command_schema(subcommand))
    except ValueError:
        _emit_json(unknown_command_envelope(subcommand))
        raise typer.Exit(code=2) from None


@app.command(help="Report installed agent-facing capabilities as JSON.")
def capabilities(
    json_out: Annotated[
        bool,
        typer.Option(
            "--json",
            help="Accepted for explicit machine callers; output is always JSON.",
        ),
    ] = False,
) -> None:
    """Print the agent capability report."""
    _ = json_out
    _emit_json(capability_report())


@app.command(help="Print the current agent API version as JSON.")
def agent_version() -> None:
    """Print the current agent API version."""
    _emit_json(AGENT_API_VERSION)


@app.command(help="Run the rglob stdio MCP server.")
def mcp() -> None:
    """Launch the optional stdio MCP server."""
    try:
        from rglob.agent.mcp import main as mcp_main

        mcp_main()
    except RuntimeError as exc:
        _emit_json(
            {
                "ok": False,
                "error": to_json_dict(ErrorInfo(ErrorCode.UNSUPPORTED_PLATFORM, str(exc), None)),
            }
        )
        raise typer.Exit(code=2) from exc


# ─── Entry point ──────────────────────────────────────────────────────────────


def main() -> None:
    """Entry point referenced by `[project.scripts] rglob` in pyproject.toml."""
    app()


if __name__ == "__main__":  # pragma: no cover - guarded `python -m` entry
    main()
