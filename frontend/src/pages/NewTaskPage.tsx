import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { ArrowLeft, ArrowRight, Bot, Check, CircleHelp, Info, Rocket, ShieldCheck, Sparkles } from "lucide-react";
import { api } from "@/api/client";
import type { Project, Provider, TaskSummary } from "@/api/types";
import { useAsync } from "@/hooks/useAsync";
import { PageHeader } from "@/components/PageHeader";
import { FormField, SelectInput, TextArea, TextInput } from "@/components/FormField";
import { Section } from "@/components/Section";
import { EmptyState } from "@/components/EmptyState";
import { Loading } from "@/components/Loading";
import { useToast } from "@/components/Toast";

const AGENTS = [
  { key: "planning", label: "Planning", caption: "Analyze and structure", icon: Sparkles },
  { key: "execution", label: "Execution", caption: "Implement in a worktree", icon: Bot },
  { key: "review", label: "Review", caption: "Inspect changes independently", icon: ShieldCheck },
  { key: "documentation", label: "Documentation", caption: "Record the accepted work", icon: Rocket },
] as const;

interface Selection { provider_id: string; model: string; }

export function NewTaskPage() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const { toast } = useToast();
  const projects = useAsync<Project[]>(()=>api.get("/projects",{status:"ACTIVE"}),[]);
  const providers = useAsync<Provider[]>(()=>api.get("/providers"),[]);
  const [projectId,setProjectId]=useState(params.get("project_id")??"");
  const [title,setTitle]=useState(""); const [description,setDescription]=useState("");
  const [maxRetries,setMaxRetries]=useState("");
  const [selections,setSelections]=useState<Record<string,Selection>>({});
  const [busy,setBusy]=useState(false);
  const project=projects.data?.find(p=>p.id===projectId);
  const activeProviders=useMemo(()=>providers.data?.filter(p=>p.enabled)??[],[providers.data]);
  useEffect(()=>{
    if(!project)return;
    const next:Record<string,Selection>={};
    for(const {key} of AGENTS){
      const pid=project[`default_${key}_provider_id` as keyof Project] as string|null;
      const model=project[`default_${key}_model` as keyof Project] as string|null;
      const provider=providers.data?.find(p=>p.id===pid);
      const selectedModel=model&&provider?.models.some(m=>m.enabled&&m.model_id===model)
        ? model
        : provider?.models.find(m=>m.enabled)?.model_id??"";
      next[key]={provider_id:pid??"",model:selectedModel};
    }
    setSelections(next);
  },[project,providers.data]);

  const selectProvider=(agent:string,providerId:string)=>{
    const provider=activeProviders.find(p=>p.id===providerId);
    const existing=selections[agent]?.model;
    const supported=provider?.models.some(m=>m.enabled&&m.model_id===existing);
    setSelections(prev=>({...prev,[agent]:{provider_id:providerId,model:supported?existing:(provider?.models.find(m=>m.enabled)?.model_id??"")}}));
  };
  const setModel=(agent:string,model:string)=>setSelections(prev=>({...prev,[agent]:{...(prev[agent]??{provider_id:"",model:""}),model}}));

  const submit=async(e:React.FormEvent)=>{
    e.preventDefault(); if(!projectId)return;
    setBusy(true);
    const body:Record<string,unknown>={project_id:projectId,title:title.trim(),description:description.trim()};
    for(const {key} of AGENTS){const value=selections[key]; if(value?.provider_id)body[key]={provider_id:value.provider_id,model:value.model||null};}
    if(maxRetries!=="")body.max_retries=Number(maxRetries);
    try{const task=await api.post<TaskSummary>("/tasks",body);toast({title:"Task submitted",description:"The persistent production pipeline has queued your request.",tone:"success"});navigate(`/tasks/${task.id}`);}
    catch(error){toast({title:"Task could not be submitted",description:error instanceof Error?error.message:"Request failed",tone:"error"});}
    finally{setBusy(false);}
  };

  const missingDefaults=project?AGENTS.filter(a=>!selections[a.key]?.provider_id).map(a=>a.label):[];
  const modelIssues=AGENTS.filter(a=>{const s=selections[a.key];const p=activeProviders.find(x=>x.id===s?.provider_id);return !!p&& !p.models.some(m=>m.enabled&&m.model_id===s?.model);}).map(a=>a.label);

  return <div className="animate-fade-in">
    <Link to={project?`/projects/${project.id}`:"/tasks"} className="mb-4 inline-flex items-center gap-1.5 text-xs font-medium text-ink-500 hover:text-ink-900"><ArrowLeft className="h-3.5 w-3.5"/>{project?"Back to project":"Back to tasks"}</Link>
    <PageHeader eyebrow="Production pipeline · New request" title="Create a task" description="Describe the software change. H-Caliper will collect context and principles before planning, then execute, validate, review, and document the work." />
    {!projects.loading&&!projects.data?.length?<div className="card"><EmptyState title="Create a project first" description="A task must run against an isolated project workspace with a connected Git repository." action={<Link to="/projects" className="btn-primary btn-sm">Go to projects</Link>}/></div>:projects.loading?<Loading label="Loading project configuration"/>:<form onSubmit={e=>void submit(e)} className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_340px]">
      <div className="space-y-5">
        <Section title="Task request" description="Be specific about desired behavior, constraints, and acceptance criteria."><div className="space-y-4"><FormField label="Project workspace" required><SelectInput value={projectId} onChange={e=>setProjectId(e.target.value)} required><option value="">Choose a project…</option>{(projects.data??[]).map(p=><option key={p.id} value={p.id}>{p.name} · {p.slug}</option>)}</SelectInput></FormField><FormField label="Task title" required><TextInput required minLength={3} maxLength={250} value={title} onChange={e=>setTitle(e.target.value)} placeholder="e.g. Add CSV export to the reports page"/></FormField><FormField label="Detailed description" required hint={`${description.length.toLocaleString()} / 50,000 characters`}><TextArea required minLength={10} maxLength={50_000} rows={8} value={description} onChange={e=>setDescription(e.target.value)} placeholder={'Describe the goal, current behavior, expected behavior, and any constraints.\n\nAcceptance criteria:\n- …'}/></FormField></div></Section>

        <Section title="Agent configuration" description="Use project defaults or override the provider/model for this task." actions={<span className="chip border-ink-200 bg-ink-50 text-ink-500"><Sparkles className="h-3 w-3"/>4 roles</span>}>
          {providers.loading?<Loading label="Loading providers"/>:!activeProviders.length?<div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs leading-5 text-amber-900">No enabled providers are available. <Link to="/providers" className="font-semibold underline">Configure a provider</Link> before submitting work.</div>:<div className="space-y-3">{AGENTS.map(({key,label,caption,icon:Icon})=>{const selection=selections[key]??{provider_id:"",model:""};const provider=activeProviders.find(p=>p.id===selection.provider_id);const availableModels=provider?.models.filter(m=>m.enabled)??[];return <div key={key} className="grid gap-3 rounded-xl border border-ink-100 p-4 sm:grid-cols-[minmax(140px,0.8fr)_minmax(160px,1fr)_minmax(160px,1fr)] sm:items-center"><div className="flex items-center gap-2.5"><span className="flex h-8 w-8 items-center justify-center rounded-lg bg-ink-100 text-ink-600"><Icon className="h-4 w-4"/></span><span><span className="block text-xs font-bold text-ink-900">{label} agent</span><span className="block text-[10px] text-ink-400">{caption}</span></span></div><FormField label="Provider"><SelectInput value={selection.provider_id} onChange={e=>selectProvider(key,e.target.value)}><option value="">{project?.[`default_${key}_provider_id` as keyof Project]?"Use project default":"Select provider"}</option>{activeProviders.map(p=><option key={p.id} value={p.id}>{p.name}</option>)}</SelectInput></FormField><FormField label="Model"><SelectInput value={selection.model} disabled={!provider||!availableModels.length} onChange={e=>setModel(key,e.target.value)}><option value="">{availableModels.length?"Use project default":"No models available"}</option>{availableModels.map(m=><option key={m.id} value={m.model_id}>{m.display_name}</option>)}</SelectInput></FormField></div>})}</div>}
          {missingDefaults?.length?<p className="mt-3 flex items-start gap-1.5 text-[11px] leading-5 text-amber-700"><CircleHelp className="mt-0.5 h-3.5 w-3.5 shrink-0"/>Choose providers for {missingDefaults.join(", ")}. Each agent requires a valid provider and model.</p>:null}{modelIssues.length?<p className="mt-3 text-[11px] text-red-600">Select an enabled model for {modelIssues.join(", ")}.</p>:null}
        </Section>
      </div>
      <aside className="space-y-5">
        <Section title="Execution settings" description="Retry and validation policy"><div className="space-y-4"><FormField label="Maximum retries" hint={`Project default: ${project?.max_retries ?? "—"}. Retries follow a rejected review; no infinite loops.`}><SelectInput value={maxRetries} onChange={e=>setMaxRetries(e.target.value)}><option value="">Use project default</option>{Array.from({length:11},(_,i)=><option key={i} value={i}>{i} {i===1?"retry":"retries"}</option>)}</SelectInput></FormField><div className="rounded-lg border border-ink-100 bg-ink-50/70 p-3"><p className="mb-2 flex items-center gap-2 text-xs font-semibold text-ink-700"><Check className="h-3.5 w-3.5 text-emerald-600"/>Automatic quality controls</p><ul className="space-y-1.5 text-[10px] leading-4 text-ink-500"><li>• Secret scan and change policy</li><li>• Project-configured test and build gates</li><li>• Separate AI review after validation</li><li>• Explicit human merge approval</li></ul></div></div></Section>
        <div className="rounded-xl border border-sky-200 bg-sky-50/70 p-4"><p className="flex items-center gap-2 text-xs font-bold text-sky-900"><Info className="h-4 w-4"/>What happens next?</p><ol className="mt-3 space-y-2 text-[11px] leading-5 text-sky-900/80">{["Context and CALIPER principles are loaded","Planning agent produces a structured plan","Execution runs on a dedicated Git branch","Deterministic gates and independent review run","Documentation is prepared for human approval"].map((x,i)=><li className="flex gap-2" key={x}><span className="flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-sky-200/70 text-[9px] font-bold text-sky-900">{i+1}</span>{x}</li>)}</ol></div>
        <button type="submit" disabled={busy||!projectId||!title.trim()||description.trim().length<10||!activeProviders.length||Boolean(missingDefaults?.length)||Boolean(modelIssues.length)} className="btn-primary w-full py-3">{busy?"Submitting request…":<>Submit to production pipeline<ArrowRight className="h-4 w-4"/></>}</button>
        <p className="flex items-center justify-center gap-1.5 text-[10px] text-ink-400"><ShieldCheck className="h-3 w-3"/>No changes are merged without human approval.</p>
      </aside>
    </form>}
  </div>;
}
