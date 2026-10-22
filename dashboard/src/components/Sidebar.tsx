import { ArrowCounterClockwise, ArrowSquareOut, Bug, Kanban, Plus, Plugs } from "@phosphor-icons/react";
import { DEMO, type Live } from "../api";
import type { Me, Project } from "../types";

export type View = "cases" | "setup" | "new";

interface Props {
  me: Me | null;
  projects: Project[];
  project: Project | null;
  view: View;
  live: Live | null;
  busy: boolean;
  onProject: (id: string) => void;
  onView: (v: View) => void;
  onBreak: () => void;
  onReset: () => void;
}

const NAV: { id: View; label: string; icon: typeof Kanban }[] = [
  { id: "cases", label: "Cases", icon: Kanban },
  { id: "setup", label: "Set Up", icon: Plugs },
];

export function Sidebar({ me, projects, project, view, live, busy, onProject, onView, onBreak, onReset }: Props) {
  const isDemo = project?.mode === "local";
  return (
    <aside className="border-b border-line bg-surface lg:sticky lg:top-0 lg:flex lg:h-[100dvh] lg:flex-col lg:border-b-0 lg:border-r">
      <div className="flex items-center justify-between gap-3 px-4 py-4 lg:px-5 lg:py-5">
        <p className="inline-flex items-center gap-2 font-semibold tracking-tight text-ink">
          <img src={`${import.meta.env.BASE_URL}favicon.svg`} width={24} height={24} alt="" className="rounded-md" />
          Complaint Replay
        </p>
      </div>

      <div className="grid gap-4 px-4 pb-4 lg:flex-1 lg:content-start lg:px-5">
        <div className="grid gap-1.5">
          <label htmlFor="project" className="text-xs font-medium text-muted">Project</label>
          <div className="flex gap-2">
            <select
              id="project"
              value={project?.id ?? ""}
              onChange={(e) => onProject(e.target.value)}
              className="min-w-0 flex-1 rounded-lg border border-line bg-bg px-3 py-2 text-sm text-ink"
            >
              {projects.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
            </select>
            {!DEMO && (
              <button type="button" onClick={() => onView("new")} aria-label="New Project" title="New Project"
                className={`rounded-lg border px-2.5 text-ink hover:bg-surface-2 ${view === "new" ? "border-accent" : "border-line"}`}>
                <Plus size={16} weight="bold" aria-hidden="true" />
              </button>
            )}
          </div>
          {project?.repo && (
            <a href={`https://github.com/${project.repo}`} target="_blank" rel="noreferrer"
              className="truncate font-mono text-[11px] text-muted hover:text-ink" translate="no">{project.repo}</a>
          )}
        </div>

        <nav aria-label="Sections" className="flex gap-1 lg:grid">
          {NAV.map(({ id, label, icon: Icon }) => (
            <button key={id} type="button" onClick={() => onView(id)} aria-current={view === id ? "page" : undefined}
              className={`inline-flex items-center gap-2 rounded-lg px-3 py-2 text-sm transition-colors ${
                view === id ? "bg-surface-2 font-semibold text-ink" : "text-muted hover:bg-surface-2 hover:text-ink"}`}>
              <Icon size={16} weight={view === id ? "fill" : "regular"} aria-hidden="true" /> {label}
            </button>
          ))}
        </nav>

        {isDemo && !DEMO && (
          <div className="grid gap-2 rounded-xl border border-line bg-bg p-3">
            <p className="text-xs leading-relaxed text-muted">
              The built-in demo shop. Turn on one of its known bugs, use the shop, and report the problem.
            </p>
            <div className="flex flex-wrap gap-2">
              <button type="button" onClick={onBreak} disabled={busy}
                className="inline-flex items-center gap-1.5 rounded-lg bg-accent px-3 py-2 text-sm font-semibold text-accent-ink hover:opacity-90 active:scale-[0.98] disabled:opacity-50">
                <Bug size={14} weight="bold" aria-hidden="true" /> Turn on a bug
              </button>
              {live?.broken && (
                <button type="button" onClick={onReset} disabled={busy}
                  className="inline-flex items-center gap-1.5 rounded-lg border border-line px-3 py-2 text-sm text-ink hover:bg-surface-2 disabled:opacity-50">
                  <ArrowCounterClockwise size={14} aria-hidden="true" /> Reset
                </button>
              )}
              {live?.url && (
                <a href={live.url} target="_blank" rel="noreferrer"
                  className="inline-flex items-center gap-1.5 rounded-lg px-3 py-2 text-sm text-muted hover:bg-surface-2 hover:text-ink">
                  Open Shop <ArrowSquareOut size={14} aria-hidden="true" />
                </a>
              )}
            </div>
          </div>
        )}
      </div>

      <footer className="hidden border-t border-line px-5 py-4 text-xs text-muted lg:block">
        {me?.login_enabled && me.login ? (
          <p className="flex items-center justify-between gap-2">
            <span>Signed in as <span className="font-medium text-ink">{me.login}</span></span>
            <a href="/auth/logout" className="hover:text-ink">Sign out</a>
          </p>
        ) : (
          <p>{DEMO ? "Recorded demo, read-only" : "Self-hosted, single team"}</p>
        )}
      </footer>
    </aside>
  );
}
