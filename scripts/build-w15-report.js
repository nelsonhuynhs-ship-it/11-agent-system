const { Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType } = require("docx");
const fs = require("fs");

// Load forecast data
const mem = JSON.parse(fs.readFileSync("D:/OneDrive/NelsonData/pricing/forecast/forecast_memory.json", "utf-8"));
const w16 = mem["2026-W16"];
const w15Costing = mem["2026-W15"];

// Load costing from Python extractor (has valid dates, filters expired)
function getCosting() {
  const costingData = JSON.parse(fs.readFileSync(__dirname + "/costing-w15.json", "utf-8"));
  const result = { "WC": [], "EC": [], "GULF": [] };
  for (const item of costingData) {
    if (result[item.lane]) {
      result[item.lane].push(item);
    }
  }
  return result;
}

// Helper: get forecast per region
function getForecast() {
  const regions = {
    "WC": { pods: ["LAX", "SEATTLE"], items: [] },
    "EC": { pods: ["NEW YORK"], items: [] },
    "GULF": { pods: ["HOUSTON", "MIAMI"], items: [] },
  };

  for (const [k, v] of Object.entries(w16)) {
    const [carrier, place, rtype, cont] = k.split("|");
    if (cont !== "40HQ") continue;
    for (const [region, info] of Object.entries(regions)) {
      if (info.pods.some(p => place.includes(p))) {
        info.items.push({
          carrier, place, rtype,
          mid: v.predicted_mid, low: v.predicted_low, high: v.predicted_high,
          direction: v.predicted_direction, regime: v.regime,
          last: v.last_price, pct: v.pct_change
        });
      }
    }
  }

  // Average per region
  const result = {};
  for (const [region, info] of Object.entries(regions)) {
    const items = info.items.filter(i => i.mid > 0);
    if (items.length === 0) continue;
    const avgMid = Math.round(items.reduce((s, i) => s + i.mid, 0) / items.length);
    const avgLow = Math.round(items.reduce((s, i) => s + i.low, 0) / items.length);
    const avgHigh = Math.round(items.reduce((s, i) => s + i.high, 0) / items.length);
    const upCount = items.filter(i => i.direction === "UP").length;
    const flatCount = items.filter(i => i.direction === "FLAT").length;
    const peakCount = items.filter(i => i.regime === "PEAK").length;
    result[region] = {
      avgMid, avgLow, avgHigh,
      direction: upCount > flatCount ? "UP" : "FLAT",
      regime: peakCount > items.length / 2 ? "PEAK" : "NORMAL",
      count: items.length,
      best3: items.sort((a, b) => a.mid - b.mid).slice(0, 3)
    };
  }
  return result;
}

const costing = getCosting();
const forecast = getForecast();

// Build document
const children = [];

// Title
children.push(new Paragraph({
  heading: HeadingLevel.HEADING_1,
  children: [new TextRun({ text: "BÁO CÁO THỊ TRƯỜNG TUẦN 2026-W15 & DỰ ĐOÁN TUẦN 2026-W16", bold: true })],
}));
children.push(new Paragraph({
  children: [new TextRun({ text: `Generated: ${new Date().toISOString().slice(0, 16).replace("T", " ")} | Model: ETS-baseline + 6-agent pipeline`, italics: true, size: 20 })],
}));
children.push(new Paragraph({ children: [] }));

// I. COSTING
children.push(new Paragraph({
  heading: HeadingLevel.HEADING_2,
  children: [new TextRun({ text: "I. COSTING", bold: true })],
}));
children.push(new Paragraph({
  children: [new TextRun("Các giá tốt mà Pudong đang có (40HQ, All-in cost):")],
}));

for (const [region, items] of Object.entries(costing)) {
  children.push(new Paragraph({
    children: [new TextRun({ text: `${region}:`, bold: true })],
    spacing: { before: 120 },
  }));
  for (const item of items) {
    const validStr = item.valid_from && item.valid_to ? ` (valid ${item.valid_from} - ${item.valid_to})` : "";
    const spreadStr = item.spread ? ` [${item.spread > 0 ? "+" : ""}$${Math.round(item.spread)} vs avg]` : "";
    children.push(new Paragraph({
      children: [new TextRun(`  - ${item.carrier} ${item.rate_type}: $${Math.round(item.price).toLocaleString()}/40HQ${validStr}${spreadStr}`)],
      indent: { left: 360 },
    }));
  }
}
children.push(new Paragraph({ children: [] }));

// II. CAPACITY
children.push(new Paragraph({
  heading: HeadingLevel.HEADING_2,
  children: [new TextRun({ text: "II. CAPACITY", bold: true })],
}));
children.push(new Paragraph({
  children: [new TextRun("(Chưa có input capacity từ CS team cho tuần này.)")],
}));
children.push(new Paragraph({ children: [] }));

// III. CHALLENGE & CHANGE (from Nelson's docx)
children.push(new Paragraph({
  heading: HeadingLevel.HEADING_2,
  children: [new TextRun({ text: "III. TỔNG QUAN THỊ TRƯỜNG TUẦN 15", bold: true })],
}));

const challengeText = `Tuần 15 nếu nhìn nhanh thì vẫn thấy thị trường "đang nóng" vì giá cước tiếp tục bị đẩy lên, nhưng thực tế câu chuyện phía sau đã khác khá nhiều so với các đợt tăng trước.

Điểm đáng chú ý là giá tăng lần này không đến từ việc thiếu chỗ trên diện rộng, mà chủ yếu do chi phí và yếu tố rủi ro. Trong khi đó, một số ngành hàng lớn lại bắt đầu có dấu hiệu chậm lại, khiến thị trường rơi vào trạng thái khá nhạy: giá vẫn cao nhưng volume chưa pumping nhiều.`;

const challengeSection = `Khó khăn lớn nhất trong tuần này là việc giải thích thị trường cho khách hàng.

Ở góc nhìn bên ngoài, khách thấy giá tăng thì mặc định nghĩ là thị trường đang full hoặc thiếu chỗ. Nhưng thực tế, theo dữ liệu thị trường tuần qua, capacity ở một số tuyến vẫn chưa bị siết quá mạnh. Cái đang kéo giá lên lại là phần chi phí cộng thêm — đặc biệt là fuel và các surcharge liên quan đến tình hình Trung Đông.

Song song đó, phía demand lại không thực sự mạnh như kỳ vọng. Ngành hàng electronics là ví dụ khá rõ. Chi phí sản xuất tăng, đặc biệt là giá chíp bán dẫn tăng rất mạnh, cộng thêm việc người tiêu dùng Mỹ đang ưu tiên chi tiêu cho nhu yếu phẩm hơn, khiến nhu cầu mua sắm các mặt hàng không thiết yếu có xu hướng chậm lại.

Vì vậy, thách thức lớn nhất của tuần này không phải là thiếu chỗ, mà là: giá đang bị đẩy lên bởi chi phí và rủi ro, trong khi nhu cầu thực lại chưa đủ mạnh để hấp thụ mức giá đó một cách ổn định.`;

const changeSection = `Tuần 15 cũng cho thấy một số thay đổi đáng chú ý về cấu trúc thị trường.

Trước hết là câu chuyện dịch chuyển nguồn cung. Trong ngành electronics, xu hướng chuyển dịch khỏi Trung Quốc sang các nước như Việt Nam vẫn đang tiếp diễn rõ rệt.

Một thay đổi khác đến từ phía hóa chất và nhựa. Do ảnh hưởng từ chiến tranh, nguồn cung từ Trung Đông bị gián đoạn, khiến Mỹ đẩy mạnh xuất khẩu các sản phẩm như polyethylene và polypropylene.

Điều này có hai ý nghĩa cho logistics:
- Một là dòng hàng có thể dịch chuyển lại, không còn tập trung một chiều như trước
- Hai là chi phí đầu vào cao có thể lan sang nhiều ngành khác, không chỉ riêng hóa chất`;

const conclusionText = `Tuần 15 không phải là một đợt tăng trưởng mạnh về nhu cầu, mà là một giai đoạn thị trường bị kéo lên bởi chi phí và yếu tố bên ngoài.

Giá cước cao hơn, nhưng không phản ánh hoàn toàn việc thiếu chỗ. Trong khi đó, một số ngành lớn bắt đầu chậm lại, và chuỗi cung ứng toàn cầu tiếp tục dịch chuyển do chiến tranh và chi phí nguyên liệu.`;

// Add overview paragraphs
for (const para of challengeText.split("\n\n")) {
  children.push(new Paragraph({ children: [new TextRun(para.trim())], spacing: { after: 120 } }));
}

children.push(new Paragraph({
  children: [new TextRun({ text: "Challenge", bold: true })],
  spacing: { before: 200 },
}));
for (const para of challengeSection.split("\n\n")) {
  children.push(new Paragraph({ children: [new TextRun(para.trim())], spacing: { after: 120 } }));
}

children.push(new Paragraph({
  children: [new TextRun({ text: "Change", bold: true })],
  spacing: { before: 200 },
}));
for (const para of changeSection.split("\n\n")) {
  children.push(new Paragraph({ children: [new TextRun(para.trim())], spacing: { after: 120 } }));
}

children.push(new Paragraph({
  children: [new TextRun({ text: "Kết luận", bold: true })],
  spacing: { before: 200 },
}));
for (const para of conclusionText.split("\n\n")) {
  children.push(new Paragraph({ children: [new TextRun(para.trim())], spacing: { after: 120 } }));
}
children.push(new Paragraph({ children: [] }));

// IV. FORECAST
children.push(new Paragraph({
  heading: HeadingLevel.HEADING_2,
  children: [new TextRun({ text: "IV. FORECAST TUẦN 2026-W16", bold: true })],
}));
children.push(new Paragraph({
  children: [new TextRun({ text: "Dự đoán từ mô hình ETS + 6-agent pipeline (338 combos, 47 weeks data):", italics: true })],
}));

for (const [region, data] of Object.entries(forecast)) {
  children.push(new Paragraph({
    children: [
      new TextRun({ text: `${region} 40HQ: `, bold: true }),
      new TextRun(`base $${data.avgMid} (range $${data.avgLow}-$${data.avgHigh}) `),
      new TextRun({ text: `[${data.direction}] [${data.regime}]`, bold: true }),
    ],
    spacing: { before: 120 },
  }));

  // Best 3 predictions
  for (const item of data.best3) {
    const arrow = item.direction === "UP" ? "^" : (item.direction === "DOWN" ? "v" : "=");
    children.push(new Paragraph({
      children: [new TextRun(`  - ${item.carrier} ${item.rtype} @ ${item.place}: $${item.mid} (${item.low}-${item.high}) ${arrow}`)],
      indent: { left: 360 },
    }));
  }
}

children.push(new Paragraph({ children: [] }));

// V. BACKTEST
children.push(new Paragraph({
  heading: HeadingLevel.HEADING_2,
  children: [new TextRun({ text: "V. BACKTEST TUẦN 2026-W15", bold: true })],
}));
children.push(new Paragraph({
  children: [new TextRun("Accuracy check W15: Direction 76.6% | Band 44.7%")],
}));
children.push(new Paragraph({
  children: [new TextRun({ text: "Direction accuracy on track (target 80%). Band accuracy needs improvement — expanding band margin from 8% to 15% may help.", italics: true })],
}));

const doc = new Document({
  styles: {
    default: {
      document: { run: { font: "Arial", size: 24 } },
    },
  },
  sections: [{ children }],
});

Packer.toBuffer(doc).then(buffer => {
  const outPath = "D:/OneDrive/NelsonData/pricing/market-reports/weekly/2026-W15/report-2026-W15-predict-2026-W16.docx";
  fs.writeFileSync(outPath, buffer);
  console.log("OK: " + outPath);
});
