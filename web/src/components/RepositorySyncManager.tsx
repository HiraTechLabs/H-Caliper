import { useCallback, useEffect, useState } from 'react'

type SyncState = {
  status: string
  source_url: string
  branch: string
  revision: string | null
  attempted_at: string
  last_success_at: string | null
  error_code: string | null
  document_count: number
  task_id: string | null
}
type KnowledgeDocument = { path: string; revision: string; sha256: string; content: string; synced_at: string }
type Credential = { id: string; name: string; enabled: boolean; deletion_pending: boolean }

export function RepositorySyncManager({ projectId, onClose }: { projectId: string; onClose: () => void }) {
  const base = `/api/projects/${projectId}`
  const [state, setState] = useState<SyncState | null>(null)
  const [documents, setDocuments] = useState<KnowledgeDocument[]>([])
  const [credentials, setCredentials] = useState<Credential[]>([])
  const [credentialId, setCredentialId] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')

  const reload = useCallback(async () => {
    const [stateResponse, docsResponse, credentialsResponse] = await Promise.all([
      fetch(`${base}/sync`), fetch(`${base}/knowledge`), fetch(`${base}/credentials`),
    ])
    if (!stateResponse.ok || !docsResponse.ok || !credentialsResponse.ok) throw new Error('Could not load repository status and knowledge.')
    setState(await stateResponse.json() as SyncState)
    setDocuments(await docsResponse.json() as KnowledgeDocument[])
    setCredentials(await credentialsResponse.json() as Credential[])
  }, [base])

  useEffect(() => { void reload().catch((cause: unknown) => setError(cause instanceof Error ? cause.message : 'Could not load repository status.')) }, [reload])

  async function synchronize() {
    setBusy(true)
    setError('')
    setNotice('')
    try {
      const response = await fetch(`${base}/sync`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(credentialId ? { credential_id: credentialId } : {}),
      })
      if (!response.ok) {
        const failure = await response.json().catch(() => null) as { detail?: string | { message?: string; state?: SyncState } } | null
        if (typeof failure?.detail === 'object' && failure.detail?.state) setState(failure.detail.state)
        throw new Error(typeof failure?.detail === 'object' ? failure.detail.message ?? 'Repository synchronization failed.' : typeof failure?.detail === 'string' ? failure.detail : 'Repository synchronization failed.')
      }
      let confirmed = await response.json() as SyncState
      setState(confirmed)
      for (let attempt = 0; attempt < 120 && ['queued', 'running'].includes(confirmed.status); attempt += 1) {
        await new Promise((resolve) => window.setTimeout(resolve, 1000))
        const statusResponse = await fetch(`${base}/sync`)
        if (!statusResponse.ok) throw new Error('The task is still running, but its status could not be read.')
        confirmed = await statusResponse.json() as SyncState
        setState(confirmed)
      }
      await reload()
      if (['queued', 'running'].includes(confirmed.status)) {
        setNotice('Synchronization continues on the server. You can close this panel and check its status later.')
      } else if (confirmed.status === 'synchronized') {
        setNotice(`Synchronized ${confirmed.document_count} knowledge files from ${confirmed.branch}.`)
      } else {
        throw new Error(`Synchronization did not finish successfully (${confirmed.error_code ?? confirmed.status}).`)
      }
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Repository synchronization failed.')
      try { await reload() } catch { /* Keep the last confirmed view visible. */ }
    } finally {
      setBusy(false)
    }
  }

  return <section className="credential-manager" aria-labelledby="repository-sync-title">
    <div className="credential-manager-heading"><div><span className="section-kicker">PROJECT KNOWLEDGE</span><h3 id="repository-sync-title">Repository sync</h3></div><button type="button" className="dialog-close" aria-label="Close repository sync" onClick={onClose}>×</button></div>
    <p className="credential-help">Sync reads project guidance files from the configured branch. Content is stored as plain text and rendered safely.</p>
    {error && <p className="auth-error" role="alert">{error}</p>}
    {notice && <p className="credential-notice" role="status">{notice}</p>}
    {state && <dl className="project-detail-list sync-state">
      <div><dt>Status</dt><dd>{state.status}</dd></div><div><dt>Branch</dt><dd>{state.branch}</dd></div>
      <div><dt>Revision</dt><dd>{state.revision?.slice(0, 12) ?? 'Not synced'}</dd></div>
      <div><dt>Last successful sync</dt><dd>{state.last_success_at ? new Date(state.last_success_at).toLocaleString() : 'Never'}</dd></div>
      {state.error_code && <div><dt>Last error</dt><dd>{state.error_code}</dd></div>}
    </dl>}
    {credentials.some((credential) => credential.enabled && !credential.deletion_pending) && <>
      <label htmlFor="sync-credential">HTTPS credential</label>
      <select id="sync-credential" value={credentialId} onChange={(event) => setCredentialId(event.target.value)}>
        <option value="">No credential (public repository)</option>
        {credentials.filter((credential) => credential.enabled && !credential.deletion_pending).map((credential) => <option key={credential.id} value={credential.id}>{credential.name}</option>)}
      </select>
    </>}
    <div className="credential-actions sync-actions"><button className="button button-primary" type="button" disabled={busy || !state?.source_url} onClick={() => void synchronize()}>{busy ? 'Synchronizing…' : 'Synchronize now'}</button></div>
    <div className="knowledge-list" aria-label="Synchronized knowledge files">
      {documents.length === 0 ? <p>No repository knowledge has been synchronized.</p> : documents.map((document) => <details key={document.path}><summary>{document.path}</summary><pre>{document.content}</pre></details>)}
    </div>
  </section>
}
