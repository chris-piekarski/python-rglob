"""Tests for the duplicate-detection module (Phase 5)."""

from __future__ import annotations

from rglob._dupes import find_duplicates


def test_no_duplicates_empty_tree(tmp_path):
    """No files → no groups."""
    assert find_duplicates([]) == []


def test_unique_files_no_groups(tmp_path):
    """Two distinct files of the same size still aren't duplicates."""
    a = tmp_path / "a.bin"
    b = tmp_path / "b.bin"
    a.write_bytes(b"hello world!!!")  # 14 bytes
    b.write_bytes(b"goodbye world!")  # 14 bytes
    assert find_duplicates([a, b]) == []


def test_exact_duplicates_grouped(tmp_path):
    """Two identical files form one group."""
    a = tmp_path / "a.bin"
    b = tmp_path / "b.bin"
    payload = b"identical content"
    a.write_bytes(payload)
    b.write_bytes(payload)
    groups = find_duplicates([a, b])
    assert len(groups) == 1
    assert set(groups[0]) == {a, b}


def test_three_way_duplicates(tmp_path):
    """Three identical files form a single group of three."""
    payload = b"X" * 5000  # >4KB so head + full hash both run
    files = []
    for name in ("a", "b", "c"):
        p = tmp_path / f"{name}.bin"
        p.write_bytes(payload)
        files.append(p)
    groups = find_duplicates(files)
    assert len(groups) == 1
    assert set(groups[0]) == set(files)


def test_partial_overlap(tmp_path):
    """First 4 KiB match but full bytes differ → not a group."""
    head = b"X" * 4096
    a = tmp_path / "a.bin"
    b = tmp_path / "b.bin"
    a.write_bytes(head + b"hello")
    b.write_bytes(head + b"world")
    assert find_duplicates([a, b]) == []


def test_mixed_groups(tmp_path):
    """Multiple disjoint groups are returned independently."""
    g1_payload = b"group-one-payload"
    g2_payload = b"different-group-content"
    a = tmp_path / "g1a.bin"
    b = tmp_path / "g1b.bin"
    c = tmp_path / "g2a.bin"
    d = tmp_path / "g2b.bin"
    e = tmp_path / "lonely.bin"
    a.write_bytes(g1_payload)
    b.write_bytes(g1_payload)
    c.write_bytes(g2_payload)
    d.write_bytes(g2_payload)
    e.write_bytes(b"unique")
    groups = find_duplicates([a, b, c, d, e])
    sets = [set(g) for g in groups]
    assert {a, b} in sets
    assert {c, d} in sets
    # lonely.bin must not appear in any group
    assert all(e not in s for s in sets)


def test_directory_inputs_skipped(tmp_path):
    """Directory inputs are skipped (only files are hashed)."""
    sub = tmp_path / "sub"
    sub.mkdir()
    assert find_duplicates([sub]) == []
