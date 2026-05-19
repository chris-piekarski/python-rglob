# ADR-0007 · Behave kept as parallel BDD suite

**Status**: Accepted · **Date**: 2026-05-14

## Context

The pre-2.0 test suite is entirely Behave (BDD). The roadmap introduces
pytest as the primary suite in Phase 2. There were three plausible paths:

1. **Delete Behave** — clean cut, single suite, lower maintenance.
2. **Keep Behave, deprecate it** — accept it as a transitional cost.
3. **Keep Behave as a first-class parallel suite** — both suites run on
   CI, both gate merges.

## Decision

**Keep Behave** as a parallel BDD suite (option 3). The scenarios in
`features/rglob.feature` read like fun documentation (`Given I create 1100
subdirectories…`) and that's worth preserving.

To keep maintenance honest, Behave step definitions share helpers with
pytest:

- `tests/conftest.py::TreeBuilder` is the canonical tree-building helper.
- `features/steps/steps.py` step bodies call into the same builder so any
  new assertion shows up exactly once.

## Consequences

- Every new feature lands a pytest case **and** a Behave scenario if the
  feature has user-visible behaviour. Tests-only features (e.g. internal
  helpers) skip Behave.
- We **accept the drift risk**: in practice the Behave scenarios will rot
  first if they diverge from the helpers. We treat that as a maintenance
  bill rather than a blocker.
- The Behave job in CI runs alongside the pytest matrix and gates the same
  way.
