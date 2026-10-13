import { ArrowCounterClockwise, ArrowSquareOut, DiceFive, Detective } from "@phosphor-icons/react";
import { DEMO, type Live } from "../api";

interface Props {
  live: Live | null;
  busy: boolean;
  onBreak: () => void;
  onReset: () => void;
}

export function TopBar({ live, busy, onBreak, onReset }: Props) {
  return (
    <header className="border-b border-line">
      <div className="mx-auto flex h-16 max-w-[1400px] items-center justify-between gap-4 px-4 md:px-8">
        <p className="inline-flex items-center gap-2 font-semibold text-ink">
          <Detective size={22} weight="duotone" className="text-accent" aria-hidden="true" />
          Complaint Replay
        </p>
        <div className="flex items-center gap-2">
          {live?.url && (
            <a href={live.url} target="_blank" rel="noreferrer"
              className="hidden items-center gap-1.5 rounded-lg px-3 py-2 text-sm text-muted hover:bg-surface-2 hover:text-ink sm:inline-flex">
              Open Shop <ArrowSquareOut size={14} aria-hidden="true" />
            </a>
          )}
          {live?.broken && (
            <button type="button" onClick={onReset} disabled={busy}
              className="inline-flex items-center gap-1.5 rounded-lg border border-line px-3 py-2 text-sm text-ink hover:bg-surface-2 disabled:opacity-50">
              <ArrowCounterClockwise size={14} aria-hidden="true" /> Reset
            </button>
          )}
          {DEMO && (
            <a href="https://github.com/yashasviyadav30/complaint-replay" target="_blank" rel="noreferrer"
              className="inline-flex items-center gap-1.5 whitespace-nowrap rounded-lg bg-accent px-3 py-2 text-sm font-semibold text-accent-ink hover:brightness-110">
              Run It Live <ArrowSquareOut size={14} aria-hidden="true" />
            </a>
          )}
          {!DEMO && <button type="button" onClick={onBreak} disabled={busy || !live}
            className="inline-flex items-center gap-1.5 whitespace-nowrap rounded-lg bg-accent px-3 py-2 text-sm font-semibold text-accent-ink transition-transform hover:brightness-110 active:scale-[0.98] disabled:opacity-50">
            <DiceFive size={16} weight="bold" aria-hidden="true" /> Break It
          </button>}
        </div>
      </div>
    </header>
  );
}
