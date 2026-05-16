# Safety

The agent surfaces are read-only. They never edit, execute, chmod, or
delete files.

Agent and MCP defaults favor bounded output and path containment:

- `strict_base=True`
- `follow_symlinks=False`
- `include_errors=True`
- result limits are available on structured outputs
- binary grep is skipped unless `--text` / `text=True` is requested

Structured results report truncation with `truncated` and
`truncated_reason`. Operational failures are returned as `ErrorInfo`
records or as the stable error envelope for command-level failures.

