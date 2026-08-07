"use client";

/**
 * Compteur d'attente pour les appels IA longs.
 *
 * Les tâches de raisonnement (exercice SQL, relecture d'algorithme, correction
 * de copie) prennent entre 30 et 90 secondes : le modèle « réfléchit » avant
 * d'écrire, et cette réflexion se paie en temps. Un spinner sans repère donne
 * exactement la même image qu'une page plantée — mesuré sur soi-même : on
 * abandonne au bout de 30 secondes en croyant que c'est cassé.
 *
 * Afficher le temps écoulé et l'ordre de grandeur attendu suffit à changer
 * l'attente en patience.
 */

import { useEffect, useState } from "react";
import { Loader2 } from "lucide-react";

export function Waiting({
  active,
  label,
  typicalSeconds = 60,
}: {
  active: boolean;
  label: string;
  /** Durée habituelle, annoncée pour situer l'attente. */
  typicalSeconds?: number;
}) {
  const [seconds, setSeconds] = useState(0);

  useEffect(() => {
    if (!active) {
      setSeconds(0);
      return;
    }
    const started = Date.now();
    const timer = setInterval(
      () => setSeconds(Math.round((Date.now() - started) / 1000)),
      1000,
    );
    return () => clearInterval(timer);
  }, [active]);

  if (!active) return null;

  return (
    <div className="mt-3 flex items-center gap-2 rounded-xl bg-indigo-50/60 px-3 py-2.5 text-sm font-medium text-indigo-700">
      <Loader2 className="h-4 w-4 shrink-0 animate-spin" />
      <span className="flex-1">
        {label}
        {seconds > 8 && (
          <span className="ml-1 text-indigo-400">
            {/* Le seuil de 8 s évite de faire clignoter un chrono sur les
                appels courts, qui n'en ont pas besoin. */}
            · {seconds} s
          </span>
        )}
        {seconds > 25 && (
          <span className="mt-0.5 block text-xs font-normal text-indigo-500">
            Le modèle déroule son raisonnement avant de répondre — compte
            environ {typicalSeconds} s. Ne recharge pas la page.
          </span>
        )}
      </span>
    </div>
  );
}
