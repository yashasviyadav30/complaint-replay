import { Check, X } from "@phosphor-icons/react";
import { columnOf, type Case } from "../types";

const STEPS = [
  { id: "heard", label: "Heard" },
  { id: "reproduced", label: "Reproduced" },
  { id: "fixed", label: "Fixed" },
  { id: "guarded", label: "Guarded" },
] as const;

const FAILED_AT: Partial<Record<Case["stage"], number>> = {
  not_reproduced: 1, ux_confusion: 1, not_a_bug: 1, error: 1, fix_unproven: 2, fix_failed: 2,
};

/** How far the case got: each step done, the one it stopped at, and the ones it never reached. */
export function Journey({ c }: { c: Case }) {
  const failed = FAILED_AT[c.stage];
  const reached = failed ?? STEPS.findIndex((s) => s.id === columnOf(c.stage));
  return (
    <ol className="grid grid-cols-4" aria-label="Progress">
      {STEPS.map((s, i) => {
        const done = failed === undefined ? i <= reached : i < failed;
        const stopped = i === failed;
        return (
          <li key={s.id} className="relative flex flex-col items-center gap-1.5 text-center">
            {i > 0 && (
              <span aria-hidden="true"
                className={`absolute right-1/2 top-3 h-px w-full -translate-y-1/2 ${done || stopped ? "bg-ok" : "bg-line"}`} />
            )}
            <span className={`relative grid size-6 place-items-center rounded-full border text-[11px] ${
              done ? "border-ok bg-ok text-bg" : stopped ? "border-accent bg-accent-soft text-accent" : "border-line bg-surface text-muted"}`}>
              {done ? <Check size={13} weight="bold" aria-hidden="true" /> : stopped ? <X size={12} weight="bold" aria-hidden="true" /> : i + 1}
            </span>
            <span className={`text-xs ${done ? "text-ink" : stopped ? "font-medium text-accent" : "text-muted"}`}>
              {s.label}
              <span className="sr-only">{done ? ": done" : stopped ? ": stopped here" : ": not reached"}</span>
            </span>
          </li>
        );
      })}
    </ol>
  );
}
