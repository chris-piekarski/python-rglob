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

> **Note**: the `Makefile` and dev extras are introduced in Phase 2 of the
> [modernization roadmap](docs/plans/modernization-roadmap.md). Until that lands,
> use `pip install -e .` and run `pylint src/rglob features` (legacy path) or
> `behave` directly.

## Standards we enforce

- **Lint**: `ruff check` and `ruff format --check` must pass.
- **Types**: `mypy --strict src/rglob` must pass.
- **Tests**: `pytest --cov --cov-fail-under=100` and `behave` must pass.
- **Coverage**: 100% line coverage on `src/rglob/`. Use `# pragma: no cover` only
  for genuinely un-coverable lines and document the reason inline.
- **Conventional commits** are nice but not required.

CI runs the full matrix (Python 3.10–3.13 × Ubuntu/macOS/Windows). Branch
protection on `master` blocks merges without all checks green.

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
