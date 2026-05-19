# Stability

The agent API version is exposed as `rglob.agent.__agent_api_version__` and
through `rglob agent-version`.

Locked surfaces:

- `rglob.agent` dataclasses and function signatures
- runtime-generated JSON Schemas
- structured CLI JSON / JSONL shapes
- MCP tool names and result shapes
- error codes and truncation metadata

Adding fields or flags requires a minor agent API bump. Removing or
renaming locked fields requires a major bump.
