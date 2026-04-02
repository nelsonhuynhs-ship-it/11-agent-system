# -*- coding: utf-8 -*-
"""
customui_utils.py — Shared utility to ensure customUI14 survives in xlsm files.
================================================================================
openpyxl strips non-standard ZIP entries (_rels/.rels, [Content_Types].xml)
when saving .xlsm files. This module re-injects them after any openpyxl save.

Usage:
    from customui_utils import ensure_customui
    ensure_customui("path/to/ERP_Master.xlsm", "path/to/CustomUI_ERP.xml")
"""
import os
import zipfile


def ensure_customui(xlsm_path, customui_xml_path=None, customui_xml_content=None):
    """
    Ensure customUI14 is properly present in an xlsm file.
    Re-injects customUI XML, _rels/.rels reference, and [Content_Types].xml entry.

    Args:
        xlsm_path: Path to the .xlsm file
        customui_xml_path: Path to CustomUI_ERP.xml file (optional if content provided)
        customui_xml_content: Raw XML string (optional if path provided)

    Returns:
        dict with status of each injection step
    """
    if not os.path.exists(xlsm_path):
        return {"error": f"File not found: {xlsm_path}"}

    # Load customUI XML content
    if customui_xml_content is None:
        if customui_xml_path and os.path.exists(customui_xml_path):
            with open(customui_xml_path, 'r', encoding='utf-8') as f:
                customui_xml_content = f.read()
        else:
            # Try to read from the existing ZIP
            try:
                with zipfile.ZipFile(xlsm_path, 'r') as z:
                    if 'customUI/customUI14.xml' in z.namelist():
                        customui_xml_content = z.read('customUI/customUI14.xml').decode('utf-8')
            except Exception:
                pass

        if customui_xml_content is None:
            return {"error": "No customUI XML source available"}

    # Check current state
    with zipfile.ZipFile(xlsm_path, 'r') as z:
        names = z.namelist()
        rels = z.read('_rels/.rels').decode('utf-8')
        ct = z.read('[Content_Types].xml').decode('utf-8')

    has_file = 'customUI/customUI14.xml' in names
    has_rels = 'customUI' in rels
    has_ct = 'customUI14' in ct or 'customUI/customUI14.xml' in ct

    if has_file and has_rels and has_ct:
        return {"already_ok": True, "file": True, "rels": True, "content_types": True}

    # Rebuild ZIP with all three components
    tmp = xlsm_path + ".customui_tmp"
    with zipfile.ZipFile(xlsm_path, 'r') as zin:
        with zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                data = zin.read(item.filename)

                if item.filename == '_rels/.rels':
                    rels_str = data.decode('utf-8')
                    if 'customUI' not in rels_str:
                        rel_tag = (
                            '<Relationship Id="rId_customUI" '
                            'Type="http://schemas.microsoft.com/office/'
                            '2007/relationships/ui/extensibility" '
                            'Target="customUI/customUI14.xml"/>'
                        )
                        rels_str = rels_str.replace('</Relationships>',
                                                     rel_tag + '</Relationships>')
                    zout.writestr(item, rels_str.encode('utf-8'))

                elif item.filename == '[Content_Types].xml':
                    ct_str = data.decode('utf-8')
                    if 'customUI14' not in ct_str and 'customUI/customUI14.xml' not in ct_str:
                        override = (
                            '<Override PartName="/customUI/customUI14.xml" '
                            'ContentType="application/xml"/>'
                        )
                        ct_str = ct_str.replace('</Types>', override + '</Types>')
                    zout.writestr(item, ct_str.encode('utf-8'))

                elif item.filename == 'customUI/customUI14.xml':
                    # Replace with latest content
                    zout.writestr(item, customui_xml_content.encode('utf-8'))

                else:
                    zout.writestr(item, data)

            # Add customUI file if it doesn't exist yet
            if 'customUI/customUI14.xml' not in names:
                zout.writestr('customUI/customUI14.xml',
                              customui_xml_content.encode('utf-8'))

    os.replace(tmp, xlsm_path)

    return {
        "already_ok": False,
        "file": True,
        "rels": True,
        "content_types": True,
        "injected": True,
    }
