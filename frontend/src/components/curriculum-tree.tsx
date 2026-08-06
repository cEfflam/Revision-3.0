"use client";

/**
 * Éditeur du référentiel : Matière > Thème > Notion.
 *
 * C'est TOI qui écris ce squelette, l'IA ne le fabrique pas. Le programme du
 * BTS est fixe et connu ; le déduire de titres de PDF produit des doublons et
 * une granularité incohérente.
 *
 * Le déplacement se fait par sélection puis destination, pas par glisser-
 * déposer : sur un arbre à plusieurs niveaux, le glisser-déposer est pénible
 * au doigt et ambigu (dépose-t-on DANS le thème ou À CÔTÉ ?). Deux clics
 * explicites valent mieux qu'un geste approximatif.
 */

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
  ChevronDown,
  ChevronRight,
  CornerDownRight,
  FileText,
  FolderPlus,
  Layers,
  Loader2,
  Lock,
  Move,
  Pencil,
  Plus,
  Trash2,
  X,
} from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { cn, pct, STATUS_STYLES } from "@/lib/utils";
import type { CurriculumNode, CurriculumRead } from "@/types/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

interface Props {
  subject: string;
  onSelectNode?: (node: CurriculumNode) => void;
  selectedNodeId?: number | null;
}

export function CurriculumTree({ subject, onSelectNode, selectedNodeId }: Props) {
  const [data, setData] = useState<CurriculumRead | null>(null);
  const [expanded, setExpanded] = useState<Set<number>>(new Set());
  const [creatingIn, setCreatingIn] = useState<number | "root" | null>(null);
  const [draftTitle, setDraftTitle] = useState("");
  const [renamingId, setRenamingId] = useState<number | null>(null);
  const [moving, setMoving] = useState<CurriculumNode | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      const result = await api.curriculum(subject);
      setData(result);
      // Les thèmes contenant des notions s'ouvrent d'eux-mêmes : un arbre
      // entièrement replié oblige à cliquer partout pour retrouver son travail.
      setExpanded(
        (previous) =>
          new Set([
            ...previous,
            ...result.themes.filter((t) => t.children.length).map((t) => t.id),
          ]),
      );
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Chargement impossible.");
    }
  }, [subject]);

  useEffect(() => {
    load();
  }, [load]);

  function toggle(id: number) {
    setExpanded((previous) => {
      const next = new Set(previous);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  async function create(parentId: number | null, kind: "topic" | "concept") {
    const title = draftTitle.trim();
    if (!title) return;
    setBusy(true);
    setError("");
    try {
      await api.createNode({
        title,
        kind,
        subject,
        parent_id: parentId,
      });
      setDraftTitle("");
      setCreatingIn(null);
      if (parentId) setExpanded((p) => new Set([...p, parentId]));
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Création impossible.");
    } finally {
      setBusy(false);
    }
  }

  async function rename(node: CurriculumNode) {
    const title = draftTitle.trim();
    if (!title || title === node.title) {
      setRenamingId(null);
      return;
    }
    setBusy(true);
    try {
      await api.updateNode(node.id, { title });
      setRenamingId(null);
      setDraftTitle("");
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Renommage impossible.");
    } finally {
      setBusy(false);
    }
  }

  async function moveTo(parentId: number | null) {
    if (!moving) return;
    setBusy(true);
    setError("");
    try {
      await api.updateNode(moving.id, { parent_id: parentId });
      setMoving(null);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Déplacement impossible.");
    } finally {
      setBusy(false);
    }
  }

  async function remove(node: CurriculumNode) {
    const warning = node.children.length
      ? `Supprimer « ${node.title} » ET ses ${node.children.length} notion(s) ?`
      : `Supprimer « ${node.title} » ?`;
    if (!window.confirm(warning)) return;
    setBusy(true);
    try {
      await api.deleteNode(node.id);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Suppression impossible.");
    } finally {
      setBusy(false);
    }
  }

  if (error && !data) {
    return (
      <p className="rounded-xl bg-rose-50 px-4 py-3 text-sm font-medium text-rose-600">
        {error}
      </p>
    );
  }
  if (!data) {
    return (
      <div className="flex justify-center py-10">
        <Loader2 className="h-6 w-6 animate-spin text-indigo-500" />
      </div>
    );
  }

  function NodeRow({ node, depth }: { node: CurriculumNode; depth: number }) {
    const style = STATUS_STYLES[node.status] ?? STATUS_STYLES.available;
    const isTheme = node.kind !== "concept";
    const open = expanded.has(node.id);
    const selected = selectedNodeId === node.id;
    const renaming = renamingId === node.id;

    return (
      <div>
        <div
          className={cn(
            "group flex items-center gap-2 rounded-xl px-2 py-2 transition",
            selected ? "bg-indigo-50" : "hover:bg-slate-50",
            moving?.id === node.id && "opacity-40",
          )}
          style={{ paddingLeft: `${depth * 18 + 8}px` }}
        >
          {isTheme ? (
            <button
              onClick={() => toggle(node.id)}
              className="shrink-0 text-slate-400 hover:text-indigo-600"
            >
              {open ? (
                <ChevronDown className="h-4 w-4" />
              ) : (
                <ChevronRight className="h-4 w-4" />
              )}
            </button>
          ) : (
            <span className={cn("ml-1 h-2 w-2 shrink-0 rounded-full", style.dot)} />
          )}

          {renaming ? (
            <Input
              autoFocus
              value={draftTitle}
              onChange={(e) => setDraftTitle(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") rename(node);
                if (e.key === "Escape") setRenamingId(null);
              }}
              onBlur={() => rename(node)}
              className="h-8 flex-1 py-1 text-sm"
            />
          ) : (
            <button
              onClick={() => onSelectNode?.(node)}
              className="flex-1 text-left"
            >
              <span
                className={cn(
                  "text-sm",
                  isTheme ? "font-extrabold text-slate-800" : "font-semibold text-slate-700",
                )}
              >
                {node.title}
              </span>
              {!isTheme && (
                <span className="ml-2 text-xs font-medium text-slate-400">
                  {pct(node.mastery)}
                </span>
              )}
            </button>
          )}

          {node.status === "locked" && (
            <Lock className="h-3.5 w-3.5 shrink-0 text-slate-300" />
          )}
          {node.documents_count > 0 && (
            <Badge tone="slate" className="hidden sm:inline-flex">
              <FileText className="h-3 w-3" />
              {node.documents_count}
            </Badge>
          )}
          {node.cards_count > 0 && (
            <Badge tone="indigo" className="hidden sm:inline-flex">
              <Layers className="h-3 w-3" />
              {node.cards_count}
            </Badge>
          )}

          {/* Actions — visibles au survol sur desktop, toujours sur mobile */}
          <span className="flex shrink-0 gap-0.5 opacity-100 transition md:opacity-0 md:group-hover:opacity-100">
            {isTheme && (
              <button
                onClick={() => {
                  setCreatingIn(node.id);
                  setDraftTitle("");
                }}
                title="Ajouter une notion ici"
                className="rounded-lg p-1.5 text-slate-400 hover:bg-indigo-50 hover:text-indigo-600"
              >
                <Plus className="h-3.5 w-3.5" />
              </button>
            )}
            <button
              onClick={() => {
                setRenamingId(node.id);
                setDraftTitle(node.title);
              }}
              title="Renommer"
              className="rounded-lg p-1.5 text-slate-400 hover:bg-indigo-50 hover:text-indigo-600"
            >
              <Pencil className="h-3.5 w-3.5" />
            </button>
            <button
              onClick={() => setMoving(node)}
              title="Déplacer"
              className="rounded-lg p-1.5 text-slate-400 hover:bg-amber-50 hover:text-amber-600"
            >
              <Move className="h-3.5 w-3.5" />
            </button>
            <button
              onClick={() => remove(node)}
              title="Supprimer"
              className="rounded-lg p-1.5 text-slate-300 hover:bg-rose-50 hover:text-rose-500"
            >
              <Trash2 className="h-3.5 w-3.5" />
            </button>
          </span>
        </div>

        {/* Saisie d'une nouvelle notion dans ce thème */}
        {creatingIn === node.id && (
          <div
            className="flex items-center gap-2 py-1"
            style={{ paddingLeft: `${(depth + 1) * 18 + 8}px` }}
          >
            <CornerDownRight className="h-4 w-4 shrink-0 text-slate-300" />
            <Input
              autoFocus
              placeholder="Nom de la notion…"
              value={draftTitle}
              onChange={(e) => setDraftTitle(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") create(node.id, "concept");
                if (e.key === "Escape") setCreatingIn(null);
              }}
              className="h-8 flex-1 py-1 text-sm"
            />
            <Button size="sm" onClick={() => create(node.id, "concept")} disabled={busy}>
              Ajouter
            </Button>
            <button
              onClick={() => setCreatingIn(null)}
              className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        )}

        {open &&
          node.children.map((child) => (
            <NodeRow key={child.id} node={child} depth={depth + 1} />
          ))}
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      {/* Bandeau de déplacement : la destination se choisit au clic suivant */}
      {moving && (
        <div className="flex flex-wrap items-center gap-2 rounded-tile border border-amber-200 bg-amber-50 px-4 py-3">
          <Move className="h-4 w-4 shrink-0 text-amber-600" />
          <span className="flex-1 text-sm font-semibold text-amber-800">
            Où ranger « {moving.title} » ?
          </span>
          <div className="flex flex-wrap gap-1.5">
            {data.themes
              .filter((t) => t.id !== moving.id)
              .map((theme) => (
                <button
                  key={theme.id}
                  onClick={() => moveTo(theme.id)}
                  disabled={busy}
                  className="rounded-lg bg-white px-2.5 py-1 text-xs font-bold text-slate-700 shadow-soft hover:bg-indigo-50 hover:text-indigo-700"
                >
                  {theme.title}
                </button>
              ))}
            <button
              onClick={() => moveTo(null)}
              disabled={busy}
              className="rounded-lg bg-white px-2.5 py-1 text-xs font-bold text-slate-500 shadow-soft hover:bg-slate-100"
            >
              Sortir du thème
            </button>
            <button
              onClick={() => setMoving(null)}
              className="rounded-lg p-1 text-amber-600 hover:bg-amber-100"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        </div>
      )}

      {error && (
        <p className="rounded-xl bg-rose-50 px-3 py-2 text-sm font-medium text-rose-600">
          {error}
        </p>
      )}

      {/* ── L'arbre ────────────────────────────────────────────────────── */}
      <Card>
        <CardContent className="p-3 sm:p-4">
          <div className="mb-2 flex items-center justify-between px-1">
            <CardTitle className="text-base">Mon référentiel</CardTitle>
            <Button
              size="sm"
              variant="soft"
              onClick={() => {
                setCreatingIn("root");
                setDraftTitle("");
              }}
            >
              <FolderPlus className="h-4 w-4" />
              Nouveau thème
            </Button>
          </div>

          {creatingIn === "root" && (
            <div className="mb-2 flex items-center gap-2 px-1">
              <Input
                autoFocus
                placeholder="Nom du thème (ex. : Algèbre de Boole)…"
                value={draftTitle}
                onChange={(e) => setDraftTitle(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") create(null, "topic");
                  if (e.key === "Escape") setCreatingIn(null);
                }}
                className="h-9 flex-1 py-1 text-sm"
              />
              <Button size="sm" onClick={() => create(null, "topic")} disabled={busy}>
                Créer
              </Button>
              <button
                onClick={() => setCreatingIn(null)}
                className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          )}

          {data.themes.length === 0 && creatingIn !== "root" && (
            <p className="px-2 py-6 text-center text-sm font-medium text-slate-400">
              Aucun thème. Crée le premier — c&apos;est toi qui écris ce
              squelette, l&apos;IA viendra y ranger tes cours.
            </p>
          )}

          {data.themes.map((theme) => (
            <NodeRow key={theme.id} node={theme} depth={0} />
          ))}
        </CardContent>
      </Card>

      {/* ── Les notions sans thème ─────────────────────────────────────── */}
      {data.orphans.length > 0 && (
        <Card className="border-amber-100 bg-amber-50/30">
          <CardContent className="p-3 sm:p-4">
            <CardTitle className="mb-1 flex items-center gap-2 px-1 text-base">
              <CornerDownRight className="h-5 w-5 text-amber-500" />
              À classer ({data.orphans.length})
            </CardTitle>
            <p className="mb-2 px-1 text-xs font-medium text-slate-500">
              Notions créées depuis tes documents, pas encore rangées sous un
              thème. Un trou visible vaut mieux qu&apos;un trou silencieux.
            </p>
            {data.orphans.map((orphan) => (
              <NodeRow key={orphan.id} node={orphan} depth={0} />
            ))}
          </CardContent>
        </Card>
      )}

      <p className="px-1 text-xs font-medium text-slate-400">
        Besoin d&apos;un exemple ?{" "}
        <Link href="/brain" className="font-bold text-indigo-600 hover:underline">
          Importe un cours
        </Link>{" "}
        puis rattache-le : les notions détectées atterriront ici.
      </p>
    </div>
  );
}
