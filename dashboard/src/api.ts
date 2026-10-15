import type { Case, Me, Project, ProjectIn } from "./types";

export interface Live { url: string; broken: boolean }

// Demo build (GitHub Pages): read-only, serves real recorded cases from ./demo/ instead of the live service.
export const DEMO = import.meta.env.VITE_DEMO === "1";
const BASE = import.meta.env.BASE_URL;
const DEMO_PROJECT: Project = {
  id: "demo", name: "BadShop demo", key: "demo", owner: "*", mode: "local", repo: "", origins: [],
  sector: "ecommerce", retention_days: 30, screenshots: true, created_at: "2026-10-12T00:00:00Z",
};

async function call<T>(path: string, method = "GET", body?: unknown): Promise<T> {
  const res = await fetch(path, {
    method,
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    const detail = await res.json().then((d) => d.detail, () => null);
    throw new Error(typeof detail === "string" ? detail : `${method} ${path} failed with HTTP ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export const getMe = (): Promise<Me> =>
  DEMO ? Promise.resolve({ login: "demo", login_enabled: false, github_app: null }) : call<Me>("/api/v1/me");
export const getProjects = (): Promise<Project[]> => (DEMO ? Promise.resolve([DEMO_PROJECT]) : call<Project[]>("/api/v1/projects"));
export const createProject = (body: ProjectIn) => call<Project>("/api/v1/projects", "POST", body);
export const getCases = (projectId: string): Promise<Case[]> =>
  DEMO ? call<Case[]>(`${BASE}demo/cases.json`) : call<Case[]>(`/api/v1/projects/${projectId}/cases`);
export const replayCase = (caseId: string) => call<{ ok: boolean }>(`/api/v1/cases/${caseId}/replay`, "POST");
export const sendTestReport = (key: string, text: string) =>
  call<{ id: string }>("/api/v1/reports", "POST", {
    project: key, kind: "spoken", text, page: "/",
    env: { viewport: { width: 360, height: 740 }, language: navigator.language, touch: true,
           effective_type: "3g", rtt_ms: 1500, timezone: Intl.DateTimeFormat().resolvedOptions().timeZone },
  });

export const getLive = (): Promise<Live | null> => (DEMO ? Promise.resolve(null) : call<Live>("/api/live"));
export const breakShop = () => call<Live>("/api/break", "POST");
export const resetShop = () => call<Live>("/api/reset", "POST");
export const shotUrl = (name: string, base?: string) =>
  base ? `${base}/${name}?raw=true` : DEMO ? `${BASE}demo/shots/${name}` : `/shots/${name}`;
