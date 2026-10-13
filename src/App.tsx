import { useState, useRef, useEffect, useCallback } from "react";
import { useWebSocket } from "./hooks/useWebSocket";
import { useFileUpload } from "./hooks/useFileUpload";
import ReactMarkdown from "react-markdown";
import type { ChatMessage, ReportFile, ChatMeta } from "./types";

const MARKET_OPTIONS = [
  { value: "美国", label: "🇺🇸 美国 US" },
  { value: "英国", label: "🇬🇧 英国 UK" },
  { value: "德国", label: "🇩🇪 德国 DE" },
  { value: "法国", label: "🇫🇷 法国 FR" },
  { value: "意大利", label: "🇮🇹 意大利 IT" },
  { value: "西班牙", label: "🇪🇸 西班牙 ES" },
  { value: "日本", label: "🇯🇵 日本 JP" },
  { value: "加拿大", label: "🇨🇦 加拿大 CA" },
  { value: "澳大利亚", label: "🇦🇺 澳大利亚 AU" },
  { value: "印度", label: "🇮🇳 印度 IN" },
  { value: "墨西哥", label: "🇲🇽 墨西哥 MX" },
  { value: "巴西", label: "🇧🇷 巴西 BR" },
];

interface TemplateField {
  key: string;
  label: string;
  placeholder?: string;
  type?: "text" | "select" | "image";
  options?: { value: string; label: string }[];
  optional?: boolean;
}

interface Template {
  icon: string;
  title: string;
  desc: string;
  accent: string; // tailwind gradient classes
  chip: string;   // tailwind solid chip classes
  fields: TemplateField[];
  build: (v: Record<string, string>) => string;
}

const TEMPLATES: Template[] = [
  {
    icon: "🎯", title: "一站式调研", desc: "ASIN深度分析9份报告",
    accent: "from-amber-100 to-orange-50 border-amber-200",
    chip: "bg-amber-100 text-amber-700 ring-amber-200",
    fields: [
      { key: "asin", label: "ASIN 或产品 URL", placeholder: "如 B07PWTJ4H1" },
      { key: "market", label: "市场（可选，默认美国）", type: "select", options: MARKET_OPTIONS, optional: true },
    ],
    build: (v) => `深度调研 ${v.asin}${v.market ? `（${v.market}市场）` : ""}`,
  },
  {
    icon: "🔍", title: "关键词研究", desc: "长尾词+机会评分",
    accent: "from-sky-100 to-cyan-50 border-sky-200",
    chip: "bg-sky-100 text-sky-700 ring-sky-200",
    fields: [
      { key: "keyword", label: "种子关键词", placeholder: "如 portable blender" },
      { key: "market", label: "市场（可选，默认美国）", type: "select", options: MARKET_OPTIONS, optional: true },
    ],
    build: (v) => `研究关键词 "${v.keyword}" 在亚马逊${v.market || "美国"}的机会`,
  },
  {
    icon: "📝", title: "Listing优化", desc: "创建/优化Listing",
    accent: "from-emerald-100 to-teal-50 border-emerald-200",
    chip: "bg-emerald-100 text-emerald-700 ring-emerald-200",
    fields: [
      { key: "asin", label: "ASIN 或产品 URL", placeholder: "如 B0D72TSM62" },
      { key: "notes", label: "需求说明（可选）", placeholder: "如：突出便携和续航", optional: true },
    ],
    build: (v) => `帮我优化这个产品的Listing：${v.asin}${v.notes ? `。需求：${v.notes}` : ""}`,
  },
  {
    icon: "💰", title: "FBA计算", desc: "费用明细+利润分析",
    accent: "from-violet-100 to-purple-50 border-violet-200",
    chip: "bg-violet-100 text-violet-700 ring-violet-200",
    fields: [
      { key: "price", label: "售价（美元）", placeholder: "如 29.99" },
      { key: "cost", label: "采购成本（美元）", placeholder: "如 8" },
      { key: "weight", label: "重量（磅）", placeholder: "如 1.2" },
    ],
    build: (v) => `帮我计算FBA费用：售价 $${v.price}，成本 $${v.cost}，重量 ${v.weight} 磅`,
  },
  {
    icon: "📊", title: "销量估算", desc: "月销量+营收",
    accent: "from-cyan-100 to-blue-50 border-cyan-200",
    chip: "bg-cyan-100 text-cyan-700 ring-cyan-200",
    fields: [
      { key: "bsr", label: "BSR 或 ASIN", placeholder: "如 1500 或 B09V3KXJPB" },
      { key: "market", label: "市场（可选，默认美国）", type: "select", options: MARKET_OPTIONS, optional: true },
    ],
    build: (v) => `估算 ${v.bsr} 的月销量${v.market ? `（${v.market}市场）` : ""}`,
  },
  {
    icon: "📢", title: "PPC广告", desc: "广告结构+出价策略",
    accent: "from-indigo-100 to-blue-50 border-indigo-200",
    chip: "bg-indigo-100 text-indigo-700 ring-indigo-200",
    fields: [
      { key: "asin", label: "ASIN 或产品 URL", placeholder: "如 B0D72TSM62" },
      { key: "budget", label: "日预算（美元）", placeholder: "如 50" },
    ],
    build: (v) => `帮我搭建PPC广告结构，产品 ${v.asin}，预算 $${v.budget}/天`,
  },
  {
    icon: "🚀", title: "自动上架", desc: "填表+截图确认后提交",
    accent: "from-rose-100 to-red-50 border-rose-200",
    chip: "bg-rose-100 text-rose-700 ring-rose-200",
    fields: [
      { key: "asin", label: "ASIN 或产品 URL（跟卖/改款，没有可空）", placeholder: "如 B0D72TSM62", optional: true },
      { key: "market", label: "市场（可选，默认美国）", type: "select", options: MARKET_OPTIONS, optional: true },
      { key: "sku", label: "卖家 SKU", placeholder: "如 MY-SKU-001" },
      { key: "price", label: "售价", placeholder: "如 29.99" },
      { key: "quantity", label: "库存数量", placeholder: "如 100" },
      { key: "fulfillment", label: "配送方式（可选）", placeholder: "如 FBA", optional: true },
    ],
    build: (v) => `帮我自动上架${v.asin ? `产品 ${v.asin}` : "新产品"}${v.market ? `（${v.market}市场）` : ""}：SKU=${v.sku}，售价=${v.price}，库存=${v.quantity}${v.fulfillment ? `，配送=${v.fulfillment}` : ""}。注意：填表后必须截图给我确认，我确认后你才能提交`,
  },
  {
    icon: "🎨", title: "AI商品图包", desc: "5主图+8详情页图 ecom-pdp",
    accent: "from-pink-100 to-fuchsia-50 border-pink-200",
    chip: "bg-pink-100 text-pink-700 ring-pink-200",
    fields: [
      { key: "product", label: "产品描述（名称+核心卖点）", placeholder: "如 便携式榨汁杯，20秒搅打、USB-C充电、防漏、380ml" },
      { key: "audience", label: "目标人群", placeholder: "如 健身人群和通勤上班族" },
      { key: "market", label: "市场（可选，默认美国）", type: "select", options: MARKET_OPTIONS, optional: true },
      { key: "refImage", label: "参考产品图（可选，上传后走图生图）", type: "image", optional: true },
    ],
    build: (v) => `用 ecom-pdp 技能为这个产品做一套亚马逊${v.market || "美国"}PDP图包：产品是 ${v.product}，目标人群是 ${v.audience}。输出 5 张主图 + 8 张详情页图，先按方法论诊断转化驱动力并生成 Campaign Style Lock 和可执行 Prompt；${v.refImage ? `用户已上传参考产品图：${v.refImage}（img2img 用它作 refImage 参数）` : ""}如生图 API 已配置（.env 的 IMG_* ）就直接出图并给我图片路径预览，未配置就只输出 Prompt 包`,
  },
];

function FileTree({ files, onFileClick, depth = 0 }: { files: ReportFile[]; onFileClick: (path: string) => void; depth?: number }) {
  return (<div>{files.map((f) => (<div key={f.path}>{f.type === "directory" ? (<div><div className="px-2 py-1 text-xs text-stone-400 font-medium tracking-wide" style={{ paddingLeft: `${depth * 12 + 8}px` }}>▸ {f.name}</div>{f.children && <FileTree files={f.children} onFileClick={onFileClick} depth={depth + 1} />}</div>) : (<button onClick={() => onFileClick(f.path)} className="w-full text-left px-2 py-1.5 text-xs text-stone-600 hover:bg-amber-50 hover:text-amber-700 rounded-lg mx-1 truncate transition-colors" style={{ paddingLeft: `${depth * 12 + 8}px`, width: "calc(100% - 8px)" }}>📄 {f.name}</button>)}</div>))}</div>);
}

function ChatList({ chats, activeChatId, onSwitch, onDelete, onNew }: {
  chats: ChatMeta[]; activeChatId: string; onSwitch: (id: string) => void; onDelete: (id: string) => void; onNew: () => void;
}) {
  return (
    <div className="flex flex-col max-h-[35%] shrink-0">
      <div className="flex items-center justify-between px-4 py-3 shrink-0">
        <span className="text-xs font-semibold text-stone-400 uppercase tracking-wider">历史会话</span>
        <button onClick={onNew} className="text-xs text-amber-600 hover:text-amber-700 px-2 py-1 rounded-md hover:bg-amber-50 transition-colors">＋ 新会话</button>
      </div>
      <div className="flex-1 overflow-y-auto px-2 space-y-0.5">
        {chats.length === 0 && <p className="text-xs text-stone-400 text-center mt-2 px-2">暂无历史会话</p>}
        {chats.map((c) => (
          <div key={c.chatId} className={`group flex items-center gap-1.5 px-2.5 py-2 cursor-pointer rounded-lg transition-all ${c.chatId === activeChatId ? "bg-amber-50 ring-1 ring-amber-200" : "hover:bg-stone-100"}`} onClick={() => onSwitch(c.chatId)}>
            <div className="flex-1 min-w-0">
              <p className={`text-xs truncate ${c.chatId === activeChatId ? "text-amber-700 font-medium" : "text-stone-600"}`}>{c.preview || c.chatId}</p>
              <p className="text-[10px] text-stone-400 mt-0.5">{new Date(c.lastTs).toLocaleString()} · {c.messageCount} 条</p>
            </div>
            <button onClick={(e) => { e.stopPropagation(); onDelete(c.chatId); }} className="text-[11px] text-stone-300 hover:text-red-500 opacity-0 group-hover:opacity-100 shrink-0 transition-opacity" title="删除会话">✕</button>
          </div>
        ))}
      </div>
    </div>
  );
}

function ReportsSidebar({ chats, activeChatId, files, onSwitchChat, onDeleteChat, onNewChat, onFileClick, onRefresh }: {
  chats: ChatMeta[]; activeChatId: string; files: ReportFile[]; onSwitchChat: (id: string) => void; onDeleteChat: (id: string) => void; onNewChat: () => void; onFileClick: (path: string) => void; onRefresh: () => void;
}) {
  return (
    <aside className="w-[280px] border-r border-stone-200/80 bg-white/80 backdrop-blur-xl flex flex-col shrink-0">
      <div className="flex items-center gap-2.5 px-4 py-4 border-b border-stone-100 shrink-0">
        <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-amber-400 to-orange-600 flex items-center justify-center text-base shadow-lg shadow-orange-500/30">🔍</div>
        <div>
          <p className="text-sm font-semibold text-stone-800 leading-tight">Amazon AI Growth OS</p>
          <p className="text-[10px] text-stone-400">AI 亚马逊卖家助手</p>
        </div>
      </div>
      <ChatList chats={chats} activeChatId={activeChatId} onSwitch={onSwitchChat} onDelete={onDeleteChat} onNew={onNewChat} />
      <div className="flex items-center justify-between px-4 py-3 border-t border-stone-100 shrink-0">
        <span className="text-xs font-semibold text-stone-400 uppercase tracking-wider">分析报告</span>
        <button onClick={onRefresh} className="text-xs text-stone-400 hover:text-stone-600 transition-colors">刷新</button>
      </div>
      <div className="flex-1 overflow-y-auto pb-3">
        {files.length === 0 && <p className="text-xs text-stone-400 text-center mt-4 px-4 leading-relaxed">尚无报告<br />输入需求开始分析</p>}
        <FileTree files={files} onFileClick={onFileClick} />
      </div>
    </aside>
  );
}

function ProgressPanel({ messages }: { messages: ChatMessage[] }) {
  const toolCalls = messages.filter((m) => m.toolCall);
  if (toolCalls.length === 0) return null;
  return (
    <aside className="w-[230px] border-l border-stone-200/80 bg-white/80 backdrop-blur-xl flex flex-col shrink-0">
      <div className="px-4 py-3 border-b border-stone-100 shrink-0"><span className="text-xs font-semibold text-stone-400 uppercase tracking-wider">执行日志</span></div>
      <div className="flex-1 overflow-y-auto p-2.5 space-y-1">
        {toolCalls.map((m) => (<div key={m.id} className={`flex items-center gap-2 py-1.5 px-2.5 rounded-lg ${m.toolCall!.status === "running" ? "bg-amber-50" : ""}`}>
          {m.toolCall!.status === "done" && <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 shrink-0" />}
          {m.toolCall!.status === "running" && <span className="inline-block w-2 h-2 bg-amber-500 rounded-full animate-pulse shrink-0" />}
          <span className={`text-xs font-mono truncate ${m.toolCall!.status === "running" ? "text-amber-700" : "text-stone-400"}`}>{m.toolCall!.name}</span>
        </div>))}
      </div>
    </aside>
  );
}

function MessageBubble({ msg }: { msg: ChatMessage }) {
  if (msg.role === "user") return (<div className="flex justify-end mb-4 animate-fade-up"><div className="bg-gradient-to-br from-amber-500 to-orange-600 text-white rounded-2xl rounded-br-md px-4 py-2.5 max-w-[80%] whitespace-pre-wrap shadow-lg shadow-orange-500/25">{msg.content}{msg.files?.map((f) => (<div key={f.path} className="text-xs text-amber-100 mt-1.5 flex items-center gap-1">📎 {f.name}</div>))}</div></div>);
  if (msg.role === "system" && msg.toolCall) { const tc = msg.toolCall; return (<div className="flex justify-start mb-2.5 animate-fade-up"><div className={`rounded-xl px-3.5 py-2.5 max-w-[85%] text-sm shadow-sm ${tc.status === "running" ? "bg-amber-50 border border-amber-200" : "bg-white border border-stone-200"}`}><div className="flex items-center gap-2">{tc.status === "running" ? <span className="inline-block w-2 h-2 bg-amber-500 rounded-full animate-pulse" /> : <span className="inline-block w-2 h-2 bg-emerald-500 rounded-full" />}<span className="font-mono text-[13px] text-stone-600">{tc.name}</span></div>{tc.status === "running" && tc.input !== undefined && tc.input !== null && <pre className="text-xs text-stone-400 mt-1.5 max-h-20 overflow-hidden font-mono">{String(typeof tc.input === "string" ? tc.input : (JSON.stringify(tc.input as Record<string, unknown>, null, 2) || "")).slice(0, 200)}</pre>}</div></div>); }
  if (msg.role === "system") return (<div className="flex justify-center mb-3"><div className="bg-red-50 border border-red-200 text-red-600 rounded-xl px-4 py-2 text-sm max-w-[85%] text-center">{msg.content}</div></div>);
  if (msg.role === "image") return (<div className="flex justify-start mb-4 animate-fade-up"><div className="bg-white border border-stone-200 rounded-2xl rounded-bl-md p-2.5 max-w-[85%] shadow-sm"><a href={`/${msg.content}`} target="_blank" rel="noreferrer"><img src={`/${msg.content}`} alt={msg.content} className="rounded-xl max-h-80 w-auto cursor-zoom-in hover:opacity-90 transition-opacity" loading="lazy" /></a><p className="text-[10px] text-stone-400 mt-1.5 truncate font-mono">🖼 {msg.content}</p></div></div>);
  return (<div className="flex justify-start mb-4 animate-fade-up"><div className="bg-white border border-stone-200/80 text-stone-800 rounded-2xl rounded-bl-md px-4.5 py-3 max-w-[88%] md-body shadow-sm"><ReactMarkdown>{msg.content}</ReactMarkdown></div></div>);
}

function TemplateForm({ template, onStart, onCancel }: { template: Template; onStart: (text: string) => void; onCancel: () => void }) {
  const [values, setValues] = useState<Record<string, string>>({});
  const { uploading, upload } = useFileUpload();
  const imgInputRef = useRef<HTMLInputElement>(null);
  const requiredOk = template.fields.filter((f) => !f.optional).every((f) => (values[f.key] || "").trim());
  return (
    <div className={`bg-gradient-to-b ${template.accent} rounded-3xl p-5 w-full max-w-md border shadow-xl shadow-stone-900/5 animate-pop-in`}>
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2.5">
          <span className="w-9 h-9 rounded-xl bg-white/90 shadow-sm flex items-center justify-center text-lg">{template.icon}</span>
          <div>
            <p className="text-sm font-semibold text-stone-800">{template.title}</p>
            <p className="text-xs text-stone-500">{template.desc}</p>
          </div>
        </div>
        <button onClick={onCancel} className="text-xs text-stone-400 hover:text-stone-600 px-2.5 py-1 rounded-lg hover:bg-white/70 transition-colors">← 返回</button>
      </div>
      <div className="flex flex-col gap-3">
        {template.fields.map((f) => (
          <div key={f.key} className="flex flex-col gap-1.5">
            <label className="text-xs text-stone-500 flex items-center gap-1.5">{f.label}{f.optional && <span className="text-[10px] text-stone-400">可选</span>}</label>
            {f.type === "select" ? (
              <select value={values[f.key] || ""} onChange={(e) => setValues((p) => ({ ...p, [f.key]: e.target.value }))} className="input-field appearance-none cursor-pointer">
                <option value="">默认（美国）</option>
                {f.options?.map((o) => (<option key={o.value} value={o.value}>{o.label}</option>))}
              </select>
            ) : f.type === "image" ? (
              <div>
                <input type="file" ref={imgInputRef} accept=".png,.jpg,.jpeg,.webp" className="hidden"
                  onChange={async (e) => {
                    const file = e.target.files?.[0];
                    if (!file) return;
                    const r = await upload(file);
                    if (r) setValues((p) => ({ ...p, [f.key]: r.path }));
                    e.target.value = "";
                  }} />
                {values[f.key] ? (
                  <div className="flex items-center gap-2.5 bg-white border border-stone-200 rounded-xl p-2 shadow-sm">
                    <img src={`/${values[f.key]}`} alt="参考图" className="h-12 w-12 rounded-lg object-cover" />
                    <span className="text-xs text-stone-500 flex-1 truncate font-mono">{values[f.key]}</span>
                    <button onClick={() => setValues((p) => ({ ...p, [f.key]: "" }))} className="text-xs text-red-500 hover:text-red-600 px-2 py-1 rounded-md hover:bg-red-50 transition-colors">清除</button>
                  </div>
                ) : (
                  <button onClick={() => imgInputRef.current?.click()} disabled={uploading}
                    className="w-full bg-white/60 text-stone-500 text-sm rounded-xl px-3 py-2.5 border border-dashed border-stone-300 hover:border-amber-400 hover:text-amber-600 transition-colors text-left">
                    {uploading ? "⏳ 上传中..." : "📷 点击上传产品图（png/jpg/webp，可选）"}
                  </button>
                )}
              </div>
            ) : (
              <input value={values[f.key] || ""} onChange={(e) => setValues((p) => ({ ...p, [f.key]: e.target.value }))} placeholder={f.placeholder} className="input-field" />
            )}
          </div>
        ))}
        <button onClick={() => requiredOk && onStart(template.build(values))} disabled={!requiredOk}
          className="mt-2 bg-gradient-to-r from-amber-500 via-orange-500 to-amber-500 bg-[length:200%_auto] animate-gradient-x disabled:animate-none disabled:from-stone-200 disabled:to-stone-200 disabled:text-stone-400 text-white text-sm font-medium rounded-xl px-4 py-2.5 transition-all shadow-lg shadow-orange-500/25 disabled:shadow-none active:scale-[0.98]">
          开始分析 →
        </button>
      </div>
    </div>
  );
}

function WelcomeScreen({ onStart }: { onStart: (text: string) => void }) {
  const [selected, setSelected] = useState<Template | null>(null);
  return (
    <div className="relative flex flex-col items-center justify-center min-h-full text-stone-500 gap-5 py-10">
      <div className="blob w-72 h-72 bg-amber-300/40 -top-10 -left-10 animate-float" />
      <div className="blob w-64 h-64 bg-sky-300/30 -bottom-8 -right-8 animate-float-slow" />
      <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-amber-400 to-orange-600 flex items-center justify-center text-3xl shadow-xl shadow-orange-500/30 animate-float">🔍</div>
      <div className="text-center">
        <h2 className="text-xl font-semibold text-transparent bg-clip-text bg-gradient-to-r from-amber-600 to-orange-600">欢迎回来 👋</h2>
        <p className="text-sm mt-1.5">56 个专业技能 · 浏览器自动化 · 12 个市场 · 全中文分析 · AI 图包生成</p>
      </div>
      {selected ? (
        <TemplateForm template={selected} onStart={onStart} onCancel={() => setSelected(null)} />
      ) : (
        <div className="grid grid-cols-2 gap-3 mt-3 max-w-xl w-full px-4">
          {TEMPLATES.map((t, i) => (
            <button key={t.title} onClick={() => setSelected(t)} style={{ animationDelay: `${i * 60}ms` }}
              className={`card-hover bg-gradient-to-b ${t.accent} bg-white/70 backdrop-blur rounded-2xl px-4 py-4 text-left border animate-pop-in`}>
              <span className={`inline-flex w-9 h-9 rounded-xl items-center justify-center text-lg ${t.chip} ring-1 shadow-sm`}>{t.icon}</span>
              <p className="text-sm font-medium text-stone-800 mt-2.5">{t.title}</p>
              <p className="text-xs text-stone-500 mt-0.5">{t.desc}</p>
            </button>
          ))}
        </div>
      )}
      <p className="text-xs text-stone-400 mt-1">或在下方输入任意需求，如「深度调研 B07PWTJ4H1」</p>
    </div>
  );
}

function ReportView({ reportPath, content, onClose }: { reportPath: string; content: string; onClose: () => void }) {
  const fileName = reportPath.split("/").pop() || "report.md";
  const download = useCallback(() => {
    const blob = new Blob([content], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = fileName; a.click();
    URL.revokeObjectURL(url);
  }, [content, fileName]);
  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between px-5 py-3 border-b border-stone-200/70 glass shrink-0">
        <span className="text-sm text-stone-600 truncate font-medium">📄 {reportPath}</span>
        <div className="flex gap-2 shrink-0">
          <button onClick={download} className="text-xs text-amber-600 hover:text-amber-700 px-3 py-1.5 rounded-lg hover:bg-amber-50 transition-colors">⬇ 下载</button>
          <button onClick={onClose} className="text-xs text-stone-400 hover:text-stone-600 px-3 py-1.5 rounded-lg hover:bg-stone-100 transition-colors">✕ 返回对话</button>
        </div>
      </div>
      <div className="flex-1 overflow-y-auto chat-bg">
        <article className="max-w-4xl mx-auto px-6 py-8 md-body bg-white border border-stone-200/80 rounded-2xl my-6 shadow-xl shadow-stone-900/5">
          <ReactMarkdown>{content}</ReactMarkdown>
        </article>
      </div>
    </div>
  );
}

export default function App() {
  const { messages, sendMessage, stop, isConnected, isThinking, chatId, switchChat, newChat } = useWebSocket();
  const { uploading, uploadedFiles, upload, clearFiles } = useFileUpload();
  const [input, setInput] = useState("");
  const [reportFiles, setReportFiles] = useState<ReportFile[]>([]);
  const [chats, setChats] = useState<ChatMeta[]>([]);
  const [viewingReport, setViewingReport] = useState<{ path: string; content: string } | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => { messagesEndRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages]);

  const refreshReports = useCallback(async () => { try { const res = await fetch("/api/reports"); if (res.ok) setReportFiles(await res.json()); } catch {} }, []);
  const refreshChats = useCallback(async () => { try { const res = await fetch("/api/chats"); if (res.ok) setChats(await res.json()); } catch {} }, []);
  useEffect(() => { refreshReports(); refreshChats(); }, [messages, refreshReports, refreshChats]);

  const openReport = useCallback(async (relPath: string) => {
    const res = await fetch(`/reports/${relPath}`);
    if (res.ok && !res.headers.get("content-type")?.includes("text/html")) {
      setViewingReport({ path: relPath, content: await res.text() });
      return;
    }
    setViewingReport({ path: relPath, content: "无法加载文件内容" });
  }, []);

  const handleDeleteChat = useCallback(async (id: string) => {
    try {
      const res = await fetch(`/api/chats/${encodeURIComponent(id)}`, { method: "DELETE" });
      if (res.ok) {
        if (id === chatId) newChat();
        refreshChats();
      }
    } catch {}
  }, [chatId, newChat, refreshChats]);

  const handleSend = useCallback((text?: string) => { const content = text || input.trim(); if (!content && !uploadedFiles.length) return; setViewingReport(null); sendMessage(content, uploadedFiles.length ? uploadedFiles : undefined); setInput(""); clearFiles(); }, [input, uploadedFiles, sendMessage, clearFiles]);
  const handleKeyDown = (e: React.KeyboardEvent) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleSend(); } };
  const handleFileSelect = async (files: FileList | null) => { if (!files) return; for (const file of Array.from(files)) await upload(file); };

  return (
    <div className="h-screen flex bg-paper text-stone-800">
      <ReportsSidebar chats={chats} activeChatId={chatId} files={reportFiles} onSwitchChat={switchChat} onDeleteChat={handleDeleteChat} onNewChat={newChat} onFileClick={openReport} onRefresh={refreshReports} />
      <div className="flex-1 flex flex-col min-w-0">
        <header className="flex items-center justify-between px-5 py-3.5 border-b border-stone-200/70 glass shrink-0">
          <div className="flex items-center gap-2.5">
            <h1 className="text-base font-semibold text-stone-800">{viewingReport ? "报告预览" : "对话"}</h1>
          </div>
          <div className="flex items-center gap-2">
            <span className={`w-2 h-2 rounded-full ${isConnected ? "bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.5)]" : "bg-red-400"}`} />
            <span className="text-xs text-stone-400">{isConnected ? "已连接" : "断开"}</span>
          </div>
        </header>
        {viewingReport ? (
          <ReportView reportPath={viewingReport.path} content={viewingReport.content} onClose={() => setViewingReport(null)} />
        ) : (
          <>
            <main className="flex-1 overflow-y-auto chat-bg">
              <div className="max-w-3xl mx-auto px-4 py-6">
                {messages.length === 0 ? <WelcomeScreen onStart={handleSend} /> : messages.map((msg) => <MessageBubble key={msg.id} msg={msg} />)}
                {isThinking && (<div className="flex justify-start mb-3 animate-fade-up"><div className="bg-white border border-stone-200 rounded-2xl rounded-bl-md px-4 py-2.5 text-stone-500 text-sm flex items-center gap-2 shadow-sm"><span className="inline-block w-1.5 h-1.5 bg-amber-500 rounded-full animate-dot-bounce" style={{ animationDelay: "0ms" }} /><span className="inline-block w-1.5 h-1.5 bg-amber-500 rounded-full animate-dot-bounce" style={{ animationDelay: "150ms" }} /><span className="inline-block w-1.5 h-1.5 bg-amber-500 rounded-full animate-dot-bounce" style={{ animationDelay: "300ms" }} />分析中...</div></div>)}
                <div ref={messagesEndRef} />
              </div>
            </main>
            {uploadedFiles.length > 0 && (<div className="px-4 py-2 glass border-t border-stone-200/70 flex items-center gap-2 flex-wrap shrink-0">{uploadedFiles.map((f) => (<span key={f.path} className="bg-white border border-stone-200 rounded-lg px-2.5 py-1 text-xs text-stone-600 shadow-sm">📎 {f.name}</span>))}<button onClick={clearFiles} className="text-xs text-red-500 hover:text-red-600 ml-1 transition-colors">清除</button></div>)}
            <div className="px-4 py-3.5 glass border-t border-stone-200/70 shrink-0">
              <div className="max-w-3xl mx-auto flex items-end gap-2">
                <input type="file" ref={fileInputRef} className="hidden" accept=".csv,.xlsx,.xls,.txt,.pdf,.doc,.docx,.md,.png,.jpg,.jpeg,.webp" multiple onChange={(e) => handleFileSelect(e.target.files)} />
                <button onClick={() => fileInputRef.current?.click()} disabled={uploading} className="p-2.5 rounded-xl bg-white border border-stone-200 hover:border-amber-300 hover:text-amber-600 text-stone-400 transition-all shadow-sm active:scale-90 shrink-0" title="上传文件（图片可作图生图参考）">{uploading ? "⏳" : "📎"}</button>
                <textarea value={input} onChange={(e) => setInput(e.target.value)} onKeyDown={handleKeyDown} placeholder="输入 ASIN、URL 或分析需求，如「深度调研 B07PWTJ4H1」..." rows={1} className="flex-1 bg-white border border-stone-200 text-stone-800 rounded-xl px-4 py-2.5 resize-none outline-none focus:border-amber-400 focus:ring-4 focus:ring-amber-500/10 placeholder-stone-400 transition-all text-sm shadow-sm" />
                {isThinking ? (
                  <button onClick={stop} className="p-2.5 rounded-xl bg-red-50 border border-red-200 hover:bg-red-100 text-red-500 transition-all active:scale-90 shrink-0" title="停止本次任务">⏹</button>
                ) : (
                  <button onClick={() => handleSend()} disabled={(!input.trim() && !uploadedFiles.length) || !isConnected} className="p-2.5 rounded-xl bg-gradient-to-br from-amber-500 to-orange-600 hover:from-amber-400 hover:to-orange-500 disabled:from-stone-200 disabled:to-stone-200 disabled:text-stone-400 text-white transition-all shadow-lg shadow-orange-500/30 disabled:shadow-none active:scale-90 shrink-0">➤</button>
                )}
              </div>
            </div>
          </>
        )}
      </div>
      <ProgressPanel messages={messages} />
    </div>
  );
}
