import { Link } from "react-router-dom";
import { Activity, ArrowRight, ArrowUpRight, Boxes, CheckCircle2, CircleAlert, Clock3, Cpu, GitPullRequest, Plus, Workflow } from "lucide-react";
import { api } from "@/api/client";
import type { DashboardData, HealthReport, TaskSummary } from "@/api/types";
import { useAsync } from "@/hooks/useAsync";
import { formatDate, relativeTime, statusLabel } from "@/lib/format";
import { PageHeader } from "@/components/PageHeader";
import { Section } from "@/components/Section";
import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { Skeleton } from "@/components/Loading";
import { StatusBadge } from "@/components/StatusBadge";

const ACTIVE = new Set(["CREATED", "CONTEXT_COLLECTION", "PLANNING", "PLAN_REVIEW", "READY_FOR_EXECUTION", "EXECUTING", "AUTOMATED_VALIDATION", "AI_REVIEW", "REPLANNING", "DOCUMENTATION", "DEPLOYING"]);

function Metric({ label, value, icon: Icon, detail, tone = "ink", to }: { label: string; value: number | string; icon: typeof Activity; detail?: string; tone?: "ink" | "amber" | "blue" | "green" | "red"; to?: string }) {
  const tones = { ink: "bg-ink-100 text-ink-700", amber: "bg-amber-100 text-amber-700", blue: "bg-sky-100 text-sky-700", green: "bg-emerald-100 text-emerald-700", red: "bg-red-100 text-red-700" };
  const body = <div className="card group p-4 transition hover:shadow-md sm:p-5"><div className="flex items-start justify-between"><div className={`flex h-9 w-9 items-center justify-center rounded-lg ${tones[tone]}`}><Icon className="h-[17px] w-[17px]" /></div>{to ? <ArrowUpRight className="h-4 w-4 text-ink-300 transition group-hover:text-ink-600" /> : null}</div><p className="mt-4 text-2xl font-bold tracking-tight text-ink-950">{value}</p><p className="mt-0.5 text-xs font-medium text-ink-500">{label}</p>{detail ? <p className="mt-2 text-[10px] text-ink-400">{detail}</p> : null}</div>;
  return to ? <Link to={to}>{body}</Link> : body;
}

export function DashboardPage() {
  const dashboard = useAsync<DashboardData>(() => api.get("/dashboard"), [], { pollMs: 30_000 });
  const health = useAsync<HealthReport>(() => api.get("/health/ready"), [], { pollMs: 60_000 });
  const tasks = useAsync<{ items: TaskSummary[]; total: number; page: number; page_size: number }>(() => api.get("/tasks", { page: 1, page_size: 7 }), [], { pollMs: 30_000 });

  if (dashboard.error && !dashboard.data) return <><PageHeader eyebrow="Factory control plane" title="Overview" /><ErrorState message={dashboard.error} retry={dashboard.refresh} /></>;
  const data = dashboard.data;
  const activeTasks = data?.tasks.active ?? 0;
  const createdLastWeek = data?.activity_7d.reduce((sum, day) => sum + day.count, 0) ?? 0;
  const maxActivity = Math.max(1, ...(data?.activity_7d.map((d) => d.count) ?? [1]));

  return <div className="animate-fade-in">
    <PageHeader eyebrow="Factory control plane" title="Overview" description="Your production pipeline at a glance. Workflows remain persistent and traceable from request through release." actions={<><Link to="/projects" className="btn-secondary"><Plus className="h-4 w-4" />New project</Link><Link to="/tasks/new" className="btn-primary"><Plus className="h-4 w-4" />Create task</Link></>} />
    <div className="mb-6 flex items-center gap-2 rounded-lg border border-emerald-200 bg-emerald-50/70 px-3.5 py-2.5 text-xs"><span className="relative flex h-2 w-2"><span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-60"/><span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-500"/></span><span className="font-semibold text-emerald-800">Factory operational</span><span className="text-emerald-700/70">·</span><span className="text-emerald-800/80">{data?.providers.healthy ?? "—"} of {data?.providers.total ?? "—"} providers connected</span><span className="ml-auto hidden text-emerald-700/60 sm:inline">{health.data?.status === "PASSED" ? "API · Database · Storage ready" : health.data?.status === "FAILED" ? "Readiness checks report an issue" : "Checking system health…"}</span><span className="ml-auto sm:hidden"><StatusBadge status={health.data?.status ?? "UNKNOWN"} showDot={false} /></span></div>

    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-5">
      <Metric label="Projects" value={data?.projects.total ?? "—"} icon={Boxes} detail={`${data?.projects.active ?? 0} active`} to="/projects" />
      <Metric label="Active tasks" value={activeTasks} icon={Workflow} detail="Running through production pipeline" tone="blue" to="/tasks?status=EXECUTING" />
      <Metric label="Awaiting approval" value={data?.tasks.awaiting_approval ?? "—"} icon={GitPullRequest} detail="Human review required" tone="amber" to="/approvals" />
      <Metric label="Completed" value={data?.tasks.completed ?? "—"} icon={CheckCircle2} detail={`${createdLastWeek} tasks created in 7 days`} tone="green" to="/tasks?status=RELEASE_READY" />
      <Metric label="Failed / blocked" value={(data?.tasks.failed ?? 0) + (data?.tasks.blocked ?? 0)} icon={CircleAlert} detail={`${data?.tasks.failed ?? 0} failed · ${data?.tasks.blocked ?? 0} blocked`} tone="red" to="/tasks?status=FAILED" />
    </div>

    <div className="mt-6 grid gap-5 xl:grid-cols-[1.55fr_1fr]">
      <Section title="Recent production activity" description="Latest requests across your accessible projects" padded={false} actions={<Link to="/tasks" className="btn-ghost btn-sm">All tasks <ArrowRight className="h-3 w-3" /></Link>}>
        {tasks.loading && !tasks.data ? <div className="space-y-3 p-5"><Skeleton className="h-9"/><Skeleton className="h-9"/><Skeleton className="h-9"/></div> : tasks.data?.items.length ? <div className="table-wrap rounded-none border-0"><table className="table min-w-[560px]"><thead><tr><th>Task</th><th>Project</th><th>Stage</th><th>Updated</th></tr></thead><tbody>{tasks.data.items.map((task) => <tr key={task.id}><td><Link to={`/tasks/${task.id}`} className="block max-w-[230px] truncate font-semibold text-ink-900 hover:text-amber-700">{task.title}</Link><span className="mt-0.5 block font-mono text-[10px] text-ink-400">{task.id.slice(0, 8)}</span></td><td><Link to={`/projects/${task.project_id}`} className="text-xs text-ink-600 hover:text-ink-950">{task.project_name}</Link></td><td><StatusBadge status={task.status} pulse={ACTIVE.has(task.status)} /></td><td className="whitespace-nowrap text-xs text-ink-400" title={formatDate(task.updated_at)}>{relativeTime(task.updated_at)}</td></tr>)}</tbody></table></div> : <EmptyState title="No production activity yet" description="Create a task to start the planning, execution, review, and documentation pipeline." action={<Link className="btn-primary btn-sm" to="/tasks/new"><Plus className="h-3.5 w-3.5"/>Create a task</Link>} compact />}
      </Section>

      <div className="grid gap-5 sm:grid-cols-2 xl:grid-cols-1">
        <Section title="Provider health" description="Registered provider connectivity" padded={false} actions={<Link to="/providers" className="btn-ghost btn-sm">Manage <ArrowRight className="h-3 w-3" /></Link>}>
          {data?.providers.items.length ? <div className="divide-y divide-ink-100">{data.providers.items.slice(0, 5).map((provider) => <div key={provider.id} className="flex items-center gap-3 px-5 py-3"><div className="flex h-8 w-8 items-center justify-center rounded-lg bg-ink-50 text-ink-500"><Cpu className="h-4 w-4" /></div><div className="min-w-0 flex-1"><p className="truncate text-xs font-semibold text-ink-800">{provider.name}</p><p className="truncate text-[10px] text-ink-400">{statusLabel(provider.type)} · {provider.enabled ? relativeTime(provider.last_checked_at) : "disabled"}</p></div><StatusBadge status={provider.enabled ? provider.status : "DISABLED"} /></div>)}</div> : <EmptyState title="No providers configured" description="Register a provider and test its connection before assigning models." action={<Link to="/providers" className="btn-secondary btn-sm">Configure providers</Link>} compact />}
        </Section>

        <Section title="Quality gate results" description="Across persisted production attempts" padded={false}>
          <div className="p-5"><div className="mb-4 flex items-end justify-between"><div><p className="text-3xl font-bold tracking-tight text-ink-950">{data?.gates.passed ?? 0}</p><p className="text-[11px] text-ink-500">passed checks</p></div><div className="text-right"><p className="text-xs font-semibold text-ink-700">{data?.gates.failed ?? 0} failed</p><p className="text-[10px] text-ink-400">{data?.gates.warning ?? 0} warning · {data?.gates.not_configured ?? 0} not configured</p></div></div><div className="flex h-2 overflow-hidden rounded-full bg-ink-100"><div className="bg-emerald-500" style={{ width: `${data?.gates.passed ? (data.gates.passed / Math.max(1, Object.values(data.gates.by_status).reduce((a,b)=>a+b,0))) * 100 : 0}%` }} /><div className="bg-red-400" style={{ width: `${data?.gates.failed ? (data.gates.failed / Math.max(1, Object.values(data.gates.by_status).reduce((a,b)=>a+b,0))) * 100 : 0}%` }} /><div className="bg-amber-400" style={{ width: `${data?.gates.warning ? (data.gates.warning / Math.max(1, Object.values(data.gates.by_status).reduce((a,b)=>a+b,0))) * 100 : 0}%` }} /></div><div className="mt-3 flex items-center justify-between text-[10px] text-ink-400"><span className="flex items-center gap-1"><span className="h-1.5 w-1.5 rounded-full bg-emerald-500"/>Passed</span><span className="flex items-center gap-1"><span className="h-1.5 w-1.5 rounded-full bg-red-400"/>Failed</span><span className="flex items-center gap-1"><span className="h-1.5 w-1.5 rounded-full bg-amber-400"/>Warnings</span></div></div>
        </Section>
      </div>
    </div>

    <div className="mt-5 grid gap-5 lg:grid-cols-[1.25fr_1fr]">
      <Section title="Task volume" description="Requests created over the last seven days" actions={<span className="chip border-ink-200 bg-ink-50 text-ink-500"><Clock3 className="h-3 w-3"/>7 days</span>}>
        <div className="flex h-[132px] items-end gap-2 sm:gap-3">{(data?.activity_7d ?? []).map((day) => { const height = Math.max(6, (day.count / maxActivity) * 100); const today = day.date === new Date().toISOString().slice(0,10); return <div key={day.date} className="group flex h-full min-w-0 flex-1 flex-col justify-end"><div className="relative flex h-full items-end"><div className={`w-full rounded-t-md transition-all group-hover:opacity-80 ${today ? "bg-amber-500" : "bg-ink-200"}`} style={{ height: `${height}%` }} title={`${day.count} tasks · ${formatDate(day.date, false)}`} /><span className="absolute -top-5 left-1/2 hidden -translate-x-1/2 text-[10px] font-semibold text-ink-600 group-hover:block">{day.count}</span></div><span className={`mt-2 truncate text-center text-[9px] ${today ? "font-bold text-ink-800" : "text-ink-400"}`}>{new Date(`${day.date}T12:00:00`).toLocaleDateString(undefined, { weekday: "short" })}</span></div>; })}</div>
      </Section>
      <Section title="Pipeline status" description="Current workload by stage" padded={false}>
        <div className="divide-y divide-ink-100">{Object.entries(data?.tasks.by_status ?? {}).sort((a,b) => b[1]-a[1]).slice(0, 5).map(([stage, count]) => <div key={stage} className="flex items-center gap-3 px-5 py-2.5"><span className="h-1.5 w-1.5 rounded-full bg-amber-500"/><span className="flex-1 text-xs text-ink-600">{statusLabel(stage)}</span><span className="text-xs font-semibold tabular-nums text-ink-800">{count}</span><span className="w-20 overflow-hidden rounded-full bg-ink-100"><span className="block h-1 rounded-full bg-amber-400" style={{ width: `${Math.max(8, (count / Math.max(1, activeTasks)) * 100)}%` }}/></span></div>)}{!Object.keys(data?.tasks.by_status ?? {}).length ? <div className="px-5 py-8 text-center text-xs text-ink-400">No tasks to report.</div> : null}</div>
      </Section>
    </div>
  </div>;
}
