import { useState } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { Activity, ArrowRight, Eye, EyeOff, LockKeyhole, Mail, ShieldCheck, Sparkles } from "lucide-react";
import { ApiError } from "@/api/client";
import { useAuth } from "@/auth/AuthContext";

export function AuthPage({ bootstrap = false }: { bootstrap?: boolean }) {
  const { user, bootstrap: status, signIn, createFirstAdmin, loading } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  if (loading) return <div className="grid min-h-screen place-items-center bg-ink-950"><div className="h-6 w-6 animate-spin rounded-full border-2 border-ink-600 border-t-amber-400" /></div>;
  if (user) return <Navigate to="/" replace />;
  if (!bootstrap && status?.bootstrap_required) return <Navigate to="/setup" replace />;
  if (bootstrap && status && !status.bootstrap_required) return <Navigate to="/login" replace />;

  const submit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      if (bootstrap) await createFirstAdmin({ email, password, full_name: fullName || "Administrator" });
      else await signIn(email, password);
      const from = (location.state as { from?: { pathname?: string } } | null)?.from?.pathname;
      navigate(from || "/", { replace: true });
    } catch (cause) {
      if (cause instanceof ApiError && cause.status === 429) setError("Too many attempts. Wait a minute and try again.");
      else setError(cause instanceof Error ? cause.message : "Unable to sign in.");
    } finally { setSubmitting(false); }
  };

  return <div className="min-h-screen bg-ink-950 text-white">
    <div className="grid min-h-screen lg:grid-cols-[1.05fr_0.95fr]">
      <section className="relative hidden overflow-hidden border-r border-white/[0.07] lg:flex lg:flex-col lg:justify-between lg:px-14 lg:py-12 xl:px-20">
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_18%_20%,rgba(232,163,61,0.13),transparent_42%),radial-gradient(ellipse_at_80%_90%,rgba(88,110,155,0.13),transparent_40%)]" />
        <div className="absolute inset-0 opacity-[0.09] [background-image:linear-gradient(rgba(255,255,255,.12)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,.12)_1px,transparent_1px)] [background-size:56px_56px] [mask-image:linear-gradient(to_bottom,black,transparent_90%)]" />
        <div className="relative flex items-center gap-3"><div className="flex h-10 w-10 items-center justify-center rounded-xl bg-amber-400 text-sm font-black text-ink-950">HC</div><div><p className="text-sm font-bold tracking-wide">H-CALIPER</p><p className="text-[10px] tracking-[.16em] text-ink-400">SOFTWARE FACTORY</p></div></div>
        <div className="relative max-w-xl py-14">
          <div className="mb-7 inline-flex items-center gap-2 rounded-full border border-amber-400/25 bg-amber-400/[0.08] px-3 py-1.5 text-[11px] font-semibold tracking-wide text-amber-300"><Sparkles className="h-3.5 w-3.5" />ENGINEERING, STANDARDIZED</div>
          <h1 className="text-balance text-5xl font-semibold leading-[1.12] tracking-[-.04em] xl:text-[58px]">Build with intent.<br /><span className="text-amber-400">Ship with confidence.</span></h1>
          <p className="mt-6 max-w-lg text-sm leading-7 text-ink-400">A governed production pipeline for AI-assisted software engineering. Every change is planned, validated, reviewed, documented, and traceable.</p>
          <div className="mt-10 grid max-w-lg grid-cols-3 gap-3">
            {[{ n: "12", label: "Principles" }, { n: "04", label: "Agent roles" }, { n: "100%", label: "Traceability" }].map((x) => <div key={x.label} className="rounded-xl border border-white/[0.08] bg-white/[0.025] p-4"><p className="text-xl font-bold tracking-tight text-white">{x.n}</p><p className="mt-1 text-[10px] font-medium uppercase tracking-wider text-ink-500">{x.label}</p></div>)}
          </div>
        </div>
        <div className="relative flex items-center justify-between text-[10px] text-ink-600"><span>H-CALIPER · SOFTWARE PRODUCTION FACTORY</span><span>v1.0</span></div>
      </section>

      <section className="flex min-h-screen flex-col justify-between px-5 py-7 sm:px-10 lg:px-14 lg:py-12">
        <div className="flex items-center gap-3 lg:hidden"><div className="flex h-9 w-9 items-center justify-center rounded-xl bg-amber-400 text-xs font-black text-ink-950">HC</div><div><p className="text-sm font-bold">H-CALIPER</p><p className="text-[9px] tracking-[.15em] text-ink-500">SOFTWARE FACTORY</p></div></div>
        <div className="mx-auto w-full max-w-[410px] flex-1 py-10 sm:py-16 lg:flex lg:flex-col lg:justify-center lg:py-0">
          <div className="mb-8">
            <div className="mb-5 flex h-11 w-11 items-center justify-center rounded-xl border border-white/10 bg-white/[0.04] text-amber-400"><LockKeyhole className="h-5 w-5" /></div>
            <p className="mb-2 text-[11px] font-bold uppercase tracking-[.16em] text-amber-400">{bootstrap ? "First-time setup" : "Welcome back"}</p>
            <h2 className="text-3xl font-semibold tracking-tight">{bootstrap ? "Create your admin" : "Sign in to H-Caliper"}</h2>
            <p className="mt-2 text-sm leading-6 text-ink-400">{bootstrap ? "This creates the first administrator account for your instance." : "Enter your credentials to access the production workspace."}</p>
          </div>
          <form onSubmit={submit} className="space-y-4">
            {bootstrap ? <div><label htmlFor="full_name" className="mb-1.5 block text-xs font-semibold text-ink-300">Full name</label><input id="full_name" autoComplete="name" value={fullName} onChange={(e) => setFullName(e.target.value)} className="w-full rounded-lg border border-white/10 bg-white/[0.04] px-3.5 py-3 text-sm text-white placeholder:text-ink-600 focus:border-amber-500 focus:outline-none focus:ring-2 focus:ring-amber-500/20" placeholder="Administrator" /></div> : null}
            <div><label htmlFor="email" className="mb-1.5 block text-xs font-semibold text-ink-300">Email address</label><div className="relative"><Mail className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-600" /><input id="email" type="email" autoComplete="username" required value={email} onChange={(e) => setEmail(e.target.value)} className="w-full rounded-lg border border-white/10 bg-white/[0.04] py-3 pl-10 pr-3.5 text-sm text-white placeholder:text-ink-600 focus:border-amber-500 focus:outline-none focus:ring-2 focus:ring-amber-500/20" placeholder="you@company.com" /></div></div>
            <div><label htmlFor="password" className="mb-1.5 block text-xs font-semibold text-ink-300">Password</label><div className="relative"><LockKeyhole className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-600" /><input id="password" type={showPassword ? "text" : "password"} autoComplete={bootstrap ? "new-password" : "current-password"} required minLength={bootstrap ? 12 : 1} value={password} onChange={(e) => setPassword(e.target.value)} className="w-full rounded-lg border border-white/10 bg-white/[0.04] py-3 pl-10 pr-11 text-sm text-white placeholder:text-ink-600 focus:border-amber-500 focus:outline-none focus:ring-2 focus:ring-amber-500/20" placeholder={bootstrap ? "At least 12 characters" : "Enter your password"} /><button type="button" onClick={() => setShowPassword((v) => !v)} className="absolute right-3 top-1/2 -translate-y-1/2 text-ink-500 hover:text-ink-200" aria-label={showPassword ? "Hide password" : "Show password"}>{showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}</button></div>{bootstrap ? <p className="mt-1.5 text-[11px] text-ink-600">Use 12+ characters, including at least one letter and one number.</p> : null}</div>
            {error ? <div role="alert" className="rounded-lg border border-red-400/20 bg-red-500/10 px-3 py-2.5 text-xs leading-5 text-red-300">{error}</div> : null}
            <button type="submit" disabled={submitting} className="mt-2 flex w-full items-center justify-center gap-2 rounded-lg bg-amber-500 px-4 py-3 text-sm font-bold text-ink-950 transition hover:bg-amber-400 disabled:cursor-wait disabled:opacity-60">{submitting ? <span className="h-4 w-4 animate-spin rounded-full border-2 border-ink-950/30 border-t-ink-950" /> : <>{bootstrap ? "Create administrator" : "Sign in securely"}<ArrowRight className="h-4 w-4" /></>}</button>
          </form>
          <div className="mt-7 flex items-start gap-2.5 rounded-xl border border-white/[0.07] bg-white/[0.025] p-3.5"><ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-emerald-400" /><p className="text-[11px] leading-5 text-ink-500">Protected by role-based access, encrypted sessions, and audit logging. Your credentials are never exposed to AI providers.</p></div>
          {!bootstrap ? <p className="mt-5 text-center text-[11px] text-ink-600">Need help? Contact your H-Caliper administrator.</p> : null}
        </div>
        <div className="mx-auto flex w-full max-w-[410px] items-center justify-between text-[10px] text-ink-700"><span>© {new Date().getFullYear()} H-Caliper</span><span className="flex items-center gap-1.5"><Activity className="h-3 w-3 text-emerald-500" />Factory ready</span></div>
      </section>
    </div>
  </div>;
}
