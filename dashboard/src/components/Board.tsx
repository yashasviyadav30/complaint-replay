import { LayoutGroup } from "motion/react";
import { columnOf, type Case, type Column } from "../types";
import { CaseCard } from "./CaseCard";

const COLUMNS: { id: Column; title: string; hint: string }[] = [
  { id: "heard", title: "Heard", hint: "Complaints and silent signals" },
  { id: "reproduced", title: "Reproduced", hint: "Proven with browser evidence" },
  { id: "fixed", title: "Fixed", hint: "Fix replayed by the same user" },
  { id: "guarded", title: "Guarded", hint: "Saved as a test" },
];

export function Board({ cases, now, onOpen }: { cases: Case[]; now: number; onOpen: (id: string) => void }) {
  return (
    <LayoutGroup>
      <div className="grid grid-cols-1 gap-6 md:grid-cols-2 xl:grid-cols-4">
        {COLUMNS.map((col) => {
          // Most-reported first: one bug hurting 40 people outranks one hurting 1.
          const items = cases
            .filter((c) => columnOf(c.stage) === col.id)
            .sort((a, b) => (b.reports ?? 1) - (a.reports ?? 1) || b.created_at.localeCompare(a.created_at));
          return (
            <section key={col.id} aria-labelledby={`col-${col.id}`} className="min-w-0">
              <header className="mb-3 flex items-baseline justify-between gap-2 border-b border-line pb-2">
                <h2 id={`col-${col.id}`} className="text-sm font-semibold text-ink">
                  {col.title} <span className="ml-1 font-mono text-xs font-normal text-muted">{items.length}</span>
                </h2>
                <p className="truncate text-xs text-muted">{col.hint}</p>
              </header>
              <div className="grid grid-cols-1 gap-3">
                {items.map((c) => (
                  <CaseCard key={c.id} c={c} now={now} onOpen={onOpen} />
                ))}
                {items.length === 0 && <p className="rounded-xl border border-dashed border-line p-4 text-xs text-muted">Nothing here yet.</p>}
              </div>
            </section>
          );
        })}
      </div>
    </LayoutGroup>
  );
}
