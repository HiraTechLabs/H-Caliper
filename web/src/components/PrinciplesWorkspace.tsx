import { useCallback, useEffect, useMemo, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import rehypeSanitize from 'rehype-sanitize'

type KnowledgeDocument = { path: string; revision: string; sha256: string; content: string; synced_at: string }
type SyncState = { status: string; source_url: string; branch: string; revision: string | null; last_success_at: string | null; error_code: string | null; task_id: string | null }
type GraphNode = { id: string; label?: string; kind?: string; status?: string }
type GraphEdge = { from: string; to: string; relation: string }
type Workspace = { sync: SyncState; documents: KnowledgeDocument[]; graph: { nodes: GraphNode[]; edges: GraphEdge[] } | null; graph_errors: string[] }
type View = 'principles' | 'manifest' | 'decisions' | 'graph'

const viewLabels: Record<View, string> = { principles: 'Principles', manifest: 'Manifest', decisions: 'Decisions', graph: 'Graph' }

function titleFor(path: string) {
  return path.split('/').at(-1)?.replace(/\.(md|mdx|yaml|yml)$/i, '').replace(/[-_]/g, ' ') ?? path
}

export function PrinciplesWorkspace({ projectId, onClose }: { projectId: string; onClose: () => void }) {
  const [workspace, setWorkspace] = useState<Workspace | null>(null)
  const [view, setView] = useState<View>('principles')
  const [selectedPath, setSelectedPath] = useState('')
  const [search, setSearch] = useState('')
  const [selectedNode, setSelectedNode] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')

  const reload = useCallback(async () => {
    const response = await fetch(`/api/projects/${projectId}/workspace`)
    if (!response.ok) throw new Error('Could not load the synchronized project workspace.')
    const result = await response.json() as Workspace
    setWorkspace(result)
    if (!result.documents.some((document) => document.path === selectedPath)) {
      setSelectedPath(result.documents.find((document) => document.path.startsWith('.caliper/principles/'))?.path ?? '')
    }
  }, [projectId, selectedPath])

  useEffect(() => { void reload().catch((cause: unknown) => setError(cause instanceof Error ? cause.message : 'Could not load project knowledge.')) }, [reload])

  const visibleDocuments = useMemo(() => {
    if (!workspace) return []
    const query = search.trim().toLocaleLowerCase()
    return workspace.documents.filter((document) => {
      const inView = view === 'principles' ? document.path.startsWith('.caliper/principles/')
        : view === 'manifest' ? document.path === '.caliper/manifest.yaml'
          : view === 'decisions' ? document.path === '.caliper/DECISIONS.md' : false
      return inView && (!query || `${document.path}\n${document.content}`.toLocaleLowerCase().includes(query))
    })
  }, [search, view, workspace])
  const selectedDocument = visibleDocuments.find((document) => document.path === selectedPath) ?? visibleDocuments[0]
  const decisionCards = useMemo(() => {
    const document = visibleDocuments.find((item) => item.path === '.caliper/DECISIONS.md')
    if (!document) return []
    return document.content.split(/(?=^##\s+D-\d+\b)/m).filter((section) => /^##\s+D-\d+\b/m.test(section))
      .filter((section) => !search.trim() || section.toLocaleLowerCase().includes(search.trim().toLocaleLowerCase()))
  }, [search, visibleDocuments])
  const graph = workspace?.graph
  const graphPositions = graph?.nodes.map((node, index) => {
    const angle = (2 * Math.PI * index / Math.max(graph.nodes.length, 1)) - Math.PI / 2
    return { node, x: 450 + Math.cos(angle) * 320, y: 220 + Math.sin(angle) * 155 }
  }) ?? []
  const positionById = new Map(graphPositions.map(({ node, x, y }) => [node.id, { x, y }]))

  async function synchronize() {
    setBusy(true); setError(''); setNotice('')
    try {
      const response = await fetch(`/api/projects/${projectId}/sync`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' })
      if (!response.ok) throw new Error('Synchronization could not be queued. Check the project repository and try again.')
      let status = await response.json() as SyncState
      for (let attempt = 0; attempt < 120 && ['queued', 'running'].includes(status.status); attempt += 1) {
        await new Promise((resolve) => window.setTimeout(resolve, 1000))
        const poll = await fetch(`/api/projects/${projectId}/sync`)
        if (!poll.ok) throw new Error('The synchronization task is active, but its current status could not be read.')
        status = await poll.json() as SyncState
      }
      await reload()
      if (status.status === 'synchronized') setNotice(`Workspace refreshed from ${status.branch} at ${status.revision?.slice(0, 12) ?? 'the confirmed revision'}.`)
      else if (['queued', 'running'].includes(status.status)) setNotice('Synchronization is still running on the server. The workspace will show the confirmed revision after it finishes.')
      else throw new Error(`Synchronization did not complete (${status.error_code ?? status.status}). The saved documents may be stale.`)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Synchronization failed.')
      try { await reload() } catch { /* Preserve the last server-confirmed snapshot. */ }
    } finally { setBusy(false) }
  }

  function resolveLink(href: string | undefined) {
    if (!href) return { document: undefined, externalHref: undefined }
    try {
      const target = new URL(href, `https://caliper.invalid/${selectedDocument?.path ?? ''}`)
      if (target.origin === 'https://caliper.invalid') {
        const path = decodeURIComponent(target.pathname).replace(/^\//, '')
        const document = workspace?.documents.find((item) => item.path === path || item.path.endsWith(`/${path}`))
        return { document, externalHref: undefined }
      }
      return { document: undefined, externalHref: target.protocol === 'https:' ? href : undefined }
    } catch {
      return { document: undefined, externalHref: undefined }
    }
  }

  return <section className="principles-workspace" aria-labelledby="knowledge-title">
    <div className="credential-manager-heading"><div><span className="section-kicker">REVISIONED PROJECT CONTEXT</span><h3 id="knowledge-title">Knowledge workspace</h3></div><button type="button" className="dialog-close" aria-label="Close knowledge workspace" onClick={onClose}>×</button></div>
    {workspace && <>
      <div className="workspace-source" aria-label="Repository revision and synchronization status">
        <div><span>Repository</span><strong title={workspace.sync.source_url}>{workspace.sync.source_url || 'Not configured'}</strong></div>
        <div><span>Branch</span><strong>{workspace.sync.branch || '—'}</strong></div>
        <div><span>Revision</span><strong title={workspace.sync.revision ?? ''}>{workspace.sync.revision?.slice(0, 12) ?? 'Not synchronized'}</strong></div>
        <div><span>Last successful sync</span><strong>{workspace.sync.last_success_at ? new Date(workspace.sync.last_success_at).toLocaleString() : 'Never'}</strong></div>
        <div><span>Status</span><strong>{workspace.sync.status}{workspace.sync.error_code ? ` · ${workspace.sync.error_code}` : ''}</strong></div>
      </div>
      {workspace.sync.status === 'stale' && <p className="workspace-stale" role="status">Showing the last confirmed snapshot. It is stale and needs a successful synchronization.</p>}
    </>}
    {error && <p className="auth-error" role="alert">{error}</p>}{notice && <p className="credential-notice" role="status">{notice}</p>}
    <div className="workspace-toolbar"><nav aria-label="Knowledge views" className="workspace-tabs">{(Object.keys(viewLabels) as View[]).map((item) => <button key={item} type="button" aria-current={view === item ? 'page' : undefined} onClick={() => { setView(item); setSelectedPath('') }}>{viewLabels[item]}</button>)}</nav><button className="button button-primary" type="button" disabled={busy || !workspace?.sync.source_url} onClick={() => void synchronize()}>{busy ? 'Synchronizing…' : 'Synchronize'}</button></div>
    {view === 'graph' ? <div className="workspace-graph-view">
      {workspace?.graph_errors.map((message) => <p className="workspace-graph-error" role="alert" key={message}>{message}</p>)}
      {graph && <><div className="workspace-graph-canvas" role="group" aria-label="Architecture graph from .caliper/graph.yaml">
        <svg viewBox="0 0 900 440" role="img" aria-label={`${graph.nodes.length} components and ${graph.edges.length} relationships`}>
          <defs><marker id="graph-arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 z" fill="#99aa9f" /></marker></defs>
          {graph.edges.map((edge, index) => { const from = positionById.get(edge.from); const to = positionById.get(edge.to); return from && to ? <g key={`${edge.from}-${edge.to}-${index}`}><line x1={from.x} y1={from.y} x2={to.x} y2={to.y} stroke="#b7c8be" strokeWidth="1.5" markerEnd="url(#graph-arrow)" /><title>{edge.relation}</title></g> : null })}
          {graphPositions.map(({ node, x, y }) => <g key={node.id} tabIndex={0} role="button" aria-label={`${node.label ?? node.id}, ${node.status ?? 'status not specified'}`} aria-pressed={selectedNode === node.id} onClick={() => setSelectedNode(node.id)} onKeyDown={(event) => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); setSelectedNode(node.id) } }} className={`graph-node ${selectedNode === node.id ? 'graph-node-selected' : ''}`}><rect x={x - 72} y={y - 25} width="144" height="50" rx="12" /><text x={x} y={y - 3}>{(node.label ?? node.id).slice(0, 21)}</text><text x={x} y={y + 14} className="graph-node-status">{node.status ?? 'status unspecified'}</text></g>)}
        </svg>
      </div><div className="graph-node-list" aria-label="Graph components">{graph.nodes.map((node) => <button type="button" key={node.id} aria-pressed={selectedNode === node.id} onClick={() => setSelectedNode(node.id)}><strong>{node.label ?? node.id}</strong><span>{node.kind ?? 'component'} · {node.status ?? 'status unspecified'}</span></button>)}</div>
      {selectedNode && <p className="graph-selection" role="status">Selected component: <strong>{graph.nodes.find((node) => node.id === selectedNode)?.label ?? selectedNode}</strong></p>}</>}
    </div> : <div className="workspace-document-layout">
      <aside className="workspace-document-nav"><label htmlFor="knowledge-search">Search this view</label><input id="knowledge-search" type="search" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search knowledge…" />
        <nav aria-label={`${viewLabels[view]} documents`}>{visibleDocuments.map((document) => <button type="button" key={document.path} aria-current={(selectedDocument?.path === document.path) ? 'page' : undefined} onClick={() => setSelectedPath(document.path)}><strong>{titleFor(document.path)}</strong><span>{document.path}</span></button>)}</nav>
        {visibleDocuments.length === 0 && <p>{workspace ? 'No matching documents in this view for the synchronized revision.' : 'Load the repository snapshot to explore guidance.'}</p>}
      </aside>
      <article className="workspace-markdown" aria-label={selectedDocument ? titleFor(selectedDocument.path) : 'Knowledge document'}>
        {view === 'decisions' ? <><p className="workspace-document-path">Decision records · {decisionCards.length}</p>{decisionCards.length ? decisionCards.map((section, index) => <section className="decision-card" key={`${index}-${section.slice(0, 30)}`}><ReactMarkdown rehypePlugins={[rehypeSanitize]} components={{ a: ({ href, children }) => { const link = resolveLink(href); return link.document ? <a href="#knowledge-document" onClick={(event) => { event.preventDefault(); const targetView: View = link.document?.path === '.caliper/manifest.yaml' ? 'manifest' : link.document?.path === '.caliper/DECISIONS.md' ? 'decisions' : 'principles'; setView(targetView); setSelectedPath(link.document?.path ?? '') }}>{children}</a> : link.externalHref ? <a href={link.externalHref} target="_blank" rel="noreferrer">{children}</a> : <span className="workspace-internal-link">{children}</span> } }}>{section}</ReactMarkdown></section>) : <p className="workspace-empty">No decision records match this search.</p>}</> : selectedDocument ? <><p className="workspace-document-path">{selectedDocument.path}</p><ReactMarkdown rehypePlugins={[rehypeSanitize]} components={{ a: ({ href, children }) => { const link = resolveLink(href); return link.document ? <a href="#knowledge-document" onClick={(event) => { event.preventDefault(); const targetView: View = link.document?.path === '.caliper/manifest.yaml' ? 'manifest' : link.document?.path === '.caliper/DECISIONS.md' ? 'decisions' : 'principles'; setView(targetView); setSelectedPath(link.document?.path ?? '') }}>{children}</a> : link.externalHref ? <a href={link.externalHref} target="_blank" rel="noreferrer">{children}</a> : <span className="workspace-internal-link">{children}</span> } }}>{selectedDocument.content}</ReactMarkdown></> : <p className="workspace-empty">{workspace?.sync.status === 'synchronized' ? 'No documents are available for this view in the current revision.' : 'Synchronize the project repository to load its canonical guidance files.'}</p>}
      </article>
    </div>}
  </section>
}
