# Migrating to 2.0

`rglob` 2.0 is a top-to-bottom modernization (see the
[roadmap](plans/modernization-roadmap.md)). The vast majority of changes are
additive — new helpers, new CLI flags, better docs. **One** intentional
breaking change is worth calling out:

## The breaking change: `list[Path]` return type

`rglob()` and `rglob_()` now return **`list[pathlib.Path]`** instead of
`list[str]`. The new `find()` / `find_all()` family already returns `Path`,
so code that already migrated to them is unaffected.

### One-line migration

```diff
- paths: list[str] = rglob("/repo", "*.py")
+ paths: list[Path] = rglob("/repo", "*.py")          # if you want Path
+ paths: list[str]  = [str(p) for p in rglob("/repo", "*.py")]   # if you want str
```

### Why this changes

- Modern Python (`pathlib.Path`, `os.PathLike`, `mypy` strict mode) is much
  nicer to use with `Path` instances than raw strings.
- The Phase 3 walker rewrite is on `os.scandir`, which natively produces
  `Path`-compatible entries.
- Downstream filters introduced in Phase 5 (`--gitignore`, `min_size`,
  `kinds=...`) want `Path` semantics anyway.

See [ADR-0003](decisions/0003-path-return.md) for the full reasoning.

## Other changes worth knowing

These are not breaking, but they are new defaults you might encounter:

### Sorted output

`rglob()` and `find()` now sort entries by default (the 1.x walker
documented its output as "not guaranteed sorted"). Pass `sort=False` to opt
out:

```python
paths = rglob.find_all("/repo", "*.py", sort=False)
```

### Python floor: 3.11

`rglob` 2.0 requires **Python 3.11+** (3.10 reaches upstream EOL in October
2026; see [ADR-0002](decisions/0002-python-floor.md)). Pin `rglob<2` if you
need 3.10 support:

```text
rglob<2; python_version<"3.11"
rglob>=2; python_version>="3.11"
```

### `**` patterns now work

The 1.x README explicitly disclaimed `**` support
(`"**/*.py" is not supported here`). The 2.0 walker handles `**` natively:

```python
rglob.find_all("/repo", "**/*.py")
```

### Symlink handling is opt-in

By default, the walker does **not** follow symbolic links. Pass
`follow_symlinks=True` to opt in; cycles are terminated automatically via a
realpath memo. See [ADR-0008](decisions/0008-security-model.md).

### Hidden files are skipped by default

Dotfiles and dot-directories are skipped unless you pass `hidden=True`.

## Doing a clean upgrade

1. Bump your pin to `rglob>=2,<3`.
2. Run your test suite — type checkers will flag any `list[str]` callers.
3. Apply the `str(p)` wrap where you really need strings, or migrate to
   `Path` semantics.
4. Adopt `find()` / `find_all()` for new code — they have the full filter
   suite (`exclude`, `max_depth`, `hidden`, `kinds`, `min_size`, etc.).

If you hit anything surprising, please file an issue at
<https://github.com/chris-piekarski/python-rglob/issues>.
