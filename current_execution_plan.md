Objective: Fix session/snapshot hash mismatch by enforcing a single canonical serialisation pathway and using identical bytes for hashing and writing the accepted_master snapshot; correct failure stage reporting; keep downstream verification consistent.

Action [1]:

    FILE: canonical_master.py

    SEARCH: 
    (new file)

    REPLACE:
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

    VERIFICATION: python -m py_compile canonical_master.py

Action [2]:

    FILE: pages/03_Tabletop_Designer.py

    SEARCH:
import logging

    REPLACE:
import logging
from canonical_master import canonical_tabletop_master_bytes, canonical_tabletop_master_sha256
    VERIFICATION: python -m py_compile pages/03_Tabletop_Designer.py

Action [3]:

    FILE: pages/03_Tabletop_Designer.py

    SEARCH:
                                try:
                                    _session_canon = json.dumps(accepted, ensure_ascii=False, sort_keys=True).encode("utf-8")
                                    _session_sha = hashlib.sha256(_session_canon).hexdigest()
                                except Exception:
                                    _session_canon = None
                                    _session_sha = None
                                # Strict atomic write: tmp -> flush -> fsync -> replace (no fallback)
                                with open(tmp_path, "w", encoding="utf-8") as _mf:
                                    json.dump(accepted, _mf, ensure_ascii=False, indent=2, sort_keys=True)
                                    try:
                                        _mf.flush()
                                        os.fsync(_mf.fileno())
                                    except Exception:
                                        pass
                                import os as _os
                                _os.replace(tmp_path, master_path)
                                # Reopen snapshot and compute SHA; verify equality
                                try:
                                    with open(master_path, "rb") as _rf:
                                        _snap_bytes = _rf.read()
                                    _snapshot_sha = hashlib.sha256(_snap_bytes).hexdigest()
                                except Exception:
                                    _snapshot_sha = None

    REPLACE:
                                try:
                                    # Canonical serialisation (session) + SHA using shared function
                                    _canonical_bytes = canonical_tabletop_master_bytes(accepted)
                                    _session_sha = hashlib.sha256(_canonical_bytes).hexdigest()
                                except Exception:
                                    _canonical_bytes = None
                                    _session_sha = None
                                # Strict atomic write with exact canonical bytes: tmp -> flush -> fsync -> replace (no fallback)
                                with open(tmp_path, "wb") as _mf:
                                    if _canonical_bytes is None:
                                        raise RuntimeError("Canonical serialisation failed")
                                    _mf.write(_canonical_bytes)
                                    try:
                                        _mf.flush()
                                        os.fsync(_mf.fileno())
                                    except Exception:
                                        pass
                                import os as _os
                                _os.replace(tmp_path, master_path)
                                # Reopen snapshot and compute SHA; verify equality
                                try:
                                    with open(master_path, "rb") as _rf:
                                        _snap_bytes = _rf.read()
                                    _snapshot_sha = hashlib.sha256(_snap_bytes).hexdigest()
                                except Exception:
                                    _snapshot_sha = None
    VERIFICATION: python -m py_compile pages/03_Tabletop_Designer.py

Action [4]:

    FILE: pages/03_Tabletop_Designer.py

    SEARCH:
                                if not (_session_sha and _snapshot_sha and _session_sha == _snapshot_sha):
                                    st.session_state["tabletop_export_state"] = "failed"
                                    st.session_state["tabletop_export_result"] = {"succeeded": False, "failed_stage": "persist_master", "safe_error_message": "Snapshot hash mismatch"}
                                    raise RuntimeError("Snapshot hash mismatch")

    REPLACE:
                                if not (_session_sha and _snapshot_sha and _session_sha == _snapshot_sha):
                                    st.session_state["tabletop_export_state"] = "failed"
                                    st.session_state["tabletop_export_result"] = {"succeeded": False, "failed_stage": "accepted_master_snapshot", "safe_error_message": "Snapshot hash mismatch"}
                                    raise RuntimeError("Snapshot hash mismatch")
    VERIFICATION: python -m py_compile pages/03_Tabletop_Designer.py

Action [5]:

    FILE: pages/03_Tabletop_Designer.py

    SEARCH:
                    st.session_state["tabletop_export_state"] = "failed"
                    st.session_state["tabletop_export_result"] = {"succeeded": False, "failed_stage": "unexpected_error", "safe_error_message": str(_xe)}

    REPLACE:
                    st.session_state["tabletop_export_state"] = "failed"
                    _prev_stage = (st.session_state.get("tabletop_export_result") or {}).get("failed_stage") or "accepted_master_snapshot"
                    st.session_state["tabletop_export_result"] = {"succeeded": False, "failed_stage": _prev_stage, "safe_error_message": str(_xe)}
    VERIFICATION: python -m py_compile pages/03_Tabletop_Designer.py

Action [6]:

    FILE: production_export.py

    SEARCH:
import tempfile
import shutil
import time
from typing import Optional, Tuple

    REPLACE:
import tempfile
import shutil
import time
from typing import Optional, Tuple
from canonical_master import canonical_tabletop_master_sha256_from_path
    VERIFICATION: python -m py_compile production_export.py

Action [7]:

    FILE: production_export.py

    SEARCH:
        # 1. Validate master path exists; compute master SHA and fingerprint
        if not os.path.exists(tabletop_plan):
            result["failed_stage"] = "validate_master"
            raise RuntimeError("TabletopMasterPlan missing")
        master_sha = _sha256(tabletop_plan)
        result["source_master_sha256"] = master_sha

    REPLACE:
        # 1. Validate master path exists; compute master SHA and fingerprint
        if not os.path.exists(tabletop_plan):
            result["failed_stage"] = "validate_master"
            raise RuntimeError("TabletopMasterPlan missing")
        master_sha = canonical_tabletop_master_sha256_from_path(tabletop_plan) or _sha256(tabletop_plan)
        result["source_master_sha256"] = master_sha
    VERIFICATION: python -m py_compile production_export.py

Action [8]:

    FILE: tests/test_canonical_master_serialisation.py

    SEARCH:
    (new file)

    REPLACE:
    # -*- coding: utf-8 -*-
    import json
    import os
    import tempfile
    import hashlib
    from copy import deepcopy

    from canonical_master import (
        canonical_tabletop_master_bytes,
        canonical_tabletop_master_sha256,
    )

    def test_dict_and_equivalent_model_bytes_and_hashes():
        # Simulate dict vs model_dump
        d = {"b": 2, "a": 1, "nested": {"x": 1, "y": 2}, "arr": [3, 2, 1], "unicode": "Ångström"}
        # "model_dump" equivalent
        m = deepcopy(d)
        b1 = canonical_tabletop_master_bytes(d)
        b2 = canonical_tabletop_master_bytes(m)
        assert b1 == b2
        assert canonical_tabletop_master_sha256(d) == canonical_tabletop_master_sha256(m)

    def test_insertion_order_does_not_change_hash():
        d1 = {"a": 1, "b": 2, "c": {"x": 1, "y": 2}}
        d2 = {"b": 2, "a": 1, "c": {"y": 2, "x": 1}}
        h1 = canonical_tabletop_master_sha256(d1)
        h2 = canonical_tabletop_master_sha256(d2)
        assert h1 == h2

    def test_pretty_vs_canonical_parse_equal_but_hash_differs():
        d = {"a": 1, "b": 2, "nested": {"x": 1}}
        # Pretty JSON
        pretty = json.dumps(d, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8")
        # Canonical JSON
        canon = canonical_tabletop_master_bytes(d)
        assert json.loads(pretty.decode("utf-8")) == json.loads(canon.decode("utf-8"))
        assert hashlib.sha256(pretty).hexdigest() != hashlib.sha256(canon).hexdigest()

    def test_unicode_utf8_stable_hash():
        d = {"title": "Café résumé naïve — £€", "emoji": "🚀"}
        h = canonical_tabletop_master_sha256(d)
        assert isinstance(h, str) and len(h) == 64

    def test_trailing_newline_changes_hash_and_is_not_appended():
        d = {"a": 1}
        b = canonical_tabletop_master_bytes(d)
        bn = b + b"\n"
        assert hashlib.sha256(b).hexdigest() != hashlib.sha256(bn).hexdigest()

    def test_atomic_write_and_reopen_same_hash(tmp_path=None):
        d = {"x": 1, "y": [1, 2, 3]}
        b = canonical_tabletop_master_bytes(d)
        # Write atomically to a temp path and verify hash remains same on reopen
        fd, p = tempfile.mkstemp()
        os.close(fd)
        tmp = p + ".tmp"
        with open(tmp, "wb") as f:
            f.write(b)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, p)
        with open(p, "rb") as f:
            reopened = f.read()
        assert hashlib.sha256(reopened).hexdigest() == hashlib.sha256(b).hexdigest()
        os.remove(p)

    VERIFICATION: pytest -q tests/test_canonical_master_serialisation.py

Action [9]:

    FILE: tests/test_provenance_verification.py

    SEARCH:
    (new file)

    REPLACE:
    # -*- coding: utf-8 -*-
    import json
    from canonical_master import canonical_tabletop_master_bytes, canonical_tabletop_master_sha256

    def test_semantic_roundtrip_parsed_content_matches():
        d = {"a": 1, "b": {"c": [1, 2, 3]}, "unicode": "Δοκιμή"}
        b = canonical_tabletop_master_bytes(d)
        parsed = json.loads(b.decode("utf-8"))
        assert parsed == d
        h1 = canonical_tabletop_master_sha256(d)
        h2 = canonical_tabletop_master_sha256(parsed)
        assert h1 == h2

    VERIFICATION: pytest -q tests/test_provenance_verification.py

Action [10]:

    FILE: tests/test_tabletop_export_ui.py

    SEARCH:
        "source_master_sha256": "deadbeef",

    REPLACE:
        "source_master_sha256": "deadbeef",  # placeholder; verified pathways use on-disk master hash

    VERIFICATION: pytest -q tests/test_tabletop_export_ui.py

Action [11]:

    FILE: current_execution_plan.md

    SEARCH:
Objective:

    REPLACE:
Objective: [This file documents the execution blueprint; no runtime change.]

    VERIFICATION: echo "blueprint ready"

Action [12]:

    FILE: N/A (Static Verification)

    SEARCH:
    (noop)

    REPLACE:
    Run:
      - pytest -q tests/test_canonical_master_serialisation.py tests/test_provenance_verification.py
      - python -m py_compile pages/03_Tabletop_Designer.py tabletop_export_ui.py production_export.py
      - git diff --check

    VERIFICATION: echo "static verification commands listed"