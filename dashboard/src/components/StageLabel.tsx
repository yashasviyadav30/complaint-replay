import { STAGE } from "../labels";
import type { Stage } from "../types";

const TONE = {
  ok: "bg-ok-soft text-ok",
  accent: "bg-accent-soft text-accent",
  muted: "bg-surface-2 text-muted",
} as const;

export function StageLabel({ stage }: { stage: Stage }) {
  const s = STAGE[stage];
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ${s.busy ? "bg-surface-2 text-ink" : TONE[s.tone ?? "muted"]}`}>
      {s.busy ? (
        // A live indicator for real work in progress, not decoration.
        <span className="relative flex size-2" aria-hidden="true">
          <span className="absolute inline-flex size-full animate-ping rounded-full bg-accent opacity-60" />
          <span className="relative inline-flex size-2 rounded-full bg-accent" />
        </span>
      ) : (
        s.icon && <s.icon size={13} weight="bold" aria-hidden="true" />
      )}
      {s.label}
    </span>
  );
}
