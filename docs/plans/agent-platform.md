# `python-rglob` 2.0 — Agent Platform Additions

## Context

This plan **extends the in-flight 2.0 PR ([#6](https://github.com/chris-piekarski/python-rglob/pull/6))**;
it does not gate a new release. The goal is to position `rglob` as the
**default recursive-search dependency for coding agents** (Claude Code,
Cursor, Aider, Gemini CLI, Codex CLI, generic MCP clients) for
**filename globbing**, **content grep**, and **`find(1)`-style
predicates** — exposed through a stability-promised, agent-friendly
surface.

The audience widens from "human writing scripts" to "autonomous agent
shelling out, importing, or talking MCP". Every phase below serves that
audience and ships as **additional commits on `release/2.0`**.

**Decisions locked in**:

- **Version**: stays at `2.0.0`. Single-release strategy
  ([ADR-0005](../decisions/0005-single-release.md)) still applies — we
  ship one PyPI publish covering everything from the modernization
  roadmap *and* this plan. The `CHANGELOG.md` `[2.0.0]` section already
  exists on `release/2.0`; it accumulates the agent additions and its
  date is refreshed at tag time if needed.
- **Scope**: glob + grep + find-style predicates. Pure Python; no
  vendored ripgrep / GNU find. Goal is a credible agent-default for the
  *common* 90% of search tasks, with bounded outputs and predictable
  failure modes, not a ripgrep replacement at the perf frontier.
- **Integration**: three first-class surfaces — (a) stable bounded JSON CLI,
  (b) typed `rglob.agent` Python API, (c) `rglob mcp` stdio MCP server.
  No HTTP/OpenAPI in 2.0 (revisit if demand emerges).
- **Stability promise**: a focused `rglob.agent` namespace — *only* its
  dataclasses, function signatures, JSON schemas, MCP tool list, and
  CLI subcommand+flag surface are SemVer-locked. Error envelopes,
  truncation metadata, resource-limit semantics, and capability reports
  are part of that contract. Everything else (`_filters`, `_dupes`,
  walker internals) stays free to evolve.
- **Discovery**: `AGENTS.md` grows a "consumer-facing" half (today it
  only speaks to *contributors*); `docs/examples/` ships runnable
  recipes; `rglob describe <subcommand>` and `rglob schema <subcommand>`
  give agents a machine-readable manifest without scraping `--help`;
  `rglob schema --all` emits the full schema set for artifact-oriented
  consumers; `rglob capabilities --json` reports
  installed extras, platform-supported predicates, MCP availability, and
  schema/API versions.

**Out of scope for 2.0** (revisit later):

- OpenAPI / JSON-RPC over HTTP
- `llms.txt` manifest (re-evaluate when the spec is more settled)
- Replacing ripgrep on huge corpora (we don't compete on raw GBs/sec)
- Symbolic search (LSP-style "find references")
- Editing operations (we stay read-only)
- A full Git-compatible `.gitignore` engine beyond the practical
  `pathspec`-based behaviour already in 2.0

**Prerequisite**: the 2.0 PR's lone outstanding CI failure
(`test_find_help_lists_filter_flags`, an ANSI-stripping flake on
GitHub Actions' `FORCE_COLOR=1` env) needs a 5-line fix on
`release/2.0` before agent-platform commits start landing. The patch is
already in the working tree and should be committed before this plan's
first implementation commit.

---

## Implementation checklist

This section is the durable handoff log for agent-platform work. Keep it
updated as changes land so another coding agent can restart from the
current state without reconstructing context from git history.

**Status legend**: `[ ]` not started, `[~]` in progress, `[x]` done,
`[!]` blocked / needs attention.

### Current status

- `[~]` Overall phase: Agent platform implementation is locally green in
  the working tree, but not committed yet.
- `[!]` Repository state: the agent-platform implementation and schema
  cleanup are currently unstaged/untracked working-tree changes on
  `release/2.0`; stage/commit/push them before treating the PR as updated.
- `[x]` Prerequisite help flake patch exists in the working tree and
  passes `.venv/bin/pytest -q tests/test_cli.py::test_find_help_lists_filter_flags`.
- `[x]` Phase 0a ADRs 0009/0010 written and linked from docs navigation.
- `[x]` Phase 0b contract dataclasses and `tests/fixtures/agent-tree/`
  added to the working tree.
- `[x]` Phase 0c runtime schema generation wired from `_models.py`; no
  committed schema cache or drift tooling remains.
- `[x]` Phase 0d CLI introspection commands and structured JSON output
  implemented.
- `[x]` Docs, changelog, and snapshots updated for Phase 0.
- `[x]` Phase 1 grep engine, `grep` CLI, `count` CLI, structured JSON,
  and additional find predicates.
- `[x]` Phase 2 public `rglob.agent` API.
- `[x]` Phase 3 `rglob mcp` stdio MCP server and optional extra.
- `[x]` Phase 4 AGENTS.md consumer half, `docs/agents/*`, and README
  top-fold rewrite.
- `[~]` Phase 4 `docs/examples/` content exists, but the runnable examples
  harness `tests/examples_harness.py` is not implemented yet.
- `[~]` Phase 5 packaging/docs polish is complete for the implemented
  surface; final release/tag work remains pending.
- `[x]` Review follow-up verification: import cycle, strict base
  containment, byte-limit prechecks, and timeouts fixed; final build gate
  passed.
- `[x]` Final verification run: `make lint`, `make test`, `make build`.
- `[ ]` Add `tests/examples_harness.py` and wire runnable docs examples
  into CI / `make test`.
- `[ ]` Stage and commit the current working-tree changes with a
  Conventional Commit subject, then push/update the pull request.
- `[ ]` Tag `v2.0.0` after PR merge/release approval so `release.yml`
  publishes to PyPI and creates the GitHub release.

### Work log

- 2026-05-15: Began implementation pass. Added this checklist so progress
  survives context compaction or agent handoff.
- 2026-05-15: Completed Phase 0a. Added ADR-0009 (agent API contract),
  ADR-0010 (agent safety model), decisions index entries, and MkDocs nav.
- 2026-05-15: Completed Phase 0b/0c in the working tree. Added
  `src/rglob/agent/_models.py`, the golden fixture tree, runtime schema
  generation in `src/rglob/agent/_introspection.py`, and schema tests.
- 2026-05-15: Completed Phase 0d in the working tree. Added `describe`,
  `schema`, `capabilities`, and `agent-version`; changed `find --json` and
  `find --jsonl` to emit `FileSearchResult`; updated CLI docs and changelog.
  `make test` passes with 100% coverage and Behave green.
- 2026-05-15: Completed Phase 1 in the working tree. Added `grep` and
  `count` helpers/CLI commands, structured `LineSearchResult`/`Stats` JSON,
  `perm`/`uid`/`gid`/`newer_than_file` filters, runtime-generated schemas,
  and tests. `make test` passes with 100% coverage and Behave green.
- 2026-05-15: Completed Phase 2 in the working tree. Added public
  `rglob.agent` exports and non-raising `search`, `search_all`, `grep`,
  `grep_all`, `count`, and `find_duplicates` functions with tests.
- 2026-05-15: Completed Phase 3 in the working tree. Added `rglob[mcp]`,
  `src/rglob/agent/mcp.py`, `rglob mcp`, and fake-SDK tests covering the
  stdio server registration and JSON result shapes. `make test` passes with
  100% coverage and Behave green.
- 2026-05-15: Completed documentation and packaging polish for the
  implemented working-tree surface. Updated README, AGENTS consumer
  guidance, CLI docs, architecture, changelog, `docs/agents/`, and
  `docs/examples/`. `tests/examples_harness.py` remains pending.
- 2026-05-15: Addressed review findings in the working tree. Removed the
  fresh-process CLI import cycle, enforced strict base containment for
  symlink escapes, moved `max_bytes` checks ahead of file body reads, and
  wired `timeout_seconds` through search, grep, count, and duplicate
  helpers. Added regression tests for each issue. Verification passed:
  `make lint`, `make test`, `make build`, and `make docs-build`.
- 2026-05-15: Cleaned up schema generation after review. Removed committed
  `_schemas/*.json`, removed `scripts/generate_agent_schemas.py`, removed
  schema drift checks from Makefile/CI, generated schemas on demand from
  `_models.py`, added `rglob schema --all`, and verified `make lint`,
  `make test`, and `make build`.
- 2026-05-15: Updated this checklist to distinguish implemented
  working-tree changes from committed/PR state. Pending items are the
  docs examples harness, staging/committing/pushing the PR changes, and
  the eventual `v2.0.0` tag/release.

---

## Phase 0 — Contract, safety, and golden fixtures

Do this before expanding the surface. Agents need stable machine
contracts more than they need another flag, and the current CLI JSON
already has two shapes (`find --json` is a string array; `find --jsonl`
is object records). Lock the record model first so Phase 1 does not
ship unstable JSON by accident.

**Sub-phase order** (each chunk lands as its own conventional commit on
`release/2.0`):

- **0a** — Write ADRs 0009 (contract) and 0010 (safety). No code yet.
- **0b** — Land `src/rglob/agent/_models.py` and the
  `tests/fixtures/agent-tree/` golden fixture.
- **0c** — Generate JSON Schema Draft 2020-12 documents on demand from
  `src/rglob/agent/_models.py`.
- **0d** — Add the four Typer subcommands (`describe`, `schema`,
  `capabilities`, `agent-version`); update existing subcommands to
  produce the new structured JSON.

**Tasks**

- New ADRs:
  - `docs/decisions/0009-agent-api-contract.md` — SemVer rules for
    `rglob.agent`, CLI JSON, schemas, and MCP tools.
  - `docs/decisions/0010-agent-safety-model.md` — read-only threat
    model for agents and MCP: path containment, symlink escape,
    content disclosure, binary files, unreadable files, and output
    exhaustion.
- Define the shared contract models in `src/rglob/agent/_models.py`
  before implementing the public API: `FileMatch`, `LineMatch`, `Stats`,
  `Duplicate`, `ErrorInfo`, `ErrorCode`, `FileSearchResult`,
  `LineSearchResult`, `DuplicateSearchResult`, `CapabilityReport`,
  `WalkOptions`, `GrepOptions`, `CountOptions`. All are
  `@dataclass(frozen=True, slots=True)` (no Pydantic). We use **three
  concrete result classes** rather than a `Generic[T]` wrapper — frozen+
  slotted dataclasses with `Generic[T]` are awkward, and one schema per
  result type is exactly what agents want. Minimum viable field shapes
  (refined during ADR-0009 drafting):

  - `WalkOptions`: `patterns`, `base`, `exclude`, `max_depth`, `kinds`,
    `min_size`/`max_size`, `newer_than`/`older_than`, `limit`,
    `max_bytes`, `max_file_size`, `timeout_seconds`, `strict_base`,
    `follow_symlinks`, `respect_gitignore`, `include_errors`,
    `case_sensitive`, `sort`.
  - `FileMatch`: `path: Path`, `relative_path: str`,
    `size: int`, `mtime: datetime`, `kinds: list[Kind]`,
    `errors: list[ErrorInfo]`. `kinds` is plural because an executable
    file is both `"f"` and `"x"`, and a symlink can have its own tag.
  - `LineMatch`: `path: Path`, `line_number: int`, `content: str`,
    `before: list[str]`, `after: list[str]`, `encoding: str`.
  - `FileSearchResult` / `LineSearchResult` / `DuplicateSearchResult`:
    each carries `results: list[<concrete type>]`, `truncated: bool`,
    `total_files_searched: int`, `bytes_read: int`,
    `errors: list[ErrorInfo]`, `truncated_reason: str | None`. A common
    metadata mixin can DRY the shared fields, but the public types stay
    concrete.
  - `ErrorInfo`: `code: ErrorCode` (a `StrEnum` — see below),
    `message: str`, `path: Path | None`.
  - `ErrorCode`: a closed `StrEnum` for the v1.x agent API:
    `PERM`, `UNREADABLE`, `BINARY`, `TIMEOUT`, `REGEX`,
    `BAD_PREDICATE`, `UNSUPPORTED_PLATFORM`. ADR-0009 records that
    *adding* a code is a minor `__agent_api_version__` bump; renaming
    or removing one is a major bump.
  - `CapabilityReport`: locked shape:

    ```json
    {
      "agent_api_version": "1.0",
      "schema_version": "1.0",
      "package_version": "2.0.0",
      "extras": {"mcp": true, "gitignore": true, "ext": false},
      "predicates": {
        "perm": "supported",
        "uid": "POSIX-only",
        "gid": "POSIX-only",
        "newer_than": "supported",
        "respect_gitignore": "supported"
      },
      "mcp": {"available": true, "transport": "stdio"}
    }
    ```

- **Wire serialization is locked in ADR-0009**:
  - Python dataclasses may store `Path`, `datetime`, and `StrEnum`
    instances for ergonomic typed use.
  - JSON / JSONL / schema / MCP wire output serializes every `Path` as
    a string. `path` is an absolute normalized path using the host
    filesystem spelling; `relative_path` is POSIX-style relative to the
    requested `base` and never starts with `./`.
  - `datetime` fields serialize as ISO 8601 UTC strings with a `Z`
    suffix.
  - `ErrorCode` serializes as its string value.
  - A shared `to_json_dict()` helper in `src/rglob/agent/_models.py`
    handles this conversion for CLI JSON, schema examples, and MCP so
    the three surfaces cannot drift.

- Every option model includes resource controls: `limit`,
  `max_bytes`, `max_file_size`, `timeout_seconds`, `strict_base`,
  `follow_symlinks`, `respect_gitignore`, and `include_errors`.
  MCP defaults are conservative (`limit` set, `strict_base=True`,
  `follow_symlinks=False`); CLI streaming remains human-friendly, but
  structured `--json` / `--jsonl` always reports whether output was
  truncated.
  `include_errors=True` (the agent/MCP default) makes the walker collect
  `ErrorInfo` records instead of emitting `RuntimeWarning` or raising;
  the public `find(on_error=...)` API and its warning behaviour are
  unchanged for backward compatibility.
- **`timeout_seconds` semantics** — *cooperative only*. The walker
  checks `time.monotonic()` at every `scandir()` iteration and at every
  yielded match; on expiry it raises `TIMEOUT` via the error envelope
  (or `ErrorInfo` when `include_errors=True`) and returns whatever was
  collected so far in the `SearchResult`. Minimum value is 0.1s; a
  finer floor isn't useful for filesystem walks. We do **not** use
  signals (POSIX-only) or threads (cancellation is hard). Document the
  precision honestly: the walker can run a bit past the deadline if a
  single `scandir()` call is slow.
- Define the stable error envelope once:
  `{"ok": false, "error": {"code": "...", "message": "...", "path": ...}}`.
  User mistakes (bad regex, bad predicate, unsupported platform field)
  must be machine-readable, not only Rich-coloured stderr.
- Add a tiny golden fixture tree under `tests/fixtures/agent-tree/`
  (committed, < 50 files). All three surfaces (Python API, CLI `--json`/`--jsonl`,
  and MCP tools) must produce identical `SearchResult` / `FileMatch` /
  `LineMatch` records against it. Required structure:

  ```
  tests/fixtures/agent-tree/
    .gitignore
    src/
      main.py
      utils/
        helper.py
    docs/
      notes.txt
    binary.bin          # non-UTF-8 content
    unreadable/         # permission-denied case (mocked or chmod 000)
    duplicates/
      a.txt
      b.txt (byte-identical copy)
    hidden/
      .secret.py
  ```

  Tests exercise hidden entries, gitignore pruning, binary skipping,
  context capture, truncation, and error envelopes. The fixture must
  produce identical `FileSearchResult` / `LineSearchResult` /
  `DuplicateSearchResult`, `FileMatch`, and `LineMatch` records
  across the Python API, CLI JSON, and MCP surfaces.
- Add schema tooling without a runtime modelling dependency. **Decision**:
  keep `src/rglob/agent/_models.py` as the sole source of truth and
  generate JSON Schema Draft 2020-12 documents on demand in
  `src/rglob/agent/_introspection.py`. The generator is stdlib-only and
  powers `rglob.agent.schema_for()`, `rglob.agent.all_schemas()`,
  `rglob schema <subcommand>`, and `rglob schema --all`.
- **No schema cache** — generated JSON files are not committed or packaged.
  This removes the `make schemas` target, the `make build` drift check,
  and the CI schema-drift step because there is no second artifact to keep
  synchronized.
- **Generator contract** (for Phase 0c): schema generation imports the
  dataclasses from `rglob.agent._models`, emits one JSON Schema Draft
  2020-12 document per public type, includes stable `$id` and `version`
  fields, and remains deterministic.
- **Chosen introspection CLI surface** (locked for implementation):
  - `rglob describe <subcommand>` — full JSON manifest (arguments, types,
    defaults, input/output schemas, default limits, supported extras).
  - `rglob schema <subcommand>` — just the input + output JSON Schema
    objects.
  - `rglob schema --all` — every public JSON Schema object, keyed by stable
    schema stem.
  - `rglob capabilities --json` — reports `__agent_api_version__`, installed
    extras, platform-supported predicates, MCP availability, and schema
    versions.
  - `rglob agent-version` — prints the current `__agent_api_version__`.
  These are implemented as normal Typer subcommands (no global-option
  parsing hacks). All existing subcommands (`find`, `grep`, `count`,
  `lcount`, `tsize`, `stats`, `tree`, `top`, `dupes`) receive `describe`
  and `schema` support.
  **`describe` / `schema` / `capabilities` / `agent-version` always emit
  pure JSON to stdout regardless of TTY** — no Rich coloring, no
  `--json` flag needed, no banner. They're machine endpoints first.
  Tests assert generated schema shape and CLI emission across patches.
- **Snapshot regeneration**: changing `find --json` from a string array
  to a `FileSearchResult` object invalidates
  `tests/__snapshots__/test_cli.ambr::test_find_default_output` and
  related snapshots. Phase 0d regenerates them via
  `pytest --snapshot-update` and commits the diff alongside the schema
  flip. Reviewers should diff the snapshots against the new schema to
  confirm shape parity.

**Critical files**: `src/rglob/agent/_models.py` (new),
`src/rglob/agent/_introspection.py` (runtime schema generation),
`src/rglob/cli.py`,
`tests/fixtures/agent-tree/` (new), `tests/test_agent_contract.py` (new),
`tests/__snapshots__/test_cli.ambr` (regenerated for the new
`find --json` shape),
`docs/decisions/0009-agent-api-contract.md` (new),
`docs/decisions/0010-agent-safety-model.md` (new).

**Acceptance**: `rglob schema find | jq` validates as JSON Schema
Draft 2020-12; `rglob capabilities --json` reports schema/API versions
and installed extras; golden fixture snapshots prove Python API, CLI
JSON, and future MCP output use the same record shapes; invalid regexes,
unsupported predicates, unreadable paths, and truncated searches all
produce stable machine-readable errors or warnings.

---

## Phase 1 — Scope expansion (`grep` + `find` predicates)

Land the missing `find(1)` / `grep` capabilities so the CLI is genuinely
"all your search needs", not just "globbing with filters".

**Tasks**

- New module `src/rglob/_grep.py`: regex / fixed-string content matcher
  with `before`/`after`/`context` line capture. Iterates files yielded
  from `find()`. Uses `re` (stdlib) — no `regex` extra in 2.0; revisit
  if PCRE features are demanded. The matcher returns Phase 0
  `LineMatch` records, not ad hoc dicts.
- Grep defaults are agent-safe and explicit: UTF-8 with
  `errors="replace"`, binary files skipped by default, `--text/-a` to
  force binary-as-text, `--encoding` for override, `--max-file-size` and
  `--max-bytes` for output control, and stable regex-compile errors.
- New CLI subcommand `rglob grep <pattern> [files-or-globs...]` with
  flags: `--fixed-string/-F`, `--ignore-case/-i`, `--line-number/-n`,
  `--context/-C N`, `--before/-B N`, `--after/-A N`, `--max-count/-m N`,
  `--word/-w`, `--invert/-v`, `--encoding`, `--text/-a`, `--limit`,
  `--max-bytes`, `--max-file-size`. Honours all the existing `find`
  filter flags (`--exclude`, `--max-depth`, `--hidden`, `--type`,
  `--gitignore`, `--min-size`, `--newer-than`, etc.).
- New CLI subcommand `rglob count <pattern>` (split out from today's
  `lcount`/`tsize` so the verb is consistent: `count` reports files +
  lines + bytes in one structured view). `lcount`/`tsize` stay as
  aliases for backward-compatibility.
- Extend `find()` with the `find(1)`-style filters we don't have:
  `mtime`/`ctime`/`atime` ranges (already partially via `newer_than` /
  `older_than`), `perm`-mask matching, `uid`/`gid` matching (POSIX-only;
  reported as unsupported on Windows rather than silently no-oping),
  `newer_than_file=Path` shortcut (mirroring `find -newer FILE`).
  This work includes:
  - New predicate helpers in `src/rglob/_filters.py`.
  - Updates to `WalkOptions` and the core walker logic in
    `src/rglob/rglob.py` (must respect `strict_base` and feed into
    the error envelope / `ErrorInfo`).
  - Corresponding entries in `CapabilityReport.predicates`
    (`"supported"`, `"POSIX-only"`, or `"unsupported"`).
  - Cross-platform tests and clear documentation of Windows behaviour.
- Output formats unified: `--json` and `--jsonl` work on `find`, `grep`,
  `count`. The schemas are version-locked (Phase 0) and emitted via
  `rglob schema`; legacy `find --json` string arrays may remain under
  `--json-paths` only if compatibility demands it.
- Revisit `.gitignore` semantics before agents depend on it. Document
  the current `pathspec` approximation honestly, add tests for nested
  `.gitignore` files, and decide whether Phase 1 needs a small
  per-directory matcher improvement.

**Critical files**: `src/rglob/_grep.py` (new), `src/rglob/cli.py` (new
subcommands), `src/rglob/rglob.py` (predicate extensions),
`tests/test_grep.py` (new), `docs/cli/grep.md` (new).

**Acceptance**: `rglob grep TODO src/ --json | jq '.results[] | .path'`
returns the expected matches; `rglob count "*.py" --jsonl` round-trips
through `jq`; binary files, bad regexes, invalid encodings, context
groups, and truncation are covered; **aggregated coverage stays at
100%**; no hard new dependencies introduced; CHANGELOG `[2.0.0]`
accumulates the new surface under a "Phase 1 — Agent platform: scope
expansion" subsection.

---

## Phase 2 — Agent API contract (`rglob.agent`)

The implementation phase for the Phase 0 contract. Expose the
agent-facing Python namespace so 2.x is a contract agents can integrate
against without fear of churn.

**Tasks**

- New top-level module `src/rglob/agent/__init__.py` re-exporting *only*
  the agent-stable surface. Initial members:
  - Dataclasses (frozen, slotted; defined in Phase 0): `FileMatch`,
    `LineMatch`, `Stats`, `Duplicate`, `ErrorInfo`, `ErrorCode`,
    `FileSearchResult`, `LineSearchResult`, `DuplicateSearchResult`,
    `CapabilityReport`, `WalkOptions`, `GrepOptions`, `CountOptions`.
  - Functions (typed end-to-end):
    `search(opts: WalkOptions) -> Iterator[FileMatch]`,
    `search_all(opts: WalkOptions) -> FileSearchResult`,
    `grep(opts: GrepOptions) -> Iterator[LineMatch]`,
    `grep_all(opts: GrepOptions) -> LineSearchResult`,
    `count(opts: CountOptions) -> Stats`,
    `find_duplicates(opts: WalkOptions) -> DuplicateSearchResult`.
  - Error handling contract (locked for the agent API):
    The functions `search`, `search_all`, `grep`, `grep_all`, `count`,
    and `find_duplicates` are **non-raising** for operational errors
    (permission denied, timeout, unreadable files, binary files,
    bad regex, unsupported predicates, etc.). All such conditions
    are reported via the `errors: list[ErrorInfo]` field on the
    returned `FileSearchResult` / `LineSearchResult` / `DuplicateSearchResult`
    (or on `Stats` for `count`).
    Only genuine programmer errors may raise. This contract must be
    documented in the function docstrings and in
    `docs/agents/python-api.md`.
  - Constants: `__agent_api_version__ = "1.0"` (SemVer-locked
    independently of package `__version__` so the CLI/library can
    evolve faster than the agent contract).
- JSON schemas (JSON Schema Draft 2020-12) come from the Phase 0 runtime
  generator in `src/rglob/agent/_introspection.py`. No runtime dep on
  `pydantic`; schemas are emitted by `rglob.agent.schema_for()`,
  `rglob.agent.all_schemas()`, `rglob schema <subcommand>`, and
  `rglob schema --all`.
- New CLI introspection: `rglob describe <subcommand>` prints a JSON
  manifest of arguments + types + defaults; `rglob schema <subcommand>`
  prints the input + output JSON schemas; `rglob agent-version` prints
  `__agent_api_version__`. Tests assert these endpoints' outputs are
  byte-stable across patch releases.
- The agent functions share implementation with CLI JSON. They should
  not re-wrap private helpers in a second, drifting way; the golden
  fixture snapshots from Phase 0 are the guardrail.
- Stability rules documented in
  `docs/decisions/0009-agent-api-contract.md` (written in Phase 0a):
  - Adding a field to a dataclass / a flag to a CLI command = minor
    bump on `__agent_api_version__`.
  - Removing or renaming = major bump.
  - JSON schemas have an `$id` and `version` field; the contract is
    that **`rglob` will always emit valid v1.x schemas while
    `__agent_api_version__` starts with `"1."`**.
  - The `rglob.agent` import path is the only path agents should pin
    against. Importing from `rglob` directly continues to work but is
    "best-effort" stable.

**Critical files**: `src/rglob/agent/__init__.py` (new),
`tests/test_agent_api.py` (new). (`_models.py`, `_introspection.py`, the
ADRs, and `tests/test_agent_contract.py` are owned by Phase 0; this phase
only adds the public re-exports and consumer-facing tests.)

**Acceptance**: `from rglob.agent import search, FileMatch` works on a
fresh `pip install -e .`; `rglob schema find | jq '.input.required'`
returns the locked input schema; `mypy --strict` passes against the
agent module from a downstream consumer; one full round-trip
documented in `docs/agents/python-api.md`.

---

## Phase 3 — MCP server (`rglob mcp`)

Ship `rglob` as a stdio MCP server so Claude Code / Cursor / any
MCP-aware host can discover and call it natively, no shell-out
required.

**Tasks**

- New optional extra: `pip install rglob[mcp]` pulls in the official
  `mcp` Python SDK **plus** `pathspec` and `xxhash` so `--gitignore` and
  `dupes` work out of the box (`mcp = ["mcp>=1.0", "pathspec>=0.12",
  "xxhash>=3.4"]`).
- Before coding `src/rglob/agent/mcp.py`, verify the installed official
  `mcp` SDK API in a throwaway import smoke test and update the rough
  sketch below if the actual `Server`, `@tool`, or stdio runner names
  differ. The plan's contract is the tool list and JSON shape, not the
  exact SDK spelling in the sketch.
- New entry point: `rglob mcp` (subcommand) launches a stdio MCP server
  exposing tools:
  - `find_files(pattern, **filters) -> FileSearchResult`
  - `grep_content(pattern, paths, **opts) -> LineSearchResult`
  - `count_lines(pattern, **filters) -> Stats`
  - `find_duplicates(pattern, **filters) -> DuplicateSearchResult`
  - `describe_subcommand(name) -> dict` (mirrors `rglob describe <name>`)

  Rough implementation shape (in `src/rglob/agent/mcp.py`):

  ```python
  import asyncio
  from pathlib import Path

  from mcp.server import Server

  from rglob.agent import WalkOptions, search_all, to_json_dict

  mcp = Server("rglob")


  @mcp.tool()
  async def find_files(pattern: str, base: str = ".", **filters) -> dict:
      opts = WalkOptions(
          base=Path(base),
          patterns=[pattern],
          strict_base=True,            # conservative MCP defaults
          follow_symlinks=False,
          limit=5000,
          **filters,
      )
      return to_json_dict(search_all(opts))

  # similar @mcp.tool() for grep_content, count_lines, find_duplicates, etc.

  def main() -> None:
      asyncio.run(mcp.run_stdio_async())
  ```

  The Typer `mcp` command simply calls this `main()` after optional
  banner / version checks. All tools return the same concrete result
  shapes (`FileSearchResult` / `LineSearchResult` /
  `DuplicateSearchResult`) used by the CLI and Python API; the
  shared `to_json_dict()` helper gives the MCP layer JSON-safe `Path` /
  `datetime` / `StrEnum` serialisation without dragging in `pydantic`.

- MCP tools keep the Phase 0 conservative defaults: bounded result
  counts, bounded bytes, `strict_base=True`, `follow_symlinks=False`,
  and explicit truncation metadata. Agents can opt into larger searches,
  but the server must never dump an unbounded repository over stdio by
  default.
- Each tool's input/output schema is **derived from the same Phase 0/B
  dataclasses** — single source of truth, no schema drift between CLI
  JSON output and MCP tool I/O.
- Sample MCP client config snippets for Claude Code, Cursor, generic
  hosts in `docs/agents/mcp-setup.md` (new doc subdirectory).
- Integration test: spin up the server in a subprocess, send tool calls
  via the `mcp` SDK's stdio transport, verify the responses match the
  equivalent CLI JSON records from the golden fixture. Include truncated
  results and error-envelope cases.

**Critical files**: `src/rglob/agent/mcp.py` (new server module),
`tests/test_mcp.py` (new), `docs/agents/mcp-setup.md` (new),
`pyproject.toml` (the `mcp` extra).

**Acceptance**: `pip install -e .[mcp] && rglob mcp` starts and
responds to a `tools/list` request listing all five tools; Claude Code
with the documented config snippet successfully calls `find_files` and
gets typed, bounded results; coverage of `agent/mcp.py` stays at 100%
(mocked transport in tests); the MCP server is genuinely useful —
verified by asking Claude to find duplicate files and watching it
succeed without hand-holding or runaway output.

---

## Phase 4 — Documentation push (agent-first)

Today's docs assume a human reader. The agent platform additions make
agent-facing docs first-class.

**Tasks**

- Split `AGENTS.md` into two sections (or two files):
  1. **Contributor guidance** (today's content — kept).
  2. **Consumer guidance** (new) — for agents *using* `rglob` in their
     projects. Includes: how to install, how to discover via
     `rglob describe` / `rglob schema`, the JSON output schemas, MCP
     setup, the stability promise.
- New `docs/agents/` subdirectory:
  - `index.md` — the consumer landing page.
  - `mcp-setup.md` — copy-paste configs for Claude Code / Cursor /
    generic MCP hosts.
  - `python-api.md` — typed Python integration guide with
    `from rglob.agent import ...` examples.
  - `cli-recipes.md` — common subprocess patterns with `subprocess.run`
    and friends.
  - `stability.md` — the SemVer + agent-API contract spelled out.
  - `safety.md` — safe defaults, path containment, output limits,
    binary grep behaviour, and what file contents may be exposed.
- New `docs/examples/` directory — every recipe is *runnable* via the
  Phase 0-locked custom harness (`tests/examples_harness.py`); both
  bash and Python blocks execute in CI so examples cannot rot.
  Initial set:
  - "Find all Python files modified in last 7 days, as JSON."
  - "Grep TODOs across `src/`, excluding `.venv` and `dist`, with
    surrounding context."
  - "Count non-blank, non-comment lines per language."
  - "Detect duplicate files in `~/Downloads` larger than 1 MiB."
- Self-describing CLI: every subcommand wired to the `rglob describe` /
  `rglob schema` introspection from Phase 0/B; surfaced in
  `cli-recipes.md`.
- README rewrite of the top fold to lead with the agent-friendly
  positioning: ASCII banner → tagline → "**Designed to be the default
  recursive-search dependency for coding agents**" → install → MCP /
  Python / CLI examples in three columns / tabs.
- README accuracy pass: current 2.0 code returns `list[Path]` from
  `rglob()` / `rglob_()`; remove any remaining `list[str]` wording from
  README and docs before agent-facing examples land.
- `mkdocs.yml` nav update for `docs/agents/`, `docs/examples/`, and ADRs
  0009/0010. `docs/changelog.md` must still include the root
  `CHANGELOG.md` without duplicate stale release text.

**Critical files**: `AGENTS.md` (consumer half added), `docs/agents/*`
(new tree), `docs/examples/*` (new tree), `README.md` (top-fold
rewrite), `mkdocs.yml`, `docs/changelog.md`, `SECURITY.md`,
`tests/examples_harness.py` (runs the example recipes via the
Phase 0-locked custom harness).

**Acceptance**: a brand-new agent (test: spawn a fresh Claude Code
session, point it at the README, ask it to "use rglob to find
duplicate PNGs over 1MB in this dir" — measure success on first try);
every doc example runs green in CI; `rglob describe` / `rglob schema`
outputs are snapshot-tested via syrupy.

---

## Phase 5 — Final 2.0 polish before tag

The single PyPI release point for 2.0 still applies — these phases
land on the same PR and ship together.

**Tasks**

- `__version__` stays `"2.0.0"`. Confirm `Development Status` classifier
  remains `6 - Mature` (decided in the original Phase 6 of the
  modernization roadmap).
- `CHANGELOG.md` `[2.0.0]` section absorbs the agent-platform additions
  under clearly-titled "Phase 0 / 1 / 2 / 3 / 4 — Agent platform"
  subsections; release date is refreshed when the tag is pushed.
- Architecture diagram refresh: add Mermaid `classDiagram` of the
  `rglob.agent` namespace, sequence diagram of an MCP request
  lifecycle.
- Release packaging check: generated schemas work from an installed wheel
  without packaged `_schemas/*.json`; `py.typed` and any `docs/examples/`
  test data are present in the wheel/sdist where expected; `rglob schema
  find` works from an installed wheel, not only from an editable checkout.
- README final pass — the top-fold rewrite from Phase 4 becomes the
  canonical 2.0 README.
- Tag `v2.0.0` → `release.yml` workflow does PyPI OIDC publish + GH
  Release.

**Critical files**: `src/rglob/__init__.py` (version unchanged at
`2.0.0`), `src/rglob/agent/__init__.py`, `pyproject.toml`,
`CHANGELOG.md`, `docs/architecture.md`, `README.md`,
`.github/workflows/ci.yml`, `.github/workflows/release.yml`.

**Acceptance**: `pip install rglob==2.0.0 && rglob mcp --help` works;
`from rglob.agent import search, FileMatch` works in a fresh venv;
`rglob.agent.__agent_api_version__ == "1.0"`; aggregated coverage =
100%; the docs site renders the agent landing page; one full
Claude-Code-driven "find duplicate downloads" task succeeds on a fresh
install of 2.0 from PyPI.

---

## Critical files (cross-phase quick reference)

- `src/rglob/agent/` — new top-level subpackage holding the locked
  contract (Phase 0 defines the records/schemas; Phase 2 exposes the
  public Python API; Phase 3 extends it; Phase 4 documents it).
- `src/rglob/_grep.py` — new content-search engine (Phase 1).
- `src/rglob/cli.py` — gains `grep` / `count` / `mcp` subcommands and
  `describe` / `schema` introspection (Phases 1–3).
- `pyproject.toml` — new `mcp` extra (Phase 3).
- `tests/fixtures/agent-tree/` — shared golden fixture proving CLI,
  Python API, and MCP records stay aligned.
- `docs/agents/` and `docs/examples/` — new doc subtrees (Phase 4).
- `AGENTS.md` — consumer-facing half added (Phase 4).
- `README.md` — top fold rewritten to lead with the agent positioning
  (Phase 4, refined in Phase 5).
- `docs/decisions/0009-agent-api-contract.md` — the SemVer + stability
  ADR (Phase 0/2).
- `docs/decisions/0010-agent-safety-model.md` — path containment,
  content disclosure, and output-limit ADR (Phase 0).
- `mkdocs.yml`, `.github/workflows/ci.yml`, `.github/workflows/release.yml`
  — docs navigation, CI extras, and release packaging must reflect the
  new schema/MCP surface.

---

## Verification

End-to-end checks per phase. As with the modernization roadmap, no
PyPI publishes happen until the single 2.0 tag.

- **Phase 0**: `rglob schema find | jq` validates as JSON Schema
  Draft 2020-12; `rglob capabilities --json` reports extras and
  platform-supported predicates; golden fixture snapshots cover success,
  errors, and truncation.
- **Phase 1**: `rglob grep TODO src/ --json | jq` round-trips; `rglob
  count "*.py" --jsonl` works; full coverage maintained.
- **Phase 2**: `python -c "from rglob.agent import search, FileMatch"`
  succeeds; downstream `mypy --strict` accepts the exported types;
  ADR-0009 and ADR-0010 are reflected in the public docs.
- **Phase 3**: `pip install -e .[mcp]` + `rglob mcp` accepts a
  `tools/list` MCP request; integration test against a mocked stdio
  transport passes; documented Claude Code config produces a working
  tool call.
- **Phase 4**: `[ ]` every `docs/examples/*.md` runs as part of
  `make test` after `tests/examples_harness.py` lands; `[ ]`
  `make docs-build` strict-mode clean after the final docs pass; `[x]`
  new agent landing page content exists in the working tree.
- **Phase 5**: `[ ]` after tag/publish, `pip install rglob==2.0.0` from
  PyPI gives an importable `rglob.agent`, a working `rglob mcp` server,
  and a green smoke test driven by a real coding agent.

---

## Open questions to resolve before Phase 0 / Phase 1 starts

Some questions (CLI introspection syntax, schema generation approach,
golden fixture layout, `mcp` extra composition, and phase numbering)
were locked during the pre-implementation pass and are documented in
Phase 0 and Phase 3. The remaining open questions below will be answered
during the Phase 0 design pass.

1. **`grep` regex flavour** — stick with stdlib `re` (POSIX-ish,
   Python-flavoured), or expose `regex` as an optional extra for
   look-around / Unicode-class power users? Default proposal: stdlib
   `re` in 2.0; revisit in 2.x if asked.
2. **`grep` on binaries** — skip-by-default like ripgrep, with
   `--text/-a` to force? Default proposal: yes.
3. **MCP transport** — stdio is non-negotiable for Claude Code /
   Cursor. Should we *also* ship SSE/HTTP variants? Default proposal:
   no in 2.0.
4. **Versioning of `__agent_api_version__`** — separate SemVer line
   from package version, or always lockstep? Default proposal:
   separate, so the CLI / library can patch without touching the agent
   contract.
5. **`docs/examples/` runner** — *Locked*: a small custom harness in
   `tests/examples_harness.py` that walks `docs/examples/*.md`,
   extracts fenced \`\`\`bash and \`\`\`python blocks tagged with a
   magic header line (`<!-- example: name=foo runner=bash -->`),
   executes bash blocks via `subprocess.run` against a freshly-built
   wheel and Python blocks via `exec` in a per-example namespace, and
   compares stdout to a sibling `<!-- expected: ... -->` block when
   present. Doctest is too narrow (no shell coverage) and
   `pytest-codeblocks` adds a runtime dep we don't need.
6. **Default output limits** — what are the MCP and structured-CLI
   defaults for `limit`, `max_bytes`, and `timeout_seconds`? Default
   proposal: MCP is bounded by default; CLI path streaming is unbounded;
   CLI `--json` / `--jsonl` reports truncation and accepts explicit
   limit flags.
7. **Strict base containment** — should `strict_base=True` become a
   public `find()` default or only the agent/MCP default? Default
   proposal: keep the existing public walker behaviour for compatibility,
   but make agent/MCP tools strict by default.
8. **Structured JSON compatibility** — should current `find --json`
   remain a string array, or can it become a `SearchResult` object before
   2.0 ships? Default proposal: use the better `SearchResult` shape now
   because 2.0 is not released yet; offer `--json-paths` only if needed.

These are answered in-line during Phase 0's design pass; the defaults
above are what we'll execute unless flagged otherwise.
