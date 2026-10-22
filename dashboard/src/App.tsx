import { GithubLogo } from "@phosphor-icons/react";
import { MotionConfig } from "motion/react";
import { useCallback, useEffect, useState } from "react";
import { DEMO, breakShop, getCases, getLive, getMe, getProjects, resetShop, type Live } from "./api";
import { Board } from "./components/Board";
import { CaseDetail } from "./components/CaseDetail";
import { NewProject, SetupSteps } from "./components/Setup";
import { Sidebar, type View } from "./components/Sidebar";
import type { Case, Me, Project } from "./types";

const POLL_MS = 2000;
const PROJECT_KEY = "crp-project";

function remembered(): string | null {
  try { return localStorage.getItem(PROJECT_KEY); } catch { return null; }
}

function viewFromHash(): View {
  const h = location.hash.slice(1);
  return h === "setup" || h === "new" ? h : "cases";
}

function remember(id: string) {
  try { localStorage.setItem(PROJECT_KEY, id); } catch { /* private mode: fine */ }
}

export default function App() {
  const [me, setMe] = useState<Me | null>(null);
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectId, setProjectId] = useState<string | null>(remembered());
  const [view, setViewState] = useState<View>(viewFromHash());
  const [cases, setCases] = useState<Case[] | null>(null);
  const [live, setLive] = useState<Live | null>(null);
  const [openId, setOpenId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(
    DEMO ? "Read-only demo: real replays of the bugs planted in our demo shop, with their films, evidence and fixes. To run it on your own app, see the README on GitHub." : null,
  );
  const [busy, setBusy] = useState(false);
  const [now, setNow] = useState(() => Date.now());

  const project = projects.find((p) => p.id === projectId) ?? projects[0] ?? null;

  useEffect(() => {
    (async () => {
      try {
        const who = await getMe();
        setMe(who);
        if (!who.login_enabled || who.login) setProjects(await getProjects());
      } catch {
        setError("Can't reach the Complaint Replay service. Is it running?");
      }
    })();
  }, []);

  const refresh = useCallback(async () => {
    if (!project) return;
    try {
      const [c, l] = await Promise.all([getCases(project.id), project.mode === "local" ? getLive() : Promise.resolve(null)]);
      setCases(c);
      setLive(l);
      setError(null);
    } catch {
      setError("Lost contact with the service. Retrying.");
    }
    setNow(Date.now());
  }, [project]);

  useEffect(() => {
    // Polling the service is syncing with an outside system; state is set only after each request resolves.
    // oxlint-disable-next-line react/set-state-in-effect
    refresh();
    if (DEMO) return; // recorded data never changes
    const timer = setInterval(refresh, POLL_MS);
    return () => clearInterval(timer);
  }, [refresh]);

  const setView = (v: View) => {
    setViewState(v);
    history.replaceState(null, "", v === "cases" ? location.pathname : `#${v}`);
  };

  const pick = (id: string) => {
    setProjectId(id);
    remember(id);
    setOpenId(null);
    setCases(null);
  };

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

  if (me?.login_enabled && !me.login) return <SignIn />;

  const open = cases?.find((c) => c.id === openId);
  return (
    <MotionConfig reducedMotion="user">
      <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-30 focus:rounded-lg focus:bg-surface focus:px-4 focus:py-2 focus:text-sm">
        Skip to Content
      </a>
      <div className="min-h-[100dvh] lg:grid lg:grid-cols-[17rem_1fr]" inert={!!open}>
        <Sidebar
          me={me} projects={projects} project={project} view={view} live={live} busy={busy}
          onProject={pick} onView={setView}
          onBreak={() => act(breakShop, "One of the demo shop's known bugs is now on. Use the shop as a customer would and report what goes wrong.")}
          onReset={() => act(resetShop, "The shop is clean again.")}
        />
        <main id="main" tabIndex={-1} className="min-w-0 px-4 py-8 md:px-8 lg:py-10">
          {error && <p role="alert" className="mb-6 rounded-lg border border-accent p-3 text-sm text-accent">{error}</p>}
          {notice && !error && view === "cases" && (
            <p role="status" className="mb-6 flex items-start justify-between gap-4 rounded-lg border border-line bg-surface p-3 text-sm text-ink">
              {notice}
              <button type="button" onClick={() => setNotice(null)} className="shrink-0 text-xs text-muted hover:text-ink">Dismiss</button>
            </p>
          )}

          {view === "new" && (
            <NewProject onCreated={(p) => { setProjects((all) => [...all, p]); pick(p.id); setView("setup"); }} />
          )}
          {view === "setup" && project && <SetupSteps project={project} me={me} onTested={refresh} />}
          {view === "cases" && project && (
            <>
              <h1 className="text-2xl font-semibold tracking-tight text-ink">{project.name}</h1>
              <p className="mb-8 mt-1 text-sm text-muted">{cases ? summary(cases) : " "}</p>
              {cases === null && !error && <BoardSkeleton />}
              {cases?.length === 0 && <EmptyState project={project} shopUrl={live?.url} onSetup={() => setView("setup")} />}
              {cases && cases.length > 0 && <Board cases={cases} now={now} onOpen={setOpenId} />}
            </>
          )}
        </main>
      </div>
      {open && <CaseDetail c={open} onClose={() => setOpenId(null)} />}
    </MotionConfig>
  );
}

function SignIn() {
  return (
    <main className="grid min-h-[100dvh] place-items-center px-4">
      <section className="w-full max-w-sm">
        <h1 className="text-2xl font-semibold tracking-tight text-ink">Complaint Replay</h1>
        <p className="mt-2 text-sm leading-relaxed text-muted">
          Your users already told you what is broken. Sign in to see their complaints replayed, fixed and guarded.
        </p>
        <a href="/auth/login"
          className="mt-6 inline-flex items-center gap-2 rounded-lg bg-ink px-4 py-2.5 text-sm font-semibold text-bg hover:opacity-90 active:scale-[0.98]">
          <GithubLogo size={18} weight="fill" aria-hidden="true" /> Sign in with GitHub
        </a>
      </section>
    </main>
  );
}

function EmptyState({ project, shopUrl, onSetup }: { project: Project; shopUrl?: string; onSetup: () => void }) {
  if (project.mode === "local") {
    return (
      <section className="max-w-xl py-10">
        <h2 className="text-xl font-semibold tracking-tight text-ink">No complaints yet.</h2>
        <p className="mt-2 text-sm leading-relaxed text-muted">
          Turn on a bug in the built-in demo shop, then use the shop as a customer would and report the
          problem with its Report a problem button. Rage clicks and page errors are caught too. Every case lands here.
        </p>
        {shopUrl && (
          <a href={shopUrl} target="_blank" rel="noreferrer" className="mt-4 inline-block text-sm font-semibold text-accent hover:underline">
            Open Shop
          </a>
        )}
      </section>
    );
  }
  return (
    <section className="max-w-xl py-10">
      <h2 className="text-xl font-semibold tracking-tight text-ink">Nothing reported yet.</h2>
      <p className="mt-2 text-sm leading-relaxed text-muted">
        Add the widget to your site and send a test complaint. It shows up here within seconds.
      </p>
      <button type="button" onClick={onSetup}
        className="mt-4 rounded-lg bg-accent px-4 py-2 text-sm font-semibold text-accent-ink hover:opacity-90 active:scale-[0.98]">
        Set Up
      </button>
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

/** One line a team lead can read at a glance: how many complaints, and how many are now guarded. */
function summary(cases: Case[]): string {
  if (!cases.length) return "No complaints yet.";
  const people = cases.reduce((n, c) => n + (c.reports ?? 1), 0);
  const guarded = cases.filter((c) => c.stage === "guarded").length;
  const open = cases.filter((c) => !["guarded", "fixed", "not_a_bug"].includes(c.stage)).length;
  const plural = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`;
  return [`${plural(cases.length, "case", "cases")} from ${plural(people, "person", "people")}`,
    `${guarded} guarded by a test`, `${open} open`].join(", ") + ".";
}
