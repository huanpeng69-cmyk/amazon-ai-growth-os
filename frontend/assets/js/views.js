/* 视图渲染器：AI 市场雷达 / 产品机会报告 / VOC 分析 / Listing 工厂 / 广告分析 / 总报告 / 视觉工厂 / 利润分析 / 市场调研 / 接口设置 */


const COUNTRIES = [
  { code: "US", label: "美国" }, { code: "DE", label: "德国" },
  { code: "JP", label: "日本" }, { code: "UK", label: "英国" },
];

/* 从自然语言解析参数（首页便捷输入） */
function parseNL(q) {
  q = (q || "").toLowerCase();
  let country = "US";
  if (/(德国|德区|de\b|germany)/.test(q)) country = "DE";
  else if (/(日本|日区|jp\b|japan)/.test(q)) country = "JP";
  else if (/(英国|英区|uk\b|britain)/.test(q)) country = "UK";
  let budget = 5000;
  const m = q.match(/(\d[\d,]*)\s*(万|k|千)?/);
  if (m) {
    budget = parseInt(m[1].replace(/,/g, ""), 10);
    if (m[2] === "万") budget *= 10000;
    else if (m[2] === "k" || m[2] === "千") budget *= 1000;
  }
  let category = "Kitchen";
  const cleaned = q.replace(/(美国|美区|德国|德区|日本|日区|英国|英区|us|de|jp|uk|germany|japan|britain)/g, "")
    .replace(/(\d[\d,]*\s*(万|k|千)?)/g, "").replace(/[找看分析挖掘做选蓝海市场类目预算产品利基的给帮我想在]/g, "").trim();
  if (cleaned) {
    // 降级清洗：去掉残留主语（我/你）与货币单位（美元/元），避免 "我厨房美元" 这类垃圾
    const cat = cleaned.replace(/^(我|你|他|她|它|我们|你们)+/, "")
                       .replace(/(美元|美金|元|欧|eur|usd)$/i, "").trim();
    if (cat) category = cat.split(/\s+/)[0].replace(/[，。,.]/g, "");
  }
  return { country, category: category || "Kitchen", budget };
}

/* —— 利润分析：字段回填 & 报告渲染 —— */
const PF_FIELD_MAP = {
  selling_price: "#pPrice", product_cost: "#pCost", shipping_cost: "#pShip",
  referral_fee_rate: "#pRef", fba_fee: "#pFba", ad_acos: "#pAcos",
  other_cost_per_unit: "#pOther", monthly_fixed_cost: "#pFixed", initial_investment: "#pInv",
};
function fillCostFields(view, fields) {
  if (!fields) return;
  Object.entries(PF_FIELD_MAP).forEach(([fld, sel]) => {
    if (fields[fld] == null) return;
    const el = view.querySelector(sel); if (!el) return;
    const v = fields[fld];
    el.value = (fld === "referral_fee_rate" || fld === "ad_acos") ? (v * 100).toFixed(1) : v;
  });
}
function metric(k, v, color) {
  return `<div class="card metric"><div class="k">${esc(k)}</div><div class="v" style="${color ? "color:" + color : ""}">${esc(v)}</div></div>`;
}
function renderProfit(out, r) {
  const p = r.profit.per_unit;
  const recMap = { invest: ["建议投入", "var(--good)"], cautious: ["谨慎投入", "var(--warn)"], avoid: ["暂不推荐", "var(--bad)"] };
  const [recLabel, recCol] = recMap[r.profit.recommendation] || ["—", "var(--txt-2)"];
  const steps = [
    { label: "售价", value: p.selling_price, kind: "base" },
    { label: "产品成本", value: p.product_cost, kind: "minus" },
    { label: "物流", value: p.shipping_cost, kind: "minus" },
    { label: "Amazon费", value: p.amazon_fee, kind: "minus" },
    { label: "广告", value: p.ad_cost, kind: "minus" },
    { label: "其他", value: p.other_cost, kind: "minus" },
    { label: "净利润", value: p.net_profit, kind: "result" },
  ];
  const segs = [
    { label: "产品成本", value: p.product_cost, color: "#8b5cf6" },
    { label: "物流", value: p.shipping_cost, color: "#22d3ee" },
    { label: "Amazon费", value: p.amazon_fee, color: "#f59e0b" },
    { label: "广告", value: p.ad_cost, color: "#ef4444" },
    { label: "其他", value: p.other_cost, color: "#64748b" },
  ];
  const f = r.forecast;
  const rkMap = { low: ["低风险", "var(--good)"], medium: ["中风险", "var(--warn)"], high: ["高风险", "var(--bad)"] };
  const [rkLabel, rkCol] = rkMap[r.risk.risk_level] || ["—", "var(--txt-2)"];
  const tone = (c) => c >= 0 ? "var(--good)" : "var(--bad)";
  out.innerHTML = `
    <div class="pf-head">
      <div>${scoreRing(r.profit.profitability_score, 88)}</div>
      <div class="pf-head-main">
        <div class="eyebrow"><span class="pulse"></span>PROFIT REPORT</div>
        <h2 style="font-size:20px;font-weight:660">${esc(r.product_name)} · ${esc(r.country)}</h2>
        <div style="font-size:12.5px;color:var(--txt-2);margin-top:2px">数据来源：<b>${esc(r.cost_source)}</b> · 生成于 ${esc((r.generated_at || "").replace("T", " "))}</div>
        <div class="rec-badge" style="margin-top:8px;color:${recCol};font-weight:650">投资建议：${recLabel}</div>
      </div>
    </div>

    <div class="metric-row">
      ${metric("售价", "$" + Math.round(p.selling_price))}
      ${metric("单件毛利", "$" + Math.round(p.gross_profit), tone(p.gross_profit))}
      ${metric("单件净利", "$" + Math.round(p.net_profit), tone(p.net_profit))}
      ${metric("净利率", (p.net_margin * 100).toFixed(1) + "%", p.net_margin >= 0.18 ? "var(--good)" : p.net_margin >= 0.08 ? "var(--warn)" : "var(--bad)")}
    </div>

    <div class="pf-grid">
      <div class="card"><h3 class="pf-h">利润瀑布图</h3>${waterfallChart(steps)}</div>
      <div class="card"><h3 class="pf-h">成本结构</h3>${donutChart(segs)}</div>
    </div>

    <div class="card insight" style="margin-top:6px"><p>${esc(r.profit.recommendation_reason)}</p></div>

    <div class="metric-row" style="margin-top:14px">
      ${metric("预测月销量", (f.estimated_monthly_units || 0) + " 件")}
      ${metric("月净利润", "$" + Math.round(r.profit.monthly_net_profit))}
      ${metric("月净经营利润", "$" + Math.round(r.profit.monthly_net_operating), tone(r.profit.monthly_net_operating))}
      ${metric("回本周期", f.payback_months != null ? f.payback_months + " 个月" : "—")}
      ${metric("盈亏平衡(月销量)", f.break_even_monthly_units > 0 ? Math.ceil(f.break_even_monthly_units) + " 件" : "—")}
    </div>
    <div class="card insight" style="margin-top:6px;font-size:12.5px;color:var(--txt-2)">销量预测依据：${esc(f.basis)}</div>

    <h3 class="pf-h" style="margin-top:18px">风险分析 · <span style="color:${rkCol}">${rkLabel} (${r.risk.risk_score})</span></h3>
    <div class="card insight" style="color:${rkCol}">${esc(r.risk.warning_text)}</div>
    <div class="risk-list">
      ${r.risk.risks.map((rk) => `
        <div class="risk-item">
          <div class="risk-top"><span>${esc(rk.factor)}</span><span class="sev" style="color:${scoreColor(rk.severity)}">${Math.round(rk.severity)}</span></div>
          ${bar(rk.severity, scoreColor(rk.severity))}
          <div class="risk-desc">${esc(rk.description)}</div>
          <div class="risk-mit"><b>应对：</b>${esc(rk.mitigation)}</div>
        </div>`).join("")}
    </div>`;
}

const Views = {
  /* ---------- 首页：AI 市场雷达 ---------- */
  home(view) {
    view.innerHTML = `
      <div class="eyebrow"><span class="pulse"></span>AI MARKET RADAR</div>
      <h1 class="page-title">用 AI 扫描全球<span class="gradient-text">蓝海市场</span></h1>
      <p class="page-sub">告诉 AI 你想进入的市场，Multi-Agent 会在数秒内扫描数千个利基信号，
        结合需求、竞争、用户痛点与你的预算，给出可立即行动的机会清单。</p>

      <div class="card hero-panel fade-up">
        <div class="nl-input">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="11" cy="11" r="7"/><path d="M21 21l-4-4"/></svg>
          <input id="nl" placeholder="例如：帮我在美国厨房类目找预算 5000 美元的蓝海产品" />
        </div>
        <div class="param-row">
          <div class="field" style="min-width:200px">
            <label>站点市场</label>
            <div class="seg" id="countrySeg">
              ${COUNTRIES.map((c, i) => `<button data-c="${c.code}" class="${i === 0 ? "on" : ""}">${c.label}</button>`).join("")}
            </div>
          </div>
          <div class="field" style="flex:1;min-width:200px">
            <label>类目 / 利基</label>
            <input id="cat" value="Kitchen" />
          </div>
          <div class="field" style="min-width:220px">
            <label>进入预算 · <span class="range-val" id="budVal">$5,000</span></label>
            <input type="range" id="bud" min="500" max="50000" step="500" value="5000" />
          </div>
          <button class="btn btn-primary" id="launch" style="margin-left:auto">
            <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14M13 6l6 6-6 6"/></svg>
            发射雷达
          </button>
        </div>
      </div>

      <div id="scanResult"></div>
    `;

    let country = "US";
    view.querySelector("#countrySeg").addEventListener("click", (e) => {
      const b = e.target.closest("button"); if (!b) return;
      view.querySelectorAll("#countrySeg button").forEach((x) => x.classList.remove("on"));
      b.classList.add("on"); country = b.dataset.c;
    });
    const bud = view.querySelector("#bud"), budVal = view.querySelector("#budVal");
    bud.addEventListener("input", () => budVal.textContent = "$" + Number(bud.value).toLocaleString());

    view.querySelector("#launch").addEventListener("click", async () => {
      const nl = view.querySelector("#nl").value.trim();
      if (nl) {
        // 自然语言走 Supervisor Agent 总控（市场/竞品/VOC/产品均可识别）
        await dispatchQuery(nl);
        return;
      }
      const p = { country, category: view.querySelector("#cat").value || "Kitchen", budget: Number(bud.value) };
      await runRadar(view, p.country, p.category, p.budget);
    });
  },

  /* ---------- 产品机会报告（已合并到首页，此处保留为兼容跳转） ---------- */
  opportunity(view) {
    // 已合并到 AI 市场雷达单页；若有历史数据则首页会直接展示完整报告
    view.innerHTML = `
      <div class="eyebrow"><span class="pulse"></span>PRODUCT OPPORTUNITY</div>
      <h1 class="page-title">产品<span class="gradient-text">机会报告</span></h1>
      <div class="card empty" style="margin-top:30px">
        <div class="big">已合并到「AI 市场雷达」</div>
        <p>产品机会报告现在与雷达扫描在同一页面展示。发射雷达后即可看到完整的产品卡片网格。</p>
        <button class="btn btn-primary" style="margin-top:18px" onclick="location.hash='#/'">去 AI 市场雷达 →</button>
      </div>`;
  },

  /* ---------- VOC 分析 ---------- */
  voc(view) {
    view.innerHTML = `
      <div class="eyebrow"><span class="pulse"></span>VOICE OF CUSTOMER</div>
      <h1 class="page-title">用户评论<span class="gradient-text">VOC 分析</span></h1>
      <p class="page-sub">输入一个利基或 ASIN，AI 聚合真实买家评论，提炼高频痛点、严重程度与可落地的改进建议。</p>
      ${provBarHtml(["amazon", "review"])}
      <div class="card hero-panel fade-up" style="margin-top:24px">
        <div class="param-row">
          <div class="field" style="flex:1;min-width:240px"><label>利基 / 产品关键词</label>
            <input id="vocKw" value="cat water fountain" /></div>
          <div class="field" style="min-width:150px"><label>站点</label>
            <select id="vocC"><option>US</option><option>DE</option><option>JP</option><option>UK</option></select></div>
          <button class="btn btn-primary" id="vocRun" style="margin-left:auto">分析评论</button>
        </div>
      </div>
      <div id="vocOut"></div>`;
    view.querySelector("#vocRun").addEventListener("click", async () => {
      const kw = view.querySelector("#vocKw").value.trim() || "cat water fountain";
      const country = view.querySelector("#vocC").value;
      const out = view.querySelector("#vocOut");
      out.innerHTML = `<div class="scan-dots"><span class="s"></span><span class="s"></span><span class="s"></span><span class="s"></span><span class="s"></span></div>
        <p class="page-sub" style="margin-top:12px">AI 正在聚合 ${esc(kw)} 的买家评论并提炼痛点…</p>`;
      try {
        const r = await API.voc({
          product_name: kw, country,
          ...(Workspace.productId ? { product_id: Workspace.productId } : {}),
        });
        const res = r;
        try { sessionStorage.setItem("lastVoc", JSON.stringify({ kw, pains: (res.pain_points || []).map((p) => p.pain) })); } catch (_) {}
        if (Workspace.productId) Workspace.loadLinkage();
        out.innerHTML = `
          <div class="card insight" style="margin-top:22px"><p id="vocSum"></p></div>
          <div id="vocList" style="margin-top:18px"></div>`;
        typeWriter(view.querySelector("#vocSum"), res.summary, 9);
        const list = view.querySelector("#vocList");
        res.pain_points.forEach((p, i) => {
          const el = document.createElement("div");
          el.className = "card voice fade-up";
          el.style.animationDelay = (i * 0.06) + "s";
          el.innerHTML = `
            <div class="ico"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M21 11.5a8.4 8.4 0 0 1-9 8.4L3 21l1.1-3.9A8.4 8.4 0 1 1 21 11.5z"/></svg></div>
            <div class="body">
              <div class="ph">${esc(p.pain)}</div>
              <div class="meta"><span>严重度 <b style="color:${scoreColor(p.severity)}">${p.severity}</b></span><span>证据量 ${p.evidence.toLocaleString()}</span></div>
              ${bar(p.severity, scoreColor(p.severity))}
              <div class="fix" style="margin-top:10px">💡 改进建议：${esc(p.suggested_fix)}</div>
            </div>`;
          list.appendChild(el);
        });
      } catch (e) { out.innerHTML = `<div class="card empty">分析失败：${esc(e.message)}</div>`; }
    });
    prefillWorkspace(view, { "#vocKw": "niche_keyword", "#vocC": "country" });
    refreshProvenance(view.querySelector(".prov-bar"), ["amazon", "review"]);
  },

  /* ---------- 市场调研 Agent（Bright Data 取数 + 数据清洗 + AI 分析） ---------- */
  marketResearch(view) {
    const countryOpts = (typeof COUNTRY_OPTS !== "undefined" ? COUNTRY_OPTS : ["US", "DE", "JP", "UK"])
      .map((c) => `<option value="${c}">${c}</option>`).join("");
    view.innerHTML = `
      <div class="eyebrow"><span class="pulse"></span>MARKET RESEARCH · BRIGHT DATA + AI</div>
      <h1 class="page-title">市场<span class="gradient-text">调研 Agent</span></h1>
      <p class="page-sub">输入国家 / 类目 / 关键词，Agent 经 Bright Data 实时取数、数据清洗，并由 AI 产出市场报告（不返回原始数据）。</p>
      ${provBarHtml(["amazon"])}
      <div class="card hero-panel fade-up" style="margin-top:24px">
        <div class="param-row">
          <div class="field" style="min-width:140px"><label>站点</label>
            <select id="mrC">${countryOpts}</select></div>
          <div class="field" style="flex:1;min-width:200px"><label>类目</label>
            <input id="mrCat" value="Pets" /></div>
          <div class="field" style="flex:1;min-width:200px"><label>关键词（可选）</label>
            <input id="mrKw" placeholder="如 cat water fountain，留空则用类目检索" /></div>
          <button class="btn btn-primary" id="mrRun" style="margin-left:auto">生成市场报告</button>
        </div>
      </div>
      <div id="mrOut"></div>`;
    view.querySelector("#mrRun").addEventListener("click", async () => {
      const country = view.querySelector("#mrC").value;
      const category = view.querySelector("#mrCat").value.trim() || "Pets";
      const keyword = view.querySelector("#mrKw").value.trim();
      const out = view.querySelector("#mrOut");
      out.innerHTML = `<div class="scan-dots"><span class="s"></span><span class="s"></span><span class="s"></span><span class="s"></span><span class="s"></span></div>
        <p class="page-sub" style="margin-top:12px">Bright Data 取数中 → 数据清洗 → AI 撰写市场报告…</p>`;
      try {
        const r = await API.marketResearch({ country, category, keyword });
        out.innerHTML = renderMarketReport(r);
        const sum = out.querySelector("#mrSum");
        if (sum) typeWriter(sum, r.summary || "", 9);
      } catch (e) {
        out.innerHTML = `<div class="card empty">生成失败：${esc(e.message || String(e))}</div>`;
      }
    });
    prefillWorkspace(view, { "#mrCat": "category", "#mrC": "country" });
    refreshProvenance(view.querySelector(".prov-bar"), ["amazon"]);
  },

  /* ---------- Listing 工厂（真实 Listing Agent） ---------- */
  listing(view) {
    view.innerHTML = `
      <div class="eyebrow"><span class="pulse"></span>LISTING FACTORY</div>
      <h1 class="page-title">AI <span class="gradient-text">Listing 工厂</span></h1>
      <p class="page-sub">输入产品信息，AI 一次性产出合规、高转化的标题、五点描述、详情文案、后台关键词与图片方案。</p>
      <div class="two-col" style="margin-top:24px">
        <div class="card hero-panel">
          <div class="field" style="margin-bottom:14px"><label>产品名称</label><input id="lName" value="Cat Water Fountain" /></div>
          <div class="field" style="margin-bottom:14px"><label>核心利基</label><input id="lNic" value="quiet pet hydration" /></div>
          <div class="field" style="margin-bottom:14px"><label>核心卖点（逗号分隔）</label><input id="lFeat" value="超静音,食品级材质,大容量,易清洗" /></div>
          <div class="field" style="margin-bottom:18px"><label>语气</label>
            <select id="lTone"><option>专业可信</option><option>年轻活力</option><option>高端奢华</option></select></div>
          <button class="btn btn-primary" id="lGen" style="width:100%">⚡ 生成 Listing</button>
          <button class="btn" id="lImg" style="width:100%;margin-top:10px">🖼 生成图片方案</button>
        </div>
        <div id="lOut"><div class="card empty"><div class="big">等待生成</div><p>左侧填写信息后点击生成，AI 将产出完整 Listing 与图片方案。</p></div></div>
      </div>`;
    view.querySelector("#lGen").addEventListener("click", async () => {
      const name = view.querySelector("#lName").value.trim() || "Product";
      const nic = view.querySelector("#lNic").value.trim() || "";
      const feats = view.querySelector("#lFeat").value.split(/[,，]/).map((s) => s.trim()).filter(Boolean);
      const tone = view.querySelector("#lTone").value;
      const out = view.querySelector("#lOut");
      out.innerHTML = `<div class="card hero-panel" style="margin-top:0"><div class="scan-dots"><span class="s"></span><span class="s"></span><span class="s"></span><span class="s"></span><span class="s"></span></div><p class="page-sub" style="margin-top:10px">AI 正在生成高转化 Listing…</p></div>`;
      try {
        const r = await API.listing({ product_name: name, niche_keyword: nic, key_features: feats, tone,
        ...(Workspace.productId ? { product_id: Workspace.productId } : {}) });
        renderListing(out, r);
      } catch (e) { out.innerHTML = `<div class="card empty">生成失败：${esc(e.message)}</div>`; }
    });
    view.querySelector("#lImg").addEventListener("click", async () => {
      const name = view.querySelector("#lName").value.trim() || "Product";
      const nic = view.querySelector("#lNic").value.trim() || "";
      const out = view.querySelector("#lOut");
      out.innerHTML = `<div class="card hero-panel" style="margin-top:0"><div class="scan-dots"><span class="s"></span><span class="s"></span><span class="s"></span><span class="s"></span><span class="s"></span></div><p class="page-sub" style="margin-top:10px">AI 正在规划电商视觉…</p></div>`;
      try {
        const r = await API.imageGen({ product_name: name, niche_keyword: nic, count: 6,
          ...(Workspace.productId ? { product_id: Workspace.productId } : {}) });
        renderImages(out, r);
      } catch (e) { out.innerHTML = `<div class="card empty">生成失败：${esc(e.message)}</div>`; }
    });
    prefillWorkspace(view, {
      "#lName": "name", "#lNic": "niche_keyword", "#lCountry": "country",
      "#lFeat": "_selling_points",
    });
    applyLinkage(view, "listing");
  },

  /* ---------- 广告分析（真实 Advertising Agent） ---------- */
  ads(view) {
    view.innerHTML = `
      <div class="eyebrow"><span class="pulse"></span>AD ANALYTICS</div>
      <h1 class="page-title">AI <span class="gradient-text">广告分析</span></h1>
      <p class="page-sub">聚合 SP/SB/SD 投放数据，AI 定位低效词、预算错配与增量机会，给出可执行的优化动作。</p>
      ${provBarHtml(["amazon", "ads", "review"])}
      <div class="card hero-panel" style="margin-top:24px">
        <div class="param-row">
          <div class="field" style="flex:1;min-width:200px"><label>产品名称</label><input id="adName" value="Cat Water Fountain" /></div>
          <div class="field" style="flex:1;min-width:170px"><label>核心利基</label><input id="adNic" value="quiet pet hydration" /></div>
          <div class="field" style="min-width:110px"><label>站点</label><select id="adC"><option>US</option><option>DE</option><option>JP</option><option>UK</option></select></div>
          <div class="field" style="min-width:140px"><label>月预算(可选) $</label><input id="adBud" type="number" value="2000" /></div>
          <button class="btn btn-primary" id="adRun" style="margin-left:auto">分析广告</button>
        </div>
        <div class="field" style="margin-top:12px"><label>种子关键词（可选，可由上游联动自动带入）</label><input id="adSeeds" placeholder="从 VOC / 竞品 自动派生，可手动补充" /></div>
        </div>
      </div>
      <div id="adOut"></div>`;
    view.querySelector("#adRun").addEventListener("click", async () => {
      const name = view.querySelector("#adName").value.trim() || "Product";
      const nic = view.querySelector("#adNic").value.trim();
      const country = view.querySelector("#adC").value;
      const bud = parseInt(view.querySelector("#adBud").value || "0", 10);
      const out = view.querySelector("#adOut");
      out.innerHTML = `<div class="card hero-panel" style="margin-top:0"><div class="scan-dots"><span class="s"></span><span class="s"></span><span class="s"></span><span class="s"></span><span class="s"></span></div><p class="page-sub" style="margin-top:10px">AI 正在分析 ${esc(name)} 的广告表现…</p></div>`;
      try {
        const r = await API.advertising({ product_name: name, niche_keyword: nic, country, budget_usd: bud,
          ...(Workspace.productId ? { product_id: Workspace.productId } : {}) });
        renderAds(out, r);
        refreshProvenance(view.querySelector(".prov-bar"), ["amazon", "ads", "review"]);
      } catch (e) { out.innerHTML = `<div class="card empty">分析失败：${esc(e.message)}</div>`; }
    });
    prefillWorkspace(view, { "#adName": "name", "#adNic": "niche_keyword", "#adC": "country", "#adBud": "budget_usd" });
    applyLinkage(view, "advertising");
  },

  /* ---------- AI 商品视觉工厂（Product Visual Agent —— 左右分栏专业版） ---------- */
  visual(view) {
    view.innerHTML = `
      <div class="vf-header">
        <div class="vf-header-left">
          <div class="eyebrow"><span class="pulse"></span>AI DETAIL PAGE GENERATOR</div>
          <h1 class="page-title">AI <span class="gradient-text">详情页生成</span></h1>
          <p class="page-sub">左侧输入参数面板，用于上传参考图、设置生成参数并提交生成任务；右侧为结果展示版面，支持版本对比、图片预览、下载、重新生成等操作</p>
        </div>
        <div class="vf-header-icon">
          <svg viewBox="0 0 24 24" fill="none" stroke="var(--ai-3)" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/></svg>
        </div>
      </div>

      <div class="vf-workspace">
        <!-- ===== 左侧：输入参数面板 ===== -->
        <div class="vf-input-panel">

          <!-- 1. 参考图/风格参考 -->
          <div class="vf-section">
            <div class="vf-section-head">
              <div class="vf-section-num">①</div>
              <div class="vf-section-title">参考图区域</div>
              <div class="vf-section-desc">支持上传或从图库选择风格参考图</div>
            </div>
            <div class="vf-upload-zone" id="vfRefZone" data-type="ref">
              <div class="vf-upload-placeholder">
                <svg viewBox="0 0 24 24" width="28" height="28" fill="none" stroke="var(--txt-3)" stroke-width="1.6"><rect x="3" y="3" width="18" height="18" rx="3"/><line x1="12" y1="8" x2="12" y2="16"/><line x1="8" y1="12" x2="16" y2="12"/></svg>
                <span>参考图 / 风格参考</span>
              </div>
              <div class="vf-upload-actions">
                <button class="vf-btn-sm" id="vfRefAdd" type="button"><svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2.2"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg> 添加</button>
                <button class="vf-btn-sm vf-btn-ghost" id="vfRefLib" type="button"><svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.8"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="9" cy="9" r="2"/><path d="M21 15l-5-5L5 21"/></svg> 图库</button>
              </div>
              <div class="vf-preview-list" id="vfRefPreview"></div>
              <input type="file" id="vfRefInput" accept="image/*" multiple hidden />
            </div>
          </div>

          <!-- 2. 商品图/产品素材 -->
          <div class="vf-section">
            <div class="vf-section-head">
              <div class="vf-section-num">②</div>
              <div class="vf-section-title">素材上传区域</div>
              <div class="vf-section-desc">支持上传商品原图素材</div>
            </div>
            <div class="vf-upload-zone" id="vfMatZone" data-type="mat">
              <div class="vf-upload-placeholder">
                <svg viewBox="0 0 24 24" width="28" height="28" fill="none" stroke="var(--txt-3)" stroke-width="1.6"><rect x="3" y="3" width="18" height="18" rx="3"/><line x1="12" y1="8" x2="12" y2="16"/><line x1="8" y1="12" x2="16" y2="12"/></svg>
                <span>商品图 / 产品素材</span>
              </div>
              <div class="vf-upload-actions">
                <button class="vf-btn-sm" id="vfMatAdd" type="button"><svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2.2"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg> 添加</button>
                <button class="vf-btn-sm vf-btn-ghost" id="vfMatDel" type="button"><svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.8"><polyline points="3,6 5,6 21,6"/><path d="M19,6v14a2,2,0,0,1-2,2H7a2,2,0,0,1-2-2V6m3,0V4a2,2,0,0,1,2-2h4a2,2,0,0,1,2,2v2"/></svg> 删除</button>
              </div>
              <div class="vf-preview-list" id="vfMatPreview"></div>
              <input type="file" id="vfMatInput" accept="image/*" multiple hidden />
            </div>
          </div>

          <!-- 3. 基本信息输入 -->
          <div class="vf-section">
            <div class="vf-section-head">
              <div class="vf-section-num">③</div>
              <div class="vf-section-title">基本信息输入</div>
              <div class="vf-section-desc">项目名称、类目、网站</div>
            </div>
            <div class="vf-form-row">
              <div class="vf-field vf-flex-1">
                <input id="vfName" class="vf-input" placeholder="如 linux.do" value="Cat Water Fountain" />
                <span class="vf-input-label">商品图 / 产品素材</span>
              </div>
              <div class="vf-field vf-field-inline" style="width:90px">
                <select id="vfCategory" class="vf-select">
                  <option value="Pet Supplies">宠物用品</option><option value="Kitchen">厨房</option>
                  <option value="Electronics">电子</option><option value="Sports">运动</option>
                  <option value="Beauty">美妆</option><option value="Home">家居</option>
                  <option value="Garden">园艺</option><option value="Toys">玩具</option>
                </select>
              </div>
              <div class="vf-field vf-field-inline" style="width:80px">
                <select id="vfSite" class="vf-select">
                  <option value="amazon">Amazon</option><option value="shopify">Shopify</option>
                  <option value="独立站">独立站</option>
                </select>
              </div>
            </div>
            <div class="vf-form-hint" id="vfNameHint">LINUX DO · 新的理想型社区</div>
          </div>

          <!-- 4. 生成参数设置 -->
          <div class="vf-section">
            <div class="vf-section-head">
              <div class="vf-section-num">④</div>
              <div class="vf-section-title">生成参数设置</div>
              <div class="vf-section-desc">平台、地区、语言、风格等成参配置项</div>
            </div>
            <div class="vf-form-row">
              <div class="vf-field vf-field-inline" style="flex:1;min-width:0">
                <select id="vfPlatform" class="vf-select">
                  <option value="amazon">淘宝/天猫</option><option value="amazon_us">Amazon US</option>
                  <option value="amazon_eu">Amazon EU</option><option value="shopify">Shopify</option>
                </select>
                <span class="vf-input-label">平台</span>
              </div>
              <div class="vf-field vf-field-inline" style="flex:1;min-width:0">
                <select id="vfRegion" class="vf-select">
                  <option value="US">中国大陆</option><option value="US">美国</option>
                  <option value="DE">德国</option><option value="JP">日本</option>
                  <option value="UK">英国</option>
                </select>
                <span class="vf-input-label">大区</span>
              </div>
              <div class="vf-field vf-field-inline" style="flex:1;min-width:0">
                <select id="vfLang" class="vf-select">
                  <option value="zh">中文</option><option value="en">English</option>
                  <option value="de">Deutsch</option><option value="ja">日本語</option>
                </select>
                <span class="vf-input-label">语言</span>
              </div>
              <div class="vf-field vf-field-inline" style="flex:1.4;min-width:0">
                <select id="vfStyle" class="vf-select">
                  <option value="premium_clean">高级简洁</option><option value="ecommerce">电商白底</option>
                  <option value="lifestyle">生活方式</option><option value="minimal">极简</option>
                  <option value="luxury">奢华</option><option value="playful">活泼</option>
                </select>
                <span class="vf-input-label">高级简洁</span>
              </div>
            </div>
          </div>

          <!-- 5. 需求补充说明 -->
          <div class="vf-section">
            <div class="vf-section-head">
              <div class="vf-section-num">⑤</div>
              <div class="vf-section-title">需求补充说明</div>
              <div class="vf-section-desc">补充目标人群、价值定位等需求描述</div>
            </div>
            <div class="vf-form-group">
              <label class="vf-label">目标人群</label>
              <input id="vfAudience" class="vf-input" placeholder="例如：饲养猫、宝妈、送礼人群、送礼人群" value="Cat owners, pet parents looking for quiet hydration solutions" />
            </div>
            <div class="vf-form-group">
              <label class="vf-label">价格/定位</label>
              <input id="vfPricePos" class="vf-input" placeholder="例如：中高端、性价比、入门款" value="Mid-range premium pet product" />
            </div>
            <div class="vf-form-group">
              <label class="vf-label">核心卖点</label>
              <textarea id="vfSellingPts" class="vf-textarea" rows="2" placeholder="例如：超静音水泵、易拆洗设计、大容量水箱…">Ultra-quiet pump (<30dB), easy-to-clean modular design, 3L large capacity, BPA-free materials, LED indicator</textarea>
            </div>
            <div class="vf-form-group">
              <label class="vf-label">补充要求</label>
              <textarea id="vfExtraReq" class="vf-textarea" rows="2" placeholder="例如：需展示尺寸对比、儿童或卡片风格…">Show size comparison with everyday objects, include lifestyle scene with cat drinking happily</textarea>
            </div>
          </div>

          <!-- 6. 一键生成功能 -->
          <div class="vf-section vf-gen-section">
            <label class="vf-toggle">
              <input type="checkbox" id="vfBatchRef" />
              <span class="vf-toggle-slider"></span>
              <span class="vf-toggle-label">一键批量参考图模式</span>
            </label>
            <button class="btn btn-primary vf-gen-btn" id="vfGen" type="button">
              <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/></svg>
              生成 <span id="vfGenCount">6</span> 张详情页
            </button>
          </div>

        </div>

        <!-- ===== 右侧：结果展示面板 ===== -->
        <div class="vf-output-panel">
          <!-- 版本对比功能区 -->
          <div class="vf-output-toolbar">
            <div class="vf-ver-group">
              <span class="vf-ver-label">出图历史 / 版本对比</span>
              <div class="ver-selects">
                <select id="vfVer1" class="vf-ver-select"><option value="">选择版本 1</option></select>
                <select id="vfVer2" class="vf-ver-select"><option value="">选择版本 2</option></select>
              </div>
              <button class="vf-btn-xs" id="vfClearHistory" type="button">清空历史</button>
            </div>
            <div class="vf-ver-actions">
              <span class="vf-feature-tag">① 版本对比功能</span>
              <p class="vf-feature-desc">选择不同版本进行并排查看生成效果差异</p>
            </div>
          </div>

          <!-- 详情情页标题栏 -->
          <div class="vf-result-header">
            <div class="vf-result-title-row">
              <h3 class="vf-result-title">详情情页</h3>
              <span class="vf-result-sub">上屏商品，一次生成 <b id="vfTotalCount">6</b> 张详情页素材。</span>
            </div>
            <div class="vf-result-actions">
              <button class="vf-action-btn" id="vfActExpand" title="展开长图">
                <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M15 3h6v6M9 21H3v-6M21 3l-7 7M3 21l7-7"/></svg> 展开长图
              </button>
              <button class="vf-action-btn" id="vfActDownload" title="打包下载">
                <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M7 10l5 5 5-5M12 15V3"/></svg> 打包下载
              </button>
              <button class="vf-action-btn" id="vfActRegen" title="重新生成">
                <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.8"><polyline points="23,4 23,10 17,10"/><path d="M20.49,15a9,9,0,1,1-2.12-9.36L23,10"/></svg> 重新生成
              </button>
            </div>
          </div>

          <!-- 结果展示区域 -->
          <div class="vf-results" id="vfResults">
            <div class="vf-empty-state">
              <svg viewBox="0 0 24 24" width="48" height="48" fill="none" stroke="var(--txt-3)" stroke-width="1.2"><rect x="3" y="3" width="18" height="18" rx="3"/><circle cx="8.5" cy="8.5" r="1.5"/><path d="M21 15l-5-5L5 21"/></svg>
              <p>等待生成详情页图片</p>
              <span>在左侧填写参数后点击「生成」按钮</span>
            </div>
          </div>

          <!-- 右侧功能说明 -->
          <div class="vf-sidebar-tips">
            <div class="vf-tip-card">
              <div class="vf-tip-badge">② 操作功能按钮</div>
              <p>预览长图、打包下载、重新生成等操作</p>
            </div>
            <div class="vf-tip-card">
              <div class="vf-tip-badge">③ 结果展示区域</div>
              <p>展示生成的详情页图片，支持预览和查看</p>
            </div>
            <div class="vf-tip-card">
              <div class="vf-tip-badge">④ 图片操作功能</div>
              <p>支持下载原始图片、查看任务ID等信息</p>
            </div>
          </div>
        </div>
      </div>
    `;

    /* ---- 上传交互：参考图 ---- */
    const refZone = view.querySelector("#vfRefZone");
    const refInput = view.querySelector("#vfRefInput");
    const refPreview = view.querySelector("#vfRefPreview");

    function handleRefFiles(files) {
      Array.from(files).forEach((f) => {
        if (!f.type.startsWith("image/")) return;
        const reader = new FileReader();
        reader.onload = (e) => {
          refFiles.push({ name: f.name, dataUrl: e.target.result });
          renderPreviews(refPreview, refFiles, "ref");
        };
        reader.readAsDataURL(f);
      });
    }

    view.querySelector("#vfRefAdd").addEventListener("click", () => refInput.click());
    refInput.addEventListener("change", () => { handleRefFiles(refInput.files); refInput.value = ""; });

    refZone.addEventListener("dragover", (e) => { e.preventDefault(); refZone.classList.add("vf-drag-over"); });
    refZone.addEventListener("dragleave", () => refZone.classList.remove("vf-drag-over"));
    refZone.addEventListener("drop", (e) => { e.preventDefault(); refZone.classList.remove("vf-drag-over"); handleRefFiles(e.dataTransfer.files); });

    /* ---- 上传交互：商品素材 ---- */
    const matZone = view.querySelector("#vfMatZone");
    const matInput = view.querySelector("#vfMatInput");
    const matPreview = view.querySelector("#vfMatPreview");

    function handleMatFiles(files) {
      Array.from(files).forEach((f) => {
        if (!f.type.startsWith("image/")) return;
        const reader = new FileReader();
        reader.onload = (e) => {
          matFiles.push({ name: f.name, dataUrl: e.target.result });
          renderPreviews(matPreview, matFiles, "mat");
        };
        reader.readAsDataURL(f);
      });
    }

    view.querySelector("#vfMatAdd").addEventListener("click", () => matInput.click());
    matInput.addEventListener("change", () => { handleMatFiles(matInput.files); matInput.value = ""; });
    view.querySelector("#vfMatDel").addEventListener("click", () => { matFiles = []; renderPreviews(matPreview, matFiles, "mat"); });

    matZone.addEventListener("dragover", (e) => { e.preventDefault(); matZone.classList.add("vf-drag-over"); });
    matZone.addEventListener("dragleave", () => matZone.classList.remove("vf-drag-over"));
    matZone.addEventListener("drop", (e) => { e.preventDefault(); matZone.classList.remove("vf-drag-over"); handleMatFiles(e.dataTransfer.files); });

    /* ---- 名称输入联动提示 ---- */
    view.querySelector("#vfName").addEventListener("input", (e) => {
      const v = e.target.value.trim();
      view.querySelector("#vfNameHint").textContent = v ? `${v} · Amazon Product Visual` : "LINUX DO · 新的理想型社区";
    });

    /* ---- 生成按钮 ---- */
    view.querySelector("#vfGen").addEventListener("click", async () => {
      const btn = view.querySelector("#vfGen");
      btn.disabled = true;
      btn.innerHTML = `<svg class="spin" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="#fff" stroke-width="2"><path d="M21 12a9 9 0 11-6.219-8.56"/></svg> 生成中…`;

      const resultsEl = view.querySelector("#vfResults");
      resultsEl.innerHTML = `<div class="vf-loading-state"><div class="scan-dots"><span class="s"></span><span class="s"></span><span class="s"></span><span class="s"></span><span class="s"></span></div><p>AI 正在分析产品并生成详情页方案…</p></div>`;

      try {
        const name = view.querySelector("#vfName").value.trim() || "Product";
        const c = Workspace.get();
        const r = await API.visual({
          product_name: name,
          niche_keyword: c.niche_keyword || c.category || "",
          market_positioning: view.querySelector("#vfPricePos").value.trim(),
          voc_pain_points: view.querySelector("#vfSellingPts").value.split(/[,，]/).map((s) => s.trim()).filter(Boolean),
          competitor_insights: view.querySelector("#vfExtraReq").value.trim(),
          style: view.querySelector("#vfStyle").value,
          country: view.querySelector("#vfRegion").value,
          ...(Workspace.productId ? { product_id: Workspace.productId } : {}),
        });

        renderVFResults(resultsEl, r, name);
        addVersionHistory(view, r);
      } catch (e) {
        resultsEl.innerHTML = `<div class="vf-error-state"><p>⚠ 生成失败：${esc(e.message)}</p><button class="btn btn-primary" onclick="this.closest('.vf-results').querySelectorAll('.vf-error-state')[0].remove()">关闭</button></div>`;
      } finally {
        btn.disabled = false;
        btn.innerHTML = `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/></svg> 生成 <span id="vfGenCount">6</span> 张详情页`;
      }
    });
    prefillWorkspace(view, {
      "#vfName": "name", "#vfCategory": "category", "#vfCountry": "country",
      "#vfAudience": "_target_audience", "#vfPricePos": "_price_positioning", "#vfSellingPts": "_selling_points",
    });

    /* ---- 自动填充 VOC / 竞品数据 ---- */
    view.querySelector("#vfRefLib").addEventListener("click", () => {
      let filled = 0;
      try {
        const v = JSON.parse(sessionStorage.getItem("lastVoc") || "null");
        if (v && v.pains && v.pains.length) {
          view.querySelector("#vfSellingPts").value = v.pains.join(", ");
          filled++;
        }
      } catch (_) {}
      try {
        const c = JSON.parse(sessionStorage.getItem("lastCompetitor") || "null");
        if (c && c.text) {
          view.querySelector("#vfExtraReq").value = c.text;
          filled++;
        }
      } catch (_) {}
      toast(filled ? `已自动填充 ${filled} 项（VOC / 竞品）` : "暂无可填充的 VOC / 竞品数据，请先运行对应分析");
    });
  },

  /* ---------- 总报告（汇总市场机会 / VOC / 竞品 / 利润，单页总览） ---------- */
  async report(view) {
    const research = JSON.parse(sessionStorage.getItem("lastResearch") || "null");
    const voc = JSON.parse(sessionStorage.getItem("lastVoc") || "null");
    const comp = JSON.parse(sessionStorage.getItem("lastCompetitor") || "null");
    const hasAny = research || voc || comp;

    if (!hasAny) {
      view.innerHTML = `
        <div class="eyebrow"><span class="pulse"></span>MASTER REPORT</div>
        <h1 class="page-title">产品<span class="gradient-text">总报告</span></h1>
        <div class="card empty" style="margin-top:30px">
          <div class="big">还没有可用数据</div>
          <p>先运行「AI 市场雷达」（蓝海挖掘）、「VOC 分析」或「竞品分析」，本页会自动汇总成一份完整的总报告。</p>
          <button class="btn btn-primary" style="margin-top:18px" onclick="location.hash='#/'">去发射雷达 →</button>
        </div>`;
      return;
    }

    const tags = [];
    if (research) tags.push("蓝海挖掘");
    if (voc) tags.push("VOC 分析");
    if (comp) tags.push("竞品分析");

    view.innerHTML = `
      <div class="eyebrow"><span class="pulse"></span>MASTER REPORT</div>
      <h1 class="page-title">产品<span class="gradient-text">总报告</span></h1>
      <p class="page-sub">汇总 ${tags.map((t) => `<span class="prod-chip">${esc(t)}</span>`).join(" ")} 的 AI 研判，一页看清该不该做、怎么做。</p>
      <div class="card insight" style="margin-top:18px"><div class="eyebrow">执行摘要</div><p id="repSum" style="font-size:1.05rem;line-height:1.6"></p></div>
      <div id="repBody"></div>`;

    const body = view.querySelector("#repBody");
    const execBits = [];

    /* —— 一、市场机会（蓝海挖掘） —— */
    if (research) {
      const ops = research.products || [];
      const top = ops[0];
      const html = `
        <h3 class="section-h" style="margin-top:26px">① 市场机会（蓝海挖掘）</h3>
        <p class="page-sub" style="margin-top:0">${esc(research.country)} · ${esc(research.category)} · 预算 $${Number(research.budget_usd).toLocaleString()} · 命中 ${ops.length} 个潜力产品</p>
        <div class="prod-grid stagger">
          ${ops.slice(0, 6).map((o) => `
            <div class="card prod-card" onclick="openDetail(${JSON.stringify(o).replace(/"/g, "&quot;")})">
              <div class="top"><div><div class="rank">#${o.rank} 潜力产品</div><h3>${esc(o.product_name)}</h3></div>${scoreRing(o.opportunity_score, 52)}</div>
              <div class="stats">
                <div class="stat"><b>${money(o.market_size_monthly_usd)}</b><span>月规模</span></div>
                <div class="stat"><b>${(o.market_size_growth_yoy * 100).toFixed(0)}%</b><span>年增速</span></div>
                <div class="stat"><span class="badge ${o.competition_level.toLowerCase()}">${o.competition_level} 竞争</span></div>
              </div>
              <div class="pains">${o.top_pain_points.slice(0, 2).map((p) => `<div class="pain">${esc(p.pain)}</div>`).join("")}</div>
              <div class="rec">${esc(o.entry_recommendation)}</div>
            </div>`).join("")}
        </div>`;
      body.insertAdjacentHTML("beforeend", html);
      execBits.push(`市场最值得切入的是「${top.product_name}」（机会评分 ${top.opportunity_score}，竞争度 ${top.competition_level}，月规模约 ${money(top.market_size_monthly_usd)}）`);
    }

    /* —— 二、用户痛点（VOC） —— */
    if (voc && voc.pains && voc.pains.length) {
      const html = `
        <h3 class="section-h" style="margin-top:26px">② 用户痛点（VOC 分析）</h3>
        <p class="page-sub" style="margin-top:0">关键词「${esc(voc.kw || "")}」的 ${voc.pains.length} 条高频痛点</p>
        <div class="voice-list">
          ${voc.pains.slice(0, 8).map((p, i) => `<div class="card voice">${esc(p)}</div>`).join("")}
        </div>`;
      body.insertAdjacentHTML("beforeend", html);
      execBits.push(`用户最在意的是「${voc.pains[0]}」`);
    }

    /* —— 三、竞争格局（竞品分析） —— */
    if (comp && comp.text) {
      const html = `
        <h3 class="section-h" style="margin-top:26px">③ 竞争格局（竞品分析）</h3>
        <p class="page-sub" style="margin-top:0">${esc(comp.niche || "")}</p>
        <div class="card insight">${esc(comp.text)}</div>`;
      body.insertAdjacentHTML("beforeend", html);
    }

    /* —— 四、综合建议 —— */
    const go = research && research.products && research.products[0] && research.products[0].competition_level === "Low";
    const advise = go
      ? "综合研判：市场机会评分高、竞争偏低，建议优先立项验证，先用最小成本做出 MVP 验证前 3 个机会。"
      : "综合研判：机会与竞争并存，建议先以差异化卖点切入（对标用户未被满足的痛点），小批量验证后再放量。";
    const adviseHtml = `
      <h3 class="section-h" style="margin-top:26px">④ 综合建议</h3>
      <div class="card insight" style="border-left:3px solid var(--ai-3)">${esc(advise)}</div>
      <div class="prov-badge live" style="margin-top:14px">总报告由 AI 基于本地会话内的市场 / VOC / 竞品分析自动汇总</div>`;
    body.insertAdjacentHTML("beforeend", adviseHtml);

    /* —— 执行摘要打字机 —— */
    const summary = execBits.length
      ? "AI 总览：" + execBits.join("；") + "。" + advise
      : advise;
    typeWriter(view.querySelector("#repSum"), summary, 12);
  },

  /* ---------- 利润分析 ---------- */
  profit(view) {
    view.innerHTML = `
      <div class="eyebrow"><span class="pulse"></span>PROFIT ANALYSIS</div>
      <h1 class="page-title">产品<span class="gradient-text">利润测算</span></h1>
      <p class="page-sub">不只判断有没有市场，更判断值不值得投入。填入真实成本（手动 / Excel 上传），平台费(FBA/佣金)由 amazon_connector 费率表提供，AI 测算利润、销量与风险。</p>
      ${provBarHtml(["amazon"])}

      <div class="card hero-panel fade-up">
        <div class="param-row" style="flex-wrap:wrap">
          <div class="field" style="min-width:180px"><label>产品名称</label><input id="pName" placeholder="Cat Water Fountain" /></div>
          <div class="field" style="min-width:110px"><label>站点</label><select id="pCountry">${COUNTRIES.map((c) => `<option ${c.code === "US" ? "selected" : ""}>${c.code}</option>`).join("")}</select></div>
          <div class="field" style="min-width:140px"><label>类目</label><input id="pCat" placeholder="Pet / Kitchen" /></div>
          <div class="field" style="min-width:130px"><label>竞争强度</label><select id="pComp"><option value="">未知</option><option value="low">低</option><option value="medium">中</option><option value="high">高</option></select></div>
        </div>
        <div class="param-row" style="flex-wrap:wrap;margin-top:8px">
          <div class="field" style="min-width:130px"><label>售价 (USD)</label><input id="pPrice" type="number" value="29.99" /></div>
          <div class="field" style="min-width:120px"><label>产品成本</label><input id="pCost" type="number" value="8" /></div>
          <div class="field" style="min-width:120px"><label>头程物流</label><input id="pShip" type="number" value="2" /></div>
          <div class="field" style="min-width:110px"><label>佣金率 %</label><input id="pRef" type="number" value="15" /></div>
          <div class="field" style="min-width:110px"><label>FBA费</label><input id="pFba" type="number" value="3.5" /></div>
          <div class="field" style="min-width:110px"><label>广告ACOS %</label><input id="pAcos" type="number" value="15" /></div>
          <div class="field" style="min-width:110px"><label>其他成本</label><input id="pOther" type="number" value="1" /></div>
        </div>
        <div class="param-row" style="flex-wrap:wrap;margin-top:8px">
          <div class="field" style="min-width:150px"><label>预期月销量(可选)</label><input id="pUnits" type="number" placeholder="留空则预测" /></div>
          <div class="field" style="min-width:130px"><label>月固定成本</label><input id="pFixed" type="number" value="400" /></div>
          <div class="field" style="min-width:130px"><label>首单投入</label><input id="pInv" type="number" value="3000" /></div>
        </div>
        <div class="param-row" style="margin-top:12px;align-items:center">
          <button class="btn btn-primary" id="pRun">测算盈利</button>
          <button class="btn btn-ghost" id="pExcelBtn" type="button">⬆ 上传成本表(Excel/CSV)</button>
          <input type="file" id="pExcel" accept=".xlsx,.xls,.csv" style="display:none" />
          <select id="pSource" style="margin-left:auto" title="数据来源">
            <option value="manual">手动输入</option><option value="excel">Excel 上传</option>
          </select>
        </div>
      </div>

      <div id="profitOut"></div>`;

    prefillWorkspace(view, { "#pName": "name", "#pCountry": "country", "#pCat": "category" });
    /* 额外：从 Workspace 扩展字段预填估算售价与竞争强度（prefillWorkspace 不支持扩展字段，手动处理） */
    const c = Workspace.get();
    if (c) {
      const priceNode = view.querySelector("#pPrice");
      if (priceNode && !priceNode.value && c._est_price) priceNode.value = c._est_price;
      const compNode = view.querySelector("#pComp");
      if (compNode && !compNode.value && c._competition) compNode.value = c._competition.toLowerCase();
    }
    const out = view.querySelector("#profitOut");

    const gather = () => ({
      product_name: view.querySelector("#pName").value.trim() || "Product",
      country: view.querySelector("#pCountry").value,
      category: view.querySelector("#pCat").value.trim() || null,
      competition_level: view.querySelector("#pComp").value || null,
      selling_price: parseFloat(view.querySelector("#pPrice").value || "0"),
      product_cost: parseFloat(view.querySelector("#pCost").value || "0"),
      shipping_cost: parseFloat(view.querySelector("#pShip").value || "0"),
      referral_fee_rate: parseFloat(view.querySelector("#pRef").value || "0") / 100,
      fba_fee: parseFloat(view.querySelector("#pFba").value || "0"),
      ad_acos: parseFloat(view.querySelector("#pAcos").value || "0") / 100,
      other_cost_per_unit: parseFloat(view.querySelector("#pOther").value || "0"),
      monthly_units: view.querySelector("#pUnits").value ? parseInt(view.querySelector("#pUnits").value, 10) : null,
      monthly_fixed_cost: parseFloat(view.querySelector("#pFixed").value || "0"),
      initial_investment: parseFloat(view.querySelector("#pInv").value || "0"),
      cost_source: view.querySelector("#pSource").value,
      product_id: Workspace.productId || null,
    });

    view.querySelector("#pRun").addEventListener("click", async () => {
      const btn = view.querySelector("#pRun"); btn.disabled = true; btn.textContent = "测算中…";
      try { const r = await API.profit(gather()); renderProfit(out, r); refreshProvenance(view.querySelector(".prov-bar"), ["amazon"]); }
      catch (e) { out.innerHTML = `<div class="card empty">测算失败：${esc(e.message)}</div>`; }
      finally { btn.disabled = false; btn.textContent = "测算盈利"; }
    });

    view.querySelector("#pExcelBtn").addEventListener("click", () => view.querySelector("#pExcel").click());
    view.querySelector("#pExcel").addEventListener("change", async (e) => {
      const file = e.target.files[0]; if (!file) return;
      try {
        const d = await API.profitUploadCost(file);
        if (!d.ok) { toast("解析失败：" + (d.error || "")); return; }
        fillCostFields(view, d.fields);
        view.querySelector("#pSource").value = "excel";
        toast("已从「" + (d.filename || "成本表") + "」读入成本字段");
      } catch (err) { toast("上传失败：" + err.message); }
      e.target.value = "";
    });
  },
};

/* —— Listing 渲染 —— */
function imageBoxSVG() {
  return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="9" cy="9" r="2"/><path d="M21 15l-5-5L5 21"/></svg>`;
}

function imagePlanHTML(images) {
  return `<div class="img-grid">${images.map((im) => `
    <div class="img-card">
      <div class="box">${imageBoxSVG()}</div>
      <div class="scene">${esc(im.scene)}</div>
      <div class="ar">比例 ${esc(im.aspect_ratio)}</div>
      <div class="pr">${esc(im.description)}</div>
    </div>`).join("")}</div>`;
}

function renderListing(out, r) {
  out.innerHTML = `
    <div class="card gen-block"><h4>📝 标题 Title</h4><div class="content" id="gTitle"></div></div>
    <div class="card gen-block"><h4>✦ 五点描述 Bullet Points</h4><div class="content">${r.bullet_points.map((b) => `<div class="bullet">${esc(b)}</div>`).join("")}</div></div>
    <div class="card gen-block"><h4>📄 详情描述 Description</h4><div class="content">${esc(r.description)}</div></div>
    <div class="card gen-block"><h4>🔑 后台关键词 Keywords</h4><div class="content">${r.search_terms.map((k) => `<span class="prod-chip">${esc(k)}</span>`).join(" ")}</div></div>
    <div class="card gen-block"><h4>🖼 图片方案 Image Plan (${r.image_plan.length})</h4>${imagePlanHTML(r.image_plan)}</div>
    <div class="card insight" style="margin-bottom:14px"><b>完整度 ${r.completeness_score}/100</b><div class="content" style="margin-top:8px;font-size:12.5px;color:var(--txt-1)">${r.compliance_notes.map((n) => `• ${esc(n)}`).join("<br>")}</div></div>`;
  typeWriter(out.querySelector("#gTitle"), r.title, 6);
}

function renderImages(out, r) {
  out.innerHTML = `
    <div class="card insight" style="margin-top:18px"><p>${esc(r.composition_strategy)}</p></div>
    <div class="img-grid">${r.shots.map((s) => `
      <div class="img-card">
        <div class="box">${imageBoxSVG()}</div>
        <div class="scene">${esc(s.scene)}</div>
        <div class="ar">${esc(s.aspect_ratio)} · 优先级 ${s.priority}</div>
        <div class="pur">用途：${esc(s.purpose)}</div>
        <div class="pr">${esc(s.description)}</div>
      </div>`).join("")}</div>
    <div class="card insight" style="margin-top:14px"><b>品牌一致性：</b> ${esc(r.brand_guidance)}</div>`;
}

/* —— 视觉工厂：上传预览渲染 —— */
function renderPreviews(container, files, type) {
  if (!files.length) { container.innerHTML = ""; return; }
  container.innerHTML = `<div class="vf-thumb-grid">${files.map((f, i) => `
    <div class="vf-thumb" data-idx="${i}">
      <img src="${f.dataUrl}" alt="${esc(f.name)}" />
      <span class="vf-thumb-name">${esc(f.name)}</span>
      <button class="vf-thumb-del" data-type="${type}" data-idx="${i}" type="button">×</button>
    </div>`).join("")}</div>`;
  container.querySelectorAll(".vf-thumb-del").forEach((btn) => {
    btn.addEventListener("click", () => {
      const t = btn.dataset.type, idx = parseInt(btn.dataset.idx, 10);
      if (t === "ref") { refFiles.splice(idx, 1); renderPreviews(container, refFiles, "ref"); }
      else { matFiles.splice(idx, 1); renderPreviews(container, matFiles, "mat"); }
    });
  });
}

/* 全局引用（供删除回调使用） */
let refFiles = [];
let matFiles = [];

/* —— 视觉工厂：结果渲染（新版左右分栏） —— */
function vfResultCard(im, i) {
  const slotLabels = ["首屏主视觉", "卖点总览", "核心功能展示", "场景生活方式", "尺寸规格对比", "社会证明/评价", "信任背书"];
  const label = slotLabels[i] || im.slot || `详情页 ${i + 1}`;
  return `
    <div class="vfr-card" data-slot="${i}">
      <div class="vfr-card-header">
        <div class="vfr-slot-num">${String(i + 1).padStart(2, "0")}</div>
        <div class="vfr-slot-info">
          <div class="vfr-slot-name">${esc(label)}</div>
          <div class="vfr-slot-meta">${esc(im.purpose || "")} · ${esc(im.aspect_ratio || "1:1")}</div>
        </div>
        <div class="vfr-slot-badge ${i === 0 ? "badge-primary" : ""}">${i === 0 ? "高亮位" : "辅助位"}</div>
      </div>
      <div class="vfr-card-body">
        <!-- 图片预览区 -->
        <div class="vfr-preview">
          ${im.image_url
            ? `<img class="vfr-img-real" src="${esc(im.image_url)}" alt="${esc(im.slot || 'AI生成')}" loading="lazy" onerror="this.style.display='none';this.nextElementSibling.style.display='flex';" />
                <div class="vfr-img-placeholder" style="display:none">
                  <svg viewBox="0 0 24 24" width="36" height="36" fill="none" stroke="var(--txt-3)" stroke-width="1.2"><rect x="3" y="3" width="18" height="18" rx="3"/><circle cx="8.5" cy="8.5" r="1.5"/><path d="M21 15l-5-5L5 21"/></svg>
                  <span>图片加载失败</span>
                </div>`
            : `<div class="vfr-img-placeholder">
                <svg viewBox="0 0 24 24" width="36" height="36" fill="none" stroke="var(--txt-3)" stroke-width="1.2"><rect x="3" y="3" width="18" height="18" rx="3"/><circle cx="8.5" cy="8.5" r="1.5"/><path d="M21 15l-5-5L5 21"/></svg>
                <span>AI 生成预览</span>
              </div>`
          }
          ${im.generated_scene ? `<div class="vfr-scene-tag">${esc(im.generated_scene)}</div>` : ""}
        </div>
        <!-- 信息区 -->
        <div class="vfr-info">
          <div class="vfr-concept"><b>创意概念：</b>${esc(im.concept || im.purpose || "")}</div>
          <div class="vfr-diff"><b>差异化要点：</b>${esc(im.differentiation_point || "-")}</div>
          ${im.pain_addressed ? `<div class="vfr-pain">🎯 命中痛点：${esc(im.pain_addressed)}</div>` : ""}
        </div>
      </div>
      <!-- Prompt 展开区 -->
      <details class="vfr-prompt">
        <summary><svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14,2 14,8 20,8"/></svg> 生成 Prompt</summary>
        <pre class="vfr-prompt-text">${esc(im.generation_prompt || "")}</pre>
        <button class="copy-btn vfr-copy-btn" type="button">复制 Prompt</button>
      </details>
      <!-- 操作按钮行 -->
      <div class="vfr-actions">
        <button class="vfr-action-btn" title="展开预览"><svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M15 3h6v6M9 21H3v-6M21 3l-7 7M3 21l7-7"/></svg> 展开</button>
        <button class="vfr-action-btn" title="下载图片"><svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M7 10l5 5 5-5M12 15V3"/></svg> 下载</button>
        <button class="vfr-action-btn" title="重新生成此张"><svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="1.8"><polyline points="23,4 23,10 17,10"/><path d="M20.49,15a9,9,0,1,1-2.12-9.36L23,10"/></svg> 重生</button>
        <button class="vfr-action-btn vfr-id-btn" title="查看任务ID"><svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg> ID</button>
      </div>
      <!-- 质检标签 -->
      ${im.quality_checks && im.quality_checks.length ? `
        <div class="vfr-qchecks">${im.quality_checks.map((q) => `<span class="qc">${esc(q)}</span>`).join("")}</div>` : ""}
    </div>`;
}

function renderVFResults(container, r, productName) {
  const s = r.strategy || {};
  const plan = r.image_plan || [];
  container.innerHTML = `
    <!-- 质量评分头部 -->
    <div class="vfr-header-card">
      <div class="vfr-score-area">
        ${scoreRing(r.quality_score, 80)}
        <div class="vfr-score-text">
          <div class="vfr-score-label">${esc(productName || "")} · 视觉质量评分</div>
          <div class="vfr-score-value">综合 <b style="color:${scoreColor(r.quality_score)}">${Math.round(r.quality_score)}</b> / 100</div>
        </div>
      </div>
      <div class="vfr-strategy-mini">
        <div class="vfr-strat-item"><span class="k">主图策略</span><p id="vfrMainStrat">${esc(s.main_image_strategy || "")}</p></div>
        <div class="vfr-strat-item"><span class="k">色彩方向</span><p>${esc(s.color_direction || "")}</p></div>
        <div class="vfr-strat-item"><span class="k">情感钩子</span><p>${esc(s.emotional_hook || "")}</p></div>
      </div>
    </div>

    <!-- 策略维度卡片 -->
    <div class="vfr-strategy-card">
      <h4 class="vfr-section-title">🎯 视觉策略总览</h4>
      <div class="vfr-facets">
        <div class="vff"><span class="k">视觉角度</span><div>${(s.visual_angles || []).map((a) => `<span class="prod-chip">${esc(a)}</span>`).join(" ")}</div></div>
        <div class="vff"><span class="k">差异化锚点</span><div>${esc(s.differentiation || "")}</div></div>
        <div class="vff"><span class="k">构图策略</span><div>${esc(r.composition_strategy || "")}</div></div>
      </div>
    </div>

    <!-- 详情页图片网格 -->
    <h4 class="vfr-section-title" style="margin-top:18px">🖼 详情页图片规划（${plan.length} 张）</h4>
    <div class="vfr-grid">${plan.map((im, i) => vfResultCard(im, i)).join("")}</div>

    <!-- 优化建议 -->
    ${(r.optimization_suggestions || []).length ? `
      <div class="vfr-suggest-card" style="margin-top:16px">
        <h4 class="vfr-section-title">💡 优化建议</h4>
        ${r.optimization_suggestions.map((t) => `<div class="bullet">${esc(t)}</div>`).join("")}
      </div>` : ""}
  `;

  /* 打字机效果 */
  const mainEl = container.querySelector("#vfrMainStrat");
  if (mainEl) typeWriter(mainEl, s.main_image_strategy || "", 8);

  /* 复制按钮 */
  container.querySelectorAll(".vfr-copy-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const pre = btn.closest(".vfr-prompt").querySelector(".vfr-prompt-text");
      const text = pre ? pre.textContent : "";
      const done = () => toast("已复制 Prompt");
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(done).catch(() => fallbackCopy(text, done));
      } else fallbackCopy(text, done);
    });
  });

  /* 更新计数 */
  const tc = document.getElementById("vfTotalCount");
  if (tc) tc.textContent = String(plan.length);

  /* 图片展开 / 灯箱：点图片或「展开」按钮弹出大图预览 */
  container.querySelectorAll(".vfr-card").forEach((card) => {
    const idx = parseInt(card.dataset.slot, 10);
    const im = plan[idx] || {};
    const openOne = () => openVFImageLightbox([{ url: im.image_url, label: im.slot || ("详情页 " + (idx + 1)) }]);
    const prev = card.querySelector(".vfr-preview");
    if (prev) { prev.style.cursor = "zoom-in"; prev.addEventListener("click", openOne); }
    const expBtn = card.querySelector('.vfr-action-btn[title="展开预览"]');
    if (expBtn) expBtn.addEventListener("click", openOne);
  });

  /* 展开长图：把所有详情页图纵向拼成一张长图预览 */
  const longBtn = document.getElementById("vfActExpand");
  if (longBtn) longBtn.onclick = () =>
    openVFImageLightbox(plan.map((im, i) => ({ url: im.image_url, label: im.slot || ("详情页 " + (i + 1)) })));
}

/* 视觉工厂图片灯箱 */
function openVFImageLightbox(items) {
  const mask = document.createElement("div");
  mask.className = "vf-lightbox-mask";
  const body = (items || []).map((it) => `
    <div class="vf-lb-item">
      ${it.url
        ? `<img src="${esc(it.url)}" alt="${esc(it.label || "")}" />`
        : `<div class="vf-lb-empty"><div class="vfr-img-placeholder"><svg viewBox="0 0 24 24" width="40" height="40" fill="none" stroke="var(--txt-3)" stroke-width="1.2"><rect x="3" y="3" width="18" height="18" rx="3"/><circle cx="8.5" cy="8.5" r="1.5"/><path d="M21 15l-5-5L5 21"/></svg><span>暂无生成结果</span></div></div>`}
      <div class="vf-lb-cap">${esc(it.label || "")}</div>
    </div>`).join("");
  mask.innerHTML = `
    <div class="vf-lightbox">
      <div class="vf-lb-head"><span>图片预览（点击外部关闭）</span><button class="vf-lb-close" type="button">✕</button></div>
      <div class="vf-lb-scroll">${body}</div>
    </div>`;
  mask.addEventListener("click", (e) => {
    if (e.target === mask || e.target.closest(".vf-lb-close")) mask.remove();
  });
  document.addEventListener("keydown", function escClose(ev) {
    if (ev.key === "Escape") { mask.remove(); document.removeEventListener("keydown", escClose); }
  });
  document.body.appendChild(mask);
}

/* —— 版本历史管理 —— */
const _vfVersionHistory = [];
function addVersionHistory(view, result) {
  const entry = {
    id: Date.now(),
    ts: new Date().toLocaleTimeString(),
    quality: result.quality_score,
    count: (result.image_plan || []).length,
    data: result,
  };
  _vfVersionHistory.unshift(entry);
  if (_vfVersionHistory.length > 10) _vfVersionHistory.pop();

  const sel1 = view.querySelector("#vfVer1");
  const sel2 = view.querySelector("#vfVer2");
  [sel1, sel2].forEach((sel) => {
    const prevVal = sel.value;
    sel.innerHTML = '<option value="">选择版本 ' + (sel === sel1 ? "1" : "2") + "</option>"
      + _vfVersionHistory.map((v) => `<option value="${v.id}">#${_vfVersionHistory.indexOf(v) + 1} [${v.ts}] 评分${Math.round(v.quality_score)} · ${v.count}张</option>`).join("");
    if (prevVal && _vfVersionHistory.find((v) => String(v.id) === prevVal)) sel.value = prevVal;
  });

  // 绑定版本切换事件
  [sel1, sel2].forEach((sel) => {
    sel.onchange = () => {
      const vId = sel.value;
      if (!vId) return;
      const entry = _vfVersionHistory.find((v) => String(v.id) === vId);
      if (entry) renderVFResults(view.querySelector("#vfResults"), entry.data, entry.data.product_name);
    };
  });

  // 清空历史
  view.querySelector("#vfClearHistory").onclick = () => {
    _vfVersionHistory.length = 0;
    [sel1, sel2].forEach((s) => { s.innerHTML = '<option value="">选择版本 ' + (s === sel1 ? "1" : "2") + "</option>"; });
    toast("已清空生成历史");
  };
}

function fallbackCopy(text, done) {
  try {
    const ta = document.createElement("textarea");
    ta.value = text; ta.style.position = "fixed"; ta.style.opacity = "0";
    document.body.appendChild(ta); ta.select();
    document.execCommand("copy"); ta.remove(); done();
  } catch (_) { toast("复制失败，请手动选择"); }
}

/* —— 广告渲染 —— */
function renderAds(out, r) {
  out.innerHTML = `
    <div class="metric-row">
      ${r.metrics.map((m) => `
        <div class="card metric"><div class="k">${esc(m.key)}</div><div class="v">${esc(m.value)}</div><div class="d ${m.trend}">${esc(m.delta)}</div></div>`).join("")}
    </div>
    <div class="card insight" style="margin-top:6px"><p id="adSum"></p></div>
    <h3 style="font-size:15px;margin:18px 0 10px;font-weight:620">可执行的广告动作</h3>
    ${r.campaign_actions.map((a) => `
      <div class="ad-action">
        <span class="tag ${a.campaign_type.toLowerCase()}">${esc(a.campaign_type)}·${esc(a.match_type)}</span>
        <div class="body"><div class="act">${esc(a.action)} — ${esc(a.target)}</div><div class="rat">${esc(a.rationale)}</div></div>
      </div>`).join("")}
    <div class="card insight" style="margin-top:14px"><b>预算建议：</b> ${esc(r.budget_recommendation)}</div>`;
  typeWriter(out.querySelector("#adSum"), r.summary, 7);
}

/* 机会详情抽屉 */
function openDetail(o) {
  /* 选品后自动预填到产品空间 */
  if (typeof selectProduct === "function") selectProduct(o);
  const mask = document.createElement("div");
  mask.className = "drawer-mask";
  mask.innerHTML = `
    <div class="card drawer">
      <span class="close" onclick="this.closest('.drawer-mask').remove()">✕</span>
      <div class="eyebrow"><span class="pulse"></span>OPPORTUNITY #${o.rank}</div>
      <h2 style="font-size:21px;font-weight:650">${esc(o.product_name)}</h2>
      <div class="detail-grid">
        ${subScoreRadar(o)}
        <div>
          <div style="display:flex;gap:10px;margin-bottom:12px">${scoreRing(o.opportunity_score, 64)}<div style="font-size:12.5px;color:var(--txt-2);align-self:center">综合机会评分<br><b style="color:#fff;font-size:15px">${o.opportunity_score} / 100</b></div></div>
          <div class="stats" style="display:flex;gap:18px;margin-bottom:12px">
            <div class="stat"><b>${money(o.market_size_monthly_usd)}</b><span>月规模</span></div>
            <div class="stat"><b>${(o.market_size_growth_yoy * 100).toFixed(0)}%</b><span>年增速</span></div>
            <div class="stat"><span class="badge ${o.competition_level.toLowerCase()}">${o.competition_level}</span></div>
          </div>
          <div class="pains">${o.top_pain_points.map((p) => `<div class="pain" style="font-size:13px;color:var(--txt-1)">• ${esc(p.pain)} <span style="color:var(--txt-3)">(severity ${p.severity})</span></div>`).join("")}</div>
        </div>
      </div>
      <div class="rec" style="margin-top:18px;font-size:13.5px;color:var(--txt-1);line-height:1.6;border-top:1px solid var(--border);padding-top:14px">${esc(o.entry_recommendation)}</div>
      <div style="margin-top:12px;padding:10px;background:rgba(255,255,255,0.04);border-radius:8px;font-size:12px;color:var(--txt-2)">
        ✅ 已自动预填到「利润 / Listing / 视觉 / 广告」页，切换过去即可看到
      </div>
    </div>`;
  mask.addEventListener("click", (e) => { if (e.target === mask) mask.remove(); });
  document.body.appendChild(mask);
}

/* Supervisor 派发的竞品 / 产品结果 → AI 报告抽屉（让 4 个 Agent 全部可呈现） */
function openAgentReport(kind, data, q) {
  if (!data) { toast("未获取到结果"); return; }
  const provConnectors = kind === "competitor" ? ["amazon", "review"] : ["amazon", "keyword", "review"];
  const mask = document.createElement("div");
  mask.className = "drawer-mask";
  let inner;
  if (kind === "competitor") {
    const comps = data.competitors || [];
    const compText = (data.summary || "") + "\n" + comps.map((c) => `${c.name}: ${c.weakness}`).join("\n");
    try { sessionStorage.setItem("lastCompetitor", JSON.stringify({ niche: data.niche_keyword || "", text: compText })); } catch (_) {}
    inner = `
      <div class="eyebrow"><span class="pulse"></span>COMPETITOR ANALYSIS</div>
      <h2 style="font-size:21px;font-weight:650">竞品分析 · ${esc(data.niche_keyword || q || "")}
        <span style="font-size:13px;color:var(--txt-2);font-weight:400"> @ ${esc(data.country || "US")}</span></h2>
      <div class="prod-grid stagger" style="margin-top:14px;grid-template-columns:1fr 1fr">
        ${comps.map((c, i) => `
          <div class="card voice fade-up" style="animation-delay:${(i * 0.05).toFixed(2)}s">
            <div class="ph" style="font-size:15px;font-weight:600">${esc(c.name)}</div>
            <div class="meta"><span>价格 <b>$${Math.round(c.price_usd)}</b></span><span>评分 ${c.rating}</span><span>评论 ${c.avg_reviews}</span></div>
            <div class="meta" style="margin-top:6px"><span>估计份额 <b>${(c.est_market_share * 100).toFixed(1)}%</b></span></div>
            <div class="fix" style="margin-top:8px">⚠️ 软肋：${esc(c.weakness)}</div>
          </div>`).join("")}
      </div>
      <div class="card insight" style="margin-top:14px"><p id="cSum"></p></div>
      ${provBarHtml(provConnectors)}`;
  } else { // product
    inner = `
      <div class="eyebrow"><span class="pulse"></span>PRODUCT OPPORTUNITY</div>
      <h2 style="font-size:21px;font-weight:650">产品机会判断 · ${esc(data.niche_keyword || q || "")}</h2>
      <div class="detail-grid" style="margin-top:14px">
        ${scoreRing(data.opportunity_score, 84)}
        <div>
          <div style="font-size:13px;color:var(--txt-2)">AI 研判结论</div>
          <div style="font-size:18px;font-weight:650;color:${scoreColor(data.opportunity_score)};margin:4px 0 10px">${esc(data.verdict)}</div>
          ${(data.reasons || []).map((r) => `<div class="pain" style="font-size:13px;color:var(--txt-1)">• ${esc(r)}</div>`).join("")}
        </div>
      </div>
      <div class="card insight" style="margin-top:14px"><b>推荐定位：</b> ${esc(data.recommended_positioning || "")}</div>
      ${provBarHtml(provConnectors)}`;
  }
  mask.innerHTML = `<div class="card drawer" style="max-width:780px">${inner}<span class="close" onclick="this.closest('.drawer-mask').remove()">✕</span></div>`;
  mask.addEventListener("click", (e) => { if (e.target === mask) mask.remove(); });
  document.body.appendChild(mask);
  refreshProvenance(mask.querySelector(".prov-bar"), provConnectors);
  const sum = mask.querySelector("#cSum");
  if (sum) typeWriter(sum, data.summary || "", 9);
}

/* 意图不明确时 → 澄清抽屉 + 可直接点击的示例 */
function showClarification(text, q) {
  const mask = document.createElement("div");
  mask.className = "drawer-mask";
  const suggestions = [
    "在美国厨房类目找预算5000的蓝海产品",
    "分析 wireless earbuds 的竞品",
    "分析 cat water fountain 的评论痛点",
    "判断 pets 类目 cat water fountain 是否值得做，预算3000",
  ];
  mask.innerHTML = `
    <div class="card drawer" style="max-width:540px">
      <span class="close" onclick="this.closest('.drawer-mask').remove()">✕</span>
      <div class="eyebrow"><span class="pulse"></span>NEED MORE INFO</div>
      <h2 style="font-size:19px;font-weight:650;margin-top:6px">AI 需要更多信息</h2>
      <p class="page-sub" style="margin-top:8px">${esc(text)}</p>
      <div class="prod-grid" style="margin-top:14px">
        ${suggestions.map((s) => `<div class="card sug" data-q="${esc(s)}" style="padding:11px 13px;cursor:pointer">${esc(s)}</div>`).join("")}
      </div>
    </div>`;
  mask.addEventListener("click", (e) => { if (e.target === mask) mask.remove(); });
  document.body.appendChild(mask);
  mask.querySelectorAll(".sug").forEach((el) => el.addEventListener("click", () => {
    mask.remove();
    dispatchQuery(el.dataset.q, document.getElementById("globalInput"));
  }));
}

/* 首页雷达执行 —— 扫描完成后直接在下方渲染完整产品机会报告（单页） */
async function runRadar(view, country, category, budget) {
  const box = view.querySelector("#scanResult");
  box.innerHTML = `
    <div class="card hero-panel" style="margin-top:26px">
      <div style="display:flex;align-items:center;gap:10px">
        <div class="scan-dots"><span class="s"></span><span class="s"></span><span class="s"></span><span class="s"></span><span class="s"></span></div>
        <span style="color:var(--txt-1);font-size:14px">AI 正在扫描 ${country} · ${esc(category)} 的利基信号并评分…</span>
      </div>
    </div>`;
  try {
    const data = await API.blueOcean(country, category, budget, Workspace.productId || undefined);
    sessionStorage.setItem("lastResearch", JSON.stringify(data));
    if (Workspace.productId) Workspace.loadLinkage();
    const ops = data.products;

    /* ── 上半：雷达概览（极坐标图 + Top3 + 摘要） ── */
    const radarHtml = `
      <div class="scan-grid fade-up">
        <div>${radarChart(ops)}</div>
        <div>
          <h3 style="font-size:17px;font-weight:620;margin-bottom:6px">扫描完成 · 命中 <span class="gradient-text">${ops.length}</span> 个机会</h3>
          <p class="page-sub" style="margin-top:0">竞争越低、机会越高的信号越靠近外圈。外圈亮点即蓝海。</p>
          <div style="margin-top:16px;display:flex;flex-direction:column;gap:10px">
            ${ops.slice(0, 3).map((o) => `
              <div class="card" style="padding:13px 15px;display:flex;align-items:center;gap:13px">
                ${scoreRing(o.opportunity_score, 46)}
                <div><div style="font-weight:600;font-size:14px">${esc(o.product_name)}</div>
                <div style="font-size:12px;color:var(--txt-2)">${money(o.market_size_monthly_usd)}/月 · ${o.competition_level} 竞争</div></div>
              </div>`).join("")}
          </div>
          ${provBarHtml(["amazon", "keyword", "review"])}
        </div>
      </div>`;

    /* ── 下半：完整产品机会报告（原 opportunity 内容内联） ── */
    const top = ops[0];
    const insightText = `AI 洞察：当前市场最值得切入的是「${top.product_name}」（机会评分 ${top.opportunity_score}）。`
      + `其竞争度为 ${top.competition_level}，月规模约 ${money(top.market_size_monthly_usd)}，`
      + `年增速 ${(top.market_size_growth_yoy * 100).toFixed(0)}%。核心突破口是用户未被满足的「${top.top_pain_points[0]?.pain || "需求"}」，`
      + `建议以差异化卖点切入，优先验证前 3 个机会。`;

    const reportHtml = `
      <div style="margin-top:28px">
        <div class="eyebrow"><span class="pulse"></span>PRODUCT OPPORTUNITY</div>
        <h2 style="font-size:20px;font-weight:660;margin-top:4px">${esc(data.country)} · ${esc(data.category)} <span class="gradient-text">机会报告</span></h2>
        <p class="page-sub">基于预算 $${Number(data.budget_usd).toLocaleString()} 的 AI 研判 · 共扫描并排序 ${ops.length} 个潜力产品</p>
        <div class="card insight"><p id="insightText"></p></div>
        <div class="prod-grid stagger" id="prodGrid"></div>
      </div>`;

    box.innerHTML = radarHtml + reportHtml;

    /* 渲染产品卡片 */
    const grid = view.querySelector("#prodGrid");
    ops.forEach((o) => {
      const el = document.createElement("div");
      el.className = "card prod-card";
      el.innerHTML = `
        <div class="top">
          <div><div class="rank">#${o.rank} 潜力产品</div><h3>${esc(o.product_name)}</h3></div>
          ${scoreRing(o.opportunity_score, 58)}
        </div>
        <div class="stats">
          <div class="stat"><b>${money(o.market_size_monthly_usd)}</b><span>月规模</span></div>
          <div class="stat"><b>${(o.market_size_growth_yoy * 100).toFixed(0)}%</b><span>年增速</span></div>
          <div class="stat"><span class="badge ${o.competition_level.toLowerCase()}">${o.competition_level} 竞争</span></div>
        </div>
        <div class="pains">${o.top_pain_points.slice(0, 2).map((p) => `<div class="pain">${esc(p.pain)}</div>`).join("")}</div>
        <div class="rec">${esc(o.entry_recommendation)}</div>`;
      el.addEventListener("click", () => openDetail(o));
      grid.appendChild(el);
    });

    /* 打字机洞察 */
    typeWriter(view.querySelector("#insightText"), insightText, 10);
    refreshProvenance(box.querySelector(".prov-bar"), ["amazon", "keyword", "review"]);
  } catch (e) {
      box.innerHTML = `<div class="card empty">雷达扫描失败：${esc(e.message)}</div>`;
  }
}

/* —— 接口设置（运行时配置；前端可切换模型/后端，保存即时生效） —— */
function settingRow(label, hint, inputHtml) {
  return `<div class="set-row"><div class="set-label">${esc(label)}<span class="set-hint">${esc(hint || "")}</span></div><div class="set-input">${inputHtml}</div></div>`;
}

function statusPill(on, text) {
  return `<span class="s-status ${on ? "on" : "off"}">${on ? "● " : "○ "}${esc(text)}</span>`;
}

/* —— 数据溯源徽标（来源 + 时间）—— */
function renderMarketReport(r) {
  const ms = r.market_size || {};
  const pr = r.price_range || {};
  const top = (r.top_products || []).map((p, i) => `
    <div class="card voice fade-up" style="animation-delay:${i * 0.05}s">
      <div class="ico">${i + 1}</div>
      <div class="body">
        <div class="ph">${esc(p.product_name || "")}</div>
        <div class="meta">
          ${p.price != null ? `<span>价格 ${esc(p.price)}</span>` : ""}
          ${p.rating != null ? `<span>评分 ${esc(p.rating)}</span>` : ""}
          ${p.reviews != null ? `<span>评论 ${p.reviews.toLocaleString()}</span>` : ""}
        </div>
        <div class="fix" style="margin-top:8px">🏆 头部原因：${esc(p.why_top || "")}</div>
      </div>
    </div>`).join("");
  const ops = (r.opportunities || []).map((o, i) => `
    <div class="card insight fade-up" style="animation-delay:${i * 0.05}s">
      <div class="ph" style="font-weight:600;margin-bottom:6px">${esc(o.title || "")}</div>
      <div style="color:var(--txt-2);line-height:1.6">${esc(o.detail || "")}</div>
      <div class="fix" style="margin-top:8px">📊 依据：${esc(o.evidence || "")}</div>
    </div>`).join("");
  const tier = ms.tier || "—";
  const est = ms.monthly_usd_estimate ? ` · ≈$${Number(ms.monthly_usd_estimate).toLocaleString()}` : "";
  const priceTxt = `${(pr.min != null ? pr.min : "?")}–${(pr.max != null ? pr.max : "?")} ${esc(pr.currency || "USD")}`;
  return `
    <div class="card insight" style="margin-top:22px">
      <div class="eyebrow">执行摘要</div>
      <p id="mrSum" style="font-size:1.05rem;line-height:1.6"></p>
    </div>
    <div class="grid-3" style="margin-top:18px">
      ${metric("市场规模", tier + est, "var(--good)")}
      ${metric("竞品数量", `${(r.competitor_count != null ? r.competitor_count : 0)} 个`, "var(--ai-3)")}
      ${metric("价格区间", priceTxt, "var(--warn)")}
    </div>
    <h3 class="section-h" style="margin-top:24px">价格带分析</h3>
    <div class="card">${esc(pr.note || "")}</div>
    <h3 class="section-h" style="margin-top:24px">头部产品洞察</h3>
    <div id="mrTop">${top || '<div class="card empty">无</div>'}</div>
    <h3 class="section-h" style="margin-top:24px">市场机会点</h3>
    <div id="mrOps">${ops || '<div class="card empty">无</div>'}</div>
    <div class="card insight" style="margin-top:20px;border-left:3px solid var(--ai-3)">
      <div class="eyebrow">进入建议</div>
      <p style="font-size:1.02rem;line-height:1.6">${esc(r.entry_recommendation || "")}</p>
    </div>
    <div class="prov-badge live" style="margin-top:14px">报告由 AI 基于 Bright Data 数据生成 · ${esc(r.country)} · ${esc(r.category)}</div>`;
}

function provBarHtml(connectors) {
  return `<div class="prov-bar" data-prov="${(connectors || []).join(",")}">
    <span class="prov-label">数据溯源</span>
    <span class="prov-items"><span class="prov-loading">读取中…</span></span>
  </div>`;
}
async function refreshProvenance(el, connectors) {
  if (!el) return;
  const box = el.querySelector ? el.querySelector(".prov-items") : null;
  const target = box || el;
  if (!target) return;
  try {
    const d = await API.dataProvenance(connectors);
    const items = (d.provenance || []).map((p) => {
      const fetched = p.status === "fetched";
      const srcLabel = fetched
        ? (p.source === "live" ? "真实 API" : "真实样本")
        : "待获取";
      const time = p.fetched_at ? new Date(p.fetched_at).toLocaleString() : "";
      const cls = fetched ? (p.source === "live" ? "live" : "fixture") : "pending";
      return `<span class="prov-badge ${cls}" title="connector: ${esc(p.connector)} · 模式: ${esc(p.mode)}">
        <span class="dot"></span>${esc(p.connector)} · ${esc(srcLabel)}${time ? " · " + esc(time) : ""}
      </span>`;
    }).join("");
    target.innerHTML = items || '<span class="prov-loading">暂无</span>';
  } catch (e) {
    target.innerHTML = '<span class="prov-loading">溯源不可用</span>';
  }
}

async function saveSettings(view) {
  const btn = view.querySelector("#sSave");
  btn.disabled = true; btn.textContent = "保存中…";
  // 若用户填写了设置保护令牌，本次保存携带它
  const tokEl = view.querySelector("#sToken");
  if ( tokEl) API.setSettingsToken(tokEl.value.trim());
  const ch = {};
  const ak = view.querySelector("#sAgnesKey").value.trim(); if (ak) ch.AGNES_API_KEY = ak;
  ch.AGNES_BASE_URL = view.querySelector("#sAgnesUrl").value.trim() || "https://apihub.agnes-ai.com/v1";
  ch.AGNES_TEXT_MODEL = view.querySelector("#sAgnesText").value.trim() || "agnes-gpt-4o";
  ch.AGNES_IMAGE_MODEL = view.querySelector("#sAgnesImg").value.trim() || "agnes-sd";
  ch.AGNES_TIMEOUT = view.querySelector("#sAgnesTimeout").value.trim() || "60";
  ch.TOOL_BACKEND_IMAGE_GENERATION = view.querySelector("#sImgBackend").value;
  const wk = view.querySelector("#sWisKey").value.trim(); if (wk) ch.WISART_API_KEY = wk;
  ch.WISART_BASE_URL = view.querySelector("#sWisUrl").value.trim() || "https://wisart.kuaileshifu.com/api";
  ch.WISART_ENDPOINT = view.querySelector("#sWisEndpoint").value.trim() || "/v1/images/generations";
  ch.WISART_AUTH_SCHEME = view.querySelector("#sWisAuth").value.trim() || "Bearer";
  ch.WISART_ASYNC = view.querySelector("#sWisAsync").checked ? "1" : "0";
  try {
    await API.settingsPut(ch);
    toast("设置已保存并即时生效（无需重启）");
    Views.settings(view);
  } catch (e) {
    if ((e.message || "").includes("受保护")) {
      toast("保存被拒绝：请先在上方填入正确的设置保护令牌");
      const t = view.querySelector("#sToken"); if (t) t.focus();
    } else {
      toast("保存失败：" + e.message);
    }
  } finally {
    btn.disabled = false; btn.textContent = "保存设置";
  }
}

async function testConn(view, target) {
  const btn = view.querySelector(target === "text" ? "#sTestText" : "#sTestImg");
  const orig = btn.textContent; btn.disabled = true; btn.textContent = "测试中…";
  const tokEl = view.querySelector("#sToken");
  if (tokEl) API.setSettingsToken(tokEl.value.trim());
  try {
    const r = await API.settingsTest(target);
    toast(r.ok
      ? ("✅ " + (target === "text" ? "文本接口连通" : "生图接口路由正常") + "：" + (r.detail || ""))
      : ("❌ 连接失败：" + (r.detail || "")));
  } catch (e) {
    if ((e.message || "").includes("受保护")) {
      toast("测试被拒绝：请先在上方填入正确的设置保护令牌");
      const t = view.querySelector("#sToken"); if (t) t.focus();
    } else {
      toast("测试请求失败：" + e.message);
    }
  } finally {
    btn.disabled = false; btn.textContent = orig;
  }
}

Views.settings = function (view) {
  view.innerHTML = `
    <div class="eyebrow"><span class="pulse"></span>AI INTERFACE SETTINGS</div>
    <h1 class="page-title">接口设置 · <span class="gradient-text">模型与后端</span></h1>
    <p class="page-sub">在此配置并切换 AI 模型与生成后端。保存后<strong>立即生效，无需重启</strong>；配置会持久化到项目根目录的 <code>.env</code>。</p>
    <div id="sBody" class="set-wrap"><div class="card empty">读取配置中…</div></div>
  `;
  const body = view.querySelector("#sBody");
  API.settingsGet().then(async (d) => {
    const g = d.groups || {};
    const t = g.text || {}, im = g.image || {};
    const textOn = !!t.__hasKey;
    const imgOn = (im.TOOL_BACKEND_IMAGE_GENERATION === "api") && !!im.__hasKey;
    const keyHint = (has) => (has ? "已配置 · 留空则不修改" : "粘贴 API Key 后启用");
    // 本实例是否启用了设置保护令牌
    let reqTok = false;
    try {
      const st = await API._req("GET", "/api/settings/status");
      reqTok = !!(st && st.requires_token);
    } catch (_) {}
    const tokWarn = reqTok
      ? `<div class="set-token-warn">⚠️ 本实例已启用设置保护令牌，保存或测试前请填入正确令牌。</div>`
      : "";
    const savedTok = API.settingsToken;
    body.innerHTML = `
      <div class="card set-card set-token-card">
        <div class="set-head"><div><div class="set-title">设置保护令牌</div><div class="set-sub">可选 · 后端配置 SETTINGS_API_TOKEN 后，保存/测试需携带（会话级，关闭标签页即失效）</div></div></div>
        ${tokWarn}
        ${settingRow("访问令牌", reqTok ? "必填" : "可选（留空则使用本地默认）", `<input id="sToken" type="password" placeholder="${reqTok ? "请输入设置保护令牌" : "未启用保护时可留空"}" autocomplete="off" value="${esc(savedTok)}">`)}
      </div>

      <div class="card set-card">
        <div class="set-head"><div><div class="set-title">文本 AI · Agnes</div><div class="set-sub">驱动视觉策略与 Listing/广告 的中英翻译（OpenAI 兼容）</div></div>${statusPill(textOn, textOn ? "已启用" : "未启用")}</div>
        ${settingRow("API Key", keyHint(textOn), `<input id="sAgnesKey" type="password" placeholder="${textOn ? "已配置 · 留空则不修改" : "粘贴你的 Agnes API Key"}" autocomplete="off">`)}
        ${settingRow("Base URL", "一般无需修改", `<input id="sAgnesUrl" value="${esc(t.AGNES_BASE_URL || "")}">`)}
        ${settingRow("文本模型", "切换为你控制台的真实模型 ID", `<input id="sAgnesText" list="agnesModels" value="${esc(t.AGNES_TEXT_MODEL || "agnes-gpt-4o")}"><datalist id="agnesModels"><option value="agnes-gpt-4o"><option value="agnes-gpt-4"><option value="agnes-claude"><option value="agnes-gpt-4o-mini"></datalist>`)}
        ${settingRow("图像模型", "Agnes 文生图模型 ID", `<input id="sAgnesImg" value="${esc(t.AGNES_IMAGE_MODEL || "agnes-sd")}">`)}
        ${settingRow("超时(秒)", "单次请求超时", `<input id="sAgnesTimeout" type="number" value="${esc(t.AGNES_TIMEOUT || "60")}" style="max-width:120px">`)}
        <div class="set-foot"><button class="btn" id="sTestText">测试连接</button><span class="set-note">向 Agnes 发送一次最小化探测</span></div>
      </div>

      <div class="card set-card">
        <div class="set-head"><div><div class="set-title">图像生成 · WisArt（智画创）</div><div class="set-sub">驱动商品图生成的真实生图后端</div></div>${statusPill(imgOn, im.TOOL_BACKEND_IMAGE_GENERATION === "api" ? "真实生图(api)" : "模拟(mock)")}</div>
        ${settingRow("后端模式", "mock=内置方案；api=真实 WisArt", `<select id="sImgBackend"><option value="mock" ${im.TOOL_BACKEND_IMAGE_GENERATION === "mock" ? "selected" : ""}>mock（模拟方案）</option><option value="api" ${im.TOOL_BACKEND_IMAGE_GENERATION === "api" ? "selected" : ""}>api（真实 WisArt）</option></select>`)}
        ${settingRow("API Key", keyHint(!!im.__hasKey), `<input id="sWisKey" type="password" placeholder="${!!im.__hasKey ? "已配置 · 留空则不修改" : "粘贴 WisArt API Key"}" autocomplete="off">`)}
        ${settingRow("Base URL", "WisArt 基址", `<input id="sWisUrl" value="${esc(im.WISART_BASE_URL || "")}">`)}
        ${settingRow("文生图路径", "按 WisArt 真实契约调整", `<input id="sWisEndpoint" value="${esc(im.WISART_ENDPOINT || "/v1/images/generations")}">`)}
        ${settingRow("鉴权头名", "Bearer 或 X-API-Key 等", `<input id="sWisAuth" value="${esc(im.WISART_AUTH_SCHEME || "Bearer")}">`)}
        ${settingRow("异步任务", "若 WisArt 是 submit→query 模式则开启", `<label class="switch"><input id="sWisAsync" type="checkbox" ${im.WISART_ASYNC === "1" ? "checked" : ""}><span class="slider"></span></label>`)}
        <div class="set-foot"><button class="btn" id="sTestImg">测试连接</button><span class="set-note">验证生图后端是否可路由</span></div>
      </div>

      <div class="set-savebar">
        <span class="set-savehint">配置即时生效并写入 .env</span>
        <button class="btn btn-primary" id="sSave">保存设置</button>
      </div>
    `;
    body.querySelector("#sSave").addEventListener("click", () => saveSettings(view));
    body.querySelector("#sTestText").addEventListener("click", () => testConn(view, "text"));
    body.querySelector("#sTestImg").addEventListener("click", () => testConn(view, "image"));
  }).catch((e) => {
    body.innerHTML = `<div class="card empty">读取配置失败：${esc(e.message)}</div>`;
  });
};
