# Email Verification + Cleaning Tools — Research Report

**Date:** 2026-04-12 | **Target:** Nelson Freight CNEE master (~28,170 rows) | **Constraint:** Python, open-source, on-prem preferred

---

## 1. Email Verification Libraries (Top 5)

### 1.1 python-email-validator (JoshData) — RECOMMENDED for syntax
- URL: https://github.com/JoshData/python-email-validator
- Stars: ~1.4k | v2.3.0 (Aug 2025) | MIT | Python 3.8+
- Features: syntax (RFC-compliant), IDN/internationalized, optional MX resolve, friendly errors, display-name parse
- Does NOT do SMTP handshake by design ("nothing to be gained"). Only syntax + MX.
- API:
  ```
  from email_validator import validate_email, EmailNotValidError
  try:
      v = validate_email("info@example.com", check_deliverability=True)
      print(v.normalized, v.domain)
  except EmailNotValidError as e: print(e)
  ```
- Pros: mature, maintained, fast, used by Django/SQLAlchemy/Pydantic ecosystem
- Cons: no SMTP, no disposable, no role-based
- Pricing: free
- Source: https://github.com/JoshData/python-email-validator

### 1.2 py3-validate-email (karolyi / husisusi fork) — RECOMMENDED for SMTP
- URL: https://github.com/husisusi/py3-validate-email (migrated to https://git.ksol.io/karolyi/py3-validate-email)
- Features: regex, MX, SMTP handshake w/ STARTTLS, built-in disposable blacklist (auto-updates every 5 days from martenson/disposable-email-domains)
- API:
  ```
  from validate_email import validate_email
  ok = validate_email(email_address="x@y.com", check_format=True,
                      check_blacklist=True, check_dns=True, check_smtp=True,
                      smtp_timeout=10, smtp_helo_host='my.host.name',
                      smtp_from_address='me@my.host.name')
  ```
- Pros: all-in-one, includes disposable list
- Cons: **MAINTAINER EXPLICITLY WARNS AGAINST BULK USE** — "thousands at once might get your IP blocklisted"
- Pricing: free
- Source: https://github.com/husisusi/py3-validate-email

### 1.3 reacherhq/check-if-email-exists — RECOMMENDED for production bulk
- URL: https://github.com/reacherhq/check-if-email-exists
- Stars: ~4.4k | Rust core + Docker HTTP backend | AGPL-3.0 or commercial
- Features: syntax, MX, SMTP, catch-all detection, disposable, role-based, Yahoo/Hotmail/Gmail heuristics, SOCKS5 proxy support, `/v1/bulk` endpoints, CSV download
- Python integration: HTTP POST to self-hosted Docker container
  ```
  import requests
  r = requests.post("http://localhost:8080/v0/check_email",
                    json={"to_email":"info@example.com"})
  print(r.json()["is_reachable"])  # "safe"|"risky"|"invalid"|"unknown"
  ```
- Pros: best accuracy in class, Docker-ready, bulk v1 API, active dev
- Cons: AGPL license (commercial license needed if Nelson ships SaaS externally), Rust binary not pure Python
- Pricing: self-host free (AGPL); hosted SaaS at reacher.email
- Source: https://github.com/reacherhq/check-if-email-exists

### 1.4 dns-smtp-email-validator (shaileshpandit141)
- URL: https://github.com/shaileshpandit141/dns-smtp-email-validator
- Features: format, MX lookup, SMTP handshake, minimal deps
- Pros: simple single-file
- Cons: low stars, less battle-tested, no disposable/role detection
- Pricing: free

### 1.5 getconversio/email-deep-validator
- URL: https://github.com/getconversio/email-deep-validator
- Features: MX + SMTP, configurable mailbox + domain checks
- Note: **Node.js**, not Python. Mentioned for completeness — skip unless Nelson wants JS pipeline.

**Paid APIs (reference only, not recommended for main pipeline):**
ZeroBounce, NeverBounce, EmailListVerify, Hunter, AbstractAPI. Typical $3–8 per 1,000 emails. Use ONLY for GOLD-tier verification before high-value campaigns.

---

## 2. Bulk Email Cleaning / Normalization

### 2.1 email-normalize (gmr) — RECOMMENDED for canonical form
- URL: https://github.com/gmr/email-normalize | PyPI v2.0.0
- Strips provider quirks: `f.o.o+tag@gmail.com` → `foo@gmail.com`
- Supports Google, Microsoft, Apple, Yahoo, Fastmail, ProtonMail, Rackspace, Yandex, Zoho
- API: `email_normalize.normalize("f.o.o+bar@gmail.com")`
- License: BSD | async-first
- Source: https://github.com/gmr/email-normalize

### 2.2 iDoRecall/email-normalize (alternate, JS)
- URL: https://github.com/iDoRecall/email-normalize
- Note: JS not Python. Skip.

### 2.3 Pandas + regex (for prefix garbage, multi-cell split)
- No dedicated library needed. Standard approach:
  - `df['email'].str.lower().str.strip()`
  - Split multi-email: `df['email'].str.split(r'[;,/|]').explode()`
  - Strip Vietnamese honorific prefixes: `re.sub(r'^\s*(em|anh|chị|te|me|mr|ms|info|contact)[,:\s]+', '', email)` — need custom regex
- Reference: https://www.educative.io/answers/how-to-filter-valid-email-addresses-from-a-series-in-pandas

### 2.4 Typo correction — TheFuzz (rapidfuzz)
- URL: https://github.com/rapidfuzz/RapidFuzz (drop-in for fuzzywuzzy, 10–100× faster, MIT)
- Approach: maintain canonical list `['gmail.com','yahoo.com','hotmail.com','outlook.com',...]`, use `process.extractOne(domain, canonical, score_cutoff=85)` to fix `gmial.com → gmail.com`, `yaho.com → yahoo.com`
- Source: https://medium.com/data-science/how-to-do-fuzzy-matching-in-python-pandas-dataframe-6ce3025834a6

### 2.5 dataprep / clean-text
- `dataprep.clean.clean_email()` — normalize + split, pandas-native. URL: https://github.com/sfu-db/dataprep
- `clean-text` — general-purpose strip. Less email-specific.

---

## 3. Disposable / Role-based / Free-mail Detection

### 3.1 Disposable domain lists
| Repo | Entries | Update freq | Format |
|---|---|---|---|
| **disposable-email-domains/disposable-email-domains** (~3.3k stars) | ~3,500 | Manual, slow | txt/json |
| **disposable/disposable** | ~10k+ | Every 24h auto | txt/json |
| **eramitgupta/disposable-email** | **110,646+** | Daily GH Actions | txt |
| **amieiro/disposable-email-domains** | ~30k | Every 15 min | txt/json |

- **Pick:** `disposable-email-domains/disposable-email-domains` for stability + `amieiro` for freshness. Load as Python set.
- Sources: https://github.com/disposable-email-domains/disposable-email-domains | https://github.com/amieiro/disposable-email-domains | https://github.com/eramitgupta/disposable-email | https://www.usercheck.com/guides/best-github-lists-for-disposable-email-domains

### 3.2 Role-based prefix list
- URL: https://github.com/mixmaxhq/role-based-email-addresses (primary)
- Compiled txt: https://github.com/mbalatsko/role-based-email-addresses-list
- Alternate: https://github.com/tomba-io/generic-emails
- Reserved usernames: https://github.com/forwardemail/reserved-email-addresses-list (~3,223 usernames)
- Common entries: info, sales, support, admin, contact, hello, noreply, no-reply, team, office, marketing, hr, accounting, billing, help, service

### 3.3 Free-mail providers (manual list, stable)
`gmail.com, googlemail.com, yahoo.com, yahoo.co.*, hotmail.com, outlook.com, live.com, msn.com, aol.com, icloud.com, me.com, mac.com, protonmail.com, proton.me, zoho.com, gmx.*, yandex.*, mail.ru, qq.com, 163.com, 126.com, naver.com, daum.net` — ~30 domains, hardcode as set.

---

## 4. Competitor Domain Blocklist (Freight/Logistics)

**Finding:** No public GitHub repo maintains a freight-forwarder competitor blocklist. Nelson must build his own. Search for "nvocc list", "freight forwarder domains" returned zero relevant repos. FMC maintains a licensed NVOCC list at https://www2.fmc.gov/oti/NVOCC.aspx but it is HTML/PDF, not a machine-readable domain list.

**Seed blocklist (YAML, ~50 domains):**
```yaml
competitors:
  # Global top-tier forwarders
  - expeditors.com
  - dhl.com
  - dhl.de
  - kuehne-nagel.com
  - kn-portal.com
  - dbschenker.com
  - schenker.com
  - fedex.com
  - ups.com
  - dsv.com
  - cevalogistics.com
  - yusen-logistics.com
  - nipponexpress.com
  - panalpina.com        # legacy, now DSV
  - agility.com
  - bollore-logistics.com
  - damco.com             # legacy, now Maersk
  - gac.com
  - hellmann.com
  - kintetsu-wel.com
  - sinotrans.com
  - geodis.com
  - xpo.com
  - id-logistics.com
  - dachser.com
  - rhenus.com

  # Ocean carriers (VOCC — not NVOCC but often in scrapes)
  - maersk.com
  - hapag-lloyd.com
  - msc.com
  - cma-cgm.com
  - coscoshipping.com
  - evergreen-line.com
  - yangming.com
  - one-line.com
  - hmm21.com
  - zim.com
  - oocl.com
  - wanhai.com
  - pilship.com

  # US-specific + regional
  - chrobinson.com
  - flexport.com
  - forwardair.com
  - matson.com
  - crowley.com
  - seaboardmarine.com

  # VN-specific competitors (add as discovered)
  - gemadept.com.vn
  - vinafco.com.vn
  - transimexsaigon.com
  - sotrans.com.vn
```

Store at `email_engine/config/competitor_domains.yaml`. Match by `email_domain in competitor_set` or suffix check (`*.dhl.*`).

---

## 5. Recommended Architecture — 3-Stage Pipeline

### Stage A — Offline Clean + Dedup (seconds on 28K rows)
**Tools:** pandas + python-email-validator (syntax-only) + email-normalize + rapidfuzz
**Steps:**
1. Load xlsx → DataFrame
2. Explode multi-email cells (split on `[;,/|]`)
3. Lowercase, strip whitespace
4. Strip Vietnamese honorific prefix via regex (`^(em|anh|chị|te|me|mr|ms|info|contact)[,:\s]+`)
5. Typo-fix domain via rapidfuzz against canonical domain list (cutoff 90)
6. `validate_email(check_deliverability=False)` → `email_syntax_valid` bool
7. `email_normalize.normalize()` → canonical form
8. Dedup on normalized email
- **Est LOC:** ~200 | **Runtime:** <30s

### Stage B — Competitor + Role + Disposable Filter (instant)
**Tools:** YAML blocklist + disposable list + role-based list
**Steps:**
1. Extract `email_domain` from each row
2. Flag `competitor_flag` if domain in YAML
3. Flag `disposable_flag` if domain in disposable set
4. Flag `role_based_flag` if local-part in role prefix set
5. Flag `free_mail_flag` if domain in free-mail set
6. Assign `email_quality_tier`:
   - `EXCLUDE` — competitor_flag OR disposable_flag OR syntax invalid
   - `BRONZE` — role_based OR free_mail
   - `SILVER` — corporate domain, syntax OK, not yet SMTP-checked
   - `GOLD` — corporate + SMTP verified alive (after Stage C)
- **Est LOC:** ~50 | **Runtime:** instant

### Stage C — Online Alive/Dead Verification (hours)
**Tools:** reacherhq/check-if-email-exists Docker container (self-host on VPS)
**Steps:**
1. Deploy Docker: `docker run -p 8080:8080 reacherhq/check-if-email-exists`
2. Filter SILVER tier only (skip EXCLUDE and known BRONZE = lower priority)
3. Async batch POST to `/v0/check_email` with rate limit (e.g. 5 req/sec to avoid IP flag)
4. Parse `is_reachable`: safe → GOLD, risky → keep SILVER, invalid → EXCLUDE
5. Write `email_mx_valid`, `email_smtp_valid`, `last_verified_at` columns
- **Alt:** Use paid API (ZeroBounce) for top 2,000 high-value prospects only (~$10)
- **Est LOC:** ~150 | **Runtime:** 28K × 1s ≈ 8h for full pass; ~1h for SILVER subset

### Output Schema (add to cnee_master_v2.xlsx / Parquet)
```
email_raw              str   (original)
email_clean            str   (lowercase, stripped, prefix removed, typo fixed)
email_normalized       str   (provider-canonical: gmail dots+plus stripped)
email_domain           str
email_syntax_valid     bool
email_mx_valid         bool
email_smtp_valid       bool | None
email_quality_tier     enum  (GOLD|SILVER|BRONZE|EXCLUDE)
competitor_flag        bool
disposable_flag        bool
role_based_flag        bool
free_mail_flag         bool
last_verified_at       datetime
verification_source    str   (reacher|zerobounce|syntax_only)
```

---

## 6. Top 3 Final Picks

| Rank | Repo | Why |
|---|---|---|
| 1 | **reacherhq/check-if-email-exists** | Only OSS tool with production bulk SMTP + catch-all detection. Docker = on-prem friendly. AGPL OK for internal use. 4.4k stars. https://github.com/reacherhq/check-if-email-exists |
| 2 | **JoshData/python-email-validator** | Gold standard syntax + MX check. Zero risk Stage-A baseline. Used by Pydantic ecosystem. MIT. https://github.com/JoshData/python-email-validator |
| 3 | **gmr/email-normalize** | Handles Gmail dots/plus-addressing, Outlook variants → catches duplicates Stage A dedup would miss. BSD. https://github.com/gmr/email-normalize |

Supporting: `disposable-email-domains/disposable-email-domains` + `mixmaxhq/role-based-email-addresses` + `rapidfuzz` for typo fix.

**License summary:** All MIT/BSD except Reacher (AGPL-3.0). AGPL is safe for internal tools — only matters if Nelson SaaS-exposes Reacher to external customers.

**Integration effort:** Stage A ~1 day, Stage B ~0.5 day, Stage C ~1–2 days (incl. Docker deploy + rate-limit tuning). Total ~4 dev days.

---

## 7. Risks + Gotchas

1. **SMTP false positives:** Gmail/Outlook/Yahoo always return 250 OK for any valid-format mailbox (catch-all behavior). Reacher tags these `risky`, not `safe`. Do not auto-EXCLUDE risky.
2. **IP reputation:** Bulk SMTP probing from the same IP that sends email will tank deliverability. Run Reacher from a **separate IP** (VPS, not the Office 365 SMTP sender). Throttle <5 req/sec.
3. **Rate limiting / blocklisting:** Some providers (Yahoo esp.) rate-limit or blocklist aggressive verifiers. Use SOCKS5 proxy rotation if doing full 28K scan.
4. **py3-validate-email warning:** Maintainer says "not for thousands at once." Use Reacher for bulk instead.
5. **Catch-all domains:** ~20% of corporate domains accept all mail. SMTP returns 250 OK for `notarealmailbox@cnee.com`. Cannot distinguish. Tag tier as SILVER not GOLD.
6. **Vietnamese Unicode in emails:** Rare but possible. `python-email-validator` handles IDN (internationalized domain names) but not UTF-8 in local part from broken scrapes. Pre-filter with `email.isascii()` check.
7. **Free APIs daily caps:** Hunter 50/day, ZeroBounce 100 trial. Not viable for 28K bulk.
8. **Competitor list maintenance:** YAML blocklist will drift. Add quarterly review cron or auto-enrich from FMC NVOCC list scrape.
9. **Reacher AGPL:** Modifications must stay open-source. Using as-is via HTTP API is fine.
10. **Disposable list churn:** `eramitgupta/disposable-email` has 110k entries — false positives possible. Start with smaller, curated `disposable-email-domains/disposable-email-domains` (~3.5k entries) and escalate if bounces persist.

---

## 8. Unresolved Questions

1. **Budget for paid verification?** Should Nelson allocate $50–100 for ZeroBounce to verify top 2,000 GOLD prospects before big campaigns?
2. **Where to run Reacher Docker?** VPS (14.225.207.145) has ports 8100/3003 used. Reacher needs outbound port 25 (often blocked by VPS providers — must confirm with host). Laptop VP may be better, but offline at night.
3. **Should multi-email cells produce N rows or keep primary only?** E.g. `info@x.com; sales@x.com` → dedup by domain (keep one) or explode both?
4. **Confidence threshold for typo fix?** rapidfuzz cutoff 85 will fix obvious (gmial→gmail) but may mis-correct rare real domains. Whitelist first?
5. **Does Nelson want to archive EXCLUDE rows or hard-delete?** Recommend archive with tier=EXCLUDE for audit trail.
6. **Retention:** how often to re-verify? Emails rot ~30% per year. Suggest 6-month re-check on GOLD, 3-month on SILVER.
7. **VN competitor domains:** current seed list has ~4 VN forwarders. Does Nelson have internal list to bulk-import?
8. **Integration point:** Should this pipeline run inside `email_engine/` (new `email_engine/verify/`) or as separate `tools/email-cleaner/`?

---

**Status:** DONE
**Summary:** Researched 15+ OSS tools. Recommended 3-stage pipeline (pandas+JoshData → YAML blocklist → Reacher Docker) with ~4 days integration effort. All tools free/OSS, no paid deps required. Top pick: reacherhq/check-if-email-exists for production bulk SMTP.
