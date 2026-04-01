# File Ownership — Who edits what

## PC Home (primary development)
- webapp/ — all frontend development
- api/ — all backend development
- TelegramBot/ — bot features
- .agent/ — AI agent improvements
- Pricing_Engine/scripts/ — data processing

## Laptop VP (review + lightweight edits)
- .agent/handoff.md — session context
- deploy/ — deploy scripts
- .github/ — CI/CD config
- Bug fixes in any file (small changes only)

## VPS (runtime only — never edit directly)
- Only receives code via git pull
- .env files managed separately
- Parquet data uploaded separately

## Rules
1. ALWAYS `git pull` before starting work
2. Push immediately after editing shared files
3. Merge conflict: `git pull --rebase` (later commit wins)
4. Large features: create branch, merge when done
