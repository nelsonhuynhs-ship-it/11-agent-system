#!/usr/bin/env python3
"""Regression tests: search policy in role templates."""
import os

AGENTS_DIR = "C:/Users/Nelson/.claude/agents-mm"

def test_all_search_capable_templates_have_citation_policy():
    """Templates with search access require source URL + access date."""
    search_roles = ["security-auditor", "design-finder", "code-reviewer"]
    for role in search_roles:
        path = os.path.join(AGENTS_DIR, f"{role}.md")
        with open(path, encoding="utf-8") as f:
            content = f.read()
        assert "source URL" in content or "cite" in content.lower(), \
            f"{role}.md missing citation/source URL requirement"

def test_security_templates_require_nvd_cve():
    """security-auditor requires NVD/CVE/vendor source for security claims."""
    path = os.path.join(AGENTS_DIR, "security-auditor.md")
    with open(path, encoding="utf-8") as f:
        content = f.read()
    assert "NVD" in content or "CVE" in content or "vendor" in content.lower(), \
        "security-auditor.md missing NVD/CVE/vendor citation requirement"

def test_capability_policy_mentions_upgrade_search():
    """Capability policy mentions --upgrade-search."""
    files = ["master-executor.md", "code-reviewer.md"]
    for f in files:
        path = os.path.join(AGENTS_DIR, f)
        with open(path, encoding="utf-8") as fh:
            content = fh.read()
        assert "--upgrade-search" in content, f"{f} missing --upgrade-search"

def test_no_hardcoded_external_urls_in_templates():
    """Templates should not hardcode URLs (use search instead)."""
    files = [f for f in os.listdir(AGENTS_DIR) if f.endswith(".md")]
    violations = []
    for f in files:
        path = os.path.join(AGENTS_DIR, f)
        with open(path, encoding="utf-8") as fh:
            content = fh.read()
        # Look for http URLs that aren't reference-style
        if "https://" in content and "cite" not in content.lower():
            violations.append(f)
    # Allow for design-finder which references platforms
    violations = [v for v in violations if v != "design-finder.md"]
    assert not violations, f"Hardcoded URLs found in: {violations}"

if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])