"use client";

import { useMemo } from "react";
import type { HeatmapPoint } from "@/types/api";
import { cn } from "@/lib/utils";

/**
 * Heatmap de régularité façon GitHub.
 *
 * Le backend n'envoie que les jours actifs ; les jours vides sont reconstruits
 * ici. Rendu en colonnes de 7 (une colonne = une semaine), du plus ancien au
 * plus récent.
 */
interface HeatmapProps {
  points: HeatmapPoint[];
  /** Nombre de jours affichés (arrondi à la semaine). */
  days?: number;
  className?: string;
}

function intensityClass(xp: number): string {
  if (xp <= 0) return "bg-slate-100";
  if (xp < 50) return "bg-indigo-200";
  if (xp < 150) return "bg-indigo-400";
  return "bg-indigo-600";
}

export function Heatmap({ points, days = 119, className }: HeatmapProps) {
  const weeks = useMemo(() => {
    const byDay = new Map(points.map((p) => [p.day, p]));
    const today = new Date();

    const cells: { day: string; xp: number; reviews: number }[] = [];
    for (let i = days - 1; i >= 0; i--) {
      const date = new Date(today);
      date.setDate(today.getDate() - i);
      const key = date.toISOString().slice(0, 10);
      const point = byDay.get(key);
      cells.push({ day: key, xp: point?.xp ?? 0, reviews: point?.reviews ?? 0 });
    }

    const columns: (typeof cells)[] = [];
    for (let i = 0; i < cells.length; i += 7) columns.push(cells.slice(i, i + 7));
    return columns;
  }, [points, days]);

  return (
    <div className={cn("flex gap-1 overflow-x-auto pb-1", className)}>
      {weeks.map((week, index) => (
        <div key={index} className="flex flex-col gap-1">
          {week.map((cell) => (
            <div
              key={cell.day}
              title={`${cell.day} — ${cell.reviews} révision(s), ${cell.xp} XP`}
              className={cn("h-3 w-3 rounded-[4px]", intensityClass(cell.xp))}
            />
          ))}
        </div>
      ))}
    </div>
  );
}
