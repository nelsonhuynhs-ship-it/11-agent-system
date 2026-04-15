"""
Offline VBA structural lint — catches classes of compile errors without
opening Excel.

Rules enforced (each maps to a real regression we've hit):

  R1  Module-level Private/Public variable declarations must come BEFORE
      the first Sub/Function/Property. VBA raises
      "Only comments may appear after End Sub, End Function or End Property"
      when this is violated. (gotcha #11)

  R2  Every Sub/Function must have a matching End Sub/End Function.

  R3  No `Chr(n)` with n > 255 — must be `ChrW(n)` for Unicode.
      (gotcha #1)

  R4  Line continuation `& _` must not be immediately followed by an
      identifier starting with `_` on the next line — VBA concatenates
      to `__X`. (gotcha #2)

Exits 0 on success, 1 on any violation. Run against every .bas in
`D:/OneDrive/NelsonData/erp/`.
"""
from __future__ import annotations

import glob
import os
import re
import sys
from pathlib import Path

BAS_DIR = Path(sys.argv[1] if len(sys.argv) > 1
               else r"D:\OneDrive\NelsonData\erp")

PROC_START = re.compile(
    r"^\s*(Public\s+|Private\s+|Friend\s+)?"
    r"(Static\s+)?(Sub|Function|Property\s+(Get|Let|Set))\b",
    re.IGNORECASE,
)
PROC_END = re.compile(
    r"^\s*End\s+(Sub|Function|Property)\b", re.IGNORECASE
)
MODULE_VAR = re.compile(
    r"^\s*(Public|Private|Dim)\s+[A-Za-z_]\w*\s+As\b", re.IGNORECASE
)
MODULE_CONST = re.compile(
    r"^\s*(Public|Private)\s+Const\b", re.IGNORECASE
)
CHR_CALL = re.compile(r"\bChr\s*\(\s*(\d+)\s*\)")
LINE_CONT = re.compile(r"&\s*_\s*$")
UNDERSCORE_ID_START = re.compile(r"^\s*_[A-Za-z]")


def lint_file(path: Path) -> list[str]:
    errors: list[str] = []
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()

    in_proc = False
    seen_first_proc = False
    proc_stack: list[tuple[str, int]] = []

    for i, line in enumerate(lines, start=1):
        stripped = line.lstrip()

        # R2: Sub/Function entry/exit tracking
        if PROC_START.match(stripped):
            # Nested Subs are illegal but let's just track depth
            seen_first_proc = True
            in_proc = True
            proc_stack.append((stripped[:60], i))
            continue

        if PROC_END.match(stripped):
            if not proc_stack:
                errors.append(f"{path.name}:{i} orphan End Sub/Function — no matching open")
            else:
                proc_stack.pop()
            in_proc = bool(proc_stack)
            continue

        # R1: module-level var after first procedure
        if seen_first_proc and not in_proc:
            if MODULE_VAR.match(stripped) or MODULE_CONST.match(stripped):
                errors.append(
                    f"{path.name}:{i} module-level declaration AFTER first "
                    f"procedure — move to top of module (gotcha #11):\n"
                    f"      {stripped.rstrip()[:120]}"
                )

        # R3: Chr(n>255)
        for m in CHR_CALL.finditer(line):
            n = int(m.group(1))
            if n > 255:
                errors.append(
                    f"{path.name}:{i} Chr({n}) must be ChrW({n}) — Unicode "
                    f"escapes (gotcha #1)"
                )

        # R4: line continuation followed by _Ident
        if LINE_CONT.search(line) and i < len(lines):
            nxt = lines[i]  # i is 1-based, next is index i
            if UNDERSCORE_ID_START.match(nxt):
                errors.append(
                    f"{path.name}:{i} line-continuation '& _' followed by "
                    f"underscore identifier at line {i+1} — VBA parses as "
                    f"'__Ident' (gotcha #2). Rename the identifier."
                )

    if proc_stack:
        for name, ln in proc_stack:
            errors.append(f"{path.name}:{ln} unclosed {name!r}")

    return errors


def main() -> int:
    if not BAS_DIR.exists():
        print(f"[FAIL] VBA dir not found: {BAS_DIR}")
        return 1

    bas_files = sorted(Path(p) for p in glob.glob(str(BAS_DIR / "*.bas")))
    if not bas_files:
        print(f"[FAIL] no .bas files under {BAS_DIR}")
        return 1

    total_errors = 0
    for path in bas_files:
        errs = lint_file(path)
        status = "OK" if not errs else f"FAIL ({len(errs)})"
        print(f"  {path.name:<40s} {status}")
        for e in errs:
            print(f"    - {e}")
        total_errors += len(errs)

    print()
    if total_errors:
        print(f"[FAIL] {total_errors} VBA structural issues across "
              f"{len(bas_files)} files")
        return 1
    print(f"VBA_COMPILE_LINT: OK ({len(bas_files)} files)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
