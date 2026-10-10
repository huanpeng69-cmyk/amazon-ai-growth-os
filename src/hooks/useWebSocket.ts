import { useState, useEffect, useRef, useCallback } from "react";
import type { ChatMessage } from "../types";

let globalId = 0;
const uid = () => `msg_${++globalId}_${Date.now()}`;

// 默认会话 ID：localStorage 持久化，刷新页面不丢失
function getDefaultChatId(): string {
  try {
    let id = localStorage.getItem("amazon_skills_chat_id");
    if (!id) {
      id = `chat_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
      localStorage.setItem("amazon_skills_chat_id", id);
    }
    return id;
  } catch {
    return "default";
  }
}

export function useWebSocket() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const [isThinking, setIsThinking] = useState(false);
  const [chatId, setChatId] = useState<string>(() => getDefaultChatId());
  const wsRef = useRef<WebSocket | null>(null);
  const retryRef = useRef(0);
  const chatIdRef = useRef(chatId);

  useEffect(() => { chatIdRef.current = chatId; }, [chatId]);

  const connect = useCallback(() => {
    const proto = location.protocol === "https:" ? "wss:" : "ws:";
    const ws = new WebSocket(`${proto}//${location.host}/ws`);
    wsRef.current = ws;

    ws.onopen = () => {
      setIsConnected(true);
      retryRef.current = 0;
      ws.send(JSON.stringify({ type: "subscribe", chatId: chatIdRef.current }));
    };
    ws.onclose = () => {
      setIsConnected(false);
      const delay = Math.min(1000 * 2 ** retryRef.current, 10000);
      retryRef.current++;
      setTimeout(connect, delay);
    };
    ws.onmessage = (e) => {
      const msg = JSON.parse(e.data);
      if (msg.type === "subscribed") return;

      // 历史消息恢复（订阅后/切换会话后）
      if (msg.type === "history") {
        if (msg.chatId !== chatIdRef.current) return;
        const history: ChatMessage[] = (msg.messages || []).map((m: { role: string; content: string }) => ({
          id: uid(), role: m.role as ChatMessage["role"], content: m.content,
        }));
        setMessages(history);
        return;
      }

      if (msg.type === "user_message") {
        setMessages((p) => [...p, { id: uid(), role: "user", content: msg.content }]);
        setIsThinking(true);
        return;
      }
      // 服务端实时推送的生成图片（生成一张看一张）
      if (msg.type === "image") {
        setMessages((p) => [...p, { id: uid(), role: "image", content: msg.path }]);
        return;
      }
      if (msg.type === "assistant_message") {
        setMessages((p) => {
          const last = p[p.length - 1];
          if (last?.role === "assistant" && !last.toolCall) return [...p.slice(0, -1), { ...last, content: last.content + msg.content }];
          return [...p, { id: uid(), role: "assistant", content: msg.content }];
        });
        setIsThinking(false);
        return;
      }
      if (msg.type === "tool_use") {
        const tc = { name: msg.toolName, input: msg.toolInput, status: "running" as const };
        setMessages((p) => [...p, { id: uid(), role: "system", content: "", toolCall: tc }]);
        setIsThinking(true);
        return;
      }
      if (msg.type === "result") {
        setMessages((p) => {
          const idx = p.length - 1;
          const last = p[idx];
          if (last?.toolCall && last.toolCall.status === "running") {
            const updated = [...p];
            updated[idx] = { ...last, toolCall: { ...last.toolCall, status: "done" } };
            return updated;
          }
          return p;
        });
        setIsThinking(false);
        return;
      }
      if (msg.type === "error") {
        setMessages((p) => [...p, { id: uid(), role: "system", content: `Error: ${msg.error}` }]);
        setIsThinking(false);
      }
    };
  }, []);

  useEffect(() => { connect(); return () => wsRef.current?.close(); }, [connect]);

  const sendMessage = useCallback((content: string, files?: { name: string; path: string }[]) => {
    const payload = files?.length ? `${content}\n\n附件文件：${files.map((f) => `${f.name} (${f.path})`).join(", ")}` : content;
    wsRef.current?.send(JSON.stringify({ type: "chat", chatId: chatIdRef.current, content: payload }));
  }, []);

  const stop = useCallback(() => {
    wsRef.current?.send(JSON.stringify({ type: "stop", chatId: chatIdRef.current }));
  }, []);

  // 切换到已有会话（服务端会回发该会话历史）
  const switchChat = useCallback((newChatId: string) => {
    if (newChatId === chatIdRef.current) return;
    setChatId(newChatId);
    chatIdRef.current = newChatId;
    try { localStorage.setItem("amazon_skills_chat_id", newChatId); } catch { /* ignore */ }
    setMessages([]);
    setIsThinking(false);
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: "subscribe", chatId: newChatId }));
    }
  }, []);

  // 开启新会话
  const newChat = useCallback(() => {
    const id = `chat_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
    switchChat(id);
  }, [switchChat]);

  return { messages, sendMessage, stop, isConnected, isThinking, chatId, switchChat, newChat };
}
