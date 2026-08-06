"use client";

/**
 * Gestion des cartes.
 *
 * Sans cet écran, une carte mal générée par l'IA restait dans les révisions à
 * vie — c'est ce qui dégoûte le plus vite d'un système de répétition espacée.
 *
 * Trois actions, dans l'ordre de ce qu'on veut faire en pratique :
 *   • CORRIGER  — la carte est bonne mais la formulation est mauvaise ;
 *   • SUSPENDRE — la carte n'est pas fausse mais gêne maintenant. Elle sort
 *     de la file sans perdre son historique SRS, et peut revenir plus tard ;
 *   • SUPPRIMER — irréversible, réservé aux cartes vraiment ratées.
 */

import { Suspense, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import {
  ArrowLeft,
  BellOff,
  Check,
  Loader2,
  Pencil,
  Sparkles,
  Trash2,
  X,
} from "lucide-react";
import { api } from "@/lib/api";
import { cn, formatInterval, SUBJECT_LABELS } from "@/lib/utils";
import type { CardRead, SubjectDetail } from "@/types/api";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/input";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

const STATE_TONES: Record<string, "emerald" | "amber" | "indigo" | "slate"> = {
  review: "emerald",
  learning: "amber",
  relearning: "amber",
  new: "slate",
};

function CardManager() {
  const params = useSearchParams();
  const subject = params.get("subject");
  const nodeParam = params.get("node");

  const [cards, setCards] = useState<CardRead[] | null>(null);
  const [detail, setDetail] = useState<SubjectDetail | null>(null);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [draft, setDraft] = useState({ front: "", back: "" });
  const [busyId, setBusyId] = useState<number | null>(null);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      if (nodeParam) {
        setCards(await api.listCards({ node_id: Number(nodeParam), limit: 300 }));
        return;
      }
      if (subject) {
        // L'API filtre par notion, pas par matière : on récupère les notions
        // de la matière puis on assemble. Charger toutes les cartes une fois
        // et filtrer localement évite N requêtes.
        const subjectDetail = await api.subject(subject);
        setDetail(subjectDetail);
        const nodeIds = new Set(subjectDetail.nodes.map((n) => n.id));
        const all = await api.listCards({ limit: 500 });
        setCards(all.filter((c) => c.node_id && nodeIds.has(c.node_id)));
        return;
      }
      setCards(await api.listCards({ limit: 300 }));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Chargement impossible.");
    }
  }, [subject, nodeParam]);

  useEffect(() => {
    load();
  }, [load]);

  function startEdit(card: CardRead) {
    setEditingId(card.id);
    setDraft({ front: card.front, back: card.back });
  }

  async function saveEdit(cardId: number) {
    setBusyId(cardId);
    try {
      const updated = await api.updateCard(cardId, {
        front: draft.front.trim(),
        back: draft.back.trim(),
      });
      setCards((list) =>
        (list ?? []).map((c) => (c.id === cardId ? updated : c)),
      );
      setEditingId(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Enregistrement impossible.");
    } finally {
      setBusyId(null);
    }
  }

  async function toggleSuspend(card: CardRead) {
    setBusyId(card.id);
    try {
      const updated = await api.updateCard(card.id, {
        is_suspended: !card.is_suspended,
      });
      setCards((list) =>
        (list ?? []).map((c) => (c.id === card.id ? updated : c)),
      );
    } finally {
      setBusyId(null);
    }
  }

  async function remove(card: CardRead) {
    if (!window.confirm("Supprimer définitivement cette carte ?")) return;
    setBusyId(card.id);
    try {
      await api.deleteCard(card.id);
      setCards((list) => (list ?? []).filter((c) => c.id !== card.id));
    } finally {
      setBusyId(null);
    }
  }

  if (error) {
    return (
      <p className="rounded-xl bg-rose-50 px-4 py-3 text-sm font-medium text-rose-600">
        {error}
      </p>
    );
  }
  if (!cards) {
    return (
      <div className="flex justify-center pt-20">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-indigo-200 border-t-indigo-600" />
      </div>
    );
  }

  const scopeLabel = subject
    ? (detail?.label ?? SUBJECT_LABELS[subject] ?? subject)
    : null;

  return (
    <div className="flex flex-col gap-4">
      {scopeLabel && (
        <Link
          href={`/subjects/${subject}`}
          className="flex items-center gap-1 text-sm font-semibold text-slate-400 hover:text-indigo-600"
        >
          <ArrowLeft className="h-4 w-4" /> {scopeLabel}
        </Link>
      )}

      <header>
        <h1 className="text-2xl font-extrabold tracking-tight">
          Mes cartes{scopeLabel ? ` — ${scopeLabel}` : ""}
        </h1>
        <p className="mt-1 text-sm font-medium text-slate-400">
          {cards.length} carte{cards.length > 1 ? "s" : ""} · corrige,
          suspends ou supprime ce qui ne va pas.
        </p>
      </header>

      {cards.length === 0 && (
        <Card>
          <CardContent className="py-10 text-center">
            <p className="text-sm font-medium text-slate-400">
              Aucune carte ici. Génère-en depuis un cours dans le Brain.
            </p>
            <Link href="/brain">
              <Button variant="soft" className="mt-3">
                Aller au Brain
              </Button>
            </Link>
          </CardContent>
        </Card>
      )}

      <div className="flex flex-col gap-2.5">
        {cards.map((card) => {
          const editing = editingId === card.id;
          const busy = busyId === card.id;
          const suspended = card.is_suspended;
          return (
            <Card
              key={card.id}
              className={cn(suspended && "opacity-60")}
            >
              <CardContent className="p-4">
                {editing ? (
                  <div className="flex flex-col gap-2">
                    <Textarea
                      rows={2}
                      value={draft.front}
                      onChange={(e) =>
                        setDraft({ ...draft, front: e.target.value })
                      }
                      placeholder="Question"
                      className="min-h-0 font-bold"
                    />
                    <Textarea
                      rows={3}
                      value={draft.back}
                      onChange={(e) =>
                        setDraft({ ...draft, back: e.target.value })
                      }
                      placeholder="Réponse"
                      className="min-h-0"
                    />
                    <div className="flex gap-2">
                      <Button
                        size="sm"
                        onClick={() => saveEdit(card.id)}
                        disabled={busy || !draft.front.trim() || !draft.back.trim()}
                      >
                        {busy ? (
                          <Loader2 className="h-4 w-4 animate-spin" />
                        ) : (
                          <Check className="h-4 w-4" />
                        )}
                        Enregistrer
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => setEditingId(null)}
                      >
                        <X className="h-4 w-4" />
                        Annuler
                      </Button>
                    </div>
                  </div>
                ) : (
                  <>
                    <p className="font-bold text-slate-800">{card.front}</p>
                    <p className="mt-1 text-sm font-medium text-slate-500">
                      {card.back}
                    </p>

                    <div className="mt-3 flex flex-wrap items-center gap-2">
                      <Badge tone={STATE_TONES[card.state] ?? "slate"}>
                        {card.state}
                      </Badge>
                      {card.interval_days > 0 && (
                        <span className="text-xs font-semibold text-slate-400">
                          {formatInterval(card.interval_days)}
                        </span>
                      )}
                      {card.lapses > 0 && (
                        <Badge tone="rose">{card.lapses} oubli(s)</Badge>
                      )}
                      {card.ai_generated && (
                        <Badge tone="indigo">
                          <Sparkles className="h-3 w-3" />
                          IA
                        </Badge>
                      )}
                      {suspended && <Badge tone="amber">suspendue</Badge>}

                      <span className="ml-auto flex gap-1">
                        <button
                          onClick={() => startEdit(card)}
                          title="Corriger"
                          className="rounded-lg p-1.5 text-slate-400 transition hover:bg-indigo-50 hover:text-indigo-600"
                        >
                          <Pencil className="h-4 w-4" />
                        </button>
                        <button
                          onClick={() => toggleSuspend(card)}
                          disabled={busy}
                          title={suspended ? "Réactiver" : "Suspendre"}
                          className="rounded-lg p-1.5 text-slate-400 transition hover:bg-amber-50 hover:text-amber-600"
                        >
                          <BellOff className="h-4 w-4" />
                        </button>
                        <button
                          onClick={() => remove(card)}
                          disabled={busy}
                          title="Supprimer"
                          className="rounded-lg p-1.5 text-slate-300 transition hover:bg-rose-50 hover:text-rose-500"
                        >
                          <Trash2 className="h-4 w-4" />
                        </button>
                      </span>
                    </div>
                  </>
                )}
              </CardContent>
            </Card>
          );
        })}
      </div>
    </div>
  );
}

export default function CardsPage() {
  return (
    <Suspense
      fallback={
        <div className="flex justify-center pt-20">
          <Loader2 className="h-8 w-8 animate-spin text-indigo-500" />
        </div>
      }
    >
      <CardManager />
    </Suspense>
  );
}
