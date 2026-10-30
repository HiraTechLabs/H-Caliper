import { Navigate, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "@/auth/AuthContext";
import { Loading } from "@/components/Loading";

export function RequireAuth() {
  const { user, loading } = useAuth();
  const location = useLocation();
  if (loading) return <Loading full label="Checking your session" />;
  return user ? <Outlet /> : <Navigate to="/login" replace state={{ from: location }} />;
}

export function RequireAdmin() {
  const { user } = useAuth();
  if (user?.role !== "ADMIN") return <Navigate to="/" replace />;
  return <Outlet />;
}
