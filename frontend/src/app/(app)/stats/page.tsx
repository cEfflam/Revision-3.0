"use client";

/**
 * Statistiques + journal du soir.
 * Pas une note globale : une carte des compétences par matière — c'est elle
 * qui dit où investir la prochaine heure de travail.
 */

import { useEffect, useState } from "react";
import { BookOpen, Loader2, NotebookPen } from "lucide-react";
import { api } from "@/lib/api";
import { pct, SUBJECT_LABELS } from "@/lib/utils";
import type { HeatmapPoint, StatsRead } from "@/types/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Heatmap } from "@/components/heatmap";

export default function StatsPage() {
  const [stats, setStats] = useState<StatsRead | null>(null);
  const [heatmap, setHeatmap] = useState<HeatmapPoint[]>([]);
  const [journal, setJournal] = useState("");
  const [journalBusy, setJournalBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([api.stats(), api.heatmap(365)])
      .then(([s, h]) => {
        setStats(s);
        setHeatmap(h);
      })
      .catch((e) => setError(e.message));
  }, []);

  async function generateJournal() {
    setJournalBusy(true);
    try {
      const result = await api.journal();
      setJournal(result.journal);
    } catch {
      setJournal("Le journal n'a pas pu être généré.");
    } finally {
      setJournalBusy(false);
    }
  }

  if (error) {
    return (
      <p className="rounded-xl bg-rose-50 px-4 py-3 text-sm font-medium text-rose-600">
        {error}
      </p>
    );
  }
  if (!stats) {
    return (
      <div className="flex justify-center pt-20">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-indigo-200 border-t-indigo-600" />
      </div>
    );
  }

  const tiles = [
    { label: "Cartes", value: stats.total_cards },
    { label: "Acquises", value: stats.mastered_cards },
    { label: "Révisions", value: stats.reviews_total },
    { label: "Réussite", value: pct(stats.accuracy) },
  ];

  return (
    <div className="flex flex-col gap-5">
      <header>
        <h1 className="text-2xl font-extrabold tracking-tight">Statistiques</h1>
        <p className="mt-1 text-sm font-medium text-slate-400">
          {stats.nodes_mastered}/{stats.nodes_total} notions maîtrisées ·{" "}
          {stats.documents_total} documents dans le Brain
        </p>
      </header>

      {/* ── Tuiles ─────────────────────────────────────────────────────── */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {tiles.map((tile) => (
          <Card key={tile.label}>
            <CardContent className="p-4 text-center">
              <p className="text-2xl font-black text-indigo-600">{tile.value}</p>
              <p className="text-xs font-bold uppercase tracking-wider text-slate-400">
                {tile.label}
              </p>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* ── Carte des compétences ──────────────────────────────────────── */}
      <Card>
        <CardContent>
          <CardTitle className="mb-4 flex items-center gap-2 text-base">
            <BookOpen className="h-5 w-5 text-indigo-500" />
            Carte des compétences
          </CardTitle>
          <div className="flex flex-col gap-3">
            {Object.entries(stats.subject_mastery)
              .sort(([, a], [, b]) => b - a)
              .map(([subject, mastery]) => (
                <div key={subject}>
                  <div className="mb-1 flex justify-between text-sm">
                    <span className="font-semibold text-slate-700">
                      {SUBJECT_LABELS[subject] ?? subject}
                    </span>
                    <span className="font-bold text-indigo-600">
                      {pct(mastery)}
                    </span>
                  </div>
                  <Progress value={mastery} className="h-2.5" />
                </div>
              ))}
            {Object.keys(stats.subject_mastery).length === 0 && (
              <p className="text-sm font-medium text-slate-400">
                Le graphe est vide — passe par l&apos;onboarding.
              </p>
            )}
          </div>
        </CardContent>
      </Card>

      {/* ── Année complète ─────────────────────────────────────────────── */}
      <Card>
        <CardContent>
          <CardTitle className="mb-4 text-base">Mon année</CardTitle>
          <Heatmap points={heatmap} days={365} />
        </CardContent>
      </Card>

      {/* ── Journal du soir ────────────────────────────────────────────── */}
      <Card>
        <CardContent>
          <div className="mb-3 flex items-center justify-between">
            <CardTitle className="flex items-center gap-2 text-base">
              <NotebookPen className="h-5 w-5 text-indigo-500" />
              Journal du soir
            </CardTitle>
            <Button variant="soft" size="sm" onClick={generateJournal} disabled={journalBusy}>
              {journalBusy ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                "Générer"
              )}
            </Button>
          </div>
          {journal ? (
            <p className="whitespace-pre-wrap rounded-2xl bg-indigo-50/60 px-4 py-3 text-sm font-medium leading-relaxed text-slate-700">
              {journal}
            </p>
          ) : (
            <p className="text-sm font-medium text-slate-400">
              En fin de journée, l&apos;IA résume ce que tu as réellement appris
              — et ce qu&apos;il faudra reprendre demain.
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
