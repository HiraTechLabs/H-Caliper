import { useEffect, useState, type FormEvent } from 'react'

type OllamaSettings = {
  endpoint_url: string
  selected_model_id: string | null
  status: 'not_configured' | 'configured' | 'reachable' | 'failed'
  checked_at: string | null
  error_code: string | null
  models: string[]
}

export function OllamaProviderManager({ onClose }: { onClose: () => void }) {
  const [settings, setSettings] = useState<OllamaSettings | null>(null)
  const [endpoint, setEndpoint] = useState('')
  const [busy, setBusy] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')

  async function reload() {
    setLoading(true)
    try {
      const response = await fetch('/api/providers/ollama')
      if (!response.ok) throw new Error('Could not load the Ollama connection settings.')
      const current = await response.json() as OllamaSettings
      setSettings(current)
      setEndpoint(current.endpoint_url)
    } finally { setLoading(false) }
  }

  useEffect(() => { void reload().catch((cause: unknown) => setError(cause instanceof Error ? cause.message : 'Could not load Ollama settings.')) }, [])

  async function saveEndpoint(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError(''); setNotice('')
    try {
      const response = await fetch('/api/providers/ollama', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ endpoint_url: endpoint.trim() }) })
      if (!response.ok) {
        const result = await response.json().catch(() => null) as { detail?: string } | null
        throw new Error(result?.detail ?? 'The Ollama endpoint was not saved.')
      }
      const saved = await response.json() as OllamaSettings
      setSettings(saved); setEndpoint(saved.endpoint_url)
      setNotice('Endpoint saved. Validate it to discover the models available on the server.')
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'The endpoint was not saved.') }
    finally { setBusy(false) }
  }

  async function validateEndpoint() {
    setBusy(true); setError(''); setNotice('')
    try {
      const response = await fetch('/api/providers/ollama/validate', { method: 'POST' })
      if (!response.ok) {
        const result = await response.json().catch(() => null) as { detail?: string } | null
        throw new Error(result?.detail ?? 'Ollama validation failed.')
      }
      const fresh = await response.json() as OllamaSettings
      setSettings(fresh)
      setNotice(fresh.status === 'reachable' ? `Ollama is reachable. Found ${fresh.models.length} model${fresh.models.length === 1 ? '' : 's'}.` : `Ollama could not be validated (${fresh.error_code ?? fresh.status}).`)
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Ollama validation failed.') }
    finally { setBusy(false) }
  }

  async function selectModel(modelId: string) {
    if (!modelId) return
    setBusy(true); setError(''); setNotice('')
    try {
      const response = await fetch('/api/providers/ollama/model', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ model_id: modelId }) })
      if (!response.ok) {
        const result = await response.json().catch(() => null) as { detail?: string } | null
        throw new Error(result?.detail ?? 'The model selection was not saved.')
      }
      setSettings(await response.json() as OllamaSettings)
      setNotice('Selected model saved to Caliper.')
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'The model selection was not saved.') }
    finally { setBusy(false) }
  }

  return <section className="ollama-manager" aria-labelledby="ollama-title">
    <div className="credential-manager-heading"><div><span className="section-kicker">MODEL CONNECTION</span><h3 id="ollama-title">Ollama</h3></div><button type="button" className="dialog-close" aria-label="Close Ollama settings" onClick={onClose}>×</button></div>
    <p className="credential-help">Configure the Ollama endpoint reachable from the Caliper server. The configured administrator controls this outbound connection. Endpoint credentials and URL paths are not accepted.</p>
    {loading && <p className="credential-help" role="status">Loading saved Ollama settings…</p>}
    {error && <p className="auth-error" role="alert">{error}</p>}{notice && <p className={settings?.status === 'failed' ? 'workspace-stale' : 'credential-notice'} role="status">{notice}</p>}
    {settings && <dl className="project-detail-list ollama-status"><div><dt>Connection status</dt><dd>{settings.status}{settings.error_code ? ` · ${settings.error_code}` : ''}</dd></div><div><dt>Last checked</dt><dd>{settings.checked_at ? new Date(settings.checked_at).toLocaleString() : 'Not checked'}</dd></div></dl>}
    <form className="credential-form" onSubmit={(event) => void saveEndpoint(event)}>
      <label htmlFor="ollama-endpoint">Ollama endpoint URL</label>
      <input id="ollama-endpoint" type="url" inputMode="url" value={endpoint} onChange={(event) => setEndpoint(event.target.value)} placeholder="http://host.docker.internal:11434" maxLength={512} required disabled={loading || busy} />
      <div className="credential-actions"><button type="submit" disabled={loading || busy || !endpoint.trim()}>Save endpoint</button><button type="button" disabled={loading || busy || !settings?.endpoint_url} onClick={() => void validateEndpoint()}>{busy ? 'Working…' : 'Validate and discover'}</button></div>
    </form>
    {settings?.models.length ? <div className="ollama-model-selection"><label htmlFor="ollama-model">Available model</label><select id="ollama-model" value={settings.selected_model_id ?? ''} disabled={busy || settings.status !== 'reachable'} onChange={(event) => void selectModel(event.target.value)}><option value="">Choose a discovered model</option>{settings.models.map((model) => <option key={model} value={model}>{model}</option>)}</select></div> : settings?.status === 'reachable' ? <p className="credential-help">The endpoint is reachable, but it reported no installed models.</p> : null}
    <p className="credential-help">Ollama API authentication and model invocation are not configured in this slice. Only a discovered model can be selected.</p>
  </section>
}
