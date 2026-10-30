import { useEffect, useState } from "react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import {
  Activity, Bell, Boxes, BookOpenCheck, ChevronDown, CircleHelp, ClipboardCheck,
  Command, FileClock, Gauge, GitBranch, LogOut, Menu, PanelLeftClose,
  PanelLeftOpen, Plus, Settings2, ShieldCheck, X,
} from "lucide-react";
import { useAuth } from "@/auth/AuthContext";
import { api } from "@/api/client";
import type { Notification } from "@/api/types";
import { useAsync } from "@/hooks/useAsync";
import { formatDate, initials } from "@/lib/format";
import { StatusBadge } from "@/components/StatusBadge";

const primaryNav = [
  { to: "/", label: "Overview", icon: Gauge, end: true },
  { to: "/projects", label: "Projects", icon: Boxes },
  { to: "/tasks", label: "Production tasks", icon: Activity },
  { to: "/providers", label: "AI providers", icon: Command },
  { to: "/approvals", label: "Approvals", icon: ClipboardCheck },
];

const adminNav = [
  { to: "/environments", label: "Environments", icon: GitBranch },
  { to: "/audit", label: "Audit trail", icon: FileClock },
  { to: "/users", label: "Users & access", icon: ShieldCheck },
];

function Brand() {
  return (
    <div className="flex items-center gap-3 px-2">
      <div className="relative flex h-9 w-9 items-center justify-center rounded-xl bg-amber-400 text-ink-950 shadow-sm">
        <span className="text-[15px] font-black tracking-tighter">HC</span>
        <span className="absolute -bottom-0.5 -right-0.5 h-2.5 w-2.5 rounded-full border-2 border-ink-950 bg-emerald-400" />
      </div>
      <div className="min-w-0">
        <p className="truncate text-sm font-bold tracking-tight text-white">H-CALIPER</p>
        <p className="truncate text-[10px] font-medium tracking-[0.12em] text-ink-400">SOFTWARE FACTORY</p>
      </div>
    </div>
  );
}

function SideNav({ compact = false, onNavigate }: { compact?: boolean; onNavigate?: () => void }) {
  const { user } = useAuth();
  const renderGroup = (label: string, items: typeof primaryNav) => (
    <div className="mb-5">
      {!compact ? <p className="mb-2 px-3 text-[10px] font-bold uppercase tracking-[0.16em] text-ink-500">{label}</p> : null}
      <div className="space-y-1">
        {items.map(({ to, label: text, icon: Icon, ...rest }) => (
          <NavLink
            key={to}
            to={to}
            end={"end" in rest ? rest.end : false}
            title={compact ? text : undefined}
            onClick={onNavigate}
            className={({ isActive }) => `group flex h-10 items-center gap-3 rounded-lg px-3 text-[13px] font-medium transition ${isActive ? "bg-white/10 text-white shadow-sm" : "text-ink-400 hover:bg-white/5 hover:text-white"} ${compact ? "justify-center px-0" : ""}`}
          >
            {({ isActive }) => <><Icon className={`h-[17px] w-[17px] shrink-0 ${isActive ? "text-amber-400" : "text-ink-500 group-hover:text-ink-300"}`} strokeWidth={1.8} />{!compact ? <span className="truncate">{text}</span> : null}{!compact && to === "/approvals" ? <span className="ml-auto h-1.5 w-1.5 rounded-full bg-amber-400" /> : null}</>}
          </NavLink>
        ))}
      </div>
    </div>
  );

  return <nav className="flex-1 overflow-y-auto px-3 pt-7">
    {renderGroup("Workspace", primaryNav)}
    {user?.role === "ADMIN" ? renderGroup("Administration", adminNav) : null}
    {!compact ? <div className="mt-8 rounded-xl border border-white/10 bg-white/[0.035] p-3.5">
      <div className="flex items-center gap-2 text-[11px] font-semibold text-ink-300"><BookOpenCheck className="h-3.5 w-3.5 text-amber-400" />CALIPER standard</div>
      <p className="mt-1.5 text-[11px] leading-5 text-ink-500">12 active engineering principles. One reserved slot for your team’s future rule.</p>
    </div> : null}
  </nav>;
}

export function AppShell() {
  const { user, signOut } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [compact, setCompact] = useState(() => localStorage.getItem("hc-nav-compact") === "1");
  const [mobileOpen, setMobileOpen] = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);
  const { data: notifications, refresh: refreshNotifications } = useAsync<Notification[]>(() => api.get("/notifications"), [], { pollMs: 60_000 });
  const unread = (notifications ?? []).filter((item) => !item.is_read).length;

  useEffect(() => { setMobileOpen(false); }, [location.pathname]);
  useEffect(() => { localStorage.setItem("hc-nav-compact", compact ? "1" : "0"); }, [compact]);

  const handleSignOut = async () => {
    await signOut();
    navigate("/login", { replace: true });
  };

  return <div className="flex h-full min-h-0 bg-ink-50">
    <aside className={`relative z-30 hidden shrink-0 flex-col bg-ink-950 transition-[width] duration-200 lg:flex ${compact ? "w-[76px]" : "w-[248px]"}`}>
      <div className={`flex h-[68px] items-center border-b border-white/[0.08] ${compact ? "justify-center" : "px-5"}`}><Brand /></div>
      <SideNav compact={compact} />
      <div className={`border-t border-white/[0.08] p-3 ${compact ? "flex justify-center" : ""}`}>
        {compact ? <button className="rounded-lg p-2 text-ink-500 hover:bg-white/5 hover:text-white" title="Expand sidebar" onClick={() => setCompact(false)}><PanelLeftOpen className="h-4 w-4" /></button> : <div className="flex items-center gap-2 px-1">
          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-ink-800 text-[11px] font-bold text-ink-200">{initials(user?.full_name ?? "", user?.email)}</div>
          <div className="min-w-0 flex-1"><p className="truncate text-xs font-semibold text-white">{user?.full_name || user?.email}</p><p className="text-[10px] text-ink-500">{user?.role}</p></div>
          <button className="rounded-md p-1.5 text-ink-500 hover:bg-white/5 hover:text-white" onClick={() => setCompact(true)} title="Collapse sidebar"><PanelLeftClose className="h-4 w-4" /></button>
        </div>}
      </div>
    </aside>

    {mobileOpen ? <div className="fixed inset-0 z-50 lg:hidden">
      <button className="absolute inset-0 bg-ink-950/50" onClick={() => setMobileOpen(false)} aria-label="Close navigation" />
      <aside className="relative flex h-full w-[280px] max-w-[85vw] flex-col bg-ink-950 shadow-lift">
        <div className="flex h-[68px] items-center justify-between border-b border-white/[0.08] px-5"><Brand /><button onClick={() => setMobileOpen(false)} className="rounded p-1.5 text-ink-400 hover:bg-white/10"><X className="h-4 w-4" /></button></div>
        <SideNav onNavigate={() => setMobileOpen(false)} />
        <div className="border-t border-white/[0.08] p-4 text-xs text-ink-400">{user?.full_name || user?.email} · {user?.role}</div>
      </aside>
    </div> : null}

    <div className="flex min-w-0 flex-1 flex-col">
      <header className="sticky top-0 z-20 flex h-[68px] shrink-0 items-center justify-between border-b border-ink-200/80 bg-white/90 px-4 backdrop-blur sm:px-6 lg:px-8">
        <div className="flex items-center gap-3">
          <button className="rounded-lg p-2 text-ink-500 hover:bg-ink-100 lg:hidden" onClick={() => setMobileOpen(true)} aria-label="Open navigation"><Menu className="h-5 w-5" /></button>
          <div className="hidden items-center gap-2 text-xs text-ink-400 sm:flex"><span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />Factory online<span className="mx-1 text-ink-300">/</span><span className="font-medium text-ink-600">{location.pathname === "/" ? "Overview" : location.pathname.split("/").filter(Boolean).at(-1)?.replace(/-/g, " ")}</span></div>
          <div className="sm:hidden"><span className="text-xs font-semibold text-ink-800">H-CALIPER</span><span className="ml-2 h-1.5 w-1.5 rounded-full bg-emerald-500 inline-block" /></div>
        </div>
        <div className="flex items-center gap-1.5">
          <button onClick={() => { void refreshNotifications(); navigate("/notifications"); }} className="relative rounded-lg p-2 text-ink-500 transition hover:bg-ink-100 hover:text-ink-900" aria-label={`Notifications${unread ? `, ${unread} unread` : ""}`}>
            <Bell className="h-[18px] w-[18px]" />{unread ? <span className="absolute right-1.5 top-1.5 flex h-4 min-w-4 items-center justify-center rounded-full border-2 border-white bg-amber-500 px-0.5 text-[8px] font-bold text-white">{unread > 9 ? "9+" : unread}</span> : null}
          </button>
          <button onClick={() => navigate("/tasks/new")} className="btn-primary btn-sm ml-1 hidden sm:inline-flex"><Plus className="h-3.5 w-3.5" />New task</button>
          <div className="relative ml-1">
            <button onClick={() => setProfileOpen((v) => !v)} className="flex items-center gap-2 rounded-lg p-1.5 transition hover:bg-ink-100" aria-expanded={profileOpen}>
              <span className="flex h-8 w-8 items-center justify-center rounded-full bg-ink-900 text-[11px] font-bold text-amber-300">{initials(user?.full_name ?? "", user?.email)}</span>
              <span className="hidden max-w-[130px] truncate text-xs font-semibold text-ink-700 md:block">{user?.full_name || user?.email}</span><ChevronDown className="hidden h-3.5 w-3.5 text-ink-400 md:block" />
            </button>
            {profileOpen ? <><button className="fixed inset-0 z-30 cursor-default" onClick={() => setProfileOpen(false)} aria-label="Close profile menu" /><div className="absolute right-0 z-40 mt-2 w-60 rounded-xl border border-ink-200 bg-white p-2 shadow-lift">
              <div className="border-b border-ink-100 px-3 py-2"><p className="truncate text-xs font-semibold text-ink-900">{user?.full_name || user?.email}</p><p className="truncate text-[11px] text-ink-500">{user?.email}</p><div className="mt-1.5"><StatusBadge status={user?.role ?? "VIEWER"} showDot={false} /></div></div>
              <button onClick={() => { setProfileOpen(false); navigate("/profile"); }} className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-xs text-ink-700 hover:bg-ink-50"><Settings2 className="h-3.5 w-3.5" />Profile & preferences</button>
              <button onClick={() => { setProfileOpen(false); navigate("/help"); }} className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-xs text-ink-700 hover:bg-ink-50"><CircleHelp className="h-3.5 w-3.5" />Help & documentation</button>
              <button onClick={() => void handleSignOut()} className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-xs font-medium text-red-600 hover:bg-red-50"><LogOut className="h-3.5 w-3.5" />Sign out</button>
              <p className="px-3 pb-1 pt-2 text-[10px] text-ink-400">Signed in · {formatDate(user?.last_login_at, false)}</p>
            </div></> : null}
          </div>
        </div>
      </header>
      <main className="min-h-0 flex-1 overflow-y-auto">
        <div className="mx-auto w-full max-w-[1600px] px-4 py-6 sm:px-6 sm:py-8 lg:px-8"><Outlet /></div>
      </main>
      <button onClick={() => navigate("/tasks/new")} className="fixed bottom-5 right-5 z-20 flex h-12 w-12 items-center justify-center rounded-full bg-amber-500 text-ink-950 shadow-lift transition hover:bg-amber-400 sm:hidden" aria-label="Create task"><Plus className="h-5 w-5" /></button>
    </div>
  </div>;
}
