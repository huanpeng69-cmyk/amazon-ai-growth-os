/* 路由 + 全局 AI 命令 + 启动 */

const ROUTES = {
  "#/": { view: "home", crumb: "AI 市场雷达" },
  "#/opportunity": { view: "opportunity", crumb: "产品机会报告" },
  "#/voc": { view: "voc", crumb: "VOC 分析" },
  "#/listing": { view: "listing", crumb: "Listing 工厂" },
  "#/ads": { view: "ads", crumb: "广告分析" },
  "#/report": { view: "report", crumb: "总报告" },
  "#/visual": { view: "visual", crumb: "AI 商品视觉工厂" },
  "#/profit": { view: "profit", crumb: "利润分析" },
  "#/market-research": { view: "marketResearch", crumb: "市场调研" },
  "#/settings": { view: "settings", crumb: "接口设置" },
};

let pendingRadar = null;   // {country, category, budget}
let pendingVoc = null;     // 关键词字符串
let pendingListing = null; // {product_name, niche_keyword, tone}
let pendingImage = null;   // {product_name, niche_keyword}
let pendingAds = null;     // {product_name, niche_keyword, country, budget_usd}
let pendingVisual = null;  // {product_name, niche_keyword, market_positioning, voc_pain_points, competitor_insights, country}
let pendingMarketResearch = null;  // {country, category, keyword}

/* ───────── 产品空间（跨模块共享上下文：一次填写，全模块通用） ───────── */
const COUNTRY_OPTS = ["US", "DE", "JP", "UK", "FR", "CA", "AU", "IT", "ES", "MX"];
const PLATFORM_OPTS = [["amazon", "Amazon"], ["shopify", "Shopify"], ["independent", "独立站"]];

function pickCtx(p) {
  return {
    name: p.name, niche_keyword: p.niche_keyword,
    category: p.category || "", country: p.country,
    platform: p.platform || "amazon", budget_usd: p.budget_usd,
  };
}

const Workspace = {
  ctx: null,          // {name, niche_keyword, category, country, platform, budget_usd}
  productId: null,
  linkage: null,      // 跨模块联动图（{upstream, injections}）
  _forceCreate: false,
  init() {
    try {
      const c = JSON.parse(localStorage.getItem("ws_ctx") || "null");
      if (c) { this.ctx = c.ctx; this.productId = c.productId; }
    } catch (_) {}
    this.renderBar();
    API.workspaceGet().then((d) => {
      if (d && d.active) {
        this.ctx = pickCtx(d.active);
        this.productId = d.active.product_id;
        this._persist();
      }
      this.renderBar();
      this.loadLinkage();
    }).catch(() => {});
  },
  async loadLinkage() {
    if (!this.productId) { this.linkage = null; return; }
    try { this.linkage = await API.linkage(this.productId); } catch (_) { this.linkage = null; }
  },
  _persist() {
    try { localStorage.setItem("ws_ctx", JSON.stringify({ ctx: this.ctx, productId: this.productId })); } catch (_) {}
  },
  get() { return this.ctx || {}; },
  async save(ctx) {
    const body = Object.assign({}, this.productId ? { product_id: this.productId } : {},
                                this._forceCreate ? { force_create: true } : {}, ctx);
    this._forceCreate = false;
    const d = await API.workspaceSave(body);
    this.ctx = pickCtx(d);
    this.productId = d.product_id;
    this._persist();
    this.renderBar();
    this.loadLinkage();
    return d;
  },
  async activate(id) {
    const d = await API.workspaceActivate(id);
    this.productId = id;
    this.ctx = pickCtx(d);
    this._persist();
    this.renderBar();
    this.loadLinkage();
    toast("已切换到产品：" + (d.name || id));
  },
  async refreshProducts() {
    try { return await API.workspaceProducts(); } catch (_) { return []; }
  },
  renderBar() {
    const el = document.getElementById("contextBar");
    if (!el) return;
    const c = this.get();
    el.innerHTML = `
      <div class="cb-title">📦 产品空间</div>
      <div class="cb-fields">
        <input id="cbName" class="cb-input" placeholder="产品名称" value="${esc(c.name || "")}" />
        <input id="cbNic" class="cb-input" placeholder="核心利基" value="${esc(c.niche_keyword || "")}" />
        <input id="cbCat" class="cb-input cb-sm" placeholder="类目" value="${esc(c.category || "")}" />
        <select id="cbCountry" class="cb-input cb-sm">
          ${COUNTRY_OPTS.map((o) => `<option ${o === (c.country || "US") ? "selected" : ""}>${o}</option>`).join("")}
        </select>
        <select id="cbPlatform" class="cb-input cb-sm">
          ${PLATFORM_OPTS.map(([v, l]) => `<option value="${v}" ${v === (c.platform || "amazon") ? "selected" : ""}>${l}</option>`).join("")}
        </select>
        <input id="cbBud" class="cb-input cb-xs" type="number" placeholder="预算$" value="${c.budget_usd || ""}" />
        <button class="cb-btn" id="cbSave" type="button">保存上下文</button>
        <button class="cb-btn-ghost" id="cbNew" type="button">＋新建产品</button>
      </div>
      <div class="cb-right">
        <button class="cb-btn-ghost" id="cbLink" type="button">🔗 联动</button>
        <select id="cbSwitch" class="cb-input cb-sm"><option value="">切换产品…</option></select>
      </div>`;

    const sync = () => {
      this.ctx = {
        name: el.querySelector("#cbName").value.trim(),
        niche_keyword: el.querySelector("#cbNic").value.trim(),
        category: el.querySelector("#cbCat").value.trim(),
        country: el.querySelector("#cbCountry").value,
        platform: el.querySelector("#cbPlatform").value,
        budget_usd: parseInt(el.querySelector("#cbBud").value || "0", 10) || 0,
      };
      this._persist();
    };
    ["cbName", "cbNic", "cbCat", "cbCountry", "cbPlatform", "cbBud"].forEach((id) => {
      const node = el.querySelector("#" + id);
      node.addEventListener("input", sync);
      node.addEventListener("change", sync);
    });
    el.querySelector("#cbSave").addEventListener("click", async () => {
      sync();
      if (!this.ctx.name && !this.ctx.niche_keyword) { toast("请至少填写产品名称或利基"); return; }
      try { await this.save(this.ctx); toast("✓ 上下文已保存，各模块将自动带入"); }
      catch (e) { toast("保存失败：" + e.message); }
    });
    el.querySelector("#cbNew").addEventListener("click", () => {
      this.productId = null;
      this._forceCreate = true;
      this.ctx = { name: "", niche_keyword: "", category: "", country: "US", platform: "amazon", budget_usd: 0 };
      this._persist();
      el.querySelector("#cbName").value = "";
      el.querySelector("#cbNic").value = "";
      el.querySelector("#cbCat").value = "";
      el.querySelector("#cbBud").value = "";
      el.querySelector("#cbName").focus();
      toast("已新建产品：填写信息后点「保存上下文」");
    });
    const sw = el.querySelector("#cbSwitch");
    this.refreshProducts().then((list) => {
      list.forEach((p) => {
        const o = document.createElement("option");
        o.value = p.product_id; o.textContent = p.name + " · " + (p.country || "US");
        sw.appendChild(o);
      });
    });
    sw.addEventListener("change", () => { if (sw.value) this.activate(sw.value); });
    const linkBtn = el.querySelector("#cbLink");
    if (linkBtn) linkBtn.addEventListener("click", () => this.renderLinkagePanel());
  },
  renderLinkagePanel() {
    const L = this.linkage;
    const wrap = document.createElement("div");
    wrap.className = "lk-mask";
    const hasUp = L && L.upstream && L.upstream.length;
    const inj = (L && L.injections) || {};
    const downstream = [
      { key: "listing", label: "Listing 工厂", hash: "#/listing", fields: inj.listing },
      { key: "visual", label: "AI 视觉工厂", hash: "#/visual", fields: inj.visual },
      { key: "advertising", label: "广告分析", hash: "#/ads", fields: inj.advertising },
    ];
    const upstreamHtml = hasUp ? L.upstream.map((u) => `
      <div class="lk-up">
        <div class="lk-up-head"><span class="lk-badge lk-${u.module}">${esc(u.label)}</span><span class="lk-count">${u.count} 条</span></div>
        <div class="lk-up-sum">${esc(u.summary || "")}</div>
        <div class="lk-up-items">${(u.items || []).map((it) => `<span class="lk-chip">${esc(it.pain || it.name || it.weakness || "")}</span>`).join("")}</div>
      </div>`).join("")
      : `<div class="lk-empty">暂无上游数据。先去 <b>VOC 分析 / 竞品 / 蓝海市场</b> 跑一次，这里就会出现可复用的成果。</div>`;
    const downHtml = downstream.map((d) => {
      const f = d.fields || {};
      const keys = Object.keys(f);
      const n = keys.reduce((a, k) => a + ((f[k] || []).length || 0), 0);
      const labelMap = { key_features: "卖点", differentiation: "差异化", selling_points: "卖点场景", angles: "视觉角度", seed_keywords: "种子关键词" };
      const detail = keys.map((k) => {
        const v = f[k] || [];
        const items = v.slice(0, 4);
        return `<div class="lk-inj"><span class="lk-inj-k">${labelMap[k] || k}</span>${items.map((x) => `<span class="lk-chip">${esc(String(x))}</span>`).join("")}${v.length > 4 ? ` <span class="lk-more">+${v.length - 4}</span>` : ""}</div>`;
      }).join("");
      return `<div class="lk-down ${n ? "" : "lk-down-off"}">
        <div class="lk-down-head"><b>${d.label}</b>${n ? `<span class="lk-count">可带入 ${n} 项</span>` : `<span class="lk-count">暂无可用</span>`}</div>
        ${detail || ""}
        <button class="cb-btn lk-go" data-hash="${d.hash}" ${n ? "" : "disabled"}>灌入并打开 →</button>
      </div>`;
    }).join("");
    wrap.innerHTML = `
      <div class="lk-panel">
        <div class="lk-panel-head">
          <div><div class="eyebrow"><span class="pulse"></span>CROSS-MODULE</div><h2>模块联动 · 互相促进</h2>
          <p class="page-sub" style="margin-top:4px">上游模块的产出会自动沉淀到产品空间，并派生出下游模块可直接复用的内容。</p></div>
          <span class="lk-close" id="lkClose">✕</span>
        </div>
        <div class="lk-cols">
          <div class="lk-col"><div class="lk-col-title">① 上游已有数据</div>${upstreamHtml}</div>
          <div class="lk-col"><div class="lk-col-title">② 可一键灌入的下游</div>${downHtml}</div>
        </div>
      </div>`;
    document.body.appendChild(wrap);
    wrap.addEventListener("click", (e) => { if (e.target === wrap || e.target.id === "lkClose") wrap.remove(); });
    wrap.querySelectorAll(".lk-go").forEach((b) => b.addEventListener("click", () => { wrap.remove(); location.hash = b.dataset.hash; }));
  },
};

/* 各模块表单从产品空间预填：仅填空字段，不覆盖用户已输入或 Supervisor 预填的值 */
function prefillWorkspace(view, map) {
  const c = Workspace.get();
  if (!c) return;
  Object.entries(map).forEach(([sel, field]) => {
    const node = view.querySelector(sel);
    if (!node) return;
    if (node.value && node.value.trim()) return;
    const v = c[field];
    if (field === "country" || field === "platform") {
      if (Array.from(node.options).some((o) => o.value === String(v))) node.value = String(v);
    } else if (v !== undefined && v !== null && v !== "") {
      node.value = v;
    }
  });
}

/* 各下游模块从「上游产出」自动注入：进入模块时把联动派生内容带入对应字段（仅填空字段） */
const LINK_MAP = {
  listing: [{ sel: "#lFeat", keys: ["key_features", "differentiation"], label: "Listing" }],
  visual: [
    { sel: "#vfSellingPts", keys: ["selling_points"], label: "视觉工厂" },
    { sel: "#vfExtraReq", keys: ["angles"], label: "视觉工厂" },
  ],
  advertising: [{ sel: "#adSeeds", keys: ["seed_keywords"], label: "广告" }],
};
function applyLinkage(view, target) {
  const L = Workspace.linkage;
  if (!L || !L.injections) return;
  const inj = L.injections[target];
  if (!inj) return;
  let total = 0;
  (LINK_MAP[target] || []).forEach(({ sel, keys }) => {
    const node = view.querySelector(sel);
    if (!node || (node.value && node.value.trim())) return;
    const parts = [];
    keys.forEach((k) => (inj[k] || []).forEach((x) => parts.push(String(x))));
    if (!parts.length) return;
    node.value = parts.join("，");
    total += parts.length;
  });
  if (total > 0) toast(`🔗 已从上游自动带入 ${total} 项内容到「${target === "listing" ? "Listing" : target === "visual" ? "视觉工厂" : "广告"}」`);
}

function render() {
  const hash = location.hash || "#/";
  const route = ROUTES[hash] || ROUTES["#/"];
  const view = document.getElementById("view");
  document.querySelectorAll(".nav-item").forEach((n) =>
    n.classList.toggle("active", n.dataset.route === hash));
  document.getElementById("crumbs").innerHTML =
    `首页 / <b>${route.crumb}</b>`;

  view.scrollTop = 0;
  Views[route.view](view);

  if (route.view === "home" && pendingRadar) {
    const p = pendingRadar; pendingRadar = null;
    runRadar(view, p.country, p.category, p.budget);
  }
  if (route.view === "voc" && pendingVoc) {
    const kw = pendingVoc; pendingVoc = null;
    const inp = view.querySelector("#vocKw");
    if (inp) { inp.value = kw; view.querySelector("#vocRun").click(); }
  }
  if (route.view === "listing") {
    if (pendingListing) {
      const p = pendingListing; pendingListing = null;
      const inp = view.querySelector("#lName");
      if (inp) {
        inp.value = p.product_name;
        if (p.niche_keyword) view.querySelector("#lNic").value = p.niche_keyword;
        view.querySelector("#lGen").click();
      }
    } else if (pendingImage) {
      const p = pendingImage; pendingImage = null;
      const inp = view.querySelector("#lName");
      if (inp) {
        inp.value = p.product_name;
        if (p.niche_keyword) view.querySelector("#lNic").value = p.niche_keyword;
        const b = view.querySelector("#lImg");
        if (b) b.click();
      }
    }
  }
  if (route.view === "ads" && pendingAds) {
    const p = pendingAds; pendingAds = null;
    const inp = view.querySelector("#adName");
    if (inp) {
      inp.value = p.product_name;
      if (p.niche_keyword) view.querySelector("#adNic").value = p.niche_keyword;
      if (p.country) view.querySelector("#adC").value = p.country;
      if (p.budget_usd) view.querySelector("#adBud").value = p.budget_usd;
      view.querySelector("#adRun").click();
    }
  }
  if (route.view === "visual" && pendingVisual) {
    const p = pendingVisual; pendingVisual = null;
    const inp = view.querySelector("#vfName");
    if (inp) {
      inp.value = p.product_name || "";
      if (p.niche_keyword) { const nicEl = view.querySelector("#vfNic"); if (nicEl) nicEl.value = p.niche_keyword; }
      if (p.market_positioning) { const posEl = view.querySelector("#vfPricePos"); if (posEl) posEl.value = p.market_positioning; }
      if (p.voc_pain_points && p.voc_pain_points.length) { const painEl = view.querySelector("#vfSellingPts"); if (painEl) painEl.value = p.voc_pain_points.join(", "); }
      if (p.competitor_insights) { const compEl = view.querySelector("#vfExtraReq"); if (compEl) compEl.value = p.competitor_insights; }
      if (p.country) { const cEl = view.querySelector("#vfRegion"); if (cEl) cEl.value = p.country; }
      const genBtn = view.querySelector("#vfGen");
      if (genBtn) genBtn.click();
    }
  }
  if (route.view === "marketResearch" && pendingMarketResearch) {
    const p = pendingMarketResearch; pendingMarketResearch = null;
    const inp = view.querySelector("#mrCat");
    if (inp) {
      if (p.country) { const cEl = view.querySelector("#mrC"); if (cEl) cEl.value = p.country; }
      inp.value = p.category || "Pets";
      if (p.keyword) { const kEl = view.querySelector("#mrKw"); if (kEl) kEl.value = p.keyword; }
      const runBtn = view.querySelector("#mrRun");
      if (runBtn) runBtn.click();
    }
  }
}

/* 侧边导航点击 */
document.querySelectorAll(".nav-item").forEach((n) =>
  n.addEventListener("click", () => { location.hash = n.dataset.route; }));

/* 全局 AI 命令栏：自然语言 → Supervisor Agent 总控（不再用正则重做路由） */
document.getElementById("globalCmd").addEventListener("submit", (e) => {
  e.preventDefault();
  const input = document.getElementById("globalInput");
  const q = input.value.trim();
  if (!q) return;
  input.value = "";
  dispatchQuery(q, input);
});

/* 调用 Supervisor Agent 并按意图分发（取代脆弱的浏览器端正则路由） */
async function dispatchQuery(q, input) {
  if (input) { input.disabled = true; input.placeholder = "AI 总控分析中…"; }
  toast("AI 总控分析中…");
  try {
    const d = await API.runAgent(q);
    routeIntent(d, q);
  } catch (e) {
    // 后端不可用时降级：仅本地正则解析（市场类），保证基本可用
    const p = parseNL(q);
    pendingRadar = p;
    location.hash = "#/";
    toast("AI 总控暂不可用，已用本地解析继续");
  } finally {
    if (input) {
      input.disabled = false;
      input.placeholder = "向 AI 描述你的需求，例如：在美国厨房类目找预算 5000 的蓝海产品";
    }
  }
}

/* 依据 Supervisor 返回的意图分发到对应视图 / 报告抽屉 */
function routeIntent(d, q) {
  // 切换到目标路由；若已在目标路由则直接重渲染（hash 不变不会触发 hashchange）
  const go = (hash) => { if ((location.hash || "#/") === hash) render(); else location.hash = hash; };
  switch (d.intent) {
    case "market": {
      const pa = d.params || {};
      pendingRadar = { country: pa.country || "US", category: pa.category || "Kitchen", budget: pa.budget_usd || 5000 };
      go("#/");
      break;
    }
    case "voc": {
      const pa = d.params || {};
      pendingVoc = pa.product_name || pa.niche_keyword || q;
      go("#/voc");
      break;
    }
    case "competitor":
      openAgentReport("competitor", d.competitor, q);
      break;
    case "product":
      openAgentReport("product", d.product, q);
      break;
    case "listing": {
      const pa = d.params || {};
      pendingListing = {
        product_name: pa.product_name || q,
        niche_keyword: pa.niche_keyword || "",
        tone: "专业可信",
      };
      go("#/listing");
      break;
    }
    case "image": {
      const pa = d.params || {};
      pendingImage = { product_name: pa.product_name || q, niche_keyword: pa.niche_keyword || "" };
      go("#/listing");
      toast("已切换到 Listing 工厂并生成图片方案");
      break;
    }
    case "advertising": {
      const pa = d.params || {};
      pendingAds = {
        product_name: pa.product_name || q,
        niche_keyword: pa.niche_keyword || "",
        country: pa.country || "US",
        budget_usd: pa.budget_usd || 0,
      };
      go("#/ads");
      break;
    }
    case "report":
      go("#/report");
      toast("已切换到总报告");
      break;
    case "visual": {
      const pa = d.params || {};
      pendingVisual = {
        product_name: pa.product_name || q,
        niche_keyword: pa.niche_keyword || "",
        market_positioning: pa.market_positioning || "",
        voc_pain_points: pa.voc_pain_points || [],
        competitor_insights: pa.competitor_insights || "",
        country: pa.country || "US",
      };
      go("#/visual");
      toast("已切换到 AI 商品视觉工厂");
      break;
    }
    case "market_research": {
      const pa = d.params || {};
      pendingMarketResearch = {
        country: pa.country || "US",
        category: pa.category || "Pets",
        keyword: pa.keyword || "",
      };
      go("#/market-research");
      toast("已切换到市场调研 Agent（Bright Data + AI）");
      break;
    }
    default:
      showClarification(d.clarification || "请告诉我你想做：蓝海市场挖掘 / 竞品分析 / 用户评论(VOC)分析 / 产品机会判断？", q);
  }
}

window.addEventListener("hashchange", render);
Workspace.init();   // 恢复产品空间上下文（内部状态，不再渲染上下文条 UI）
render();

/* —— 选品后自动预填：从雷达/报告选中产品时，把名称/类目/国家/预算写入 Workspace ——
 *   后续进入利润 / Listing / 视觉 / 广告等页面时，prefillWorkspace 会自动带入。
 *   o: 产品对象(蓝海挖掘产物)  research: 完整 research 数据(含 country/category/budget) */
function selectProduct(o, research) {
  const r = research || JSON.parse(sessionStorage.getItem("lastResearch") || "null");
  const name = o.product_name || "";
  const cat = (r && r.category) || "";
  const comp = (o.competition_level || "").toLowerCase();
  const price = o.estimated_price ||
    Math.round((o.market_size_monthly_usd || 0) / ((o.est_monthly_units || 100) || 1)) || null;

  /* 从类目 + 产品名推导目标人群 */
  const _audience_hint = (function () {
    const map = {
      "Pet Supplies": "Cat owners, pet parents looking for quiet hydration solutions",
      "Kitchen": "Home cooks, busy professionals who value convenience",
      "Electronics": "Tech enthusiasts, early adopters seeking performance",
      "Beauty": "Skincare lovers, beauty-conscious consumers",
      "Home": "Homeowners, interior design enthusiasts",
      "Sports": "Fitness enthusiasts, active lifestyle seekers",
      "Garden": "Gardeners, outdoor living enthusiasts",
      "Toys": "Parents, gift shoppers, kids entertainment",
    };
    if (cat && map[cat]) return map[cat];
    /* fallback: 从产品名猜 */
    if (/cat|pet|dog|fountain/i.test(name)) return "Cat owners, pet parents looking for quality pet products";
    if (/kitchen|cook|blender/i.test(name)) return "Home cooks, busy families";
    return "";
  })();

  /* 从价格/竞争度推导定位 */
  const _price_pos_hint = (function () {
    if (!price) return comp === "low" ? "高性价比入门款" : comp === "high" ? "高端 premium 定位" : "中端主流价位";
    if (price < 15) return "极致性价比·入门款";
    if (price < 35) return "中端主流·性价比优选";
    if (price < 70) return "中高端 premium · 品质升级";
    return "高端奢华 · 品牌溢价";
  })();

  /* 从产品标题提取卖点关键词（去掉品牌词和通用修饰） */
  const _selling_pts_hint = (function () {
    const junk = /^(the |a |an |new |upgraded?|innovations?|award.?winner?|stainless |premium |automatic )/i;
    const clean = name.replace(junk, "").replace(/\s*\|.*/, "").trim();
    if (clean.length > 10) return clean;
    return "";
  })();

  Workspace.ctx = {
    name: name,
    niche_keyword: name,
    category: cat,
    country: (r && r.country) || "US",
    platform: "amazon",
    budget_usd: (r && r.budget_usd) || 0,
    _est_price: price,
    _competition: o.competition_level || "",
    /* 视觉工厂 / Listing 自动带入 */
    _target_audience: _audience_hint,
    _price_positioning: _price_pos_hint,
    _selling_points: _selling_pts_hint,
  };
  Workspace._persist();
  toast(`已选「${name}」· 利润/Listing/视觉/广告 页将自动带入`);
}
