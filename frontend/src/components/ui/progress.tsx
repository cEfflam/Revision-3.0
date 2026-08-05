import { cn } from "@/lib/utils";

interface ProgressProps {
  /** Valeur entre 0 et 1. */
  value: number;
  className?: string;
  barClassName?: string;
}

export function Progress({ value, className, barClassName }: ProgressProps) {
  const clamped = Math.max(0, Math.min(1, value));
  return (
    <div
      className={cn("h-3 w-full overflow-hidden rounded-full bg-indigo-50", className)}
      role="progressbar"
      aria-valuenow={Math.round(clamped * 100)}
      aria-valuemin={0}
      aria-valuemax={100}
    >
      <div
        className={cn(
          "h-full rounded-full bg-indigo-600 transition-all duration-500",
          barClassName,
        )}
        style={{ width: `${clamped * 100}%` }}
      />
    </div>
  );
}
