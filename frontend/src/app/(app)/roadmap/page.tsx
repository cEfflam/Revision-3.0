"use client";

/**
 * Parcours IA + Arbre de compétences.
 *
 * Les deux vues répondent à des questions différentes et se complètent :
 *   • le PARCOURS dit « dans quel ordre attaquer » — une ligne temporelle
 *     générée à partir de ton objectif et de tes points faibles réels ;
 *   • l'ARBRE dit « où j'en suis » — l'état de chaque notion et ses blocages.
 *
 * Le parcours est persisté en base : on le suit sur des semaines et on coche
 * les étapes. Le régénérer à chaque affichage coûterait un appel de modèle par
 * ouverture d'écran, pour un contenu qui ne bouge pas.
 */

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
  ChevronDown,
  Circle,
  CircleCheckBig,
  Clock,
  Loader2,
  Lock,
  // Aliasé : l'icône `Map` masquerait le constructeur natif `Map` du langage,
  // et `new Map()` cesserait de compiler.
  Map as MapIcon,
  Sparkles,
  Trash2,
} from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { cn, pct, STATUS_STYLES, SUBJECT_LABELS } from "@/lib/utils";
import type { DiagnosisRead, GraphRead, NodeRead, RoadmapRead } from "@/types/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";

export default function RoadmapPage() {
  const [graph, setGraph] = useState<GraphRead | null>(null);
  const [roadmap, setRoadmap] = useState<RoadmapRead | null>(null);
  const [generating, setGenerating] = useState(false);
  const [openNodeId, setOpenNodeId] = useState<number | null>(null);
  const [diagnosis, setDiagnosis] = useState<DiagnosisRead | null>(null);
  const [diagnosisLoading, setDiagnosisLoading] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const load = useCallback(() => {
    api.graph().then(setGraph).catch((e) => setError(e.message));
    api.roadmap().then(setRoadmap).catch(() => setRoadmap(null));
  }, []);

  useEffect(load, [load]);

  async function generate() {
    setGenerating(true);
    setNotice("");
    try {
      setRoadmap(await api.generateRoadmap(12));
    } catch (err) {
      setNotice(
        err instanceof ApiError ? err.detail : "Génération impossible.",
      );
    } finally {
      setGenerating(false);
    }
  }

  async function toggleStep(stepId: number, isDone: boolean) {
    if (!roadmap) return;
    // Mise à jour optimiste : cocher une étape doit répondre instantanément,
    // le serveur confirme derrière.
    setRoadmap({
      ...roadmap,
      steps: roadmap.steps.map((s) =>
        s.id === stepId ? { ...s, is_done: isDone } : s,
      ),
    });
    try {
      await api.toggleRoadmapStep(stepId, isDone);
    } catch {
      load();
    }
  }

  async function removeRoadmap() {
    if (!window.confirm("Supprimer ce parcours ? Tu pourras en regénérer un.")) {
      return;
    }
    await api.deleteRoadmap();
    setRoadmap(null);
  }

  async function toggleNode(node: NodeRead) {
    if (openNodeId === node.id) {
      setOpenNodeId(null);
      setDiagnosis(null);
      return;
    }
    setOpenNodeId(node.id);
    setDiagnosis(null);
    setDiagnosisLoading(true);
    try {
      setDiagnosis(await api.diagnosis(node.id));
    } catch {
      /* le panneau restera vide */
    } finally {
      setDiagnosisLoading(false);
    }
  }

  if (error) {
    return (
      <p className="rounded-xl bg-rose-50 px-4 py-3 text-sm font-medium text-rose-600">
        {error}
      </p>
    );
  }
  if (!graph) {
    return (
      <div className="flex justify-center pt-20">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-indigo-200 border-t-indigo-600" />
      </div>
    );
  }

  const bySubject = new Map<string, NodeRead[]>();
  for (const node of graph.nodes) {
    const list = bySubject.get(node.subject) ?? [];
    list.push(node);
    bySubject.set(node.subject, list);
  }

  const doneSteps = roadmap?.steps.filter((s) => s.is_done).length ?? 0;
  const totalSteps = roadmap?.steps.length ?? 0;

  return (
    <div className="flex flex-col gap-5">
      <header>
        <h1 className="text-2xl font-extrabold tracking-tight">Mon parcours</h1>
        <p className="mt-1 text-sm font-medium text-slate-400">
          {graph.counts.total ?? 0} notions · {graph.counts.mastered ?? 0}{" "}
          maîtrisées · {graph.counts.critical ?? 0} critiques
        </p>
      </header>

      {/* ══ Parcours généré par l'IA ═══════════════════════════════════ */}
      <Card>
        <CardContent>
          <div className="mb-3 flex items-center justify-between gap-3">
            <CardTitle className="flex items-center gap-2 text-base">
              <MapIcon className="h-5 w-5 text-indigo-500" />
              Parcours vers mon objectif
            </CardTitle>
            {roadmap && totalSteps > 0 ? (
              <div className="flex gap-1">
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={generate}
                  disabled={generating}
                  title="Régénérer le parcours"
                >
                  {generating ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Sparkles className="h-4 w-4" />
                  )}
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={removeRoadmap}
                  title="Supprimer"
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              </div>
            ) : (
              <Button size="sm" onClick={generate} disabled={generating}>
                {generating ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Construction…
                  </>
                ) : (
                  <>
                    <Sparkles className="h-4 w-4" />
                    Générer
                  </>
                )}
              </Button>
            )}
          </div>

          {notice && (
            <p className="mb-3 rounded-xl bg-rose-50 px-3 py-2 text-sm font-medium text-rose-600">
              {notice}
            </p>
          )}

          {!roadmap || totalSteps === 0 ? (
            <p className="text-sm font-medium text-slate-400">
              Aucun parcours pour l&apos;instant. L&apos;IA en construira un à
              partir de ton objectif, de ton niveau déclaré et des notions que
              le graphe a mesurées comme fragiles.
            </p>
          ) : (
            <>
              <div className="mb-4 flex items-center gap-3">
                <Progress
                  value={totalSteps ? doneSteps / totalSteps : 0}
                  className="h-2 flex-1"
                />
                <span className="text-xs font-bold text-slate-400">
                  {doneSteps}/{totalSteps}
                </span>
              </div>

              {roadmap.advice && (
                <p className="mb-3 rounded-xl bg-indigo-50/60 px-3 py-2 text-sm font-medium text-indigo-700">
                  {roadmap.advice}
                </p>
              )}
              {!roadmap.feasible && (
                <Badge tone="rose" className="mb-3">
                  Objectif difficile à tenir dans le temps imparti
                </Badge>
              )}

              <div className="flex flex-col gap-2">
                {roadmap.steps.map((step) => (
                  <div
                    key={step.id}
                    className={cn(
                      "rounded-tile border px-4 py-3 transition",
                      step.is_done
                        ? "border-emerald-100 bg-emerald-50/40"
                        : "border-slate-100 bg-white",
                    )}
                  >
                    <div className="flex items-start gap-3">
                      <button
                        onClick={() => toggleStep(step.id, !step.is_done)}
                        className="mt-0.5 shrink-0"
                        title={step.is_done ? "Décocher" : "Marquer comme fait"}
                      >
                        {step.is_done ? (
                          <CircleCheckBig className="h-5 w-5 text-emerald-500" />
                        ) : (
                          <Circle className="h-5 w-5 text-slate-300" />
                        )}
                      </button>
                      <div className="min-w-0 flex-1">
                        <p
                          className={cn(
                            "font-bold text-slate-800",
                            step.is_done && "line-through opacity-60",
                          )}
                        >
                          {step.order_index}. {step.title}
                        </p>
                        {step.why && (
                          <p className="mt-0.5 text-sm font-medium text-slate-500">
                            {step.why}
                          </p>
                        )}
                        <div className="mt-2 flex flex-wrap items-center gap-2">
                          <Badge tone="slate">
                            {SUBJECT_LABELS[step.subject] ?? step.subject}
                          </Badge>
                          <span className="flex items-center gap-1 text-xs font-semibold text-slate-400">
                            <Clock className="h-3 w-3" />
                            {step.estimated_minutes} min
                          </span>
                          {step.node_id && (
                            <Link
                              href={`/review?node=${step.node_id}&focus=25`}
                              className="text-xs font-bold text-indigo-600 hover:text-indigo-500"
                            >
                              Travailler ça →
                            </Link>
                          )}
                        </div>
                        {step.prerequisites && (
                          <p className="mt-1.5 text-xs font-medium italic text-slate-400">
                            Après : {step.prerequisites.split(" | ").join(", ")}
                          </p>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>

              <p className="mt-3 text-xs font-medium text-slate-400">
                {roadmap.total_estimated_hours} h estimées au total
                {roadmap.mocked && " · parcours simulé (AI_MOCK)"}
              </p>
            </>
          )}
        </CardContent>
      </Card>

      {/* ══ Arbre de compétences ═══════════════════════════════════════ */}
      <div className="flex flex-wrap gap-3 px-1">
        {Object.entries(STATUS_STYLES).map(([status, style]) => (
          <span
            key={status}
            className="flex items-center gap-1.5 text-xs font-semibold text-slate-500"
          >
            <span className={cn("h-2.5 w-2.5 rounded-full", style.dot)} />
            {style.label}
          </span>
        ))}
      </div>

      {[...bySubject.entries()].map(([subject, nodes]) => {
        const sorted = [...nodes].sort((a, b) => a.mastery - b.mastery);
        const average =
          nodes.reduce((sum, n) => sum + n.mastery, 0) / nodes.length;
        return (
          <Card key={subject}>
            <CardContent>
              <div className="mb-4 flex items-center justify-between">
                <Link
                  href={`/subjects/${subject}`}
                  className="text-base font-extrabold text-slate-800 hover:text-indigo-600"
                >
                  {SUBJECT_LABELS[subject] ?? subject}
                </Link>
                <Badge tone="indigo">{pct(average)}</Badge>
              </div>

              <div className="flex flex-col gap-1">
                {sorted.map((node) => {
                  const style =
                    STATUS_STYLES[node.status] ?? STATUS_STYLES.available;
                  const locked = node.status === "locked";
                  const open = openNodeId === node.id;
                  return (
                    <div key={node.id}>
                      <button
                        onClick={() => toggleNode(node)}
                        className={cn(
                          "flex w-full items-center gap-3 rounded-xl px-2 py-2 text-left transition hover:bg-slate-50",
                          locked && "opacity-50",
                        )}
                      >
                        <span
                          className={cn("h-2.5 w-2.5 shrink-0 rounded-full", style.dot)}
                        />
                        <span className="flex-1 text-sm font-semibold text-slate-700">
                          {node.title}
                        </span>
                        {locked && <Lock className="h-3.5 w-3.5 text-slate-300" />}
                        <span className="w-28 shrink-0">
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
                        <ChevronDown
                          className={cn(
                            "h-4 w-4 text-slate-300 transition",
                            open && "rotate-180",
                          )}
                        />
                      </button>

                      {open && (
                        <div className="mb-2 ml-5 rounded-2xl bg-slate-50 px-4 py-3">
                          {diagnosisLoading ? (
                            <Loader2 className="h-4 w-4 animate-spin text-slate-400" />
                          ) : diagnosis ? (
                            <>
                              <p className="text-sm font-medium text-slate-600">
                                {diagnosis.verdict}
                              </p>
                              {diagnosis.weak_prerequisites.length > 0 && (
                                <div className="mt-2 flex flex-wrap gap-1.5">
                                  {diagnosis.weak_prerequisites.map((weak) => (
                                    <Badge key={weak.id} tone="amber">
                                      {weak.title} · {pct(weak.mastery)}
                                    </Badge>
                                  ))}
                                </div>
                              )}
                              <Link
                                href={`/review?node=${node.id}&focus=25`}
                                className="mt-2 inline-block text-xs font-bold text-indigo-600 hover:text-indigo-500"
                              >
                                Session Focus sur cette notion →
                              </Link>
                            </>
                          ) : (
                            <p className="text-sm font-medium text-slate-400">
                              Diagnostic indisponible.
                            </p>
                          )}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}
