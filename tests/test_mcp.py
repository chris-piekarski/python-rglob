"""Tests for the optional MCP server wrapper."""

from __future__ import annotations

import asyncio
import sys
import types
from collections.abc import Awaitable, Callable

from typer.testing import CliRunner

from rglob.agent import mcp as mcp_module
from rglob.cli import app

runner = CliRunner(env={"COLUMNS": "200"})


class FakeServer:
    """Tiny stand-in for the official MCP Server."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.tools: dict[str, Callable[..., Awaitable[object]]] = {}
        self.ran = False

    def tool(self):
        """Return a decorator that records tool functions."""

        def _register(func):
            self.tools[func.__name__] = func
            return func

        return _register

    async def run_stdio_async(self) -> None:
        """Record that the server was run."""
        self.ran = True


def test_create_server_registers_tools(tmp_path):
    """The MCP server exposes the planned tool list."""
    server = mcp_module.create_server(FakeServer)
    assert set(server.tools) == {
        "find_files",
        "grep_content",
        "count_lines",
        "find_duplicate_files",
        "describe_subcommand",
    }

    (tmp_path / "a.py").write_text("TODO\n", encoding="utf-8")
    find_payload = asyncio.run(server.tools["find_files"]("*.py", base=str(tmp_path)))
    grep_payload = asyncio.run(
        server.tools["grep_content"]("TODO", paths=["*.py"], base=str(tmp_path))
    )
    count_payload = asyncio.run(server.tools["count_lines"]("*.py", base=str(tmp_path)))
    describe_payload = asyncio.run(server.tools["describe_subcommand"]("find"))

    assert find_payload["results"][0]["relative_path"] == "a.py"
    assert grep_payload["results"][0]["content"] == "TODO"
    assert count_payload["files"] == 1
    assert describe_payload["name"] == "find"


def test_find_duplicate_files_tool(tmp_path):
    """The duplicate MCP tool returns DuplicateSearchResult payloads."""
    (tmp_path / "a.bin").write_bytes(b"same")
    (tmp_path / "b.bin").write_bytes(b"same")
    server = mcp_module.create_server(FakeServer)

    payload = asyncio.run(server.tools["find_duplicate_files"]("*.bin", base=str(tmp_path)))

    assert len(payload["results"]) == 1


def test_load_server_factory_missing_extra(monkeypatch):
    """If `mcp` isn't installed, the factory raises with a clear message."""
    # Make every relevant `mcp.*` module appear absent. Using sys.modules
    # lets us simulate the un-installed state without actually uninstalling
    # the optional dep from the test venv.
    for name in list(sys.modules):
        if name == "mcp" or name.startswith("mcp."):
            monkeypatch.delitem(sys.modules, name)
    import builtins

    real_import = builtins.__import__

    def _block_mcp(name, *args, **kwargs):
        if name.startswith("mcp"):
            raise ModuleNotFoundError(f"No module named {name!r}")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _block_mcp)

    import pytest

    with pytest.raises(RuntimeError, match="requires the optional mcp extra"):
        mcp_module._load_server_factory()


def test_load_server_factory_success(monkeypatch):
    """The lazy MCP import accepts a module exposing FastMCP."""
    fake_mcp = types.ModuleType("mcp")
    fake_server_pkg = types.ModuleType("mcp.server")
    fake_fastmcp_module = types.ModuleType("mcp.server.fastmcp")
    fake_fastmcp_module.FastMCP = FakeServer
    monkeypatch.setitem(sys.modules, "mcp", fake_mcp)
    monkeypatch.setitem(sys.modules, "mcp.server", fake_server_pkg)
    monkeypatch.setitem(sys.modules, "mcp.server.fastmcp", fake_fastmcp_module)

    factory = mcp_module._load_server_factory()

    assert factory("rglob").name == "rglob"


def test_main_runs_stdio(monkeypatch):
    """main() runs the server's stdio coroutine."""
    fake = FakeServer("rglob")
    monkeypatch.setattr(mcp_module, "create_server", lambda: fake)

    mcp_module.main()

    assert fake.ran is True


def test_cli_mcp_without_extra_is_json_error(monkeypatch):
    """Without the optional SDK, `rglob mcp` fails as a stable JSON envelope."""

    def boom() -> None:
        raise RuntimeError("rglob mcp requires the optional mcp extra")

    monkeypatch.setattr(mcp_module, "main", boom)
    result = runner.invoke(app, ["mcp"])
    assert result.exit_code == 2
    assert "UNSUPPORTED_PLATFORM" in result.stdout
