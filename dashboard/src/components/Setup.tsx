import { Check, Copy, PaperPlaneTilt } from "@phosphor-icons/react";
import { useState } from "react";
import { DEMO, createProject, sendTestReport } from "../api";
import type { Me, Project, ProjectIn } from "../types";

function CopyBlock({ code, label }: { code: string; label: string }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    await navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 1600);
  };
  return (
    <div className="relative">
      <pre translate="no" aria-label={label}
        className="overflow-x-auto rounded-lg border border-line bg-surface-2 p-3 pr-12 font-mono text-[12px] leading-relaxed text-ink">{code}</pre>
      <button type="button" onClick={copy} aria-label={copied ? "Copied" : `Copy ${label}`}
        className="absolute right-2 top-2 rounded-md p-1.5 text-muted hover:bg-surface hover:text-ink">
        {copied ? <Check size={16} weight="bold" className="text-ok" /> : <Copy size={16} />}
      </button>
    </div>
  );
}

function Step({ n, title, done, children }: { n: number; title: string; done?: boolean; children: React.ReactNode }) {
  return (
    <li className="grid grid-cols-[2rem_1fr] gap-x-4">
      <span aria-hidden="true"
        className={`grid size-8 place-items-center rounded-full font-mono text-sm ${done ? "bg-ok text-surface" : "border border-line text-muted"}`}>
        {done ? <Check size={14} weight="bold" /> : n}
      </span>
      <div className="grid min-w-0 gap-3 pb-8">
        <h2 className="pt-1 text-base font-semibold text-ink">{title}</h2>
        {children}
      </div>
    </li>
  );
}

const code = "font-mono text-[12px]";

export function SetupSteps({ project, me, onTested }: { project: Project; me: Me | null; onTested: () => void }) {
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const test = async () => {
    setError(null);
    try {
      await sendTestReport(project.key, "Test from setup: the Pay button does nothing on my phone.");
      setSent(true);
      onTested();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not send the test complaint.");
    }
  };

  return (
    <section className="max-w-3xl">
      <h1 className="text-2xl font-semibold tracking-tight text-ink md:text-3xl">Set Up {project.name}</h1>
      <p className="mt-2 max-w-[65ch] text-sm leading-relaxed text-muted">
        Four steps, about ten minutes. Complaints are replayed inside your own GitHub Actions, so your code never leaves your CI.
      </p>
      <ol className="mt-8">
        <Step n={1} title="Add the Widget to Your Site">
          <p className="text-sm text-muted">One script tag, before the closing body tag. It speaks your users' language and never reads what they type into your forms.</p>
          <CopyBlock label="widget script tag" code={`<script src="${window.location.origin}/widget.js" data-project="${project.key}" defer></script>`} />
        </Step>
        <Step n={2} title="Add the Workflow to Your Repo">
          <p className="text-sm text-muted">
            Run this in the repo. It writes <code translate="no" className={code}>complaint-replay.toml</code>, which says how to start
            your app, and a GitHub workflow. Then add <code translate="no" className={code}>NEBIUS_API_KEY</code> as a repository secret.
          </p>
          <CopyBlock label="setup command" code="uvx --from git+https://github.com/yashasviyadav30/complaint-replay crp init" />
          <p className="text-sm text-muted">
            In the repo's Settings, under Actions, turn on <span className="text-ink">Allow GitHub Actions to create and approve pull requests</span>.
          </p>
        </Step>
        <Step n={3} title="Connect GitHub" done={!!project.repo && !!me?.github_app}>
          {!project.repo && (
            <p className="text-sm text-muted">
              No repo is linked, so complaints are only collected. Replay one by hand with <code translate="no" className={code}>crp replay</code>.
            </p>
          )}
          {project.repo && me?.github_app && (
            <a href={`https://github.com/apps/${me.github_app}/installations/new`} target="_blank" rel="noreferrer"
              className="inline-flex w-fit items-center gap-2 rounded-lg bg-accent px-4 py-2 text-sm font-semibold text-accent-ink hover:opacity-90">
              Install on {project.repo}
            </a>
          )}
          {project.repo && !me?.github_app && (
            <p className="text-sm text-muted">
              This server has no GitHub App yet. <a href="/setup/github-app" className="text-accent hover:underline">Create one in one click</a>,
              or set <code translate="no" className={code}>GITHUB_TOKEN</code> on the server for a single team.
            </p>
          )}
        </Step>
        <Step n={4} title="Send a Test Complaint" done={sent}>
          <p className="text-sm text-muted">It arrives as a phone user on a slow 3G network. Watch it move across the board.</p>
          <button type="button" onClick={test} disabled={DEMO || sent}
            className="inline-flex w-fit items-center gap-2 rounded-lg border border-line px-4 py-2 text-sm font-semibold text-ink hover:bg-surface-2 active:scale-[0.98] disabled:opacity-50">
            <PaperPlaneTilt size={16} aria-hidden="true" /> {sent ? "Sent" : "Send Test Complaint"}
          </button>
          {error && <p role="alert" className="text-sm text-accent">{error}</p>}
        </Step>
        {project.secret && (
          <Step n={5} title="Connect Your Other Tools">
            <p className="text-sm text-muted">
              Complaints that reach your support desk can come in too. Forward them from Zendesk, Intercom or an email
              bridge with this request. Keep the secret private.
            </p>
            <CopyBlock label="support inbox request" code={`curl -X POST ${window.location.origin}/api/v1/projects/${project.id}/inbox   -H "Authorization: Bearer ${project.secret}" -H "Content-Type: application/json"   -d '{"text": "The pay button does nothing on my phone", "language": "en"}'`} />
            <p className="text-sm text-muted">Sentry: add an issue alert with a webhook to this address, and new errors arrive as silent signals.</p>
            <CopyBlock label="Sentry webhook address" code={`${window.location.origin}/api/v1/projects/${project.id}/sentry?secret=${project.secret}`} />
          </Step>
        )}
      </ol>
    </section>
  );
}

const SECTORS: { id: ProjectIn["sector"]; label: string }[] = [
  { id: "general", label: "General" },
  { id: "ecommerce", label: "Shopping" },
  { id: "fintech", label: "Payments and banking" },
  { id: "public", label: "Government, health or education" },
];

export function NewProject({ onCreated }: { onCreated: (p: Project) => void }) {
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const submit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    setSaving(true);
    setError(null);
    try {
      onCreated(await createProject({
        name: String(f.get("name")).trim(),
        repo: String(f.get("repo")).trim(),
        origins: String(f.get("origins")).split(/[\s,]+/).filter(Boolean),
        sector: f.get("sector") as ProjectIn["sector"],
        retention_days: Number(f.get("retention")),
        screenshots: f.get("screenshots") === "on",
        notify_url: String(f.get("notify_url") ?? "").trim(),
      }));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not create the project.");
    } finally {
      setSaving(false);
    }
  };

  const field = "w-full rounded-lg border border-line bg-surface px-3 py-2 text-sm text-ink placeholder:text-muted";
  return (
    <section className="max-w-xl">
      <h1 className="text-2xl font-semibold tracking-tight text-ink md:text-3xl">New Project</h1>
      <p className="mt-2 text-sm leading-relaxed text-muted">One project per website. The next screen gives you its widget key.</p>
      <form onSubmit={submit} className="mt-8 grid gap-5">
        <div className="grid gap-2">
          <label htmlFor="name" className="text-sm font-medium text-ink">Name</label>
          <input id="name" name="name" required maxLength={80} autoComplete="off" className={field} placeholder="Storefront…" />
        </div>
        <div className="grid gap-2">
          <label htmlFor="repo" className="text-sm font-medium text-ink">GitHub repo</label>
          <input id="repo" name="repo" pattern="[\w.\-]+/[\w.\-]+" autoComplete="off" spellCheck={false} className={`${field} font-mono`}
            placeholder="your-org/your-app…" aria-describedby="repo-help" />
          <p id="repo-help" className="text-xs text-muted">Where fixes arrive as pull requests. Leave empty to only collect complaints.</p>
        </div>
        <div className="grid gap-2">
          <label htmlFor="origins" className="text-sm font-medium text-ink">Sites allowed to send complaints</label>
          <input id="origins" name="origins" autoComplete="off" spellCheck={false} className={`${field} font-mono`}
            placeholder="https://shop.example.com…" aria-describedby="origins-help" />
          <p id="origins-help" className="text-xs text-muted">Separate with spaces. Empty means any site with your key.</p>
        </div>
        <div className="grid gap-5 sm:grid-cols-2 sm:gap-4">
          <div className="grid gap-2">
            <label htmlFor="sector" className="text-sm font-medium text-ink">Kind of product</label>
            <select id="sector" name="sector" defaultValue="general" className={field}>
              {SECTORS.map((s) => <option key={s.id} value={s.id}>{s.label}</option>)}
            </select>
          </div>
          <div className="grid gap-2">
            <label htmlFor="retention" className="text-sm font-medium text-ink">Keep complaints for</label>
            <select id="retention" name="retention" defaultValue="30" className={field}>
              {[7, 30, 90, 365].map((d) => <option key={d} value={d}>{d} days</option>)}
            </select>
          </div>
        </div>
        <div className="grid gap-2">
          <label htmlFor="notify_url" className="text-sm font-medium text-ink">Team chat webhook</label>
          <input id="notify_url" name="notify_url" type="url" pattern="https://.*" autoComplete="off" spellCheck={false}
            className={`${field} font-mono`} placeholder="https://hooks.slack.com/services/…" aria-describedby="notify-help" />
          <p id="notify-help" className="text-xs text-muted">Slack, Mattermost or Discord (add /slack). Told when a bug is proven, fixed, or needs a person.</p>
        </div>
        <label className="flex items-center gap-2 text-sm text-ink">
          <input type="checkbox" name="screenshots" defaultChecked className="size-4 accent-[var(--accent)]" />
          Keep screenshots of what the user saw
        </label>
        {error && <p role="alert" tabIndex={-1} ref={(el) => el?.focus()} className="text-sm text-accent">{error}</p>}
        <button type="submit" disabled={saving}
          className="w-fit rounded-lg bg-accent px-4 py-2 text-sm font-semibold text-accent-ink hover:opacity-90 active:scale-[0.98] disabled:opacity-50">
          {saving ? "Creating…" : "Create Project"}
        </button>
      </form>
    </section>
  );
}
