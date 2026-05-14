"""Duplicate-file detection used by the `rglob dupes` subcommand.

Strategy:
1. Bucket candidate files by exact size.
2. For each size bucket with ≥2 entries, bucket again by the hash of the
   first 4 KiB.
3. For each surviving bucket with ≥2 entries, hash the full contents.

This three-stage approach minimises I/O — large unique files only ever read
their first 4 KiB.

Uses :func:`xxhash.xxh3_64` when available (under the `[ext]` extra) and
falls back to :func:`hashlib.file_digest` with BLAKE2b otherwise — both
are fast enough in 2026 that the choice is rarely visible.
"""

from __future__ import annotations

import hashlib
from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path


def _fast_hash(data: bytes) -> str:
    """Return a fast 64-bit hex digest of `data`.

    Uses :func:`xxhash.xxh3_64` when the optional ``xxhash`` dependency is
    installed (via ``pip install rglob[ext]``); falls back to the stdlib
    BLAKE2b otherwise — both are fast enough in 2026 that the choice is
    rarely visible.
    """
    try:
        import xxhash

        return xxhash.xxh3_64(data).hexdigest()
    except ImportError:  # pragma: no cover - exercised only when xxhash absent
        return hashlib.blake2b(data, digest_size=16).hexdigest()


# Chunk read for the fast-path "first 4 KiB" bucket.
_HEAD_BYTES = 4 * 1024


def _hash_head(path: Path) -> str:
    """Hash the first 4 KiB of a file."""
    with path.open("rb") as fp:
        chunk = fp.read(_HEAD_BYTES)
    return _fast_hash(chunk)


def _hash_full(path: Path) -> str:
    """Hash the entire file in 64 KiB chunks."""
    hasher_state = hashlib.blake2b(digest_size=16)
    with path.open("rb") as fp:
        while True:
            chunk = fp.read(64 * 1024)
            if not chunk:
                break
            hasher_state.update(chunk)
    return hasher_state.hexdigest()


def find_duplicates(paths: Iterable[Path]) -> list[list[Path]]:
    """Group paths by content equivalence.

    Returns a list of groups, where each group contains 2+ paths sharing
    identical bytes. Files that are unique are *not* returned (only
    duplicate groups).
    """
    by_size: dict[int, list[Path]] = defaultdict(list)
    for path in paths:
        try:
            if not path.is_file():
                continue
            by_size[path.stat().st_size].append(path)
        except OSError:  # pragma: no cover - rare
            continue

    candidates: list[list[Path]] = []
    for group in by_size.values():
        if len(group) < 2:
            continue
        by_head: dict[str, list[Path]] = defaultdict(list)
        for path in group:
            try:
                by_head[_hash_head(path)].append(path)
            except OSError:  # pragma: no cover - rare
                continue
        candidates.extend(head_group for head_group in by_head.values() if len(head_group) >= 2)

    final_groups: list[list[Path]] = []
    for group in candidates:
        by_full: dict[str, list[Path]] = defaultdict(list)
        for path in group:
            try:
                by_full[_hash_full(path)].append(path)
            except OSError:  # pragma: no cover - rare
                continue
        final_groups.extend(
            sorted(full_group) for full_group in by_full.values() if len(full_group) >= 2
        )

    return final_groups
