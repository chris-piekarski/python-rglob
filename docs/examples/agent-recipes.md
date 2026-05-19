# Agent Recipes

## Find Python files modified recently

```bash
rglob find "*.py" --newer-than 7d --json
```

## Grep TODOs with context

```bash
rglob grep TODO "*.py" --context 2 --exclude .venv --exclude dist --json
```

## Count non-empty Python lines

```bash
rglob count "*.py" --no-empty --no-comments --json
```

## Find duplicate downloads over 1 MiB

```bash
rglob dupes "*" --base ~/Downloads --min-size 1MiB
```

---

## Runnable smoke tests

These blocks exercise the same surface against the project's golden
fixture (`tests/fixtures/agent-tree/`). They run as part of `make test`
via `tests/test_examples.py`, so the published recipes can't silently
rot. The fixture path is injected as the `$RGLOB_FIXTURE` env var.

<!-- example: name=find_py_files runner=bash expected_substring='helper.py' -->
```bash
rglob find "*.py" --base "$RGLOB_FIXTURE" --json
```

<!-- example: name=grep_todo_with_context runner=bash expected_substring='TODO' -->
```bash
rglob grep TODO "*.py" --base "$RGLOB_FIXTURE" --context 1 --json
```

<!-- example: name=schema_find_is_valid_jsonschema runner=bash expected_substring='WalkOptions' expected_substring='FileSearchResult' -->
```bash
rglob schema find
```

<!-- example: name=capabilities_reports_versions runner=bash expected_substring='agent_api_version' -->
```bash
rglob capabilities --json
```

<!-- example: name=python_search_all runner=python expected_substring='helper.py' -->
```python
import os
from pathlib import Path

from rglob.agent import WalkOptions, search_all

fixture = Path(os.environ["RGLOB_FIXTURE"])
result = search_all(WalkOptions(patterns=["*.py"], base=fixture, limit=100))
for match in result.results:
    print(match.relative_path)
```
