"use client";

/**
 * Technique Feynman.
 *
 * Les quatre temps de la méthode, dans l'ordre :
 *   1. tu choisis une notion (fait par l'arbre du référentiel) ;
 *   2. tu l'expliques avec tes mots, comme à un enfant de dix ans ;
 *   3. l'IA repère les blocages — là où tu hésites ou restes vague ;
 *   4. elle te renvoie au passage exact du cours, et tu recommences.
 *
 * Le bouton « Voir la réponse » n'existe pas, volontairement. Chaque lacune
 * s'accompagne d'une QUESTION qui pousse à la combler soi-même : la méthode
 * ne vaut que si l'effort est fourni.
 */

import { useState } from "react";
import {
  BookOpen,
  CheckCircle2,
  CircleHelp,
  Loader2,
  MessageCircleQuestion,
  RotateCcw,
  XCircle,
} from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { FeynmanResponse } from "@/types/api";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/input";
import { Card, CardContent, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";
import { Waiting } from "@/components/ui/waiting";

const STATUS_META: Record<
  string,
  { label: string; tone: "emerald" | "amber" | "indigo" | "rose"; icon: typeof CheckCircle2 }
> = {
  acquis: { label: "Acquis", tone: "emerald", icon: CheckCircle2 },
  flou: { label: "Flou", tone: "amber", icon: CircleHelp },
  manquant: { label: "Manquant", tone: "indigo", icon: BookOpen },
  errone: { label: "Erroné", tone: "rose", icon: XCircle },
};

const MIN_CHARS = 20;

export function FeynmanPanel({
  nodeId,
  nodeTitle,
}: {
  nodeId: number;
  nodeTitle: string;
}) {
  const [explanation, setExplanation] = useState("");
  const [result, setResult] = useState<FeynmanResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit() {
    setBusy(true);
    setError("");
    try {
      setResult(await api.feynman(nodeId, explanation.trim()));
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Analyse impossible.");
    } finally {
      setBusy(false);
    }
  }

  function retry() {
    setResult(null);
    setError("");
  }

  const tooShort = explanation.trim().length < MIN_CHARS;

  return (
    <Card>
      <CardContent>
        <CardTitle className="mb-1 flex items-center gap-2 text-base">
          <MessageCircleQuestion className="h-5 w-5 text-indigo-500" />
          Explique-moi « {nodeTitle} »
        </CardTitle>
        <p className="mb-3 text-xs font-medium text-slate-400">
          Avec tes mots, comme si tu l&apos;enseignais à un enfant de dix ans.
          Sans jargon. <strong className="text-slate-500">Là où tu hésites
          ou restes vague, il y a une lacune</strong> — c&apos;est tout
          l&apos;intérêt de l&apos;exercice.
        </p>

        {!result ? (
          <>
            <Textarea
              rows={7}
              value={explanation}
              onChange={(e) => setExplanation(e.target.value)}
              placeholder="Alors, en fait, ça sert à…"
              className="min-h-0 leading-relaxed"
            />
            <div className="mt-2 flex items-center justify-between">
              <span className="text-xs font-semibold text-slate-400">
                {explanation.trim().length} caractères
                {tooShort && ` · ${MIN_CHARS} minimum`}
              </span>
              <Button onClick={submit} disabled={busy || tooShort}>
                {busy ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Comparaison au cours…
                  </>
                ) : (
                  "Vérifier ma compréhension"
                )}
              </Button>
            </div>
            <Waiting
              active={busy}
              label="Ton explication est comparée à ton cours"
              typicalSeconds={45}
            />
            {error && (
              <p className="mt-2 rounded-xl bg-rose-50 px-3 py-2 text-sm font-medium text-rose-600">
                {error}
              </p>
            )}
          </>
        ) : (
          <>
            {/* Fluidité */}
            <div className="mb-3 flex items-center gap-3">
              <Progress
                value={result.fluency / 100}
                className="h-2.5 flex-1"
                barClassName={
                  result.fluency >= 75
                    ? "bg-emerald-500"
                    : result.fluency >= 45
                      ? "bg-amber-400"
                      : "bg-rose-500"
                }
              />
              <span className="text-sm font-black text-slate-700">
                {result.fluency}/100
              </span>
            </div>
            <p className="mb-3 text-sm font-semibold text-slate-700">
              {result.verdict}
            </p>
            {result.mastery_delta !== 0 && (
              <Badge
                tone={result.mastery_delta > 0 ? "emerald" : "rose"}
                className="mb-3"
              >
                maîtrise {result.mastery_delta > 0 ? "+" : ""}
                {Math.round(result.mastery_delta * 100)} pts →{" "}
                {Math.round(result.mastery_after * 100)} %
              </Badge>
            )}

            <div className="flex flex-col gap-2">
              {result.points.map((point, index) => {
                const meta = STATUS_META[point.status] ?? STATUS_META.flou;
                const Icon = meta.icon;
                return (
                  <div
                    key={index}
                    className={cn(
                      "rounded-tile border px-4 py-3",
                      point.status === "acquis"
                        ? "border-emerald-100 bg-emerald-50/40"
                        : "border-slate-100",
                    )}
                  >
                    <div className="mb-1 flex items-center gap-2">
                      <Badge tone={meta.tone}>
                        <Icon className="h-3 w-3" />
                        {meta.label}
                      </Badge>
                      <span className="text-sm font-bold text-slate-800">
                        {point.label}
                      </span>
                    </div>
                    {point.detail && (
                      <p className="text-sm font-medium text-slate-600">
                        {point.detail}
                      </p>
                    )}
                    {point.course_extract && (
                      <p className="mt-2 border-l-2 border-indigo-200 pl-2 text-xs font-medium italic text-slate-500">
                        Ton cours : « {point.course_extract} »
                      </p>
                    )}
                    {point.question && (
                      <p className="mt-2 rounded-xl bg-indigo-50/60 px-3 py-2 text-sm font-semibold text-indigo-700">
                        ? {point.question}
                      </p>
                    )}
                  </div>
                );
              })}
            </div>

            {result.next_action && (
              <p className="mt-3 rounded-xl bg-slate-50 px-3 py-2 text-sm font-medium text-slate-700">
                📖 {result.next_action}
              </p>
            )}

            <Button variant="soft" onClick={retry} className="mt-3 w-full">
              <RotateCcw className="h-4 w-4" />
              Réexpliquer après avoir relu
            </Button>
          </>
        )}
      </CardContent>
    </Card>
  );
}
