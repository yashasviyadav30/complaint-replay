import { LayoutGroup } from "motion/react";
import { columnOf, type Case, type Column } from "../types";
import { CaseCard } from "./CaseCard";

const COLUMNS: { id: Column; title: string; hint: string }[] = [
  { id: "heard", title: "Heard", hint: "Complaints and silent signals" },
  { id: "reproduced", title: "Reproduced", hint: "Proven with browser evidence" },
  { id: "fixed", title: "Fixed", hint: "Fix replayed by the same user" },
  { id: "guarded", title: "Guarded", hint: "Saved as a test" },
];

// Highest impact first: people affected x how bad it is (a double charge outranks a missing image).
const rank = (c: Case) => c.impact ?? c.reports ?? 1;

export function Board({ cases, now, onOpen }: { cases: Case[]; now: number; onOpen: (id: string) => void }) {
  const columns = COLUMNS.map((col) => ({
    ...col,
    items: cases.filter((c) => columnOf(c.stage) === col.id)
      .sort((a, b) => rank(b) - rank(a) || b.created_at.localeCompare(a.created_at)),
  }));
  // On wide screens an empty column shrinks, so a full one can lay its cards out side by side.
  const widths = columns.map((col) => (col.items.length ? "minmax(0,2fr)" : "minmax(9rem,0.6fr)")).join(" ");
  return (
    <LayoutGroup>
      <div className="grid grid-cols-1 gap-6 md:grid-cols-2 xl:[grid-template-columns:var(--cols)]"
        style={{ "--cols": widths } as React.CSSProperties}>
        {columns.map(({ items, ...col }) => {
          return (
            <section key={col.id} aria-labelledby={`col-${col.id}`} className="min-w-0">
              <header className="mb-3 border-b border-line pb-2">
                <h2 id={`col-${col.id}`} className="text-sm font-semibold text-ink">
                  {col.title} <span className="ml-1 font-mono text-xs font-normal text-muted">{items.length}</span>
                </h2>
                <p className="mt-0.5 truncate text-xs text-muted">{col.hint}</p>
              </header>
              <div className="grid grid-cols-[repeat(auto-fill,minmax(min(16rem,100%),1fr))] gap-3">
                {items.map((c) => (
                  <CaseCard key={c.id} c={c} now={now} onOpen={onOpen} />
                ))}
                {items.length === 0 && <p className="rounded-xl border border-dashed border-line p-4 text-xs text-muted">None right now.</p>}
              </div>
            </section>
          );
        })}
      </div>
    </LayoutGroup>
  );
}
