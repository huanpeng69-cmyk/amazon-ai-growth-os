import express from "express";
import { createServer } from "http";
import { WebSocketServer, WebSocket } from "ws";
import multer from "multer";
import { AgentSession, SDKMessage } from "./agent-client.js";
import { fileLog } from "./logger.js";
import { loadChat, appendMessage, listChats, deleteChat, StoredMessage } from "./chat-store.js";
import path from "path";
import { fileURLToPath } from "url";
import fs from "fs";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

interface ClientWS extends WebSocket {
  isAlive: boolean;
  chatId?: string;
}

interface Session {
  id: string;
  agent: AgentSession;
  subscribers: Set<ClientWS>;
  listening: boolean;
  pendingAssistant: string;
}

interface OutMessage {
  type: string;
  content?: string;
  toolName?: string;
  toolInput?: unknown;
  path?: string;
  success?: boolean;
  cost?: number;
  duration?: number;
  error?: string;
}

const sessions = new Map<string, Session>();
const UPLOAD_DIR = path.resolve(process.cwd(), "uploads");
const REPORTS_DIR = path.resolve(process.cwd(), "reports");
const REVIEW_REPORTS_DIR = path.resolve(process.cwd(), "review-analysis-reports");

[UPLOAD_DIR, REPORTS_DIR, REVIEW_REPORTS_DIR].forEach((d) => {
  if (!fs.existsSync(d)) fs.mkdirSync(d, { recursive: true });
});

const upload = multer({
  storage: multer.diskStorage({
    destination: (_req, _file, cb) => cb(null, UPLOAD_DIR),
    filename: (_req, file, cb) => {
      // 保留原始扩展名（图生图需要识别 png/jpg/webp）；随机名防覆盖
      const ext = path.extname(file.originalname).toLowerCase();
      cb(null, `${Date.now()}-${Math.random().toString(36).slice(2, 8)}${ext}`);
    },
  }),
  limits: { fileSize: 50 * 1024 * 1024 },
  fileFilter: (_req, file, cb) => {
    const allowed = [".csv", ".xlsx", ".xls", ".txt", ".md", ".png", ".jpg", ".jpeg", ".webp"];
    const ext = path.extname(file.originalname).toLowerCase();
    cb(null, allowed.includes(ext));
  },
});

function getOrCreateSession(chatId: string): Session {
  let session = sessions.get(chatId);
  if (!session) {
    fileLog("Server", "New session:", chatId);
    session = { id: chatId, agent: new AgentSession(), subscribers: new Set(), listening: false, pendingAssistant: "" };
    sessions.set(chatId, session);
  }
  return session;
}

function broadcast(session: Session, data: OutMessage) {
  const msg = JSON.stringify(data);
  fileLog("WS.out", data.type, data.toolName || data.content?.substring(0, 60) || "");
  for (const client of session.subscribers) {
    if (client.readyState === WebSocket.OPEN) client.send(msg);
  }
}

function formatMessage(message: SDKMessage): OutMessage | null {
  // Direct API mode messages (already in OutMessage format)
  if (message.type === "assistant_message" || message.type === "tool_use" || message.type === "error" || message.type === "image") {
    return message as unknown as OutMessage;
  }
  // SDK mode messages
  if (message.type === "assistant" && message.message) {
    for (const block of message.message.content) {
      if (block.type === "text" && block.text) {
        return { type: "assistant_message", content: block.text };
      }
      if (block.type === "tool_use") {
        return { type: "tool_use", toolName: block.name, toolInput: block.input };
      }
    }
  }
  if (message.type === "result") {
    return { type: "result", success: message.subtype === "success", cost: message.total_cost_usd, duration: message.duration_ms };
  }
  return null;
}

async function startListening(session: Session) {
  if (session.listening) return;
  session.listening = true;

  const flushAssistant = () => {
    if (session.pendingAssistant.trim()) {
      appendMessage(session.id, { role: "assistant", content: session.pendingAssistant, ts: Date.now() });
      session.pendingAssistant = "";
    }
  };

  try {
    for await (const message of session.agent.getOutputStream()) {
      const out = formatMessage(message);
      if (!out) continue;
      // 持久化：assistant 文本累积，result/error 时落盘
      if (out.type === "assistant_message" && out.content && out.content !== "正在思考...") {
        session.pendingAssistant += out.content;
      }
      // 生成的图片即时落盘到历史（role=image），刷新/切会话后仍可预览
      if (out.type === "image" && out.path) {
        appendMessage(session.id, { role: "image", content: out.path, ts: Date.now() });
      }
      if (out.type === "result" || out.type === "error") flushAssistant();
      broadcast(session, out);
    }
  } catch (error: unknown) {
    const msg = error instanceof Error ? error.message : String(error);
    fileLog("Server", "listen error:", msg);
    flushAssistant();
    broadcast(session, { type: "error", error: msg });
  } finally {
    session.listening = false;
  }
}

function scanDir(dir: string, base: string): any[] {
  const items: any[] = [];
  try {
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      const fullPath = path.join(dir, entry.name);
      const relPath = path.relative(base, fullPath).replace(/\\/g, "/");
      if (entry.isDirectory()) {
        const children = scanDir(fullPath, base);
        if (children.length > 0) {
          items.push({ name: entry.name, path: relPath, type: "directory", children });
        }
      } else {
        items.push({ name: entry.name, path: relPath, type: "file" });
      }
    }
  } catch { /* ignore */ }
  return items;
}

function scanReports(): any[] {
  const tree: any[] = [];

  const reports = scanDir(REPORTS_DIR, REPORTS_DIR);
  if (reports.length > 0) {
    tree.push({ name: "reports", path: "reports", type: "directory", children: reports });
  }

  const reviewReports = scanDir(REVIEW_REPORTS_DIR, REVIEW_REPORTS_DIR);
  if (reviewReports.length > 0) {
    tree.push({ name: "review-analysis-reports", path: "review-analysis-reports", type: "directory", children: reviewReports });
  }

  return tree;
}

// --- Express ---
const app = express();
app.use(express.json());
const distPath = path.resolve(process.cwd(), "dist");
app.use(express.static(distPath));
app.use("/reports", express.static(REPORTS_DIR));
app.use("/review-analysis-reports", express.static(REVIEW_REPORTS_DIR));
app.use("/generated-images", express.static(path.resolve(process.cwd(), "generated-images")));
app.use("/uploads", express.static(UPLOAD_DIR));

app.get("/api/sessions", (_req, res) => res.json([...sessions.keys()]));
app.get("/api/health", (_req, res) => {
  res.json({ status: "ok", sessions: sessions.size, env: {
    MODEL: process.env.MODEL || "(not set)",
    BASE_URL: process.env.ANTHROPIC_BASE_URL || "(not set)",
    HAS_KEY: !!process.env.ANTHROPIC_API_KEY,
  }});
});

app.get("/api/files", (_req, res) => {
  const files = fs.readdirSync(UPLOAD_DIR).map((name) => {
    const stat = fs.statSync(path.join(UPLOAD_DIR, name));
    return { name, path: `uploads/${name}`, size: stat.size, modified: stat.mtime };
  });
  res.json(files);
});

app.get("/api/reports", (_req, res) => {
  const tree = scanReports();
  res.json(tree);
});

app.get("/api/chats", (_req, res) => {
  res.json(listChats());
});

app.delete("/api/chats/:chatId", (req, res) => {
  const chatId = req.params.chatId;
  const session = sessions.get(chatId);
  if (session && (session.listening || session.subscribers.size > 0)) {
    return res.status(409).json({ error: "会话正在使用中，无法删除" });
  }
  if (session) { session.agent.close(); sessions.delete(chatId); }
  const ok = deleteChat(chatId);
  res.json({ ok });
});

app.post("/api/upload", upload.single("file"), (req, res) => {
  if (!req.file) return res.status(400).json({ error: "No file uploaded" });
  const result = {
    name: req.file.originalname,
    path: `uploads/${req.file.filename}`,
    size: req.file.size,
  };
  fileLog("Upload", result.name, result.path);
  res.json(result);
});

app.get("*", (_req, res) => res.sendFile(path.join(distPath, "index.html")));

// --- WebSocket ---
const server = createServer(app);
const wss = new WebSocketServer({ server, path: "/ws" });

wss.on("connection", (ws: ClientWS) => {
  fileLog("WS", "Client connected");
  ws.isAlive = true;
  ws.on("pong", () => { ws.isAlive = true; });

  ws.on("message", (data) => {
    let msg: any;
    try { msg = JSON.parse(data.toString()); } catch { return; }

    fileLog("WS.in", msg.type, (msg.content || msg.chatId || "").substring(0, 60));

    if (msg.type === "subscribe") {
      const chatId = msg.chatId || "default";
      // 先从所有旧会话移除订阅，避免切换会话后收到旧会话广播
      for (const s of sessions.values()) s.subscribers.delete(ws);
      const session = getOrCreateSession(chatId);
      session.subscribers.add(ws);
      ws.chatId = chatId;
      ws.send(JSON.stringify({ type: "subscribed", chatId }));
      // 回发历史消息（刷新/切换会话后恢复上下文）
      const history: StoredMessage[] = loadChat(chatId);
      ws.send(JSON.stringify({ type: "history", chatId, messages: history }));
    }

    if (msg.type === "chat") {
      const chatId = msg.chatId || "default";
      const session = getOrCreateSession(chatId);
      session.subscribers.add(ws);
      ws.chatId = chatId;
      appendMessage(chatId, { role: "user", content: msg.content, ts: Date.now() });
      broadcast(session, { type: "user_message", content: msg.content });
      session.agent.sendMessage(msg.content);
      startListening(session);
    }

    if (msg.type === "stop") {
      const chatId = msg.chatId || "default";
      const session = sessions.get(chatId);
      if (session) {
        fileLog("WS", "Stop requested:", chatId);
        session.agent.stop();
      }
    }
  });

  ws.on("close", () => {
    for (const session of sessions.values()) session.subscribers.delete(ws);
  });
});

// Cleanup empty sessions every 5 minutes
setInterval(() => {
  for (const [id, session] of sessions) {
    if (session.subscribers.size === 0 && !session.listening) {
      session.agent.close();
      sessions.delete(id);
    }
  }
}, 5 * 60 * 1000);

setInterval(() => { wss.clients.forEach((ws) => { const c = ws as ClientWS; if (!c.isAlive) return c.terminate(); c.isAlive = false; c.ping(); }); }, 30000);

const PORT = process.env.PORT ? parseInt(process.env.PORT) : 3014;
server.listen(PORT, () => { fileLog("Server", `Amazon AI Growth OS Server listening on :${PORT}`); });
