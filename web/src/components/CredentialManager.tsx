import { useCallback, useEffect, useState, type FormEvent } from 'react'

type Credential = {
  id: string
  name: string
  kind: 'https_token'
  username: string
  enabled: boolean
  status: string
  deletion_pending: boolean
  cleanup_pending: boolean
}

type Props = { projectId: string; onClose: () => void }

export function CredentialManager({ projectId, onClose }: Props) {
  const [credentials, setCredentials] = useState<Credential[]>([])
  const [name, setName] = useState('')
  const [secret, setSecret] = useState('')
  const [username, setUsername] = useState('x-access-token')
  const [editingId, setEditingId] = useState<string | null>(null)
  const [deleteId, setDeleteId] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const baseUrl = `/api/projects/${projectId}/credentials`

  const reload = useCallback(async () => {
    setLoading(true)
    try {
      const response = await fetch(baseUrl)
      if (!response.ok) throw new Error('Could not load credential settings.')
      setCredentials(await response.json() as Credential[])
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Could not load credential settings.')
    } finally {
      setLoading(false)
    }
  }, [baseUrl])

  useEffect(() => { void reload() }, [reload])

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setBusy(true)
    setError('')
    setNotice('')
    const replacing = editingId !== null
    try {
      const response = await fetch(replacing ? `${baseUrl}/${editingId}` : baseUrl, {
        method: replacing ? 'PUT' : 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: name.trim(), kind: 'https_token', username: username.trim(), secret }),
      })
      if (!response.ok) throw new Error(response.status === 409 ? 'That credential name is already used or cleanup is pending.' : 'The credential was not saved.')
      setName('')
      setUsername('x-access-token')
      setSecret('')
      setEditingId(null)
      setNotice(replacing ? 'Credential replaced.' : 'Credential saved securely.')
      await reload()
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'The credential was not saved.')
    } finally {
      setBusy(false)
    }
  }

  async function setEnabled(credential: Credential) {
    setBusy(true)
    setError('')
    try {
      const response = await fetch(`${baseUrl}/${credential.id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled: !credential.enabled }),
      })
      if (!response.ok) throw new Error('Credential status was not changed.')
      setNotice(credential.enabled ? 'Credential disabled.' : 'Credential enabled.')
      await reload()
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Credential status was not changed.')
    } finally {
      setBusy(false)
    }
  }

  async function validate(credential: Credential) {
    setBusy(true)
    setError('')
    try {
      const response = await fetch(`${baseUrl}/${credential.id}/validate`, { method: 'POST' })
      if (!response.ok) throw new Error('Remote access check failed. Check the repository URL and token.')
      const result = await response.json() as Credential
      if (result.status === 'reachable') {
        setNotice('The remote is reachable. Public repositories may not confirm token identity.')
      } else {
        setError('The remote could not be reached with this configuration. Review the token and repository URL.')
      }
      await reload()
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Remote access check failed.')
      await reload()
    } finally {
      setBusy(false)
    }
  }

  async function remove(id: string) {
    setBusy(true)
    setError('')
    try {
      const response = await fetch(`${baseUrl}/${id}`, { method: 'DELETE' })
      if (!response.ok) throw new Error('Credential removal is pending. Retry after the server is available.')
      setDeleteId(null)
      setNotice('Credential and its encrypted secret were removed.')
      await reload()
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Credential was not removed.')
      await reload()
    } finally {
      setBusy(false)
    }
  }

  function beginReplace(credential: Credential) {
    setEditingId(credential.id)
    setName(credential.name)
    setUsername(credential.username)
    setSecret('')
    setError('')
    setNotice('')
  }

  function cancelEdit() {
    setEditingId(null)
    setName('')
    setUsername('x-access-token')
    setSecret('')
  }

  return (
    <section className="credential-manager" aria-labelledby="credential-manager-title">
      <div className="credential-manager-heading">
        <div><span className="section-kicker">PROJECT ACCESS</span><h3 id="credential-manager-title">Credentials</h3></div>
        <button type="button" className="dialog-close" aria-label="Close credential settings" onClick={onClose}>×</button>
      </div>
      <p className="credential-help">HTTPS access tokens are encrypted on the server. The secret is never shown again after saving.</p>
      {error && <p className="auth-error" role="alert">{error}</p>}
      {notice && <p className="credential-notice" role="status">{notice}</p>}
      {loading ? <p role="status">Loading credentials…</p> : credentials.length === 0 ? <p>No credentials are configured.</p> : (
        <ul className="credential-list">
          {credentials.map((credential) => (
            <li key={credential.id}>
              <div><strong>{credential.name}</strong><span>{credential.kind === 'https_token' ? 'HTTPS token' : credential.kind} · {credential.status}{credential.cleanup_pending ? ' · cleanup pending' : ''}</span></div>
              {deleteId === credential.id ? (
                <div className="credential-actions"><span>Destroy this secret?</span><button type="button" disabled={busy} onClick={() => void remove(credential.id)}>Confirm</button><button type="button" disabled={busy} onClick={() => setDeleteId(null)}>Cancel</button></div>
              ) : (
                <div className="credential-actions">
                  <button type="button" disabled={busy || credential.deletion_pending} onClick={() => void setEnabled(credential)}>{credential.enabled ? 'Disable' : 'Enable'}</button>
                  <button type="button" disabled={busy || !credential.enabled || credential.deletion_pending} onClick={() => void validate(credential)}>Check access</button>
                  <button type="button" disabled={busy || credential.deletion_pending || credential.cleanup_pending} onClick={() => beginReplace(credential)}>Replace</button>
                  <button type="button" disabled={busy} onClick={() => setDeleteId(credential.id)}>Delete</button>
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
      <form className="credential-form" onSubmit={(event) => void save(event)}>
        <h4>{editingId ? 'Replace token' : 'Add an HTTPS token'}</h4>
        <label htmlFor="credential-name">Name</label>
        <input id="credential-name" value={name} onChange={(event) => setName(event.target.value)} maxLength={120} required />
        <label htmlFor="credential-username">Git username</label>
        <input id="credential-username" value={username} onChange={(event) => setUsername(event.target.value)} maxLength={255} required />
        <label htmlFor="credential-secret">Token</label>
        <input id="credential-secret" type="password" autoComplete="new-password" value={secret} onChange={(event) => setSecret(event.target.value)} maxLength={16384} required />
        <div className="credential-actions">
          {editingId && <button type="button" disabled={busy} onClick={cancelEdit}>Cancel</button>}
          <button className="button button-primary" type="submit" disabled={busy || !name.trim() || !secret}>{busy ? 'Saving…' : editingId ? 'Replace token' : 'Save token'}</button>
        </div>
      </form>
    </section>
  )
}
