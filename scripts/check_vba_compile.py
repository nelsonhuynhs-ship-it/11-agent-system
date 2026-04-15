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

  R5  VBA identifiers (Sub/Function/Property/Dim/Const names) MUST NOT
      start with an underscore. VBA raises "Syntax error" at compile
      time. Legal in Python but not VBA. (gotcha #12)

  R6  Identifier names MUST NOT be VBA reserved keywords (Dim, Sub,
      Type, String, Boolean, etc.) — per MS-VBAL spec.

  R7  Identifier names MUST NOT contain `.`, `!`, `@`, `&`, `$`, `#`
      (reserved as type-declaration or member-access chars).

  R8  Every .bas module MUST have `Option Explicit` in the declaration
      section — otherwise undeclared-variable bugs slip past lint.

  R9  `Attribute VB_Name = "X"` MUST match the .bas filename stem;
      mismatch causes silent import rename ("Module1", "ModuleN").

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
# R5 — identifier name starts with underscore (illegal in VBA)
PROC_NAME_LEADING_UNDERSCORE = re.compile(
    r"^\s*(?:Public\s+|Private\s+|Friend\s+)?"
    r"(?:Static\s+)?(?:Sub|Function|Property\s+(?:Get|Let|Set))\s+"
    r"(_[A-Za-z0-9_]*)",
    re.IGNORECASE,
)
VAR_LEADING_UNDERSCORE = re.compile(
    r"^\s*(?:Public|Private|Dim|Const|Static)\s+(_[A-Za-z0-9_]*)\s+As\b",
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

# R6 — identifier cannot be a VBA reserved keyword.
# Source: MS-VBAL spec statement/marker keywords + literals + type idents.
RESERVED_KEYWORDS = {
    # statement keywords
    "call", "case", "close", "const", "declare", "dim", "do", "else",
    "elseif", "end", "endif", "enum", "erase", "event", "exit", "for",
    "friend", "function", "get", "global", "gosub", "goto", "if",
    "implements", "input", "let", "lock", "loop", "lset", "next", "on",
    "open", "option", "print", "private", "public", "put", "raiseevent",
    "redim", "resume", "return", "rset", "seek", "select", "set", "static",
    "stop", "sub", "then", "type", "unlock", "wend", "while", "with", "write",
    # marker/operator keywords
    "addressof", "and", "any", "as", "byref", "byval", "each", "eqv", "imp",
    "in", "is", "like", "mod", "new", "not", "optional", "or", "paramarray",
    "preserve", "shared", "spc", "tab", "to", "until", "withevents", "xor",
    # literal identifiers
    "true", "false", "nothing", "empty", "null", "me",
    # reserved type identifiers
    "boolean", "byte", "currency", "date", "double", "integer", "long",
    "longlong", "longptr", "single", "string", "variant", "object",
}
IDENT_DECL = re.compile(
    r"^\s*(?:Public\s+|Private\s+|Friend\s+|Dim\s+|Const\s+|Static\s+)+"
    # Must skip legal declaration keywords that take a name after them:
    # Sub/Function/Property (procedures), Type/Enum (UDT/enum declarations),
    # Declare/WithEvents. The NAME we want to validate is AFTER these.
    r"(?:(?:Sub|Function|Property\s+(?:Get|Let|Set)|Type|Enum|Declare|WithEvents)\s+)?"
    r"([A-Za-z_][A-Za-z0-9_]*)",
    re.IGNORECASE,
)

# R7 — illegal chars in declared identifier name.
ILLEGAL_NAME_CHARS = re.compile(r"[\.!@#]")

# R9 — VB_Name attribute capture.
VB_NAME = re.compile(r'^\s*Attribute\s+VB_Name\s*=\s*"([^"]+)"', re.IGNORECASE)
OPTION_EXPLICIT = re.compile(r"^\s*Option\s+Explicit\b", re.IGNORECASE)


def lint_file(path: Path) -> list[str]:
    errors: list[str] = []
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()

    # R8 — Option Explicit check (scan declaration-section, first ~40 lines
    # before any procedure — attribute headers + Option rows live here).
    option_explicit_found = False
    for scan_line in lines[:60]:
        if PROC_START.match(scan_line.lstrip()):
            break
        if OPTION_EXPLICIT.match(scan_line):
            option_explicit_found = True
            break
    if not option_explicit_found:
        errors.append(
            f"{path.name}:1 missing 'Option Explicit' in declaration section — "
            f"undeclared variables will not be caught at compile (rule R8)"
        )

    # R9 — VB_Name attribute must match filename stem WHEN stem is a valid
    # VBA identifier. Kebab-case filenames (Nelson's convention) cannot
    # legally be module names — in that case we only require VB_Name to
    # exist and be a valid identifier itself.
    valid_vba_ident = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")
    for scan_line in lines[:10]:
        m_vb = VB_NAME.match(scan_line)
        if m_vb:
            declared = m_vb.group(1)
            stem = path.stem
            if not valid_vba_ident.match(declared):
                errors.append(
                    f"{path.name}:1 Attribute VB_Name={declared!r} is not a "
                    f"valid VBA identifier (rule R9)"
                )
            elif valid_vba_ident.match(stem) and declared.lower() != stem.lower():
                # Both filename AND VB_Name are valid VBA idents — they SHOULD match
                errors.append(
                    f"{path.name}:1 Attribute VB_Name={declared!r} does not match "
                    f"filename stem {stem!r} — VBE will rename on import (rule R9)"
                )
            break

    in_proc = False
    seen_first_proc = False
    proc_stack: list[tuple[str, int]] = []

    for i, line in enumerate(lines, start=1):
        stripped = line.lstrip()

        # R5: leading underscore on procedure or variable name (VBA syntax error)
        m5 = PROC_NAME_LEADING_UNDERSCORE.match(stripped)
        if m5:
            errors.append(
                f"{path.name}:{i} procedure name {m5.group(1)!r} starts with "
                f"underscore — VBA raises 'Syntax error' at compile (gotcha #12). "
                f"Rename without leading underscore."
            )
        m5v = VAR_LEADING_UNDERSCORE.match(stripped)
        if m5v:
            errors.append(
                f"{path.name}:{i} variable name {m5v.group(1)!r} starts with "
                f"underscore — illegal VBA identifier (gotcha #12)."
            )

        # R6/R7: identifier name is reserved keyword or contains illegal chars.
        m_id = IDENT_DECL.match(stripped)
        if m_id:
            name = m_id.group(1)
            if name.lower() in RESERVED_KEYWORDS:
                errors.append(
                    f"{path.name}:{i} identifier {name!r} is a VBA reserved "
                    f"keyword — compiler raises 'Syntax error' (rule R6)"
                )
            if ILLEGAL_NAME_CHARS.search(name):
                errors.append(
                    f"{path.name}:{i} identifier {name!r} contains illegal "
                    f"char (. ! @ #) — reserved for type/member access (rule R7)"
                )

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
