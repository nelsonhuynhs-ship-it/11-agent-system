# -*- coding: utf-8 -*-
"""
build-skill-zips.py — Bulk zip builder for GoClaw Lite skill uploads.

Creates flat zips (SKILL.md at root, subfolders preserved) from
.claude/skills/{name}/ source folders. Matches format of existing
Fox Spirit skill zips (e.g. freight-ops-flat.zip).

Usage:
    python build-skill-zips.py              # Build all target skills
    python build-skill-zips.py devops gkg   # Build specific skills only
    python build-skill-zips.py --force      # Overwrite existing zips

Output: D:/GoClaw-skills-zips/{skill}-flat.zip
"""
import argparse
import sys
import zipfile
from pathlib import Path

SKILLS_SRC = Path(r"D:/NELSON/2. Areas/Engine_test/.claude/skills")
ZIPS_OUT = Path(r"D:/GoClaw-skills-zips")

# Target skill list — 22 skills for 3 sub-agents.
# Some overlap with Fox Spirit's existing zips (verification-before-completion,
# freight-ops) so they can be re-granted without re-zipping.
TARGET_SKILLS = [
    # WATCHDOG (6): infrastructure, deploy, security
    "devops",
    "deploy",
    "security-scan",
    "gkg",
    "verification-before-completion",
    "systematic-debugging",
    # OPS-ENGINE (8): data pipeline, backend, APIs
    "databases",
    "data-pipeline",
    "backend-development",
    "panjiva-data-pull",
    "email-intelligence",
    "repomix",
    "research",
    "mcp-builder",
    # SALES-OPS (8): frontend, UX, business
    "next-best-practices",
    "react-best-practices",
    "ui-styling",
    "ui-ux-pro-max",
    "web-design-guidelines",
    "frontend-development",
    "copywriting",
    "freight-ops",
]

# Patterns to exclude from zips (bloat or OS artifacts)
EXCLUDE_DIRS = {
    "__pycache__", ".git", "node_modules", ".venv", "venv",
    ".pytest_cache", ".mypy_cache",
    # scripts/ folders contain Python helpers that Gemma agents can't usefully
    # execute in GoClaw Lite, and often declare pytest/win_compat imports that
    # trigger GoClaw's pip auto-install scanner causing "Missing deps" errors.
    # The knowledge value lives in SKILL.md + references/*.md.
    "scripts",
}
EXCLUDE_SUFFIXES = {".pyc", ".pyo", ".swp", ".DS_Store", ".coverage"}

# Skill-specific exclusions — large asset dirs not needed by Gemma agents
SKILL_EXCLUDE_PATHS = {
    "ui-styling": ["canvas-fonts"],  # 5.6MB fonts, not used by LLM agent
}


def should_exclude(rel_path: Path, skill: str) -> bool:
    """Return True if this path should be excluded from the zip."""
    parts = rel_path.parts
    if any(p in EXCLUDE_DIRS for p in parts):
        return True
    if rel_path.suffix in EXCLUDE_SUFFIXES:
        return True
    # Skill-specific excludes
    for excluded in SKILL_EXCLUDE_PATHS.get(skill, []):
        if parts and parts[0] == excluded:
            return True
    return False


def build_zip(skill: str, force: bool = False) -> tuple[bool, str]:
    """Build flat zip for a single skill. Returns (success, message)."""
    src_dir = SKILLS_SRC / skill
    if not src_dir.is_dir():
        return False, f"Source folder missing: {src_dir}"

    skill_md = src_dir / "SKILL.md"
    if not skill_md.exists():
        return False, f"SKILL.md missing in {src_dir}"

    out_path = ZIPS_OUT / f"{skill}-flat.zip"
    if out_path.exists() and not force:
        return True, f"EXISTS  {out_path.name} ({out_path.stat().st_size // 1024} KB) — use --force to rebuild"

    ZIPS_OUT.mkdir(parents=True, exist_ok=True)

    file_count = 0
    total_bytes = 0
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for file_path in sorted(src_dir.rglob("*")):
            if not file_path.is_file():
                continue
            rel_path = file_path.relative_to(src_dir)
            if should_exclude(rel_path, skill):
                continue
            # Use forward slashes in archive names (ZIP spec standard,
            # matches existing Fox Spirit zip format). zipfile normalizes
            # Windows backslashes automatically but we do it explicitly for clarity.
            arc_name = rel_path.as_posix()
            zf.write(file_path, arcname=arc_name)
            file_count += 1
            total_bytes += file_path.stat().st_size

    size_kb = out_path.stat().st_size // 1024
    return True, f"BUILT   {out_path.name} ({file_count} files, {size_kb} KB zipped, {total_bytes // 1024} KB raw)"


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass

    parser = argparse.ArgumentParser(description="Build skill zips for GoClaw Lite")
    parser.add_argument("skills", nargs="*", help="Specific skill names (default: all targets)")
    parser.add_argument("--force", action="store_true", help="Overwrite existing zips")
    args = parser.parse_args()

    skills = args.skills or TARGET_SKILLS

    print(f"Building {len(skills)} skill zips → {ZIPS_OUT}\n")

    ok = 0
    fail = 0
    for skill in skills:
        success, msg = build_zip(skill, force=args.force)
        tag = "✓" if success else "✗"
        print(f"  {tag} {skill}: {msg}")
        if success:
            ok += 1
        else:
            fail += 1

    print(f"\n{ok} built/exists, {fail} failed.")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
