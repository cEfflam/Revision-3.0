"use client";

/**
 * Contexte utilisateur + garde d'authentification.
 *
 * Ce provider enveloppe toute la zone connectée `(app)` :
 *   1. au montage, il charge le profil via /auth/me ;
 *   2. pas de jeton ou jeton invalide → redirection /login ;
 *   3. onboarding non terminé → redirection /onboarding ;
 *   4. sinon, il expose `user` à toutes les pages via `useUser()`.
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import { usePathname, useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { getToken } from "@/lib/auth";
import type { User } from "@/types/api";

interface UserContextValue {
  user: User | null;
  refresh: () => Promise<void>;
}

const UserContext = createContext<UserContextValue>({
  user: null,
  refresh: async () => {},
});

export function useUser() {
  return useContext(UserContext);
}

export function UserProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const router = useRouter();
  const pathname = usePathname();

  const refresh = useCallback(async () => {
    const me = await api.me();
    setUser(me);
  }, []);

  useEffect(() => {
    if (!getToken()) {
      router.replace("/login");
      return;
    }
    api
      .me()
      .then((me) => {
        setUser(me);
        if (!me.onboarding_completed && pathname !== "/onboarding") {
          router.replace("/onboarding");
        }
      })
      // Le client API gère déjà la redirection sur 401.
      .catch(() => {})
      .finally(() => setLoading(false));
    // volontairement sans `pathname` : la garde ne rejoue qu'au montage,
    // pas à chaque navigation interne.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [router]);

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-indigo-200 border-t-indigo-600" />
      </div>
    );
  }

  return (
    <UserContext.Provider value={{ user, refresh }}>
      {children}
    </UserContext.Provider>
  );
}
