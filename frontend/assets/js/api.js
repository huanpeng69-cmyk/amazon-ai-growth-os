/* API 客户端：封装后端接口调用。
 * 演示模式：当后端不可达（静态部署 / 本地未启动）时，自动回退到内嵌示例数据，
 * 保证在线展示可用。可在 URL 加 ?demo=1 强制开启。 */
const API = {
  base: "",
  demoMode: false,        // 是否处于演示回退（后端不可达）
  _forceDemo: false,      // ?demo=1 强制
  _bannerShown: false,

  /* 设置写入保护令牌：后端配置 SETTINGS_API_TOKEN 后，保存/测试需携带。
     存于 sessionStorage，关闭标签页即失效（不落盘，避免长期泄露）。 */
  get settingsToken() {
    try { return sessionStorage.getItem("settingsToken") || ""; } catch (_) { return ""; }
  },
  setSettingsToken(v) {
    try {
      if (v) sessionStorage.setItem("settingsToken", v);
      else sessionStorage.removeItem("settingsToken");
    } catch (_) {}
  },

  /* 轻量健康检查，用于主动判定后端是否在线 */
  async health() {
    try {
      const r = await fetch(this.base + "/api/health");
      return r.ok;
    } catch (_) {
      return false;
    }
  },

  /* 统一请求入口：网络层失败 → 演示数据回退；HTTP 错误 → 原样抛出 */
  async _req(method, path, body, isForm, extraHeaders) {
    let r;
    const headers = isForm
      ? {}
      : (body !== undefined ? { "Content-Type": "application/json" } : {});
    if (extraHeaders) Object.assign(headers, extraHeaders);
    // 设置写入保护令牌（仅当本会话已填入且后端要求时携带）
    const tk = this.settingsToken;
    if (tk && (path === "/api/settings" || path === "/api/settings/test")) {
      headers["X-Settings-Token"] = tk;
    }
    try {
      r = await fetch(this.base + path, {
        method,
        headers,
        body: isForm ? body : (body !== undefined ? JSON.stringify(body) : undefined),
      });
    } catch (netErr) {
      // 后端不可达：尝试演示数据回退
      const d = this._demo(method, path, body);
      if (d !== undefined) { this._markDemo(); return d; }
      throw netErr;
    }
    if (!r.ok) {
      // 演示模式（后端不可达或 ?demo=1）：HTTP 错误也尝试回退
      if (this.demoMode || this._forceDemo) {
        const d = this._demo(method, path, body);
        if (d !== undefined) { this._markDemo(); return d; }
      }
      let detail = method + " " + path + " failed: " + r.status;
      try { detail = (await r.json()).detail || detail; } catch (_) {}
      throw new Error(detail);
    }
    return r.json();
  },

  /* 演示数据路由 */
  _demo(method, path, body) {
    const DD = window.DEMO_DATA;
    if (!DD) return undefined;
    // 蓝海雷达：按类目选择示例
    if (path === "/api/blue-ocean/research") {
      const cat = (body && body.category) || "Beauty";
      return DD.blueocean[cat] || DD.blueocean[cat.toLowerCase()] || DD.blueocean.__default;
    }
    if (path === "/api/agent/run") return DD.run;
    if (path === "/api/agent/listing") return DD.listing;
    if (path === "/api/agent/image") return DD.image;
    if (path === "/api/agent/advertising") return DD.advertising;
    if (path === "/api/agent/visual") return DD.visual;
    if (path === "/api/agent/voc") return DD.voc;
    if (path === "/api/agent/profit") return DD.profit;
    if (path === "/api/agent/market_research") return DD.market_research;
    if (path === "/api/data/connectors") return DD.connectors;
    if (path === "/api/lifecycle" && method === "GET") return DD.lifecycle;
    if (path === "/api/workspace/products") return DD.workspace_products;
    if (path === "/api/workspace" && method === "GET")
      return { active: null, products: DD.workspace_products };
    // 写操作 / 设置：演示模式返回成功桩，避免界面报错
    if (path === "/api/settings" && method === "GET")
      return { demo: true, configured: {}, available: ["bright_data", "agnes", "wisart"], providers: {} };
    if (path === "/api/settings" && method === "PUT") return { ok: true, demo: true };
    if (path === "/api/settings/test") return { ok: true, demo: true, message: "演示模式：跳过真实校验" };
    if (path === "/api/workspace/context" && method === "PUT") return { ok: true, demo: true };
    if (path === "/api/lifecycle" && method === "POST") return { ok: true, demo: true };
    if (path === "/api/tools/") return undefined;
    if (path.startsWith("/api/tools/")) return { demo: true, note: "演示模式不支持工具直调" };
    if (path.startsWith("/api/workspace/") && path.endsWith("/activate"))
      return { ok: true, demo: true };
    if (path.startsWith("/api/lifecycle/") && path.endsWith("/advance"))
      return { ok: true, demo: true };
    return undefined;
  },

  _markDemo() {
    this.demoMode = true;
    if (!this._bannerShown) { this._bannerShown = true; this._showBanner(); }
  },

  _showBanner() {
    try {
      if (document.getElementById("demoBanner")) return;
      const b = document.createElement("div");
      b.id = "demoBanner";
      b.textContent = "演示模式 · 当前展示示例数据（后端未连接）。本地运行后端可获取实时结果。";
      b.style.cssText =
        "position:fixed;top:0;left:0;right:0;z-index:9999;background:#f5a623;color:#1a1a1a;" +
        "font-size:13px;font-weight:600;text-align:center;padding:7px 12px;box-shadow:0 2px 10px rgba(0,0,0,.25)";
      document.body.appendChild(b);
    } catch (_) {}
  },

  async blueOcean(country, category, budgetUsd, productId) {
    const body = { country, category, budget_usd: budgetUsd };
    if (productId) body.product_id = productId;
    return this._req("POST", "/api/blue-ocean/research", body);
  },

  async runAgent(query) {
    return this._req("POST", "/api/agent/run", { query });
  },

  async tool(name, input, backend) {
    const body = { input };
    if (backend) body.backend = backend;
    return this._req("POST", "/api/tools/" + name, body);
  },

  async listing(input) { return this._req("POST", "/api/agent/listing", input); },
  async imageGen(input) { return this._req("POST", "/api/agent/image", input); },
  async advertising(input) { return this._req("POST", "/api/agent/advertising", input); },
  async visual(input) { return this._req("POST", "/api/agent/visual", input); },
  async voc(input) { return this._req("POST", "/api/agent/voc", input); },

  async linkage(productId) { return this._req("GET", "/api/workspace/" + productId + "/linkage"); },

  async lifecycleCreate(input) { return this._req("POST", "/api/lifecycle", input); },
  async lifecycleList() { return this._req("GET", "/api/lifecycle"); },
  async lifecycleGet(id) { return this._req("GET", "/api/lifecycle/" + id); },
  async lifecycleAdvance(id) {
    return this._req("POST", "/api/lifecycle/" + id + "/advance", {});
  },

  async settingsGet() { return this._req("GET", "/api/settings"); },
  async settingsPut(changes) { return this._req("PUT", "/api/settings", { changes }); },
  async settingsTest(target) { return this._req("POST", "/api/settings/test", { target }); },

  async dataConnectors() { return this._req("GET", "/api/data/connectors"); },
  async dataProvenance(connectors) {
    const qs = (connectors && connectors.length)
      ? "?connectors=" + connectors.map(encodeURIComponent).join(",") : "";
    return this._req("GET", "/api/data/provenance" + qs);
  },

  async workspaceGet() { return this._req("GET", "/api/workspace"); },
  async workspaceProducts() { return this._req("GET", "/api/workspace/products"); },
  async workspaceActivate(id) {
    return this._req("POST", "/api/workspace/" + id + "/activate", {});
  },
  async workspaceSave(ctx) { return this._req("PUT", "/api/workspace/context", ctx); },

  async profit(input) { return this._req("POST", "/api/agent/profit", input); },
  async marketResearch(input) { return this._req("POST", "/api/agent/market_research", input); },

  async profitUploadCost(file) {
    const fd = new FormData();
    fd.append("file", file);
    const r = await fetch(this.base + "/api/profit/upload_cost", { method: "POST", body: fd });
    if (!r.ok) throw new Error("upload failed: " + r.status);
    return r.json();
  },
};

/* 兼顾 ?demo=1 强制演示模式 */
(function () {
  try {
    const p = new URLSearchParams(location.search);
    if (p.has("demo")) API._forceDemo = true;
  } catch (_) {}
})();

/* 简易 toast */
function toast(msg) {
  const el = document.getElementById("toast");
  if (!el) return;
  el.textContent = msg;
  el.classList.add("show");
  clearTimeout(el._t);
  el._t = setTimeout(() => el.classList.remove("show"), 2600);
}
