"""Step definitions for Behave scenarios testing rglob.

Pylint notes:
- Behave's decorators confuse type inference; suppress not-callable for them.
"""
# pylint: disable=missing-function-docstring,not-callable
from __future__ import annotations

import os
import tempfile
from behave import given, then

import rglob


def _create_file(path: str, contents: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write(contents)


@given("I create a root directory")
def create_root_dir(context) -> None:
    if context.root is None:
        context.root = tempfile.mkdtemp(suffix="_rglob", prefix="root_")


@given("I create {num_of_sub_dirs:d} subdirectories in each directory")
def create_subdirectories(context, num_of_sub_dirs: int) -> None:
    subdirs: list[str] = []
    if not context.dirs:
        for _ in range(num_of_sub_dirs):
            subdirs.append(
                tempfile.mkdtemp(prefix="subdir_", suffix="_rglob", dir=context.root)
            )
    else:
        for root_dir in context.dirs:
            for _ in range(num_of_sub_dirs):
                subdirs.append(
                    tempfile.mkdtemp(
                        prefix="subdir_", suffix="_rglob", dir=root_dir
                    )
                )
    context.dirs.extend(subdirs)


@given("I create {num_of_files:d} {file_type} files in each directory")
def create_files(context, num_of_files: int, file_type: str) -> None:
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
    assert (
        found_total_size == context.known_size
    ), f"Known size {context.known_size} doesn't match found size {found_total_size}"


@then("I find {expected_num_of_dirs:d} total directories")
def find_directories(context, expected_num_of_dirs: int) -> None:
    matches = rglob.rglob(context.root, "*_rglob")
    assert (
        len(matches) == expected_num_of_dirs
    ), f"Found {len(matches)} directories"


@then("I find {expected_num_of_files:d} total {file_type} files")
def find_files(context, expected_num_of_files: int, file_type: str) -> None:
    matches = rglob.rglob(context.root, f"*{file_type}")
    assert (
        len(matches) == expected_num_of_files
    ), f"Found {len(matches)} files"


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
