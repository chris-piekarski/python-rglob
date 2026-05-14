# ADR-0005 · Single `2.0.0` release strategy

**Status**: Accepted · **Date**: 2026-05-14

## Context

The roadmap spans six phases. We considered cutting an intermediate release
(e.g. `2.0.0b1`) after each phase. That would:

- ship value faster to early adopters
- catch packaging issues earlier on real installs
- give us tag-driven smoke-test coverage of `release.yml`

…but it would also:

- create six migration notes for users to chase
- pin us into supporting half-finished APIs (the Phase 3 walker before
  Phase 4 wires the CLI to it, for example)
- conflict with the "labor of love" pacing — these are weekend phases

## Decision

**Ship 2.0.0 once, after all six phases have landed.** Source version
stays at PEP 440 `"2.0.0.dev0"` throughout development so editable installs
are visibly WIP. `release.yml` is wired in Phase 2 but only fires on
`v*` tag push.

## Consequences

- Phase 2's release-workflow verification is a **dry-run against
  TestPyPI** rather than a real publish.
- One migration document, one CHANGELOG section, one PyPI version bump.
- If we change our mind mid-flight, we can always cut a `2.0.0a1` from a
  partially-landed branch — no design lock-in here, just a default.
