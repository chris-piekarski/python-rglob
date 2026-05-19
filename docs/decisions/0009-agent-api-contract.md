# ADR-0009 - Agent API contract

**Status**: Accepted - **Date**: 2026-05-15

## Context

The 2.0 release adds agent-facing search surfaces:

- bounded JSON and JSONL CLI output
- a typed `rglob.agent` Python namespace
- a stdio MCP server
- machine-readable `describe`, `schema`, `capabilities`, and
  `agent-version` CLI endpoints

Human-oriented help text is not enough for autonomous tools. Agents need
stable field names, error envelopes, truncation metadata, and schemas that
can be inspected without scraping Rich-rendered output.

## Decision

`rglob` will expose a focused agent contract with its own semantic version:
`__agent_api_version__ = "1.0"`. The package version stays `2.0.0`, but
the agent contract can move independently in future releases.

Only these surfaces are covered by the agent compatibility promise:

- public dataclasses and function signatures exported from `rglob.agent`
- JSON Schema documents emitted by `rglob.agent.schema_for`,
  `rglob.agent.all_schemas`, and `rglob schema`
- structured CLI subcommands and flags used by agents
- structured CLI JSON and JSONL output shapes
- MCP tool names, input shapes, and output shapes
- error codes, error envelopes, truncation metadata, and capability reports

Private helper modules such as `_filters`, `_dupes`, and walker internals
remain implementation details.

Agent results use concrete frozen, slotted dataclasses rather than a generic
wrapper. The v1 contract includes `FileSearchResult`,
`LineSearchResult`, and `DuplicateSearchResult`, each with explicit
metadata fields:

- `results`
- `truncated`
- `total_files_searched`
- `bytes_read`
- `errors`
- `truncated_reason`

`Path`, `datetime`, and `StrEnum` are allowed in Python dataclasses for
ergonomic typed use. Wire output is normalized through a single
`to_json_dict()` helper:

- `Path` serializes to string.
- Absolute `path` fields use the host filesystem spelling.
- `relative_path` is POSIX-style relative to the requested base and never
  starts with `./`.
- `datetime` serializes as ISO 8601 UTC with a `Z` suffix.
- `ErrorCode` serializes as its string value.

Structured failures use one envelope:

```json
{"ok": false, "error": {"code": "REGEX", "message": "...", "path": null}}
```

Operational issues discovered during a search are represented as
`ErrorInfo` records when the agent API or MCP server is configured to
collect errors. The legacy public `find(on_error=...)` warning and raising
behavior is preserved for compatibility.

`ErrorCode` is a closed `StrEnum` for v1.x:

- `PERM`
- `UNREADABLE`
- `BINARY`
- `TIMEOUT`
- `REGEX`
- `BAD_PREDICATE`
- `UNSUPPORTED_PLATFORM`

JSON Schema documents use Draft 2020-12, include an `$id`, include a
`version` field, and are generated directly from the dataclasses in
`src/rglob/agent/_models.py`. `rglob.agent.schema_for(<schema-name>)`
returns one public schema, `rglob.agent.all_schemas()` returns the full
mapping, `rglob schema <subcommand>` returns a command's input/output
schemas, and `rglob schema --all` emits every public schema for callers
that want a file artifact.

Compatibility rules:

- Adding a dataclass field, CLI flag, MCP tool field, or error code is a
  minor bump of `__agent_api_version__`.
- Removing or renaming any locked field, flag, function, or tool is a major
  bump.
- Patch releases may clarify descriptions and fix bugs without changing the
  emitted schema shape.
- While `__agent_api_version__` starts with `"1."`, `rglob` will emit
  schemas that validate against the v1.x contract.

## Consequences

Agents can pin to `rglob.agent` and the schema version instead of inferring
behavior from human help text. The cost is that every future change to the
agent-facing surface must be reviewed as a compatibility decision.

Tests must compare the Python API, CLI JSON/JSONL, MCP outputs, and
generated schemas against the same golden fixture records. `_models.py` is
the single source of truth, so committed schema artifacts cannot drift from
the contract.
