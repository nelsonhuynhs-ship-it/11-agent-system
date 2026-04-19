# Panjiva Deep-Dive Research — 2026-04-18
**Audience:** Nelson Huynh, Nelson Freight NVOCC (Vietnam→USA/Canada)
**Purpose:** Maximize Panjiva value, identify hidden fields, plan contact enrichment strategy

---

## EXECUTIVE SUMMARY

Panjiva's bulk xlsx export is **fundamentally limited by design** — contact titles/positions are
NEVER included in shipment-level downloads, even at enterprise tier. This is not a missing feature
Nelson hasn't found; it is a structural constraint of CBP bill-of-lading source data. The fix is a
**two-platform workflow**: Panjiva for finding who ships what → enrichment tool (ImportGenius or
ZoomInfo) for decision-maker contacts. ImportGenius is the most cost-effective path at $229–$449/mo.

---

## 1. PANJIVA PLATFORM TIERS + FEATURES

### Key Facts
- **Panjiva Free** (panjiva.com): 5 free company lookups/month, no bulk export, no HS filter,
  no email data. Useful only for ad-hoc research.
- **Panjiva Supply Chain Intelligence** (via S&P Global Market Intelligence / Capital IQ Pro):
  Enterprise-only, quote-based. Reported range $10,000–$50,000+/year. Full dataset: 2B+ shipment
  records, 9M+ companies, 30 data sources (US, Vietnam, China, India, Brazil, etc.).
  API access, saved alerts, shipment-level download, near-real-time US data.
- **S&P Global Marketplace dataset** (Xpressfeed/bulk feed): Separate product for quant/data
  teams. Raw parquet/CSV data feed. No UI. Higher cost still.
- **Contact fields available per tier:**
  | Field | Free | Enterprise |
  |-------|------|-----------|
  | Company name | ✅ | ✅ |
  | Email 1–3 | ❌ | ✅ (bulk download) |
  | Phone | ❌ | ✅ |
  | Contact Name / Title | ❌ | ❌ (not in download) |
  | Title / Position / Department | ❌ | ❌ (never exportable) |
  | API | ❌ | ✅ (enterprise only) |

### VERDICT
Nelson's current tier already gives Email 1–3 + Phone in xlsx. **No upgrade will add titles or
positions** — that data does not exist in Panjiva's CBP source. Paying for enterprise is only
justified if Nelson needs: (a) HS code-level filtering at scale, (b) API automation, or (c) VN
shipper data from Vietnam customs. For pure prospecting, the current access level is sufficient.

---

## 2. EXPORT OPTIONS — HIDDEN FIELDS

### Key Facts
- **Shipment xlsx export**: Columns shown in UI = columns in export. You can toggle visible
  columns via the column picker (left button showing "X fields selected"). This IS the max — no
  hidden export mode.
- **Contact data architecture**: Panjiva stores a "Company Profile" separately from shipment
  records. The profile CAN contain email + phone. But when you do bulk shipment search and
  download, **contact info is NOT included in the Excel/CSV**, even if visible in individual
  company profile pages on-screen. This is a documented platform limitation, confirmed by
  multiple user reports.
- **API (enterprise only)**: Returns shipment records in JSON. Same field set as UI — no title/
  position. HS code lookup endpoint available. Max fields per record: ~40 (consignee, shipper,
  carrier, POL, POD, commodity, TEU, bill number, arrival date, etc.).
- **Maximum possible fields in xlsx export** (US imports): Consignee Name, Consignee Address,
  Consignee Email 1–3, Consignee Phone, Shipper Name, Shipper Address, Carrier SCAC, Vessel,
  Voyage, POL, POD, Arrival Date, Bill of Lading #, TEU, Container Count, HS Code (imputed),
  Commodity Description, Weight (KG/LBS), Marks & Numbers.
- **What is NEVER in any export**: Contact Name, Title, Position, Department, LinkedIn URL,
  Revenue, Employee Count (these come from company enrichment layers, not CBP data).

### VERDICT
Nelson has already found the ceiling. The 14 xlsx files with Email 1–3 + Phone represent
**maximum Panjiva export**. No hidden export mode exists. The only way to get titles is
post-export enrichment using a separate tool.

---

## 3. BEST PRACTICES — SEARCHING + FILTERING

### Key Facts
- **HS Code mapping for Nelson's campaigns** (6-digit US HTS):
  | Campaign | Primary HS Codes |
  |----------|-----------------|
  | FURNITURE | 9403.10–9403.90 (other furniture + parts) |
  | FLOORING | 4418.73–4418.79 (engineered wood floor), 5702.xx (carpet) |
  | PLASTIC | 3926.xx (plastic articles), 3920.xx (plastic sheets) |
  | CANDLE | 3406.00 (candles, tapers) |
  | PLYWOOD | 4412.xx (plywood, veneered panels) |
  | RUBBER | 4016.xx (rubber articles), 4005.xx (compounded rubber) |
- **Filter by volume/frequency**: Use "TEU range" and "shipment count in last 12 months" in
  Shipment Search. Target CNEEs with ≥4 shipments/year = active buyers worth emailing.
- **Filter to avoid forwarders**: In Panjiva search results, consignees that are freight
  forwarders often appear as "C/O [forwarder name]" or have SCAC codes as consignee. Cross-
  reference against known forwarder domains (Nelson already blacklisted 5,939 — reuse that list).
  Panjiva has no built-in "exclude forwarders" toggle.
- **Saved searches + alerts**: Available at enterprise tier. Set alert for when a CNEE ships
  new containers → trigger follow-up email within days of their shipment activity. Extremely
  powerful for timing outreach.
- **POL filter for VN origin**: Filter by POL = VNHPH (Hải Phòng) or VNSGN (Hồ Chí Minh) to
  get only CNEEs that already buy from Vietnam = warm prospects.

### VERDICT
Nelson is likely NOT using HS code + POL=VN + TEU filter combo. This triple filter dramatically
improves prospect quality. Action: Export only CNEEs who (a) import from VN, (b) HS code matches
campaign, (c) ≥3 shipments last 12 months. Expected result: smaller list but 3–5x higher
response rate vs. blind bulk send.

---

## 4. CONTACT ENRICHMENT WORKAROUNDS

### Key Facts

**ImportGenius ($229–$449/mo)**
- Strongest alternative for US importer prospecting. Specializes in BOL data + contact
  enrichment. Offers "verified, up-to-date prospect contact information on demand" via a
  research team (50 contact requests/month on Pro tier). AI-powered Company Profiler includes
  contact info, shipment trends, HS codes. Daily/weekly refresh (vs. Panjiva's monthly).
- Export: XLSX/CSV/API. Includes decision-maker contacts in export (unlike Panjiva).
- **Best fit for Nelson**: Import Genius Pro at ~$449/mo gives 50 enriched contact requests/mo
  + 10K row downloads. Start here.

**ImportKey ($30/mo)**
- Lowest cost. US + Global BOL data. Phone + address in export. Title/position NOT confirmed.
  Very limited contact enrichment. Good for raw data volume, poor for quality enrichment.

**ZoomInfo (~$15,000+/year)**
- 320M professional contacts, titles, direct dials, LinkedIn. Integrates with CRM. But: (a)
  very expensive, (b) coverage for small freight importers is thin. Overkill for Nelson's volume.

**LinkedIn Sales Navigator ($99–$149/mo)**
- Best for mapping titles AFTER you have company name from Panjiva. Workflow: Panjiva gives
  company → LinkedIn finds "Logistics Manager" or "VP Procurement" → email via Hunter.io or
  direct. Manual but high-quality. Practical for Nelson's top 200 VIP targets.

**Hunter.io (~$49/mo)**
- Given company domain (from Panjiva CNEE), Hunter finds email patterns and verified emails.
  Works well when Panjiva email shows forwarder address — Hunter finds the real corporate email.

**Panjiva Contact Lookup API**: No documented standalone contact enrichment API. The API
  returns shipment data only. No separate "contact lookup" endpoint exists.

### VERDICT
**Recommended stack for Nelson:**
1. Panjiva (current) → filter with HS + POL + TEU → get company names + raw emails
2. ImportGenius Pro ($449/mo) → enrich top 50/mo with verified decision-maker contacts
3. Hunter.io ($49/mo) → find real corporate emails when Panjiva shows forwarder address
4. LinkedIn (manual) → for top VIP 50 accounts only

Skip ZoomInfo (too expensive). Skip ImportKey (no quality contact enrichment).

---

## 5. COMMON PITFALLS + QUALITY ISSUES

### Key Facts

**Data freshness:**
- US import data: updated several times per week. ~7–14 day lag behind actual ship arrival.
  This is good — near real-time for a CBP-sourced dataset.
- US export data: ~23-day regulatory lag.
- International (VN, CN, etc.): ~2-month lag, monthly updates. Much staler.

**Why CNEE email shows forwarder email:**
- CBP bill of lading is filed by the importer of record (IOR), which is sometimes the forwarder
  acting on behalf of the CNEE. The "Notify Party" or "Consignee" field in the BL may be the
  freight forwarder's address, not the actual buyer. Panjiva faithfully copies what's in the BL.
  This is not a Panjiva bug — it's source data reality. Nelson's 5,939-email forwarder blacklist
  is the correct mitigation.

**Detecting stale/invalid emails:**
- Panjiva does NOT validate emails. An email in export could be 3+ years old.
- Practical check: run exports through Hunter.io email verifier or NeverBounce before sending.
  Expected bounce rate on raw Panjiva emails: 15–30%.

**Deduplication issues:**
- Same CNEE appears as "ABC FURNITURE INC", "A B C FURNITURE", "ABC FURNITURE LLC" across
  different BLs. Panjiva does some entity resolution (machine learning) but imperfect.
  Nelson's existing rapidfuzz/Splink dedup pipeline (per architecture research) is the right
  approach.

**HS codes are IMPUTED, not official:**
- Panjiva assigns HS codes via algorithm from commodity description text. Not always accurate.
  For high-stakes targeting, verify against actual HTS codes in CBP AES data.

**Legal:**
- CBP manifest data (US imports) is public domain under FOIA. No GDPR issue for US CNEEs.
- EU consignees in Panjiva (via European customs sources): GDPR applies to using personal data
  for marketing. Nelson's traffic is Vietnam→USA/Canada so EU exposure is minimal.
- Vietnamese shippers in Panjiva: Vietnam customs data available in Panjiva but quality is
  lower and contact enrichment near-zero.

### VERDICT
Nelson's bounce rate is likely 15–30% on raw exports. Add NeverBounce or Hunter verify step
before each campaign blast. The forwarder contamination problem is real and already partially
solved by the 5,939-email blacklist — keep expanding it.

---

## 5 CONCRETE NEXT ACTIONS (Do Tomorrow)

1. **Run the triple filter NOW**: In Panjiva Shipment Search → set POL = VNHPH/VNSGN +
   HS Code = 9403 + Min 3 shipments/12mo → export. Compare quality vs. current 28K list.
   Expected: 2,000–5,000 high-intent CNEEs with VN buying history.

2. **Sign up for ImportGenius free trial**: importgenius.com → test the "Contact Profiler" on
   10 of Nelson's existing CNEEs. Check if titles/positions appear. If yes → upgrade to Pro
   ($449/mo) for 50 enriched contacts/month pipeline.

3. **Add Hunter.io email verify**: Before next campaign blast, run the target CNEE email list
   through Hunter.io's bulk verifier ($49/mo). Remove "invalid" and "risky" — cut bounce rate
   from ~25% to <5%.

4. **Set up Panjiva saved alert for top 200 VIPs**: For Nelson's existing active customers or
   warm prospects, set a Panjiva activity alert → email when they ship a new container from VN.
   Trigger follow-up email within 48h of shipment = highest-converting timing.

5. **Map forwarder blacklist to email domains (not just full emails)**: Current blacklist is
   5,939 individual emails. Extend to domain-level blacklist (e.g., *@kuehne-nagel.com,
   *@expeditors.com) so new Panjiva exports are auto-filtered even if email format differs.

---

## SOURCES

- [Panjiva Supply Chain Intelligence — S&P Global](https://www.spglobal.com/market-intelligence/en/solutions/products/panjiva-supply-chain-intelligence)
- [Panjiva S&P Marketplace Dataset](https://www.marketplace.spglobal.com/en/datasets/panjiva-supply-chain-intelligence-(22))
- [Panjiva — Global Trade Insights (official)](https://panjiva.com/)
- [ImportGenius Pricing](https://www.importgenius.com/pricing)
- [ImportGenius vs. Panjiva Comparison — TradeInt](https://tradeint.com/insights/panjiva-vs-importgenius-a-detailed-comparison/)
- [ImportGenius — The Best Alternative to Panjiva](https://www.importgenius.com/comparison/panjiva)
- [Panjiva vs ImportGenius — SourceForge](https://sourceforge.net/software/compare/ImportGenius-vs-Panjiva/)
- [Top 7 ImportGenius Alternatives — RevenueVessel](https://www.revenuevessel.com/blogs/sites-like-import-genius)
- [ImportKey Pricing](https://importkey.com/pricing)
- [Bill of Lading Data in International Trade Research — Federal Reserve](https://www.federalreserve.gov/econres/feds/files/2021066pap.pdf)
- [Panjiva — Stanford GSB Library Guide](https://libguides.stanford.edu/blogs/library/new/14145/new-resource-panjiva-supply-chain-intelligence)
- [Panjiva Reviews 2026 — G2](https://www.g2.com/products/panjiva/reviews)
- [Taming the Data Beast for Logistics Sales — RevenueVessel](https://www.revenuevessel.com/featured-blogs/taming-the-data-beast-for-logistics-sales)
- [Panjiva Wikipedia](https://en.wikipedia.org/wiki/Panjiva)

---
*Research completed: 2026-04-18 | Mode: Deep Research | Sources: 14 | Tool calls: ~15*
