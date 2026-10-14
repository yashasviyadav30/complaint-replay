import { X } from "@phosphor-icons/react";
import { motion } from "motion/react";
import { useEffect, useRef } from "react";
import { shotUrl } from "../api";
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

function Shot({ src, caption }: { src: string; caption: string }) {
  return (
    <figure className="min-w-0">
      <a href={shotUrl(src)} target="_blank" rel="noreferrer">
        <img src={shotUrl(src)} alt={caption} loading="lazy"
          className="max-h-96 w-full rounded-lg border border-line bg-surface-2 object-contain object-top" />
      </a>
      <figcaption className="mt-1.5 text-xs text-muted">{caption}</figcaption>
    </figure>
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

        <div className="grid grid-cols-1 gap-6 px-6 py-6">
          <div className="grid gap-2">
            <StageLabel stage={c.stage} />
            <p className="text-sm text-muted">
              Replayed as: <span className="font-mono text-[12px] text-ink">{twinSummary(c)}</span>
            </p>
            {c.error && <p className="text-sm text-accent">{c.error}</p>}
          </div>

          {c.also_reported && c.also_reported.length > 0 && (
            <Section title={`Also reported by ${c.also_reported.length} more ${c.also_reported.length === 1 ? "person" : "people"}`}>
              <p className="mb-3 text-xs text-muted">Grouped by Nemotron Embed and confirmed by a Nemotron check, so this bug is investigated once.</p>
              <ul className="grid gap-2">
                {c.also_reported.map((r, i) => (
                  <li key={i} className="rounded-lg border border-line bg-surface-2 p-3 text-sm">
                    <p className="text-ink">"{r.said || KIND[r.kind].label}"</p>
                    <p className="mt-1 font-mono text-[11px] text-muted">{r.condition}</p>
                  </li>
                ))}
              </ul>
            </Section>
          )}

          {c.shots?.before && (
            <Section title="What the user saw">
              <div className="grid gap-3 sm:grid-cols-2">
                <Shot src={c.shots.before} caption="When the bug was proven" />
                {c.shots.after && c.stage !== "fix_unproven" && <Shot src={c.shots.after} caption="Same user, on the fixed code" />}
              </div>
            </Section>
          )}

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
              {c.fix.sources && c.fix.sources.length > 0 && (
                <div className="mt-4">
                  <p className="mb-1 text-xs text-muted">Researched with Tavily before writing the fix:</p>
                  <ul className="grid gap-1 text-sm">
                    {c.fix.sources.map((s) => (
                      <li key={s.url} className="truncate">
                        <a href={s.url} target="_blank" rel="noreferrer" className="text-accent hover:underline">{s.title || s.url}</a>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
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
                The steps that triggered the bug are saved as <code translate="no" className="font-mono text-[12px]">{c.guard.file}</code>,{" "}
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
