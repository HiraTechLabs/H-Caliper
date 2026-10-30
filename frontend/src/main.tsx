import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider } from "@/auth/AuthContext";
import { RequireAdmin, RequireAuth } from "@/auth/RequireAuth";
import { AppShell } from "@/components/AppShell";
import { ToastProvider } from "@/components/Toast";
import { AuthPage } from "@/pages/AuthPage";
import { DashboardPage } from "@/pages/DashboardPage";
import { ProjectsPage } from "@/pages/ProjectsPage";
import { ProjectDetailPage } from "@/pages/ProjectDetailPage";
import { TasksPage } from "@/pages/TasksPage";
import { NewTaskPage } from "@/pages/NewTaskPage";
import { TaskDetailPage } from "@/pages/TaskDetailPage";
import { ProvidersPage } from "@/pages/ProvidersPage";
import { ApprovalsPage } from "@/pages/ApprovalsPage";
import { AuditPage, EnvironmentsPage, NotificationsPage, UsersPage } from "@/pages/OperationalPages";
import { HelpPage, ProfilePage } from "@/pages/MiscPages";
import "./index.css";

function NotFound(){return <div className="flex min-h-[60vh] flex-col items-center justify-center text-center"><p className="font-mono text-xs text-amber-600">ERROR 404</p><h1 className="mt-2 text-2xl font-bold text-ink-950">Page not found</h1><p className="mt-2 text-sm text-ink-500">The address may have changed or the page is unavailable.</p><a href="/" className="btn-primary mt-5">Return to overview</a></div>}

function Root(){return <ToastProvider><AuthProvider><BrowserRouter><Routes><Route path="/login" element={<AuthPage/>}/><Route path="/setup" element={<AuthPage bootstrap/>}/><Route element={<RequireAuth/>}><Route element={<AppShell/>}><Route index element={<DashboardPage/>}/><Route path="projects" element={<ProjectsPage/>}/><Route path="projects/:projectId" element={<ProjectDetailPage/>}/><Route path="tasks" element={<TasksPage/>}/><Route path="tasks/new" element={<NewTaskPage/>}/><Route path="tasks/:taskId" element={<TaskDetailPage/>}/><Route path="providers" element={<ProvidersPage/>}/><Route path="approvals" element={<ApprovalsPage/>}/><Route path="environments" element={<EnvironmentsPage/>}/><Route path="notifications" element={<NotificationsPage/>}/><Route path="profile" element={<ProfilePage/>}/><Route path="help" element={<HelpPage/>}/><Route element={<RequireAdmin/>}><Route path="audit" element={<AuditPage/>}/><Route path="users" element={<UsersPage/>}/></Route><Route path="*" element={<NotFound/>}/></Route></Route><Route path="*" element={<Navigate to="/" replace/>}/></Routes></BrowserRouter></AuthProvider></ToastProvider>}

ReactDOM.createRoot(document.getElementById("root")!).render(<React.StrictMode><Root/></React.StrictMode>);
