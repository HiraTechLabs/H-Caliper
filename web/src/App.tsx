import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { Activity, ArrowUpRight, Boxes, Check, CircleAlert, FolderGit2, Plus, RefreshCw, Sparkles } from 'lucide-react'
import { Button } from './components/ui/button'
import { Card } from './components/ui/card'

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
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')

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

  useEffect(() => { void loadProjects() }, [loadProjects])

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

  const projectCount = projects.length

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
          <a className="nav-item nav-muted" href="#principles" aria-disabled="true"><Sparkles size={17} />Knowledge<span className="soon-tag">SOON</span></a>
        </nav>
        <div className="sidebar-bottom">
          <div className={`connection-indicator connection-${connection}`}><span className="status-dot" />{connection === 'ready' ? 'Workspace connected' : connection === 'error' ? 'Workspace unavailable' : 'Connecting…'}</div>
          <p>Project context, ready for the work ahead.</p>
        </div>
      </aside>

      <main className="main-content" id="projects">
        <header className="topbar">
          <div className="breadcrumb">Workspace <span>/</span> Projects</div>
          <div className={`topbar-status connection-${connection}`}><span className="status-dot" />{connection === 'ready' ? 'Workspace connected' : connection === 'error' ? 'Connection issue' : 'Checking workspace'}</div>
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

          <footer className="page-footer"><span>CALIPER <span className="footer-dot">·</span> BUILT FOR THOUGHTFUL WORK</span><span>Project workspace <span aria-hidden="true">·</span> v0.1</span></footer>
        </div>
      </main>
    </div>
  )
}

export default App
