# MCP Setup

Install the optional extra:

```bash
pip install "rglob[mcp]"
```

Then configure an MCP host to run:

```bash
rglob mcp
```

The stdio server exposes these tools:

- `find_files(pattern, **filters)`
- `grep_content(pattern, paths, **opts)`
- `count_lines(pattern, **filters)`
- `find_duplicate_files(pattern, **filters)`
- `describe_subcommand(name)`

All tool results use the same JSON-safe shapes as `rglob.agent` and the
structured CLI output.

