"use client";

/**
 * Navigation : barre latérale sur desktop, barre d'onglets en bas sur mobile.
 * Les mêmes entrées alimentent les deux rendus.
 */

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  BarChart3,
  Brain,
  Flame,
  Home,
  Layers,
  LogOut,
  MessageCircle,
  Network,
  PenLine,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { clearToken } from "@/lib/auth";
import { useUser } from "@/components/layout/user-context";

// `short` sert à la barre d'onglets mobile, où la place est comptée.
const NAV_ITEMS = [
  { href: "/dashboard", label: "Aujourd'hui", short: "Accueil", icon: Home },
  { href: "/review", label: "Réviser", short: "Réviser", icon: Layers },
  { href: "/brain", label: "Brain", short: "Brain", icon: Brain },
  { href: "/writing", label: "Audit d'écrit", short: "Écrits", icon: PenLine },
  { href: "/chat", label: "Coach IA", short: "Coach", icon: MessageCircle },
  { href: "/roadmap", label: "Skill Tree", short: "Skills", icon: Network },
  { href: "/stats", label: "Stats", short: "Stats", icon: BarChart3 },
];

export function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const { user } = useUser();

  function logout() {
    clearToken();
    router.replace("/login");
  }

  return (
    <>
      {/* ── Desktop : colonne fixe ─────────────────────────────────────── */}
      <aside className="fixed inset-y-0 left-0 z-20 hidden w-60 flex-col border-r border-slate-100 bg-white/70 px-4 py-6 backdrop-blur-md md:flex">
        <Link href="/dashboard" className="mb-8 flex items-center gap-2 px-2">
          <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-indigo-600 text-sm font-black text-white">
            R
          </span>
          <span className="text-lg font-extrabold tracking-tight">REVISIO</span>
        </Link>

        <nav className="flex flex-1 flex-col gap-1">
          {NAV_ITEMS.map(({ href, label, icon: Icon }) => {
            const active = pathname.startsWith(href);
            return (
              <Link
                key={href}
                href={href}
                className={cn(
                  "flex items-center gap-3 rounded-2xl px-3 py-2.5 text-sm font-semibold transition",
                  active
                    ? "bg-indigo-50 text-indigo-700"
                    : "text-slate-500 hover:bg-slate-50 hover:text-slate-700",
                )}
              >
                <Icon className="h-[18px] w-[18px]" />
                {label}
              </Link>
            );
          })}
        </nav>

        <div className="mt-4 border-t border-slate-100 pt-4">
          {user && (
            <div className="mb-3 flex items-center gap-2 px-2">
              <Flame className="h-4 w-4 text-amber-500" />
              <span className="text-xs font-semibold text-slate-500">
                {user.streak_current} jour{user.streak_current > 1 ? "s" : ""} de
                suite
              </span>
            </div>
          )}
          <button
            onClick={logout}
            className="flex w-full items-center gap-3 rounded-2xl px-3 py-2.5 text-sm font-semibold text-slate-400 transition hover:bg-rose-50 hover:text-rose-600"
          >
            <LogOut className="h-[18px] w-[18px]" />
            Déconnexion
          </button>
        </div>
      </aside>

      {/* ── Mobile : onglets en bas ────────────────────────────────────── */}
      <nav className="fixed inset-x-0 bottom-0 z-20 flex justify-around border-t border-slate-100 bg-white/90 px-1 py-2 backdrop-blur-md md:hidden">
        {NAV_ITEMS.map(({ href, short, icon: Icon }) => {
          const active = pathname.startsWith(href);
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                "flex flex-1 flex-col items-center gap-0.5 rounded-xl px-0.5 py-1 text-[9px] font-semibold",
                active ? "text-indigo-600" : "text-slate-400",
              )}
            >
              <Icon className="h-5 w-5" />
              {short}
            </Link>
          );
        })}
      </nav>
    </>
  );
}
