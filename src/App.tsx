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
    accent: "from-amber-500/20 to-orange-600/5 border-amber-500/25",
    chip: "bg-amber-500/15 text-amber-300 ring-amber-500/30",
    fields: [
      { key: "asin", label: "ASIN 或产品 URL", placeholder: "如 B07PWTJ4H1" },
      { key: "market", label: "市场（可选，默认美国）", type: "select", options: MARKET_OPTIONS, optional: true },
    ],
    build: (v) => `深度调研 ${v.asin}${v.market ? `（${v.market}市场）` : ""}`,
  },
  {
    icon: "🔍", title: "关键词研究", desc: "长尾词+机会评分",
    accent: "from-sky-500/20 to-cyan-600/5 border-sky-500/25",
    chip: "bg-sky-500/15 text-sky-300 ring-sky-500/30",
    fields: [
      { key: "keyword", label: "种子关键词", placeholder: "如 portable blender" },
      { key: "market", label: "市场（可选，默认美国）", type: "select", options: MARKET_OPTIONS, optional: true },
    ],
    build: (v) => `研究关键词 "${v.keyword}" 在亚马逊${v.market || "美国"}的机会`,
  },
  {
    icon: "📝", title: "Listing优化", desc: "创建/优化Listing",
    accent: "from-emerald-500/20 to-teal-600/5 border-emerald-500/25",
    chip: "bg-emerald-500/15 text-emerald-300 ring-emerald-500/30",
    fields: [
      { key: "asin", label: "ASIN 或产品 URL", placeholder: "如 B0D72TSM62" },
      { key: "notes", label: "需求说明（可选）", placeholder: "如：突出便携和续航", optional: true },
    ],
    build: (v) => `帮我优化这个产品的Listing：${v.asin}${v.notes ? `。需求：${v.notes}` : ""}`,
  },
  {
    icon: "💰", title: "FBA计算", desc: "费用明细+利润分析",
    accent: "from-violet-500/20 to-purple-600/5 border-violet-500/25",
    chip: "bg-violet-500/15 text-violet-300 ring-violet-500/30",
    fields: [
      { key: "price", label: "售价（美元）", placeholder: "如 29.99" },
      { key: "cost", label: "采购成本（美元）", placeholder: "如 8" },
      { key: "weight", label: "重量（磅）", placeholder: "如 1.2" },
    ],
    build: (v) => `帮我计算FBA费用：售价 $${v.price}，成本 $${v.cost}，重量 ${v.weight} 磅`,
  },
  {
    icon: "📊", title: "销量估算", desc: "月销量+营收",
    accent: "from-cyan-500/20 to-blue-600/5 border-cyan-500/25",
    chip: "bg-cyan-500/15 text-cyan-300 ring-cyan-500/30",
    fields: [
      { key: "bsr", label: "BSR 或 ASIN", placeholder: "如 1500 或 B09V3KXJPB" },
      { key: "market", label: "市场（可选，默认美国）", type: "select", options: MARKET_OPTIONS, optional: true },
    ],
    build: (v) => `估算 ${v.bsr} 的月销量${v.market ? `（${v.market}市场）` : ""}`,
  },
  {
    icon: "📢", title: "PPC广告", desc: "广告结构+出价策略",
    accent: "from-indigo-500/20 to-blue-600/5 border-indigo-500/25",
    chip: "bg-indigo-500/15 text-indigo-300 ring-indigo-500/30",
    fields: [
      { key: "asin", label: "ASIN 或产品 URL", placeholder: "如 B0D72TSM62" },
      { key: "budget", label: "日预算（美元）", placeholder: "如 50" },
    ],
    build: (v) => `帮我搭建PPC广告结构，产品 ${v.asin}，预算 $${v.budget}/天`,
  },
  {
    icon: "🚀", title: "自动上架", desc: "填表+截图确认后提交",
    accent: "from-rose-500/20 to-red-600/5 border-rose-500/25",
    chip: "bg-rose-500/15 text-rose-300 ring-rose-500/30",
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
    accent: "from-pink-500/20 to-fuchsia-600/5 border-pink-500/25",
    chip: "bg-pink-500/15 text-pink-300 ring-pink-500/30",
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
  return (<div>{files.map((f) => (<div key={f.path}>{f.type === "directory" ? (<div><div className="px-2 py-1 text-xs text-slate-500 font-medium tracking-wide" style={{ paddingLeft: `${depth * 12 + 8}px` }}>▸ {f.name}</div>{f.children && <FileTree files={f.children} onFileClick={onFileClick} depth={depth + 1} />}</div>) : (<button onClick={() => onFileClick(f.path)} className="w-full text-left px-2 py-1.5 text-xs text-slate-300 hover:bg-white/5 hover:text-amber-300 rounded-lg mx-1 truncate transition-colors" style={{ paddingLeft: `${depth * 12 + 8}px`, width: "calc(100% - 8px)" }}>📄 {f.name}</button>)}</div>))}</div>);
}

function ChatList({ chats, activeChatId, onSwitch, onDelete, onNew }: {
  chats: ChatMeta[]; activeChatId: string; onSwitch: (id: string) => void; onDelete: (id: string) => void; onNew: () => void;
}) {
  return (
    <div className="flex flex-col max-h-[35%] shrink-0">
      <div className="flex items-center justify-between px-4 py-3 shrink-0">
        <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">历史会话</span>
        <button onClick={onNew} className="text-xs text-amber-400 hover:text-amber-300 px-2 py-1 rounded-md hover:bg-amber-500/10 transition-colors">＋ 新会话</button>
      </div>
      <div className="flex-1 overflow-y-auto px-2 space-y-0.5">
        {chats.length === 0 && <p className="text-xs text-slate-600 text-center mt-2 px-2">暂无历史会话</p>}
        {chats.map((c) => (
          <div key={c.chatId} className={`group flex items-center gap-1.5 px-2.5 py-2 cursor-pointer rounded-lg transition-colors ${c.chatId === activeChatId ? "bg-amber-500/10 ring-1 ring-amber-500/25" : "hover:bg-white/5"}`} onClick={() => onSwitch(c.chatId)}>
            <div className="flex-1 min-w-0">
              <p className={`text-xs truncate ${c.chatId === activeChatId ? "text-amber-300" : "text-slate-300"}`}>{c.preview || c.chatId}</p>
              <p className="text-[10px] text-slate-600 mt-0.5">{new Date(c.lastTs).toLocaleString()} · {c.messageCount} 条</p>
            </div>
            <button onClick={(e) => { e.stopPropagation(); onDelete(c.chatId); }} className="text-[11px] text-slate-600 hover:text-red-400 opacity-0 group-hover:opacity-100 shrink-0 transition-opacity" title="删除会话">✕</button>
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
    <aside className="w-[280px] border-r border-white/5 bg-[#0d1119] flex flex-col shrink-0">
      <div className="flex items-center gap-2.5 px-4 py-4 border-b border-white/5 shrink-0">
        <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-amber-400 to-orange-600 flex items-center justify-center text-base shadow-lg shadow-amber-500/20">🔍</div>
        <div>
          <p className="text-sm font-semibold text-slate-100 leading-tight">AmazonSkillsChat</p>
          <p className="text-[10px] text-slate-500">AI 亚马逊卖家助手</p>
        </div>
      </div>
      <ChatList chats={chats} activeChatId={activeChatId} onSwitch={onSwitchChat} onDelete={onDeleteChat} onNew={onNewChat} />
      <div className="flex items-center justify-between px-4 py-3 border-t border-white/5 shrink-0">
        <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">分析报告</span>
        <button onClick={onRefresh} className="text-xs text-slate-500 hover:text-slate-300 transition-colors">刷新</button>
      </div>
      <div className="flex-1 overflow-y-auto pb-3">
        {files.length === 0 && <p className="text-xs text-slate-600 text-center mt-4 px-4 leading-relaxed">尚无报告<br />输入需求开始分析</p>}
        <FileTree files={files} onFileClick={onFileClick} />
      </div>
    </aside>
  );
}

function ProgressPanel({ messages }: { messages: ChatMessage[] }) {
  const toolCalls = messages.filter((m) => m.toolCall);
  if (toolCalls.length === 0) return null;
  return (
    <aside className="w-[230px] border-l border-white/5 bg-[#0d1119] flex flex-col shrink-0">
      <div className="px-4 py-3 border-b border-white/5 shrink-0"><span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">执行日志</span></div>
      <div className="flex-1 overflow-y-auto p-2.5 space-y-1">
        {toolCalls.map((m) => (<div key={m.id} className={`flex items-center gap-2 py-1.5 px-2.5 rounded-lg ${m.toolCall!.status === "running" ? "bg-amber-500/10" : ""}`}>
          {m.toolCall!.status === "done" && <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 shrink-0" />}
          {m.toolCall!.status === "running" && <span className="inline-block w-2 h-2 bg-amber-400 rounded-full animate-pulse shrink-0" />}
          <span className={`text-xs font-mono truncate ${m.toolCall!.status === "running" ? "text-amber-300" : "text-slate-500"}`}>{m.toolCall!.name}</span>
        </div>))}
      </div>
    </aside>
  );
}

function MessageBubble({ msg }: { msg: ChatMessage }) {
  if (msg.role === "user") return (<div className="flex justify-end mb-4 animate-fade-up"><div className="bg-gradient-to-br from-amber-500 to-orange-600 text-white rounded-2xl rounded-br-md px-4 py-2.5 max-w-[80%] whitespace-pre-wrap shadow-lg shadow-amber-900/30">{msg.content}{msg.files?.map((f) => (<div key={f.path} className="text-xs text-amber-100 mt-1.5 flex items-center gap-1">📎 {f.name}</div>))}</div></div>);
  if (msg.role === "system" && msg.toolCall) { const tc = msg.toolCall; return (<div className="flex justify-start mb-2.5 animate-fade-up"><div className={`rounded-xl px-3.5 py-2.5 max-w-[85%] text-sm ${tc.status === "running" ? "bg-amber-500/10 border border-amber-500/25" : "bg-white/[0.03] border border-white/10"}`}><div className="flex items-center gap-2">{tc.status === "running" ? <span className="inline-block w-2 h-2 bg-amber-400 rounded-full animate-pulse" /> : <span className="inline-block w-2 h-2 bg-emerald-400 rounded-full" />}<span className="font-mono text-[13px] text-slate-300">{tc.name}</span></div>{tc.status === "running" && tc.input !== undefined && tc.input !== null && <pre className="text-xs text-slate-500 mt-1.5 max-h-20 overflow-hidden font-mono">{String(typeof tc.input === "string" ? tc.input : (JSON.stringify(tc.input as Record<string, unknown>, null, 2) || "")).slice(0, 200)}</pre>}</div></div>); }
  if (msg.role === "system") return (<div className="flex justify-center mb-3"><div className="bg-red-500/10 border border-red-500/20 text-red-300 rounded-xl px-4 py-2 text-sm max-w-[85%] text-center">{msg.content}</div></div>);
  if (msg.role === "image") return (<div className="flex justify-start mb-4 animate-fade-up"><div className="bg-white/[0.03] border border-white/10 rounded-2xl rounded-bl-md p-2.5 max-w-[85%]"><a href={`/${msg.content}`} target="_blank" rel="noreferrer"><img src={`/${msg.content}`} alt={msg.content} className="rounded-xl max-h-80 w-auto cursor-zoom-in hover:opacity-90 transition-opacity" loading="lazy" /></a><p className="text-[10px] text-slate-600 mt-1.5 truncate font-mono">🖼 {msg.content}</p></div></div>);
  return (<div className="flex justify-start mb-4 animate-fade-up"><div className="bg-[#131826] border border-white/8 text-slate-100 rounded-2xl rounded-bl-md px-4.5 py-3 max-w-[88%] md-body"><ReactMarkdown>{msg.content}</ReactMarkdown></div></div>);
}

function TemplateForm({ template, onStart, onCancel }: { template: Template; onStart: (text: string) => void; onCancel: () => void }) {
  const [values, setValues] = useState<Record<string, string>>({});
  const { uploading, upload } = useFileUpload();
  const imgInputRef = useRef<HTMLInputElement>(null);
  const requiredOk = template.fields.filter((f) => !f.optional).every((f) => (values[f.key] || "").trim());
  return (
    <div className={`bg-gradient-to-b ${template.accent} rounded-2xl p-5 w-full max-w-md border shadow-xl shadow-black/30 animate-fade-up`}>
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2.5">
          <span className="w-9 h-9 rounded-xl bg-black/30 flex items-center justify-center text-lg">{template.icon}</span>
          <div>
            <p className="text-sm font-semibold text-slate-100">{template.title}</p>
            <p className="text-xs text-slate-400">{template.desc}</p>
          </div>
        </div>
        <button onClick={onCancel} className="text-xs text-slate-400 hover:text-slate-200 px-2.5 py-1 rounded-lg hover:bg-white/5 transition-colors">← 返回</button>
      </div>
      <div className="flex flex-col gap-3">
        {template.fields.map((f) => (
          <div key={f.key} className="flex flex-col gap-1.5">
            <label className="text-xs text-slate-400 flex items-center gap-1.5">{f.label}{f.optional && <span className="text-[10px] text-slate-600">可选</span>}</label>
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
                  <div className="flex items-center gap-2.5 bg-black/30 border border-white/10 rounded-xl p-2">
                    <img src={`/${values[f.key]}`} alt="参考图" className="h-12 w-12 rounded-lg object-cover" />
                    <span className="text-xs text-slate-400 flex-1 truncate font-mono">{values[f.key]}</span>
                    <button onClick={() => setValues((p) => ({ ...p, [f.key]: "" }))} className="text-xs text-red-400 hover:text-red-300 px-2 py-1 rounded-md hover:bg-red-500/10 transition-colors">清除</button>
                  </div>
                ) : (
                  <button onClick={() => imgInputRef.current?.click()} disabled={uploading}
                    className="w-full bg-black/20 text-slate-400 text-sm rounded-xl px-3 py-2.5 border border-dashed border-white/15 hover:border-amber-500/50 hover:text-amber-400 transition-colors text-left">
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
          className="mt-2 bg-gradient-to-r from-amber-500 to-orange-600 hover:from-amber-400 hover:to-orange-500 disabled:from-slate-700 disabled:to-slate-700 disabled:text-slate-500 text-white text-sm font-medium rounded-xl px-4 py-2.5 transition-all shadow-lg shadow-amber-900/30 disabled:shadow-none">
          开始分析 →
        </button>
      </div>
    </div>
  );
}

function WelcomeScreen({ onStart }: { onStart: (text: string) => void }) {
  const [selected, setSelected] = useState<Template | null>(null);
  return (
    <div className="flex flex-col items-center justify-center min-h-full text-slate-400 gap-5 py-10">
      <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-amber-400 to-orange-600 flex items-center justify-center text-3xl shadow-xl shadow-amber-500/20">🔍</div>
      <div className="text-center">
        <h2 className="text-xl font-semibold text-slate-100">欢迎回来 👋</h2>
        <p className="text-sm mt-1.5">56 个专业技能 · 浏览器自动化 · 12 个市场 · 全中文分析 · AI 图包生成</p>
      </div>
      {selected ? (
        <TemplateForm template={selected} onStart={onStart} onCancel={() => setSelected(null)} />
      ) : (
        <div className="grid grid-cols-2 gap-3 mt-3 max-w-xl w-full px-4">
          {TEMPLATES.map((t) => (
            <button key={t.title} onClick={() => setSelected(t)}
              className={`card-hover bg-gradient-to-b ${t.accent} bg-[#131826]/40 rounded-2xl px-4 py-4 text-left border`}>
              <span className={`inline-flex w-9 h-9 rounded-xl items-center justify-center text-lg ${t.chip} ring-1`}>{t.icon}</span>
              <p className="text-sm font-medium text-slate-100 mt-2.5">{t.title}</p>
              <p className="text-xs text-slate-500 mt-0.5">{t.desc}</p>
            </button>
          ))}
        </div>
      )}
      <p className="text-xs text-slate-600 mt-1">或在下方输入任意需求，如「深度调研 B07PWTJ4H1」</p>
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
      <div className="flex items-center justify-between px-5 py-3 border-b border-white/5 glass shrink-0">
        <span className="text-sm text-slate-300 truncate font-medium">📄 {reportPath}</span>
        <div className="flex gap-2 shrink-0">
          <button onClick={download} className="text-xs text-amber-400 hover:text-amber-300 px-3 py-1.5 rounded-lg hover:bg-amber-500/10 transition-colors">⬇ 下载</button>
          <button onClick={onClose} className="text-xs text-slate-400 hover:text-slate-200 px-3 py-1.5 rounded-lg hover:bg-white/5 transition-colors">✕ 返回对话</button>
        </div>
      </div>
      <div className="flex-1 overflow-y-auto chat-bg">
        <article className="max-w-4xl mx-auto px-6 py-8 md-body bg-[#0d1119]/60 border border-white/5 rounded-2xl my-6 shadow-xl shadow-black/20">
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
    <div className="h-screen flex bg-[#090c12] text-slate-100">
      <ReportsSidebar chats={chats} activeChatId={chatId} files={reportFiles} onSwitchChat={switchChat} onDeleteChat={handleDeleteChat} onNewChat={newChat} onFileClick={openReport} onRefresh={refreshReports} />
      <div className="flex-1 flex flex-col min-w-0">
        <header className="flex items-center justify-between px-5 py-3.5 border-b border-white/5 glass shrink-0">
          <div className="flex items-center gap-2.5">
            <h1 className="text-base font-semibold text-slate-100">{viewingReport ? "报告预览" : "对话"}</h1>
          </div>
          <div className="flex items-center gap-2">
            <span className={`w-2 h-2 rounded-full ${isConnected ? "bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.6)]" : "bg-red-400"}`} />
            <span className="text-xs text-slate-500">{isConnected ? "已连接" : "断开"}</span>
          </div>
        </header>
        {viewingReport ? (
          <ReportView reportPath={viewingReport.path} content={viewingReport.content} onClose={() => setViewingReport(null)} />
        ) : (
          <>
            <main className="flex-1 overflow-y-auto chat-bg">
              <div className="max-w-3xl mx-auto px-4 py-6">
                {messages.length === 0 ? <WelcomeScreen onStart={handleSend} /> : messages.map((msg) => <MessageBubble key={msg.id} msg={msg} />)}
                {isThinking && (<div className="flex justify-start mb-3"><div className="bg-[#131826] border border-white/10 rounded-2xl rounded-bl-md px-4 py-2.5 text-slate-400 text-sm flex items-center gap-2"><span className="inline-block w-2 h-2 bg-amber-400 rounded-full animate-pulse" />分析中...</div></div>)}
                <div ref={messagesEndRef} />
              </div>
            </main>
            {uploadedFiles.length > 0 && (<div className="px-4 py-2 glass border-t border-white/5 flex items-center gap-2 flex-wrap shrink-0">{uploadedFiles.map((f) => (<span key={f.path} className="bg-white/5 border border-white/10 rounded-lg px-2.5 py-1 text-xs text-slate-300">📎 {f.name}</span>))}<button onClick={clearFiles} className="text-xs text-red-400 hover:text-red-300 ml-1 transition-colors">清除</button></div>)}
            <div className="px-4 py-3.5 glass border-t border-white/5 shrink-0">
              <div className="max-w-3xl mx-auto flex items-end gap-2">
                <input type="file" ref={fileInputRef} className="hidden" accept=".csv,.xlsx,.xls,.txt,.pdf,.doc,.docx,.md,.png,.jpg,.jpeg,.webp" multiple onChange={(e) => handleFileSelect(e.target.files)} />
                <button onClick={() => fileInputRef.current?.click()} disabled={uploading} className="p-2.5 rounded-xl bg-white/5 border border-white/10 hover:bg-white/10 text-slate-400 hover:text-slate-200 transition-colors shrink-0" title="上传文件（图片可作图生图参考）">{uploading ? "⏳" : "📎"}</button>
                <textarea value={input} onChange={(e) => setInput(e.target.value)} onKeyDown={handleKeyDown} placeholder="输入 ASIN、URL 或分析需求，如「深度调研 B07PWTJ4H1」..." rows={1} className="flex-1 bg-white/5 border border-white/10 text-slate-100 rounded-xl px-4 py-2.5 resize-none outline-none focus:border-amber-500/50 focus:ring-2 focus:ring-amber-500/15 placeholder-slate-600 transition-all text-sm" />
                {isThinking ? (
                  <button onClick={stop} className="p-2.5 rounded-xl bg-red-500/15 border border-red-500/30 hover:bg-red-500/25 text-red-300 transition-colors shrink-0" title="停止本次任务">⏹</button>
                ) : (
                  <button onClick={() => handleSend()} disabled={(!input.trim() && !uploadedFiles.length) || !isConnected} className="p-2.5 rounded-xl bg-gradient-to-br from-amber-500 to-orange-600 hover:from-amber-400 hover:to-orange-500 disabled:from-slate-700 disabled:to-slate-700 disabled:text-slate-500 text-white transition-all shadow-lg shadow-amber-900/30 disabled:shadow-none shrink-0">➤</button>
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
