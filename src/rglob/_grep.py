r"""Content search helpers for the agent-aware grep command.

The walker yields candidate files via :func:`rglob.find`. Each file is
streamed through a binary peek (for ``\x00`` detection) followed by an
``io.TextIOWrapper`` for line-by-line iteration — this avoids reading
the full file into memory and lets the loop break out as soon as
``--limit`` / ``--max-count`` / ``--max-bytes`` / ``--timeout`` fires,
which matters most on large files where only the first few lines need
to be searched.

Trailing context (``--after`` / ``--context``) requires lookahead, so
matches that still need after-lines park in a small *pending* list.
Each subsequent line either feeds existing pending matches or starts a
new one; pending matches finalize when their counter hits zero or the
file ends.
"""

import io
import re
from collections import deque
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

from rglob import find as _find
from rglob.agent._models import ErrorCode, ErrorInfo, GrepOptions, LineMatch, LineSearchResult
from rglob.agent._runtime import (
    _absolute,
    _is_contained,
    _strict_base_error,
    check_timeout,
    deadline_from_timeout,
    timeout_error,
)

# Bytes peeked from each file to classify it as binary before streaming.
_BINARY_PROBE_BYTES = 1024

# Files at or below this size are read with a single `fp.read()` and
# split via `str.splitlines()` rather than wrapped in
# :class:`io.TextIOWrapper`. The wrapper has measurable per-file
# instantiation overhead that dominates for small files where
# early-termination isn't possible anyway. Large files keep the
# streaming path so `--limit` / `--max-count` / `--timeout` short-
# circuit reading.
_STREAM_THRESHOLD_BYTES = 64 * 1024


def _compile_pattern(opts: GrepOptions) -> re.Pattern[str]:
    """Compile a grep pattern according to options."""
    pattern = re.escape(opts.pattern) if opts.fixed_string else opts.pattern
    if opts.word:
        pattern = rf"\b(?:{pattern})\b"
    flags = re.IGNORECASE if opts.ignore_case else 0
    return re.compile(pattern, flags)


def _is_binary(data: bytes) -> bool:
    """Return true when a byte sample looks binary."""
    return b"\x00" in data[:_BINARY_PROBE_BYTES]


def _iter_candidate_files(opts: GrepOptions) -> Iterable[Path]:
    """Yield files selected by the path side of GrepOptions."""
    return _find(
        opts.base,
        opts.paths,
        exclude=opts.exclude,
        max_depth=opts.max_depth,
        hidden=opts.hidden,
        follow_symlinks=opts.follow_symlinks,
        case_sensitive=opts.case_sensitive,
        sort=opts.sort,
        on_error="ignore",
        kinds=opts.kinds,
        min_size=opts.min_size,
        max_size=opts.max_file_size or opts.max_size,
        newer_than=opts.newer_than,
        older_than=opts.older_than,
        newer_than_file=opts.newer_than_file,
        perm=opts.perm,
        uid=opts.uid,
        gid=opts.gid,
        respect_gitignore=opts.respect_gitignore,
    )


@dataclass
class _PendingMatch:
    """In-flight match whose `after` context is still being collected."""

    line_match: LineMatch
    remaining_after: int
    after: list[str] = field(default_factory=list)

    def feed(self, line: str) -> bool:
        """Append `line` to this match's after context. Returns True when full."""
        self.after.append(line)
        self.remaining_after -= 1
        return self.remaining_after == 0

    def finalize(self) -> LineMatch:
        """Materialise the LineMatch with whatever after lines we collected."""
        return LineMatch(
            path=self.line_match.path,
            line_number=self.line_match.line_number,
            content=self.line_match.content,
            before=self.line_match.before,
            after=self.after,
            encoding=self.line_match.encoding,
        )


def grep_iter(opts: GrepOptions) -> Iterable[LineMatch]:
    """Yield each :class:`LineMatch` as the search progresses.

    Useful for ``--jsonl`` consumers that want one record per line of
    output. Errors / truncation / per-file stats are *not* surfaced
    through this generator — the caller can follow up with
    :func:`grep_all` against the same options to get a full
    :class:`LineSearchResult` summary.

    The current implementation buffers internally via :func:`grep_all`
    and yields after the search completes; the public contract still
    holds (one ``LineMatch`` per yielded value, in find order), and a
    future refactor can make the underlying scan truly lazy without
    changing this signature.
    """
    yield from grep_all(opts).results


def grep_all(opts: GrepOptions) -> LineSearchResult:
    """Search files selected by GrepOptions and return structured matches.

    Streams each file line-by-line via :class:`io.TextIOWrapper` so the
    walker stops reading as soon as ``--limit`` / ``--max-count`` /
    ``--max-bytes`` / ``--timeout`` fires. Trailing-context matches are
    parked in a small pending list and finalised when their counter
    reaches zero or the file ends.
    """
    try:
        regex = _compile_pattern(opts)
    except re.error as exc:
        return LineSearchResult(
            results=[],
            truncated=False,
            total_files_searched=0,
            bytes_read=0,
            errors=[ErrorInfo(ErrorCode.REGEX, str(exc), None)],
            truncated_reason=None,
        )

    results: list[LineMatch] = []
    errors: list[ErrorInfo] = []
    total_files = 0
    bytes_read = 0
    truncated = False
    truncated_reason: str | None = None
    files_with_matches = opts.files_with_matches
    count_only = opts.count_only
    summary_only = files_with_matches or count_only
    # `--files-with-matches` and `--count-only` emit one summary
    # `LineMatch` per matching file; per-line context never makes sense
    # for them, so collapse the cold path and skip per-line `before`/
    # `after` tracking entirely.
    before_count = 0 if summary_only else (opts.context if opts.context else opts.before)
    after_count = 0 if summary_only else (opts.context if opts.context else opts.after)
    deadline = deadline_from_timeout(opts.timeout_seconds)
    limit = opts.limit
    max_count = opts.max_count
    invert = opts.invert
    encoding = opts.encoding
    include_errors = opts.include_errors
    regex_search = regex.search  # bound-method hoist for the hot loop

    pending: list[_PendingMatch] = []

    for path in _iter_candidate_files(opts):
        try:
            check_timeout(deadline)
        except TimeoutError:
            truncated = True
            truncated_reason = "timeout"
            if opts.include_errors:
                errors.append(timeout_error())
            break

        if opts.strict_base and not _is_contained(path, opts.base):
            if opts.include_errors:
                errors.append(_strict_base_error(path, _absolute(opts.base)))
            continue

        try:
            file_size = path.stat().st_size
        except OSError as exc:
            if opts.include_errors:
                errors.append(ErrorInfo(ErrorCode.UNREADABLE, str(exc), _absolute(path)))
            continue

        if opts.max_bytes is not None and bytes_read + file_size > opts.max_bytes:
            truncated = True
            truncated_reason = "max_bytes"
            break

        # `bytes_read` is a per-file budget account — adding `file_size`
        # up front (rather than tracking actual bytes consumed by
        # streaming) keeps the `--max-bytes` gate stable and pessimistic
        # in the right direction (we never over-budget).
        bytes_read += file_size
        total_files += 1
        file_truncated = False
        file_path_abs = _absolute(path)

        try:
            with path.open("rb") as fp:
                # Choose between read-all and streaming. Small files pay
                # too much for `TextIOWrapper` instantiation; large files
                # benefit from the early-break short-circuit it enables.
                if file_size <= _STREAM_THRESHOLD_BYTES:
                    data = fp.read()
                    if _is_binary(data) and not opts.text:
                        if opts.include_errors:
                            errors.append(
                                ErrorInfo(ErrorCode.BINARY, "binary file skipped", file_path_abs)
                            )
                        continue
                    text = data.decode(opts.encoding, errors="replace")
                    line_iter: Iterable[str] = iter(text.splitlines())
                    text_stream: io.TextIOWrapper | None = None
                else:
                    head = fp.read(_BINARY_PROBE_BYTES)
                    if _is_binary(head) and not opts.text:
                        if opts.include_errors:
                            errors.append(
                                ErrorInfo(ErrorCode.BINARY, "binary file skipped", file_path_abs)
                            )
                        continue
                    fp.seek(0)
                    # `TextIOWrapper` takes ownership of `fp` for line
                    # iteration; the outer `with` still closes the file.
                    text_stream = io.TextIOWrapper(fp, encoding=opts.encoding, errors="replace")
                    line_iter = text_stream

                previous: deque[str] = deque(maxlen=before_count)
                pending.clear()
                file_match_counter = 0

                try:
                    if after_count == 0:
                        # Hot path: no after-context, no pending list.
                        # `committed = len(results)` (no pending entries
                        # ever exist on this branch), so `--limit` and
                        # `--max-count` are dirt-cheap O(1) checks.
                        for line_number, raw_line in enumerate(line_iter, start=1):
                            line = raw_line.rstrip("\r\n")

                            try:
                                check_timeout(deadline)
                            except TimeoutError:
                                truncated = True
                                truncated_reason = "timeout"
                                if include_errors:
                                    errors.append(timeout_error(file_path_abs))
                                file_truncated = True
                                break

                            matched = regex_search(line) is not None
                            if invert:
                                matched = not matched

                            if matched:
                                if files_with_matches:
                                    # One stub per matching file → stop reading
                                    # *this* file. `file_truncated` only flips
                                    # if the global limit is hit, so the outer
                                    # file loop continues to the next file.
                                    results.append(
                                        LineMatch(
                                            path=file_path_abs,
                                            line_number=0,
                                            content="",
                                            before=[],
                                            after=[],
                                            encoding=encoding,
                                        )
                                    )
                                    if limit is not None and len(results) >= limit:
                                        truncated = True
                                        truncated_reason = "limit"
                                        file_truncated = True
                                    break
                                if count_only:
                                    file_match_counter += 1
                                    continue
                                results.append(
                                    LineMatch(
                                        path=file_path_abs,
                                        line_number=line_number,
                                        content=line,
                                        before=list(previous),
                                        after=[],
                                        encoding=encoding,
                                    )
                                )
                                committed = len(results)
                                if limit is not None and committed >= limit:
                                    truncated = True
                                    truncated_reason = "limit"
                                    file_truncated = True
                                    break
                                if max_count is not None and committed >= max_count:
                                    truncated = True
                                    truncated_reason = "max_count"
                                    file_truncated = True
                                    break

                            previous.append(line)

                        # `count_only` defers emission until the file is
                        # fully scanned (or short-circuited by a limit on
                        # a per-file basis — N/A here since count_only
                        # never breaks early on its own).
                        if count_only and file_match_counter > 0:
                            results.append(
                                LineMatch(
                                    path=file_path_abs,
                                    line_number=file_match_counter,
                                    content="",
                                    before=[],
                                    after=[],
                                    encoding=encoding,
                                )
                            )
                            if limit is not None and len(results) >= limit:
                                truncated = True
                                truncated_reason = "limit"
                                file_truncated = True
                    else:
                        # Cold path: trailing context (`--after`/`--context`).
                        # Pending matches park here until their after-counter
                        # hits zero or the file ends.
                        for line_number, raw_line in enumerate(line_iter, start=1):
                            line = raw_line.rstrip("\r\n")

                            if pending:
                                still_pending: list[_PendingMatch] = []
                                for pmatch in pending:
                                    if pmatch.feed(line):
                                        results.append(pmatch.finalize())
                                    else:
                                        still_pending.append(pmatch)
                                pending = still_pending

                            try:
                                check_timeout(deadline)
                            except TimeoutError:
                                truncated = True
                                truncated_reason = "timeout"
                                if include_errors:
                                    errors.append(timeout_error(file_path_abs))
                                file_truncated = True
                                break

                            matched = regex_search(line) is not None
                            if invert:
                                matched = not matched

                            committed = len(results) + len(pending)
                            if matched and (limit is None or committed < limit):
                                pending.append(
                                    _PendingMatch(
                                        LineMatch(
                                            path=file_path_abs,
                                            line_number=line_number,
                                            content=line,
                                            before=list(previous),
                                            after=[],
                                            encoding=encoding,
                                        ),
                                        after_count,
                                    )
                                )
                                committed = len(results) + len(pending)

                            if limit is not None and committed >= limit and not pending:
                                truncated = True
                                truncated_reason = "limit"
                                file_truncated = True
                                break
                            if max_count is not None and committed >= max_count and not pending:
                                truncated = True
                                truncated_reason = "max_count"
                                file_truncated = True
                                break

                            previous.append(line)
                finally:
                    # Flush pending matches with whatever after-context we
                    # collected. Pending is per-file: matches never span
                    # files. `text_stream.detach()` releases the underlying
                    # `fp` so the outer `with` can close it; the read-all
                    # path has no wrapper to detach.
                    results.extend(p.finalize() for p in pending)
                    pending.clear()
                    if text_stream is not None:
                        text_stream.detach()
        except OSError as exc:
            if opts.include_errors:
                errors.append(ErrorInfo(ErrorCode.UNREADABLE, str(exc), file_path_abs))
            continue

        if file_truncated:
            break

    return LineSearchResult(
        results=results,
        truncated=truncated,
        total_files_searched=total_files,
        bytes_read=bytes_read,
        errors=errors,
        truncated_reason=truncated_reason,
    )
