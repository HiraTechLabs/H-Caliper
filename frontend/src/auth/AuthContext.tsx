import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { api } from "@/api/client";
import type { BootstrapStatus, Me, User } from "@/api/types";

interface AuthContextValue {
  user: User | null;
  loading: boolean;
  bootstrap: BootstrapStatus | null;
  refresh: () => Promise<void>;
  signIn: (email: string, password: string) => Promise<void>;
  createFirstAdmin: (input: { email: string; password: string; full_name: string }) => Promise<void>;
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [bootstrap, setBootstrap] = useState<BootstrapStatus | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    const [status, me] = await Promise.allSettled([
      api.get<BootstrapStatus>("/auth/bootstrap-status"),
      api.get<Me>("/auth/me"),
    ]);
    if (status.status === "fulfilled") setBootstrap(status.value);
    if (me.status === "fulfilled") setUser(me.value.user);
    else setUser(null);
    setLoading(false);
  }, []);

  useEffect(() => { void refresh(); }, [refresh]);

  const signIn = useCallback(async (email: string, password: string) => {
    const result = await api.post<Me>("/auth/login", { email, password });
    setUser(result.user);
  }, []);

  const createFirstAdmin = useCallback(async (input: { email: string; password: string; full_name: string }) => {
    const result = await api.post<Me>("/auth/bootstrap", input);
    setUser(result.user);
    setBootstrap((current) => current ? { ...current, bootstrap_required: false } : current);
  }, []);

  const signOut = useCallback(async () => {
    try { await api.post("/auth/logout"); } finally { setUser(null); }
  }, []);

  const value = useMemo(() => ({ user, loading, bootstrap, refresh, signIn, createFirstAdmin, signOut }), [user, loading, bootstrap, refresh, signIn, createFirstAdmin, signOut]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth must be used inside AuthProvider");
  return value;
}
