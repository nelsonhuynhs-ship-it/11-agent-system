# -*- coding: utf-8 -*-
"""
customui_utils.py — Inject CustomUI14 ribbon XML into .xlsm (ZIP) file.

openpyxl strips the customUI folder on save, so refresh-v14.py calls this
after writing data to re-inject the ribbon XML and restore the ribbon tabs.

Usage:
    from customui_utils import ensure_customui
    result = ensure_customui("path/to/ERP.xlsm", customui_xml_path="CustomUI_v14.xml")
    # result: {"injected": True} | {"already_ok": True} | {"error": str}
"""
import os
import shutil
import zipfile
import tempfile

# Path inside the .xlsm ZIP where ribbon XML lives
_CUSTOMUI_INNER = "customUI/customUI14.xml"
_RELS_INNER     = "_rels/.rels"

# Relationship entry to add to _rels/.rels
_REL_ID   = "rId_customUI14"
_REL_TYPE = "http://schemas.microsoft.com/office/2007/relationships/ui/extensibility"
_REL_TARGET = "customUI/customUI14.xml"

_REL_ENTRY = (
    f'<Relationship Id="{_REL_ID}" '
    f'Type="{_REL_TYPE}" '
    f'Target="{_REL_TARGET}"/>'
)


def ensure_customui(xlsm_path: str, customui_xml_path: str) -> dict:
    """
    Inject CustomUI14 ribbon XML into the .xlsm file if not already present.

    Steps:
    1. Read ribbon XML from customui_xml_path
    2. Check if customUI/customUI14.xml already exists in the xlsm ZIP
    3. If yes → return {"already_ok": True}
    4. If no  → rewrite ZIP adding customUI/customUI14.xml + update _rels/.rels

    Returns:
        {"injected": True}   — ribbon XML was injected successfully
        {"already_ok": True} — ribbon XML already present, no change needed
        {"error": str}       — something went wrong
    """
    if not os.path.exists(xlsm_path):
        return {"error": f"xlsm not found: {xlsm_path}"}
    if not os.path.exists(customui_xml_path):
        return {"error": f"customUI XML not found: {customui_xml_path}"}

    # Read ribbon XML content
    with open(customui_xml_path, "r", encoding="utf-8") as f:
        customui_content = f.read()

    try:
        # ── Check if already injected (BOTH file AND relationship must exist) ──
        with zipfile.ZipFile(xlsm_path, "r") as z:
            existing_names = set(z.namelist())
            has_xml = _CUSTOMUI_INNER in existing_names
            has_rel = False
            xml_matches = False
            if _RELS_INNER in existing_names:
                rels_text = z.read(_RELS_INNER).decode("utf-8")
                has_rel = _REL_TARGET in rels_text
            if has_xml:
                existing_xml = z.read(_CUSTOMUI_INNER).decode("utf-8")
                xml_matches = existing_xml == customui_content
            if has_xml and has_rel and xml_matches:
                return {"already_ok": True}

        # ── Inject: rewrite ZIP with customUI added ──────────────────────────
        fd, tmp_path = tempfile.mkstemp(prefix="customui_", suffix=".tmp")
        os.close(fd)
        try:
            with zipfile.ZipFile(xlsm_path, "r") as zin, \
                 zipfile.ZipFile(tmp_path, "w", compression=zipfile.ZIP_DEFLATED) as zout:

                for item in zin.infolist():
                    # Skip old customUI file — we'll write fresh copy below
                    if item.filename == _CUSTOMUI_INNER:
                        continue

                    data = zin.read(item.filename)

                    # Patch _rels/.rels to add relationship entry
                    if item.filename == _RELS_INNER:
                        rels_text = data.decode("utf-8")
                        if _REL_TARGET not in rels_text:
                            # Insert before closing </Relationships>
                            rels_text = rels_text.replace(
                                "</Relationships>",
                                f"  {_REL_ENTRY}\n</Relationships>",
                            )
                        data = rels_text.encode("utf-8")

                    zout.writestr(item, data)

                # Add the customUI14 XML file
                zout.writestr(_CUSTOMUI_INNER, customui_content.encode("utf-8"))

            # Replace original with patched version
            shutil.copyfile(tmp_path, xlsm_path)
            os.remove(tmp_path)

            # ── Post-inject verification (BELT+SUSPENDERS) ─────────────────
            # Bug history: 21/04 refresh produced xlsm with customUI file but
            # rels relationship missing → ribbon 2 tabs disappeared in Excel.
            # Verify BOTH components present, force-patch if rels still missing.
            verify = _verify_customui_integrity(xlsm_path, customui_content)
            if not verify["ok"]:
                patch = _force_patch_rels(xlsm_path)
                if not patch["ok"]:
                    return {"error": f"Verify fail after inject: {verify['issue']} | patch fail: {patch.get('error')}"}
                return {"injected": True, "force_patched_rels": True}

            return {"injected": True}

        except Exception as e:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            return {"error": str(e)}

    except zipfile.BadZipFile as e:
        return {"error": f"Not a valid zip/xlsm file: {e}"}
    except Exception as e:
        return {"error": str(e)}


def _verify_customui_integrity(xlsm_path: str, expected_xml: str) -> dict:
    """Verify BOTH customUI/customUI14.xml AND rels entry present + correct."""
    try:
        with zipfile.ZipFile(xlsm_path, "r") as z:
            names = set(z.namelist())
            if _CUSTOMUI_INNER not in names:
                return {"ok": False, "issue": "customUI14.xml missing"}
            if _RELS_INNER not in names:
                return {"ok": False, "issue": "_rels/.rels missing"}
            xml_body = z.read(_CUSTOMUI_INNER).decode("utf-8")
            rels_body = z.read(_RELS_INNER).decode("utf-8")
            if xml_body != expected_xml:
                return {"ok": False, "issue": "customUI14.xml content mismatch"}
            if _REL_TARGET not in rels_body:
                return {"ok": False, "issue": "rels missing customUI relationship"}
            return {"ok": True}
    except Exception as e:
        return {"ok": False, "issue": f"verify error: {e}"}


def _force_patch_rels(xlsm_path: str) -> dict:
    """Force-inject customUI relationship into _rels/.rels if missing."""
    try:
        fd, tmp_path = tempfile.mkstemp(prefix="relsfix_", suffix=".tmp")
        os.close(fd)
        with zipfile.ZipFile(xlsm_path, "r") as zin, \
             zipfile.ZipFile(tmp_path, "w", compression=zipfile.ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                data = zin.read(item.filename)
                if item.filename == _RELS_INNER:
                    txt = data.decode("utf-8")
                    if _REL_TARGET not in txt:
                        if "</Relationships>" in txt:
                            txt = txt.replace(
                                "</Relationships>",
                                f"{_REL_ENTRY}</Relationships>",
                            )
                            data = txt.encode("utf-8")
                        else:
                            return {"ok": False, "error": "rels missing </Relationships> tag"}
                zout.writestr(item, data)
        shutil.copyfile(tmp_path, xlsm_path)
        os.remove(tmp_path)
        return {"ok": True}
    except Exception as e:
        if "tmp_path" in dir() and os.path.exists(tmp_path):
            os.remove(tmp_path)
        return {"ok": False, "error": str(e)}


# ── CLI quick-test ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        print("Usage: python customui_utils.py <file.xlsm> <CustomUI_v14.xml>")
        sys.exit(1)
    result = ensure_customui(sys.argv[1], sys.argv[2])
    print("Result:", result)
