import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Activity, ArrowRight, ClipboardList, Filter, Plus, Search, X } from "lucide-react";
import { api } from "@/api/client";
import type { Paginated, Project, TaskStatus, TaskSummary } from "@/api/types";
import { useAsync } from "@/hooks/useAsync";
import { formatDate, relativeTime, statusLabel, truncate } from "@/lib/format";
import { PageHeader } from "@/components/PageHeader";
import { StatusBadge } from "@/components/StatusBadge";
import { Loading } from "@/components/Loading";
import { ErrorState } from "@/components/ErrorState";
import { EmptyState } from "@/components/EmptyState";
import { Pagination } from "@/components/Pagination";

const statusOptions: TaskStatus[] = ["CREATED","CONTEXT_COLLECTION","PLANNING","PLAN_REVIEW","READY_FOR_EXECUTION","EXECUTING","AUTOMATED_VALIDATION","AI_REVIEW","REPLANNING","DOCUMENTATION","AWAITING_APPROVAL","RELEASE_READY","COMPLETED","FAILED","BLOCKED","CANCELLED"];

export function TasksPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [query, setQuery] = useState(searchParams.get("search") ?? "");
  const [page, setPage] = useState(1);
  const status = searchParams.get("status") ?? "";
  const projectId = searchParams.get("project_id") ?? "";
  const projects = useAsync<Project[]>(()=>api.get("/projects"),[]);
  const state = useAsync<Paginated<TaskSummary>>(()=>api.get("/tasks",{page,page_size:20,status:status||undefined,project_id:projectId||undefined,search:query.trim()||undefined}),[page,status,projectId,query.trim()],{pollMs:15000});
  useEffect(()=>{const timer=window.setTimeout(()=>{if(query!== (searchParams.get("search")??"")){const next=new URLSearchParams(searchParams);if(query.trim())next.set("search",query.trim());else next.delete("search");setSearchParams(next,{replace:true});setPage(1);}},280);return()=>window.clearTimeout(timer);},[query,searchParams,setSearchParams]);
  const setFilter=(key:string,value:string)=>{const next=new URLSearchParams(searchParams);if(value)next.set(key,value);else next.delete(key);setSearchParams(next);setPage(1);};
  const runningCount=useMemo(()=>state.data?.items.filter(t=>["PLANNING","EXECUTING","AI_REVIEW","AUTOMATED_VALIDATION","DOCUMENTATION"].includes(t.status)).length??0,[state.data]);
  return <div className="animate-fade-in">
    <PageHeader eyebrow="Production pipeline" title="Tasks" description="Track work from request through isolated implementation, deterministic gates, independent review, and human approval." actions={<Link to="/tasks/new" className="btn-primary"><Plus className="h-4 w-4"/>New task</Link>} />
    <div className="mb-5 flex flex-wrap items-center gap-3"><div className="relative min-w-[220px] flex-1 sm:max-w-sm"><Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-400"/><input className="input pl-9 pr-9" placeholder="Search tasks…" value={query} onChange={e=>setQuery(e.target.value)}/>{query?<button className="absolute right-3 top-1/2 -translate-y-1/2 text-ink-400" onClick={()=>setQuery("")} aria-label="Clear search"><X className="h-3.5 w-3.5"/></button>:null}</div><div className="relative"><Filter className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-ink-400"/><select className="input w-auto min-w-[170px] pl-9 pr-8" value={projectId} onChange={e=>setFilter("project_id",e.target.value)}><option value="">All projects</option>{(projects.data??[]).map(p=><option key={p.id} value={p.id}>{p.name}</option>)}</select></div><div className="relative"><Activity className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-ink-400"/><select className="input w-auto min-w-[180px] pl-9 pr-8" value={status} onChange={e=>setFilter("status",e.target.value)}><option value="">All statuses</option>{statusOptions.map(s=><option key={s} value={s}>{statusLabel(s)}</option>)}</select></div><div className="ml-auto hidden items-center gap-1.5 text-[10px] text-ink-400 sm:flex"><span className="h-1.5 w-1.5 animate-pulse rounded-full bg-emerald-500"/>Live · {runningCount} active on this page</div></div>
    {state.loading&&!state.data?<div className="card"><Loading label="Loading tasks"/></div>:state.error&&!state.data?<ErrorState message={state.error} retry={state.refresh}/>:state.data?.items.length?<div className="table-wrap"><table className="table min-w-[760px]"><thead><tr><th>Task</th><th>Project</th><th>Pipeline stage</th><th>Retries</th><th>Last update</th><th></th></tr></thead><tbody>{state.data.items.map(task=><tr key={task.id}><td><Link to={`/tasks/${task.id}`} className="block max-w-[320px] font-semibold text-ink-900 hover:text-amber-700">{truncate(task.title,80)}</Link><span className="mt-1 block max-w-[300px] truncate text-[10px] text-ink-400">{truncate(task.description,100)}</span></td><td><Link to={`/projects/${task.project_id}`} className="text-xs font-medium text-ink-600 hover:text-ink-950">{task.project_name}</Link></td><td><StatusBadge status={task.status} pulse={["PLANNING","EXECUTING","AI_REVIEW","AUTOMATED_VALIDATION","DOCUMENTATION","CONTEXT_COLLECTION"].includes(task.status)}/></td><td><span className="font-mono text-xs text-ink-600">{task.retry_count}<span className="text-ink-400"> / {task.max_retries}</span></span></td><td className="whitespace-nowrap text-xs text-ink-400" title={formatDate(task.updated_at)}>{relativeTime(task.updated_at)}</td><td><Link to={`/tasks/${task.id}`} className="btn-ghost btn-sm" aria-label={`Open ${task.title}`}><ArrowRight className="h-3.5 w-3.5"/></Link></td></tr>)}</tbody></table><Pagination page={state.data.page} pageSize={state.data.page_size} total={state.data.total} onChange={setPage}/></div>:<div className="card"><EmptyState icon={ClipboardList} title={query||status||projectId?"No matching tasks":"No tasks yet"} description={query||status||projectId?"Adjust the filters or search query to see more work.":"Submit a software change request to start the persistent production pipeline."} action={!query&&!status&&!projectId?<Link to="/tasks/new" className="btn-primary btn-sm"><Plus className="h-3.5 w-3.5"/>Create first task</Link>:null}/></div>}
  </div>;
}
