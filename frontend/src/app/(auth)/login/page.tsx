"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { api, ApiError } from "@/lib/api";
import { setToken } from "@/lib/auth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent } from "@/components/ui/card";

export default function LoginPage() {
  const router = useRouter();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError("");
    setBusy(true);
    try {
      const token =
        mode === "login"
          ? await api.login(email, password)
          : await api.register(email, password, displayName);
      setToken(token.access_token);
      router.replace("/dashboard");
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Erreur inattendue.");
      setBusy(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <div className="w-full max-w-md">
        <div className="mb-8 text-center">
          <span className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-indigo-600 text-xl font-black text-white">
            R
          </span>
          <h1 className="text-2xl font-extrabold tracking-tight">REVISIO</h1>
          <p className="mt-1 text-sm font-medium text-slate-400">
            Ton OS d&apos;apprentissage personnel
          </p>
        </div>

        <Card>
          <CardContent>
            <form onSubmit={submit} className="flex flex-col gap-3">
              {mode === "register" && (
                <Input
                  placeholder="Ton prénom"
                  value={displayName}
                  onChange={(e) => setDisplayName(e.target.value)}
                  autoComplete="given-name"
                />
              )}
              <Input
                type="email"
                required
                placeholder="email@exemple.fr"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                autoComplete="email"
              />
              <Input
                type="password"
                required
                minLength={8}
                placeholder="Mot de passe (8 caractères min.)"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete={
                  mode === "login" ? "current-password" : "new-password"
                }
              />

              {error && (
                <p className="rounded-xl bg-rose-50 px-3 py-2 text-sm font-medium text-rose-600">
                  {error}
                </p>
              )}

              <Button type="submit" disabled={busy} className="mt-1">
                {busy
                  ? "…"
                  : mode === "login"
                    ? "Se connecter"
                    : "Créer mon compte"}
              </Button>
            </form>

            <button
              onClick={() => {
                setMode(mode === "login" ? "register" : "login");
                setError("");
              }}
              className="mt-4 w-full text-center text-sm font-semibold text-indigo-600 hover:text-indigo-500"
            >
              {mode === "login"
                ? "Pas encore de compte ? Inscris-toi"
                : "Déjà un compte ? Connecte-toi"}
            </button>
          </CardContent>
        </Card>

        <p className="mt-4 text-center text-xs font-medium text-slate-400">
          Compte de démo : demo@revisio.app / revisio123
        </p>
      </div>
    </div>
  );
}
