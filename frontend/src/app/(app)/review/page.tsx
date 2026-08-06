"use client";

/**
 * Session de révision (Active Recall + SRS) et Mode Focus.
 *
 * Le déroulé applique la science de l'apprentissage à la lettre :
 *   1. la QUESTION s'affiche seule — le cerveau doit chercher AVANT de voir ;
 *   2. « Afficher la réponse » ne vient qu'après cet effort de rappel ;
 *   3. l'auto-évaluation replanifie la carte côté serveur, temps de réflexion
 *      mesuré et transmis ;
 *   4. un échec peut déclencher le diagnostic des prérequis — le graphe parle.
 *
 * Paramètres d'URL :
 *   ?subject=sql    révise une seule matière
 *   ?node=12        cible une seule notion (l'interleaving est alors coupé
 *                   côté serveur : il n'a pas de sens sur une notion unique)
 *   ?focus=25       lance un chronomètre de 25 minutes
 *
 * Le chronomètre ne coupe rien à l'expiration : interrompre quelqu'un au
 * milieu d'une carte détruirait l'effort de rappel en cours. Il signale la
 * fin et laisse terminer.
 */

import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import {
  ArrowLeft,
  CheckCircle2,
  Lightbulb,
  Loader2,
  PartyPopper,
  Timer,
} from "lucide-react";
import { api } from "@/lib/api";
import { cn, formatInterval, pct, SUBJECT_LABELS } from "@/lib/utils";
import type { CardQueueItem, Rating, ReviewResponse } from "@/types/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";

const RATINGS: { value: Rating; label: string; className: string }[] = [
  { value: "again", label: "Oublié", className: "bg-rose-50 text-rose-600 hover:bg-rose-100" },
  { value: "hard", label: "Difficile", className: "bg-amber-50 text-amber-600 hover:bg-amber-100" },
  { value: "good", label: "Correct", className: "bg-indigo-50 text-indigo-600 hover:bg-indigo-100" },
  { value: "easy", label: "Facile", className: "bg-emerald-50 text-emerald-600 hover:bg-emerald-100" },
];

function formatClock(seconds: number): string {
  const m = Math.floor(Math.abs(seconds) / 60);
  const s = Math.abs(seconds) % 60;
  return `${seconds < 0 ? "+" : ""}${m}:${String(s).padStart(2, "0")}`;
}

function ReviewSession() {
  const params = useSearchParams();
  const subject = params.get("subject");
  const nodeParam = params.get("node");
  const focusMinutes = Number(params.get("focus") || 0);

  const [queue, setQueue] = useState<CardQueueItem[]>([]);
  const [index, setIndex] = useState(0);
  const [revealed, setRevealed] = useState(false);
  const [showHint, setShowHint] = useState(false);
  const [phase, setPhase] = useState<"loading" | "active" | "empty" | "done">(
    "loading",
  );
  const [lastDiagnosis, setLastDiagnosis] = useState<ReviewResponse | null>(null);
  const [correct, setCorrect] = useState(0);
  const [reviewedCount, setReviewedCount] = useState(0);
  const [error, setError] = useState("");
  const [remaining, setRemaining] = useState(focusMinutes * 60);

  const sessionId = useRef<number | null>(null);
  const shownAt = useRef<number>(Date.now());

  // ── Démarrage : file ciblée + session serveur ──────────────────────────
  useEffect(() => {
    Promise.all([
      api.queue({
        limit: 30,
        subject: subject ?? undefined,
        node_id: nodeParam ? Number(nodeParam) : undefined,
      }),
      api.startSession("srs", nodeParam ? Number(nodeParam) : undefined),
    ])
      .then(([cards, session]) => {
        sessionId.current = session.id;
        setQueue(cards);
        setPhase(cards.length ? "active" : "empty");
        shownAt.current = Date.now();
      })
      .catch((e) => setError(e.message));
  }, [subject, nodeParam]);

  // ── Chronomètre du Mode Focus ──────────────────────────────────────────
  useEffect(() => {
    if (!focusMinutes || phase !== "active") return;
    const tick = setInterval(() => setRemaining((r) => r - 1), 1000);
    return () => clearInterval(tick);
  }, [focusMinutes, phase]);

  const finish = useCallback(
    async (finalReviewed: number, finalCorrect: number) => {
      setPhase("done");
      if (sessionId.current) {
        try {
          await api.endSession(sessionId.current, finalReviewed, finalCorrect);
        } catch {
          /* la session sera simplement non créditée */
        }
      }
    },
    [],
  );

  async function rate(rating: Rating) {
    const card = queue[index];
    if (!card) return;

    const duration = Date.now() - shownAt.current;
    setLastDiagnosis(null);

    try {
      const response = await api.reviewCard(card.id, rating, duration);
      const nextReviewed = reviewedCount + 1;
      const nextCorrect = correct + (rating === "again" ? 0 : 1);
      setReviewedCount(nextReviewed);
      setCorrect(nextCorrect);

      if (response.diagnosis) setLastDiagnosis(response);

      if (index + 1 >= queue.length) {
        await finish(nextReviewed, nextCorrect);
      } else {
        setIndex(index + 1);
        setRevealed(false);
        setShowHint(false);
        shownAt.current = Date.now();
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erreur.");
    }
  }

  const scopeLabel = subject
    ? (SUBJECT_LABELS[subject] ?? subject)
    : nodeParam && queue[0]?.node_title
      ? queue[0].node_title
      : null;

  // ── Rendus par phase ───────────────────────────────────────────────────
  if (error) {
    return (
      <p className="rounded-xl bg-rose-50 px-4 py-3 text-sm font-medium text-rose-600">
        {error}
      </p>
    );
  }

  if (phase === "loading") {
    return (
      <div className="flex justify-center pt-20">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-indigo-200 border-t-indigo-600" />
      </div>
    );
  }

  if (phase === "empty") {
    return (
      <Card>
        <CardContent className="flex flex-col items-center gap-3 py-12 text-center">
          <CheckCircle2 className="h-10 w-10 text-emerald-500" />
          <h2 className="text-lg font-extrabold">
            {scopeLabel ? `Rien à réviser en ${scopeLabel}` : "Rien à réviser !"}
          </h2>
          <p className="max-w-sm text-sm font-medium text-slate-400">
            L&apos;algorithme n&apos;a programmé aucune carte pour maintenant.
            Importe un cours dans le Brain pour en générer de nouvelles.
          </p>
          <div className="mt-2 flex gap-2">
            {scopeLabel && (
              <Link href="/review">
                <Button variant="soft">Réviser tout</Button>
              </Link>
            )}
            <Link href="/brain">
              <Button variant={scopeLabel ? "ghost" : "soft"}>
                Aller au Brain
              </Button>
            </Link>
          </div>
        </CardContent>
      </Card>
    );
  }

  if (phase === "done") {
    const accuracy = reviewedCount ? correct / reviewedCount : 0;
    const elapsed = focusMinutes ? focusMinutes * 60 - remaining : 0;
    return (
      <Card>
        <CardContent className="flex flex-col items-center gap-3 py-12 text-center">
          <PartyPopper className="h-10 w-10 text-indigo-500" />
          <h2 className="text-lg font-extrabold">Session terminée</h2>
          <p className="text-sm font-medium text-slate-400">
            {reviewedCount} carte{reviewedCount > 1 ? "s" : ""} ·{" "}
            {pct(accuracy)} de réussite
            {focusMinutes > 0 && ` · ${Math.round(elapsed / 60)} min`}
          </p>
          <div className="mt-2 flex gap-2">
            <Link href="/dashboard">
              <Button variant="soft">Retour à l&apos;accueil</Button>
            </Link>
            <Button onClick={() => window.location.reload()}>
              Nouvelle session
            </Button>
          </div>
        </CardContent>
      </Card>
    );
  }

  const card = queue[index];
  const timeUp = focusMinutes > 0 && remaining <= 0;

  return (
    <div className="flex flex-col gap-4">
      {/* Bandeau de portée + chronomètre */}
      {(scopeLabel || focusMinutes > 0) && (
        <div className="flex items-center justify-between gap-3">
          {scopeLabel ? (
            <Link
              href="/subjects"
              className="flex items-center gap-1 text-sm font-semibold text-slate-400 hover:text-indigo-600"
            >
              <ArrowLeft className="h-4 w-4" />
              {scopeLabel}
            </Link>
          ) : (
            <span />
          )}
          {focusMinutes > 0 && (
            <Badge
              tone={timeUp ? "emerald" : "indigo"}
              className="px-3 py-1.5 text-sm tabular-nums"
            >
              <Timer className="h-4 w-4" />
              {formatClock(remaining)}
            </Badge>
          )}
        </div>
      )}

      {timeUp && (
        <div className="rounded-2xl border border-emerald-100 bg-emerald-50 px-4 py-3">
          <p className="text-sm font-semibold text-emerald-800">
            ⏱️ Les {focusMinutes} minutes sont écoulées. Termine cette carte
            tranquillement, puis arrête quand tu veux.
          </p>
          <Button
            size="sm"
            variant="soft"
            className="mt-2"
            onClick={() => finish(reviewedCount, correct)}
          >
            Clôturer la session
          </Button>
        </div>
      )}

      {/* Progression */}
      <div className="flex items-center gap-3">
        <Progress value={index / queue.length} className="h-2 flex-1" />
        <span className="text-sm font-bold text-slate-400">
          {index + 1}/{queue.length}
        </span>
      </div>

      {lastDiagnosis && (
        <div className="rounded-2xl border border-amber-100 bg-amber-50 px-4 py-3">
          <p className="text-sm font-semibold text-amber-800">
            🔍 {lastDiagnosis.diagnosis}
          </p>
        </div>
      )}

      <AnimatePresence mode="wait">
        <motion.div
          key={card.id}
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -12 }}
          transition={{ duration: 0.18 }}
        >
          <Card>
            <CardContent className="flex min-h-[280px] flex-col">
              {card.node_title && (
                <Badge tone="indigo" className="mb-4 self-start">
                  {card.node_title}
                </Badge>
              )}

              <p className="flex-1 whitespace-pre-wrap text-lg font-bold leading-relaxed text-slate-800">
                {card.front}
              </p>

              {!revealed && card.hint && (
                <div className="mt-4">
                  {showHint ? (
                    <p className="rounded-xl bg-slate-50 px-3 py-2 text-sm font-medium text-slate-500">
                      💡 {card.hint}
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

              {revealed && (
                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  className="mt-5 border-t border-slate-100 pt-5"
                >
                  <p className="whitespace-pre-wrap font-medium leading-relaxed text-slate-700">
                    {card.back}
                  </p>
                  {card.explanation && (
                    <p className="mt-3 rounded-xl bg-indigo-50/60 px-3 py-2 text-sm font-medium text-indigo-700">
                      {card.explanation}
                    </p>
                  )}
                </motion.div>
              )}
            </CardContent>
          </Card>
        </motion.div>
      </AnimatePresence>

      {!revealed ? (
        <Button size="lg" onClick={() => setRevealed(true)}>
          Afficher la réponse
        </Button>
      ) : (
        <div className="grid grid-cols-4 gap-2">
          {RATINGS.map((rating) => (
            <button
              key={rating.value}
              onClick={() => rate(rating.value)}
              className={cn(
                "rounded-2xl px-2 py-3 text-sm font-bold transition active:scale-95",
                rating.className,
              )}
            >
              {rating.label}
            </button>
          ))}
        </div>
      )}

      {revealed && (
        <p className="text-center text-xs font-medium text-slate-400">
          Intervalle actuel : {formatInterval(card.interval_days)} · Sois honnête
          — l&apos;algorithme travaille pour toi, pas pour ta fierté.
        </p>
      )}
    </div>
  );
}

export default function ReviewPage() {
  return (
    <Suspense
      fallback={
        <div className="flex justify-center pt-20">
          <Loader2 className="h-8 w-8 animate-spin text-indigo-500" />
        </div>
      }
    >
      <ReviewSession />
    </Suspense>
  );
}
