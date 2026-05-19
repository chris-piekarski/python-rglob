# Contributing

The canonical contributor guide lives at [`CONTRIBUTING.md`][src] in the repo
root.

[src]: https://github.com/chris-piekarski/python-rglob/blob/master/CONTRIBUTING.md

## Quick start

```bash
git clone https://github.com/chris-piekarski/python-rglob.git
cd python-rglob
python -m venv .venv && source .venv/bin/activate
make dev-setup     # installs [dev,bdd,docs,gitignore] and pre-commit hooks
make test          # pytest + behave, gated at 100% local coverage
make lint          # ruff + mypy --strict
```

## Standards we enforce

- **Lint**: `ruff check` and `ruff format --check` must pass.
- **Types**: `mypy --strict src/rglob` must pass.
- **Tests**: `pytest --cov --cov-fail-under=100` and `behave` must pass.
- **Coverage**: 100% aggregated coverage on `src/rglob/` via Codecov merge
  (see [ADR-0006](decisions/0006-aggregated-coverage.md)). Local runs enforce
  100%; CI per-job enforces 95% with the merged-report gate at 100%.

CI runs the full matrix (Python 3.11–3.14 × Ubuntu/macOS/Windows).

## Filing bugs

Open an issue at <https://github.com/chris-piekarski/python-rglob/issues>.

For security issues, please follow the [security policy][sec] (GitHub private
advisories).

[sec]: https://github.com/chris-piekarski/python-rglob/security/policy
