#!/bin/sh
# mm-agent-spawner.sh — Route 11 sub-agents to optimal MiniMax capability
# Approved by Nelson 2026-04-27 — uses FULL Token Plan (text+image+vlm+search+audio).
#
# Args:
#   $1 = role-name (one of 11 supported)
#   $2 = task-string OR @path/to/task.md
#   --out PATH    output report path (default: auto-generated)
#   --notify      after task done, TTS announce via mm-audio.sh
#   --no-template skip role template injection (raw task only)
#
# Capability routing (chốt 2026-04-27 dựa quota check):
#   text-heavy:  code-reviewer, master-executor, test-writer, doc-writer,
#                tech-debt-tracker, git-commit
#   text+search: security-auditor (CVE lookup)
#   vlm:         ux-reviewer, perf-analyzer (đọc screenshot/flame graph)
#   image+search: design-finder (gen mockup + browse Dribbble)
#
# Output: report file path on stdout, exit 0 = OK
# Log: ~/.claude/mm-agent-runs.log

set -u

# ---------- defaults ----------
ROLE=""
TASK=""
OUT=""
NOTIFY=0
NO_TEMPLATE=0
STATUS=""
CWD_OVERRIDE=""
ADD_DIRS=""
APPEND_SYS=""
FEATURE_ID=""
UPGRADE_SEARCH=0
UPGRADE_VLM=0
UPGRADE_IMAGE=0
TRACE_ID=""
REQUESTED_CAPABILITY=""
RESOLVED_EXECUTOR=""
FALLBACK_EXECUTOR=""

AGENTS_DIR="$HOME/.claude/agents-mm"
REPORTS_DIR="$HOME/.claude/agent-reports"
LOG_FILE="$HOME/.claude/mm-agent-runs.log"

MM_CLAUDE="${MM_CLAUDE_OVERRIDE:-$HOME/.claude/bin/mm-claude.sh}"
MM_VLM="${MM_VLM_OVERRIDE:-$HOME/.claude/bin/mm-vlm.sh}"
MM_SEARCH="${MM_SEARCH_OVERRIDE:-$HOME/.claude/bin/mm-search.sh}"
MM_IMAGE="${MM_IMAGE_OVERRIDE:-$HOME/.claude/bin/mm-image.sh}"
MM_AUDIO="${MM_AUDIO_OVERRIDE:-$HOME/.claude/bin/mm-audio.sh}"

mkdir -p "$REPORTS_DIR" "$AGENTS_DIR"

# ---------- arg parse ----------
while [ $# -gt 0 ]; do
  case "$1" in
    --out) OUT="$2"; shift 2 ;;
    --notify) NOTIFY=1; shift ;;
    --no-template) NO_TEMPLATE=1; shift ;;
    --cwd) CWD_OVERRIDE="$2"; shift 2 ;;
    --add-dir) ADD_DIRS="$ADD_DIRS --add-dir \"$2\""; shift 2 ;;
    --append-sys) APPEND_SYS="$2"; shift 2 ;;
    --feature-id) FEATURE_ID="$2"; shift 2 ;;
    --upgrade-search) UPGRADE_SEARCH=1; shift ;;
    --upgrade-vlm) UPGRADE_VLM=1; shift ;;
    --upgrade-image) UPGRADE_IMAGE=1; shift ;;
    -h|--help)
      echo "Usage: $0 <role> <task-or-@file> [options]"
      echo "Options:"
      echo "  --out PATH          output report path (default: auto-generated)"
      echo "  --notify            TTS announce via mm-audio.sh when done"
      echo "  --no-template       skip role template injection (raw task only)"
      echo "  --cwd PATH          override working directory"
      echo "  --upgrade-search    use mm-search.sh (overrides default routing)"
      echo "  --upgrade-vlm       use mm-vlm.sh (overrides default routing)"
      echo "  --upgrade-image     use mm-image.sh (image-gen only, not a text executor)"
      echo "  --feature-id ID     tag run for memory tracking"
      exit 0
      ;;
    *)
      if [ -z "$ROLE" ]; then ROLE="$1"
      elif [ -z "$TASK" ]; then TASK="$1"
      else echo "[spawner] unknown arg: $1" >&2; exit 2
      fi
      shift
      ;;
  esac
done

if [ -z "$ROLE" ] || [ -z "$TASK" ]; then
  echo "[spawner] Usage: $0 <role> <task-or-@file> [--out PATH] [--notify] [--upgrade-search] [--upgrade-vlm] [--upgrade-image]" >&2
  exit 2
fi

# Generate trace ID for observability
TRACE_ID="$(date +%s)-$$"

# Project dir must be resolved early for capability_resolved event
PROJECT_DIR="${CWD_OVERRIDE:-$PWD}"

# ---------- resolve task text (needed for image validation + prompt assembly) ----------
case "$TASK" in
  @*)
    TASK_FILE="${TASK#@}"
    if [ ! -f "$TASK_FILE" ]; then
      echo "[spawner] task file not found: $TASK_FILE" >&2
      exit 2
    fi
    TASK_TEXT=$(cat "$TASK_FILE")
    ;;
  *)
    TASK_TEXT="$TASK"
    ;;
esac

# ---------- capability routing (MUST run before upgrade override) ----------
case "$ROLE" in
  code-reviewer|master-executor|test-writer|doc-writer|tech-debt-tracker|git-commit)
    EXECUTOR="$MM_CLAUDE"
    CAPABILITY="text"
    ;;
  security-auditor)
    EXECUTOR="$MM_SEARCH"
    CAPABILITY="search+text"
    ;;
  ux-reviewer|perf-analyzer)
    EXECUTOR="$MM_VLM"
    CAPABILITY="vlm"
    ;;
  design-finder)
    # Two-step: search inspiration first, then user can call mm-image separately
    EXECUTOR="$MM_SEARCH"
    CAPABILITY="search (image-01 separate call)"
    ;;
  *)
    echo "[spawner] unknown role: $ROLE" >&2
    echo "Supported: code-reviewer, master-executor, test-writer, doc-writer," >&2
    echo "           tech-debt-tracker, git-commit, security-auditor," >&2
    echo "           ux-reviewer, perf-analyzer, design-finder" >&2
    exit 2
    ;;
esac

# ---------- upgrade overrides (run AFTER default routing) ----------
if [ "$UPGRADE_SEARCH" -eq 1 ]; then
  REQUESTED_CAPABILITY="search"
  RESOLVED_EXECUTOR="$MM_SEARCH"
elif [ "$UPGRADE_VLM" -eq 1 ]; then
  REQUESTED_CAPABILITY="vlm"
  RESOLVED_EXECUTOR="$MM_VLM"
elif [ "$UPGRADE_IMAGE" -eq 1 ]; then
  REQUESTED_CAPABILITY="image"
  echo "[spawner] WARNING: --upgrade-image routes to mm-image.sh (image-01, not a text executor)" >&2
  RESOLVED_EXECUTOR="$MM_IMAGE"
  # Validate task is image generation (TASK_TEXT resolved below)
  TASK_LOWER=$(echo "$TASK_TEXT" | tr '[:upper:]' '[:lower:]')
  if ! echo "$TASK_LOWER" | grep -qE 'gen|create image|generate image|draw|画|图'; then
    echo "[spawner] ERROR: --upgrade-image only valid for image generation tasks" >&2
    exit 2
  fi
else
  REQUESTED_CAPABILITY="$CAPABILITY"
  RESOLVED_EXECUTOR="$EXECUTOR"
fi

# Apply upgrade override AFTER default routing
if [ -n "$RESOLVED_EXECUTOR" ] && [ "$RESOLVED_EXECUTOR" != "$EXECUTOR" ]; then
  FALLBACK_EXECUTOR="$EXECUTOR"
  EXECUTOR="$RESOLVED_EXECUTOR"
fi

# Emit capability_resolved event
python ~/.claude/bin/log-spawn.py \
  --role "$ROLE" --capability "$CAPABILITY" --cwd "$PROJECT_DIR" \
  --duration 0 --status "capability_resolved" \
  --trace-id "$TRACE_ID" \
  --requested-capability "$REQUESTED_CAPABILITY" \
  --resolved-executor "$(basename "$EXECUTOR")" \
  --fallback-executor "$(basename "$FALLBACK_EXECUTOR" 2>/dev/null || echo "")" \
  --event-type "capability_resolved" \
  2>/dev/null || true

if [ ! -x "$EXECUTOR" ]; then
  echo "[spawner] executor not found: $EXECUTOR" >&2
  exit 2
fi

# ---------- retry/fallback logic ----------
# Primary executor fails → retry once with fallback → then degrade
RETRY_COUNT=0
MAX_RETRIES=1

# ---------- inject role template ----------
ROLE_TEMPLATE="$AGENTS_DIR/${ROLE}.md"
if [ "$NO_TEMPLATE" -eq 0 ] && [ -f "$ROLE_TEMPLATE" ]; then
  TEMPLATE_TEXT=$(cat "$ROLE_TEMPLATE")
  FULL_PROMPT="$TEMPLATE_TEXT

---

TASK:
$TASK_TEXT"
else
  FULL_PROMPT="$TASK_TEXT"
fi

# ---------- output path ----------
if [ -z "$OUT" ]; then
  TS=$(date +%Y%m%d-%H%M%S)
  OUT="$REPORTS_DIR/${ROLE}-${TS}.md"
fi

# ---------- compose claude CLI flags ----------
CLAUDE_FLAGS=""

if [ -d "$PROJECT_DIR/.claude" ]; then
  CLAUDE_FLAGS="--add-dir \"$PROJECT_DIR\" --setting-sources project,local,user"
  echo "[spawner] project skills detected: $PROJECT_DIR/.claude/" >&2
fi

[ -n "$ADD_DIRS" ] && CLAUDE_FLAGS="$CLAUDE_FLAGS $ADD_DIRS"
[ -n "$APPEND_SYS" ] && CLAUDE_FLAGS="$CLAUDE_FLAGS --append-system-prompt \"$APPEND_SYS\""

# ---------- log start ----------
START_TS=$(date -Iseconds 2>/dev/null || date +'%Y-%m-%dT%H:%M:%S')
START_EPOCH=$(date +%s)
printf '%s | trace=%s | role=%s | capability=%s | requested=%s | resolved=%s | cwd=%s | executor=%s | status=started\n' \
  "$START_TS" "$TRACE_ID" "$ROLE" "$CAPABILITY" "$REQUESTED_CAPABILITY" "$(basename "$EXECUTOR")" "$PROJECT_DIR" "$(basename "$EXECUTOR")" >> "$LOG_FILE"

# ---------- execute ----------
echo "[spawner] role=$ROLE capability=$CAPABILITY executor=$(basename "$EXECUTOR")" >&2
echo "[spawner] output: $OUT" >&2

# write prompt to temp file (avoid arg length limit + safer escaping)
PROMPT_FILE=$(mktemp)
printf '%s\n' "$FULL_PROMPT" > "$PROMPT_FILE"

# cd to project for skill auto-discovery
cd "$PROJECT_DIR" 2>/dev/null || true

# Memory + failure injection (Phase 04-B)
INJECT_TEXT=""
if [ -n "$FEATURE_ID" ] || [ -f "$HOME/.claude/agent-failures.db" ]; then
  INJECT_TEXT=$(python ~/.claude/bin/inject-memory.py \
    --feature-id "$FEATURE_ID" --task-keywords "$ROLE" 2>/dev/null || echo "")
fi
if [ -n "$INJECT_TEXT" ]; then
  CLAUDE_FLAGS="$CLAUDE_FLAGS --append-system-prompt \"$INJECT_TEXT\""
fi

# Phase 04-F: Wiki context auto-inject
WIKI_INDEX="D:/OneDrive/NelsonLifeOS/10-People/mentees/_index.json"
if [ -f "$WIKI_INDEX" ]; then
  TASK_LOWER=$(echo "$TASK_TEXT" | tr '[:upper:]' '[:lower:]')
  WIKI_HITS=""
  for slug in $(python3 -c "import json; print(' '.join(p['slug'] for p in json.load(open(r'$WIKI_INDEX'))['people']))" 2>/dev/null); do
    if echo "$TASK_LOWER" | grep -qw "$slug"; then
      WIKI_FILE="D:/OneDrive/NelsonLifeOS/10-People/mentees/$slug.md"
      if [ -f "$WIKI_FILE" ]; then
        WIKI_HITS="$WIKI_HITS\n## Wiki: $slug\n$(grep -v '<!-- PRIVATE -->' "$WIKI_FILE" | head -50)"
      fi
    fi
  done
  if [ -n "$WIKI_HITS" ]; then
    INJECT_TEXT="${INJECT_TEXT:-}\n$WIKI_HITS"
    CLAUDE_FLAGS="$CLAUDE_FLAGS --append-system-prompt \"$INJECT_TEXT\""
  fi
fi

EXEC_OK=0
SPAWN_EVENT_TYPE="spawn_start"

# Emit spawn_start event via log-spawn.py
python ~/.claude/bin/log-spawn.py \
  --role "$ROLE" --capability "$CAPABILITY" --cwd "$PROJECT_DIR" \
  --duration 0 --status "started" \
  --trace-id "$TRACE_ID" \
  --requested-capability "$REQUESTED_CAPABILITY" \
  --resolved-executor "$(basename "$EXECUTOR")" \
  --fallback-executor "" \
  --event-type "spawn_start" \
  2>/dev/null || true

while [ $RETRY_COUNT -le $MAX_RETRIES ]; do
  if eval "\"$EXECUTOR\" --file \"$PROMPT_FILE\" $CLAUDE_FLAGS" > "$OUT" 2>&1; then
    EXEC_OK=1
    break
  else
    if [ -n "$FALLBACK_EXECUTOR" ] && [ $RETRY_COUNT -eq 0 ]; then
      echo "[spawner] primary executor failed, retrying with fallback: $(basename "$FALLBACK_EXECUTOR")" >&2
      # Emit fallback_used event
      python ~/.claude/bin/log-spawn.py \
        --role "$ROLE" --capability "$CAPABILITY" --cwd "$PROJECT_DIR" \
        --duration 0 --status "fallback_used" \
        --trace-id "$TRACE_ID" \
        --requested-capability "$REQUESTED_CAPABILITY" \
        --resolved-executor "$(basename "$EXECUTOR")" \
        --fallback-executor "$(basename "$FALLBACK_EXECUTOR")" \
        --event-type "fallback_used" \
        2>/dev/null || true
      EXECUTOR="$FALLBACK_EXECUTOR"
      FALLBACK_EXECUTOR=""
      RETRY_COUNT=1
      continue
    else
      if [ -n "$REQUESTED_CAPABILITY" ]; then
        echo "[spawner] DEGRADED: requested_capability=$REQUESTED_CAPABILITY unavailable" >> "$OUT"
        echo "NEEDS VERIFICATION: $REQUESTED_CAPABILITY failed, logged as degraded-mode run" >> "$OUT"
      fi
      EXEC_OK=0
      break
    fi
  fi
done

rm -f "$PROMPT_FILE"

END_TS=$(date -Iseconds 2>/dev/null || date +'%Y-%m-%dT%H:%M:%S')
END_EPOCH=$(date +%s)
DURATION=$((END_EPOCH - START_EPOCH))
if [ $EXEC_OK -eq 1 ]; then
  STATUS="completed"
  # Append to memory file if feature-id set
  if [ -n "$FEATURE_ID" ]; then
    mkdir -p "$HOME/.claude/agent-memory"
    SUMMARY=$(grep -A 3 "^## " "$OUT" 2>/dev/null | head -3 | tr '\n' ' ' | cut -c1-500)
    echo "{\"ts\":\"$END_TS\",\"spawn_n\":$(date +%s),\"role\":\"$ROLE\",\"summary\":\"$SUMMARY\"}" \
      >> "$HOME/.claude/agent-memory/$FEATURE_ID.jsonl" 2>/dev/null || true
  fi
  # Log to SQLite (best-effort, non-blocking)
  python ~/.claude/bin/log-spawn.py \
    --role "$ROLE" --capability "$CAPABILITY" --cwd "$PROJECT_DIR" \
    --duration "$DURATION" --status "$STATUS" \
    --report-path "$OUT" --trace-id "$TRACE_ID" \
    --requested-capability "$REQUESTED_CAPABILITY" \
    --resolved-executor "$(basename "$EXECUTOR")" \
    --fallback-executor "$(basename "$FALLBACK_EXECUTOR" 2>/dev/null || echo "")" \
    --event-type "spawn_complete" \
    2>/dev/null || true
  printf '%s | trace=%s | role=%s | duration=%ds | status=%s | requested=%s | resolved=%s | report=%s\n' \
    "$END_TS" "$TRACE_ID" "$ROLE" "$DURATION" "$STATUS" "$REQUESTED_CAPABILITY" "$(basename "$EXECUTOR")" "$OUT" >> "$LOG_FILE"
  echo "[spawner] DONE in ${DURATION}s — report: $OUT" >&2

  # ---------- optional TTS notify ----------
  if [ "$NOTIFY" -eq 1 ] && [ -x "$MM_AUDIO" ]; then
    NOTIFY_TEXT="Sub agent $ROLE đã xong sau $DURATION giây"
    NOTIFY_OUT="${OUT%.md}-notify.mp3"
    "$MM_AUDIO" --text "$NOTIFY_TEXT" --output "$NOTIFY_OUT" 2>/dev/null || true
    if [ -f "$NOTIFY_OUT" ]; then
      echo "[spawner] notify audio: $NOTIFY_OUT" >&2
    fi
  fi

  echo "$OUT"
  exit 0
else
  STATUS="failed"
  # Log failure to failure DB
  python ~/.claude/bin/log-failure.py --report "$OUT" 2>/dev/null || true
  # Log to SQLite (best-effort, non-blocking)
  python ~/.claude/bin/log-spawn.py \
    --role "$ROLE" --capability "$CAPABILITY" --cwd "$PROJECT_DIR" \
    --duration "$DURATION" --status "$STATUS" \
    --report-path "$OUT" --trace-id "$TRACE_ID" \
    --requested-capability "$REQUESTED_CAPABILITY" \
    --resolved-executor "$(basename "$EXECUTOR")" \
    --fallback-executor "$(basename "$FALLBACK_EXECUTOR" 2>/dev/null || echo "")" \
    --event-type "spawn_failed" \
    --error-class "executor_failed" \
    2>/dev/null || true
  printf '%s | trace=%s | role=%s | duration=%ds | status=%s | degraded=%s\n' \
    "$END_TS" "$TRACE_ID" "$ROLE" "$DURATION" "$STATUS" "true" >> "$LOG_FILE"
  echo "[spawner] FAILED — see $OUT for details" >&2
  echo "$OUT"
  exit 1
fi
