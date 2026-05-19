# ADR-0004 · Typer + Rich for the CLI

**Status**: Accepted · **Date**: 2026-05-14

## Context

The pre-2.0 CLI uses stdlib `argparse`. We want:

- Click-quality UX (subcommands, completion, friendly help) without raw
  Click verbosity
- type-driven argument parsing (so the CLI surface tracks the typed API)
- pleasant terminal output (color, progress, tables)
- shell-completion for bash / zsh / fish / powershell out of the box

## Decision

Migrate to **Typer** (built on Click) with **Rich** for output formatting.

- Typer for command/option declaration — type hints drive argument shape.
- Rich for tables (`stats`, `top`, `dupes`), trees (`tree`), and the
  progress bar on long walks.

## Consequences

- Two new runtime dependencies. Both are widely deployed and stable.
- Shell completion is a one-liner per shell:
  `rglob --install-completion {bash,zsh,fish,powershell}`.
- Docs page (`docs/cli.md`) uses **`mkdocs-typer2`** — the modern,
  actively-maintained Typer plugin that renders the command tree directly
  from the Typer app object. The older `mkdocs-click` bridge required a
  manual `typer.main.get_command()` step and is no longer needed.
- We respect `NO_COLOR` and TTY detection; the snapshot tests run with
  color disabled to keep diffs stable.
