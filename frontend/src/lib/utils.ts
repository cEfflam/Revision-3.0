import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

/** Fusionne des classes Tailwind sans conflits (`p-2` + `p-4` → `p-4`). */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/** 0.7342 → « 73 % » */
export function pct(value: number): string {
  return `${Math.round(value * 100)} %`;
}

/** Libellés français des matières (miroir de l'enum backend `Subject`). */
export const SUBJECT_LABELS: Record<string, string> = {
  dev: "Développement",
  sql: "SQL",
  network: "Réseau",
  security: "Cybersécurité",
  math: "Mathématiques",
  cejm: "CEJM",
  cge: "Culture générale",
  english: "Anglais",
  cloud: "Cloud",
  devops: "DevOps",
  other: "Autre",
};

/** Couleur de statut d'un nœud du graphe (miroir de `NodeStatus`). */
export const STATUS_STYLES: Record<string, { dot: string; label: string }> = {
  mastered: { dot: "bg-emerald-500", label: "Maîtrisé" },
  learning: { dot: "bg-amber-400", label: "En cours" },
  critical: { dot: "bg-rose-500", label: "Critique" },
  available: { dot: "bg-slate-300", label: "À découvrir" },
  locked: { dot: "bg-slate-200", label: "Verrouillé" },
};

/** Formatte un intervalle SRS en texte lisible. */
export function formatInterval(days: number): string {
  if (days < 1) {
    const minutes = Math.max(1, Math.round(days * 1440));
    return minutes < 60 ? `${minutes} min` : `${Math.round(minutes / 60)} h`;
  }
  if (days < 30) return `${Math.round(days)} j`;
  if (days < 365) return `${Math.round(days / 30)} mois`;
  return `${(days / 365).toFixed(1)} an(s)`;
}
