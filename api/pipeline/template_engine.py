"""
template_engine.py — Jinja2 email template engine with A/B subject testing.
"""
import os
import random
from pathlib import Path
from typing import Optional

from jinja2 import Environment, FileSystemLoader, select_autoescape

TEMPLATES_DIR = Path(__file__).parent / "templates"

_env = Environment(
    loader=FileSystemLoader([str(TEMPLATES_DIR), str(TEMPLATES_DIR / "cold"),
                             str(TEMPLATES_DIR / "followup"), str(TEMPLATES_DIR / "transactional")]),
    autoescape=select_autoescape(["html"]),
)

# A/B subject line variants per template category
SUBJECT_VARIANTS = {
    "cold": {
        "generic": [
            "{commodity} rates from {pol} — direct carrier contracts",
            "Competitive ocean freight: {pol} → {destination}",
            "{company}, exploring freight options from {pol}?",
            "Quick intro — {commodity} shipping specialist",
        ],
        "rate-focused": [
            "Exclusive {container} rates: {pol} → {pod}",
            "${amount}/container — {pol} to {pod} via {carrier}",
            "Rate alert: {carrier} {pol} → {pod}",
        ],
        "commodity-expert": [
            "{commodity} logistics from {pol} — specialist rates",
            "Your {commodity} shipments — can we help?",
            "{pic}, question about {company}'s {commodity} freight",
        ],
        "volume-discount": [
            "Volume discount available for {company}",
            "VIP rates for high-volume shippers: {pol} → {destination}",
            "{total_shipment}+ containers? Let's talk rates",
        ],
        "referral": [
            "Introduction — ocean freight from {pol}",
            "Recommended to reach out — freight services",
        ],
    },
    "followup": {
        "gentle-reminder": [
            "Following up — {commodity} rates from {pol}",
            "Quick check-in: {company}",
        ],
        "value-add": [
            "Market update — {pol} → US freight rates",
            "Rate trends: {pol} ocean freight this month",
        ],
        "last-chance": [
            "Last follow-up — {company}",
            "Closing the loop on freight rates",
        ],
    },
    "transactional": {
        "quote": [
            "Quotation: {pol} → {pod} | {commodity}",
            "Your freight quote — {pol} to {pod}",
        ],
        "rate-update": [
            "Rate update: {carrier} {pol} → {pod}",
            "Important: {pol} → {pod} rate change",
        ],
    },
}


def render_email(
    category: str,
    template_name: str,
    context: dict,
    subject_variant: int = None,
) -> dict:
    """
    Render an email from template + context.

    Args:
        category: 'cold', 'followup', 'transactional'
        template_name: e.g., 'generic', 'rate-focused', 'quote'
        context: template variables (company, pic, pol, pod, rates, etc.)
        subject_variant: specific A/B variant index, or None for random

    Returns:
        {'subject': str, 'body_html': str, 'template': str, 'variant': int}
    """
    template_file = f"{category}/{template_name}.html.j2"
    tmpl = _env.get_template(template_file)
    body_html = tmpl.render(**context)

    # Select subject line
    variants = SUBJECT_VARIANTS.get(category, {}).get(template_name, [])
    if not variants:
        variants = [f"{category} — {template_name}"]

    if subject_variant is not None and subject_variant < len(variants):
        idx = subject_variant
    else:
        idx = random.randint(0, len(variants) - 1)

    safe_ctx = {k: v for k, v in context.items() if isinstance(v, (str, int, float))}
    subject = variants[idx].format_map(type("D", (), {"__getitem__": lambda s, k: safe_ctx.get(k, ""), "__contains__": lambda s, k: True})())

    return {
        "subject": subject,
        "body_html": body_html,
        "template": f"{category}/{template_name}",
        "variant": idx,
    }


def list_templates() -> dict:
    """List all available templates grouped by category."""
    result = {}
    for category in ["cold", "followup", "transactional"]:
        cat_dir = TEMPLATES_DIR / category
        if cat_dir.exists():
            result[category] = [f.stem for f in cat_dir.glob("*.html.j2")]
    return result


def preview_subjects(category: str, template_name: str, context: dict) -> list[str]:
    """Preview all subject line variants for a template."""
    variants = SUBJECT_VARIANTS.get(category, {}).get(template_name, [])
    return [v.format(**{k: v2 for k, v2 in context.items() if isinstance(v2, (str, int, float))})
            for v in variants]
