import { useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ArrowRight, Boxes, GitBranch, Plus, Search, X } from "lucide-react";
import { api } from "@/api/client";
import type { Project } from "@/api/types";
import { useAsync } from "@/hooks/useAsync";
import { formatDate, relativeTime } from "@/lib/format";
import { PageHeader } from "@/components/PageHeader";
import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { Loading } from "@/components/Loading";
import { StatusBadge } from "@/components/StatusBadge";
import { Modal } from "@/components/Modal";
import { FormField, TextArea, TextInput } from "@/components/FormField";
import { useToast } from "@/components/Toast";

export function ProjectsPage() {
  const nav = useNavigate();
  const { toast } = useToast();
  const state = useAsync<Project[]>(() => api.get("/projects"), [], { pollMs: 60_000 });
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("ACTIVE");
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState({ name: "", description: "", slug: "", repository_url: "", repository_token: "", default_branch: "main" });
  const projects = useMemo(() => (state.data ?? []).filter((p) => (statusFilter === "ALL" || p.status === statusFilter) && `${p.name} ${p.slug} ${p.description}`.toLowerCase().includes(search.toLowerCase())), [state.data, search, statusFilter]);
  const update = (key: keyof typeof form, value: string) => setForm((old) => ({ ...old, [key]: value }));

  const create = async (event: React.FormEvent) => {
    event.preventDefault(); setBusy(true);
    try {
      const payload: Record<string, unknown> = { name: form.name, description: form.description, default_branch: form.default_branch || "main" };
      if (form.slug.trim()) payload.slug = form.slug.trim();
      if (form.repository_url.trim()) { payload.repository_url = form.repository_url.trim(); if (form.repository_token) { payload.repository_auth_type = "token"; payload.repository_token = form.repository_token; } }
      const project = await api.post<Project>("/projects", payload);
      toast({ title: "Project created", description: `${project.name} is ready for configuration.`, tone: "success" });
      setOpen(false); nav(`/projects/${project.id}`);
    } catch (error) { toast({ title: "Could not create project", description: error instanceof Error ? error.message : "Request failed", tone: "error" }); }
    finally { setBusy(false); }
  };

  return <div className="animate-fade-in">
    <PageHeader eyebrow="Workspace management" title="Projects" description="Independent workspaces, engineering principles, Git connections, and environment configuration." actions={<button className="btn-primary" onClick={() => setOpen(true)}><Plus className="h-4 w-4"/>Create project</button>} />
    <div className="mb-5 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
      <div className="relative w-full sm:max-w-sm"><Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-400"/><input className="input pl-9 pr-9" placeholder="Search projects…" value={search} onChange={(e) => setSearch(e.target.value)}/>{search ? <button className="absolute right-3 top-1/2 -translate-y-1/2 text-ink-400 hover:text-ink-800" onClick={() => setSearch("")}><X className="h-3.5 w-3.5"/></button> : null}</div>
      <div className="flex items-center gap-1 rounded-lg border border-ink-200 bg-white p-1">{[["ACTIVE", "Active"], ["ARCHIVED", "Archived"], ["ALL", "All"]].map(([value, label]) => <button key={value} onClick={() => setStatusFilter(value)} className={`rounded-md px-3 py-1.5 text-xs font-medium transition ${statusFilter === value ? "bg-ink-950 text-white" : "text-ink-500 hover:bg-ink-100 hover:text-ink-900"}`}>{label}{value === "ACTIVE" ? <span className="ml-1.5 text-[10px] opacity-60">{state.data?.filter(p => p.status === "ACTIVE").length ?? "—"}</span> : null}</button>)}</div>
    </div>
    {state.loading && !state.data ? <Loading label="Loading projects"/> : state.error && !state.data ? <ErrorState message={state.error} retry={state.refresh}/> : projects.length ? <div className="grid gap-4 md:grid-cols-2 2xl:grid-cols-3">{projects.map((project) => <ProjectCard key={project.id} project={project}/>)}</div> : <div className="card"><EmptyState icon={Boxes} title={search ? "No matching projects" : `No ${statusFilter.toLowerCase()} projects`} description={search ? "Try a different search term." : "Create a project to establish its own isolated workspace and CALIPER engineering constitution."} action={!search && statusFilter !== "ARCHIVED" ? <button className="btn-primary btn-sm" onClick={() => setOpen(true)}><Plus className="h-3.5 w-3.5"/>Create project</button> : null}/></div>}

    <Modal open={open} onClose={() => setOpen(false)} title="Create a project" description="Set up an independent engineering workspace. Repository can be connected now or later." footer={<><button className="btn-secondary" onClick={() => setOpen(false)} disabled={busy}>Cancel</button><button className="btn-primary" form="new-project" disabled={busy}>{busy ? "Creating…" : "Create project"}</button></>}>
      <form id="new-project" onSubmit={(e) => void create(e)} className="grid gap-4 sm:grid-cols-2">
        <FormField label="Project name" required><TextInput required minLength={2} maxLength={200} autoFocus placeholder="e.g. Customer Portal" value={form.name} onChange={(e) => update("name", e.target.value)}/></FormField>
        <FormField label="Project slug" hint="Lowercase letters, numbers, and hyphens. Leave blank to generate automatically."><TextInput pattern="[a-z0-9][a-z0-9-]*" maxLength={80} placeholder="customer-portal" value={form.slug} onChange={(e) => update("slug", e.target.value)}/></FormField>
        <div className="sm:col-span-2"><FormField label="Description"><TextArea maxLength={20_000} rows={3} placeholder="What does this project do?" value={form.description} onChange={(e) => update("description", e.target.value)}/></FormField></div>
        <FormField label="Git repository URL" hint="HTTPS URL. Private repositories can use a scoped token."><TextInput type="url" placeholder="https://github.com/org/repository" value={form.repository_url} onChange={(e) => update("repository_url", e.target.value)}/></FormField>
        <FormField label="Default branch"><TextInput maxLength={200} placeholder="main" value={form.default_branch} onChange={(e) => update("default_branch", e.target.value)}/></FormField>
        {form.repository_url ? <div className="sm:col-span-2"><FormField label="Repository access token" hint="Optional. Encrypted before storage; never shown again. Use a narrowly scoped GitHub token."><TextInput type="password" autoComplete="new-password" maxLength={4096} placeholder="ghp_…" value={form.repository_token} onChange={(e) => update("repository_token", e.target.value)}/></FormField></div> : null}
      </form>
    </Modal>
  </div>;
}

function ProjectCard({ project }: { project: Project }) {
  return <Link to={`/projects/${project.id}`} className="card group block p-5 transition hover:-translate-y-0.5 hover:border-ink-300 hover:shadow-md"><div className="flex items-start justify-between"><div className="flex h-10 w-10 items-center justify-center rounded-xl border border-ink-200 bg-ink-50 text-ink-600 transition group-hover:border-amber-300 group-hover:bg-amber-50 group-hover:text-amber-700"><Boxes className="h-[18px] w-[18px]"/></div><StatusBadge status={project.status}/></div><div className="mt-4 flex items-start justify-between gap-2"><div className="min-w-0"><h2 className="truncate text-base font-bold text-ink-950 group-hover:text-amber-700">{project.name}</h2><p className="mt-0.5 font-mono text-[10px] text-ink-400">/{project.slug}</p></div><ArrowRight className="mt-1 h-4 w-4 shrink-0 text-ink-300 transition group-hover:translate-x-0.5 group-hover:text-ink-700"/></div><p className="mt-3 line-clamp-2 min-h-[40px] text-xs leading-5 text-ink-500">{project.description || "No description provided."}</p><div className="mt-4 flex flex-wrap items-center gap-x-4 gap-y-2 border-t border-ink-100 pt-3 text-[10px] text-ink-400"><span className="flex items-center gap-1.5"><GitBranch className="h-3 w-3"/>{project.default_branch}</span><span>{project.max_retries} retries</span><span className="ml-auto" title={formatDate(project.updated_at)}>{relativeTime(project.updated_at)}</span></div></Link>;
}
