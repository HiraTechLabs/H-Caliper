import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { Activity, ArrowUpRight, Boxes, Check, CircleAlert, Cpu, FolderGit2, Pencil, Plus, RefreshCw, Trash2, X } from 'lucide-react'
import { Button } from './components/ui/button'
import { Card } from './components/ui/card'
import { CredentialManager } from './components/CredentialManager'
import { PrinciplesWorkspace } from './components/PrinciplesWorkspace'
import { OllamaProviderManager } from './components/OllamaProviderManager'
import { RepositorySyncManager } from './components/RepositorySyncManager'

type Project = {
  id: string
  name: string
  description: string
  repository_url: string | null
  default_branch: string
  created_at: string
  updated_at: string
}

type ProjectInput = Pick<Project, 'name' | 'description' | 'default_branch'> & {
  repository_url: string | null
}

function App() {
  const [projects, setProjects] = useState<Project[]>([])
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [repositoryUrl, setRepositoryUrl] = useState('')
  const [loading, setLoading] = useState(true)
  const [connection, setConnection] = useState<'checking' | 'ready' | 'error'>('checking')
  const [saving, setSaving] = useState(false)
  const [selectedProject, setSelectedProject] = useState<Project | null>(null)
  const [dialogMode, setDialogMode] = useState<'details' | 'edit' | 'delete' | null>(null)
  const [dialogLoading, setDialogLoading] = useState(false)
  const [dialogBusy, setDialogBusy] = useState(false)
  const [dialogError, setDialogError] = useState('')
  const [editName, setEditName] = useState('')
  const [editDescription, setEditDescription] = useState('')
  const [editRepositoryUrl, setEditRepositoryUrl] = useState('')
  const [editDefaultBranch, setEditDefaultBranch] = useState('main')
  const [showCredentialManager, setShowCredentialManager] = useState(false)
  const [showRepositorySync, setShowRepositorySync] = useState(false)
  const [showPrinciplesWorkspace, setShowPrinciplesWorkspace] = useState(false)
  const [showOllamaSettings, setShowOllamaSettings] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [authReady, setAuthReady] = useState(false)
  const [adminConfigured, setAdminConfigured] = useState(false)
  const [authenticated, setAuthenticated] = useState(false)
  const [password, setPassword] = useState('')
  const [authError, setAuthError] = useState('')
  const [authBusy, setAuthBusy] = useState(false)

  const loadProjects = useCallback(async () => {
    setLoading(true)
    setConnection('checking')
    setError('')
    try {
      const response = await fetch('/api/projects')
      if (!response.ok) throw new Error('Could not load projects. Check the API and try again.')
      setProjects(await response.json() as Project[])
      setConnection('ready')
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Could not load projects.')
      setConnection('error')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void (async () => {
      try {
        const response = await fetch('/api/auth/session')
        if (!response.ok) throw new Error('Could not check the administrator session.')
        const state = await response.json() as { configured: boolean; authenticated: boolean }
        setAdminConfigured(state.configured)
        setAuthenticated(state.authenticated)
        if (state.authenticated) await loadProjects()
      } catch {
        setConnection('error')
        setError('Caliper could not connect to the server. Check the connection and refresh.')
      } finally {
        setAuthReady(true)
        setLoading(false)
      }
    })()
  }, [loadProjects])

  async function signIn(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setAuthBusy(true)
    setAuthError('')
    try {
      const response = await fetch('/api/auth/session', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ password }),
      })
      if (!response.ok) throw new Error(response.status === 409 ? 'Administrator setup is required on the server.' : 'The password was not accepted.')
      setPassword('')
      setAuthenticated(true)
      await loadProjects()
    } catch (cause) {
      setAuthError(cause instanceof Error ? cause.message : 'Could not sign in.')
    } finally {
      setAuthBusy(false)
    }
  }

  async function signOut() {
    await fetch('/api/auth/session', { method: 'DELETE' })
    setAuthenticated(false)
    setProjects([])
    setPassword('')
  }

  async function createProject(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setSaving(true)
    setError('')
    setNotice('')
    const payload: ProjectInput = {
      name: name.trim(),
      description: description.trim(),
      repository_url: repositoryUrl.trim() || null,
      default_branch: 'main',
    }
    try {
      const response = await fetch('/api/projects', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      if (!response.ok) {
        if (response.status >= 500) setConnection('error')
        const result = await response.json().catch(() => null) as { detail?: string | { msg?: string }[] } | null
        const detail = Array.isArray(result?.detail) ? result.detail[0]?.msg : result?.detail
        throw new Error(typeof detail === 'string' ? detail : 'Project was not saved. Please try again.')
      }
      const confirmedProject = await response.json() as Project
      setProjects((current) => [confirmedProject, ...current])
      setName('')
      setDescription('')
      setRepositoryUrl('')
      setNotice(`${confirmedProject.name} is ready in your workspace.`)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Project was not saved. Please try again.')
    } finally {
      setSaving(false)
    }
  }

  async function openProject(projectId: string) {
    setDialogMode('details')
    setDialogLoading(true)
    setDialogError('')
    setSelectedProject(null)
    try {
      const response = await fetch(`/api/projects/${projectId}`)
      if (!response.ok) throw new Error('Could not load the latest project details. Try again.')
      setSelectedProject(await response.json() as Project)
    } catch (cause) {
      setDialogError(cause instanceof Error ? cause.message : 'Could not load project details.')
    } finally {
      setDialogLoading(false)
    }
  }

  function beginEdit() {
    if (!selectedProject) return
    setEditName(selectedProject.name)
    setEditDescription(selectedProject.description)
    setEditRepositoryUrl(selectedProject.repository_url ?? '')
    setEditDefaultBranch(selectedProject.default_branch)
    setDialogError('')
    setDialogMode('edit')
  }

  async function saveProject(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!selectedProject) return
    setDialogBusy(true)
    setDialogError('')
    const payload: ProjectInput = {
      name: editName.trim(),
      description: editDescription.trim(),
      repository_url: editRepositoryUrl.trim() || null,
      default_branch: editDefaultBranch.trim(),
    }
    try {
      const response = await fetch(`/api/projects/${selectedProject.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      if (!response.ok) {
        const result = await response.json().catch(() => null) as { detail?: string | { msg?: string }[] } | null
        const detail = Array.isArray(result?.detail) ? result.detail[0]?.msg : result?.detail
        throw new Error(typeof detail === 'string' ? detail : 'Project was not updated. Please try again.')
      }

      const freshResponse = await fetch(`/api/projects/${selectedProject.id}`)
      if (!freshResponse.ok) throw new Error('The update was saved, but a fresh read failed. Refresh the workspace before continuing.')
      const freshProject = await freshResponse.json() as Project
      setProjects((current) => current.map((project) => project.id === freshProject.id ? freshProject : project))
      setSelectedProject(freshProject)
      setNotice(`${freshProject.name} was updated.`)
      setDialogMode('details')
    } catch (cause) {
      setDialogError(cause instanceof Error ? cause.message : 'Project was not updated. Please try again.')
    } finally {
      setDialogBusy(false)
    }
  }

  async function deleteProject() {
    if (!selectedProject) return
    setDialogBusy(true)
    setDialogError('')
    try {
      const response = await fetch(`/api/projects/${selectedProject.id}`, { method: 'DELETE' })
      if (!response.ok) {
        const result = await response.json().catch(() => null) as { detail?: string } | null
        throw new Error(result?.detail ?? 'Project was not deleted. Please try again.')
      }

      const freshResponse = await fetch('/api/projects')
      if (!freshResponse.ok) throw new Error('The delete was accepted, but a fresh project list failed. Refresh before continuing.')
      const freshProjects = await freshResponse.json() as Project[]
      if (freshProjects.some((project) => project.id === selectedProject.id)) {
        throw new Error('The project still appears in the fresh list. It was not removed from the workspace.')
      }
      setProjects(freshProjects)
      setNotice(`${selectedProject.name} was deleted.`)
      setSelectedProject(null)
      setDialogMode(null)
    } catch (cause) {
      setDialogError(cause instanceof Error ? cause.message : 'Project was not deleted. Please try again.')
    } finally {
      setDialogBusy(false)
    }
  }

  function closeDialog() {
    if (dialogBusy || dialogLoading) return
    setDialogMode(null)
    setSelectedProject(null)
    setDialogError('')
    setShowCredentialManager(false)
    setShowRepositorySync(false)
    setShowPrinciplesWorkspace(false)
  }

  const projectCount = projects.length

  if (!authReady || (authenticated && loading)) return <main className="auth-shell" role="status">Connecting securely to Caliper…</main>
  if (!authenticated) return (
    <main className="auth-shell">
      <form className="auth-card" onSubmit={(event) => void signIn(event)}>
        <div className="brand-mark"><Activity size={20} /></div>
        <p className="eyebrow">CALIPER WORKSPACE</p>
        <h1>{adminConfigured ? 'Welcome back.' : 'Finish administrator setup.'}</h1>
        <p>{adminConfigured ? 'Sign in with your local administrator password.' : 'Run the administrator setup command on the server, then refresh this page.'}</p>
        {!adminConfigured ? <code>docker compose exec api python -m caliper.cli admin init</code> : <>
          <label htmlFor="admin-password">Administrator password</label>
          <input id="admin-password" type="password" autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} required />
          {authError && <p className="auth-error" role="alert">{authError}</p>}
          <button className="button button-primary" type="submit" disabled={authBusy || !password}>{authBusy ? 'Signing in…' : 'Sign in'}</button>
        </>}
        {!adminConfigured && authError && <p className="auth-error" role="alert">{authError}</p>}
      </form>
    </main>
  )

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <a className="brand" href="#home" aria-label="Caliper home">
          <span className="brand-mark"><Activity size={20} strokeWidth={2.6} /></span>
          <span>caliper<span className="brand-period">.</span></span>
        </a>
        <div className="sidebar-caption">WORKSPACE</div>
        <nav aria-label="Main navigation">
          <a className="nav-item nav-active" href="#projects"><Boxes size={17} />Projects<span className="nav-count">{projectCount}</span></a>
          <button className="nav-item nav-muted nav-button" type="button" onClick={() => { setDialogMode(null); setSelectedProject(null); setShowOllamaSettings(true) }}><Cpu size={17} />Ollama</button>
        </nav>
        <div className="sidebar-bottom">
          <div className={`connection-indicator connection-${connection}`}><span className="status-dot" />{connection === 'ready' ? 'Workspace connected' : connection === 'error' ? 'Workspace unavailable' : 'Connecting…'}</div>
          <p>Project context, ready for the work ahead.</p>
        </div>
      </aside>

      <main className="main-content" id="projects">
        <header className="topbar">
          <div className="breadcrumb">Workspace <span>/</span> Projects</div>
          <div className="topbar-status connection-ready"><span className="status-dot" />Administrator <button className="signout-button" type="button" onClick={() => void signOut()}>Sign out</button></div>
        </header>

        <div className="page-wrap">
          <section className="page-heading">
            <div>
              <div className="eyebrow"><span className="eyebrow-line" />YOUR SOFTWARE FACTORY</div>
              <h1>Projects<span className="heading-period">.</span></h1>
              <p className="subtitle">A clear home for every codebase, decision, and next step.</p>
            </div>
          <Button variant="outline" size="sm" className="button-quiet refresh-button" type="button" onClick={() => void loadProjects()} disabled={loading}>
              <RefreshCw size={15} className={loading ? 'spinning' : ''} /> Refresh
          </Button>
          </section>

          <div className="summary-row" aria-label="Workspace summary">
            <div className="summary-card"><span className="summary-icon"><FolderGit2 size={17} /></span><div><span className="summary-label">ACTIVE PROJECTS</span><strong>{projectCount.toString().padStart(2, '0')}</strong></div></div>
            <div className="summary-card summary-card-status"><span className={`summary-icon ${connection === 'ready' ? 'green-icon' : connection === 'error' ? 'error-icon' : ''}`}>{connection === 'error' ? <CircleAlert size={17} /> : <Check size={17} />}</span><div><span className="summary-label">WORKSPACE STATUS</span><strong className="status-ready">{connection === 'ready' ? 'Ready to build' : connection === 'error' ? 'Connection issue' : 'Checking…'}</strong></div></div>
            <div className="summary-note"><span className="note-star">✳</span><span>Your projects stay yours.<br /><strong>Private by default.</strong></span></div>
          </div>

          <section className="projects-layout">
            <div className="project-list-section">
              <div className="section-header">
                <div><span className="section-kicker">OVERVIEW</span><h2>Your projects <span className="count-pill">{projectCount}</span></h2></div>
                <span className="sort-label">Recently added <span aria-hidden="true">⌄</span></span>
              </div>

              {error && <div className="alert alert-error" role="alert"><CircleAlert size={17} /><span>{error}</span><button type="button" onClick={() => void loadProjects()}>Try again</button></div>}
              {notice && <div className="alert alert-success" role="status"><Check size={17} /><span>{notice}</span><button type="button" aria-label="Dismiss" onClick={() => setNotice('')}>×</button></div>}

              {loading ? (
                <div className="loading-card" role="status"><span className="loader" />Loading your projects…</div>
              ) : projectCount === 0 ? (
                <div className="empty-state">
                  <div className="empty-illustration"><FolderGit2 size={27} /><span>+</span></div>
                  <h3>Your next big thing starts here.</h3>
                  <p>Create a project to give your codebase and decisions a home.</p>
                  <a className="text-link" href="#new-project">Create your first project <ArrowUpRight size={15} /></a>
                </div>
              ) : (
                <div className="project-cards">
                  {projects.map((project, index) => (
                    <Card className="project-card" key={project.id}>
                      <div className={`project-avatar avatar-${index % 4}`} aria-hidden="true">{project.name.slice(0, 1).toUpperCase()}</div>
                      <div className="project-card-main">
                        <div className="project-title-row"><h3>{project.name}</h3><span className="project-state"><span className="status-dot" />Active</span></div>
                        <p>{project.description || 'No description yet.'}</p>
                        <div className="project-meta">
                          <span className="branch-label"><span aria-hidden="true">⌘</span> {project.default_branch}</span>
                          {project.repository_url && <a href={project.repository_url} target="_blank" rel="noreferrer">Repository <ArrowUpRight size={12} /></a>}
                          <span>Added {new Intl.DateTimeFormat(undefined, { month: 'short', day: 'numeric' }).format(new Date(project.created_at))}</span>
                        </div>
                        <button className="project-details-button" type="button" onClick={() => void openProject(project.id)}>View project details <ArrowUpRight size={13} /></button>
                      </div>
                    </Card>
                  ))}
                </div>
              )}
            </div>

            <aside className="create-panel" id="new-project">
              <div className="create-panel-heading"><span className="create-icon"><Plus size={17} /></span><div><span className="section-kicker">GET STARTED</span><h2>New project</h2></div></div>
              <p className="create-intro">Bring a codebase into your workspace. You can add context any time.</p>
              <form onSubmit={createProject}>
                <label htmlFor="project-name">Project name <span className="required-mark">*</span></label>
                <input id="project-name" name="name" value={name} onChange={(event) => setName(event.target.value)} placeholder="e.g. Atlas Platform" maxLength={120} required autoComplete="off" />
                <label htmlFor="project-description">A little context <span className="optional-mark">OPTIONAL</span></label>
                <textarea id="project-description" name="description" value={description} onChange={(event) => setDescription(event.target.value)} placeholder="What are you building?" rows={3} maxLength={2000} />
                <label htmlFor="repository-url">Repository URL <span className="optional-mark">OPTIONAL</span></label>
                <input id="repository-url" name="repository_url" type="url" value={repositoryUrl} onChange={(event) => setRepositoryUrl(event.target.value)} placeholder="https://github.com/you/project" />
                <button className="button button-primary create-button" type="submit" disabled={saving || !name.trim()}>
                  {saving ? <><span className="button-loader" />Creating project…</> : <><Plus size={16} /> Create project</>}
                </button>
                <p className="form-footnote">Saved securely to your workspace.</p>
              </form>
            </aside>
          </section>

          {dialogMode && (
            <div className="dialog-backdrop">
              <section
                className="project-dialog"
                role={dialogMode === 'delete' ? 'alertdialog' : 'dialog'}
                aria-modal="true"
                aria-labelledby="project-dialog-title"
                aria-busy={dialogBusy || dialogLoading}
              >
                <div className="dialog-heading">
                  <div>
                    <span className="section-kicker">PROJECT WORKSPACE</span>
                    <h2 id="project-dialog-title">{dialogMode === 'delete' ? 'Delete project?' : dialogMode === 'edit' ? 'Edit project' : selectedProject?.name ?? 'Project details'}</h2>
                  </div>
                  <button className="dialog-close" type="button" aria-label="Close project dialog" onClick={closeDialog} disabled={dialogBusy || dialogLoading}><X size={18} /></button>
                </div>

                {dialogError && <div className="alert alert-error" role="alert"><CircleAlert size={17} /><span>{dialogError}</span></div>}
                {dialogLoading ? (
                  <div className="loading-card dialog-loading" role="status"><span className="loader" />Loading the latest project details…</div>
                ) : selectedProject && dialogMode === 'details' ? (
                  <>
                    {showRepositorySync ? (
                      <RepositorySyncManager projectId={selectedProject.id} onClose={() => setShowRepositorySync(false)} />
                    ) : showPrinciplesWorkspace ? (
                      <PrinciplesWorkspace projectId={selectedProject.id} onClose={() => setShowPrinciplesWorkspace(false)} />
                    ) : showCredentialManager ? (
                      <CredentialManager projectId={selectedProject.id} onClose={() => setShowCredentialManager(false)} />
                    ) : <>
                    <dl className="project-detail-list">
                      <div><dt>Description</dt><dd>{selectedProject.description || 'No description yet.'}</dd></div>
                      <div><dt>Repository</dt><dd>{selectedProject.repository_url ? <a href={selectedProject.repository_url} target="_blank" rel="noreferrer">{selectedProject.repository_url}<ArrowUpRight size={13} /></a> : 'Not connected'}</dd></div>
                      <div><dt>Default branch</dt><dd>{selectedProject.default_branch}</dd></div>
                      <div><dt>Created</dt><dd>{new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(selectedProject.created_at))}</dd></div>
                      <div><dt>Last updated</dt><dd>{new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(selectedProject.updated_at))}</dd></div>
                    </dl>
                    <div className="dialog-actions">
                      <Button variant="outline" size="sm" type="button" onClick={() => setShowRepositorySync(true)}>Repository knowledge</Button>
                      <Button variant="outline" size="sm" type="button" onClick={() => setShowPrinciplesWorkspace(true)}>Principles workspace</Button>
                      <Button variant="outline" size="sm" type="button" onClick={() => setShowCredentialManager(true)}>Manage credentials</Button>
                      <Button variant="outline" size="sm" type="button" onClick={() => { setDialogError(''); setDialogMode('delete') }}><Trash2 size={15} />Delete project</Button>
                      <Button variant="default" size="sm" type="button" onClick={beginEdit}><Pencil size={15} />Edit project</Button>
                    </div>
                    </>}
                  </>
                ) : selectedProject && dialogMode === 'edit' ? (
                  <form className="dialog-form" onSubmit={(event) => void saveProject(event)}>
                    <label htmlFor="edit-project-name">Project name <span className="required-mark">*</span></label>
                    <input id="edit-project-name" value={editName} onChange={(event) => setEditName(event.target.value)} maxLength={120} required />
                    <label htmlFor="edit-project-description">Description <span className="optional-mark">OPTIONAL</span></label>
                    <textarea id="edit-project-description" value={editDescription} onChange={(event) => setEditDescription(event.target.value)} rows={3} maxLength={2000} />
                    <label htmlFor="edit-project-repository">Repository URL <span className="optional-mark">OPTIONAL</span></label>
                    <input id="edit-project-repository" type="url" value={editRepositoryUrl} onChange={(event) => setEditRepositoryUrl(event.target.value)} />
                    <label htmlFor="edit-project-branch">Default branch</label>
                    <input id="edit-project-branch" value={editDefaultBranch} onChange={(event) => setEditDefaultBranch(event.target.value)} maxLength={255} required />
                    <div className="dialog-actions">
                      <Button variant="outline" size="sm" type="button" onClick={() => { setDialogError(''); setDialogMode('details') }} disabled={dialogBusy}>Cancel</Button>
                      <Button variant="default" size="sm" type="submit" disabled={dialogBusy || !editName.trim() || !editDefaultBranch.trim()}>{dialogBusy ? 'Saving…' : 'Save changes'}</Button>
                    </div>
                  </form>
                ) : selectedProject && dialogMode === 'delete' ? (
                  <div className="delete-confirmation">
                    <p>Delete <strong>{selectedProject.name}</strong>? This removes the project from the workspace and cannot be undone.</p>
                    <div className="dialog-actions">
                      <Button variant="outline" size="sm" type="button" onClick={() => { setDialogError(''); setDialogMode('details') }} disabled={dialogBusy}>Keep project</Button>
                      <Button variant="default" className="bg-red-700 text-white hover:bg-red-800" size="sm" type="button" onClick={() => void deleteProject()} disabled={dialogBusy}>{dialogBusy ? 'Deleting…' : 'Delete permanently'}</Button>
                    </div>
                  </div>
                ) : null}
              </section>
            </div>
          )}

          {showOllamaSettings && <div className="dialog-backdrop"><section className="project-dialog ollama-dialog" role="dialog" aria-modal="true" aria-labelledby="ollama-title"><OllamaProviderManager onClose={() => setShowOllamaSettings(false)} /></section></div>}

          <footer className="page-footer"><span>CALIPER <span className="footer-dot">·</span> BUILT FOR THOUGHTFUL WORK</span><span>Project workspace <span aria-hidden="true">·</span> v0.1</span></footer>
        </div>
      </main>
    </div>
  )
}

export default App
