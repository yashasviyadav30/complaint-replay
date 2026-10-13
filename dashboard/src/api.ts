import type { Case } from "./types";

export interface Live { url: string; broken: boolean }

// Demo build (GitHub Pages): read-only, serves real recorded cases from ./demo/ instead of the live service.
export const DEMO = import.meta.env.VITE_DEMO === "1";
const BASE = import.meta.env.BASE_URL;

async function call<T>(path: string, method = "GET"): Promise<T> {
  const res = await fetch(path, { method });
  if (!res.ok) throw new Error(`${method} ${path} failed with HTTP ${res.status}`);
  return res.json() as Promise<T>;
}

export const getCases = () => call<Case[]>(DEMO ? `${BASE}demo/cases.json` : "/api/cases");
export const getLive = (): Promise<Live | null> => (DEMO ? Promise.resolve(null) : call<Live>("/api/live"));
export const breakShop = () => call<Live>("/api/break", "POST");
export const resetShop = () => call<Live>("/api/reset", "POST");
export const shotUrl = (name: string) => (DEMO ? `${BASE}demo/shots/${name}` : `/shots/${name}`);
