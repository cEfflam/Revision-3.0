"use client";

/**
 * Synthèse d'une notion, et sa relecture par l'IA.
 *
 * Les deux sont volontairement SÉPARÉS à l'écran comme en base :
 *   • la SYNTHÈSE est fidèle aux cours — c'est sur eux que tu seras noté ;
 *   • la RELECTURE est le regard de l'IA, avec ses connaissances générales.
 *
 * Les mélanger rendrait impossible de distinguer ce qui tombera à l'épreuve
 * de ce qui n'est que culture générale. D'où deux blocs, deux couleurs, et
 * un bouton distinct pour chacun.
 */

import { useCallback, useEffect, useState } from "react";
import {
  AlertTriangle,
  BookOpen,
  CheckCircle2,
  Lightbulb,
  Loader2,
  RefreshCw,
  ScanSearch,
  Sparkles,
} from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { NodeSynthesis, SynthesisReview } from "@/types/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

const REMARK_META: Record<
  string,
  { label: string; tone: "rose" | "amber" | "indigo" | "emerald"; icon: typeof AlertTriangle }
> = {
  erreur: { label: "Erreur", tone: "rose", icon: AlertTriangle },
  imprecision: { label: "Imprécision", tone: "amber", icon: ScanSearch },
  manque: { label: "Manque", tone: "indigo", icon: BookOpen },
  methode: { label: "Méthode plus simple", tone: "emerald", icon: Lightbulb },
};

const VERDICT_META: Record<string, { label: string; tone: "emerald" | "amber" | "rose" }> = {
  fidele: { label: "Synthèse fiable", tone: "emerald" },
  a_preciser: { label: "À préciser", tone: "amber" },
  erreur_detectee: { label: "Erreur détectée", tone: "rose" },
};

export function NodeSynthesisPanel({
  nodeId,
  nodeTitle,
}: {
  nodeId: number;
  nodeTitle: string;
}) {
  const [data, setData] = useState<NodeSynthesis | null>(null);
  const [review, setReview] = useState<SynthesisReview | null>(null);
  const [building, setBuilding] = useState(false);
  const [reviewing, setReviewing] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(() => {
    api
      .synthesis(nodeId)
      .then(setData)
      .catch(() => setData(null));
  }, [nodeId]);

  useEffect(() => {
    setReview(null);
    setError("");
    load();
  }, [load]);

  async function build() {
    setBuilding(true);
    setError("");
    setReview(null);
    try {
      setData(await api.buildSynthesis(nodeId));
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Génération impossible.");
    } finally {
      setBuilding(false);
    }
  }

  async function runReview() {
    setReviewing(true);
    setError("");
    try {
      setReview(await api.reviewSynthesis(nodeId));
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Relecture impossible.");
    } finally {
      setReviewing(false);
    }
  }

  const hasSynthesis = Boolean(data?.synthesis);

  return (
    <div className="flex flex-col gap-4">
      {/* ── La synthèse, fidèle aux cours ──────────────────────────────── */}
      <Card>
        <CardContent>
          <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
            <CardTitle className="flex items-center gap-2 text-base">
              <BookOpen className="h-5 w-5 text-indigo-500" />
              Ma synthèse de « {nodeTitle} »
            </CardTitle>
            <div className="flex items-center gap-2">
              {data?.is_stale && (
                <Badge tone="amber">
                  <RefreshCw className="h-3 w-3" />
                  {data.linked_documents - data.source_count} document(s) en plus
                </Badge>
              )}
              <Button size="sm" variant={hasSynthesis ? "ghost" : "primary"} onClick={build} disabled={building}>
                {building ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Fusion des sources…
                  </>
                ) : (
                  <>
                    <Sparkles className="h-4 w-4" />
                    {hasSynthesis ? "Régénérer" : "Générer"}
                  </>
                )}
              </Button>
            </div>
          </div>

          {error && (
            <p className="mb-3 rounded-xl bg-rose-50 px-3 py-2 text-sm font-medium text-rose-600">
              {error}
            </p>
          )}

          {hasSynthesis ? (
            <>
              <p className="whitespace-pre-wrap rounded-2xl bg-slate-50/70 px-4 py-3 text-sm font-medium leading-relaxed text-slate-700">
                {data?.synthesis}
              </p>
              <p className="mt-2 text-xs font-medium text-slate-400">
                Fusionnée depuis {data?.source_count} document(s) · fidèle à tes
                cours, sans ajout extérieur
              </p>
            </>
          ) : (
            <p className="text-sm font-medium text-slate-400">
              Aucune synthèse. Elle fusionnera tout ce que tu as rattaché à
              cette notion — cours, fiches, annotations — en un texte unique
              que l&apos;IA relira à chaque question.
            </p>
          )}
        </CardContent>
      </Card>

      {/* ── La relecture IA, séparée ───────────────────────────────────── */}
      {hasSynthesis && (
        <Card className={cn(review && "border-indigo-100")}>
          <CardContent>
            <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
              <CardTitle className="flex items-center gap-2 text-base">
                <ScanSearch className="h-5 w-5 text-indigo-500" />
                Relecture par l&apos;IA
              </CardTitle>
              <Button size="sm" variant="soft" onClick={runReview} disabled={reviewing}>
                {reviewing ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  "Faire relire"
                )}
              </Button>
            </div>
            <p className="mb-3 text-xs font-medium text-slate-400">
              L&apos;IA compare ta synthèse à ses connaissances générales.
              <strong className="text-slate-500">
                {" "}
                Elle ne la modifie jamais
              </strong>{" "}
              — tu restes noté sur tes cours, pas sur ce qu&apos;elle sait.
            </p>

            {review && (
              <>
                <div className="mb-3 flex flex-wrap items-center gap-2">
                  <Badge tone={VERDICT_META[review.verdict]?.tone ?? "slate"}>
                    {VERDICT_META[review.verdict]?.label ?? review.verdict}
                  </Badge>
                  {review.mocked && <Badge tone="amber">mode simulé</Badge>}
                  <span className="text-sm font-medium text-slate-500">
                    {review.summary}
                  </span>
                </div>

                {review.remarks.length === 0 ? (
                  <p className="flex items-center gap-2 rounded-xl bg-emerald-50 px-3 py-2 text-sm font-medium text-emerald-700">
                    <CheckCircle2 className="h-4 w-4" />
                    Rien à signaler : ta synthèse tient la route.
                  </p>
                ) : (
                  <div className="flex flex-col gap-2">
                    {review.remarks.map((remark, index) => {
                      const meta = REMARK_META[remark.type] ?? REMARK_META.methode;
                      const Icon = meta.icon;
                      return (
                        <div
                          key={index}
                          className="rounded-tile border border-slate-100 bg-white px-4 py-3"
                        >
                          <div className="mb-1.5 flex flex-wrap items-center gap-2">
                            <Badge tone={meta.tone}>
                              <Icon className="h-3 w-3" />
                              {meta.label}
                            </Badge>
                            <span className="text-xs font-semibold text-slate-400">
                              confiance {remark.confidence}
                            </span>
                          </div>
                          {remark.quote && (
                            <p className="mb-1.5 border-l-2 border-slate-200 pl-2 text-xs font-medium italic text-slate-500">
                              « {remark.quote} »
                            </p>
                          )}
                          <p className="text-sm font-medium text-slate-600">
                            {remark.detail}
                          </p>
                          {remark.suggestion && (
                            <p className="mt-1.5 rounded-xl bg-indigo-50/60 px-3 py-2 text-sm font-medium text-indigo-700">
                              → {remark.suggestion}
                            </p>
                          )}
                        </div>
                      );
                    })}
                  </div>
                )}
              </>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
