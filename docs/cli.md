# CLI Reference

`rglob` ships a Typer-powered CLI with recursive search commands,
Rich-styled human output, structured JSON / JSONL / NUL-separated output
formats, and shell completion. Agent-oriented introspection endpoints always
emit plain JSON to stdout.

## Auto-generated command tree

::: mkdocs-typer2
    :module: rglob.cli
    :name: app

## Subcommand quick reference

### `rglob find`

Print paths under `--base` (default: CWD) matching one or more glob
patterns. Multiple positionals are OR'd. Filter and output options:

| Flag                                 | Meaning |
| ------------------------------------ | ------- |
| `-E, --exclude PATTERN`              | Glob(s) to exclude *and* prune from descent. Repeatable. |
| `-d, --max-depth N`                  | Maximum recursion depth (0 = base only). |
| `-H, --hidden`                       | Include dotfiles and dot-directories. |
| `-L, --follow`                       | Follow symlinks (cycles are auto-detected). |
| `-s/-i, --case-sensitive/-insensitive` | Force case sensitivity (default: follow host OS). |
| `--json`                             | Emit a `FileSearchResult` object with `results`, truncation metadata, and errors. |
| `--jsonl`                            | Emit one compact `FileSearchResult` object line. |
| `--limit N`                          | Maximum structured records to emit. |
| `--max-bytes SIZE`                   | Maximum structured output bytes. |
| `--max-file-size SIZE`               | Skip files larger than this. |
| `--include-errors/--no-include-errors` | Include per-record errors in structured output. |
| `-0, --null`                         | Separate paths with NUL bytes (for `xargs -0`). |
| `--format TEMPLATE`                  | Render each match through a mini-template. Available fields: `path`, `rel`, `name`, `size`, `size_kb`, `size_mb`. |

### `rglob grep`

```text
rglob grep <pattern> [files-or-globs...] [--base DIR] [--json|--jsonl]
```

Searches matching files for a regex by default, or a literal with
`--fixed-string/-F`. Useful flags:

| Flag | Meaning |
| ---- | ------- |
| `-i, --ignore-case` | Match content case-insensitively. |
| `-C, --context N` | Include N lines before and after each match. |
| `-B, --before N` / `-A, --after N` | Include asymmetric context. |
| `-m, --max-count N` | Stop after N matches. |
| `-w, --word` | Match whole words. |
| `-v, --invert` | Return non-matching lines. |
| `--encoding TEXT` | Decode files with this encoding. |
| `-a, --text` | Search binary files as text. |
| `--json` / `--jsonl` | Emit a `LineSearchResult`. |

### `rglob count`

```text
rglob count <pattern>... [--base DIR] [--no-empty] [--no-comments] [--json|--jsonl]
```

Reports files, lines, and bytes in one structured view. `--json` and
`--jsonl` emit the `Stats` schema used by the Python API and MCP tools.

### `rglob lcount`

```text
rglob lcount <pattern> [--base DIR] [--no-empty] [--no-comments]
```

`--no-empty` skips blank lines; `--no-comments` skips `#`-prefixed lines.

### `rglob tsize`

```text
rglob tsize <pattern> [--base DIR] [--unit {kb,mb,gb,tb}]
```

Defaults to `--unit mb`. Output is `Total size: X.XX UNIT`.

### `rglob mcp`

```text
pip install "rglob[mcp]"
rglob mcp
```

Starts the stdio MCP server. The server exposes `find_files`,
`grep_content`, `count_lines`, `find_duplicate_files`, and
`describe_subcommand`.

## Quoting

!!! warning "Quote your patterns"
    Quote glob patterns so your shell doesn't pre-expand them. Use
    `rglob find "*.py"`, not `rglob find *.py`. The CLI emits a warning to
    stderr if it sees multiple positional arguments that look pre-expanded
    (no glob metacharacters).

## Shell completion

```bash
rglob --install-completion bash      # or zsh / fish / powershell
```

Then restart your shell. `<TAB>` completes subcommands, flags, and option
values.

## Agent introspection

These commands are machine endpoints. They do not use Rich coloring and do
not require a TTY:

```bash
rglob describe find
rglob schema find
rglob schema --all
rglob capabilities --json
rglob agent-version
```

- `describe <subcommand>` returns arguments, options, default limits, and
  input/output schemas.
- `schema <subcommand>` returns only the input and output JSON Schema Draft
  2020-12 documents.
- `schema --all` returns every public JSON Schema document keyed by stable
  schema stem.
- `capabilities --json` reports the agent API version, schema version,
  installed extras, predicate support, and MCP availability.
- `agent-version` emits the current agent API version as a JSON string.

## Exit codes

| Code | Meaning |
| ---: | ------- |
| `0`  | Success. |
| `2`  | Invalid argument (e.g. unknown unit on `tsize`). |
| `1`  | Unhandled error. |
