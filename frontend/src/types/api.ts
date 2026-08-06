/**
 * Types miroirs des schémas Pydantic du backend.
 *
 * Maintenus à la main pour l'instant — c'est voulu : les recopier oblige à
 * connaître son API. Le jour où ça devient pénible, ils se génèrent depuis
 * /openapi.json (openapi-typescript) sans rien changer au reste du code.
 */

// ── Auth ──────────────────────────────────────────────────────────────────
export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
}

export interface User {
  id: number;
  email: string;
  display_name: string;
  daily_minutes: number;
  onboarding_completed: boolean;
  streak_current: number;
  streak_best: number;
  last_active_day: string | null;
}

// ── Onboarding / objectifs ────────────────────────────────────────────────
export interface Goal {
  id: number;
  title: string;
  kind: string;
  description: string;
  target_date: string | null;
  daily_minutes: number;
  is_primary: boolean;
  is_active: boolean;
  progress: number;
  days_left: number | null;
}

export interface OnboardingResponse {
  goal: Goal;
  assessments: { subject: string; level: number }[];
  nodes_created: number;
  message: string;
}

// ── Graphe ────────────────────────────────────────────────────────────────
export interface NodeRead {
  id: number;
  slug: string;
  title: string;
  kind: string;
  subject: string;
  description: string;
  mastery: number;
  status: string;
  difficulty: number;
  estimated_minutes: number;
  review_count: number;
  failure_count: number;
  last_studied_at: string | null;
}

export interface EdgeRead {
  id: number;
  source_id: number;
  target_id: number;
  relation: string;
  weight: number;
}

export interface GraphRead {
  nodes: NodeRead[];
  edges: EdgeRead[];
  counts: Record<string, number>;
}

export interface DiagnosisRead {
  node: NodeRead;
  weak_prerequisites: NodeRead[];
  verdict: string;
}

// ── Cartes & révision ─────────────────────────────────────────────────────
export interface CardRead {
  id: number;
  front: string;
  back: string;
  kind: string;
  hint: string;
  explanation: string;
  state: string;
  due_at: string;
  interval_days: number;
  ease_factor: number;
  repetitions: number;
  lapses: number;
  node_id: number | null;
  document_id: number | null;
  ai_generated: boolean;
  is_suspended: boolean;
}

export interface CardQueueItem extends CardRead {
  node_title: string | null;
  node_subject: string | null;
}

export type Rating = "again" | "hard" | "good" | "easy";

export interface ReviewResponse {
  card: CardRead;
  next_due_at: string;
  interval_days: number;
  weak_prerequisites: NodeRead[];
  diagnosis: string;
  remaining_due: number;
}

export interface GenerateCardsResponse {
  created: number;
  cards: CardRead[];
  model: string;
  mocked: boolean;
}

// ── Sessions ──────────────────────────────────────────────────────────────
export interface SessionRead {
  id: number;
  engine: string;
  node_id: number | null;
  started_at: string;
  ended_at: string | null;
  duration_seconds: number;
  cards_reviewed: number;
  correct_count: number;
  summary: string;
}

// ── Dashboard & stats ─────────────────────────────────────────────────────
export interface TodayAction {
  key: string;
  icon: string;
  title: string;
  subtitle: string;
  href: string;
  count: number | null;
  accent: string;
}

export interface HeatmapPoint {
  day: string;
  minutes: number;
  reviews: number;
  xp: number;
}

export interface DashboardRead {
  greeting: string;
  goal: Goal | null;
  days_left: number | null;
  readiness: number;
  due_now: number;
  daily_minutes: number;
  streak_current: number;
  streak_best: number;
  minutes_today: number;
  actions: TodayAction[];
  weakest_nodes: NodeRead[];
  heatmap: HeatmapPoint[];
}

export interface StatsRead {
  total_cards: number;
  new_cards: number;
  mastered_cards: number;
  reviews_total: number;
  accuracy: number;
  due_now: number;
  nodes_total: number;
  nodes_mastered: number;
  documents_total: number;
  subject_mastery: Record<string, number>;
}

// ── Documents ─────────────────────────────────────────────────────────────
export interface DocumentRead {
  id: number;
  title: string;
  original_filename: string;
  mime_type: string;
  size_bytes: number;
  collection: string;
  subject: string;
  status: string;
  error_message: string;
  char_count: number;
  chunk_count: number;
  summary: string;
  created_at: string;
}

export interface IngestResponse {
  document: DocumentRead;
  chunk_count: number;
  vectors_indexed: number;
  warning: string;
}

export interface SearchHit {
  document_title: string;
  heading: string;
  excerpt: string;
  score: number;
  document_id: number | null;
  ordinal: number | null;
}

export interface SearchResponse {
  query: string;
  hits: SearchHit[];
  embedder: string;
}

// ── IA ────────────────────────────────────────────────────────────────────
export interface SourceRead {
  index: number;
  document_title: string;
  heading: string;
  excerpt: string;
  score: number;
}

export interface ChatResponse {
  answer: string;
  sources: SourceRead[];
  model: string;
  tier: string;
  mocked: boolean;
  latency_ms: number;
  tokens: number;
}

export interface EngineInfo {
  task: string;
  label: string;
  tier: string;
  uses_documents: string;
}

// ── Matières ──────────────────────────────────────────────────────────────
export interface SubjectSummary {
  subject: string;
  label: string;
  mastery: number;
  nodes_total: number;
  nodes_mastered: number;
  nodes_critical: number;
  cards_total: number;
  cards_due: number;
  documents_total: number;
}

export interface SubjectDetail extends SubjectSummary {
  nodes: NodeRead[];
  weak_nodes: NodeRead[];
  documents: DocumentRead[];
  advice: string;
}

// ── Quiz ──────────────────────────────────────────────────────────────────
export interface QuizQuestion {
  question: string;
  kind: "mcq" | "open" | string;
  choices: string[];
  /** Index de la bonne réponse dans `choices`, ou -1 si question ouverte. */
  answer_index: number;
  explanation: string;
}

export interface QuizResponse {
  questions: QuizQuestion[];
  source: string;
  model: string;
  mocked: boolean;
}

// ── Roadmap ───────────────────────────────────────────────────────────────
export interface RoadmapStep {
  id: number;
  order_index: number;
  title: string;
  subject: string;
  estimated_minutes: number;
  why: string;
  /** Titres des étapes prérequises, séparés par « | ». */
  prerequisites: string;
  node_id: number | null;
  is_done: boolean;
  completed_at: string | null;
}

export interface RoadmapRead {
  objective: string;
  feasible: boolean;
  advice: string;
  total_estimated_hours: number;
  steps: RoadmapStep[];
  generated_at: string | null;
  model: string;
  mocked: boolean;
}

// ── Entraînement type examen ──────────────────────────────────────────────
export interface ExamFormat {
  subject: string;
  label: string;
  /** "text" | "code" | "sql" — pilote le champ de réponse. */
  input_kind: string;
  method: string;
  criteria: string[];
  duration_minutes: number;
  total_points: number;
  placeholder: string;
}

export interface ExamQuestion {
  number: number;
  text: string;
  points: number;
}

export interface ExamRead {
  subject: string;
  format: ExamFormat;
  title: string;
  instructions: string;
  context: string;
  questions: ExamQuestion[];
  duration_minutes: number;
  total_points: number;
  inspired_by: string;
  /** False quand aucune annale n'a servi de modèle de style. */
  has_annales: boolean;
  sources: SourceRead[];
  model: string;
  mocked: boolean;
}

export interface QuestionFeedback {
  number: number;
  points_earned: number;
  points_max: number;
  feedback: string;
}

export interface CriterionFeedback {
  criterion: string;
  verdict: string;
  comment: string;
}

export interface ExamEvaluation {
  score: number;
  max_score: number;
  per_question: QuestionFeedback[];
  criteria_feedback: CriterionFeedback[];
  strengths: string[];
  gaps: string[];
  next_step: string;
  model: string;
  mocked: boolean;
}

export interface PracticeSubject {
  subject: string;
  label: string;
  exam_label: string;
}

// ── Audit d'écrit (CGE) ───────────────────────────────────────────────────
/** Types de problèmes détectés — miroir du prompt CGE_ANALYSIS. */
export type WritingIssueType =
  | "plan"
  | "repetition"
  | "transition"
  | "vocabulary"
  | "syntax"
  | "argument";

export interface WritingIssue {
  type: WritingIssueType | string;
  severity: "info" | "warning" | "critical" | string;
  label: string;
  /**
   * Extrait EXACT du texte de l'étudiant, ou chaîne vide. Le backend ne le
   * conserve que s'il figure littéralement dans le texte soumis : c'est ce
   * qui permet de le retrouver pour le surligner.
   */
  quote: string;
  detail: string;
  suggestion: string;
}

export interface WritingAnalysis {
  score: number | null;
  issues: WritingIssue[];
  strengths: string[];
  next_step: string;
  model: string;
  mocked: boolean;
}
