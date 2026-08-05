"use client";

/**
 * Onboarding en trois blocs : l'objectif, le niveau déclaré, le temps dispo.
 * Une seule requête à la validation — le backend crée l'objectif ET instancie
 * le graphe de compétences BTS SIO calibré sur les curseurs.
 */

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { api, ApiError } from "@/lib/api";
import { SUBJECT_LABELS } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Input, Select } from "@/components/ui/input";
import { Card, CardContent, CardTitle } from "@/components/ui/card";
import { useUser } from "@/components/layout/user-context";

const ASSESSED_SUBJECTS = [
  "dev",
  "sql",
  "network",
  "security",
  "math",
  "cejm",
  "cge",
  "english",
];

const GOAL_KINDS = [
  { value: "diploma", label: "Diplôme (BTS, licence…)" },
  { value: "certification", label: "Certification (AWS, TOEIC…)" },
  { value: "career", label: "Objectif de carrière (DevOps…)" },
  { value: "language", label: "Langue" },
  { value: "custom", label: "Autre" },
];

export default function OnboardingPage() {
  const router = useRouter();
  const { refresh } = useUser();

  const [title, setTitle] = useState("Réussir le BTS SIO (SLAM)");
  const [kind, setKind] = useState("diploma");
  const [targetDate, setTargetDate] = useState("");
  const [dailyMinutes, setDailyMinutes] = useState(30);
  const [levels, setLevels] = useState<Record<string, number>>(
    Object.fromEntries(ASSESSED_SUBJECTS.map((s) => [s, 30])),
  );
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError("");
    setBusy(true);
    try {
      await api.completeOnboarding({
        goal: { title, kind, target_date: targetDate || null },
        assessments: Object.entries(levels).map(([subject, level]) => ({
          subject,
          level,
        })),
        daily_minutes: dailyMinutes,
      });
      await refresh();
      router.replace("/dashboard");
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Erreur inattendue.");
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="flex flex-col gap-5">
      <header>
        <h1 className="text-2xl font-extrabold tracking-tight">
          Bienvenue 👋
        </h1>
        <p className="mt-1 text-sm font-medium text-slate-400">
          Trois questions, et l&apos;application saura quoi te faire travailler.
        </p>
      </header>

      {/* ── 1. L'objectif ─────────────────────────────────────────────── */}
      <Card>
        <CardContent className="flex flex-col gap-3">
          <CardTitle>🎯 Ton objectif principal</CardTitle>
          <Input
            required
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Ex. : avoir 16 au BTS SIO"
          />
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <Select value={kind} onChange={(e) => setKind(e.target.value)}>
              {GOAL_KINDS.map((k) => (
                <option key={k.value} value={k.value}>
                  {k.label}
                </option>
              ))}
            </Select>
            <Input
              type="date"
              value={targetDate}
              onChange={(e) => setTargetDate(e.target.value)}
              title="Date de l'épreuve ou de l'examen (optionnel)"
            />
          </div>
        </CardContent>
      </Card>

      {/* ── 2. Le niveau déclaré ──────────────────────────────────────── */}
      <Card>
        <CardContent className="flex flex-col gap-4">
          <CardTitle>📊 Ton niveau estimé</CardTitle>
          <p className="-mt-2 text-sm font-medium text-slate-400">
            Sois honnête : surestimer un niveau, c&apos;est se priver des
            révisions dont on a besoin.
          </p>
          {ASSESSED_SUBJECTS.map((subject) => (
            <div key={subject}>
              <div className="mb-1 flex justify-between text-sm">
                <span className="font-semibold text-slate-700">
                  {SUBJECT_LABELS[subject]}
                </span>
                <span className="font-bold text-indigo-600">
                  {levels[subject]} %
                </span>
              </div>
              <input
                type="range"
                min={0}
                max={100}
                step={5}
                value={levels[subject]}
                onChange={(e) =>
                  setLevels({ ...levels, [subject]: Number(e.target.value) })
                }
                className="w-full accent-indigo-600"
              />
            </div>
          ))}
        </CardContent>
      </Card>

      {/* ── 3. Le temps disponible ────────────────────────────────────── */}
      <Card>
        <CardContent className="flex flex-col gap-3">
          <CardTitle>⏱️ Temps disponible par jour</CardTitle>
          <div className="flex items-center gap-4">
            <input
              type="range"
              min={10}
              max={120}
              step={5}
              value={dailyMinutes}
              onChange={(e) => setDailyMinutes(Number(e.target.value))}
              className="flex-1 accent-indigo-600"
            />
            <span className="w-20 text-right text-lg font-extrabold text-indigo-600">
              {dailyMinutes} min
            </span>
          </div>
          <p className="text-sm font-medium text-slate-400">
            Mieux vaut 20 minutes tous les jours que 3 heures le dimanche : la
            répétition espacée ne fonctionne qu&apos;avec de la régularité.
          </p>
        </CardContent>
      </Card>

      {error && (
        <p className="rounded-xl bg-rose-50 px-3 py-2 text-sm font-medium text-rose-600">
          {error}
        </p>
      )}

      <Button type="submit" size="lg" disabled={busy}>
        {busy ? "Création de ton graphe de compétences…" : "C'est parti 🚀"}
      </Button>
    </form>
  );
}
