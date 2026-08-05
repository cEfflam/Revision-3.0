"use client";

/**
 * Audit d'écrit — Culture Générale et Expression.
 *
 * Ce n'est pas un correcteur qui met une note : une note ne dit pas quoi
 * retravailler. L'IA renvoie des problèmes LOCALISÉS, chacun accompagné d'un
 * extrait exact du texte. Cliquer sur un problème surligne le passage fautif
 * dans la copie — c'est la différence entre « 11/20 » et « ce paragraphe
 * répète l'idée du premier ».
 *
 * Le backend ne conserve `quote` que s'il figure littéralement dans le texte
 * soumis, donc la recherche de sous-chaîne ci-dessous est fiable.
 */

import { useMemo, useState } from "react";
import {
  AlertTriangle,
  BookOpen,
  CheckCircle2,
  Copy,
  Layers,
  Loader2,
  MessageSquareQuote,
  Repeat,
  Sparkles,
  Target,
  type LucideIcon,
} from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { WritingAnalysis, WritingIssue } from "@/types/api";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/input";
import { Card, CardContent, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";

const MIN_CHARS = 50;

/** Libellé + icône par type de problème (miroir du prompt CGE_ANALYSIS). */
const ISSUE_META: Record<string, { label: string; icon: LucideIcon }> = {
  plan: { label: "Plan", icon: Layers },
  repetition: { label: "Répétition", icon: Repeat },
  transition: { label: "Transition", icon: Copy },
  vocabulary: { label: "Vocabulaire", icon: BookOpen },
  syntax: { label: "Syntaxe", icon: MessageSquareQuote },
  argument: { label: "Argumentation", icon: Target },
};

const SEVERITY_STYLES: Record<
  string,
  { tone: "rose" | "amber" | "indigo"; ring: string; mark: string }
> = {
  critical: {
    tone: "rose",
    ring: "border-rose-200 bg-rose-50/50",
    mark: "bg-rose-200/70",
  },
  warning: {
    tone: "amber",
    ring: "border-amber-200 bg-amber-50/50",
    mark: "bg-amber-200/70",
  },
  info: {
    tone: "indigo",
    ring: "border-indigo-200 bg-indigo-50/50",
    mark: "bg-indigo-200/70",
  },
};

function severityOf(issue: WritingIssue) {
  return SEVERITY_STYLES[issue.severity] ?? SEVERITY_STYLES.info;
}

export default function WritingPage() {
  const [text, setText] = useState("");
  // Le texte figé au moment de l'analyse : si l'utilisateur continue à taper,
  // les extraits ne correspondraient plus et le surlignage sauterait.
  const [analysedText, setAnalysedText] = useState("");
  const [analysis, setAnalysis] = useState<WritingAnalysis | null>(null);
  const [activeIndex, setActiveIndex] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const tooShort = text.trim().length < MIN_CHARS;

  async function analyse() {
    setBusy(true);
    setError("");
    setActiveIndex(null);
    try {
      const result = await api.analyseWriting(text.trim());
      setAnalysis(result);
      setAnalysedText(text.trim());
    } catch (err) {
      setError(
        err instanceof ApiError ? err.detail : "L'analyse a échoué. Réessaie.",
      );
    } finally {
      setBusy(false);
    }
  }

  function reset() {
    setAnalysis(null);
    setAnalysedText("");
    setActiveIndex(null);
    setError("");
  }

  // Découpe la copie autour de l'extrait sélectionné pour le surligner.
  const segments = useMemo(() => {
    if (!analysis || activeIndex === null) return null;
    const quote = analysis.issues[activeIndex]?.quote;
    if (!quote) return null;
    const start = analysedText.indexOf(quote);
    if (start === -1) return null;
    return {
      before: analysedText.slice(0, start),
      match: quote,
      after: analysedText.slice(start + quote.length),
      style: severityOf(analysis.issues[activeIndex]).mark,
    };
  }, [analysis, activeIndex, analysedText]);

  return (
    <div className="flex flex-col gap-5">
      <header>
        <h1 className="text-2xl font-extrabold tracking-tight">
          Audit d&apos;écrit ✍️
        </h1>
        <p className="mt-1 text-sm font-medium text-slate-400">
          Synthèse, écriture personnelle, cas pratique — colle ton texte et
          vois précisément quoi retravailler.
        </p>
      </header>

      {/* ── Saisie ─────────────────────────────────────────────────────── */}
      {!analysis && (
        <Card>
          <CardContent className="flex flex-col gap-3">
            <CardTitle>Ton texte</CardTitle>
            <Textarea
              rows={14}
              placeholder="Colle ici ta synthèse ou ton écriture personnelle…"
              value={text}
              onChange={(e) => setText(e.target.value)}
              className="min-h-[280px] font-medium leading-relaxed"
            />
            <div className="flex items-center justify-between">
              <span
                className={cn(
                  "text-xs font-semibold",
                  tooShort ? "text-slate-400" : "text-emerald-600",
                )}
              >
                {text.trim().length} caractères
                {tooShort && ` · ${MIN_CHARS} minimum`}
              </span>
              <Button onClick={analyse} disabled={busy || tooShort}>
                {busy ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Analyse en cours…
                  </>
                ) : (
                  <>
                    <Sparkles className="h-4 w-4" />
                    Analyser
                  </>
                )}
              </Button>
            </div>
            {error && (
              <p className="rounded-xl bg-rose-50 px-3 py-2 text-sm font-medium text-rose-600">
                {error}
              </p>
            )}
          </CardContent>
        </Card>
      )}

      {/* ── Résultats ──────────────────────────────────────────────────── */}
      {analysis && (
        <>
          {/* Score + note de mode simulé */}
          <Card>
            <CardContent>
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1">
                  <p className="text-xs font-bold uppercase tracking-wider text-indigo-500">
                    Estimation
                  </p>
                  <h2 className="mt-0.5 text-lg font-extrabold text-slate-800">
                    {analysis.issues.length} point
                    {analysis.issues.length > 1 ? "s" : ""} à retravailler
                  </h2>
                  {analysis.score !== null && (
                    <Progress
                      value={analysis.score / 20}
                      className="mt-3 h-2.5"
                    />
                  )}
                </div>
                {analysis.score !== null && (
                  <div className="rounded-2xl bg-indigo-50 px-4 py-2 text-center">
                    <p className="text-2xl font-black leading-none text-indigo-600">
                      {analysis.score}
                    </p>
                    <p className="text-[10px] font-bold uppercase text-indigo-400">
                      / 20
                    </p>
                  </div>
                )}
              </div>
              {analysis.mocked && (
                <Badge tone="amber" className="mt-3">
                  mode simulé — ajoute une clé OpenRouter pour une vraie analyse
                </Badge>
              )}
            </CardContent>
          </Card>

          {/* La copie, avec surlignage de l'extrait sélectionné */}
          <Card>
            <CardContent>
              <div className="mb-3 flex items-center justify-between">
                <CardTitle className="text-base">Ta copie</CardTitle>
                {activeIndex !== null && (
                  <button
                    onClick={() => setActiveIndex(null)}
                    className="text-xs font-semibold text-slate-400 hover:text-indigo-600"
                  >
                    Retirer le surlignage
                  </button>
                )}
              </div>
              <p className="max-h-72 overflow-y-auto whitespace-pre-wrap rounded-2xl bg-slate-50/70 px-4 py-3 text-sm font-medium leading-relaxed text-slate-700">
                {segments ? (
                  <>
                    {segments.before}
                    <mark
                      className={cn("rounded px-0.5 text-slate-900", segments.style)}
                    >
                      {segments.match}
                    </mark>
                    {segments.after}
                  </>
                ) : (
                  analysedText
                )}
              </p>
              {activeIndex !== null && !segments && (
                <p className="mt-2 text-xs font-medium text-slate-400">
                  Ce problème est global : il ne cible pas un passage précis.
                </p>
              )}
            </CardContent>
          </Card>

          {/* Les problèmes, cliquables */}
          <section>
            <h3 className="mb-3 px-1 text-sm font-bold uppercase tracking-wider text-slate-400">
              À retravailler
            </h3>
            <div className="flex flex-col gap-2.5">
              {analysis.issues.length === 0 && (
                <p className="px-1 text-sm font-medium text-slate-400">
                  Aucun problème détecté. C&apos;est rare — relis quand même.
                </p>
              )}
              {analysis.issues.map((issue, index) => {
                const meta = ISSUE_META[issue.type] ?? {
                  label: issue.type,
                  icon: AlertTriangle,
                };
                const style = severityOf(issue);
                const Icon = meta.icon;
                const active = activeIndex === index;
                return (
                  <button
                    key={index}
                    onClick={() => setActiveIndex(active ? null : index)}
                    className={cn(
                      "rounded-tile border bg-white px-4 py-3.5 text-left shadow-soft transition",
                      active ? style.ring : "border-slate-100 hover:bg-slate-50",
                    )}
                  >
                    <div className="flex items-center gap-3">
                      <span className="icon-tile">
                        <Icon className="h-5 w-5" />
                      </span>
                      <span className="flex-1">
                        <span className="block font-bold text-slate-800">
                          {issue.label}
                        </span>
                        <span className="block text-sm font-medium text-slate-400">
                          {meta.label}
                        </span>
                      </span>
                      <Badge tone={style.tone}>{issue.severity}</Badge>
                    </div>

                    {active && (
                      <div className="mt-3 border-t border-slate-100 pt-3">
                        {issue.detail && (
                          <p className="text-sm font-medium text-slate-600">
                            {issue.detail}
                          </p>
                        )}
                        {issue.suggestion && (
                          <p className="mt-2 rounded-xl bg-indigo-50/60 px-3 py-2 text-sm font-medium text-indigo-700">
                            💡 {issue.suggestion}
                          </p>
                        )}
                        {issue.quote && (
                          <p className="mt-2 text-xs font-medium italic text-slate-400">
                            Passage surligné dans ta copie ci-dessus.
                          </p>
                        )}
                      </div>
                    )}
                  </button>
                );
              })}
            </div>
          </section>

          {/* Points forts + priorité */}
          {analysis.strengths.length > 0 && (
            <Card>
              <CardContent>
                <CardTitle className="mb-3 flex items-center gap-2 text-base">
                  <CheckCircle2 className="h-5 w-5 text-emerald-500" />
                  Ce qui fonctionne déjà
                </CardTitle>
                <ul className="flex flex-col gap-1.5">
                  {analysis.strengths.map((strength, index) => (
                    <li
                      key={index}
                      className="text-sm font-medium text-slate-600"
                    >
                      • {strength}
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          )}

          {analysis.next_step && (
            <Card className="border-indigo-100 bg-indigo-50/40">
              <CardContent>
                <CardTitle className="mb-1.5 flex items-center gap-2 text-base">
                  <Target className="h-5 w-5 text-indigo-500" />
                  Ta priorité
                </CardTitle>
                <p className="text-sm font-medium leading-relaxed text-slate-700">
                  {analysis.next_step}
                </p>
              </CardContent>
            </Card>
          )}

          <Button variant="soft" onClick={reset}>
            Analyser un autre texte
          </Button>
        </>
      )}
    </div>
  );
}
