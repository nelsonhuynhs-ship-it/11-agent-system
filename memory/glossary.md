# Glossary — Nelson Freight System
Last updated: 2026-04-01

## Logistics Terms
| Term | Meaning | Context |
|------|---------|---------|
| NVOCC | Non-Vessel Operating Common Carrier | Nelson's business type |
| CNEE | Consignee | Người nhận hàng bên Mỹ/Canada — data trong cnee_master.xlsx |
| POL | Port of Loading | HPH (Hải Phòng), HCM (Hồ Chí Minh) |
| POD | Port of Discharge | USLGB (Long Beach), USLAX (LA), USNYC, CAVAN, USSAV… |
| 40HQ / 40HC | 40ft High Cube container | Most common type |
| 20GP / 20DC | 20ft General Purpose container | |
| HBL | House Bill of Lading | Vận đơn nhà |
| BKG | Booking | Đặt chỗ tàu |
| FWD | Forwarder | Đại lý vận chuyển |
| Coload | Co-loading | Gom hàng nhiều shipper |
| LCH | Lacquer/furniture? | Campaign prefix |
| ETA | Estimated Time of Arrival | |
| ETD | Estimated Time of Departure | |

## Port Codes
| Code | Port | Country |
|------|------|---------|
| HPH | Hải Phòng | Vietnam |
| HCM | Hồ Chí Minh (VICT) | Vietnam |
| USLGB | Long Beach | USA |
| USLAX | Los Angeles | USA |
| USNYC | New York | USA |
| USEWR | Newark | USA |
| USSAV | Savannah | USA |
| USCHS | Charleston | USA |
| USTIW | Tacoma | USA |
| USSEA | Seattle | USA |
| USCHI | Chicago | USA |
| USDAL | Dallas | USA |
| USDEN | Denver | USA |
| CAVAN | Vancouver | Canada |
| CAHAL | Halifax | Canada |

## System Terms
| Term | Meaning |
|------|---------|
| DuckDB | Query engine chạy trực tiếp trên Parquet — 28x faster than Pandas |
| Parquet | Cleaned_Master_History.parquet — ~6.6M rows rate data |
| FreightDB | Class DuckDB engine trong db/duckdb_engine.py |
| Rate & Send | WebApp tool: query giá → preview email → gửi hàng loạt |
| Campaign | Nhóm CNEE theo ngành hàng (CANDLE, FURNITURE…) |
| SEQ / Sequence | Email follow-up sequence — bước 0→1→2→3 |
| SEQ_STEP | Bước hiện tại của prospect trong sequence |
| SEQ_STATUS | ACTIVE / BOUNCED |
| Cooldown | Thời gian chờ tối thiểu giữa 2 lần gửi (default 7 ngày) |
| markup | USD cộng thêm vào giá carrier per container |
| Fallback | Khi 30d không có giá → tự thử 60d → 90d |
| Rate freshness | Độ tươi của giá — bao nhiêu ngày từ Eff đến hôm nay |
| SENTINEL | N.E.L.S.O.N module — giám sát anomaly |
| ORACLE | N.E.L.S.O.N module — dự báo giá |
| Drewry | Index cước tàu quốc tế — dùng để detect anomaly ±15%/30% |
| TraSuaPOS | Phần mềm POS nước trà — port 3000/3001 KHÔNG ĐƯỢC TOUCH |

## Campaigns (cnee_master.xlsx)
| Campaign ID | Ngành hàng | Số prospects |
|-------------|------------|-------------|
| FLOORING | Sàn gỗ/vinyl | 1,057 |
| FURNITURE | Nội thất | 745 |
| PLASTIC | Nhựa | 590 |
| MALAYSIA | Hàng Malaysia | 562 |
| CANDLE | Nến | 495 |
| LCHFURNITURE | Nội thất LCH | 336 |
| PLYWOOD | Ván ép | 312 |
| FOODSTUFF | Thực phẩm | 259 |
| RUBBER | Cao su | 180 |
| FROZEN | Hàng đông lạnh | 111 |
| LCHFOOD | Thực phẩm LCH | 101 |
| GARMENT C.A | Quần áo CA | 95 |
| PLASTIC C.A | Nhựa CA | 84 |
| WOODEN FURNITURE | Nội thất gỗ | 78 |
| TOY | Đồ chơi | 73 |
| STEEL RACK | Kệ thép | 63 |
| GARMENT BANGLADESH | Quần áo BD | 58 |
| SHIPPER MALAYSIA | Shipper Malaysia | 39 |
| POTTERY | Gốm sứ | 28 |
| FURNITURE C.A | Nội thất CA | 18 |
| SEAFOOD | Hải sản | 17 |
| CANNED FOOD | Đồ hộp | 14 |
| LED LIGHT | Đèn LED | 1 |

## Direct Customers (Nelson's own)
| Name | Type | Route | Notes |
|------|------|-------|-------|
| WEST FOOD | DIRECT | HCM-NYC | KEY customer |
| SIRI | FWD | HPH-EL PASO/US | CMA carrier affinity |
| HML | FWD | HPH-DENVER/KANSAS/EL PASO | ONE SOC |
| PANDA | FWD | HCM+HPH-US | ZIM/HPL/ONE — Hà Nội + HCM |
| Nafood | DIRECT | HCM-AUS | MSC, reefer cargo |

→ Full customer list: memory/context/customers.md

## Sprint Codes
| Code | Meaning |
|------|---------|
| S14A | Sprint 14A — Fix rate query fallback + freshness badge |
| S14B | Sprint 14B — Email History + Follow-up Dashboard |
| S14C | Sprint 14C — Price Delta + Smart Compose |
| S14D | Sprint 14D — Bulk Send Intelligence + Cooldown |
| S13 | Sprint 13 — Rate & Send API + WebApp (completed) |

## File Paths (VPS & Local)
| Path | Purpose |
|------|---------|
| email_engine/data/cnee_master.xlsx | 5,316 CNEE prospects |
| email_engine/logs/email_log.csv | Send history (585 rows) |
| email_engine/logs/followup_alerts.csv | Follow-up alerts |
| email_engine/data/customer_rules.json | Direct customer rules |
| api/routers/email_rate_router.py | Rate & Send API |
| webapp/src/app/dashboard/rate-send/page.tsx | Rate & Send UI |
| db/duckdb_engine.py | DuckDB engine |
| Pricing_Engine/data/Cleaned_Master_History.parquet | Rate data |
