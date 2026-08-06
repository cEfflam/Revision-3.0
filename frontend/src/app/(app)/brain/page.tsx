"use client";

/**
 * Le « Brain » : là où tu déverses tes cours.
 * Import → le backend extrait, découpe, vectorise. Ensuite : recherche
 * sémantique et génération de flashcards en un clic par document.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import {
  FileText,
  Loader2,
  Network,
  Search,
  Sparkles,
  Trash2,
  Upload,
} from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { SUBJECT_LABELS } from "@/lib/utils";
import type { DocumentRead, SearchHit } from "@/types/api";
import { Button } from "@/components/ui/button";
import { Input, Select } from "@/components/ui/input";
import { Card, CardContent, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { DocumentMappingPanel } from "@/components/document-mapping";

const COLLECTIONS = [
  { value: "course", label: "Cours" },
  { value: "exam", label: "BTS blancs / annales" },
  { value: "error", label: "Erreurs passées" },
  { value: "note", label: "Notes perso" },
];

const STATUS_TONES: Record<string, "emerald" | "amber" | "rose" | "slate"> = {
  ready: "emerald",
  processing: "amber",
  failed: "rose",
  pending: "slate",
};

export default function BrainPage() {
  const [documents, setDocuments] = useState<DocumentRead[]>([]);
  const [collection, setCollection] = useState("course");
  const [subject, setSubject] = useState("other");
  const [uploading, setUploading] = useState(false);
  const [message, setMessage] = useState<{ text: string; error: boolean } | null>(
    null,
  );
  const [query, setQuery] = useState("");
  const [hits, setHits] = useState<SearchHit[] | null>(null);
  const [searching, setSearching] = useState(false);
  const [generatingId, setGeneratingId] = useState<number | null>(null);
  const [mappingId, setMappingId] = useState<number | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);

  const reload = useCallback(() => {
    api.documents().then(setDocuments).catch(() => {});
  }, []);

  useEffect(reload, [reload]);

  async function upload(file: File) {
    setUploading(true);
    setMessage(null);
    const form = new FormData();
    form.append("file", file);
    form.append("collection", collection);
    form.append("subject", subject);
    try {
      const result = await api.uploadDocument(form);
      setMessage({
        text:
          `« ${result.document.title} » importé : ${result.chunk_count} fragments, ` +
          `${result.vectors_indexed} vecteurs indexés.` +
          (result.warning ? ` ⚠️ ${result.warning}` : ""),
        error: false,
      });
      reload();
    } catch (err) {
      setMessage({
        text: err instanceof ApiError ? err.detail : "Échec de l'import.",
        error: true,
      });
    } finally {
      setUploading(false);
      if (fileInput.current) fileInput.current.value = "";
    }
  }

  async function search() {
    if (query.trim().length < 2) return;
    setSearching(true);
    try {
      const response = await api.searchDocuments(query);
      setHits(response.hits);
    } catch {
      setHits([]);
    } finally {
      setSearching(false);
    }
  }

  async function generateCards(doc: DocumentRead) {
    setGeneratingId(doc.id);
    setMessage(null);
    try {
      const result = await api.generateCards({ document_id: doc.id, count: 8 });
      setMessage({
        text:
          `${result.created} flashcards créées depuis « ${doc.title} »` +
          (result.mocked ? " (mode simulé — AI_MOCK)" : "") +
          ". Elles t'attendent dans Réviser.",
        error: false,
      });
    } catch (err) {
      setMessage({
        text: err instanceof ApiError ? err.detail : "Génération impossible.",
        error: true,
      });
    } finally {
      setGeneratingId(null);
    }
  }

  async function remove(doc: DocumentRead) {
    if (!window.confirm(`Supprimer définitivement « ${doc.title} » ?`)) return;
    await api.deleteDocument(doc.id);
    reload();
  }

  return (
    <div className="flex flex-col gap-5">
      <header>
        <h1 className="text-2xl font-extrabold tracking-tight">Brain 🧠</h1>
        <p className="mt-1 text-sm font-medium text-slate-400">
          Importe tes cours — l&apos;application les digère pour toi.
        </p>
      </header>

      {/* ── Import ─────────────────────────────────────────────────────── */}
      <Card>
        <CardContent className="flex flex-col gap-3">
          <CardTitle>Importer un document</CardTitle>
          <div className="grid grid-cols-2 gap-3">
            <Select
              value={collection}
              onChange={(e) => setCollection(e.target.value)}
            >
              {COLLECTIONS.map((c) => (
                <option key={c.value} value={c.value}>
                  {c.label}
                </option>
              ))}
            </Select>
            <Select value={subject} onChange={(e) => setSubject(e.target.value)}>
              {Object.entries(SUBJECT_LABELS).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </Select>
          </div>

          <input
            ref={fileInput}
            type="file"
            accept=".pdf,.docx,.md,.markdown,.txt"
            className="hidden"
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) upload(file);
            }}
          />
          <button
            onClick={() => fileInput.current?.click()}
            disabled={uploading}
            className="flex flex-col items-center gap-2 rounded-tile border-2 border-dashed border-indigo-200 bg-indigo-50/40 px-4 py-8 transition hover:border-indigo-300 hover:bg-indigo-50"
          >
            {uploading ? (
              <Loader2 className="h-6 w-6 animate-spin text-indigo-500" />
            ) : (
              <Upload className="h-6 w-6 text-indigo-500" />
            )}
            <span className="text-sm font-bold text-indigo-600">
              {uploading
                ? "Extraction, découpage, vectorisation…"
                : "Choisir un fichier"}
            </span>
            <span className="text-xs font-medium text-slate-400">
              PDF · DOCX · Markdown · TXT — 25 Mo max
            </span>
          </button>

          {message && (
            <p
              className={`rounded-xl px-3 py-2 text-sm font-medium ${
                message.error
                  ? "bg-rose-50 text-rose-600"
                  : "bg-emerald-50 text-emerald-700"
              }`}
            >
              {message.text}
            </p>
          )}
        </CardContent>
      </Card>

      {/* ── Recherche sémantique ───────────────────────────────────────── */}
      <Card>
        <CardContent className="flex flex-col gap-3">
          <CardTitle>Recherche dans mes cours</CardTitle>
          <div className="flex gap-2">
            <Input
              placeholder="Ex. : différence entre INNER et LEFT JOIN ?"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && search()}
            />
            <Button onClick={search} disabled={searching} className="shrink-0">
              {searching ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Search className="h-4 w-4" />
              )}
            </Button>
          </div>
          <p className="-mt-1 text-xs font-medium text-slate-400">
            Recherche par le sens, pas par mots-clés : « clé étrangère » trouvera
            aussi les passages qui parlent de FOREIGN KEY.
          </p>

          {hits !== null && (
            <div className="flex flex-col gap-2">
              {hits.length === 0 && (
                <p className="text-sm font-medium text-slate-400">
                  Aucun résultat. As-tu importé des documents ?
                </p>
              )}
              {hits.map((hit, i) => (
                <div
                  key={i}
                  className="rounded-2xl border border-slate-100 bg-slate-50/60 px-4 py-3"
                >
                  <div className="mb-1 flex items-center justify-between gap-2">
                    <p className="text-xs font-bold text-indigo-600">
                      {hit.document_title}
                      {hit.heading ? ` — ${hit.heading}` : ""}
                    </p>
                    <Badge tone="slate">{(hit.score * 100).toFixed(0)}</Badge>
                  </div>
                  <p className="line-clamp-3 text-sm font-medium text-slate-600">
                    {hit.excerpt}
                  </p>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* ── Bibliothèque ───────────────────────────────────────────────── */}
      <section>
        <h3 className="mb-3 px-1 text-sm font-bold uppercase tracking-wider text-slate-400">
          Bibliothèque ({documents.length})
        </h3>
        <div className="flex flex-col gap-2.5">
          {documents.length === 0 && (
            <p className="px-1 text-sm font-medium text-slate-400">
              Aucun document pour l&apos;instant.
            </p>
          )}
          {documents.map((doc) => (
            <div key={doc.id} className="flex flex-col gap-2">
              <div className="action-row cursor-default">
                <span className="icon-tile">
                  <FileText className="h-5 w-5" />
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block truncate font-bold text-slate-800">
                    {doc.title}
                  </span>
                  <span className="block text-sm font-medium text-slate-400">
                    {SUBJECT_LABELS[doc.subject] ?? doc.subject} ·{" "}
                    {doc.chunk_count} fragments ·{" "}
                    {(doc.size_bytes / 1024).toFixed(0)} Ko
                  </span>
                </span>
                <Badge tone={STATUS_TONES[doc.status] ?? "slate"}>
                  {doc.status}
                </Badge>
                <button
                  onClick={() =>
                    setMappingId(mappingId === doc.id ? null : doc.id)
                  }
                  title="Rattacher aux notions du graphe"
                  className="rounded-xl p-2 text-slate-400 transition hover:bg-indigo-50 hover:text-indigo-600"
                >
                  <Network className="h-5 w-5" />
                </button>
                <button
                  onClick={() => generateCards(doc)}
                  disabled={generatingId === doc.id}
                  title="Générer des flashcards"
                  className="rounded-xl p-2 text-indigo-400 transition hover:bg-indigo-50 hover:text-indigo-600"
                >
                  {generatingId === doc.id ? (
                    <Loader2 className="h-5 w-5 animate-spin" />
                  ) : (
                    <Sparkles className="h-5 w-5" />
                  )}
                </button>
                <button
                  onClick={() => remove(doc)}
                  title="Supprimer"
                  className="rounded-xl p-2 text-slate-300 transition hover:bg-rose-50 hover:text-rose-500"
                >
                  <Trash2 className="h-5 w-5" />
                </button>
              </div>

              {mappingId === doc.id && (
                <DocumentMappingPanel
                  documentId={doc.id}
                  onClose={() => setMappingId(null)}
                  onApplied={(text) => {
                    setMessage({ text, error: false });
                    reload();
                  }}
                />
              )}
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
