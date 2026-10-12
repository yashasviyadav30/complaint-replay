import type { Case } from "./types";

export interface Live { url: string; broken: boolean }

async function call<T>(path: string, method = "GET"): Promise<T> {
  const res = await fetch(path, { method });
  if (!res.ok) throw new Error(`${method} ${path} failed with HTTP ${res.status}`);
  return res.json() as Promise<T>;
}

export const getCases = () => call<Case[]>("/api/cases");
export const getLive = () => call<Live>("/api/live");
export const breakShop = () => call<Live>("/api/break", "POST");
export const resetShop = () => call<Live>("/api/reset", "POST");
