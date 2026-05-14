# CLI Reference

`rglob` ships a Typer-powered CLI with three subcommands (`find`, `lcount`,
`tsize`), Rich-styled output, JSON / JSONL / NUL-separated output formats,
and shell completion.

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
| `--json`                             | Emit a single JSON array of path strings. |
| `--jsonl`                            | One `{"path": ..., "size": ...}` per line. |
| `-0, --null`                         | Separate paths with NUL bytes (for `xargs -0`). |
| `--format TEMPLATE`                  | Render each match through a mini-template. Available fields: `path`, `rel`, `name`, `size`, `size_kb`, `size_mb`. |

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

## Exit codes

| Code | Meaning |
| ---: | ------- |
| `0`  | Success. |
| `2`  | Invalid argument (e.g. unknown unit on `tsize`). |
| `1`  | Unhandled error. |
