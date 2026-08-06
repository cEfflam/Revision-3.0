"use client";

/**
 * Écran d'une matière : tout ce qu'on peut y travailler, au même endroit.
 *
 * `useParams()` plutôt que la prop `params` : en Next 15 celle-ci est une
 * Promise qu'il faudrait déballer avec `use()`, ce qui n'apporte rien dans un
 * composant client.
 */

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import {
  ArrowLeft,
  ClipboardList,
  FileText,
  GraduationCap,
  Layers,
  Lightbulb,
  Lock,
  Target,
} from "lucide-react";
import { api } from "@/lib/api";
import { cn, pct, STATUS_STYLES } from "@/lib/utils";
import type { SubjectDetail } from "@/types/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";

export default function SubjectDetailPage() {
  const params = useParams<{ subject: string }>();
  const subject = params.subject;
  const [data, setData] = useState<SubjectDetail | null>(null);
  const [error, setError] = useState("");

  const load = useCallback(() => {
    api
      .subject(subject)
      .then(setData)
      .catch((e) => setError(e.message));
  }, [subject]);

  useEffect(load, [load]);

  if (error) {
    return (
      <div className="flex flex-col gap-4">
        <Link
          href="/subjects"
          className="flex items-center gap-1 text-sm font-semibold text-slate-400 hover:text-indigo-600"
        >
          <ArrowLeft className="h-4 w-4" /> Toutes les matières
        </Link>
        <p className="rounded-xl bg-rose-50 px-4 py-3 text-sm font-medium text-rose-600">
          {error}
        </p>
      </div>
    );
  }
  if (!data) {
    return (
      <div className="flex justify-center pt-20">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-indigo-200 border-t-indigo-600" />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-5">
      <Link
        href="/subjects"
        className="flex items-center gap-1 text-sm font-semibold text-slate-400 hover:text-indigo-600"
      >
        <ArrowLeft className="h-4 w-4" /> Toutes les matières
      </Link>

      {/* ── En-tête : niveau global + conseil d'attaque ─────────────────── */}
      <Card>
        <CardContent>
          <div className="mb-3 flex items-start justify-between gap-4">
            <div>
              <h1 className="text-2xl font-extrabold tracking-tight">
                {data.label}
              </h1>
              <p className="mt-0.5 text-sm font-medium text-slate-400">
                {data.nodes_mastered}/{data.nodes_total} notions maîtrisées ·{" "}
                {data.cards_total} cartes · {data.documents_total} cours
              </p>
            </div>
            <div className="rounded-2xl bg-indigo-50 px-4 py-2 text-center">
              <p className="text-2xl font-black leading-none text-indigo-600">
                {Math.round(data.mastery * 100)}
              </p>
              <p className="text-[10px] font-bold uppercase text-indigo-400">%</p>
            </div>
          </div>
          <Progress value={data.mastery} />

          {data.advice && (
            <p className="mt-4 flex items-start gap-2 rounded-2xl bg-indigo-50/60 px-4 py-3 text-sm font-medium text-indigo-800">
              <Lightbulb className="mt-0.5 h-4 w-4 shrink-0" />
              {data.advice}
            </p>
          )}

          <div className="mt-4 flex flex-wrap gap-2">
            <Link href={`/review?subject=${data.subject}`}>
              <Button size="sm">
                <Layers className="h-4 w-4" />
                Réviser
                {data.cards_due > 0 && ` (${data.cards_due})`}
              </Button>
            </Link>
            <Link href={`/quiz?subject=${data.subject}`}>
              <Button size="sm" variant="soft">
                <ClipboardList className="h-4 w-4" />
                Quiz
              </Button>
            </Link>
            <Link href={`/practice?subject=${data.subject}`}>
              <Button size="sm" variant="soft">
                <GraduationCap className="h-4 w-4" />
                Sujet type BTS
              </Button>
            </Link>
            <Link href={`/cards?subject=${data.subject}`}>
              <Button size="sm" variant="ghost">
                Gérer les cartes
              </Button>
            </Link>
          </div>
        </CardContent>
      </Card>

      {/* ── Points faibles : par où commencer ───────────────────────────── */}
      {data.weak_nodes.length > 0 && (
        <Card>
          <CardContent>
            <CardTitle className="mb-3 flex items-center gap-2 text-base">
              <Target className="h-5 w-5 text-rose-500" />
              À travailler en priorité
            </CardTitle>
            <div className="flex flex-col gap-2">
              {data.weak_nodes.map((node) => (
                <Link
                  key={node.id}
                  href={`/review?node=${node.id}`}
                  className="flex items-center gap-3 rounded-xl border border-slate-100 px-3 py-2.5 transition hover:bg-indigo-50/40"
                >
                  <span className="flex-1">
                    <span className="block text-sm font-bold text-slate-800">
                      {node.title}
                    </span>
                    <span className="block text-xs font-medium text-slate-400">
                      {node.estimated_minutes} min estimées · difficulté{" "}
                      {node.difficulty}/5
                    </span>
                  </span>
                  <Badge tone={node.status === "critical" ? "rose" : "amber"}>
                    {pct(node.mastery)}
                  </Badge>
                </Link>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* ── Toutes les notions ──────────────────────────────────────────── */}
      <Card>
        <CardContent>
          <CardTitle className="mb-3 text-base">
            Toutes les notions ({data.nodes.length})
          </CardTitle>
          <div className="flex flex-col gap-1">
            {data.nodes.map((node) => {
              const style = STATUS_STYLES[node.status] ?? STATUS_STYLES.available;
              const locked = node.status === "locked";
              return (
                <div
                  key={node.id}
                  className={cn(
                    "flex items-center gap-3 rounded-xl px-2 py-2",
                    locked && "opacity-50",
                  )}
                >
                  <span className={cn("h-2.5 w-2.5 shrink-0 rounded-full", style.dot)} />
                  <span className="flex-1 text-sm font-semibold text-slate-700">
                    {node.title}
                  </span>
                  {locked && <Lock className="h-3.5 w-3.5 text-slate-300" />}
                  <span className="w-24 shrink-0">
                    <Progress
                      value={node.mastery}
                      className="h-1.5"
                      barClassName={
                        node.status === "critical"
                          ? "bg-rose-500"
                          : node.status === "mastered"
                            ? "bg-emerald-500"
                            : undefined
                      }
                    />
                  </span>
                </div>
              );
            })}
          </div>
        </CardContent>
      </Card>

      {/* ── Cours importés dans cette matière ───────────────────────────── */}
      {data.documents.length > 0 && (
        <Card>
          <CardContent>
            <CardTitle className="mb-3 flex items-center gap-2 text-base">
              <FileText className="h-5 w-5 text-indigo-500" />
              Mes cours ({data.documents.length})
            </CardTitle>
            <div className="flex flex-col gap-2">
              {data.documents.map((doc) => (
                <div
                  key={doc.id}
                  className="rounded-xl border border-slate-100 px-3 py-2.5"
                >
                  <p className="text-sm font-bold text-slate-800">{doc.title}</p>
                  {doc.summary && (
                    <p className="mt-1 line-clamp-3 whitespace-pre-wrap text-xs font-medium text-slate-500">
                      {doc.summary}
                    </p>
                  )}
                  <div className="mt-2 flex gap-2">
                    <Link href={`/quiz?document=${doc.id}`}>
                      <Button size="sm" variant="ghost" className="h-7 px-2 text-xs">
                        Quiz sur ce cours
                      </Button>
                    </Link>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
