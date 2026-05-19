# Agent Integration

`rglob` 2.0 exposes three machine-friendly surfaces for coding agents:

- bounded JSON / JSONL CLI output
- the typed `rglob.agent` Python API
- an optional stdio MCP server via `rglob[mcp]`

The stable agent contract is versioned separately from the package:

```bash
rglob agent-version
```

Use `rglob describe <subcommand>`, `rglob schema <subcommand>`, and
`rglob schema --all` for machine-readable discovery instead of scraping
`--help`.

## Stability

The SemVer-locked surface is documented in
[ADR-0009](../decisions/0009-agent-api-contract.md). The read-only safety
model is documented in [ADR-0010](../decisions/0010-agent-safety-model.md).
