import { useState } from "react";

const flows = {
  checkPricing: {
    id: "checkPricing",
    label: "CHECK PRICING",
    color: "#38bdf8",
    steps: [
      {
        id: "input",
        title: "Input",
        icon: "⌨️",
        items: ["POL (HCM / HPH / DAD)", "POD (LAX / NYC / SEA...)", "Carrier (HPL / ONE / MSC...)", "Container (20DC / 40HC)", "Rate type (FAK / SCFI / FIX)"],
      },
      {
        id: "api",
        title: "FastAPI xử lý",
        icon: "⚙️",
        highlight: true,
        items: [
          "POST /api/pricing/check",
          "→ Query Parquet (last 30 days)",
          "→ Filter by POL + POD + carrier",
          "→ Apply HDL fee rules",
          "→ Return rate breakdown",
        ],
      },
      {
        id: "output",
        title: "Kết quả trả về",
        icon: "📦",
        items: ["Rate (FAK/SCFI/FIX)", "HDL fee theo carrier", "Validity date", "SOC/COC/PUC flag", "Surcharges nếu có"],
      },
      {
        id: "display",
        title: "Hiển thị",
        icon: "🖥️",
        split: true,
        platforms: [
          { name: "Telegram", icon: "✈️", desc: "Bot nhắn text\nHPL FAK 20DC\nHCM→LAX: $1,875" },
          { name: "WebApp", icon: "🌐", desc: "Bảng so sánh\ncarrier, giá thấp→cao" },
          { name: "ERP Excel", icon: "📊", desc: "Paste vào cell\nRibbon trigger" },
        ],
      },
    ],
  },
  quoteBuilder: {
    id: "quoteBuilder",
    label: "QUOTE BUILDER",
    color: "#a78bfa",
    steps: [
      {
        id: "input",
        title: "Input từ Check Pricing +",
        icon: "➕",
        items: ["Kết quả rate đã có sẵn", "Customer segment (BCO / Agent...)", "Margin % hoặc fixed", "Surcharge bổ sung nếu có", "Valid until (ETD window)"],
      },
      {
        id: "api",
        title: "FastAPI xử lý",
        icon: "⚙️",
        highlight: true,
        items: [
          "POST /api/quote/build",
          "→ Buying = rate + HDL fee",
          "→ Selling = buying + margin",
          "→ Profit = selling - buying",
          "→ Build cost breakdown (AJ format)",
          "→ Generate quote summary",
        ],
      },
      {
        id: "output",
        title: "Kết quả trả về",
        icon: "📋",
        items: [
          "Buying rate (internal)",
          "Selling rate (gửi KH)",
          "Cost breakdown (AJ column)",
          "S/C|COST|HDL FEE CAR COM",
          "Quote ID + timestamp",
        ],
      },
      {
        id: "display",
        title: "Hiển thị",
        icon: "🖥️",
        split: true,
        platforms: [
          { name: "Telegram", icon: "✈️", desc: "Bot gửi quote\nđã format sẵn\ngửi KH luôn" },
          { name: "WebApp", icon: "🌐", desc: "Quote card đẹp\n+ nút Copy / Send\n+ lưu lịch sử" },
          { name: "ERP Excel", icon: "📊", desc: "Điền AJ column\nCost Breakdown\n+ cột selling" },
        ],
      },
    ],
  },
  activeJob: {
    id: "activeJob",
    label: "QUOTE → ACTIVE JOB",
    color: "#34d399",
    steps: [
      {
        id: "input",
        title: "Trigger: KH xác nhận",
        icon: "✅",
        items: [
          "Quote ID (từ bước trên)",
          "Shipper / Consignee",
          "ETD dự kiến",
          "Volume (20 / 40 / HC)",
          "FAST_JOB_NO (anh nhập từ FAST)",
          "HBL_NO (anh nhập từ FAST)",
        ],
      },
      {
        id: "api",
        title: "FastAPI xử lý",
        icon: "⚙️",
        highlight: true,
        items: [
          "POST /api/job/activate",
          "→ Tạo job record",
          "→ Gán FAST_JOB_NO vào AL",
          "→ Gán HBL_NO vào AN",
          "→ Build booking email (AK)",
          "→ Trigger Telegram notify",
          "→ Update Active Jobs sheet",
        ],
      },
      {
        id: "output",
        title: "Kết quả trả về",
        icon: "🚢",
        items: [
          "Job record đã active",
          "Booking email draft sẵn",
          "Cost breakdown locked",
          "Monthly report ready",
          "Telegram alert gửi anh",
        ],
      },
      {
        id: "display",
        title: "Hiển thị",
        icon: "🖥️",
        split: true,
        platforms: [
          { name: "Telegram", icon: "✈️", desc: "Alert: Job mới\nSE2603/XXXX\nHPL HCM→LAX" },
          { name: "WebApp", icon: "🌐", desc: "Active Jobs tab\nStatus tracking\nP&L per job" },
          { name: "ERP Excel", icon: "📊", desc: "Row mới vào\nActive Jobs\nAJ/AK/AL/AN filled" },
        ],
      },
    ],
  },
};

const flowOrder = ["checkPricing", "quoteBuilder", "activeJob"];

const colors = {
  checkPricing: { main: "#38bdf8", bg: "rgba(56,189,248,0.08)", border: "rgba(56,189,248,0.25)" },
  quoteBuilder: { main: "#a78bfa", bg: "rgba(167,139,250,0.08)", border: "rgba(167,139,250,0.25)" },
  activeJob: { main: "#34d399", bg: "rgba(52,211,153,0.08)", border: "rgba(52,211,153,0.25)" },
};

export default function App() {
  const [active, setActive] = useState("checkPricing");
  const flow = flows[active];
  const c = colors[active];

  return (
    <div style={{
      minHeight: "100vh",
      background: "#0a0f1a",
      fontFamily: "'JetBrains Mono', 'Fira Code', monospace",
      color: "#e2e8f0",
      padding: "0",
    }}>
      {/* Header */}
      <div style={{
        padding: "28px 32px 0",
        borderBottom: "1px solid rgba(255,255,255,0.06)",
        background: "rgba(255,255,255,0.02)",
      }}>
        <div style={{ fontSize: 11, color: "#64748b", letterSpacing: 3, marginBottom: 6 }}>N.E.L.S.O.N — NGHIỆP VỤ MAP</div>
        <div style={{ fontSize: 20, fontWeight: 700, color: "#f1f5f9", marginBottom: 20, fontFamily: "Georgia, serif" }}>
          Từ Check Pricing → Active Job
        </div>

        {/* Tabs */}
        <div style={{ display: "flex", gap: 4 }}>
          {flowOrder.map((key) => {
            const f = flows[key];
            const col = colors[key];
            const isActive = active === key;
            return (
              <button
                key={key}
                onClick={() => setActive(key)}
                style={{
                  padding: "10px 20px",
                  border: "none",
                  borderRadius: "8px 8px 0 0",
                  background: isActive ? col.bg : "transparent",
                  color: isActive ? col.main : "#64748b",
                  fontFamily: "inherit",
                  fontSize: 11,
                  fontWeight: 700,
                  letterSpacing: 1.5,
                  cursor: "pointer",
                  borderBottom: isActive ? `2px solid ${col.main}` : "2px solid transparent",
                  transition: "all 0.2s",
                }}
              >
                {f.label}
              </button>
            );
          })}
        </div>
      </div>

      {/* Flow Steps */}
      <div style={{ padding: "28px 32px" }}>
        {/* Arrow connector row */}
        <div style={{ display: "flex", alignItems: "stretch", gap: 0, overflowX: "auto" }}>
          {flow.steps.map((step, i) => (
            <div key={step.id} style={{ display: "flex", alignItems: "center", flex: step.split ? 1.5 : 1 }}>
              {/* Step Card */}
              <div style={{
                flex: 1,
                background: step.highlight
                  ? `linear-gradient(135deg, ${c.bg}, rgba(255,255,255,0.03))`
                  : "rgba(255,255,255,0.03)",
                border: `1px solid ${step.highlight ? c.border : "rgba(255,255,255,0.07)"}`,
                borderRadius: 12,
                padding: "18px 16px",
                minWidth: 180,
                position: "relative",
                boxShadow: step.highlight ? `0 0 24px ${c.bg}` : "none",
              }}>
                {/* Step number */}
                <div style={{
                  position: "absolute",
                  top: -10,
                  left: 14,
                  background: step.highlight ? c.main : "#1e293b",
                  color: step.highlight ? "#0a0f1a" : "#64748b",
                  fontSize: 10,
                  fontWeight: 700,
                  padding: "2px 8px",
                  borderRadius: 4,
                  letterSpacing: 1,
                }}>
                  {String(i + 1).padStart(2, "0")}
                </div>

                {/* Icon + Title */}
                <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 14, marginTop: 4 }}>
                  <span style={{ fontSize: 16 }}>{step.icon}</span>
                  <span style={{
                    fontSize: 11,
                    fontWeight: 700,
                    color: step.highlight ? c.main : "#94a3b8",
                    letterSpacing: 0.5,
                  }}>{step.title}</span>
                </div>

                {/* Content */}
                {!step.split ? (
                  <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                    {step.items.map((item, j) => (
                      <div key={j} style={{
                        display: "flex",
                        alignItems: "flex-start",
                        gap: 8,
                        fontSize: 11.5,
                        color: item.startsWith("→") ? c.main : "#cbd5e1",
                        lineHeight: 1.5,
                      }}>
                        {!item.startsWith("→") && (
                          <span style={{ color: "#475569", marginTop: 1, flexShrink: 0 }}>·</span>
                        )}
                        <span style={{ fontFamily: item.startsWith("→") || item.includes("/api") ? "inherit" : "inherit" }}>
                          {item}
                        </span>
                      </div>
                    ))}
                  </div>
                ) : (
                  /* Split platform display */
                  <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                    {step.platforms.map((p, j) => (
                      <div key={j} style={{
                        background: "rgba(255,255,255,0.04)",
                        border: "1px solid rgba(255,255,255,0.07)",
                        borderRadius: 8,
                        padding: "10px 12px",
                        display: "flex",
                        gap: 10,
                        alignItems: "flex-start",
                      }}>
                        <span style={{ fontSize: 14 }}>{p.icon}</span>
                        <div>
                          <div style={{ fontSize: 10, color: "#64748b", fontWeight: 700, letterSpacing: 1, marginBottom: 4 }}>
                            {p.name}
                          </div>
                          <div style={{ fontSize: 11, color: "#94a3b8", lineHeight: 1.6, whiteSpace: "pre-line" }}>
                            {p.desc}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Arrow */}
              {i < flow.steps.length - 1 && (
                <div style={{ display: "flex", flexDirection: "column", alignItems: "center", padding: "0 8px" }}>
                  <div style={{
                    width: 24,
                    height: 2,
                    background: `linear-gradient(90deg, ${c.border}, ${c.main})`,
                    position: "relative",
                  }}>
                    <div style={{
                      position: "absolute",
                      right: -1,
                      top: -4,
                      width: 0,
                      height: 0,
                      borderLeft: `8px solid ${c.main}`,
                      borderTop: "5px solid transparent",
                      borderBottom: "5px solid transparent",
                    }} />
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>

        {/* API Endpoint Summary */}
        <div style={{
          marginTop: 28,
          background: "rgba(255,255,255,0.02)",
          border: `1px solid ${c.border}`,
          borderRadius: 12,
          padding: "16px 20px",
        }}>
          <div style={{ fontSize: 10, color: "#64748b", letterSpacing: 2, marginBottom: 12, fontWeight: 700 }}>
            FASTAPI ENDPOINT — {flow.label}
          </div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 16 }}>
            {active === "checkPricing" && <>
              <Chip color={c.main} label="POST /api/pricing/check" />
              <Chip color={c.main} label="GET /api/pricing/carriers" />
              <Chip color={c.main} label="GET /api/pricing/ports" />
            </>}
            {active === "quoteBuilder" && <>
              <Chip color={c.main} label="POST /api/quote/build" />
              <Chip color={c.main} label="GET /api/quote/{id}" />
              <Chip color={c.main} label="POST /api/quote/send" />
            </>}
            {active === "activeJob" && <>
              <Chip color={c.main} label="POST /api/job/activate" />
              <Chip color={c.main} label="PATCH /api/job/{id}/fast-no" />
              <Chip color={c.main} label="POST /api/job/{id}/booking-email" />
              <Chip color={c.main} label="GET /api/job/active" />
            </>}
          </div>
        </div>

        {/* Flow connector between tabs */}
        {active !== "activeJob" && (
          <div style={{
            marginTop: 16,
            display: "flex",
            alignItems: "center",
            gap: 10,
            color: "#475569",
            fontSize: 11,
          }}>
            <span>Kết quả của bước này</span>
            <span style={{ color: c.main }}>→</span>
            <span style={{ color: colors[flowOrder[flowOrder.indexOf(active) + 1]].main, fontWeight: 700 }}>
              trở thành INPUT của "{flows[flowOrder[flowOrder.indexOf(active) + 1]].label}"
            </span>
          </div>
        )}
      </div>
    </div>
  );
}

function Chip({ label, color }) {
  return (
    <div style={{
      background: "rgba(255,255,255,0.04)",
      border: `1px solid ${color}40`,
      borderRadius: 6,
      padding: "5px 12px",
      fontSize: 11.5,
      color: color,
      fontFamily: "inherit",
    }}>
      {label}
    </div>
  );
}
