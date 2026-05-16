# ADR-0010 - Agent safety model

**Status**: Accepted - **Date**: 2026-05-15

## Context

Coding agents can call tools repeatedly, pass broad paths, and consume large
machine-readable outputs. `rglob` remains read-only, but search still has
safety risks:

- walking outside the intended base through symlinks
- exposing file contents through grep
- dumping unbounded results over stdout or stdio
- hanging on large trees or slow filesystem calls
- failing ambiguously on permissions, binary files, bad predicates, or
  unsupported platform-specific filters

The existing public walker is human-friendly and backward-compatible. The
agent and MCP surfaces need stricter defaults.

## Decision

The agent surfaces are read-only. They list files, read file metadata, read
file contents for grep/count operations, and hash file contents for
duplicate detection. They never edit, delete, execute, or chmod files.

Agent and MCP defaults are conservative:

- `strict_base=True`
- `follow_symlinks=False`
- `include_errors=True`
- bounded `limit`
- bounded `max_bytes`
- bounded `max_file_size`
- cooperative `timeout_seconds`
- `.gitignore` respected only when requested or documented as an agent
  default for the specific surface

CLI path streaming can remain unbounded for human workflows. Structured
CLI output must always include truncation metadata when it uses the agent
record model.

Path containment:

- `strict_base=True` means every emitted path must remain under the
  requested base after normalization.
- Symlink traversal is opt-in. When enabled under strict mode, symlink
  targets outside the base are reported as errors instead of being emitted.
- `.gitignore` discovery is base-rooted and never walks upward.

Content disclosure:

- Grep and count read file contents by design.
- Binary files are skipped by default for grep and reported with `BINARY`
  when errors are included.
- `--text` / `text=True` is the explicit opt-in for treating binary files
  as text.
- Decoding defaults to UTF-8 with replacement unless the caller supplies
  another encoding.

Output exhaustion:

- `limit` caps result records.
- `max_bytes` caps bytes read or emitted, depending on the operation.
- `max_file_size` skips individual files that are too large for the
  requested operation.
- Truncated results set `truncated=True` and provide
  `truncated_reason`.

Timeouts are cooperative only. The walker checks `time.monotonic()` during
directory iteration and at yielded matches. Grep and duplicate detection
check between files and read chunks. No signals or worker-thread
cancellation are used. A single slow filesystem call may run past the
deadline.

Errors are machine-readable. User mistakes and operational failures use
`ErrorInfo` records or the stable error envelope from ADR-0009 rather than
only colored stderr.

## Consequences

Agent integrations get predictable failure modes and bounded output by
default. Existing human-facing APIs keep their compatibility behavior,
which means the agent implementation must adapt the walker instead of
breaking `find(on_error=...)`.

Tests must cover truncation, timeouts where practical, unreadable paths,
binary grep behavior, bad predicates, and strict-base symlink escapes.
