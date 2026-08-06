"use client";

/**
 * Liste des matières — « je veux bosser les maths maintenant ».
 *
 * Le dashboard décide à ta place, ce qui est bien pour la routine. Cet écran
 * fait l'inverse : tu choisis ton angle d'attaque. Les matières sont triées
 * par maîtrise croissante — la plus fragile en premier, parce que c'est celle
 * qui rapporte le plus de points.
 */

import { useEffect, useState } from "react";
import Link from "next/link";
import { AlertTriangle, ChevronRight, FileText, Layers } from "lucide-react";
import { api } from "@/lib/api";
import { pct } from "@/lib/utils";
import type { SubjectSummary } from "@/types/api";
import { Card, CardContent } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";

export default function SubjectsPage() {
  const [subjects, setSubjects] = useState<SubjectSummary[] | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api
      .subjects()
      .then(setSubjects)
      .catch((e) => setError(e.message));
  }, []);

  if (error) {
    return (
      <p className="rounded-xl bg-rose-50 px-4 py-3 text-sm font-medium text-rose-600">
        {error}
      </p>
    );
  }
  if (!subjects) {
    return (
      <div className="flex justify-center pt-20">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-indigo-200 border-t-indigo-600" />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-5">
      <header>
        <h1 className="text-2xl font-extrabold tracking-tight">Mes matières</h1>
        <p className="mt-1 text-sm font-medium text-slate-400">
          Choisis ce que tu veux travailler. Les plus fragiles sont en tête.
        </p>
      </header>

      {subjects.length === 0 && (
        <Card>
          <CardContent className="py-10 text-center">
            <p className="text-sm font-medium text-slate-400">
              Aucune matière. Passe par l&apos;onboarding pour créer ton graphe
              de compétences.
            </p>
          </CardContent>
        </Card>
      )}

      <div className="flex flex-col gap-2.5">
        {subjects.map((subject) => (
          <Link
            key={subject.subject}
            href={`/subjects/${subject.subject}`}
            className="action-row"
          >
            <span className="min-w-0 flex-1">
              <span className="mb-1 flex items-center gap-2">
                <span className="font-bold text-slate-800">{subject.label}</span>
                {subject.nodes_critical > 0 && (
                  <Badge tone="rose">
                    <AlertTriangle className="h-3 w-3" />
                    {subject.nodes_critical}
                  </Badge>
                )}
                {subject.cards_due > 0 && (
                  <Badge tone="indigo">{subject.cards_due} à réviser</Badge>
                )}
              </span>
              <Progress
                value={subject.mastery}
                className="h-2"
                barClassName={
                  subject.mastery < 0.3
                    ? "bg-rose-400"
                    : subject.mastery >= 0.85
                      ? "bg-emerald-500"
                      : undefined
                }
              />
              <span className="mt-1.5 flex items-center gap-3 text-xs font-medium text-slate-400">
                <span className="font-bold text-indigo-600">
                  {pct(subject.mastery)}
                </span>
                <span className="flex items-center gap-1">
                  <Layers className="h-3 w-3" />
                  {subject.nodes_mastered}/{subject.nodes_total}
                </span>
                <span className="flex items-center gap-1">
                  <FileText className="h-3 w-3" />
                  {subject.documents_total}
                </span>
              </span>
            </span>
            <ChevronRight className="h-5 w-5 shrink-0 text-slate-300" />
          </Link>
        ))}
      </div>
    </div>
  );
}
