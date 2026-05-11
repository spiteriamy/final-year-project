"""
Append-only JSONL backup helper.

Each call appends one JSON object as a single line. Uses an fcntl lock
on POSIX so concurrent workers can't interleave writes; falls back to a
plain append on Windows. ensure_ascii=False so non-ASCII (e.g. Latin
diacritics, user free-text in any language) survives round-trips.
"""

from pathlib import Path
from typing import Any, Mapping
import json
import os


def append_jsonl(path: Path, record: Mapping[str, Any]) -> None:
    """Append `record` as one JSON line to `path`. Creates parent dirs if needed."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, ensure_ascii=False) + "\n"

    # Open in append + binary mode so we control newlines exactly,
    # and so the OS-level append is atomic for small writes.
    with open(path, "ab") as f:
        if os.name == "posix":
            import fcntl
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            try:
                f.write(line.encode("utf-8"))
                f.flush()
                os.fsync(f.fileno())
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        else:
            # Windows: rely on append mode
            f.write(line.encode("utf-8"))
            f.flush()

