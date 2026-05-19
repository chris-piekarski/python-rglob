"""Stdio MCP server for the rglob agent API."""

import asyncio
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Protocol, cast

from rglob.agent import (
    CountOptions,
    GrepOptions,
    WalkOptions,
    count,
    find_duplicates,
    grep_all,
    search_all,
    to_json_dict,
)
from rglob.agent._introspection import describe_command, json_ready
from rglob.agent._models import JsonValue

ToolHandler = Callable[..., Awaitable[JsonValue]]
ToolDecorator = Callable[[ToolHandler], ToolHandler]
IntLike = str | int | float


class McpServer(Protocol):
    """Small protocol covering the MCP SDK surface we use."""

    def tool(self) -> ToolDecorator:
        """Return a decorator that registers an async tool."""

    async def run_stdio_async(self) -> None:
        """Run the stdio transport."""


ServerFactory = Callable[[str], McpServer]


def _load_server_factory() -> ServerFactory:
    """Import the official MCP FastMCP class lazily.

    `FastMCP` is the high-level server API the rest of this module is
    written against (it provides the `@server.tool()` decorator and
    `run_stdio_async()` coroutine). The low-level `mcp.server.Server`
    class uses a different `@server.list_tools()` / `@server.call_tool()`
    pattern and would not work here without a substantial rewrite.
    """
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:
        raise RuntimeError("rglob mcp requires the optional mcp extra") from exc
    return cast("ServerFactory", FastMCP)


def _walk_options(patterns: list[str], base: str, filters: dict[str, object]) -> WalkOptions:
    """Build conservative WalkOptions from MCP tool input."""
    return WalkOptions(
        patterns=patterns,
        base=Path(base),
        exclude=cast("list[str]", filters.get("exclude", [])),
        max_depth=cast("int | None", filters.get("max_depth")),
        hidden=bool(filters.get("hidden", False)),
        limit=cast("int | None", filters.get("limit", 5000)),
        max_bytes=cast("int | None", filters.get("max_bytes")),
        max_file_size=cast("int | None", filters.get("max_file_size")),
        strict_base=True,
        follow_symlinks=bool(filters.get("follow_symlinks", False)),
        respect_gitignore=bool(filters.get("respect_gitignore", False)),
        include_errors=bool(filters.get("include_errors", True)),
        case_sensitive=cast("bool | None", filters.get("case_sensitive")),
        sort=bool(filters.get("sort", True)),
    )


def _grep_options(
    pattern: str,
    paths: list[str],
    base: str,
    filters: dict[str, object],
) -> GrepOptions:
    """Build conservative GrepOptions from MCP tool input."""
    walk = _walk_options(paths, base, filters)
    return GrepOptions(
        pattern=pattern,
        paths=walk.patterns,
        base=walk.base,
        exclude=walk.exclude,
        max_depth=walk.max_depth,
        hidden=walk.hidden,
        limit=walk.limit,
        max_bytes=walk.max_bytes,
        max_file_size=walk.max_file_size,
        strict_base=walk.strict_base,
        follow_symlinks=walk.follow_symlinks,
        respect_gitignore=walk.respect_gitignore,
        include_errors=walk.include_errors,
        case_sensitive=walk.case_sensitive,
        sort=walk.sort,
        fixed_string=bool(filters.get("fixed_string", False)),
        ignore_case=bool(filters.get("ignore_case", False)),
        context=int(cast("IntLike", filters.get("context", 0))),
        before=int(cast("IntLike", filters.get("before", 0))),
        after=int(cast("IntLike", filters.get("after", 0))),
        max_count=cast("int | None", filters.get("max_count")),
        word=bool(filters.get("word", False)),
        invert=bool(filters.get("invert", False)),
        encoding=str(filters.get("encoding", "utf-8")),
        text=bool(filters.get("text", False)),
    )


def _count_options(pattern: str, base: str, filters: dict[str, object]) -> CountOptions:
    """Build conservative CountOptions from MCP tool input."""
    walk = _walk_options([pattern], base, filters)
    return CountOptions(
        patterns=walk.patterns,
        base=walk.base,
        exclude=walk.exclude,
        max_depth=walk.max_depth,
        hidden=walk.hidden,
        limit=walk.limit,
        max_bytes=walk.max_bytes,
        max_file_size=walk.max_file_size,
        strict_base=walk.strict_base,
        follow_symlinks=walk.follow_symlinks,
        respect_gitignore=walk.respect_gitignore,
        include_errors=walk.include_errors,
        case_sensitive=walk.case_sensitive,
        sort=walk.sort,
        no_empty=bool(filters.get("no_empty", False)),
        no_comments=bool(filters.get("no_comments", False)),
        encoding=str(filters.get("encoding", "utf-8")),
    )


def create_server(server_factory: ServerFactory | None = None) -> McpServer:
    """Create and register the rglob MCP server.

    Tool signatures intentionally inline every filter as a named keyword
    argument rather than using `**filters`. FastMCP introspects the
    function signature to build the public JSON Schema for the tool;
    `**kwargs` would render as a single opaque required `filters` dict
    that agents cannot discover the shape of, and would also break call
    validation (FastMCP requires every parameter to be explicit).
    """
    factory = server_factory or _load_server_factory()
    server = factory("rglob")

    @server.tool()
    async def find_files(
        pattern: str,
        base: str = ".",
        exclude: list[str] | None = None,
        max_depth: int | None = None,
        hidden: bool = False,
        follow_symlinks: bool = False,
        case_sensitive: bool | None = None,
        respect_gitignore: bool = False,
        limit: int | None = 5000,
        max_bytes: int | None = None,
        max_file_size: int | None = None,
    ) -> JsonValue:
        opts = _walk_options(
            [pattern],
            base,
            _walk_filter_dict(
                exclude=exclude,
                max_depth=max_depth,
                hidden=hidden,
                follow_symlinks=follow_symlinks,
                case_sensitive=case_sensitive,
                respect_gitignore=respect_gitignore,
                limit=limit,
                max_bytes=max_bytes,
                max_file_size=max_file_size,
            ),
        )
        return to_json_dict(search_all(opts))

    @server.tool()
    async def grep_content(
        pattern: str,
        paths: list[str] | None = None,
        base: str = ".",
        fixed_string: bool = False,
        ignore_case: bool = False,
        context: int = 0,
        before: int = 0,
        after: int = 0,
        max_count: int | None = None,
        word: bool = False,
        invert: bool = False,
        encoding: str = "utf-8",
        text: bool = False,
        exclude: list[str] | None = None,
        max_depth: int | None = None,
        hidden: bool = False,
        follow_symlinks: bool = False,
        case_sensitive: bool | None = None,
        respect_gitignore: bool = False,
        limit: int | None = 5000,
        max_bytes: int | None = None,
        max_file_size: int | None = None,
    ) -> JsonValue:
        filters = _walk_filter_dict(
            exclude=exclude,
            max_depth=max_depth,
            hidden=hidden,
            follow_symlinks=follow_symlinks,
            case_sensitive=case_sensitive,
            respect_gitignore=respect_gitignore,
            limit=limit,
            max_bytes=max_bytes,
            max_file_size=max_file_size,
        )
        filters.update(
            {
                "fixed_string": fixed_string,
                "ignore_case": ignore_case,
                "context": context,
                "before": before,
                "after": after,
                "max_count": max_count,
                "word": word,
                "invert": invert,
                "encoding": encoding,
                "text": text,
            }
        )
        opts = _grep_options(pattern, paths or ["*"], base, filters)
        return to_json_dict(grep_all(opts))

    @server.tool()
    async def count_lines(
        pattern: str,
        base: str = ".",
        no_empty: bool = False,
        no_comments: bool = False,
        encoding: str = "utf-8",
        exclude: list[str] | None = None,
        max_depth: int | None = None,
        hidden: bool = False,
        follow_symlinks: bool = False,
        case_sensitive: bool | None = None,
        respect_gitignore: bool = False,
        limit: int | None = 5000,
        max_bytes: int | None = None,
        max_file_size: int | None = None,
    ) -> JsonValue:
        filters = _walk_filter_dict(
            exclude=exclude,
            max_depth=max_depth,
            hidden=hidden,
            follow_symlinks=follow_symlinks,
            case_sensitive=case_sensitive,
            respect_gitignore=respect_gitignore,
            limit=limit,
            max_bytes=max_bytes,
            max_file_size=max_file_size,
        )
        filters.update({"no_empty": no_empty, "no_comments": no_comments, "encoding": encoding})
        opts = _count_options(pattern, base, filters)
        return to_json_dict(count(opts))

    @server.tool()
    async def find_duplicate_files(
        pattern: str,
        base: str = ".",
        exclude: list[str] | None = None,
        max_depth: int | None = None,
        hidden: bool = False,
        follow_symlinks: bool = False,
        case_sensitive: bool | None = None,
        respect_gitignore: bool = False,
        limit: int | None = 5000,
        max_bytes: int | None = None,
        max_file_size: int | None = None,
    ) -> JsonValue:
        opts = _walk_options(
            [pattern],
            base,
            _walk_filter_dict(
                exclude=exclude,
                max_depth=max_depth,
                hidden=hidden,
                follow_symlinks=follow_symlinks,
                case_sensitive=case_sensitive,
                respect_gitignore=respect_gitignore,
                limit=limit,
                max_bytes=max_bytes,
                max_file_size=max_file_size,
            ),
        )
        return to_json_dict(find_duplicates(opts))

    @server.tool()
    async def describe_subcommand(name: str) -> JsonValue:
        return json_ready(describe_command(name))

    return server


def _walk_filter_dict(
    *,
    exclude: list[str] | None,
    max_depth: int | None,
    hidden: bool,
    follow_symlinks: bool,
    case_sensitive: bool | None,
    respect_gitignore: bool,
    limit: int | None,
    max_bytes: int | None,
    max_file_size: int | None,
) -> dict[str, object]:
    """Collect the shared walker filter kwargs into a `_walk_options`-friendly dict."""
    return {
        "exclude": exclude or [],
        "max_depth": max_depth,
        "hidden": hidden,
        "follow_symlinks": follow_symlinks,
        "case_sensitive": case_sensitive,
        "respect_gitignore": respect_gitignore,
        "limit": limit,
        "max_bytes": max_bytes,
        "max_file_size": max_file_size,
    }


def main() -> None:
    """Run the stdio MCP server."""
    server = create_server()
    asyncio.run(server.run_stdio_async())
