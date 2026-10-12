import { STAGE } from "../labels";
import type { Stage } from "../types";

const TONE = { ok: "text-ok", accent: "text-accent", muted: "text-muted" } as const;

export function StageLabel({ stage }: { stage: Stage }) {
  const s = STAGE[stage];
  return (
    <span className={`inline-flex items-center gap-1.5 text-xs font-medium ${s.busy ? "text-ink" : TONE[s.tone ?? "muted"]}`}>
      {s.busy && (
        // A live indicator for real work in progress, not decoration.
        <span className="relative flex size-2" aria-hidden="true">
          <span className="absolute inline-flex size-full animate-ping rounded-full bg-accent opacity-60" />
          <span className="relative inline-flex size-2 rounded-full bg-accent" />
        </span>
      )}
      {s.label}
    </span>
  );
}
