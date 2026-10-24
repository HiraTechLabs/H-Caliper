import { useEffect, useState } from 'react'

type ModelOption = {
  provider_type: 'ollama' | 'opencode'
  provider_id: string
  provider_name: string
  model_id: string
  model_name: string
}
type Selection = Pick<ModelOption, 'provider_type' | 'provider_id' | 'model_id'> & {
  updated_at: string
}
type Snapshot = { selection: Selection | null; options: ModelOption[] }

function valueFor(model: Pick<ModelOption, 'provider_type' | 'provider_id' | 'model_id'>) {
  return JSON.stringify([model.provider_type, model.provider_id, model.model_id])
}

export function ProjectModelManager({
  projectId,
  onClose,
}: {
  projectId: string
  onClose: () => void
}) {
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null)
  const [selected, setSelected] = useState('')
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')

  async function reload() {
    setLoading(true)
    setError('')
    try {
      const response = await fetch(`/api/projects/${projectId}/model`)
      if (!response.ok) throw new Error('Could not load the project model settings.')
      const fresh = await response.json() as Snapshot
      setSnapshot(fresh)
      setSelected(fresh.selection ? valueFor(fresh.selection) : '')
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Could not load the project model settings.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { void reload() }, [projectId])

  async function save() {
    if (!selected || !snapshot) return
    const [provider_type, provider_id, model_id] = JSON.parse(selected) as [string, string, string]
    setBusy(true)
    setError('')
    setNotice('')
    try {
      const response = await fetch(`/api/projects/${projectId}/model`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ provider_type, provider_id, model_id }),
      })
      if (!response.ok) {
        const result = await response.json().catch(() => null) as { detail?: string } | null
        throw new Error(result?.detail ?? 'The project model was not saved.')
      }
      const fresh = await response.json() as Snapshot
      setSnapshot(fresh)
      setSelected(fresh.selection ? valueFor(fresh.selection) : '')
      setNotice('Model selection saved for this project.')
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'The project model was not saved.')
    } finally {
      setBusy(false)
    }
  }

  async function clear() {
    setBusy(true)
    setError('')
    setNotice('')
    try {
      const response = await fetch(`/api/projects/${projectId}/model`, { method: 'DELETE' })
      if (!response.ok) throw new Error('The project model selection could not be cleared.')
      await reload()
      setNotice('Project model selection cleared.')
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'The project model selection could not be cleared.')
    } finally {
      setBusy(false)
    }
  }

  const current = snapshot?.selection
  const currentOption = current && snapshot?.options.find((option) => valueFor(option) === valueFor(current))

  return (
    <section className="project-model-manager" aria-labelledby="project-model-title">
      <div className="credential-manager-heading">
        <div><span className="section-kicker">PROJECT CONFIGURATION</span><h3 id="project-model-title">AI model for this project</h3></div>
        <button type="button" className="dialog-close" aria-label="Back to project details" onClick={onClose}>×</button>
      </div>
      <p className="credential-help">Choose an available model specifically for this project. Configure provider access under Ollama or AI providers first.</p>
      {error && <p className="auth-error" role="alert">{error}</p>}
      {notice && <p className="credential-notice" role="status">{notice}</p>}
      {loading ? <p role="status">Loading available models…</p> : <>
        {current && <p className="credential-help">Current: {currentOption ? `${currentOption.provider_name} · ${currentOption.model_name}` : `${current.provider_type} · ${current.model_id}`} (saved {new Date(current.updated_at).toLocaleString()})</p>}
        {snapshot?.options.length ? <>
          <label htmlFor="project-ai-model">Available provider model</label>
          <select id="project-ai-model" value={selected} onChange={(event) => setSelected(event.target.value)} disabled={busy}>
            <option value="">Choose a model</option>
            {snapshot.options.map((option) => <option key={valueFor(option)} value={valueFor(option)}>{option.provider_name} · {option.model_name}</option>)}
          </select>
          <div className="dialog-actions">
        <button className="button button-primary" type="button" onClick={() => void save()} disabled={busy || !selected}>{busy ? 'Saving…' : 'Save for this project'}</button>
            {current && <button className="button button-quiet" type="button" onClick={() => void clear()} disabled={busy}>Clear selection</button>}
          </div>
        </> : <p className="empty-state">No connected provider models are available yet. Connect an OpenCode provider or validate an Ollama endpoint, then refresh this panel.</p>}
        <button className="button button-quiet" type="button" onClick={() => void reload()} disabled={busy}>Refresh available models</button>
      </>}
    </section>
  )
}
