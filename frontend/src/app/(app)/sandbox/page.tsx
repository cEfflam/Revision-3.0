"use client";

/**
 * Bacs à sable SQL et pseudo-code.
 *
 * SQL : ta requête est RÉELLEMENT exécutée sur une base SQLite créée pour
 * l'occasion et détruite aussitôt. C'est le résultat qui juge, pas
 * l'apparence de la requête — deux formulations différentes qui renvoient la
 * même chose sont toutes deux justes, et c'est la réalité de SQL.
 *
 * Pseudo-code : rien à exécuter par définition. L'IA déroule l'algorithme
 * pas à pas et montre où le résultat diverge. La trace apprend mieux qu'un
 * verdict.
 */

import { useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  Database,
  Eye,
  Lightbulb,
  Loader2,
  Play,
  Sparkles,
  Terminal,
  XCircle,
} from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { cn } from "@/lib/utils";
import type {
  PseudocodeResponse,
  SqlExercise,
  SqlRunResponse,
} from "@/types/api";
import { Button } from "@/components/ui/button";
import { Input, Textarea } from "@/components/ui/input";
import { Card, CardContent, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Waiting } from "@/components/ui/waiting";

type Mode = "sql" | "pseudocode";

function ResultTable({
  columns,
  rows,
  tone = "slate",
}: {
  columns: string[];
  rows: string[][];
  tone?: "slate" | "emerald";
}) {
  if (columns.length === 0) return null;
  return (
    <div className="overflow-x-auto rounded-xl border border-slate-100">
      <table className="w-full text-left text-xs">
        <thead
          className={cn(
            "font-bold",
            tone === "emerald"
              ? "bg-emerald-50 text-emerald-800"
              : "bg-slate-50 text-slate-600",
          )}
        >
          <tr>
            {columns.map((c, i) => (
              <th key={i} className="whitespace-nowrap px-3 py-2">
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="font-medium text-slate-700">
          {rows.map((row, i) => (
            <tr key={i} className="border-t border-slate-100">
              {row.map((cell, j) => (
                <td
                  key={j}
                  className={cn(
                    "whitespace-nowrap px-3 py-1.5",
                    cell === "NULL" && "italic text-slate-300",
                  )}
                >
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function SandboxPage() {
  const [mode, setMode] = useState<Mode>("sql");

  // ── SQL ────────────────────────────────────────────────────────────────
  const [topic, setTopic] = useState("");
  const [exercise, setExercise] = useState<SqlExercise | null>(null);
  const [query, setQuery] = useState("");
  const [result, setResult] = useState<SqlRunResponse | null>(null);
  const [showHint, setShowHint] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [running, setRunning] = useState(false);

  // ── Pseudo-code ────────────────────────────────────────────────────────
  const [code, setCode] = useState("");
  const [intent, setIntent] = useState("");
  const [analysis, setAnalysis] = useState<PseudocodeResponse | null>(null);
  const [analysing, setAnalysing] = useState(false);

  const [error, setError] = useState("");

  async function generate() {
    setGenerating(true);
    setError("");
    setResult(null);
    setQuery("");
    setShowHint(false);
    try {
      setExercise(await api.sqlExercise({ topic: topic.trim(), difficulty: 3 }));
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Génération impossible.");
    } finally {
      setGenerating(false);
    }
  }

  async function run(giveUp = false) {
    if (!exercise) return;
    setRunning(true);
    setError("");
    try {
      setResult(await api.runSql(exercise.exercise_id, query || "SELECT 1", giveUp));
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Exécution impossible.");
    } finally {
      setRunning(false);
    }
  }

  async function analyse() {
    setAnalysing(true);
    setError("");
    try {
      setAnalysis(await api.reviewPseudocode(code, intent.trim()));
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Analyse impossible.");
    } finally {
      setAnalysing(false);
    }
  }

  return (
    <div className="flex flex-col gap-5">
      <header>
        <h1 className="text-2xl font-extrabold tracking-tight">
          Bac à sable 🧪
        </h1>
        <p className="mt-1 text-sm font-medium text-slate-400">
          Écris, exécute, casse. C&apos;est en faisant tourner qu&apos;on
          comprend.
        </p>
      </header>

      <div className="flex gap-1 rounded-tile bg-slate-100/70 p-1">
        {(
          [
            ["sql", "SQL exécutable", Database],
            ["pseudocode", "Pseudo-code", Terminal],
          ] as [Mode, string, typeof Database][]
        ).map(([value, label, Icon]) => (
          <button
            key={value}
            onClick={() => setMode(value)}
            className={cn(
              "flex flex-1 items-center justify-center gap-2 rounded-xl px-3 py-2 text-sm font-bold transition",
              mode === value
                ? "bg-white text-indigo-700 shadow-soft"
                : "text-slate-500 hover:text-slate-700",
            )}
          >
            <Icon className="h-4 w-4" />
            {label}
          </button>
        ))}
      </div>

      {error && (
        <p className="rounded-xl bg-rose-50 px-4 py-3 text-sm font-medium text-rose-600">
          {error}
        </p>
      )}

      {/* ══ Mode SQL ═══════════════════════════════════════════════════ */}
      {mode === "sql" && (
        <>
          {!exercise ? (
            <Card>
              <CardContent className="flex flex-col gap-3">
                <CardTitle>Générer un exercice</CardTitle>
                <p className="-mt-1 text-sm font-medium text-slate-400">
                  Une vraie base est créée, avec un piège glissé dans les
                  données. Ta requête sera exécutée dessus.
                </p>
                <Input
                  placeholder="Thème (optionnel) : jointures externes, GROUP BY, sous-requêtes…"
                  value={topic}
                  onChange={(e) => setTopic(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && generate()}
                />
                <Button size="lg" onClick={generate} disabled={generating}>
                  {generating ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin" />
                      Construction de la base…
                    </>
                  ) : (
                    <>
                      <Sparkles className="h-4 w-4" />
                      Générer un exercice
                    </>
                  )}
                </Button>
                {/* Mesuré : 63 s de bout en bout. Sans ce compteur, on croit
                    que c'est planté et on recharge. */}
                <Waiting
                  active={generating}
                  label="Schéma, jeu de données et solution en cours d'écriture"
                  typicalSeconds={60}
                />
              </CardContent>
            </Card>
          ) : (
            <>
              {/* L'énoncé */}
              <Card>
                <CardContent>
                  <div className="mb-2 flex flex-wrap items-center gap-2">
                    <Badge tone="indigo">{exercise.title}</Badge>
                    {exercise.mocked && <Badge tone="amber">mode simulé</Badge>}
                  </div>
                  <p className="font-bold leading-relaxed text-slate-800">
                    {exercise.question}
                  </p>
                  {exercise.hint && (
                    <div className="mt-3">
                      {showHint ? (
                        <p className="rounded-xl bg-slate-50 px-3 py-2 text-sm font-medium text-slate-600">
                          💡 {exercise.hint}
                        </p>
                      ) : (
                        <button
                          onClick={() => setShowHint(true)}
                          className="flex items-center gap-1.5 text-sm font-semibold text-slate-400 hover:text-indigo-600"
                        >
                          <Lightbulb className="h-4 w-4" /> Voir l&apos;indice
                        </button>
                      )}
                    </div>
                  )}
                </CardContent>
              </Card>

              {/* Les données — les voir fait partie de l'exercice */}
              <Card>
                <CardContent>
                  <CardTitle className="mb-3 flex items-center gap-2 text-base">
                    <Database className="h-5 w-5 text-indigo-500" />
                    Les tables
                  </CardTitle>
                  <div className="flex flex-col gap-3">
                    {exercise.tables_preview.map((table) => (
                      <div key={table.name}>
                        <p className="mb-1 text-xs font-bold text-slate-600">
                          {table.name}{" "}
                          <span className="font-medium text-slate-400">
                            ({table.row_count} lignes)
                          </span>
                        </p>
                        <ResultTable columns={table.columns} rows={table.rows} />
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>

              {/* La requête */}
              <Card>
                <CardContent>
                  <CardTitle className="mb-2 text-base">Ta requête</CardTitle>
                  <Textarea
                    rows={7}
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    placeholder={"SELECT ...\nFROM ...\nWHERE ...;"}
                    className="min-h-0 font-mono text-[13px]"
                    spellCheck={false}
                  />
                  <div className="mt-2 flex flex-wrap gap-2">
                    <Button onClick={() => run()} disabled={running || !query.trim()}>
                      {running ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        <Play className="h-4 w-4" />
                      )}
                      Exécuter
                    </Button>
                    <Button variant="ghost" onClick={() => run(true)} disabled={running}>
                      <Eye className="h-4 w-4" />
                      Voir la solution
                    </Button>
                    <Button variant="ghost" onClick={generate} disabled={generating}>
                      Autre exercice
                    </Button>
                  </div>
                </CardContent>
              </Card>

              {/* Le résultat */}
              {result && (
                <Card
                  className={cn(
                    result.correct ? "border-emerald-200" : "border-slate-100",
                  )}
                >
                  <CardContent>
                    <div className="mb-3 flex items-start gap-2">
                      {result.correct ? (
                        <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-emerald-500" />
                      ) : (
                        <XCircle className="mt-0.5 h-5 w-5 shrink-0 text-rose-400" />
                      )}
                      <p
                        className={cn(
                          "text-sm font-semibold",
                          result.correct ? "text-emerald-700" : "text-slate-700",
                        )}
                      >
                        {result.explanation}
                      </p>
                    </div>

                    {result.error && (
                      <p className="mb-3 rounded-xl bg-rose-50 px-3 py-2 font-mono text-xs text-rose-700">
                        {result.error}
                      </p>
                    )}

                    {result.rows.length > 0 && (
                      <>
                        <p className="mb-1 text-xs font-bold text-slate-500">
                          Ton résultat
                        </p>
                        <ResultTable columns={result.columns} rows={result.rows} />
                      </>
                    )}

                    {result.expected_rows.length > 0 && (
                      <div className="mt-3">
                        <p className="mb-1 text-xs font-bold text-emerald-700">
                          Résultat attendu
                        </p>
                        <ResultTable
                          columns={result.expected_columns}
                          rows={result.expected_rows}
                          tone="emerald"
                        />
                      </div>
                    )}

                    {result.solution && (
                      <div className="mt-3">
                        <p className="mb-1 text-xs font-bold text-slate-500">
                          Une requête qui fonctionne
                        </p>
                        <pre className="overflow-x-auto rounded-xl bg-slate-900 px-3 py-2 font-mono text-xs text-slate-100">
                          {result.solution}
                        </pre>
                      </div>
                    )}

                    {result.correct && exercise.trap && (
                      <p className="mt-3 rounded-xl bg-indigo-50/60 px-3 py-2 text-sm font-medium text-indigo-700">
                        🪤 Le piège de cet exercice : {exercise.trap}
                      </p>
                    )}
                  </CardContent>
                </Card>
              )}
            </>
          )}
        </>
      )}

      {/* ══ Mode pseudo-code ═══════════════════════════════════════════ */}
      {mode === "pseudocode" && (
        <>
          <Card>
            <CardContent className="flex flex-col gap-3">
              <CardTitle>Ton algorithme</CardTitle>
              <p className="-mt-1 text-sm font-medium text-slate-400">
                Rien n&apos;est exécuté — du pseudo-code ne s&apos;exécute pas.
                L&apos;IA le déroule pas à pas et te montre où ça casse.
              </p>
              <Input
                placeholder="Ce que l'algorithme doit faire (recommandé)"
                value={intent}
                onChange={(e) => setIntent(e.target.value)}
              />
              <Textarea
                rows={12}
                value={code}
                onChange={(e) => setCode(e.target.value)}
                placeholder={
                  "FONCTION maximum(tableau T, entier n)\n  max <- 0\n  POUR i DE 1 A n FAIRE\n    ...\n  FIN POUR\nFIN FONCTION"
                }
                className="min-h-[240px] font-mono text-[13px]"
                spellCheck={false}
              />
              <Button
                onClick={analyse}
                disabled={analysing || code.trim().length < 10}
              >
                {analysing ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Déroulement pas à pas…
                  </>
                ) : (
                  <>
                    <Play className="h-4 w-4" />
                    Dérouler mon algorithme
                  </>
                )}
              </Button>
              <Waiting
                active={analysing}
                label="Le modèle déroule ton algorithme sur un jeu de valeurs"
                typicalSeconds={90}
              />
            </CardContent>
          </Card>

          {analysis && (
            <>
              <Card
                className={cn(
                  analysis.correct ? "border-emerald-200" : "border-rose-100",
                )}
              >
                <CardContent>
                  <div className="flex items-start gap-2">
                    {analysis.correct ? (
                      <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-emerald-500" />
                    ) : (
                      <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-rose-500" />
                    )}
                    <div>
                      <p className="text-sm font-semibold text-slate-800">
                        {analysis.verdict}
                      </p>
                      {analysis.complexity && (
                        <p className="mt-1 text-xs font-medium text-slate-400">
                          Complexité : {analysis.complexity}
                        </p>
                      )}
                    </div>
                  </div>
                </CardContent>
              </Card>

              {analysis.trace.length > 0 && (
                <Card>
                  <CardContent>
                    <CardTitle className="mb-3 text-base">
                      Déroulé pas à pas
                    </CardTitle>
                    <div className="flex flex-col gap-1.5">
                      {analysis.trace.map((step) => (
                        <div
                          key={step.step}
                          className="flex gap-3 rounded-xl bg-slate-50 px-3 py-2"
                        >
                          <span className="shrink-0 font-mono text-xs font-bold text-indigo-500">
                            {step.step}
                          </span>
                          <span className="flex-1">
                            <span className="block font-mono text-xs font-bold text-slate-700">
                              {step.state}
                            </span>
                            {step.comment && (
                              <span className="block text-xs font-medium text-slate-500">
                                {step.comment}
                              </span>
                            )}
                          </span>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              )}

              {analysis.issues.length > 0 && (
                <Card>
                  <CardContent>
                    <CardTitle className="mb-3 text-base">
                      Ce qui ne va pas
                    </CardTitle>
                    <div className="flex flex-col gap-2">
                      {analysis.issues.map((issue, index) => (
                        <div
                          key={index}
                          className="rounded-tile border border-slate-100 px-4 py-3"
                        >
                          <div className="mb-1.5 flex flex-wrap items-center gap-2">
                            <Badge
                              tone={
                                issue.severity === "bloquant" ? "rose" : "amber"
                              }
                            >
                              {issue.severity}
                            </Badge>
                            {issue.line && (
                              <code className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-xs text-slate-700">
                                {issue.line}
                              </code>
                            )}
                          </div>
                          <p className="text-sm font-medium text-slate-600">
                            {issue.problem}
                          </p>
                          {issue.fix && (
                            <p className="mt-1.5 rounded-xl bg-emerald-50 px-3 py-2 text-sm font-medium text-emerald-800">
                              → {issue.fix}
                            </p>
                          )}
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              )}
            </>
          )}
        </>
      )}
    </div>
  );
}
