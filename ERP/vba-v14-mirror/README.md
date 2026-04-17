# ERP v14 VBA Mirror — Backup Only

**⚠ NOT THE SOURCE OF TRUTH.** Canonical files live in `D:/OneDrive/NelsonData/erp/`.

This folder mirrors those files into git so:
- Peer-reviewable changes via PR
- Restore if OneDrive sync conflict destroys a module
- Version history beyond OneDrive's limited recovery

**Rules:**
- DO NOT edit `.bas` files here and expect them to land in Excel.
- Edit in OneDrive → run `scripts/reimport-erp-vba-modules.py` → test → copy back to mirror → commit.
- Standards: `docs/ERP_V14_VBA_STANDARDS.md` (WMI launch pattern, etc.)

**Sync command** (run after any VBA change):
```bash
cp "D:/OneDrive/NelsonData/erp/"*.bas "ERP/vba-v14-mirror/"
cp "D:/OneDrive/NelsonData/erp/CustomUI_v14.xml" "ERP/vba-v14-mirror/"
cp "D:/OneDrive/NelsonData/erp/refresh-v14.py" "ERP/vba-v14-mirror/"
```
