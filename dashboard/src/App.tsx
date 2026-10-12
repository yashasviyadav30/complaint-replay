import { MotionConfig } from "motion/react";
import { useCallback, useEffect, useState } from "react";
import { breakShop, getCases, getLive, resetShop, type Live } from "./api";
import { Board } from "./components/Board";
import { CaseDetail } from "./components/CaseDetail";
import { TopBar } from "./components/TopBar";
import type { Case } from "./types";

const POLL_MS = 2000;

export default function App() {
  const [cases, setCases] = useState<Case[] | null>(null);
  const [live, setLive] = useState<Live | null>(null);
  const [openId, setOpenId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [now, setNow] = useState(Date.now());

  const refresh = useCallback(async () => {
    try {
      const [c, l] = await Promise.all([getCases(), getLive()]);
      setCases(c);
      setLive(l);
      setError(null);
    } catch {
      setError("Can't reach the Complaint Replay service. Is it running on port 8200?");
    }
    setNow(Date.now());
  }, []);

  useEffect(() => {
    refresh();
    const timer = setInterval(refresh, POLL_MS);
    return () => clearInterval(timer);
  }, [refresh]);

  const act = async (fn: () => Promise<Live>, message: string) => {
    setBusy(true);
    try {
      setLive(await fn());
      setNotice(message);
    } catch {
      setError("That didn't work. Check the service logs.");
    } finally {
      setBusy(false);
    }
  };

  const open = cases?.find((c) => c.id === openId);

  return (
    <MotionConfig reducedMotion="user">
      <div className="min-h-[100dvh]">
        <TopBar
          live={live}
          busy={busy}
          onBreak={() => act(breakShop, "A secret bug is planted in the shop. Use it like a customer and complain when something goes wrong.")}
          onReset={() => act(resetShop, "The shop is clean again.")}
        />
        <main className="mx-auto max-w-[1400px] px-4 py-8 md:px-8">
          {error && <p role="alert" className="mb-6 rounded-lg border border-accent p-3 text-sm text-accent">{error}</p>}
          {notice && !error && (
            <p role="status" className="mb-6 flex items-start justify-between gap-4 rounded-lg border border-line bg-surface p-3 text-sm text-ink">
              {notice}
              <button type="button" onClick={() => setNotice(null)} className="shrink-0 text-xs text-muted hover:text-ink">Dismiss</button>
            </p>
          )}

          {cases === null && !error && <BoardSkeleton />}
          {cases?.length === 0 && <EmptyState shopUrl={live?.url} />}
          {cases && cases.length > 0 && <Board cases={cases} now={now} onOpen={setOpenId} />}
        </main>
        {open && <CaseDetail c={open} onClose={() => setOpenId(null)} />}
      </div>
    </MotionConfig>
  );
}

function EmptyState({ shopUrl }: { shopUrl?: string }) {
  return (
    <section className="max-w-xl py-16">
      <h1 className="text-3xl font-semibold tracking-tight text-ink md:text-4xl">No complaints yet.</h1>
      <p className="mt-3 text-base leading-relaxed text-muted">
        Press Break it to plant a secret bug, then use the shop like a customer. Complain with the
        Report a problem button, or just get frustrated. Every case lands here.
      </p>
      {shopUrl && (
        <a href={shopUrl} target="_blank" rel="noreferrer" className="mt-6 inline-block text-sm font-semibold text-accent hover:underline">
          Open the shop
        </a>
      )}
    </section>
  );
}

function BoardSkeleton() {
  return (
    <div className="grid grid-cols-1 gap-6 md:grid-cols-2 xl:grid-cols-4" aria-hidden="true">
      {[0, 1, 2, 3].map((i) => (
        <div key={i} className="grid gap-3">
          <div className="h-6 w-24 animate-pulse rounded bg-surface-2" />
          <div className="h-32 animate-pulse rounded-xl bg-surface-2" />
        </div>
      ))}
    </div>
  );
}
