# -*- coding: utf-8 -*-
"""
Shared canonical serialisation for Tabletop Master.

This module provides a single source of truth for producing canonical bytes
and SHA-256 for the TabletopMasterPlan. It ensures:
  - stable key order (sort_keys=True)
  - compact separators (",", ":")
  - ensure_ascii=False (UTF-8 unicode retained)
  - allow_nan=False
  - UTF-8 encoding
  - no trailing newline appended
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Optional


def canonical_tabletop_master_bytes(plan: Any) -> bytes:
    """
    Produce canonical bytes for the given plan object.
    If a Pydantic model is passed, callers must pass model_dump(mode="json") as the input.
    """
    # Serialise deterministically
    s = json.dumps(
        plan,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    # Encode using UTF-8; do not append a newline
    return s.encode("utf-8")


def canonical_tabletop_master_sha256(plan: Any) -> str:
    """
    Compute SHA-256 over canonical bytes only.
    """
    b = canonical_tabletop_master_bytes(plan)
    return hashlib.sha256(b).hexdigest()


def canonical_tabletop_master_sha256_from_path(path: str) -> Optional[str]:
    """
    Compute SHA-256 for an on-disk master snapshot by hashing its exact bytes.
    The canonical pipeline ensures files are already canonical; this function
    is provided to unify naming across modules.
    """
    try:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return None