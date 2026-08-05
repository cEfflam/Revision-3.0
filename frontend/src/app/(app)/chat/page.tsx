"use client";

/**
 * Coach IA multi-moteurs.
 *
 * Le sélecteur en haut change le MOTEUR, donc le comportement : le tuteur de
 * maths refusera de donner la réponse, l'analyste de code structurera sa
 * réponse en quatre points… Le RAG cite ses sources sous chaque réponse.
 */

import { useEffect, useRef, useState } from "react";
import { Loader2, Send } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import type { ChatResponse, EngineInfo } from "@/types/api";
import { Button } from "@/components/ui/button";
import { Select, Textarea } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";

interface Message {
  role: "user" | "assistant";
  content: string;
  meta?: ChatResponse;
}

export default function ChatPage() {
  const [engines, setEngines] = useState<EngineInfo[]>([]);
  const [task, setTask] = useState("chat");
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const bottom = useRef<HTMLDivElement>(null);

  useEffect(() => {
    api.engines().then(setEngines).catch(() => {});
  }, []);

  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function send() {
    const content = input.trim();
    if (!content || busy) return;

    const nextMessages: Message[] = [...messages, { role: "user", content }];
    setMessages(nextMessages);
    setInput("");
    setBusy(true);

    try {
      const response = await api.chat({
        message: content,
        task,
        history: messages.map((m) => ({ role: m.role, content: m.content })),
      });
      setMessages([
        ...nextMessages,
        { role: "assistant", content: response.answer, meta: response },
      ]);
    } catch (err) {
      setMessages([
        ...nextMessages,
        {
          role: "assistant",
          content:
            err instanceof ApiError
              ? `⚠️ ${err.detail}`
              : "⚠️ Erreur inattendue.",
        },
      ]);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex h-[calc(100vh-8rem)] flex-col gap-4 md:h-[calc(100vh-5rem)]">
      <header className="flex items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-extrabold tracking-tight">Coach IA</h1>
          <p className="mt-0.5 text-sm font-medium text-slate-400">
            Chaque moteur a sa pédagogie.
          </p>
        </div>
        <Select
          value={task}
          onChange={(e) => setTask(e.target.value)}
          className="w-auto max-w-[220px]"
        >
          {engines.map((engine) => (
            <option key={engine.task} value={engine.task}>
              {engine.label}
            </option>
          ))}
        </Select>
      </header>

      {/* ── Fil de discussion ──────────────────────────────────────────── */}
      <div className="flex-1 overflow-y-auto rounded-card border border-slate-100 bg-white/60 p-4">
        {messages.length === 0 && (
          <div className="flex h-full items-center justify-center">
            <p className="max-w-xs text-center text-sm font-medium text-slate-400">
              Pose une question sur tes cours, colle du code à analyser, ou
              demande un coup de main en maths — sans jamais recevoir la réponse
              toute cuite.
            </p>
          </div>
        )}
        <div className="flex flex-col gap-3">
          {messages.map((message, i) => (
            <div
              key={i}
              className={
                message.role === "user"
                  ? "self-end rounded-2xl rounded-br-md bg-indigo-600 px-4 py-2.5 text-sm font-medium text-white"
                  : "self-start rounded-2xl rounded-bl-md bg-slate-50 px-4 py-2.5 text-sm font-medium text-slate-700"
              }
              style={{ maxWidth: "85%" }}
            >
              <p className="whitespace-pre-wrap leading-relaxed">
                {message.content}
              </p>
              {message.meta && message.meta.sources.length > 0 && (
                <div className="mt-2 border-t border-slate-200 pt-2">
                  {message.meta.sources.map((source) => (
                    <p
                      key={source.index}
                      className="text-xs font-medium text-slate-400"
                    >
                      [{source.index}] {source.document_title}
                      {source.heading ? ` — ${source.heading}` : ""}
                    </p>
                  ))}
                </div>
              )}
              {message.meta?.mocked && (
                <Badge tone="amber" className="mt-2">
                  mode simulé
                </Badge>
              )}
            </div>
          ))}
          {busy && (
            <div className="self-start rounded-2xl bg-slate-50 px-4 py-3">
              <Loader2 className="h-4 w-4 animate-spin text-slate-400" />
            </div>
          )}
        </div>
        <div ref={bottom} />
      </div>

      {/* ── Saisie ─────────────────────────────────────────────────────── */}
      <div className="flex items-end gap-2">
        <Textarea
          rows={2}
          className="min-h-0"
          placeholder="Ta question… (Entrée pour envoyer, Maj+Entrée pour un retour à la ligne)"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              send();
            }
          }}
        />
        <Button onClick={send} disabled={busy || !input.trim()} className="h-[68px]">
          <Send className="h-4 w-4" />
        </Button>
      </div>
    </div>
  );
}
