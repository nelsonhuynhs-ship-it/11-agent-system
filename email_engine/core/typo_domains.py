"""
typo_domains.py — Known-good domain list for typo_shield
=========================================================
Separated from typo_shield.py to keep that file under 200 lines.

To add a legitimate .co or other TLD domain that keeps getting flagged,
call: typo_shield.add_to_known_domains("example.co")
Or add it directly to _CUSTOM_DOMAINS below and redeploy.
"""

# Consumer + major ISP
CONSUMER_DOMAINS = [
    "gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "icloud.com",
    "aol.com", "protonmail.com", "live.com", "msn.com", "ymail.com",
    "me.com", "mac.com", "googlemail.com", "mail.com", "inbox.com",
]

# Major freight / logistics / B2B
LOGISTICS_DOMAINS = [
    "maersk.com", "msc.com", "cma-cgm.com", "evergreen-marine.com",
    "cosco.com", "hapag-lloyd.com", "yang-ming.com", "oocl.com",
    "wanhai.com", "pilship.com", "sinolines.com", "heung-a.com",
    "panalpina.com", "kuehne-nagel.com", "dhl.com", "fedex.com",
    "ups.com", "expeditors.com", "flexport.com", "freightos.com",
    "flexe.com", "echo.com", "coyote.com", "xpo.com", "jbhunt.com",
    "schneider.com", "werner.com", "knight-swift.com", "ryder.com",
    "chrw.com", "radiant.com", "geodis.com", "agility.com",
    "damco.com",
]

# US/Canada importers common in Nelson's prospect list
IMPORTER_DOMAINS = [
    "amazon.com", "walmart.com", "target.com", "costco.com", "ikea.com",
    "wayfair.com", "homedepot.com", "lowes.com", "bestbuy.com",
    "overstock.com", "chewy.com", "etsy.com", "ebay.com",
    "williams-sonoma.com", "potterybarn.com", "crateandbarrel.com",
    "westelm.com", "cb2.com", "pier1.com",
]

# Common business email providers
BUSINESS_DOMAINS = [
    "microsoft.com", "google.com", "apple.com",
    "salesforce.com", "hubspot.com", "mailchimp.com", "zendesk.com",
    "shopify.com", "squarespace.com", "wix.com", "godaddy.com",
    "bluehost.com", "namecheap.com",
]

# Nelson-added legit .co domains (after Nelson-review in Typo UI)
_CUSTOM_DOMAINS: list[str] = []

# Master deduplicated list
TOP_DOMAINS: list[str] = sorted(set(
    CONSUMER_DOMAINS + LOGISTICS_DOMAINS + IMPORTER_DOMAINS + BUSINESS_DOMAINS + _CUSTOM_DOMAINS
))
