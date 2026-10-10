 import Anthropic from "@anthropic-ai/sdk";
 import fs from "fs";
 import path from "path";
import dotenv from "dotenv";
import { ProxyAgent, setGlobalDispatcher } from "undici";
import { MessageQueue } from "./message-queue.js";
import { fileLog } from "./logger.js";
import { execSync } from "child_process";

dotenv.config({ override: true });

// 代理支持：本地网络常经 Clash 等系统代理上网，但 Node fetch 默认直连，直连会被
// 代理软件拦截（TLS 报 self-signed certificate / other side closed）。
// Node 的 --use-env-proxy 只在进程启动瞬间读环境变量，dotenv 加载的 .env 太晚，
// 所以在这里（dotenv 之后、任何 fetch 之前）手动给全局 fetch 挂 undici 代理。
const _proxyUrl = process.env.HTTPS_PROXY || process.env.https_proxy || process.env.HTTP_PROXY || process.env.http_proxy;
if (_proxyUrl) {
  try {
    setGlobalDispatcher(new ProxyAgent(_proxyUrl));
    fileLog("Proxy", `fetch 走代理 ${_proxyUrl}`);
  } catch (e: any) {
    fileLog("Proxy", `代理初始化失败: ${e?.message}`);
  }
}

export interface SDKMessage {
  type: string;
  subtype?: string;
  session_id?: string;
  message?: { role: string; content: any };
  result?: string;
  total_cost_usd?: number;
  duration_ms?: number;
  content?: string;
  toolName?: string;
  toolInput?: unknown;
  path?: string;
  success?: boolean;
  error?: string;
  cost?: number;
  duration?: number;
}

const SYSTEM_PROMPT = "你是 Amazon AI Growth OS，专业的 AI 亚马逊卖家助手。拥有56个核心技能覆盖亚马逊卖家全链路：关键词研究、Listing优化、FBA费用计算、PPC广告、销量估算、自动上架、AI商品图包生成等。自动上架技能（.claude/skills/amazon-auto-listing/SKILL.md）涉及 Seller Central 提交，必须遵守人工确认门禁。技能脚本在 .claude/skills/ 目录下。关键词研究用 python .claude/skills/amazon-keyword-research/scripts/research.py（Windows）或 research.sh（macOS/Linux），FBA计算用 .claude/skills/amazon-fba-calculator/scripts/calculator.py。商品主图包/PDP详情页图/营销图 用 ecom-pdp 技能（.claude/skills/ecom-pdp/SKILL.md）：按其方法论诊断转化驱动力并规划图包，出图执行 python .claude/skills/ecom-pdp/scripts/generate_image.py（--mode image 出图 / --mode prompt 只出可执行 prompt；--image <参考图路径> 可图生图）；也可直接用 image_gen 工具出图（用户上传了产品图附件时，把附件路径 uploads/xxx.png 传给 refImage 参数做图生图，产品外观以参考图为准；无附件则纯文生图）。该脚本读取项目根 .env 的 IMG_BASE_URL/IMG_MODEL/IMG_API_KEY，未配置时如实告知用户「生图 API 未配置，仅输出 prompt」，禁止假装已出图。";
const TOOLS: Anthropic.Tool[] = [
  {
    name: "bash",
    description: "执行命令。注意：Windows 上是 cmd 语法（不是 bash），macOS/Linux 才是 bash；多行脚本或复杂引号请先用 write_file 保存成 .py/.js/.ps1 文件再执行，避免转义失败。",
    input_schema: { type: "object" as const, properties: { command: { type: "string", description: "命令" } }, required: ["command"] }
  },
  {
    name: "read_file",
    description: "读取文件",
    input_schema: { type: "object" as const, properties: { path: { type: "string", description: "路径" } }, required: ["path"] }
  },
  {
    name: "write_file",
    description: "写入文件",
    input_schema: { type: "object" as const, properties: { path: { type: "string" }, content: { type: "string" } }, required: ["path", "content"] }
  },
  {
    name: "web_search",
    description: "搜索网络（优先 Serper/Brave API，未配置时回退 DuckDuckGo）。失败时返回错误信息，必须在报告中如实标注「数据缺失」，禁止编造搜索结果。",
    input_schema: { type: "object" as const, properties: { query: { type: "string" } }, required: ["query"] }
  },
  {
    name: "browser_navigate",
    description: "用 Playwright 无头浏览器打开网页（自动处理 gzip/JS 渲染，绕过普通 fetch 的乱码问题）。返回页面标题与 URL；被 captcha 拦截时返回错误，此时在报告中标注「数据缺失」。",
    input_schema: { type: "object" as const, properties: { url: { type: "string", description: "完整 URL，如 https://www.amazon.com/s?k=..." } }, required: ["url"] }
  },
  {
    name: "browser_evaluate",
    description: "在当前已打开的页面上执行 JavaScript 表达式并返回结果（必须在 browser_navigate 之后调用）。用于提取页面数据，如 JSON.stringify([...document.querySelectorAll('...')].map(...))。",
    input_schema: { type: "object" as const, properties: { expression: { type: "string", description: "JavaScript 表达式，返回可序列化结果" } }, required: ["expression"] }
  },
  {
    name: "image_gen",
    description: "AI 生成产品图/营销图（OpenAI 兼容图片接口，需配置 IMG_API_KEY/IMG_BASE_URL/IMG_MODEL，与 ecom-pdp 脚本共用同一套 .env 变量）。入参 prompt 按 8 维框架写（主体/角度/环境/光线/相机/风格/构图/负面）。可选 refImage 传参考产品图路径（用户上传的附件，uploads/ 下）实现图生图（/images/edits，保持产品外观一致）；无参考图则走文生图（/images/generations）。输出自动保存到 reports/ 并在回复中以 markdown 图片预览。",
    input_schema: { type: "object" as const, properties: { prompt: { type: "string", description: "图片提示词（8维框架）" }, refImage: { type: "string", description: "可选，参考产品图片路径（用户上传附件，如 uploads/xxx.png）；传入时走图生图 /images/edits，产品外观以参考图为准" }, size: { type: "string", description: "如 1024x1024 / 1536x1024 / 1024x1536" }, model: { type: "string", description: "可选，覆盖 IMG_MODEL" }, count: { type: "number", description: "生成张数，1-4" }, saveTo: { type: "string", description: "保存目录，如 reports/{产品}/images" } }, required: ["prompt"] }
  }
];
// Playwright 无头浏览器单例：惰性启动，全程复用同一实例/页面（导航上下文有状态）。
// 自动解 gzip、渲染 JS，解决 fetch 直抓搜索页乱码 / 被反爬拦截的问题。
let _browser: any = null;
let _page: any = null;
async function getBrowserPage(): Promise<any> {
  if (_page) return _page;
  if (!_browser) {
    const { chromium } = await import("playwright");
    // 优先用系统自带 Edge（免 npx playwright install 下载），失败回退 bundled chromium
    try {
      _browser = await chromium.launch({ headless: true, channel: "msedge", args: ["--disable-blink-features=AutomationControlled"] });
    } catch {
      _browser = await chromium.launch({ headless: true, args: ["--disable-blink-features=AutomationControlled"] });
    }
  }
  const ctx = await _browser.newContext({
    userAgent: "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    locale: "en-US",
    viewport: { width: 1440, height: 900 },
  });
  _page = await ctx.newPage();
  return _page;
}

async function execTool(name: string, input: any): Promise<string> {
  fileLog("Tool", name, JSON.stringify(input).substring(0, 100));
  try {
    switch (name) {
      case "bash":
        return execSync(input.command, { encoding: "utf-8", timeout: 60000, maxBuffer: 5*1024*1024, cwd: process.cwd(), env: process.env }).substring(0, 10000);
      case "read_file":
        return fs.readFileSync(path.resolve(process.cwd(), input.path), "utf-8").substring(0, 20000);
      case "write_file": {
        const p = path.resolve(process.cwd(), input.path);
        const d = path.dirname(p);
        if (!fs.existsSync(d)) fs.mkdirSync(d, { recursive: true });
        fs.writeFileSync(p, input.content, "utf-8");
        return "Written: " + p;
      }
      case "web_search":
        return await webSearch(input.query);
      case "browser_navigate": {
        const page = await getBrowserPage();
        await page.goto(input.url, { waitUntil: "domcontentloaded", timeout: 45000 });
        await page.waitForTimeout(2000); // 等 JS 渲染
        const title = await page.title();
        const url = page.url();
        const captcha = await page.evaluate(() =>
          /captcha|api-services-support@amazon|To discuss automated access/i.test(document.body?.innerText || ""));
        return captcha
          ? `Error: 页面被 captcha/反爬拦截（title=${title}）。请在报告中标注「数据缺失」，禁止编造。`
          : `OK: 已打开 ${url}（title=${title}）。现在可用 browser_evaluate 提取数据。`;
      }
      case "browser_evaluate": {
        const page = await getBrowserPage();
        if (!page) return "Error: 尚未打开任何页面，请先 browser_navigate。";
        const result = await page.evaluate(input.expression);
        const text = typeof result === "string" ? result : JSON.stringify(result);
        if (!text || text === "null" || text === "[]" || text === "{}") {
          return "Empty: 表达式返回空，可能选择器不匹配或页面未加载完，可调整选择器重试。";
        }
        return text.substring(0, 15000);
      }
      case "image_gen":
        return await imageGen(input);
      default:
        return "Unknown tool: " + name;
    }
  } catch (e: any) {
    return "Error: " + (e.message || String(e)).substring(0, 3000);
  }
}

// 网络搜索：优先正规搜索 API（Serper / Brave），未配置 key 时回退 DuckDuckGo HTML。
// 失败时如实返回错误信息，由 Agent 在报告中标注「数据缺失」，禁止编造搜索结果。
async function webSearch(query: string): Promise<string> {
  const q = encodeURIComponent(query);

  const serperKey = process.env.SERPER_API_KEY;
  if (serperKey) {
    try {
      const res = await fetch("https://google.serper.dev/search", {
        method: "POST",
        headers: { "X-API-KEY": serperKey, "Content-Type": "application/json" },
        body: JSON.stringify({ q: query, num: 10 }),
        signal: AbortSignal.timeout(15000),
      });
      if (res.ok) {
        const data = await res.json();
        const lines = (data.organic || []).map((r: any, i: number) =>
          `${i + 1}. ${r.title}\n   ${r.link}\n   ${r.snippet || ""}`);
        if (lines.length > 0) return lines.join("\n").substring(0, 5000);
      } else {
        fileLog("WebSearch", "serper HTTP", String(res.status));
      }
    } catch (e: any) {
      fileLog("WebSearch", "serper failed:", e.message || String(e));
    }
  }

  const braveKey = process.env.BRAVE_API_KEY;
  if (braveKey) {
    try {
      const res = await fetch(`https://api.search.brave.com/res/v1/web/search?q=${q}&count=10`, {
        headers: { "X-Subscription-Token": braveKey, "Accept": "application/json" },
        signal: AbortSignal.timeout(15000),
      });
      if (res.ok) {
        const data = await res.json();
        const lines = ((data.web && data.web.results) || []).map((r: any, i: number) =>
          `${i + 1}. ${r.title}\n   ${r.url}\n   ${r.description || ""}`);
        if (lines.length > 0) return lines.join("\n").substring(0, 5000);
      } else {
        fileLog("WebSearch", "brave HTTP", String(res.status));
      }
    } catch (e: any) {
      fileLog("WebSearch", "brave failed:", e.message || String(e));
    }
  }

  // 回退：DuckDuckGo HTML（无需 key，反爬比 Google 宽松）
  try {
    const out = execSync(`curl -s "https://html.duckduckgo.com/html/?q=${q}" -H "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36" 2>&1`, { encoding: "utf-8", timeout: 15000, maxBuffer: 5 * 1024 * 1024 });
    const text = out.replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim();
    if (text.length > 300 && !text.includes("anomaly") && !text.toLowerCase().includes("captcha")) {
      return text.substring(0, 5000);
    }
    return "Error: 搜索失败（所有搜索渠道不可用或被反爬拦截）。请在报告中标注「搜索数据缺失」，禁止编造搜索结果。";
  } catch (e: any) {
    return "Error: 搜索失败: " + (e.message || String(e)).substring(0, 500);
  }
}

// AI 生图：调用 OpenAI 兼容 /images/generations。环境变量：
// IMG_API_KEY（必需）/ IMG_BASE_URL（缺省 https://api.openai.com/v1，需含 /v1 前缀）/ IMG_MODEL（缺省 gpt-image-1）
// IMG_API_KEY（必需）/ IMG_BASE_URL（缺省 https://api.openai.com/v1，需含 /v1 前缀）/ IMG_MODEL（缺省 gpt-image-1）
// 兼容返回 b64_json 或 url 两种格式；输出存 reports/{dir}/images，可经 /reports 静态路径预览。
// 每张图写盘后立即触发 onImageSaved 回调（由 AgentSession 构造时注册，实时推送给前端「生成一张看一张」）。
let onImageSaved: ((relPath: string) => void) | null = null;
export function setImageSavedListener(fn: (relPath: string) => void) { onImageSaved = fn; }
export async function imageGen(input: any): Promise<string> {
  const key = process.env.IMG_API_KEY || process.env.OPENAI_API_KEY;
  if (!key) {
    return "Error: 生图未配置。请在 .env 设置 IMG_API_KEY（可选 IMG_BASE_URL、IMG_MODEL，与 ecom-pdp 技能共用同一套变量），配置后重启服务再试。";
  }
  const base = (process.env.IMG_BASE_URL || "https://api.openai.com/v1").replace(/\/+$/, "");
  const model = input.model || process.env.IMG_MODEL || "gpt-image-1";
  const size = String(input.size || "1024x1024");
  const count = Math.min(Math.max(parseInt(input.count || "1", 10) || 1, 1), 4);
  const dir = String(input.saveTo || "reports/images").replace(/^\/+/, "");
  const absDir = path.resolve(process.cwd(), dir);
  if (!absDir.startsWith(path.resolve(process.cwd()))) return "Error: saveTo 不允许指向项目目录之外";
  // 图生图：可选参考图（用户上传附件），存在则走 /images/edits，产品外观以参考图为准
  const refRel = input.refImage ? String(input.refImage).replace(/\\/g, "/").replace(/^\/+/, "") : "";
  const refAbs = refRel ? path.resolve(process.cwd(), refRel) : null;
  if (refAbs) {
    if (!refAbs.startsWith(path.resolve(process.cwd()))) return "Error: refImage 不允许指向项目目录之外";
    if (!fs.existsSync(refAbs)) return `Error: 参考图不存在: ${refRel}（用户是否上传了产品图附件？）`;
  }
  try {
    let res: Response;
    if (refAbs) {
      const mimeMap: Record<string, string> = { ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp" };
      const ext = path.extname(refAbs).toLowerCase();
      if (!mimeMap[ext]) return `Error: 不支持的参考图格式 ${ext}，仅支持 png/jpg/jpeg/webp`;
      const fd = new FormData();
      fd.append("model", model);
      fd.append("prompt", String(input.prompt));
      fd.append("n", String(count));
      fd.append("size", size);
      fd.append("image", new Blob([fs.readFileSync(refAbs)], { type: mimeMap[ext] }), path.basename(refAbs));
      res = await fetch(base + "/images/edits", {
        method: "POST",
        headers: { Authorization: `Bearer ${key}` },
        body: fd,
        signal: AbortSignal.timeout(180000),
      });
    } else {
      res = await fetch(base + "/images/generations", {
        method: "POST",
        headers: { Authorization: `Bearer ${key}`, "Content-Type": "application/json" },
        body: JSON.stringify({ model, prompt: String(input.prompt), n: count, size, response_format: "b64_json" }),
        signal: AbortSignal.timeout(180000),
      });
    }
    if (!res.ok) return "Error: 生图 API HTTP " + res.status + ": " + (await res.text()).substring(0, 500);
    const data: any = await res.json();
    const items = data.data || [];
    if (items.length === 0) return "Error: 生图 API 未返回图片";
    fs.mkdirSync(absDir, { recursive: true });
    const saved: string[] = [];
    for (let i = 0; i < items.length; i++) {
      let buf: Buffer | null = null;
      const b64: string | undefined = items[i].b64_json;
      const url: string | undefined = items[i].url;
      if (b64) buf = Buffer.from(b64, "base64");
      else if (url) {
        const ir = await fetch(url, { signal: AbortSignal.timeout(60000) });
        buf = Buffer.from(await ir.arrayBuffer());
      }
      if (!buf) continue;
      const file = path.join(absDir, `img_${Date.now()}_${i + 1}.png`);
      fs.writeFileSync(file, buf);
      const rel = path.relative(process.cwd(), file).replace(/\\/g, "/");
      saved.push(rel);
      // 实时推送：每写完一张图立即通知前端展示（生成一张看一张）
      try { onImageSaved?.(rel); } catch { /* ignore */ }
    }
    if (saved.length === 0) return "Error: 生图 API 返回格式无法解析（既无 b64_json 也无 url）";
    const previews = saved.map((p) => `![img](/${p})`).join("\n");
    return `OK: 已生成 ${saved.length} 张图，保存在 ${dir}/：\n` + saved.join("\n") + `\n在回复中用 markdown 引用预览：\n` + previews;
  } catch (e: any) {
    return "Error: 生图失败: " + (e.message || String(e)).substring(0, 500);
  }
}

export class AgentSession {
  private queue: MessageQueue;
  private client: Anthropic;
  private model: string;
  private messages: Anthropic.MessageParam[] = [];
  private cbs: ((msg: SDKMessage) => void)[] = [];
  private busy = false;
  private dead = false;
  private abortController: AbortController | null = null;

  constructor() {
    this.queue = new MessageQueue();
    this.model = process.env.MODEL || "claude-sonnet-4-20250514";
    // 注册生图实时回调：图片写盘后立即作为 image 消息进入本会话输出流（index.ts formatMessage 透传给 WS）
    setImageSavedListener((relPath) => this.fire({ type: "image", path: relPath }));
    this.client = new Anthropic({ apiKey: process.env.ANTHROPIC_API_KEY || process.env.ANTHROPIC_AUTH_TOKEN, baseURL: process.env.ANTHROPIC_BASE_URL || undefined });
    fileLog("Agent", "Direct API | MODEL:", this.model, "| URL:", process.env.ANTHROPIC_BASE_URL || "(default)");
  }

  sendMessage(content: string) {
    fileLog("User", content.substring(0, 200));
    this.messages.push({ role: "user", content });
    if (!this.busy) { this.busy = true; this.loop(); }
  }

   // 按环境变量 API_STYLE 分流：openai 走 chat/completions（内部双向转换），
   // 缺省走 Anthropic 原生 /messages。返回统一结构 { content, stop_reason }。
   private async callModel(): Promise<{ content: Anthropic.ContentBlock[]; stop_reason: string }> {
     if ((process.env.API_STYLE || "").toLowerCase() === "openai") {
       return this.callOpenAI();
     }
    const res = await this.client.messages.create({ model: this.model, max_tokens: 16000, system: SYSTEM_PROMPT, tools: TOOLS, messages: this.messages }, { signal: this.abortController!.signal });
     return { content: res.content, stop_reason: res.stop_reason || "end_turn" };
   }
 
   // OpenAI 兼容模式：请求 chat/completions，把 Anthropic 消息/工具协议双向转换为 OpenAI 格式
   private async callOpenAI(): Promise<{ content: Anthropic.ContentBlock[]; stop_reason: string }> {
     const apiKey = process.env.ANTHROPIC_API_KEY || process.env.ANTHROPIC_AUTH_TOKEN || "";
     const base = (process.env.ANTHROPIC_BASE_URL || "https://api.anthropic.com").replace(/\/+$/, "");
     const sysText = typeof SYSTEM_PROMPT === "string" ? SYSTEM_PROMPT : "";
 
     // Anthropic messages -> OpenAI messages
     const oaMessages: { role: string; content?: string; tool_calls?: { id: string; type: string; function: { name: string; arguments: string } }[]; tool_call_id?: string }[] = [{ role: "system", content: sysText }];
     for (const m of this.messages) {
       if (typeof m.content === "string") {
         oaMessages.push({ role: m.role, content: m.content });
         continue;
       }
       // content block 数组：拆分 text 与 tool_use / tool_result
       const texts: string[] = [];
       const toolCalls: { id: string; type: string; function: { name: string; arguments: string } }[] = [];
       for (const b of m.content as any[]) {
         if (b.type === "text") texts.push(b.text);
         else if (b.type === "tool_use") toolCalls.push({ id: b.id, type: "function", function: { name: b.name, arguments: JSON.stringify(b.input) } });
         else if (b.type === "tool_result") {
           const inner = typeof b.content === "string" ? b.content : Array.isArray(b.content) ? (b.content as any[]).map((c: any) => c.text || "").join("\n") : "";
           oaMessages.push({ role: "tool", tool_call_id: b.tool_use_id, content: inner });
         }
       }
       if (texts.length > 0 || toolCalls.length > 0) {
         oaMessages.push({ role: m.role, content: texts.join("\n") || undefined, ...(toolCalls.length > 0 ? { tool_calls: toolCalls } : {}) });
       }
     }
 
     // Anthropic tools -> OpenAI functions
     const oaTools = TOOLS.map(t => ({ type: "function", function: { name: t.name, description: t.description, parameters: t.input_schema } }));
 
     const body = JSON.stringify({ model: this.model, max_tokens: 16000, messages: oaMessages, tools: oaTools, tool_choice: "auto" });
     const res = await fetch(base + "/chat/completions", {
       method: "POST",
       headers: { Authorization: `Bearer ${apiKey}`, "Content-Type": "application/json" },
       body,
       signal: this.abortController?.signal,
     });
     if (!res.ok) {
       const errText = await res.text().catch(() => "");
       throw new Error(`OpenAI-mode HTTP ${res.status}: ${errText.substring(0, 500)}`);
     }
     const data: any = await res.json();
     const msg = data?.choices?.[0]?.message;
     if (!msg) throw new Error("OpenAI-mode: empty response");
 
     // OpenAI response -> Anthropic content blocks
     const blocks: Anthropic.ContentBlock[] = [];
     if (msg.content) blocks.push({ type: "text", text: msg.content } as Anthropic.ContentBlock);
     if (Array.isArray(msg.tool_calls)) {
       for (const tc of msg.tool_calls) {
         let args: unknown = {};
         try { args = JSON.parse(tc.function?.arguments || "{}"); } catch { args = {}; }
         blocks.push({ type: "tool_use", id: tc.id || ("call_" + Math.random().toString(36).slice(2)), name: tc.function?.name, input: args } as Anthropic.ContentBlock);
       }
       return { content: blocks, stop_reason: "tool_use" };
     }
     return { content: blocks, stop_reason: "end_turn" };
   }
  private async loop() {
    while (!this.dead && this.messages.length > 0) {
      if (this.messages[this.messages.length - 1].role !== "user") break;
      try {
        this.fire({ type: "assistant_message", content: "正在思考..." });
        this.abortController = new AbortController();
        const res = await this.callModel();
        this.messages.push({ role: "assistant", content: res.content });
        for (const b of res.content) {
          if (b.type === "text" && b.text) { this.fire({ type: "assistant_message", content: b.text }); fileLog("AI", b.text.substring(0, 200)); }
          if (b.type === "tool_use") {
            this.fire({ type: "tool_use", toolName: b.name, toolInput: b.input });
            const r = await execTool(b.name, b.input);
            this.messages.push({ role: "user", content: [{ type: "tool_result", tool_use_id: b.id, content: r }] });
          }
        }
        if (res.stop_reason === "end_turn" || res.stop_reason === "max_tokens") { this.fire({ type: "result", success: true, cost: 0, duration_ms: 0 }); break; }
        if (res.stop_reason === "tool_use") continue;
      } catch (e: any) {
        if (e?.name === "AbortError" || this.abortController?.signal.aborted) {
          fileLog("Agent", "stopped by user");
          this.fire({ type: "assistant_message", content: "⏹ 已停止本次任务。" });
          this.fire({ type: "result", success: false, cost: 0, duration_ms: 0 });
          break;
        }
        fileLog("Err", e.message); this.fire({ type: "error", error: e.message || String(e) }); break;
      }
    }
    this.busy = false;
  }

  private fire(msg: SDKMessage) { for (const cb of this.cbs) cb(msg); }

  async *getOutputStream(): AsyncGenerator<SDKMessage> {
    const q: SDKMessage[] = [];
    let r: (() => void) | null = null;
    this.cbs.push((msg) => { q.push(msg); if (r) { r(); r = null; } });
    while (!this.dead) {
      if (q.length > 0) yield q.shift()!;
      else { await new Promise<void>(ok => { r = ok; }); if (q.length > 0) yield q.shift()!; }
    }
  }

  stop() {
    // 中断当前正在进行的 API 调用（不销毁会话，可继续对话）
    if (this.abortController) {
      try { this.abortController.abort(); } catch { /* ignore */ }
    }
  }

  close() { this.dead = true; this.stop(); this.queue.close(); }
}
