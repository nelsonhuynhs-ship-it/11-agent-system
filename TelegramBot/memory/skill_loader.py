# -*- coding: utf-8 -*-
"""
Skill Loader — Dynamic .md skill loading without restart
==========================================================
Reads skill files from .agent/skills/ with content caching.
Skills are hot-reloaded when file hash changes.

Usage:
    from memory.skill_loader import load_skill, list_skills
    content = load_skill("freight-ops")
    all_skills = list_skills()
"""

import hashlib
import time
import logging
from pathlib import Path

log = logging.getLogger(__name__)

# Skill directories to search (ordered by priority)
SKILLS_DIRS = [
    Path(__file__).parent.parent.parent / ".agent" / "skills",
]

_cache: dict = {}  # path → {hash, content, loaded_at}


def _find_skill_path(name: str) -> Path | None:
    """Find a skill file by name across all skill directories."""
    for skills_dir in SKILLS_DIRS:
        if not skills_dir.exists():
            continue
        # Check for exact match
        exact = skills_dir / name / "SKILL.md"
        if exact.exists():
            return exact
        # Check for flat .md
        flat = skills_dir / f"{name}.md"
        if flat.exists():
            return flat
    return None


def load_skill(name: str) -> str | None:
    """
    Load a skill by name. Returns content string or None.
    Uses content hash caching — only re-reads when file changes.
    """
    path = _find_skill_path(name)
    if not path:
        return None

    # Check cache
    h = hashlib.md5(path.read_bytes()).hexdigest()
    if path in _cache and _cache[path]["hash"] == h:
        return _cache[path]["content"]

    # Read and cache
    content = path.read_text(encoding="utf-8")
    _cache[path] = {
        "hash": h,
        "content": content,
        "loaded_at": time.time(),
    }
    log.debug("[SKILL] Loaded: %s (%d bytes)", name, len(content))
    return content


def list_skills() -> list[dict]:
    """
    List all available skills with metadata.
    Returns list of {name, path, size_kb}.
    """
    skills = []
    seen = set()

    for skills_dir in SKILLS_DIRS:
        if not skills_dir.exists():
            continue

        # Folder-based skills (name/SKILL.md)
        for sub in sorted(skills_dir.iterdir()):
            if sub.is_dir() and (sub / "SKILL.md").exists():
                name = sub.name
                if name not in seen:
                    seen.add(name)
                    size = (sub / "SKILL.md").stat().st_size
                    skills.append({
                        "name": name,
                        "path": str(sub / "SKILL.md"),
                        "size_kb": round(size / 1024, 1),
                    })

        # Flat .md skills
        for f in sorted(skills_dir.glob("*.md")):
            name = f.stem
            if name not in seen:
                seen.add(name)
                skills.append({
                    "name": name,
                    "path": str(f),
                    "size_kb": round(f.stat().st_size / 1024, 1),
                })

    return skills


def get_skill_summary(name: str) -> str | None:
    """Get just the description from a skill's YAML frontmatter."""
    content = load_skill(name)
    if not content:
        return None

    # Parse YAML frontmatter
    if content.startswith("---"):
        end = content.find("---", 3)
        if end > 0:
            frontmatter = content[3:end].strip()
            for line in frontmatter.split("\n"):
                if line.startswith("description:"):
                    return line.split(":", 1)[1].strip()

    # Fallback: first non-empty line
    for line in content.split("\n"):
        line = line.strip()
        if line and not line.startswith("#"):
            return line[:200]

    return None
