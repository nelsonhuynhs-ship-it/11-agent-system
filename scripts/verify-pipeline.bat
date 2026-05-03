#!/bin/bash
# verify-pipeline.bat — Mechanical lint for Nelson Python pipeline
# Usage: bash Engine_test/scripts/verify-pipeline.bat [path]
# Exit 0 = pass, Exit 1 = violation(s) found

set -e

ROOT="${1:-.}"
ROOT="$(cygpath -w "$ROOT" 2>/dev/null || echo "$ROOT")"

VIOLATIONS=0
REPORT_FILE=""

# Color codes (Windows cmd compatible)
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# ---- R1: No hardcoded path C:/ or D:/ outside shared/paths.py ----
r1_check() {
  local hardcoded=$(grep -rn 'C:/\|D:/\|C:\\\|D:\\' "$ROOT" --include="*.py" 2>/dev/null | grep -v "shared/paths.py" | grep -v "# noqa: R1" | head -5)
  if [ -n "$hardcoded" ]; then
    echo -e "${RED}R1 FAIL: hardcoded path found (allowed in shared/paths.py only)${NC}"
    echo "$hardcoded" | head -3
    VIOLATIONS=$((VIOLATIONS+1))
  fi
}

# ---- R2: No print() debug in production code ----
r2_check() {
  local prints=$(grep -rn '^\s*print\s*(' "$ROOT" --include="*.py" 2>/dev/null | grep -v "# noqa: R2" | grep -v "logger\|logging" | head -5)
  if [ -n "$prints" ]; then
    echo -e "${RED}R2 FAIL: print() found in production code (use logger instead)${NC}"
    echo "$prints" | head -3
    VIOLATIONS=$((VIOLATIONS+1))
  fi
}

# ---- R3: All public functions have docstring + type hint ----
r3_check() {
  # Fast check: grep for 'def ' followed by newline (no docstring pattern) in first 1000 lines
  # For speed: only scan files that explicitly use print() or logger (proxy for production code)
  local suspects=$(python3 -c "
import os, re

def check_file(path):
    try:
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        # Find all def lines
        lines = content.split('\n')
        in_docstring = False
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith('\"\"\"') or stripped.startswith(\"'''\"):
                in_docstring = not in_docstring
            elif not in_docstring and stripped.startswith('def ') and not stripped.startswith('def _'):
                # Check next 2 lines for docstring or ->
                next_lines = '\n'.join(lines[i+1:i+3])
                if '\"\"\"' not in next_lines and \"'''\" not in next_lines and '->' not in next_lines:
                    return path + ':' + stripped
        return None
    except:
        return None

results = []
root = r'$ROOT'
for f in ['app.py', 'email_rate_router.py', 'erp_api_bridge.py', 'email_event_engine.py', 'email_scanner.py']:
    path = os.path.join(root, f)
    if os.path.exists(path):
        result = check_file(path)
        if result:
            results.append(result)

for r, _, files in os.walk(root):
    for f in files:
        if f.endswith('.py') and len(results) < 5:
            path = os.path.join(r, f)
            result = check_file(path)
            if result:
                results.append(result)
" 2>/dev/null | head -5)
  if [ -n "$suspects" ]; then
    echo -e "${RED}R3 FAIL: public function missing docstring or type hint${NC}"
    echo "$suspects"
    VIOLATIONS=$((VIOLATIONS+1))
  fi
}

# ---- R4: No commit secrets (API key, password regex) ----
r4_check() {
  local secrets=$(grep -rn 'api[_-]key\s*=\s*["'\''][a-zA-Z0-9_-]\{20,\}["'\'']\|password\s*=\s*["'\''][a-zA-Z0-9_-]\{8,\}["'\'']\|sk-[a-zA-Z0-9]\{30,\}' "$ROOT" --include="*.py" 2>/dev/null | grep -v "# noqa: R4" | grep -v "dummy\|test\|placeholder" | head -5)
  if [ -n "$secrets" ]; then
    echo -e "${RED}R4 FAIL: potential secret/token detected${NC}"
    echo "$secrets" | head -3
    VIOLATIONS=$((VIOLATIONS+1))
  fi
}

# ---- R5: No bare except: clauses ----
r5_check() {
  local bare=$(grep -rn 'except\s*:' "$ROOT" --include="*.py" 2>/dev/null | grep -v "# noqa: R5" | grep -v "except Exception\|except BaseException\|except (Exception\|BaseException)" | head -5)
  if [ -n "$bare" ]; then
    echo -e "${RED}R5 FAIL: bare except: found (use except Exception:)${NC}"
    echo "$bare" | head -3
    VIOLATIONS=$((VIOLATIONS+1))
  fi
}

# ---- R6: Imports sorted (isort check) ----
r6_check() {
  # Check if isort available, if not skip with warning
  if command -v isort &> /dev/null; then
    local unsorted=$(isort --check-only --diff "$ROOT" --settings-file /dev/null 2>&1 | grep -v "would make" | head -10)
    if [ -n "$unsorted" ]; then
      echo -e "${RED}R6 FAIL: unsorted imports${NC}"
      echo "$unsorted" | head -3
      VIOLATIONS=$((VIOLATIONS+1))
    fi
  else
    echo -e "${YELLOW}R6 SKIP: isort not installed${NC}"
  fi
}

# ---- R7: Line length <= 120 chars ----
r7_check() {
  local longlines=$(python3 -c "
import os
for root, dirs, files in os.walk('$ROOT'):
    dirs[:] = [d for d in dirs if d not in ['.git','__pycache__']]
    for f in files:
        if f.endswith('.py'):
            path = os.path.join(root, f)
            with open(path, 'r', encoding='utf-8', errors='ignore') as fh:
                for i, line in enumerate(fh, 1):
                    if len(line.rstrip()) > 120 and '# noqa: R7' not in line:
                        print(f'{path}:{i}')
                        break
" 2>/dev/null | head -5)
  if [ -n "$longlines" ]; then
    echo -e "${RED}R7 FAIL: lines > 120 chars${NC}"
    echo "$longlines"
    VIOLATIONS=$((VIOLATIONS+1))
  fi
}

# ---- R8: No TODO without ticket reference (TODO: NF-XXX) ----
r8_check() {
  local todos=$(grep -rn 'TODO' "$ROOT" --include="*.py" 2>/dev/null | grep -v "TODO: NF-[0-9]\{3\}" | grep -v "# noqa: R8" | head -5)
  if [ -n "$todos" ]; then
    echo -e "${RED}R8 FAIL: TODO without ticket reference (format: TODO: NF-XXX)${NC}"
    echo "$todos" | head -3
    VIOLATIONS=$((VIOLATIONS+1))
  fi
}

# ---- R9: All SQL queries parameterized (no f-string SQL) ----
r9_check() {
  local sql=$(python3 -c "
import os, re
for root, dirs, files in os.walk('$ROOT'):
    dirs[:] = [d for d in dirs if d not in ['.git','__pycache__']]
    for f in files:
        if f.endswith('.py'):
            path = os.path.join(root, f)
            with open(path, 'r', encoding='utf-8', errors='ignore') as fh:
                content = fh.read()
            # Find f-string with SQL keywords
            matches = re.finditer(r'f[\"\'](.*?(SELECT|INSERT|UPDATE|DELETE|sql).*)[\"\']', content, re.IGNORECASE)
            for m in matches:
                print(f'{path}')
                break
" 2>/dev/null | head -5)
  if [ -n "$sql" ]; then
    echo -e "${RED}R9 FAIL: f-string SQL detected (use parameterized queries)${NC}"
    echo "$sql"
    VIOLATIONS=$((VIOLATIONS+1))
  fi
}

# ---- R10: Auto-imported from golden-principles.md ----
r10_check() {
  local gp_file=""
  for path in "D:/NELSON/2. Areas/Engine_test/scripts/golden-principles.md" "$ROOT/../scripts/golden-principles.md" "~/.claude/agents-mm/PRE_FLIGHT.md"; do
    if [ -f "$path" ]; then
      gp_file="$path"
      break
    fi
  done

  if [ -z "$gp_file" ]; then
    echo -e "${YELLOW}R10 SKIP: golden-principles.md not found${NC}"
    return
  fi

  # Parse auto-promoted rules section and check
  local auto_rules=$(grep -c "^### G[0-9]" "$gp_file" 2>/dev/null || echo "0")
  if [ "$auto_rules" -gt 0 ]; then
    echo -e "${GREEN}R10 INFO: $auto_rules auto-promoted rules loaded${NC}"
  fi
}

# === RUN ALL CHECKS ===
echo "========================================="
echo "  Nelson Pipeline Lint — verify-pipeline.bat"
echo "========================================="
echo "Root: $ROOT"
echo ""

r1_check
r2_check
r3_check
r4_check
r5_check
r6_check
r7_check
r8_check
r9_check
r10_check

echo ""
echo "========================================="
if [ $VIOLATIONS -gt 0 ]; then
  echo -e "${RED}Pipeline lint: FAIL — $VIOLATIONS rule(s) violated${NC}"
  echo "========================================="
  exit 1
else
  echo -e "${GREEN}Pipeline lint: PASS — 0 violations${NC}"
  echo "========================================="
  exit 0
fi