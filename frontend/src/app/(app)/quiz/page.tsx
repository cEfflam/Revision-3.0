"use client";

/**
 * Quiz de vérification.
 *
 * Différence avec les flashcards : la flashcard entraîne le RAPPEL (retrouver
 * de mémoire), le quiz teste la RECONNAISSANCE et surtout la discrimination
 * entre des propositions plausibles. Les deux sont complémentaires, et c'est
 * pour ça que les mauvaises réponses doivent correspondre à de vraies erreurs
 * de compréhension — un distracteur absurde ne teste rien.
 *
 * Le quiz n'est pas persisté : chaque passage est régénéré. Réviser deux fois
 * les mêmes questions entraîne la mémoire des questions, pas la compréhension.
 */

import { Suspense, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import {
  ArrowLeft,
  CheckCircle2,
  Loader2,
  RotateCcw,
  XCircle,
} from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { cn, pct } from "@/lib/utils";
import type { QuizResponse } from "@/types/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";

function QuizSession() {
  const params = useSearchParams();
  const documentId = params.get("document");
  const nodeId = params.get("node");
  const subject = params.get("subject");

  const [quiz, setQuiz] = useState<QuizResponse | null>(null);
  const [index, setIndex] = useState(0);
  const [picked, setPicked] = useState<number | null>(null);
  const [score, setScore] = useState(0);
  const [done, setDone] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(true);

  const load = useCallback(async () => {
    setBusy(true);
    setError("");
    setQuiz(null);
    setIndex(0);
    setPicked(null);
    setScore(0);
    setDone(false);
    try {
      let targetNode = nodeId ? Number(nodeId) : undefined;
      let targetDocument = documentId ? Number(documentId) : undefined;

      // Depuis une matière, on privilégie un COURS importé : c'est la source
      // la plus riche. Une notion ne contient que ses cartes existantes, et
      // parfois aucune — le quiz serait alors vide de substance.
      if (!targetNode && !targetDocument && subject) {
        const detail = await api.subject(subject);
        targetDocument = detail.documents.find((d) => d.status === "ready")?.id;
        if (!targetDocument) {
          targetNode = detail.weak_nodes[0]?.id ?? detail.nodes[0]?.id;
        }
      }

      setQuiz(
        await api.quiz({
          document_id: targetDocument,
          node_id: targetDocument ? undefined : targetNode,
          count: 5,
        }),
      );
    } catch (err) {
      setError(
        err instanceof ApiError ? err.detail : "Génération du quiz impossible.",
      );
    } finally {
      setBusy(false);
    }
  }, [documentId, nodeId, subject]);

  useEffect(() => {
    load();
  }, [load]);

  function choose(choiceIndex: number) {
    if (picked !== null || !quiz) return;
    setPicked(choiceIndex);
    if (choiceIndex === quiz.questions[index].answer_index) {
      setScore((s) => s + 1);
    }
  }

  function next() {
    if (!quiz) return;
    if (index + 1 >= quiz.questions.length) {
      setDone(true);
    } else {
      setIndex(index + 1);
      setPicked(null);
    }
  }

  if (busy) {
    return (
      <div className="flex flex-col items-center gap-3 pt-20">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-indigo-200 border-t-indigo-600" />
        <p className="text-sm font-medium text-slate-400">
          Génération des questions…
        </p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col gap-4">
        <p className="rounded-xl bg-rose-50 px-4 py-3 text-sm font-medium text-rose-600">
          {error}
        </p>
        <Button variant="soft" onClick={load}>
          Réessayer
        </Button>
      </div>
    );
  }

  if (!quiz || quiz.questions.length === 0) {
    return (
      <Card>
        <CardContent className="py-12 text-center">
          <p className="text-sm font-medium text-slate-400">
            Aucune question générée. Importe un cours dans le Brain d&apos;abord.
          </p>
        </CardContent>
      </Card>
    );
  }

  if (done) {
    const ratio = score / quiz.questions.length;
    return (
      <Card>
        <CardContent className="flex flex-col items-center gap-3 py-12 text-center">
          <p className="text-4xl font-black text-indigo-600">
            {score}/{quiz.questions.length}
          </p>
          <p className="text-sm font-medium text-slate-400">
            {ratio >= 0.8
              ? "Solide. Tu peux passer à la suite."
              : ratio >= 0.5
                ? "Correct, mais des zones restent floues."
                : "À reprendre : relis le cours avant de réessayer."}
          </p>
          <div className="mt-2 flex gap-2">
            <Button variant="soft" onClick={load}>
              <RotateCcw className="h-4 w-4" />
              Nouveau quiz
            </Button>
            <Link href="/subjects">
              <Button variant="ghost">Retour aux matières</Button>
            </Link>
          </div>
        </CardContent>
      </Card>
    );
  }

  const question = quiz.questions[index];
  const answered = picked !== null;

  return (
    <div className="flex flex-col gap-4">
      <Link
        href="/subjects"
        className="flex items-center gap-1 text-sm font-semibold text-slate-400 hover:text-indigo-600"
      >
        <ArrowLeft className="h-4 w-4" /> Quitter le quiz
      </Link>

      <div className="flex items-center gap-3">
        <Progress value={index / quiz.questions.length} className="h-2 flex-1" />
        <span className="text-sm font-bold text-slate-400">
          {index + 1}/{quiz.questions.length}
        </span>
      </div>

      <Card>
        <CardContent>
          <div className="mb-4 flex items-center justify-between gap-2">
            <Badge tone="indigo">{quiz.source}</Badge>
            {quiz.mocked && <Badge tone="amber">mode simulé</Badge>}
          </div>

          <p className="mb-5 text-lg font-bold leading-relaxed text-slate-800">
            {question.question}
          </p>

          {question.kind === "mcq" ? (
            <div className="flex flex-col gap-2">
              {question.choices.map((choice, choiceIndex) => {
                const isAnswer = choiceIndex === question.answer_index;
                const isPicked = choiceIndex === picked;
                return (
                  <button
                    key={choiceIndex}
                    onClick={() => choose(choiceIndex)}
                    disabled={answered}
                    className={cn(
                      "flex items-center gap-3 rounded-tile border px-4 py-3 text-left text-sm font-medium transition",
                      !answered && "border-slate-100 hover:bg-indigo-50/40",
                      answered && isAnswer && "border-emerald-200 bg-emerald-50",
                      answered &&
                        isPicked &&
                        !isAnswer &&
                        "border-rose-200 bg-rose-50",
                      answered && !isAnswer && !isPicked && "opacity-50",
                    )}
                  >
                    <span className="flex-1">{choice}</span>
                    {answered && isAnswer && (
                      <CheckCircle2 className="h-5 w-5 shrink-0 text-emerald-500" />
                    )}
                    {answered && isPicked && !isAnswer && (
                      <XCircle className="h-5 w-5 shrink-0 text-rose-500" />
                    )}
                  </button>
                );
              })}
            </div>
          ) : (
            <p className="rounded-tile bg-slate-50 px-4 py-3 text-sm font-medium text-slate-500">
              Question ouverte — formule ta réponse à voix haute, puis compare
              avec l&apos;explication.
            </p>
          )}

          {(answered || question.kind !== "mcq") && question.explanation && (
            <p className="mt-4 rounded-xl bg-indigo-50/60 px-3 py-2 text-sm font-medium text-indigo-700">
              💡 {question.explanation}
            </p>
          )}
        </CardContent>
      </Card>

      {(answered || question.kind !== "mcq") && (
        <Button size="lg" onClick={next}>
          {index + 1 >= quiz.questions.length ? "Voir mon score" : "Question suivante"}
        </Button>
      )}

      {answered && (
        <p className="text-center text-xs font-medium text-slate-400">
          Score en cours : {score}/{index + 1} ({pct(score / (index + 1))})
        </p>
      )}
    </div>
  );
}

export default function QuizPage() {
  // `useSearchParams` impose une frontière Suspense : sans elle, Next refuse
  // de prérendre la page au build.
  return (
    <Suspense
      fallback={
        <div className="flex justify-center pt-20">
          <Loader2 className="h-8 w-8 animate-spin text-indigo-500" />
        </div>
      }
    >
      <QuizSession />
    </Suspense>
  );
}
