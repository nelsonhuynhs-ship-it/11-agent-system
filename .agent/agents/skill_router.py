# ============================================================
#  SKILL ROUTER — Loads relevant skill context before tasks
#  ÉM calls this BEFORE writing code.
#  SOI calls this to know what PASS looks like.
# ============================================================
import os, sys, re, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config

SKILLS_BASE = os.path.join(config.WORKSPACE, ".agent", "skills")
AGENT_SKILLS = os.path.join(os.path.dirname(config.WORKSPACE), ".agent", "skills")

# ── Keyword → skill category mapping ──
SKILL_CATEGORIES = {
    "erp_vba": {
        "keywords": [
            "xlsm", "vba", ".bas", "ribbon", "erp", "active jobs", "crm",
            "quotebuilder", "costbreakdown", "bookingemail", "monthlyreport",
            "crm_sheet", "excel", "openpyxl", "worksheet", "workbook",
        ],
        "skills": ["erp-master", "xlsx"],
    },
    "python_api": {
        "keywords": [
            ".py", "fastapi", "router", "endpoint", "rate_importer",
            "parquet", "pandas", "openpyxl", "python", "script",
        ],
        "skills": ["data-pipeline", "webapp-scalable"],
    },
    "telegram_bot": {
        "keywords": [
            "bot", "telegram", "listener", "webhook", "getupdates",
            "notifier", "message", "bot_v5", "command",
        ],
        "skills": ["bot-v5-dev"],
    },
    "rate_pricing": {
        "keywords": [
            "fak", "scfi", "fix", "hpl", "one", "cosco", "rate", "carrier",
            "puc", "soc", "hdl", "markup", "pricing", "freight", "quote",
        ],
        "skills": ["freight-ops", "data-pipeline"],
    },
    "crm_sop": {
        "keywords": [
            "crm", "sop", "customer", "nafood", "booking", "mt pickup",
            "reefer", "contact", "profile",
        ],
        "skills": ["freight-ops", "erp-master"],
    },
    "build_deploy": {
        "keywords": [
            "build", "ribbon", "promote", "staging", "deploy", "import vba",
            "rebuild", "build_erp",
        ],
        "skills": ["erp-master", "verification-before-completion"],
    },
}


class SkillRouter:
    def __init__(self):
        self._skill_cache = {}

    def route(self, task_description):
        """
        Route a task to the best matching skills.
        Returns dict with skills, content, guard_rules, examples.
        """
        matches = self._keyword_match(task_description)

        if not matches:
            matches = self._fallback_classify(task_description)

        content = self._load_skill_content(matches)
        guard_rules = self._extract_guard_rules(content)
        examples = self._extract_examples(content)

        return {
            "skills": matches,
            "content": content,
            "guard_rules": guard_rules,
            "examples": examples,
        }

    def _keyword_match(self, task_desc):
        """Tier 1: keyword match across categories."""
        desc_lower = task_desc.lower()
        matched_skills = set()

        for category, info in SKILL_CATEGORIES.items():
            for kw in info["keywords"]:
                if kw in desc_lower:
                    for skill in info["skills"]:
                        matched_skills.add(skill)
                    break  # one keyword match per category is enough

        return list(matched_skills)

    def _fallback_classify(self, task_desc):
        """Tier 2: return general skills if no keyword match."""
        return ["systematic-debugging", "verification-before-completion"]

    def scan_skill_files(self):
        """Scan all available SKILL.md files."""
        paths = []
        # Check both possible skill locations
        for base in [SKILLS_BASE, AGENT_SKILLS]:
            if os.path.isdir(base):
                for skill_dir in os.listdir(base):
                    skill_md = os.path.join(base, skill_dir, "SKILL.md")
                    if os.path.exists(skill_md):
                        paths.append((skill_dir, skill_md))
        return paths

    def _load_skill_content(self, skill_names):
        """Load SKILL.md content for matched skills."""
        content_parts = []
        all_skills = self.scan_skill_files()

        for skill_name in skill_names:
            # Check cache
            if skill_name in self._skill_cache:
                content_parts.append(self._skill_cache[skill_name])
                continue

            # Find matching skill file
            for name, path in all_skills:
                if name == skill_name:
                    try:
                        with open(path, "r", encoding="utf-8") as f:
                            text = f.read()
                        # Cache first 2000 chars to avoid memory issues
                        truncated = text[:2000]
                        self._skill_cache[skill_name] = truncated
                        content_parts.append(truncated)
                    except Exception as e:
                        content_parts.append(f"[SKILL {skill_name}: load error: {e}]")
                    break

        return "\n---\n".join(content_parts) if content_parts else ""

    def _extract_guard_rules(self, content):
        """Extract guard rules from skill content."""
        rules = []
        for line in content.split("\n"):
            line_lower = line.lower().strip()
            if any(kw in line_lower for kw in ["never", "must not", "do not", "forbidden",
                                                "khong", "không", "cấm"]):
                rules.append(line.strip())
        return rules[:10]  # Cap at 10

    def _extract_examples(self, content):
        """Extract example patterns from skill content."""
        examples = []
        in_example = False
        buf = []
        for line in content.split("\n"):
            if "example" in line.lower() or "```" in line:
                in_example = not in_example
                if not in_example and buf:
                    examples.append("\n".join(buf))
                    buf = []
            elif in_example:
                buf.append(line)
        return examples[:5]  # Cap at 5


# Singleton
router = SkillRouter()


def route(task_description):
    """Convenience function."""
    return router.route(task_description)
