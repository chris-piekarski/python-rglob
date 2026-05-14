# Architecture

This page describes the package shape and how the pieces fit together. It
accretes per phase — each later phase adds its own diagrams (CLI hierarchy,
walker call-graph, `dupes` pipeline, final public-API class diagram).

## Phase 2 — Package layout

```mermaid
graph TD
    subgraph Source
        SRC[src/rglob/]
        INIT[__init__.py<br/>Public API + __version__]
        CORE[rglob.py<br/>rglob, rglob_, lcount, tsize,<br/>unit helpers]
        CLI[cli.py<br/>argparse → Typer in Phase 4]
        PYTYPED[py.typed]
    end

    subgraph Tests
        PYTEST[tests/<br/>pytest + hypothesis]
        BEHAVE[features/<br/>behave BDD]
        BENCH[bench/<br/>pytest-benchmark — Phase 5]
    end

    subgraph Docs
        MKDOCS[docs/<br/>MkDocs Material]
        ADRS[docs/decisions/<br/>ADRs]
        PLANS[docs/plans/<br/>Modernization roadmap]
    end

    subgraph CI
        CIYML[.github/workflows/ci.yml<br/>Lint · Test · Coverage]
        RELYML[.github/workflows/release.yml<br/>OIDC PyPI publish]
        DOCSYML[.github/workflows/docs.yml<br/>gh-pages deploy]
    end

    SRC --> INIT
    SRC --> CORE
    SRC --> CLI
    SRC --> PYTYPED

    PYTEST -. imports .-> SRC
    BEHAVE -. imports .-> SRC
    BENCH -. imports .-> SRC

    CIYML -. runs .-> PYTEST
    CIYML -. runs .-> BEHAVE
    DOCSYML -. builds .-> MKDOCS
    RELYML -. builds .-> SRC
```

## Phase 2 — CI flow

```mermaid
flowchart LR
    PR[Pull Request] --> LINT[Lint job<br/>ruff check · ruff format --check · mypy --strict]
    PR --> TEST[Test matrix<br/>3.11–3.14 × ubuntu/macos/windows]
    TEST --> COV[pytest --cov<br/>per-job fail_under=95]
    TEST --> BDD[behave]
    COV --> CC[Codecov upload<br/>per matrix cell]
    CC --> AGG[Codecov merged report<br/>project gate = 100%]
    LINT --> BP[Branch protection on master<br/>blocks merge if any check fails]
    AGG --> BP
    BDD --> BP
```

## Walker call-graph — Phase 3

```mermaid
flowchart TD
    USER[find(base, patterns, ...)]
    COMPILE[_compile_patterns<br/>fnmatch + ** translation]
    HANDLER[_make_error_handler<br/>ignore | warn | raise]
    WALK[_walk<br/>recursive descent]
    SCAN[os.scandir<br/>cached DirEntry.d_type]
    SORT{sort?}
    MATCH[_matches_any<br/>basename or rel-path]
    EXCLUDE[exclude matchers]
    DEPTH{max_depth?}
    HIDDEN{hidden=False<br/>and name.startswith('.')?}
    REAL[os.path.realpath<br/>cycle memo]
    YIELD[yield Path]

    USER --> COMPILE --> WALK
    USER --> HANDLER --> WALK
    WALK --> SCAN
    SCAN --> SORT
    SORT --> MATCH
    MATCH --> EXCLUDE
    EXCLUDE -- excluded --> WALK
    EXCLUDE -- kept --> HIDDEN
    HIDDEN -- skip --> WALK
    HIDDEN -- keep --> YIELD
    YIELD --> DEPTH
    DEPTH -- under limit --> REAL
    REAL -- new --> WALK
    REAL -- already visited --> WALK
```

## Symlink-loop detection

```mermaid
sequenceDiagram
    participant F as find(...)
    participant W as _walk
    participant FS as os.scandir
    participant R as os.path.realpath
    participant V as visited: set[str]

    F->>V: add realpath(base)
    F->>W: walk(base, depth=0)
    W->>FS: scandir(base)
    FS-->>W: [a/, sym->base]
    W->>R: realpath(base/a/)
    R-->>W: /base/a (new)
    W->>V: add /base/a
    W->>W: recurse(base/a, depth=1)

    W->>R: realpath(base/sym)
    R-->>W: /base (already in V)
    W-->>F: skip; do not recurse
```

## Pattern translation (the `**` story)

```mermaid
flowchart LR
    P[pattern: str]
    HAS{contains **?}
    SLASH{contains / or sep?}
    TR1[fnmatch.translate<br/>basename matcher]
    TR2[fnmatch.translate<br/>relpath matcher]
    TR3["preprocess<br/>**/ → (?:.*/)?<br/>/** → (?:/.*)?<br/>** → .*"]
    REGEX[re.compile]

    P --> HAS
    HAS -- no --> SLASH
    SLASH -- no --> TR1
    SLASH -- yes --> TR2
    HAS -- yes --> TR3 --> REGEX
    TR1 --> REGEX
    TR2 --> REGEX
```

## CLI command hierarchy — Phase 4

```mermaid
graph TD
    APP[rglob CLI<br/>Typer + Rich]

    APP --> FIND[rglob find]
    APP --> LCOUNT[rglob lcount]
    APP --> TSIZE[rglob tsize]
    APP --> COMPL[--install-completion]

    FIND --> FILTERS[Shared filter options<br/>-E --exclude<br/>-d --max-depth<br/>-H --hidden<br/>-L --follow<br/>-s/-i --case-sensitive/-insensitive<br/>--gitignore/--no-gitignore]
    FIND --> FORMATS[Output formats<br/>--json<br/>--jsonl<br/>-0 --null<br/>--format TEMPLATE]

    LCOUNT --> LFLAGS[--no-empty<br/>--no-comments]

    TSIZE --> TFLAGS[--unit kb/mb/gb/tb]

    classDef shared fill:#eef,stroke:#557,color:#000
    class FILTERS,FORMATS,LFLAGS,TFLAGS shared
```

Each subcommand calls into `rglob.rglob.find()` (or the legacy `rglob` /
`lcount` / `tsize` wrappers); the CLI is a thin Typer layer over the
library API.

## `dupes` pipeline — Phase 5

```mermaid
flowchart LR
    INPUT[Paths from find]
    SIZE[Bucket by exact size]
    HEAD[Bucket by xxh3_64<br/>of first 4 KiB]
    FULL[Bucket by blake2b<br/>over full bytes]
    OUT[Groups of 2+ paths]

    INPUT --> SIZE
    SIZE -- "≥2 in bucket" --> HEAD
    SIZE -- "1 in bucket" --> SKIP1[discard - unique]
    HEAD -- "≥2 in bucket" --> FULL
    HEAD -- "1 in bucket" --> SKIP2[discard - false-positive]
    FULL -- "≥2 in bucket" --> OUT
    FULL -- "1 in bucket" --> SKIP3[discard - confirmed unique]
```

Large unique files only ever read their first 4 KiB; the full hash only
runs on confirmed candidates.

## `.gitignore` pruning sequence — Phase 5

```mermaid
sequenceDiagram
    participant F as find(respect_gitignore=True)
    participant G as gitignore_matcher
    participant PS as pathspec.PathSpec
    participant W as _walk

    F->>G: gitignore_matcher(base)
    G->>G: rglob(".gitignore")
    G->>PS: PathSpec.from_lines("gitignore", lines)
    G-->>F: predicate(path) → bool
    F->>W: walk(base, gitignore=predicate)
    loop per entry
        W->>G: predicate(path)
        G->>PS: spec.match_file(rel)
        PS-->>W: match?
        W-->>W: skip if ignored, else yield/recurse
    end
```

## Public API surface — 2.0

```mermaid
classDiagram
    class rglob {
        <<module>>
        +__version__: "2.0.0"
        +find(base, patterns, *, exclude, max_depth, hidden, follow_symlinks, case_sensitive, sort, on_error, kinds, min_size, max_size, newer_than, older_than, respect_gitignore) Iterator~Path~
        +find_all(...) list~Path~
        +rglob(base, pattern) list~Path~
        +rglob_(pattern) list~Path~
        +lcount(base, pattern, func) int
        +tsize(base, pattern, func) float
        +kilobytes(value) float
        +megabytes(value) float
        +gigabytes(value) float
        +terabytes(value) float
    }

    class CLI {
        <<typer.Typer app>>
        +find(patterns, ...) None
        +lcount(pattern, ...) None
        +tsize(pattern, ...) None
        +stats(pattern, ...) None
        +tree(pattern, ...) None
        +top(pattern, ...) None
        +dupes(pattern, ...) None
    }

    class _filters {
        <<internal>>
        +parse_size(value) int
        +parse_time(value) datetime
        +size_predicate(min_size, max_size) Callable
        +mtime_predicate(newer_than, older_than) Callable
        +kinds_match(entry, wanted) bool
        +gitignore_matcher(base) Callable~|None
    }

    class _dupes {
        <<internal>>
        +find_duplicates(paths) list~list~Path~~
        -_hash_head(path) str
        -_hash_full(path) str
        -_fast_hash(data) str
    }

    CLI ..> rglob : calls
    rglob ..> _filters : uses
    CLI ..> _dupes : uses
```

The user-facing surface is intentionally small: one module-level `find()`
generator plus six legacy compatibility helpers, all importable directly
from `rglob`. Internal modules (`_filters`, `_dupes`) are prefixed with
`_` and not re-exported.
