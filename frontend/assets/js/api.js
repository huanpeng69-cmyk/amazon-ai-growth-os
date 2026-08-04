/* API 客户端：封装后端接口调用 */
const API = {
  base: "",

  async blueOcean(country, category, budgetUsd, productId) {
    const body = { country, category, budget_usd: budgetUsd };
    if (productId) body.product_id = productId;
    const r = await fetch(this.base + "/api/blue-ocean/research", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!r.ok) throw new Error("research failed: " + r.status);
    return r.json();
  },

  async runAgent(query) {
    const r = await fetch(this.base + "/api/agent/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query }),
    });
    if (!r.ok) throw new Error("agent failed: " + r.status);
    return r.json();
  },

  async tool(name, input, backend) {
    const body = { input };
    if (backend) body.backend = backend;
    const r = await fetch(this.base + "/api/tools/" + name, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!r.ok) {
      let detail = "tool failed: " + r.status;
      try { detail = (await r.json()).detail || detail; } catch (_) {}
      throw new Error(detail);
    }
    return r.json();
  },

  /* —— 新增 Agent 直调 —— */
  async listing(input) {
    const r = await fetch(this.base + "/api/agent/listing", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input),
    });
    if (!r.ok) throw new Error((await r.json()).detail || "listing failed");
    return r.json();
  },

  async imageGen(input) {
    const r = await fetch(this.base + "/api/agent/image", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input),
    });
    if (!r.ok) throw new Error((await r.json()).detail || "image failed");
    return r.json();
  },

  async advertising(input) {
    const r = await fetch(this.base + "/api/agent/advertising", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input),
    });
    if (!r.ok) throw new Error((await r.json()).detail || "advertising failed");
    return r.json();
  },

  /* —— Product Visual Agent（策略优先） —— */
  async visual(input) {
    const r = await fetch(this.base + "/api/agent/visual", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input),
    });
    if (!r.ok) throw new Error((await r.json()).detail || "visual failed");
    return r.json();
  },

  /* —— VOC 分析（直调，带产品空间回写） —— */
  async voc(input) {
    const r = await fetch(this.base + "/api/agent/voc", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input),
    });
    if (!r.ok) throw new Error((await r.json()).detail || "voc failed");
    return r.json();
  },

  /* —— 跨模块联动图 —— */
  async linkage(productId) {
    const r = await fetch(this.base + "/api/workspace/" + productId + "/linkage");
    if (!r.ok) throw new Error("linkage failed");
    return r.json();
  },

  /* —— 生命周期管理 —— */
  async lifecycleCreate(input) {
    const r = await fetch(this.base + "/api/lifecycle", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input),
    });
    if (!r.ok) throw new Error((await r.json()).detail || "create failed");
    return r.json();
  },
  async lifecycleList() {
    const r = await fetch(this.base + "/api/lifecycle");
    if (!r.ok) throw new Error("list failed");
    return r.json();
  },
  async lifecycleGet(id) {
    const r = await fetch(this.base + "/api/lifecycle/" + id);
    if (!r.ok) throw new Error("get failed");
    return r.json();
  },
  async lifecycleAdvance(id) {
    const r = await fetch(this.base + "/api/lifecycle/" + id + "/advance", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    });
    if (!r.ok) throw new Error((await r.json()).detail || "advance failed");
    return r.json();
  },

  /* —— 接口设置（运行时配置） —— */
  async settingsGet() {
    const r = await fetch(this.base + "/api/settings");
    if (!r.ok) throw new Error("settings get failed");
    return r.json();
  },
  async settingsPut(changes) {
    const r = await fetch(this.base + "/api/settings", {
      method: "PUT", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ changes }),
    });
    if (!r.ok) throw new Error((await r.json()).detail || "settings put failed");
    return r.json();
  },
  async settingsTest(target) {
    const r = await fetch(this.base + "/api/settings/test", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ target }),
    });
    if (!r.ok) throw new Error((await r.json()).detail || "test failed");
    return r.json();
  },

  /* —— 数据层状态与溯源（统一数据层可视化） —— */
  async dataConnectors() {
    const r = await fetch(this.base + "/api/data/connectors");
    if (!r.ok) throw new Error("connectors failed");
    return r.json();
  },
  async dataProvenance(connectors) {
    const qs = (connectors && connectors.length)
      ? "?connectors=" + connectors.map(encodeURIComponent).join(",")
      : "";
    const r = await fetch(this.base + "/api/data/provenance" + qs);
    if (!r.ok) throw new Error("provenance failed");
    return r.json();
  },

  /* —— 产品空间（跨模块共享上下文） —— */
  async workspaceGet() {
    const r = await fetch(this.base + "/api/workspace");
    if (!r.ok) throw new Error("workspace get failed");
    return r.json();
  },
  async workspaceProducts() {
    const r = await fetch(this.base + "/api/workspace/products");
    if (!r.ok) throw new Error("workspace list failed");
    return r.json();
  },
  async workspaceActivate(id) {
    const r = await fetch(this.base + "/api/workspace/" + id + "/activate", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({}),
    });
    if (!r.ok) throw new Error((await r.json()).detail || "activate failed");
    return r.json();
  },
  async workspaceSave(ctx) {
    const r = await fetch(this.base + "/api/workspace/context", {
      method: "PUT", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(ctx),
    });
    if (!r.ok) throw new Error((await r.json()).detail || "workspace save failed");
    return r.json();
  },

  /* —— 利润测算模块 —— */
  async profit(input) {
    const r = await fetch(this.base + "/api/agent/profit", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input),
    });
    if (!r.ok) throw new Error((await r.json()).detail || "profit failed");
    return r.json();
  },

  /* —— 市场调研 Agent（Bright Data 取数 + AI 分析，输出市场报告） —— */
  async marketResearch(input) {
    const r = await fetch(this.base + "/api/agent/market_research", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input),
    });
    if (!r.ok) {
      let detail = "market research failed";
      try { detail = (await r.json()).detail || detail; } catch (_) {}
      throw new Error(detail);
    }
    return r.json();
  },
  async profitUploadCost(file) {
    const fd = new FormData();
    fd.append("file", file);
    const r = await fetch(this.base + "/api/profit/upload_cost", { method: "POST", body: fd });
    if (!r.ok) throw new Error("upload failed: " + r.status);
    return r.json();
  },
};

/* 简易 toast */
function toast(msg) {
  const el = document.getElementById("toast");
  el.textContent = msg;
  el.classList.add("show");
  clearTimeout(el._t);
  el._t = setTimeout(() => el.classList.remove("show"), 2600);
}
