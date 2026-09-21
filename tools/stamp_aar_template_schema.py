#!/usr/bin/env python3
"""
Stamp required AAR template schema marker into a DOCX so export_aar_v2 will render.

It injects an XML comment:
  <!-- template_schema_version: aar_v2_flattened -->

Detection in aar_renderer._detect_template_schema_version() scans all XML files
and uses a regex to find the marker string, so a comment is sufficient.

Usage:
  python3 tools/stamp_aar_template_schema.py planet_it_tabletop_report_template.docx
  # optionally provide an output path:
  python3 tools/stamp_aar_template_schema.py input.docx output.docx
"""
import sys
import zipfile

MARKER = "template_schema_version: aar_v2_flattened"


def _contains_marker(files: dict) -> bool:
    for name, data in files.items():
        if name.endswith(".xml"):
            try:
                if MARKER in data.decode("utf-8", errors="ignore"):
                    return True
            except Exception:
                continue
    return False


def stamp(path_in: str, path_out: str | None = None) -> None:
    if path_out is None:
        path_out = path_in

    with zipfile.ZipFile(path_in, "r") as zin:
        files = {name: zin.read(name) for name in zin.namelist()}

    # No-op if already present
    if _contains_marker(files):
        if path_out != path_in:
            with zipfile.ZipFile(path_out, "w", zipfile.ZIP_DEFLATED) as zout:
                for n, d in files.items():
                    zout.writestr(n, d)
        print("Marker already present")
        return

    target = None
    # Prefer a non-visible metadata file if present
    if "docProps/core.xml" in files:
        target = "docProps/core.xml"
        txt = files[target].decode("utf-8", errors="ignore")
        if "</cp:coreProperties>" in txt:
            new_txt = txt.replace("</cp:coreProperties>", f"<!-- {MARKER} --></cp:coreProperties>")
        else:
            new_txt = txt + f"<!-- {MARKER} -->"
        files[target] = new_txt.encode("utf-8")
    else:
        # Fallback to main document body
        target = "word/document.xml"
        if target not in files:
            raise RuntimeError("word/document.xml not found in DOCX")
        txt = files[target].decode("utf-8", errors="ignore")
        if "</w:document>" in txt:
            new_txt = txt.replace("</w:document>", f"<!-- {MARKER} --></w:document>")
        else:
            new_txt = txt + f"<!-- {MARKER} -->"
        files[target] = new_txt.encode("utf-8")

    with zipfile.ZipFile(path_out, "w", zipfile.ZIP_DEFLATED) as zout:
        for n, d in files.items():
            zout.writestr(n, d)
    print(f"Marker stamped into {target}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        inp = "planet_it_tabletop_report_template.docx"
        out = inp
    else:
        inp = sys.argv[1]
        out = sys.argv[2] if len(sys.argv) > 2 else inp
    stamp(inp, out)