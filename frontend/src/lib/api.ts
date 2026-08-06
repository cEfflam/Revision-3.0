/**
 * Client API — l'unique porte d'entrée vers le backend.
 *
 * Aucune page n'appelle `fetch` directement : tout passe par `api.*`. Résultat,
 * la gestion du jeton, des erreurs et des redirections 401 est écrite UNE fois,
 * et changer un endpoint côté backend ne touche qu'une ligne ici.
 */

import { clearToken, getToken } from "@/lib/auth";
import type {
  CardQueueItem,
  CardRead,
  ChatResponse,
  DashboardRead,
  DiagnosisRead,
  DocumentRead,
  EngineInfo,
  ExamEvaluation,
  ExamFormat,
  ExamRead,
  PracticeSubject,
  GenerateCardsResponse,
  Goal,
  GraphRead,
  HeatmapPoint,
  IngestResponse,
  NodeRead,
  OnboardingResponse,
  QuizResponse,
  Rating,
  ReviewResponse,
  RoadmapRead,
  RoadmapStep,
  SearchResponse,
  SessionRead,
  StatsRead,
  SubjectDetail,
  SubjectSummary,
  TokenResponse,
  User,
  WritingAnalysis,
} from "@/types/api";

const BASE_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

export class ApiError extends Error {
  constructor(
    public status: number,
    public detail: string,
  ) {
    super(detail);
    this.name = "ApiError";
  }
}

interface RequestOptions {
  method?: "GET" | "POST" | "PATCH" | "DELETE";
  json?: unknown;
  form?: FormData;
  auth?: boolean;
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = "GET", json, form, auth = true } = options;

  const headers: Record<string, string> = {};
  if (json !== undefined) headers["Content-Type"] = "application/json";
  // Pour un FormData, on laisse le navigateur poser lui-même le Content-Type
  // multipart avec sa « boundary » — le forcer casserait l'upload.
  if (auth) {
    const token = getToken();
    if (token) headers.Authorization = `Bearer ${token}`;
  }

  let response: Response;
  try {
    response = await fetch(`${BASE_URL}${path}`, {
      method,
      headers,
      body: json !== undefined ? JSON.stringify(json) : form,
    });
  } catch {
    throw new ApiError(
      0,
      "Backend injoignable. Vérifie que `docker compose up -d` tourne.",
    );
  }

  if (response.status === 401 && auth) {
    // Session expirée : on nettoie et on renvoie à la connexion.
    clearToken();
    if (typeof window !== "undefined") window.location.href = "/login";
    throw new ApiError(401, "Session expirée.");
  }

  if (response.status === 204) return undefined as T;

  const body = await response.json().catch(() => null);
  if (!response.ok) {
    const detail =
      typeof body?.detail === "string"
        ? body.detail
        : `Erreur ${response.status}`;
    throw new ApiError(response.status, detail);
  }
  return body as T;
}

export const api = {
  // ── Auth ────────────────────────────────────────────────────────────────
  register: (email: string, password: string, display_name = "") =>
    request<TokenResponse>("/auth/register", {
      method: "POST",
      json: { email, password, display_name },
      auth: false,
    }),
  login: (email: string, password: string) =>
    request<TokenResponse>("/auth/login", {
      method: "POST",
      json: { email, password },
      auth: false,
    }),
  me: () => request<User>("/auth/me"),

  // ── Onboarding ──────────────────────────────────────────────────────────
  completeOnboarding: (payload: {
    goal: {
      title: string;
      kind: string;
      description?: string;
      target_date?: string | null;
    };
    assessments: { subject: string; level: number }[];
    daily_minutes: number;
  }) => request<OnboardingResponse>("/onboarding", { method: "POST", json: payload }),
  primaryGoal: () => request<Goal>("/onboarding/goal"),

  // ── Dashboard & stats ──────────────────────────────────────────────────
  dashboard: () => request<DashboardRead>("/dashboard"),
  stats: () => request<StatsRead>("/dashboard/stats"),
  heatmap: (days = 365) =>
    request<HeatmapPoint[]>(`/dashboard/heatmap?days=${days}`),
  journal: () =>
    request<{ journal: string; day: string }>("/dashboard/journal", {
      method: "POST",
    }),

  // ── Révision ────────────────────────────────────────────────────────────
  queue: (
    params: { limit?: number; subject?: string; node_id?: number } = {},
  ) => {
    const query = new URLSearchParams();
    if (params.limit) query.set("limit", String(params.limit));
    if (params.subject) query.set("subject", params.subject);
    if (params.node_id) query.set("node_id", String(params.node_id));
    return request<CardQueueItem[]>(`/cards/queue?${query.toString()}`);
  },
  reviewCard: (cardId: number, rating: Rating, durationMs: number) =>
    request<ReviewResponse>(`/cards/${cardId}/review`, {
      method: "POST",
      json: { rating, duration_ms: durationMs },
    }),
  generateCards: (payload: {
    document_id?: number;
    text?: string;
    count?: number;
    node_id?: number;
  }) =>
    request<GenerateCardsResponse>("/cards/generate", {
      method: "POST",
      json: payload,
    }),
  listCards: (
    params: { node_id?: number; limit?: number; ai_generated?: boolean } = {},
  ) => {
    const query = new URLSearchParams();
    if (params.node_id) query.set("node_id", String(params.node_id));
    if (params.limit) query.set("limit", String(params.limit));
    if (params.ai_generated !== undefined) {
      query.set("ai_generated", String(params.ai_generated));
    }
    return request<CardRead[]>(`/cards?${query.toString()}`);
  },

  // ── Sessions ────────────────────────────────────────────────────────────
  startSession: (engine = "srs", node_id?: number) =>
    request<SessionRead>("/sessions/start", {
      method: "POST",
      json: { engine, node_id: node_id ?? null, planned_minutes: 25 },
    }),
  endSession: (id: number, cards_reviewed: number, correct_count: number) =>
    request<SessionRead>(`/sessions/${id}/end`, {
      method: "POST",
      json: { cards_reviewed, correct_count },
    }),

  // ── Graphe ──────────────────────────────────────────────────────────────
  graph: () => request<GraphRead>("/nodes/graph"),
  recommended: (limit = 5) =>
    request<NodeRead[]>(`/nodes/recommended?limit=${limit}`),
  diagnosis: (nodeId: number) =>
    request<DiagnosisRead>(`/nodes/${nodeId}/diagnosis`),

  // ── Documents ───────────────────────────────────────────────────────────
  documents: (collection?: string) => {
    const query = collection ? `?collection=${collection}` : "";
    return request<DocumentRead[]>(`/documents${query}`);
  },
  uploadDocument: (form: FormData) =>
    request<IngestResponse>("/documents/upload", { method: "POST", form }),
  deleteDocument: (id: number) =>
    request<void>(`/documents/${id}`, { method: "DELETE" }),
  searchDocuments: (query: string, top_k = 6) =>
    request<SearchResponse>("/documents/search", {
      method: "POST",
      json: { query, collections: [], top_k },
    }),

  // ── Moteurs IA ──────────────────────────────────────────────────────────
  engines: () => request<EngineInfo[]>("/chat/engines"),
  chat: (payload: {
    message: string;
    task: string;
    history: { role: string; content: string }[];
  }) => request<ChatResponse>("/chat", { method: "POST", json: payload }),
  analyseWriting: (text: string) =>
    request<WritingAnalysis>("/chat/writing-analysis", {
      method: "POST",
      json: { text },
    }),

  // ── Matières ────────────────────────────────────────────────────────────
  subjects: () => request<SubjectSummary[]>("/subjects"),
  subject: (subject: string) =>
    request<SubjectDetail>(`/subjects/${subject}`),

  // ── Quiz ────────────────────────────────────────────────────────────────
  quiz: (payload: {
    document_id?: number;
    node_id?: number;
    text?: string;
    count?: number;
  }) => request<QuizResponse>("/cards/quiz", { method: "POST", json: payload }),

  // ── Roadmap ─────────────────────────────────────────────────────────────
  roadmap: () => request<RoadmapRead>("/roadmap"),
  generateRoadmap: (max_steps = 12) =>
    request<RoadmapRead>("/roadmap/generate", {
      method: "POST",
      json: { replace: true, max_steps },
    }),
  toggleRoadmapStep: (stepId: number, is_done: boolean) =>
    request<RoadmapStep>(`/roadmap/steps/${stepId}`, {
      method: "PATCH",
      json: { is_done },
    }),
  deleteRoadmap: () => request<void>("/roadmap", { method: "DELETE" }),

  // ── Entraînement type examen ────────────────────────────────────────────
  practiceSubjects: () => request<PracticeSubject[]>("/practice/subjects"),
  practiceFormats: () => request<ExamFormat[]>("/practice/formats"),
  generateExam: (payload: {
    subject: string;
    topic?: string;
    node_id?: number;
  }) => request<ExamRead>("/practice/generate", { method: "POST", json: payload }),
  evaluateExam: (payload: {
    subject: string;
    exercise: ExamRead;
    answer: string;
  }) =>
    request<ExamEvaluation>("/practice/evaluate", {
      method: "POST",
      json: payload,
    }),

  // ── Gestion des cartes ──────────────────────────────────────────────────
  updateCard: (
    cardId: number,
    patch: Partial<{
      front: string;
      back: string;
      hint: string;
      explanation: string;
      is_suspended: boolean;
    }>,
  ) => request<CardRead>(`/cards/${cardId}`, { method: "PATCH", json: patch }),
  deleteCard: (cardId: number) =>
    request<void>(`/cards/${cardId}`, { method: "DELETE" }),
};
