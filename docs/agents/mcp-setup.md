# MCP Setup

Install the optional extra:

```bash
pip install "rglob[mcp]"
```

Then configure an MCP host to run:

```bash
rglob mcp
```

The stdio server exposes these tools, all read-only with bounded
defaults (`limit=5000`, `follow_symlinks=False`, `strict_base=True`):

- `find_files(pattern, base, ...walk filters)`
- `grep_content(pattern, paths, base, ...grep options, ...walk filters)`
- `count_lines(pattern, base, no_empty, no_comments, encoding, ...walk filters)`
- `find_duplicate_files(pattern, base, ...walk filters)`
- `describe_subcommand(name)`

Each parameter is declared explicitly on the tool signature — FastMCP
introspects the signature to publish a JSON Schema, so agents discover
every field by name (no opaque `**kwargs`). The shared *walk filters*
are `exclude`, `max_depth`, `hidden`, `follow_symlinks`,
`case_sensitive`, `respect_gitignore`, `limit`, `max_bytes`,
`max_file_size`. Tool results use the same JSON-safe shapes as
`rglob.agent` and the structured CLI output; run `rglob schema --all`
for the matching agent-API contract.

