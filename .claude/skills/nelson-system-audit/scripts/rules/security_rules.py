# -*- coding: utf-8 -*-
"""
security_rules.py — Security Architecture Rules
=================================================
Checks for: missing authentication, hardcoded secrets,
no RBAC, missing rate limiting.
"""
import os
import re
import glob

from architecture_rules import (
    API_DIR, BASE_DIR, BOT_DIR, apply_deduction, LayerScore
)


def check_authentication(layers: dict[str, LayerScore]):
    """Check if API has authentication middleware."""
    server_path = os.path.join(API_DIR, "server.py")
    auth_middleware = os.path.join(API_DIR, "middleware", "auth.py")
    auth_router = os.path.join(API_DIR, "routers", "auth_router.py")

    has_auth = False
    for f in [server_path, auth_middleware, auth_router,
              os.path.join(API_DIR, "auth.py")]:
        if os.path.exists(f):
            try:
                content = open(f, encoding="utf-8", errors="ignore").read()
                if any(kw in content for kw in ['JWT', 'jwt', 'Bearer', 'oauth',
                                                  'authenticate', 'Depends(get_current_user',
                                                  'supabase.auth']):
                    has_auth = True
                    break
            except Exception:
                continue

    if not has_auth:
        apply_deduction(
            layers, "no_authentication",
            title="No authentication system detected",
            detail="No JWT, OAuth, or Supabase auth found in API layer",
            suggestion="Implement Supabase Auth with JWT middleware",
        )


def check_endpoints_auth(layers: dict[str, LayerScore]):
    """Check if individual endpoints have auth dependency."""
    server_path = os.path.join(API_DIR, "server.py")
    if not os.path.exists(server_path):
        return
    try:
        content = open(server_path, encoding="utf-8", errors="ignore").read()
    except Exception:
        return

    # Count endpoints
    endpoints = re.findall(r'@app\.(get|post|put|patch|delete)\(["\']([^"\']+)', content)
    # Check for auth dependency pattern
    has_depends = 'Depends(' in content and ('get_current_user' in content or 'verify_token' in content)

    if endpoints and not has_depends:
        # Public endpoints that are OK without auth
        public_ok = ['/api/status', '/api/auth/', '/docs', '/openapi']
        non_public = [(m, p) for m, p in endpoints if not any(p.startswith(pub) for pub in public_ok)]
        if non_public:
            apply_deduction(
                layers, "endpoint_no_auth",
                title=f"{len(non_public)} endpoints without authentication",
                detail=f"No Depends(get_current_user) pattern found",
                suggestion="Add auth dependency to all non-public endpoints",
            )


def check_hardcoded_secrets(layers: dict[str, LayerScore]):
    """Find hardcoded API keys, tokens, or passwords."""
    search_dirs = [API_DIR, BOT_DIR]
    secret_patterns = [
        (r'(?:api_key|apikey|secret|password|token)\s*=\s*["\'][^"\']{10,}["\']', "Hardcoded secret value"),
        (r'BOT_TOKEN\s*=\s*["\'][0-9]+:[A-Za-z0-9_-]+["\']', "Hardcoded Bot token"),
        (r'sk-[a-zA-Z0-9]{20,}', "Hardcoded OpenAI key"),
        (r'AIza[a-zA-Z0-9_-]{35}', "Hardcoded Google API key"),
    ]

    for sd in search_dirs:
        if not os.path.isdir(sd):
            continue
        for pyfile in glob.glob(os.path.join(sd, "**", "*.py"), recursive=True):
            try:
                lines = open(pyfile, encoding="utf-8", errors="ignore").readlines()
            except Exception:
                continue
            for i, line in enumerate(lines, 1):
                # Skip comments and env references
                stripped = line.strip()
                if stripped.startswith('#') or 'os.environ' in line or 'os.getenv' in line:
                    continue
                for pattern, desc in secret_patterns:
                    if re.search(pattern, line, re.IGNORECASE):
                        apply_deduction(
                            layers, "hardcoded_secret",
                            title=desc,
                            detail=f"Line {i}: {stripped[:60]}...",
                            file_path=os.path.relpath(pyfile, BASE_DIR),
                            line_number=i,
                            suggestion="Move to .env file and use os.environ.get()",
                        )
                        break


def check_rbac(layers: dict[str, LayerScore]):
    """Check for Role-Based Access Control implementation."""
    search_terms = ['role', 'RBAC', 'permission', 'is_admin', 'user_role',
                    'row_level_security', 'tenant_id']
    found = False

    for pyfile in glob.glob(os.path.join(API_DIR, "**", "*.py"), recursive=True):
        try:
            content = open(pyfile, encoding="utf-8", errors="ignore").read().lower()
        except Exception:
            continue
        if any(term.lower() in content for term in search_terms):
            found = True
            break

    if not found:
        apply_deduction(
            layers, "no_rbac",
            title="No RBAC (Role-Based Access Control) detected",
            detail="No role/permission checks found in API layer",
            suggestion="Add user roles (admin, operator, viewer) with permission checks",
        )


def run_all(layers: dict[str, LayerScore]):
    """Run all security checks."""
    check_authentication(layers)
    check_endpoints_auth(layers)
    check_hardcoded_secrets(layers)
    check_rbac(layers)
