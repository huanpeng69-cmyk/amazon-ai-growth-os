// 会话持久化：JSON 文件存储（零依赖，data/chats/{chatId}.json）
import fs from "fs";
import path from "path";

const DATA_DIR = path.resolve(process.cwd(), "data", "chats");

export interface StoredMessage {
  role: "user" | "assistant" | "image";
  content: string;
  ts: number;
}

export interface ChatMeta {
  chatId: string;
  lastTs: number;
  messageCount: number;
  preview: string;
}

function chatFile(chatId: string): string {
  // chatId 仅允许安全字符，防止路径穿越
  const safe = chatId.replace(/[^a-zA-Z0-9_-]/g, "_");
  return path.join(DATA_DIR, `${safe}.json`);
}

export function loadChat(chatId: string): StoredMessage[] {
  try {
    const raw = fs.readFileSync(chatFile(chatId), "utf-8");
    const data = JSON.parse(raw);
    return Array.isArray(data.messages) ? data.messages : [];
  } catch {
    return [];
  }
}

export function saveChat(chatId: string, messages: StoredMessage[]): void {
  try {
    if (!fs.existsSync(DATA_DIR)) fs.mkdirSync(DATA_DIR, { recursive: true });
    fs.writeFileSync(chatFile(chatId), JSON.stringify({ chatId, messages }, null, 0), "utf-8");
  } catch (e) {
    console.error("[ChatStore] save failed:", e);
  }
}

export function appendMessage(chatId: string, msg: StoredMessage): void {
  const messages = loadChat(chatId);
  messages.push(msg);
  saveChat(chatId, messages);
}

export function listChats(): ChatMeta[] {
  try {
    if (!fs.existsSync(DATA_DIR)) return [];
    const chats: ChatMeta[] = [];
    for (const file of fs.readdirSync(DATA_DIR)) {
      if (!file.endsWith(".json")) continue;
      try {
        const raw = fs.readFileSync(path.join(DATA_DIR, file), "utf-8");
        const data = JSON.parse(raw);
        const messages: StoredMessage[] = Array.isArray(data.messages) ? data.messages : [];
        if (messages.length === 0) continue;
        const last = messages[messages.length - 1];
        chats.push({
          chatId: data.chatId || file.replace(/\.json$/, ""),
          lastTs: last.ts || 0,
          messageCount: messages.length,
          preview: (last.content || "").replace(/\s+/g, " ").substring(0, 60),
        });
      } catch { /* skip corrupt file */ }
    }
    return chats.sort((a, b) => b.lastTs - a.lastTs);
  } catch {
    return [];
  }
}

export function deleteChat(chatId: string): boolean {
  try {
    const file = chatFile(chatId);
    if (fs.existsSync(file)) {
      fs.unlinkSync(file);
      return true;
    }
    return false;
  } catch {
    return false;
  }
}
