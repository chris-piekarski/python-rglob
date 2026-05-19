# Python API

Use `rglob.agent` when an integration needs stable dataclasses and
non-raising operational behavior.

```python
from pathlib import Path

from rglob.agent import GrepOptions, WalkOptions, grep_all, schema_for, search_all

files = search_all(WalkOptions(patterns=["*.py"], base=Path("src")))
for match in files.results:
    print(match.relative_path)

todos = grep_all(GrepOptions(pattern="TODO", paths=["*.py"], base=Path("src")))
for match in todos.results:
    print(match.path, match.line_number, match.content)

walk_schema = schema_for("walk_options")
```

Operational errors such as unreadable files, bad predicates, binary grep
skips, and regex failures are returned as `ErrorInfo` records on the result
object. Programmer errors can still raise.
