# CLI Recipes

Find Python files as structured JSON:

```bash
rglob find "*.py" --base src --json
```

Grep TODOs with context:

```bash
rglob grep TODO "*.py" --base src --context 2 --json
```

Count non-empty, non-comment Python lines:

```bash
rglob count "*.py" --base src --no-empty --no-comments --json
```

Discover command schemas:

```bash
rglob schema find
rglob schema --all
rglob describe grep
```
