/* 可视化与 AI 体验工具 */

function esc(s) {
  return String(s == null ? "" : s)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function money(n) {
  if (n >= 1e6) return "$" + (n / 1e6).toFixed(1) + "M";
  if (n >= 1e3) return "$" + Math.round(n / 1e3) + "K";
  return "$" + Math.round(n);
}

function growthPct(v) {
  /* 年增速格式化：0 或 null/undefined → N/A（数据不可用）；否则显示百分比 */
  if (v == null || v === 0) return "N/A";
  return (v * 100).toFixed(0) + "%";
}

function scoreColor(s) {
  if (s >= 75) return "var(--good)";
  if (s >= 60) return "var(--ai-3)";
  if (s >= 45) return "var(--warn)";
  return "var(--bad)";
}

/* 评分环 SVG */
function scoreRing(score, size = 64) {
  const r = size / 2 - 6;
  const c = 2 * Math.PI * r;
  const off = c * (1 - score / 100);
  const col = scoreColor(score);
  return `
  <svg width="${size}" height="${size}" viewBox="0 0 ${size} ${size}">
    <circle cx="${size / 2}" cy="${size / 2}" r="${r}" fill="none" stroke="rgba(255,255,255,0.08)" stroke-width="6"/>
    <circle cx="${size / 2}" cy="${size / 2}" r="${r}" fill="none" stroke="${col}" stroke-width="6"
      stroke-linecap="round" stroke-dasharray="${c.toFixed(1)}" stroke-dashoffset="${off.toFixed(1)}"
      transform="rotate(-90 ${size / 2} ${size / 2})" style="transition:stroke-dashoffset 1s cubic-bezier(.22,1,.36,1)"/>
    <text x="50%" y="50%" text-anchor="middle" dominant-baseline="central" fill="#fff" font-size="${size * 0.30}" font-weight="700">${Math.round(score)}</text>
  </svg>`;
}

/* 市场雷达图（首页）：机会评分 vs 竞争度 映射为极坐标点 */
function radarChart(opportunities) {
  const W = 460, H = 360, cx = W / 2, cy = H / 2, R = 138;
  const rings = [0.25, 0.5, 0.75, 1].map((f) => `
    <circle cx="${cx}" cy="${cy}" r="${R * f}" fill="none" stroke="rgba(255,255,255,0.06)"/>
  `).join("");
  const axes = opportunities.slice(0, 12).map((_, i) => {
    const a = (i / Math.min(opportunities.length, 12)) * Math.PI * 2 - Math.PI / 2;
    return `<line x1="${cx}" y1="${cy}" x2="${cx + R * Math.cos(a)}" y2="${cy + R * Math.sin(a)}" stroke="rgba(255,255,255,0.05)"/>`;
  }).join("");
  const dots = opportunities.map((o, i) => {
    const n = Math.min(opportunities.length, 12);
    const a = (i / n) * Math.PI * 2 - Math.PI / 2;
    // 竞争越低→越外圈；机会越高→点越亮越大
    const compF = 1 - (o.competition_score || 60) / 100;
    const rr = R * (0.35 + 0.6 * compF);
    const x = cx + rr * Math.cos(a), y = cy + rr * Math.sin(a);
    const col = scoreColor(o.opportunity_score);
    return `<circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="${(4 + o.opportunity_score / 18).toFixed(1)}" fill="${col}" opacity="0.85"><title>${esc(o.product_name)} · ${Math.round(o.opportunity_score)}</title></circle>`;
  }).join("");
  return `
  <svg viewBox="0 0 ${W} ${H}" width="100%" style="max-width:520px">
    <defs>
      <radialGradient id="rg" cx="50%" cy="50%" r="50%">
        <stop offset="0%" stop-color="rgba(99,102,241,0.18)"/>
        <stop offset="100%" stop-color="rgba(99,102,241,0)"/>
      </radialGradient>
    </defs>
    <circle cx="${cx}" cy="${cy}" r="${R + 18}" fill="url(#rg)"/>
    ${rings}${axes}
    <line x1="${cx}" y1="${cy - R - 22}" x2="${cx}" y2="${cy + R + 22}" stroke="rgba(34,211,238,0.5)" stroke-width="2" stroke-linecap="round">
      <animateTransform attributeName="transform" type="rotate" from="0 ${cx} ${cy}" to="360 ${cx} ${cy}" dur="6s" repeatCount="indefinite"/>
    </line>
    ${dots}
  </svg>`;
}

/* 四维度子分雷达（机会报告详情） */
function subScoreRadar(o) {
  const dims = [
    { k: "需求强度", v: o.demand_score },
    { k: "蓝海程度", v: o.competition_score },
    { k: "痛点强度", v: o.pain_severity_score },
    { k: "预算适配", v: o.budget_fit_score },
  ];
  const size = 220, cx = size / 2, cy = size / 2, R = 78;
  const pts = dims.map((d, i) => {
    const a = (i / dims.length) * Math.PI * 2 - Math.PI / 2;
    return [cx + R * (d.v / 100) * Math.cos(a), cy + R * (d.v / 100) * Math.sin(a), a];
  });
  const poly = pts.map((p) => `${p[0].toFixed(1)},${p[1].toFixed(1)}`).join(" ");
  const grid = [0.33, 0.66, 1].map((f) =>
    `<polygon points="${dims.map((_, i) => { const a = (i / dims.length) * Math.PI * 2 - Math.PI / 2; return `${cx + R * f * Math.cos(a)},${cy + R * f * Math.sin(a)}`; }).join(" ")}" fill="none" stroke="rgba(255,255,255,0.06)"/>`
  ).join("");
  const labels = dims.map((d, i) => {
    const a = (i / dims.length) * Math.PI * 2 - Math.PI / 2;
    const x = cx + (R + 20) * Math.cos(a), y = cy + (R + 20) * Math.sin(a);
    return `<text x="${x}" y="${y}" fill="var(--txt-2)" font-size="11" text-anchor="middle" dominant-baseline="central">${d.k}</text>`;
  }).join("");
  return `<svg width="${size}" height="${size}" viewBox="0 0 ${size} ${size}">
    ${grid}
    <polygon points="${poly}" fill="rgba(139,92,246,0.22)" stroke="var(--ai-2)" stroke-width="2"/>
    ${pts.map((p) => `<circle cx="${p[0].toFixed(1)}" cy="${p[1].toFixed(1)}" r="3" fill="var(--ai-3)"/>`).join("")}
    ${labels}
  </svg>`;
}

/* 打字机效果（用于 AI 生成内容的流式呈现） */
function typeWriter(el, text, speed = 14) {
  return new Promise((resolve) => {
    el.classList.add("cursor");
    let i = 0;
    const tick = () => {
      el.textContent = text.slice(0, i);
      i += Math.max(1, Math.round(text.length / 220));
      if (i >= text.length) { el.textContent = text; el.classList.remove("cursor"); resolve(); }
      else requestAnimationFrame(() => setTimeout(tick, speed));
    };
    tick();
  });
}

/* 通用进度条 */
function bar(value, color) {
  return `<div class="bar"><span style="width:${Math.max(4, value)}%;background:${color || "var(--ai-grad)"}"></span></div>`;
}

/* 利润瀑布图：售价 → 逐项扣减 → 净利润 */
function waterfallChart(steps) {
  const W = 580, H = 330, padB = 48, padT = 18, padL = 8, padR = 8;
  const plotH = H - padB - padT;
  const base = steps.find((s) => s.kind === "base") || steps[0];
  const maxV = Math.max(base.value, 1);
  const y = (v) => padT + plotH * (1 - v / maxV);
  const n = steps.length;
  const slot = (W - padL - padR) / n;
  const bw = Math.min(56, slot * 0.62);
  let cum = 0;
  const bars = steps.map((s, i) => {
    const x = padL + slot * i + (slot - bw) / 2;
    let top, bot, col;
    if (s.kind === "base") { top = y(s.value); bot = y(0); col = "var(--ai-2)"; cum = s.value; }
    else if (s.kind === "result") { top = y(s.value); bot = y(0); col = s.value >= 0 ? "var(--good)" : "var(--bad)"; }
    else { const before = cum; cum -= s.value; top = y(before); bot = y(cum); col = "var(--bad)"; }
    const h = Math.max(0, bot - top);
    return `<rect x="${x.toFixed(1)}" y="${top.toFixed(1)}" width="${bw.toFixed(1)}" height="${h.toFixed(1)}" rx="3" fill="${col}" opacity="0.92"/>`
      + `<text x="${(x + bw / 2).toFixed(1)}" y="${(top - 6).toFixed(1)}" text-anchor="middle" fill="var(--txt-2)" font-size="11" font-weight="600">$${Math.round(s.value)}</text>`
      + `<text x="${(x + bw / 2).toFixed(1)}" y="${(H - padB + 16).toFixed(1)}" text-anchor="middle" fill="var(--txt-3)" font-size="11">${esc(s.label)}</text>`;
  }).join("");
  const axis = `<line x1="${padL}" y1="${y(0).toFixed(1)}" x2="${W - padR}" y2="${y(0).toFixed(1)}" stroke="rgba(255,255,255,0.18)"/>`;
  return `<svg viewBox="0 0 ${W} ${H}" width="100%" style="max-width:620px">${axis}${bars}</svg>`;
}

/* 成本结构环形图 */
function donutChart(segments, size = 200) {
  const total = segments.reduce((a, s) => a + Math.max(0, s.value), 0) || 1;
  const cx = size / 2, cy = size / 2, r = size / 2 - 18, sw = 24;
  const c = 2 * Math.PI * r;
  let off = 0;
  const arcs = segments.map((s) => {
    const len = (Math.max(0, s.value) / total) * c;
    const seg = `<circle cx="${cx}" cy="${cy}" r="${r}" fill="none" stroke="${s.color}" stroke-width="${sw}" stroke-dasharray="${len.toFixed(2)} ${(c - len).toFixed(2)}" stroke-dashoffset="${(-off).toFixed(2)}" transform="rotate(-90 ${cx} ${cy})"/>`;
    off += len;
    return seg;
  }).join("");
  const center = `<text x="${cx}" y="${cy - 3}" text-anchor="middle" fill="#fff" font-size="13" font-weight="700">成本结构</text><text x="${cx}" y="${cy + 14}" text-anchor="middle" fill="var(--txt-2)" font-size="10">单件 $${Math.round(total)}</text>`;
  const legend = `<div class="donut-legend">${segments.map((s) => `<div class="dl"><span class="dot" style="background:${s.color}"></span>${esc(s.label)} <b>$${Math.round(s.value)}</b></div>`).join("")}</div>`;
  return `<div class="donut-wrap"><svg width="${size}" height="${size}" viewBox="0 0 ${size} ${size}">${arcs}${center}</svg>${legend}</div>`;
}

/* 全局显式暴露（防止浏览器缓存/加载时序导致 ReferenceError） */
Object.assign(window, {
  esc, money, scoreColor, scoreRing, radarChart, subScoreRadar,
  typeWriter, bar, waterfallChart, donutChart,
});

