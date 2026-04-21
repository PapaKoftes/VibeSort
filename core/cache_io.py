"""
cache_io.py — Shared atomic-write helper for JSON caches.

Every enrichment cache (Deezer, Last.fm, lyrics, MusicBrainz, Spotify genres,
etc.) writes to ``outputs/.cache_*.json`` via plain ``open(path, "w") +
json.dump``. If the process is interrupted mid-write (crash, Ctrl+C, power
loss) the file is truncated and the next scan fails to load it — which
silently means "start fresh", wiping hours of rate-limited enrichment work
that had accumulated in that cache.

This module provides a tiny ``atomic_write_json()`` wrapper used across the
enrichment modules. It writes to ``<path>.tmp`` first, fsyncs, and renames
into place so the target is either fully valid or untouched.
"""

from __future__ import annotations

import json
import os
from typing import Any


def atomic_write_json(
    path: str,
    data: Any,
    *,
    ensure_ascii: bool = False,
    indent: int | None = None,
    separators: tuple[str, str] | None = None,
) -> None:
    """
    Atomically serialise ``data`` as JSON to ``path``.

    Writes to ``<path>.tmp`` first, flushes + fsyncs, then uses ``os.replace``
    (atomic on POSIX; effectively atomic on modern Windows with NTFS) to move
    the temp file over the target. On any exception the temp file is left on
    disk for inspection; the target is never partially overwritten.

    Safe to call with ``ensure_ascii=True`` via kwarg for caches that match
    the json stdlib defaults. The caller's existing ``json.dump(...)`` flags
    are preserved by the keyword-only parameters here.
    """
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp_path = f"{path}.tmp"
    dump_kwargs: dict[str, Any] = {"ensure_ascii": ensure_ascii}
    if indent is not None:
        dump_kwargs["indent"] = indent
    if separators is not None:
        dump_kwargs["separators"] = separators

    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, **dump_kwargs)
        f.flush()
        try:
            os.fsync(f.fileno())
        except OSError:
            # Network filesystems and some containers don't support fsync;
            # os.replace is still atomic enough on all supported platforms.
            pass
    os.replace(tmp_path, path)
