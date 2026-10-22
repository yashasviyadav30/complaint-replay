import { motion } from "motion/react";
import { KIND, languageName, timeAgo, twinSummary, whatTheySaid } from "../labels";
import type { Case } from "../types";
import { StageLabel } from "./StageLabel";

export function CaseCard({ c, now, onOpen }: { c: Case; now: number; onOpen: (id: string) => void }) {
  const kind = KIND[c.kind];
  const Icon = kind.icon;
  return (
    <motion.button
      layout
      layoutId={c.id}
      type="button"
      onClick={() => onOpen(c.id)}
      transition={{ type: "spring", stiffness: 260, damping: 30 }}
      className="group w-full rounded-xl border border-line bg-surface p-4 text-left transition-colors hover:border-muted active:scale-[0.99]"
    >
      <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1 text-xs text-muted">
        <span className="inline-flex items-center gap-1.5">
          <Icon size={14} weight="bold" aria-hidden="true" />
          {kind.label}
        </span>
        <span className="inline-flex items-center gap-2">
          {(c.reports ?? 1) > 1 && (
            <span className="whitespace-nowrap rounded-full border border-line px-2 py-0.5 text-[11px] font-medium text-ink tabular-nums">
              {c.reports} people
            </span>
          )}
          <time dateTime={c.created_at} className="whitespace-nowrap tabular-nums">{timeAgo(c.created_at, now)}</time>
        </span>
      </div>
      <p className="mt-2 line-clamp-3 text-sm leading-snug text-ink">{whatTheySaid(c)}</p>
      <p className="mt-3 truncate font-mono text-[11px] text-muted" title={twinSummary(c)}>
        {twinSummary(c)}
      </p>
      {(c.lang || (c.page && c.page !== "/")) && (
        <p className="mt-1 truncate text-[11px] text-muted">
          {[c.lang && c.lang !== "en" ? `Written in ${languageName(c.lang)}` : "", c.page && c.page !== "/" ? `on ${c.page}` : ""]
            .filter(Boolean).join(" ")}
        </p>
      )}
      <div className="mt-3">
        <StageLabel stage={c.stage} />
      </div>
    </motion.button>
  );
}
