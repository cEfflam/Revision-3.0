"use client";

/**
 * Rattachement d'un document aux notions du graphe.
 *
 * Le problème résolu : sans ce panneau, importer trois fiches qui parlent
 * toutes d'« Algèbre de Boole » créerait trois notions distinctes, chacune
 * avec sa propre maîtrise. Le graphe deviendrait faux — et un graphe faux
 * oriente les révisions vers les mauvaises notions.
 *
 * Rien n'est appliqué automatiquement au-delà des cas certains : l'écran
 * PROPOSE, l'utilisateur décide. Trois verdicts, trois traitements :
 *   certain   — pré-coché, rattachement à une notion existante
 *   suggested — décoché, ressemblance probable à confirmer
 *   new       — décoché, création d'une notion avec sa matière devinée
 */

import { useCallback, useEffect, useState } from "react";
import { CheckCircle2, HelpCircle, Loader2, PlusCircle, X } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { cn, SUBJECT_LABELS } from "@/lib/utils";
import type { DocumentMapping, NodeProposal } from "@/types/api";
import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";

const VERDICT_META: Record<
  string,
  { label: string; tone: "emerald" | "amber" | "indigo"; icon: typeof CheckCircle2 }
> = {
  certain: { label: "déjà au graphe", tone: "emerald", icon: CheckCircle2 },
  suggested: { label: "à confirmer", tone: "amber", icon: HelpCircle },
  new: { label: "nouvelle", tone: "indigo", icon: PlusCircle },
};

interface Row extends NodeProposal {
  subject: string;
}

export function DocumentMappingPanel({
  documentId,
  onClose,
  onApplied,
}: {
  documentId: number;
  onClose: () => void;
  onApplied: (message: string) => void;
}) {
  const [mapping, setMapping] = useState<DocumentMapping | null>(null);
  const [rows, setRows] = useState<Row[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      const result = await api.mapDocument(documentId);
      setMapping(result);
      setRows(
        result.proposals.map((p) => ({ ...p, subject: p.suggested_subject })),
      );
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Analyse impossible.");
    }
  }, [documentId]);

  useEffect(() => {
    load();
  }, [load]);

  function toggle(index: number) {
    setRows((list) =>
      list.map((r, i) => (i === index ? { ...r, selected: !r.selected } : r)),
    );
  }

  async function apply() {
    setBusy(true);
    setError("");
    try {
      const decisions = rows
        .filter((r) => r.selected)
        .map((r) => ({
          title: r.title,
          node_id: r.matched_node_id,
          subject: r.subject,
          create: r.matched_node_id === null,
        }));
      const result = await api.applyMapping(documentId, decisions);
      onApplied(result.message);
      onClose();
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Enregistrement impossible.");
    } finally {
      setBusy(false);
    }
  }

  const selected = rows.filter((r) => r.selected).length;

  return (
    <div className="rounded-tile border border-indigo-100 bg-indigo-50/30 p-4">
      <div className="mb-3 flex items-start justify-between gap-3">
        <div>
          <p className="font-bold text-slate-800">Notions de ce document</p>
          <p className="text-sm font-medium text-slate-500">
            {mapping?.message ?? "Analyse des titres de section…"}
          </p>
        </div>
        <button
          onClick={onClose}
          className="rounded-lg p-1 text-slate-400 hover:bg-white hover:text-slate-600"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      {error && (
        <p className="mb-3 rounded-xl bg-rose-50 px-3 py-2 text-sm font-medium text-rose-600">
          {error}
        </p>
      )}

      {!mapping ? (
        <Loader2 className="h-5 w-5 animate-spin text-indigo-500" />
      ) : rows.length === 0 ? (
        <p className="text-sm font-medium text-slate-400">
          Aucune notion détectée automatiquement.
        </p>
      ) : (
        <>
          <div className="flex max-h-96 flex-col gap-1.5 overflow-y-auto">
            {rows.map((row, index) => {
              const meta = VERDICT_META[row.verdict] ?? VERDICT_META.new;
              const Icon = meta.icon;
              return (
                <div
                  key={`${row.title}-${index}`}
                  className={cn(
                    "flex items-center gap-3 rounded-xl border bg-white px-3 py-2.5 transition",
                    row.selected ? "border-indigo-200" : "border-slate-100",
                  )}
                >
                  <input
                    type="checkbox"
                    checked={row.selected}
                    onChange={() => toggle(index)}
                    className="h-4 w-4 shrink-0 accent-indigo-600"
                  />
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-sm font-bold text-slate-800">
                      {row.title}
                    </span>
                    <span className="block text-xs font-medium text-slate-400">
                      {row.matched_node_title
                        ? `→ rattachée à « ${row.matched_node_title} »`
                        : "→ nouvelle notion"}
                    </span>
                  </span>

                  {/* La matière n'est modifiable que pour une création : sur un
                      rattachement, elle vient du nœud existant. */}
                  {row.matched_node_id === null ? (
                    <Select
                      value={row.subject}
                      onChange={(e) =>
                        setRows((list) =>
                          list.map((r, i) =>
                            i === index ? { ...r, subject: e.target.value } : r,
                          ),
                        )
                      }
                      className="w-36 shrink-0 px-2 py-1 text-xs"
                    >
                      {Object.entries(SUBJECT_LABELS).map(([value, label]) => (
                        <option key={value} value={value}>
                          {label}
                        </option>
                      ))}
                    </Select>
                  ) : (
                    <Badge tone="slate">
                      {SUBJECT_LABELS[row.matched_node_subject] ??
                        row.matched_node_subject}
                    </Badge>
                  )}

                  <Badge tone={meta.tone}>
                    <Icon className="h-3 w-3" />
                    {meta.label}
                  </Badge>
                </div>
              );
            })}
          </div>

          <div className="mt-3 flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-400">
              {selected} sélectionnée{selected > 1 ? "s" : ""} sur {rows.length}
            </span>
            <Button size="sm" onClick={apply} disabled={busy || selected === 0}>
              {busy ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                "Rattacher au graphe"
              )}
            </Button>
          </div>
        </>
      )}
    </div>
  );
}
