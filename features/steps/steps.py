"""Step definitions for Behave scenarios testing rglob.

Pylint notes:
- Behave's decorators confuse type inference; suppress not-callable for them.
"""

# pylint: disable=missing-function-docstring,not-callable
from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
import tempfile

from behave import given, then, when

import rglob


def _create_file(path: str, contents: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write(contents)


@given("I create a root directory")
def create_root_dir(context) -> None:
    if not hasattr(context, "root") or context.root is None:
        context.root = tempfile.mkdtemp(suffix="_rglob", prefix="root_")


@given("I create {num_of_sub_dirs:d} subdirectories in each directory")
def create_subdirectories(context, num_of_sub_dirs: int) -> None:
    subdirs: list[str] = []
    if not hasattr(context, "dirs") or not context.dirs:
        context.dirs = []
        for _ in range(num_of_sub_dirs):
            subdirs.append(tempfile.mkdtemp(prefix="subdir_", suffix="_rglob", dir=context.root))
    else:
        for root_dir in context.dirs:
            for _ in range(num_of_sub_dirs):
                subdirs.append(tempfile.mkdtemp(prefix="subdir_", suffix="_rglob", dir=root_dir))
    context.dirs.extend(subdirs)


@given("I create {num_of_files:d} {file_type} file in each directory")
@given("I create {num_of_files:d} {file_type} files in each directory")
def create_files(context, num_of_files: int, file_type: str) -> None:
    if not hasattr(context, "known_sizes"):
        context.known_sizes = {}
    for d in context.dirs:
        for n in range(num_of_files):
            contents = f"{n}: auto generated rglob behave test file"
            # NamedTemporaryFile with delete=False to get a disk file we can reopen.
            file_name = tempfile.mktemp(prefix="rglob_test_file", suffix=file_type, dir=d)
            _create_file(file_name, contents)
            if file_type not in context.known_sizes:
                context.known_sizes[file_type] = []
            context.known_sizes[file_type].append(os.path.getsize(file_name))


@given("I sum {file_type} files known sizes")
def sum_filesize(context, file_type: str) -> None:
    if file_type in context.known_sizes:
        context.known_size = rglob.kilobytes(sum(context.known_sizes[file_type]))
    else:
        context.known_size = 0


@then("I can find the same size for {file_type}")
def find_total_size(context, file_type: str) -> None:
    found_total_size = rglob.tsize(context.root, f"*{file_type}", rglob.kilobytes)
    assert found_total_size == context.known_size, (
        f"Known size {context.known_size} doesn't match found size {found_total_size}"
    )


@then("I find {expected_num_of_dirs:d} total directories")
def find_directories(context, expected_num_of_dirs: int) -> None:
    matches = rglob.rglob(context.root, "*_rglob")
    assert len(matches) == expected_num_of_dirs, f"Found {len(matches)} directories"


@then("I find {expected_num_of_files:d} total {file_type} files")
def find_files(context, expected_num_of_files: int, file_type: str) -> None:
    matches = rglob.rglob(context.root, f"*{file_type}")
    assert len(matches) == expected_num_of_files, f"Found {len(matches)} files"


@then("I delete all")
def delete_all_directories(context) -> None:
    all_paths = rglob.rglob(context.root, "*")
    all_paths.sort(reverse=True)
    for p in all_paths:
        if os.path.isdir(p):
            os.rmdir(p)
        else:
            os.remove(p)
    context.dirs = []
    context.known_sizes = {}


@given("I add {num_lines:d} lines to each {file_type} file")
def add_lines_to_files(context, num_lines: int, file_type: str) -> None:
    all_files = rglob.rglob(context.root, f"*{file_type}")
    for f in all_files:
        with open(f, "w", encoding="utf-8") as file:
            for i in range(num_lines):
                file.write(f"line {i + 1}\n")


@when("I count the lines in all {file_type} files")
def count_lines_in_files(context, file_type: str) -> None:
    context.line_count = rglob.lcount(context.root, f"*{file_type}")


@then("I should find {expected_line_count:d} lines")
def check_line_count(context, expected_line_count: int) -> None:
    assert context.line_count == expected_line_count, (
        f"Expected {expected_line_count} lines, but found {context.line_count}"
    )


@when("I change the current working directory to the root directory")
def change_cwd_to_root(context) -> None:
    os.chdir(context.root)


@when("I use rglob_ to find all {file_type} files")
def use_rglob_(context, file_type: str) -> None:
    context.found_files = rglob.rglob_(f"*{file_type}")


# ============================================================
# New steps for agent platform CLI commands (grep, count, describe, schema, capabilities)
# ============================================================


@when('I run "{command}"')
def run_rglob_command(context, command: str):
    """Run a rglob CLI command via python -m for reliability in test environments."""
    args = shlex.split(command)
    if args and args[0] == "rglob":
        args = args[1:]
    result = subprocess.run(
        [sys.executable, "-m", "rglob.cli", *args],
        cwd=context.root,
        capture_output=True,
        text=True,
        timeout=30,
    )
    context.last_result = result
    context.last_stdout = result.stdout
    context.last_stderr = result.stderr


@then("the command succeeds")
def command_succeeds(context):
    assert context.last_result.returncode == 0, (
        f"Command failed (exit code {context.last_result.returncode})\n"
        f"stderr:\n{context.last_stderr}\n"
        f"stdout:\n{context.last_stdout}"
    )


@then("the output should be valid JSON")
def output_is_valid_json(context):
    try:
        json.loads(context.last_stdout)
    except json.JSONDecodeError as exc:
        raise AssertionError(
            f"Output was not valid JSON: {exc}\nOutput was:\n{context.last_stdout}"
        ) from exc


def _last_json(context):
    """Return the most recent CLI stdout as JSON."""
    return json.loads(context.last_stdout)


def _contains_key(value, key: str) -> bool:
    """Return true if a JSON-compatible value contains a key anywhere."""
    if isinstance(value, dict):
        return key in value or any(_contains_key(item, key) for item in value.values())
    if isinstance(value, list):
        return any(_contains_key(item, key) for item in value)
    return False


@then('the JSON output should contain a "{key}" list')
def json_contains_list(context, key: str):
    data = _last_json(context)
    assert key in data and isinstance(data[key], list), (
        f"Expected '{key}' to be a list in JSON output"
    )


@then('the JSON output should contain "{field}" and "errors" fields')
def json_contains_truncation_and_errors(context, field: str):
    data = _last_json(context)
    assert field in data, f"Missing field: {field}"
    assert "errors" in data, "Missing 'errors' field"


@then('the JSON output should contain "{field1}", "{field2}", and "{field3}"')
def json_contains_three_fields(context, field1: str, field2: str, field3: str):
    data = _last_json(context)
    for field in (field1, field2, field3):
        assert field in data, f"Missing field: {field}"


@then('the JSON should contain the key "{key}"')
@then('the JSON should contain "{key}"')
def json_contains_key(context, key: str):
    data = _last_json(context)
    assert key in data, f"Expected key '{key}' not found in JSON output"


@then("the output should be valid JSON Schema Draft 2020-12")
def output_is_valid_json_schema(context):
    data = _last_json(context)
    if "$schema" in data:
        assert data["$schema"] == "https://json-schema.org/draft/2020-12/schema"
        return
    for schema in data.values():
        assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"


@then('the JSON should contain an "{key}" field')
def json_contains_key_anywhere(context, key: str):
    assert _contains_key(_last_json(context), key), f"Expected key '{key}' not found"


@then("the JSON output should indicate that results were truncated")
def json_indicates_truncation(context):
    data = _last_json(context)
    assert data.get("truncated") is True, "Expected 'truncated' to be True in JSON output"


@then("I should find {expected_num_files:d} files")
def check_found_files(context, expected_num_files: int) -> None:
    assert len(context.found_files) == expected_num_files, (
        f"Expected {expected_num_files} files, but found {len(context.found_files)}"
    )
