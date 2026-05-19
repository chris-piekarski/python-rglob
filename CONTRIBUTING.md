# Contributing to `rglob`

Thanks for your interest! `rglob` is a small, fun, labor-of-love package — contributions in that spirit are very welcome.

## Quick start

```bash
git clone https://github.com/chris-piekarski/python-rglob.git
cd python-rglob
python -m venv .venv && source .venv/bin/activate
make dev-setup     # installs .[dev,bdd,docs] and pre-commit hooks
make test          # pytest + behave, gated at 100% coverage
make lint          # ruff + mypy --strict
```

## Standards we enforce

- **Lint**: `ruff check` and `ruff format --check` must pass.
- **Types**: `mypy --strict src/rglob` must pass.
- **Tests**: `pytest --cov --cov-fail-under=100` and `behave` must pass.
- **Coverage**: 100% line coverage on `src/rglob/`. Use `# pragma: no cover` only
  for genuinely un-coverable lines and document the reason inline.
- **Conventional commits** are nice but not required.

CI runs the full matrix (Python 3.11–3.14 × Ubuntu/macOS/Windows). Branch
protection on `master` blocks merges without all checks green.

### Cross-platform test guidelines

The Ubuntu, macOS, and Windows jobs share the same `tests/` tree, so new tests
must be portable or explicitly opt out:

- **POSIX mode bits** (`chmod`, `os.getuid`, exec-kind detection) — wrap the
  test in `@posix_only` (defined in `tests/test_filters.py`) or
  `@pytest.mark.skipif(os.name != "posix", reason=…)`. NTFS does not honour
  `Path.chmod()` for executable bits.
- **Filesystem case sensitivity** — APFS (macOS default) and NTFS treat
  `README.MD` and `readme.md` as one inode. Tests that need both casings as
  distinct files should request the `case_sensitive_fs` fixture (in
  `tests/conftest.py`) and `pytest.skip()` when it returns `False`.
- **Symlinks** — Windows requires Developer Mode or admin to create symlinks.
  Wrap `Path.symlink_to()` in `try/except (OSError, NotImplementedError)` and
  `pytest.skip()` on failure.
- **`bash` subprocesses** — Windows GA runners ship a WSL stub at
  `C:\Windows\System32\bash.exe` that exits non-zero when no distro is
  installed. Probe with `bash -c true` and check the return code (see
  `tests/test_examples.py::_has_bash`).

The `--cov-fail-under=95` gate only fires on Ubuntu because macOS/Windows
legitimately skip POSIX-only branches.

## Filing a bug or feature request

Open an issue at <https://github.com/chris-piekarski/python-rglob/issues>.
For security issues, please follow `SECURITY.md` instead.

## Pull request flow

1. Fork & branch off `master`.
2. Make your change; add tests; update `CHANGELOG.md` under `[Unreleased]`.
3. Run `make lint test` locally.
4. Open a PR. CodeRabbit / CI will leave comments — address them.
5. A maintainer will merge once green.

## Code of Conduct

By participating, you agree to abide by the [Contributor Covenant](CODE_OF_CONDUCT.md).
