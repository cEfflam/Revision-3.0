"use client";

/**
 * Entraînement type examen.
 *
 * Trois temps, comme une vraie épreuve :
 *   1. CHOISIR la matière — le format d'épreuve s'affiche AVANT de commencer,
 *      pour que l'étudiant sache sur quoi il sera jugé ;
 *   2. COMPOSER — chronomètre, énoncé, champ de réponse adapté à la matière
 *      (texte rédigé, code, requête SQL) ;
 *   3. RECEVOIR LA CORRECTION — note, détail question par question, grille de
 *      critères, et une seule priorité de travail.
 *
 * Le sujet n'est pas persisté : il est renvoyé tel quel au serveur pour la
 * correction. Ce qui doit durer, c'est la trace de progression — la session et
 * l'activité du jour, créditées à la correction.
 */

import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import {
  AlertTriangle,
  ArrowLeft,
  BookMarked,
  CheckCircle2,
  ClipboardList,
  Clock,
  Loader2,
  Send,
  Sparkles,
  Timer,
  XCircle,
} from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { ExamEvaluation, ExamRead, PracticeSubject } from "@/types/api";
import { Button } from "@/components/ui/button";
import { Input, Textarea } from "@/components/ui/input";
import { Card, CardContent, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";

type Phase = "choose" | "generating" | "compose" | "grading" | "result";

const VERDICT_TONES: Record<string, "emerald" | "amber" | "rose"> = {
  acquis: "emerald",
  fragile: "amber",
  "non acquis": "rose",
};

function clock(seconds: number): string {
  const m = Math.floor(Math.abs(seconds) / 60);
  const s = Math.abs(seconds) % 60;
  return `${seconds < 0 ? "+" : ""}${m}:${String(s).padStart(2, "0")}`;
}

function PracticeSession() {
  const params = useSearchParams();
  const initialSubject = params.get("subject") ?? "";

  const [subjects, setSubjects] = useState<PracticeSubject[]>([]);
  const [subject, setSubject] = useState(initialSubject);
  const [topic, setTopic] = useState("");
  const [phase, setPhase] = useState<Phase>("choose");
  const [exam, setExam] = useState<ExamRead | null>(null);
  const [answer, setAnswer] = useState("");
  const [evaluation, setEvaluation] = useState<ExamEvaluation | null>(null);
  const [remaining, setRemaining] = useState(0);
  const [error, setError] = useState("");
  const answerRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    api.practiceSubjects().then(setSubjects).catch(() => {});
  }, []);

  // Chronomètre de composition. Il ne coupe rien : il informe.
  useEffect(() => {
    if (phase !== "compose") return;
    const tick = setInterval(() => setRemaining((r) => r - 1), 1000);
    return () => clearInterval(tick);
  }, [phase]);

  const generate = useCallback(async () => {
    if (!subject) return;
    setPhase("generating");
    setError("");
    setEvaluation(null);
    setAnswer("");
    try {
      const generated = await api.generateExam({ subject, topic: topic.trim() });
      setExam(generated);
      setRemaining(generated.duration_minutes * 60);
      setPhase("compose");
    } catch (err) {
      setError(
        err instanceof ApiError ? err.detail : "Génération impossible.",
      );
      setPhase("choose");
    }
  }, [subject, topic]);

  async function submit() {
    if (!exam || answer.trim().length < 10) return;
    setPhase("grading");
    setError("");
    try {
      setEvaluation(
        await api.evaluateExam({ subject, exercise: exam, answer: answer.trim() }),
      );
      setPhase("result");
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Correction impossible.");
      setPhase("compose");
    }
  }

  function restart() {
    setPhase("choose");
    setExam(null);
    setAnswer("");
    setEvaluation(null);
    setError("");
  }

  // ── 1. Choix de la matière ─────────────────────────────────────────────
  if (phase === "choose" || phase === "generating") {
    const chosen = subjects.find((s) => s.subject === subject);
    return (
      <div className="flex flex-col gap-5">
        <header>
          <h1 className="text-2xl font-extrabold tracking-tight">
            Entraînement type BTS 📝
          </h1>
          <p className="mt-1 text-sm font-medium text-slate-400">
            L&apos;IA reprend la <strong>forme</strong> de tes BTS blancs et
            invente un sujet neuf sur le <strong>contenu</strong> de tes cours.
          </p>
        </header>

        <Card>
          <CardContent className="flex flex-col gap-3">
            <CardTitle>Matière</CardTitle>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
              {subjects.map((s) => (
                <button
                  key={s.subject}
                  onClick={() => setSubject(s.subject)}
                  className={cn(
                    "rounded-tile border px-3 py-2.5 text-left transition",
                    subject === s.subject
                      ? "border-indigo-200 bg-indigo-50"
                      : "border-slate-100 hover:bg-slate-50",
                  )}
                >
                  <span className="block text-sm font-bold text-slate-800">
                    {s.label}
                  </span>
                  <span className="block text-xs font-medium text-slate-400">
                    {s.exam_label}
                  </span>
                </button>
              ))}
            </div>

            <Input
              placeholder="Thème précis (optionnel) — sinon tes notions les plus fragiles"
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
            />

            {error && (
              <p className="rounded-xl bg-rose-50 px-3 py-2 text-sm font-medium text-rose-600">
                {error}
              </p>
            )}

            <Button
              size="lg"
              onClick={generate}
              disabled={!subject || phase === "generating"}
            >
              {phase === "generating" ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Conception du sujet…
                </>
              ) : (
                <>
                  <Sparkles className="h-4 w-4" />
                  Générer un sujet
                  {chosen ? ` de ${chosen.label}` : ""}
                </>
              )}
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  // ── 3. Correction ──────────────────────────────────────────────────────
  if (phase === "result" && evaluation && exam) {
    const ratio = evaluation.max_score
      ? evaluation.score / evaluation.max_score
      : 0;
    return (
      <div className="flex flex-col gap-5">
        <Card>
          <CardContent className="text-center">
            <p
              className={cn(
                "text-5xl font-black",
                ratio >= 0.7
                  ? "text-emerald-600"
                  : ratio >= 0.5
                    ? "text-amber-500"
                    : "text-rose-500",
              )}
            >
              {evaluation.score}
              <span className="text-2xl text-slate-300">
                /{evaluation.max_score}
              </span>
            </p>
            <Progress
              value={ratio}
              className="mt-4"
              barClassName={
                ratio >= 0.7
                  ? "bg-emerald-500"
                  : ratio >= 0.5
                    ? "bg-amber-400"
                    : "bg-rose-500"
              }
            />
            <p className="mt-3 text-sm font-medium text-slate-400">
              {exam.format.label} · {exam.title}
            </p>
          </CardContent>
        </Card>

        {evaluation.per_question.length > 0 && (
          <Card>
            <CardContent>
              <CardTitle className="mb-3 text-base">
                Détail par question
              </CardTitle>
              <div className="flex flex-col gap-3">
                {evaluation.per_question.map((q) => {
                  const full = q.points_earned >= q.points_max && q.points_max > 0;
                  return (
                    <div
                      key={q.number}
                      className="rounded-tile border border-slate-100 px-4 py-3"
                    >
                      <div className="mb-1 flex items-center gap-2">
                        {full ? (
                          <CheckCircle2 className="h-4 w-4 text-emerald-500" />
                        ) : (
                          <XCircle className="h-4 w-4 text-rose-400" />
                        )}
                        <span className="font-bold text-slate-800">
                          Question {q.number}
                        </span>
                        <Badge
                          tone={
                            full ? "emerald" : q.points_earned > 0 ? "amber" : "rose"
                          }
                          className="ml-auto"
                        >
                          {q.points_earned}/{q.points_max}
                        </Badge>
                      </div>
                      <p className="text-sm font-medium leading-relaxed text-slate-600">
                        {q.feedback}
                      </p>
                    </div>
                  );
                })}
              </div>
            </CardContent>
          </Card>
        )}

        {evaluation.criteria_feedback.length > 0 && (
          <Card>
            <CardContent>
              <CardTitle className="mb-3 text-base">
                Grille de l&apos;épreuve
              </CardTitle>
              <div className="flex flex-col gap-2">
                {evaluation.criteria_feedback.map((c, i) => (
                  <div key={i} className="flex items-start gap-2">
                    <Badge tone={VERDICT_TONES[c.verdict] ?? "slate"}>
                      {c.verdict}
                    </Badge>
                    <span className="flex-1 text-sm font-medium text-slate-600">
                      <strong className="text-slate-800">{c.criterion}</strong>
                      {c.comment ? ` — ${c.comment}` : ""}
                    </span>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        )}

        {(evaluation.strengths.length > 0 || evaluation.gaps.length > 0) && (
          <Card>
            <CardContent className="flex flex-col gap-3">
              {evaluation.strengths.length > 0 && (
                <div>
                  <CardTitle className="mb-1.5 text-base text-emerald-700">
                    Acquis
                  </CardTitle>
                  <ul className="flex flex-col gap-1">
                    {evaluation.strengths.map((s, i) => (
                      <li key={i} className="text-sm font-medium text-slate-600">
                        • {s}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              {evaluation.gaps.length > 0 && (
                <div>
                  <CardTitle className="mb-1.5 text-base text-rose-700">
                    Lacunes
                  </CardTitle>
                  <ul className="flex flex-col gap-1">
                    {evaluation.gaps.map((g, i) => (
                      <li key={i} className="text-sm font-medium text-slate-600">
                        • {g}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </CardContent>
          </Card>
        )}

        {evaluation.next_step && (
          <Card className="border-indigo-100 bg-indigo-50/40">
            <CardContent>
              <CardTitle className="mb-1.5 text-base">Ta priorité</CardTitle>
              <p className="text-sm font-medium leading-relaxed text-slate-700">
                {evaluation.next_step}
              </p>
            </CardContent>
          </Card>
        )}

        <div className="flex gap-2">
          <Button variant="soft" onClick={restart}>
            Nouveau sujet
          </Button>
          <Button variant="ghost" onClick={() => setPhase("compose")}>
            Revoir ma copie
          </Button>
        </div>
      </div>
    );
  }

  // ── 2. Composition ─────────────────────────────────────────────────────
  if (!exam) return null;
  const timeUp = remaining <= 0;
  const isCode = exam.format.input_kind !== "text";

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between gap-3">
        <button
          onClick={restart}
          className="flex items-center gap-1 text-sm font-semibold text-slate-400 hover:text-indigo-600"
        >
          <ArrowLeft className="h-4 w-4" /> Changer de sujet
        </button>
        <Badge
          tone={timeUp ? "rose" : "indigo"}
          className="px-3 py-1.5 text-sm tabular-nums"
        >
          <Timer className="h-4 w-4" />
          {clock(remaining)}
        </Badge>
      </div>

      {/* L'énoncé */}
      <Card>
        <CardContent>
          <div className="mb-3 flex flex-wrap items-center gap-2">
            <Badge tone="indigo">{exam.format.label}</Badge>
            <span className="flex items-center gap-1 text-xs font-semibold text-slate-400">
              <Clock className="h-3 w-3" />
              {exam.duration_minutes} min · {exam.total_points} pts
            </span>
            {exam.has_annales ? (
              <Badge tone="emerald">
                <BookMarked className="h-3 w-3" />
                style de tes annales
              </Badge>
            ) : (
              <Badge tone="amber">
                <AlertTriangle className="h-3 w-3" />
                aucune annale importée
              </Badge>
            )}
          </div>

          <h1 className="text-xl font-extrabold leading-snug text-slate-800">
            {exam.title}
          </h1>
          {exam.instructions && (
            <p className="mt-2 rounded-xl bg-slate-50 px-3 py-2 text-sm font-medium text-slate-600">
              {exam.instructions}
            </p>
          )}

          {exam.context && (
            <p className="mt-4 whitespace-pre-wrap text-sm font-medium leading-relaxed text-slate-700">
              {exam.context}
            </p>
          )}

          <div className="mt-5 flex flex-col gap-2 border-t border-slate-100 pt-4">
            {exam.questions.map((q) => (
              <p key={q.number} className="text-sm font-medium text-slate-700">
                <strong className="text-slate-900">
                  {q.number}.
                </strong>{" "}
                <span className="text-xs font-bold text-indigo-500">
                  ({q.points} pts)
                </span>{" "}
                {q.text}
              </p>
            ))}
          </div>

          {exam.inspired_by && (
            <p className="mt-4 text-xs font-medium italic text-slate-400">
              Inspiration : {exam.inspired_by}
            </p>
          )}
        </CardContent>
      </Card>

      {/* Ce sur quoi tu es jugé — affiché AVANT de composer */}
      <Card>
        <CardContent>
          <CardTitle className="mb-2 flex items-center gap-2 text-base">
            <ClipboardList className="h-5 w-5 text-indigo-500" />
            Méthode et critères
          </CardTitle>
          <p className="text-sm font-medium leading-relaxed text-slate-600">
            {exam.format.method}
          </p>
          <div className="mt-3 flex flex-wrap gap-1.5">
            {exam.format.criteria.map((c, i) => (
              <Badge key={i} tone="slate">
                {c}
              </Badge>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* La copie */}
      <Card>
        <CardContent>
          <CardTitle className="mb-2 text-base">Ta copie</CardTitle>
          <Textarea
            ref={answerRef}
            rows={isCode ? 16 : 18}
            value={answer}
            onChange={(e) => setAnswer(e.target.value)}
            placeholder={exam.format.placeholder}
            className={cn(
              "min-h-[320px] leading-relaxed",
              isCode && "font-mono text-[13px]",
            )}
            spellCheck={!isCode}
          />
          <div className="mt-2 flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-400">
              {answer.trim().length} caractères
            </span>
            <Button
              onClick={submit}
              disabled={answer.trim().length < 10 || phase === "grading"}
            >
              {phase === "grading" ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Correction en cours…
                </>
              ) : (
                <>
                  <Send className="h-4 w-4" />
                  Rendre ma copie
                </>
              )}
            </Button>
          </div>
          {error && (
            <p className="mt-2 rounded-xl bg-rose-50 px-3 py-2 text-sm font-medium text-rose-600">
              {error}
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

export default function PracticePage() {
  return (
    <Suspense
      fallback={
        <div className="flex justify-center pt-20">
          <Loader2 className="h-8 w-8 animate-spin text-indigo-500" />
        </div>
      }
    >
      <PracticeSession />
    </Suspense>
  );
}
