export type Stage =
  | "heard" | "reproducing" | "reproduced" | "not_reproduced" | "ux_confusion"
  | "fixing" | "proving" | "fixed" | "fix_unproven" | "fix_failed" | "guarded" | "error";

export type Kind = "spoken" | "rage_click" | "js_error" | "failed_request" | "slow_request";

export interface Evidence { id: string; kind: string; detail: string; step: number }

export interface Step { action: Record<string, unknown> & { type: string; why?: string }; result: string }

export interface Replay {
  verdict: "reproduced" | "ux_confusion" | "not_reproduced";
  summary: string;
  cited: string[];
  evidence: Evidence[];
  steps: Step[];
}

export interface Case {
  id: string;
  created_at: string;
  kind: Kind;
  complaint: string;
  said?: string;
  condition: { label: string; persona: string };
  stage: Stage;
  replay?: Replay;
  fix?: { model: string; explanation: string; diff?: string; error?: string };
  proof?: Replay;
  error?: string;
}

export type Column = "heard" | "reproduced" | "fixed" | "guarded";

export function columnOf(stage: Stage): Column {
  if (stage === "fixed") return "fixed";
  if (stage === "guarded") return "guarded";
  if (["reproduced", "fixing", "proving", "fix_unproven", "fix_failed"].includes(stage)) return "reproduced";
  return "heard";
}
