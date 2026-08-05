"use client";

/**
 * Le Skill Tree — vue macro du graphe de connaissances.
 *
 * Phase 1 volontairement simple : les nœuds groupés par matière, avec statut,
 * maîtrise et verrouillage. Cliquer sur un nœud ouvre son diagnostic —
 * « pourquoi je bloque ici » — calculé en remontant les prérequis.
 * La visualisation interactive (React Flow) arrivera en phase 3.
 */

import { useEffect, useState } from "react";
import { ChevronDown, Loader2, Lock } from "lucide-react";
import { api } from "@/lib/api";
import { cn, pct, STATUS_STYLES, SUBJECT_LABELS } from "@/lib/utils";
import type { DiagnosisRead, GraphRead, NodeRead } from "@/types/api";
import { Card, CardContent } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";

export default function RoadmapPage() {
  const [graph, setGraph] = useState<GraphRead | null>(null);
  const [openNodeId, setOpenNodeId] = useState<number | null>(null);
  const [diagnosis, setDiagnosis] = useState<DiagnosisRead | null>(null);
  const [diagnosisLoading, setDiagnosisLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    api
      .graph()
      .then(setGraph)
      .catch((e) => setError(e.message));
  }, []);

  async function toggle(node: NodeRead) {
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

  // Regroupement par matière, tri interne par maîtrise croissante :
  // le plus fragile en premier, c'est lui qu'on vient chercher.
  const bySubject = new Map<string, NodeRead[]>();
  for (const node of graph.nodes) {
    const list = bySubject.get(node.subject) ?? [];
    list.push(node);
    bySubject.set(node.subject, list);
  }

  return (
    <div className="flex flex-col gap-5">
      <header className="flex items-end justify-between">
        <div>
          <h1 className="text-2xl font-extrabold tracking-tight">Skill Tree</h1>
          <p className="mt-1 text-sm font-medium text-slate-400">
            {graph.counts.total ?? 0} notions · {graph.counts.mastered ?? 0}{" "}
            maîtrisées · {graph.counts.critical ?? 0} critiques
          </p>
        </div>
      </header>

      {/* Légende */}
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
                <h2 className="text-base font-extrabold text-slate-800">
                  {SUBJECT_LABELS[subject] ?? subject}
                </h2>
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
                        onClick={() => toggle(node)}
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
                        <span className="w-32 shrink-0">
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

                      {/* Panneau diagnostic */}
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
