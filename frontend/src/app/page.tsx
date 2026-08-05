"use client";

/**
 * Racine « / » : simple aiguillage.
 * Jeton présent → dashboard ; sinon → connexion. La vraie validation du jeton
 * est faite par le UserProvider de la zone (app).
 */

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { getToken } from "@/lib/auth";

export default function Home() {
  const router = useRouter();

  useEffect(() => {
    router.replace(getToken() ? "/dashboard" : "/login");
  }, [router]);

  return (
    <div className="flex min-h-screen items-center justify-center">
      <div className="h-8 w-8 animate-spin rounded-full border-4 border-indigo-200 border-t-indigo-600" />
    </div>
  );
}
