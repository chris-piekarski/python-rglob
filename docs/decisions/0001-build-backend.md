# ADR-0001 · Build backend: `hatchling`

**Status**: Accepted · **Date**: 2026-05-14

## Context

The legacy `setup.py` is gone. PEP 621 metadata lives in `pyproject.toml`,
and we need a PEP 517 build backend that:

- single-sources `__version__` from `src/rglob/__init__.py`
- supports a `src/` layout out of the box
- has zero plugin friction for typical packaging tasks (`sdist`/`wheel`)
- is well maintained in 2026

## Decision

Use **`hatchling`** as the build backend, configured via
`[tool.hatch.build.*]` in `pyproject.toml`. Run builds with the `hatch` CLI
(`make build` → `hatch build`).

## Consequences

- `[tool.hatch.version] path = "src/rglob/__init__.py"` reads the version
  string at build time — no manual sync between source and metadata.
- `[tool.hatch.build.targets.wheel] packages = ["src/rglob"]` makes the
  `src/` layout work without extra glue.
- We get a low-noise, fast build with first-class PyPI OIDC compatibility.
- Alternatives considered: `setuptools` (more legacy baggage), `flit` (less
  flexible for our metadata footprint), `pdm-backend` (good but
  PDM-flavoured).
