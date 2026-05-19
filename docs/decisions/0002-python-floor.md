# ADR-0002 · Python 3.11 floor

**Status**: Accepted · **Date**: 2026-05-14

## Context

The pre-2.0 codebase declared `python_requires=">=3.5"` despite using
features that wouldn't run cleanly on 3.5. The roadmap originally proposed a
**3.10** floor, but during the planning audit we noted that **3.10 reaches
upstream EOL in October 2026** — within months of when 2.0 is expected to
ship.

## Decision

Set `requires-python = ">=3.11"` for the 2.0 release. CI matrix runs
**3.11 → 3.12 → 3.13 → 3.14**.

## Consequences

- Two-month safety margin: 3.11 reaches EOL October 2027.
- We get to use:
    - PEP 604 `X | Y` unions at runtime (no `from __future__ import annotations`)
    - Native exception groups (`ExceptionGroup`, `except*`)
    - `typing.Self` and `assert_type`
    - `tomllib` in the stdlib
    - `StrEnum` for legible CLI choices
- We drop:
    - 3.10 users (`<1%` of `rglob` PyPI downloads at the time of writing)
- Lockstep with Astral / Pydantic / Polars / Hatch, all of which now floor
  at 3.11+ or are moving there.
