"use client";

/**
 * Le dashboard « Aujourd'hui » — l'écran de la maquette.
 * Il ne décide de rien : la liste d'actions arrive déjà priorisée du backend.
 */

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  ChevronRight,
  Compass,
  Flame,
  Layers,
  PenLine,
  Sparkles,
  Target,
  Upload,
  type LucideIcon,
} from "lucide-react";
import { api } from "@/lib/api";
import { pct, SUBJECT_LABELS } from "@/lib/utils";
import type { DashboardRead } from "@/types/api";
import { Card, CardContent } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";
import { Heatmap } from "@/components/heatmap";

const ACTION_ICONS: Record<string, LucideIcon> = {
  layers: Layers,
  target: Target,
  "pen-line": PenLine,
  upload: Upload,
  compass: Compass,
};

export default function DashboardPage() {
  const [data, setData] = useState<DashboardRead | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api
      .dashboard()
      .then(setData)
      .catch((e) => setError(e.message));
  }, []);

  if (error) {
    return (
      <p className="rounded-xl bg-rose-50 px-4 py-3 text-sm font-medium text-rose-600">
        {error}
      </p>
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
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-extrabold tracking-tight">
            {data.greeting}
          </h1>
          <p className="mt-0.5 text-sm font-medium text-slate-400">
            {data.minutes_today > 0
              ? `${data.minutes_today} min travaillées aujourd'hui`
              : "Prêt à travailler ?"}
          </p>
        </div>
        {data.streak_current > 0 && (
          <Badge tone="amber" className="px-3 py-1.5 text-sm">
            <Flame className="h-4 w-4" />
            {data.streak_current}
          </Badge>
        )}
      </header>

      {/* ── Carte objectif (la carte haute de la maquette) ─────────────── */}
      {data.goal && (
        <Card>
          <CardContent>
            <div className="mb-3 flex items-start justify-between gap-3">
              <div>
                <p className="text-xs font-bold uppercase tracking-wider text-indigo-500">
                  Objectif
                </p>
                <h2 className="mt-0.5 text-lg font-extrabold text-slate-800">
                  {data.goal.title}
                </h2>
              </div>
              {data.days_left !== null && (
                <div className="rounded-2xl bg-indigo-50 px-3 py-2 text-center">
                  <p className="text-xl font-black leading-none text-indigo-600">
                    {data.days_left}
                  </p>
                  <p className="text-[10px] font-bold uppercase text-indigo-400">
                    jours
                  </p>
                </div>
              )}
            </div>
            <div className="mb-1.5 flex justify-between text-sm">
              <span className="font-semibold text-slate-500">Préparation</span>
              <span className="font-bold text-indigo-600">
                {pct(data.readiness)}
              </span>
            </div>
            <Progress value={data.readiness} />
          </CardContent>
        </Card>
      )}

      {/* ── Actions prioritaires ───────────────────────────────────────── */}
      <section>
        <h3 className="mb-3 px-1 text-sm font-bold uppercase tracking-wider text-slate-400">
          Priorités du jour
        </h3>
        <div className="flex flex-col gap-2.5">
          {data.actions.map((action) => {
            const Icon = ACTION_ICONS[action.icon] ?? Sparkles;
            return (
              <Link key={action.key} href={action.href} className="action-row">
                <span className="icon-tile">
                  <Icon className="h-5 w-5" />
                </span>
                <span className="flex-1">
                  <span className="block font-bold text-slate-800">
                    {action.title}
                  </span>
                  <span className="block text-sm font-medium text-slate-400">
                    {action.subtitle}
                  </span>
                </span>
                {action.count !== null && (
                  <Badge tone="indigo">{action.count}</Badge>
                )}
                <ChevronRight className="h-5 w-5 text-slate-300" />
              </Link>
            );
          })}
        </div>
      </section>

      {/* ── Points faibles ─────────────────────────────────────────────── */}
      {data.weakest_nodes.length > 0 && (
        <Card>
          <CardContent>
            <h3 className="mb-3 text-sm font-bold uppercase tracking-wider text-slate-400">
              À consolider
            </h3>
            <div className="flex flex-col gap-3">
              {data.weakest_nodes.map((node) => (
                <div key={node.id} className="flex items-center gap-3">
                  <div className="flex-1">
                    <div className="flex justify-between text-sm">
                      <span className="font-semibold text-slate-700">
                        {node.title}
                      </span>
                      <span className="font-medium text-slate-400">
                        {SUBJECT_LABELS[node.subject] ?? node.subject} ·{" "}
                        {pct(node.mastery)}
                      </span>
                    </div>
                    <Progress
                      value={node.mastery}
                      className="mt-1.5 h-2"
                      barClassName={
                        node.status === "critical" ? "bg-rose-500" : undefined
                      }
                    />
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* ── Régularité ─────────────────────────────────────────────────── */}
      <Card>
        <CardContent>
          <div className="mb-3 flex items-center justify-between">
            <h3 className="text-sm font-bold uppercase tracking-wider text-slate-400">
              Régularité
            </h3>
            <span className="text-xs font-semibold text-slate-400">
              Record : {data.streak_best} jours
            </span>
          </div>
          <Heatmap points={data.heatmap} days={119} />
        </CardContent>
      </Card>
    </div>
  );
}
