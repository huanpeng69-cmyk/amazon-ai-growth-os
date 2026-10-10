export interface ChatMessage {
  id: string;
  role: "user" | "assistant" | "system" | "image";
  content: string;
  files?: { name: string; path: string }[];
  toolCall?: { name: string; input?: unknown; status: "running" | "done" };
}

export interface ReportFile {
  name: string;
  path: string;
  type: "file" | "directory";
  children?: ReportFile[];
}

export interface ChatMeta {
  chatId: string;
  lastTs: number;
  messageCount: number;
  preview: string;
}

export interface StoredMessage {
  role: "user" | "assistant" | "image";
  content: string;
  ts: number;
}
