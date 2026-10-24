import { useEffect, useState, type FormEvent } from 'react'

type Prompt = { type?: string; key?: string; message?: string; placeholder?: string; options?: string[]; when?: Record<string, string> }
type AuthMethod = { type: 'api' | 'oauth'; label: string; prompts: Prompt[] }
type Model = { id: string; name: string }
type Provider = { id: string; name: string; models: Model[] }
type Snapshot = {
  status: string; error_code: string | null; checked_at: string | null; version: string | null
  providers: Provider[]; connected_provider_ids: string[]; auth_methods: Record<string, AuthMethod[]>
  selected_provider_id: string | null; selected_model_id: string | null
}

export function OpenCodeProviderManager({ onClose }: { onClose: () => void }) {
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null)
  const [providerId, setProviderId] = useState('')
  const [apiKey, setApiKey] = useState('')
  const [metadata, setMetadata] = useState<Record<string, string>>({})
  const [oauthInputs, setOauthInputs] = useState<Record<string, string>>({})
  const [authorization, setAuthorization] = useState<{ providerId: string; method: number; url: string; instructions: string; mode: string } | null>(null)
  const [oauthCode, setOauthCode] = useState('')
  const [busy, setBusy] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')

  const providers = snapshot?.providers ?? []
  const selectedProvider = providers.find((provider) => provider.id === providerId)
  const methods = snapshot?.auth_methods[providerId] ?? []
  const connected = new Set(snapshot?.connected_provider_ids ?? [])

  async function request(path: string, init?: RequestInit) {
    const response = await fetch(path, init)
    if (!response.ok) {
      const result = await response.json().catch(() => null) as { detail?: string } | null
      throw new Error(result?.detail ?? 'OpenCode request failed.')
    }
    return response.json()
  }

  async function reload() {
    setLoading(true); setError('')
    try {
      const fresh = await request('/api/providers/opencode') as Snapshot
      setSnapshot(fresh)
      setProviderId((current) => current || fresh.providers[0]?.id || '')
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Could not load OpenCode settings.') }
    finally { setLoading(false) }
  }

  useEffect(() => { void reload() }, [])

  async function connectKey(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError(''); setNotice('')
    try {
      const response = await request(`/api/providers/opencode/auth/${encodeURIComponent(providerId)}/api-key`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ api_key: apiKey, metadata }) }) as Snapshot
      setSnapshot(response); setApiKey(''); setMetadata({}); setNotice('Provider credentials saved securely.')
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Could not connect provider.') }
    finally { setBusy(false) }
  }

  async function beginOAuth(index: number) {
    setBusy(true); setError(''); setNotice('')
    try {
      const result = await request(`/api/providers/opencode/auth/${encodeURIComponent(providerId)}/oauth/authorize`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ method: index, inputs: oauthInputs }) }) as { url: string; method: string; instructions: string }
      setAuthorization({ providerId, method: index, url: result.url, instructions: result.instructions, mode: result.method });
      window.open(result.url, '_blank', 'noopener,noreferrer')
      setOauthInputs({}); setNotice('Authorization page opened in a new tab.')
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Could not start provider authorization.') }
    finally { setBusy(false) }
  }

  async function finishOAuth(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (!authorization) return
    setBusy(true); setError(''); setNotice('')
    try {
      if (authorization.mode !== 'code') {
        const fresh = await request('/api/providers/opencode/validate', { method: 'POST' }) as Snapshot
        setSnapshot(fresh); setAuthorization(null); setNotice('Provider authorization status refreshed.')
        return
      }
      const fresh = await request(`/api/providers/opencode/auth/${encodeURIComponent(authorization.providerId)}/oauth/callback`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ method: authorization.method, code: oauthCode }) }) as Snapshot
      setSnapshot(fresh); setOauthCode(''); setAuthorization(null); setNotice('Provider account connected securely.')
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Could not complete provider authorization.') }
    finally { setBusy(false) }
  }

  async function disconnect(id: string) {
    setBusy(true); setError(''); setNotice('')
    try {
      const fresh = await request(`/api/providers/opencode/auth/${encodeURIComponent(id)}`, { method: 'DELETE' }) as Snapshot
      setSnapshot(fresh); setNotice('Provider disconnected.')
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Could not disconnect provider.') }
    finally { setBusy(false) }
  }

  async function selectModel(value: string) {
    const [id, ...parts] = value.split('::'); const modelId = parts.join('::')
    if (!id || !modelId) return
    setBusy(true); setError(''); setNotice('')
    try {
      await request('/api/providers/opencode/model', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ provider_id: id, model_id: modelId }) })
      const fresh = await request('/api/providers/opencode') as Snapshot
      setSnapshot(fresh); setNotice('Default model saved to Caliper.')
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Could not select model.') }
    finally { setBusy(false) }
  }

  const selectedValue = snapshot?.selected_provider_id && snapshot.selected_model_id ? `${snapshot.selected_provider_id}::${snapshot.selected_model_id}` : ''

  return <section className="ollama-manager" aria-labelledby="opencode-title">
    <div className="credential-manager-heading"><div><span className="section-kicker">MODEL CONNECTION</span><h3 id="opencode-title">OpenCode providers</h3></div><button type="button" className="dialog-close" aria-label="Close OpenCode settings" onClick={onClose}>×</button></div>
    <p className="credential-help">Sign in with a provider account or connect an API key. Credentials are encrypted in Caliper and loaded into temporary runtime storage.</p>
    {loading && <p className="credential-help" role="status">Loading provider catalog…</p>}
    {error && <p className="auth-error" role="alert">{error}</p>}{notice && <p className="credential-notice" role="status">{notice}</p>}
    {snapshot && <dl className="project-detail-list ollama-status"><div><dt>OpenCode status</dt><dd>{snapshot.status}{snapshot.error_code ? ` · ${snapshot.error_code}` : ''}</dd></div><div><dt>Version</dt><dd>{snapshot.version ?? 'Unavailable'}</dd></div><div><dt>Connected providers</dt><dd>{connected.size}</dd></div></dl>}
    <label className="credential-help" htmlFor="opencode-provider">Provider</label>
    <select id="opencode-provider" value={providerId} disabled={loading || busy} onChange={(event) => { setProviderId(event.target.value); setMetadata({}); setOauthInputs({}); setAuthorization(null) }}>
      {providers.map((provider) => <option key={provider.id} value={provider.id}>{provider.name}{connected.has(provider.id) ? ' · connected' : ''}</option>)}
    </select>
    {selectedProvider && <>
      {connected.has(providerId) && <button className="provider-disconnect" type="button" disabled={busy} onClick={() => void disconnect(providerId)}>Disconnect {selectedProvider.name}</button>}
      {methods.map((method, methodIndex) => method.type === 'api' ? <form className="credential-form" key={`${method.type}-${methodIndex}`} onSubmit={(event) => void connectKey(event)}>
        <h4>{method.label || 'API key'}</h4>
        {method.prompts.filter((prompt) => !prompt.when || Object.entries(prompt.when).every(([key, value]) => metadata[key] === value)).map((prompt, index) => <label key={`${prompt.key}-${index}`}>{prompt.message || prompt.key || 'Provider option'}
          {prompt.options?.length ? <select value={metadata[prompt.key ?? ''] ?? ''} onChange={(event) => setMetadata((current) => ({ ...current, [prompt.key ?? '']: event.target.value }))}><option value="">Choose…</option>{prompt.options.map((option) => <option key={option} value={option}>{option}</option>)}</select> : <input type="text" autoComplete="off" value={metadata[prompt.key ?? ''] ?? ''} onChange={(event) => setMetadata((current) => ({ ...current, [prompt.key ?? '']: event.target.value }))} placeholder={prompt.placeholder} />}
        </label>)}
        <label htmlFor="opencode-api-key">API key</label><input id="opencode-api-key" type="password" autoComplete="new-password" value={apiKey} onChange={(event) => setApiKey(event.target.value)} required maxLength={8192} />
        <div className="credential-actions"><button type="submit" disabled={busy || !apiKey}>{busy ? 'Saving…' : 'Save API key'}</button></div>
      </form> : <div className="credential-form" key={`${method.type}-${methodIndex}`}><h4>{method.label || 'Account login'}</h4>
        {method.prompts.map((prompt, index) => <label key={`${prompt.key}-${index}`}>{prompt.message || prompt.key || 'Account option'}<input type="text" value={oauthInputs[prompt.key ?? ''] ?? ''} onChange={(event) => setOauthInputs((current) => ({ ...current, [prompt.key ?? '']: event.target.value }))} placeholder={prompt.placeholder} /></label>)}
        <div className="credential-actions"><button type="button" disabled={busy} onClick={() => void beginOAuth(methodIndex)}>Sign in with account</button></div>
      </div>)}
      {selectedProvider.models.length > 0 && connected.has(providerId) && <p className="credential-help">Choose the default model <select aria-label="Default model" value={selectedValue} disabled={busy} onChange={(event) => void selectModel(event.target.value)}><option value="">Choose a model</option>{providers.filter((provider) => connected.has(provider.id)).flatMap((provider) => provider.models.map((model) => <option key={`${provider.id}::${model.id}`} value={`${provider.id}::${model.id}`}>{provider.name} · {model.name}</option>))}</select></p>}
    </>}
    {authorization && <form className="credential-form" onSubmit={(event) => void finishOAuth(event)}><h4>Complete sign-in</h4><p className="credential-help">{authorization.instructions || 'Finish authorization in the opened provider tab.'}</p>{authorization.mode === 'code' && <><label htmlFor="opencode-oauth-code">Authorization code</label><input id="opencode-oauth-code" type="password" autoComplete="off" value={oauthCode} onChange={(event) => setOauthCode(event.target.value)} required /></>}<div className="credential-actions"><a href={authorization.url} target="_blank" rel="noreferrer">Open authorization page</a><button type="submit" disabled={busy || (authorization.mode === 'code' && !oauthCode)}>{authorization.mode === 'code' ? 'Finish sign-in' : 'Check sign-in'}</button></div></form>}
    <div className="credential-actions"><button type="button" disabled={busy} onClick={() => void reload()}>Refresh providers</button></div>
  </section>
}
