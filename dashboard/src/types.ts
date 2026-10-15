export type Stage =
  | "heard" | "queued" | "reproducing" | "reproduced" | "not_reproduced" | "ux_confusion"
  | "fixing" | "proving" | "fixed" | "fix_unproven" | "fix_failed" | "guarded" | "error" | "not_a_bug";

export type Kind = "spoken" | "rage_click" | "js_error" | "failed_request" | "slow_request";

export interface Evidence { id: string; kind: string; detail: string; step: number }

export interface Step { action: Record<string, unknown> & { type: string; why?: string }; result: string; target?: string | null }

export interface Replay {
  verdict: "reproduced" | "ux_confusion" | "not_reproduced";
  summary: string;
  cited: string[];
  evidence: Evidence[];
  steps: Step[];
}

/** The fix proven by replaying the exact steps on the fixed code (older cases hold a full Replay instead). */
export interface Proof { passed: boolean; evidence: { kind: string; detail: string }[]; steps: number }

export interface Case {
  id: string;
  project?: string;
  created_at: string;
  kind: Kind;
  complaint: string;
  said?: string;
  lang?: string;
  page?: string;
  condition: { label: string; persona: string };
  stage: Stage;
  impact?: number;
  triage?: { label: "bug" | "ux_confusion" | "feature_request" | "spam"; margin: number; replay: boolean };
  replay?: Replay;
  fix?: { model: string; explanation: string; diff?: string; error?: string; sources?: { title: string; url: string }[] };
  proof?: Proof | Replay;
  shots?: { before?: string; after?: string };
  shot_base?: string;
  guard?: { file: string; steps: number; passes_on_fix: boolean; catches_bug: boolean };
  pr?: string;
  error?: string;
  reports?: number;
  also_reported?: { said: string; kind: Kind; condition: string; at: string }[];
}

export interface Project {
  id: string;
  name: string;
  key: string;
  owner: string;
  mode: "local" | "github";
  repo: string;
  origins: string[];
  sector: "general" | "ecommerce" | "fintech" | "public";
  retention_days: number;
  screenshots: boolean;
  created_at: string;
}

export type ProjectIn = Pick<Project, "name" | "repo" | "origins" | "sector" | "retention_days" | "screenshots">;

export interface Me { login: string | null; login_enabled: boolean; github_app: string | null }

export type Column = "heard" | "reproduced" | "fixed" | "guarded";

export function columnOf(stage: Stage): Column {
  if (stage === "fixed") return "fixed";
  if (stage === "guarded") return "guarded";
  if (["reproduced", "fixing", "proving", "fix_unproven", "fix_failed"].includes(stage)) return "reproduced";
  return "heard";
}

export const proofPassed = (c: Case): boolean =>
  c.proof && "passed" in c.proof ? c.proof.passed : c.stage === "fixed" || c.stage === "guarded";
