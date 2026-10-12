import { motion } from "motion/react";
import { KIND, timeAgo, twinSummary, whatTheySaid } from "../labels";
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
      <div className="flex items-center justify-between gap-3 text-xs text-muted">
        <span className="inline-flex items-center gap-1.5">
          <Icon size={14} weight="bold" aria-hidden="true" />
          {kind.label}
        </span>
        <time dateTime={c.created_at}>{timeAgo(c.created_at, now)}</time>
      </div>
      <p className="mt-2 line-clamp-3 text-sm leading-snug text-ink">{whatTheySaid(c)}</p>
      <p className="mt-3 truncate font-mono text-[11px] text-muted" title={twinSummary(c)}>
        {twinSummary(c)}
      </p>
      <div className="mt-3">
        <StageLabel stage={c.stage} />
      </div>
    </motion.button>
  );
}
