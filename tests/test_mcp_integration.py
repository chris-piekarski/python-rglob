"""Real-protocol integration test for `rglob mcp`.

Spawns the actual `rglob mcp` subprocess and drives it through the
official `mcp` SDK's stdio client. This catches breakage that mocked
unit tests cannot — for example, importing the wrong server class
(`mcp.server.Server` vs `mcp.server.fastmcp.FastMCP`), schema-
serialization issues over the wire, or async-loop bugs in the entry
point.

The test is skipped when the optional `[mcp]` extra is not installed
so the rest of the suite remains runnable on a minimal env.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

mcp_client = pytest.importorskip("mcp.client.stdio")
mcp_session = pytest.importorskip("mcp")

from mcp import ClientSession, StdioServerParameters  # noqa: E402
from mcp.client.stdio import stdio_client  # noqa: E402


def _server_params() -> StdioServerParameters:
    """Build the subprocess invocation for the rglob MCP server."""
    return StdioServerParameters(
        command=sys.executable,
        args=["-m", "rglob.cli", "mcp"],
        env=None,
    )


@pytest.mark.asyncio
async def test_mcp_lists_documented_tools(tmp_path: Path) -> None:
    """A real MCP `tools/list` request returns the five documented tools."""
    async with (
        stdio_client(_server_params()) as (read, write),
        ClientSession(read, write) as session,
    ):
        await session.initialize()
        tools = await session.list_tools()
        names = {tool.name for tool in tools.tools}

    assert names >= {
        "find_files",
        "grep_content",
        "count_lines",
        "find_duplicate_files",
        "describe_subcommand",
    }


@pytest.mark.asyncio
async def test_mcp_find_files_returns_search_result(tmp_path: Path) -> None:
    """`find_files` over a real subprocess returns FileSearchResult-shaped JSON."""
    (tmp_path / "alpha.py").write_text("a\n", encoding="utf-8")
    (tmp_path / "beta.py").write_text("b\n", encoding="utf-8")
    (tmp_path / "gamma.txt").write_text("g\n", encoding="utf-8")

    async with (
        stdio_client(_server_params()) as (read, write),
        ClientSession(read, write) as session,
    ):
        await session.initialize()
        result = await session.call_tool(
            "find_files",
            {"pattern": "*.py", "base": str(tmp_path)},
        )

    payload = _structured_payload(result)
    assert isinstance(payload, dict)
    assert {"results", "truncated", "total_files_searched"} <= set(payload)
    names = sorted(Path(match["path"]).name for match in payload["results"])
    assert names == ["alpha.py", "beta.py"]


@pytest.mark.asyncio
async def test_mcp_grep_content_returns_line_search_result(tmp_path: Path) -> None:
    """`grep_content` returns LineSearchResult records over the wire."""
    (tmp_path / "notes.txt").write_text("TODO one\nfine\nTODO two\n", encoding="utf-8")

    async with (
        stdio_client(_server_params()) as (read, write),
        ClientSession(read, write) as session,
    ):
        await session.initialize()
        result = await session.call_tool(
            "grep_content",
            {"pattern": "TODO", "paths": ["*.txt"], "base": str(tmp_path)},
        )

    payload = _structured_payload(result)
    assert isinstance(payload, dict)
    contents = sorted(match["content"] for match in payload["results"])
    assert contents == ["TODO one", "TODO two"]


@pytest.mark.asyncio
async def test_mcp_describe_subcommand_returns_manifest() -> None:
    """`describe_subcommand` returns the same manifest the CLI emits."""
    async with (
        stdio_client(_server_params()) as (read, write),
        ClientSession(read, write) as session,
    ):
        await session.initialize()
        result = await session.call_tool(
            "describe_subcommand",
            {"name": "find"},
        )

    payload = _structured_payload(result)
    assert isinstance(payload, dict)
    assert payload["name"] == "find"
    assert payload["agent_api_version"] == "1.0"
    assert "schemas" in payload


def _structured_payload(call_result: object) -> object:
    """Extract the JSON-serialisable payload from an MCP CallToolResult.

    The `mcp` SDK exposes a tool result as either a list of content blocks
    (older versions) or a `structured_content` field (newer versions).
    Older versions return a `TextContent` whose `.text` is a JSON string;
    we parse that to get the same dict shape.
    """
    import json

    # `structuredContent` is FastMCP/MCP SDK's camelCase Pydantic field;
    # newer SDKs may also expose `structured_content` as an alias.
    structured = getattr(call_result, "structuredContent", None)
    if structured is None:
        structured = getattr(call_result, "structured_content", None)
    if structured is not None:
        # FastMCP wraps non-Pydantic-model returns in {"result": <value>}
        # because the MCP spec requires structured content to be a JSON
        # object. Unwrap so callers see the underlying SearchResult shape.
        if isinstance(structured, dict) and set(structured) == {"result"}:
            return structured["result"]
        return structured
    content = getattr(call_result, "content", None)
    if content:
        first = content[0]
        text = getattr(first, "text", None)
        if text is not None:
            return json.loads(text)
    raise AssertionError(f"unexpected MCP result shape: {call_result!r}")
