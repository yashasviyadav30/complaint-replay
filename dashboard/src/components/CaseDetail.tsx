import { X } from "@phosphor-icons/react";
import { motion } from "motion/react";
import { useEffect, useRef } from "react";
import { EVIDENCE, KIND, twinSummary, whatTheySaid } from "../labels";
import type { Case, Replay } from "../types";
import { Diff } from "./Diff";
import { StageLabel } from "./StageLabel";

function EvidenceList({ replay }: { replay: Replay }) {
  if (!replay.evidence.length) return <p className="text-sm text-muted">The browser recorded no failures.</p>;
  return (
    <ul className="grid gap-2">
      {replay.evidence.map((e) => {
        const cited = replay.cited.includes(e.id);
        return (
          <li key={e.id} className={`rounded-lg border p-3 ${cited ? "border-accent bg-surface" : "border-line bg-surface-2"}`}>
            <p className="flex items-center justify-between gap-2 text-xs">
              <span className={cited ? "font-semibold text-accent" : "text-muted"}>{EVIDENCE[e.kind] ?? e.kind}</span>
              <span className="font-mono text-muted">{cited ? "cited as proof" : `step ${e.step}`}</span>
            </p>
            <p translate="no" className="mt-1 break-words font-mono text-[12px] text-ink">{e.detail}</p>
          </li>
        );
      })}
    </ul>
  );
}

function Steps({ replay }: { replay: Replay }) {
  if (!replay.steps.length) return null;
  return (
    <ol className="grid gap-2 border-l border-line pl-4">
      {replay.steps.map((s, i) => (
        <li key={i} className="text-sm">
          <p className="text-ink">{s.action.why || s.action.type}</p>
          <p className="font-mono text-[11px] text-muted">
            {s.action.type}
            {s.result !== "ok" && ` · ${s.result}`}
          </p>
        </li>
      ))}
    </ol>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="border-t border-line pt-5">
      <h3 className="mb-3 text-sm font-semibold text-ink">{title}</h3>
      {children}
    </section>
  );
}

export function CaseDetail({ c, onClose }: { c: Case; onClose: () => void }) {
  const closeRef = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    closeRef.current?.focus();
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    addEventListener("keydown", onKey);
    return () => removeEventListener("keydown", onKey);
  }, [onClose]);
  const Icon = KIND[c.kind].icon;

  return (
    <div className="fixed inset-0 z-20 flex justify-end" role="dialog" aria-modal="true" aria-labelledby="case-title">
      <motion.div className="absolute inset-0 bg-black/40" initial={{ opacity: 0 }} animate={{ opacity: 1 }} onClick={onClose} />
      <motion.aside
        initial={{ x: 40, opacity: 0 }}
        animate={{ x: 0, opacity: 1 }}
        transition={{ type: "spring", stiffness: 300, damping: 32 }}
        className="relative flex h-full w-full max-w-2xl flex-col overflow-y-auto overscroll-contain border-l border-line bg-bg"
      >
        <header className="sticky top-0 flex items-start justify-between gap-4 border-b border-line bg-bg/95 px-6 py-4 backdrop-blur">
          <div className="min-w-0">
            <p className="inline-flex items-center gap-1.5 text-xs text-muted">
              <Icon size={14} weight="bold" aria-hidden="true" /> {KIND[c.kind].label}
            </p>
            <h2 id="case-title" className="mt-1 text-lg font-semibold leading-snug text-ink">
              “{whatTheySaid(c)}”
            </h2>
          </div>
          <button ref={closeRef} type="button" onClick={onClose} aria-label="Close case"
            className="rounded-lg p-2 text-muted hover:bg-surface-2 hover:text-ink">
            <X size={18} weight="bold" />
          </button>
        </header>

        <div className="grid gap-6 px-6 py-6">
          <div className="grid gap-2">
            <StageLabel stage={c.stage} />
            <p className="text-sm text-muted">
              Replayed as: <span className="font-mono text-[12px] text-ink">{twinSummary(c)}</span>
            </p>
            {c.error && <p className="text-sm text-accent">{c.error}</p>}
          </div>

          {c.replay && (
            <Section title="What the twin found">
              <p className="mb-4 text-sm leading-relaxed text-ink">{c.replay.summary || "No verdict yet."}</p>
              <EvidenceList replay={c.replay} />
            </Section>
          )}

          {c.fix && (
            <Section title="The fix">
              <p className="mb-3 text-sm leading-relaxed text-ink">{c.fix.explanation}</p>
              {c.fix.diff && <Diff text={c.fix.diff} />}
              {c.fix.error && <p className="text-sm text-accent">{c.fix.error}</p>}
              <p className="mt-2 font-mono text-[11px] text-muted">written by {c.fix.model}</p>
            </Section>
          )}

          {c.proof && (
            <Section title="Proof on the fixed code">
              <p className={`text-sm ${c.stage === "fixed" ? "text-ok" : "text-accent"}`}>
                {c.stage === "fixed"
                  ? "The same user replayed the complaint on the fixed code. The problem is gone."
                  : "The problem still showed up on the fixed code."}
              </p>
            </Section>
          )}

          {c.guard && (
            <Section title="The guard test">
              <p className="mb-3 text-sm leading-relaxed text-ink">
                The proven replay is saved as <code translate="no" className="font-mono text-[12px]">{c.guard.file}</code>,{" "}
                {c.guard.steps} steps, no AI needed to run it.
              </p>
              <ul className="grid gap-1 text-sm">
                <li className={c.guard.passes_on_fix ? "text-ok" : "text-accent"}>
                  {c.guard.passes_on_fix ? "Passes on the fixed code" : "Does not pass on the fixed code"}
                </li>
                <li className={c.guard.catches_bug ? "text-ok" : "text-accent"}>
                  {c.guard.catches_bug ? "Fails on the old code, so it catches the bug if it comes back" : "Does not catch the old bug"}
                </li>
              </ul>
            </Section>
          )}

          {c.replay && c.replay.steps.length > 0 && (
            <Section title="Every step the twin took">
              <Steps replay={c.replay} />
            </Section>
          )}
        </div>
      </motion.aside>
    </div>
  );
}
