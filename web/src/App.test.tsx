import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import App from './App'

const savedProject = {
  id: '0cf3e630-17b4-4d27-86ec-5573c55b3a44',
  name: 'Atlas',
  description: 'The platform team workspace',
  repository_url: null,
  default_branch: 'main',
  created_at: '2026-10-23T10:00:00Z',
  updated_at: '2026-10-23T10:00:00Z',
}

function response(data: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => data,
  } as Response
}

afterEach(() => {
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

describe('project workspace', () => {
  it('requires administrator sign-in before loading projects', async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(response({ configured: true, authenticated: false }))
      .mockResolvedValueOnce(response({ authenticated: true }))
      .mockResolvedValueOnce(response([]))
    vi.stubGlobal('fetch', fetchMock)
    const user = userEvent.setup()
    render(<App />)

    await user.type(await screen.findByLabelText('Administrator password'), 'example-password')
    await user.click(screen.getByRole('button', { name: 'Sign in' }))

    expect(await screen.findByText('Your next big thing starts here.')).toBeInTheDocument()
    expect(fetchMock).toHaveBeenNthCalledWith(2, '/api/auth/session', expect.objectContaining({ method: 'POST' }))
    expect(fetchMock).toHaveBeenNthCalledWith(3, '/api/projects')
  })

  it('renders the server-confirmed create result without reloading the list', async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(response({ configured: true, authenticated: true }))
      .mockResolvedValueOnce(response([]))
      .mockResolvedValueOnce(response(savedProject, 201))
    vi.stubGlobal('fetch', fetchMock)
    const user = userEvent.setup()
    render(<App />)

    await screen.findByText('Your next big thing starts here.')
    await user.type(screen.getByLabelText(/Project name/), 'Atlas')
    await user.type(screen.getByLabelText(/A little context/), 'The platform team workspace')
    await user.click(screen.getByRole('button', { name: /Create project/ }))

    expect(await screen.findByRole('status')).toHaveTextContent('Atlas is ready in your workspace.')
    expect(screen.getByRole('heading', { name: 'Atlas' })).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledTimes(3)
    expect(fetchMock).toHaveBeenLastCalledWith('/api/projects', expect.objectContaining({ method: 'POST' }))
  })

  it('does not claim success or add a project when the server rejects the create', async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(response({ configured: true, authenticated: true }))
      .mockResolvedValueOnce(response([]))
      .mockResolvedValueOnce(response({ detail: 'Database unavailable' }, 503))
    vi.stubGlobal('fetch', fetchMock)
    const user = userEvent.setup()
    render(<App />)

    await screen.findByText('Your next big thing starts here.')
    await user.type(screen.getByLabelText(/Project name/), 'Atlas')
    await user.click(screen.getByRole('button', { name: /Create project/ }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Database unavailable')
    expect(screen.queryByRole('heading', { name: 'Atlas' })).not.toBeInTheDocument()
    expect(screen.queryByText('Atlas is ready in your workspace.')).not.toBeInTheDocument()
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3))
  })

  it('loads details and updates the card only after a fresh server read', async () => {
    const updatedProject = { ...savedProject, name: 'Atlas Core', description: 'Updated workspace' }
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(response({ configured: true, authenticated: true }))
      .mockResolvedValueOnce(response([savedProject]))
      .mockResolvedValueOnce(response(savedProject))
      .mockResolvedValueOnce(response(updatedProject))
      .mockResolvedValueOnce(response(updatedProject))
    vi.stubGlobal('fetch', fetchMock)
    const user = userEvent.setup()
    render(<App />)

    await user.click(await screen.findByRole('button', { name: /View project details/ }))
    expect(await screen.findByRole('dialog', { name: 'Atlas' })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: /Edit project/ }))
    const editDialog = screen.getByRole('dialog')
    await user.clear(within(editDialog).getByLabelText(/Project name/))
    await user.type(within(editDialog).getByLabelText(/Project name/), 'Atlas Core')
    await user.clear(within(editDialog).getByLabelText(/Description/))
    await user.type(within(editDialog).getByLabelText(/Description/), 'Updated workspace')
    await user.click(screen.getByRole('button', { name: 'Save changes' }))

    expect(await screen.findByRole('heading', { name: 'Atlas Core', level: 3 })).toBeInTheDocument()
    expect(screen.getByRole('status')).toHaveTextContent('Atlas Core was updated.')
    expect(fetchMock).toHaveBeenNthCalledWith(4, `/api/projects/${savedProject.id}`, expect.objectContaining({ method: 'PUT' }))
    expect(fetchMock).toHaveBeenNthCalledWith(5, `/api/projects/${savedProject.id}`)
  })

  it('deletes a project only after the server confirms deletion and a fresh list omits it', async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(response({ configured: true, authenticated: true }))
      .mockResolvedValueOnce(response([savedProject]))
      .mockResolvedValueOnce(response(savedProject))
      .mockResolvedValueOnce(response(null, 204))
      .mockResolvedValueOnce(response([]))
    vi.stubGlobal('fetch', fetchMock)
    const user = userEvent.setup()
    render(<App />)

    await user.click(await screen.findByRole('button', { name: /View project details/ }))
    await screen.findByRole('dialog', { name: 'Atlas' })
    await user.click(screen.getByRole('button', { name: /Delete project/ }))
    expect(screen.getByRole('alertdialog', { name: 'Delete project?' })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Delete permanently' }))

    expect(await screen.findByText('Your next big thing starts here.')).toBeInTheDocument()
    expect(screen.getByRole('status')).toHaveTextContent('Atlas was deleted.')
    expect(fetchMock).toHaveBeenNthCalledWith(4, `/api/projects/${savedProject.id}`, { method: 'DELETE' })
    expect(fetchMock).toHaveBeenNthCalledWith(5, '/api/projects')
  })

  it('manages credential metadata while never rendering the submitted token', async () => {
    const credential = {
      id: '35d2a8ef-47f7-4a6a-9aa5-22eab2362990',
      project_id: savedProject.id,
      name: 'Read-only Git token',
      kind: 'https_token',
      username: 'x-access-token',
      enabled: true,
      status: 'configured',
      deletion_pending: false,
      cleanup_pending: false,
      created_at: '2026-10-23T10:00:00Z',
      updated_at: '2026-10-23T10:00:00Z',
      last_checked_at: null,
    }
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(response({ configured: true, authenticated: true }))
      .mockResolvedValueOnce(response([savedProject]))
      .mockResolvedValueOnce(response(savedProject))
      .mockResolvedValueOnce(response([]))
      .mockResolvedValueOnce(response(credential, 201))
      .mockResolvedValueOnce(response([credential]))
    vi.stubGlobal('fetch', fetchMock)
    const user = userEvent.setup()
    render(<App />)

    await user.click(await screen.findByRole('button', { name: /View project details/ }))
    await screen.findByRole('dialog', { name: 'Atlas' })
    await user.click(screen.getByRole('button', { name: 'Manage credentials' }))
    await screen.findByText('No credentials are configured.')
    await user.type(screen.getByLabelText('Name'), 'Read-only Git token')
    await user.type(screen.getByLabelText('Token'), 'test-secret-value')
    await user.click(screen.getByRole('button', { name: 'Save token' }))

    expect(await screen.findByText('Credential saved securely.')).toBeInTheDocument()
    expect(screen.getByText('Read-only Git token')).toBeInTheDocument()
    expect(screen.queryByDisplayValue('test-secret-value')).not.toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledWith(`/api/projects/${savedProject.id}/credentials`, expect.objectContaining({ method: 'POST' }))
  })

  it('checks remote access and records a fresh reachable status', async () => {
    const credential = {
      id: '35d2a8ef-47f7-4a6a-9aa5-22eab2362990',
      project_id: savedProject.id,
      name: 'Read-only Git token',
      kind: 'https_token',
      username: 'x-access-token',
      enabled: true,
      status: 'reachable',
      deletion_pending: false,
      cleanup_pending: false,
    }
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(response({ configured: true, authenticated: true }))
      .mockResolvedValueOnce(response([savedProject]))
      .mockResolvedValueOnce(response(savedProject))
      .mockResolvedValueOnce(response([credential]))
      .mockResolvedValueOnce(response(credential))
      .mockResolvedValueOnce(response([credential]))
    vi.stubGlobal('fetch', fetchMock)
    const user = userEvent.setup()
    render(<App />)

    await user.click(await screen.findByRole('button', { name: /View project details/ }))
    await user.click(await screen.findByRole('button', { name: 'Manage credentials' }))
    await user.click(await screen.findByRole('button', { name: 'Check access' }))

    expect(await screen.findByText('The remote is reachable. Public repositories may not confirm token identity.')).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledWith(`/api/projects/${savedProject.id}/credentials/${credential.id}/validate`, { method: 'POST' })
  })

  it('keeps the project visible when the delete request fails', async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(response({ configured: true, authenticated: true }))
      .mockResolvedValueOnce(response([savedProject]))
      .mockResolvedValueOnce(response(savedProject))
      .mockResolvedValueOnce(response({ detail: 'Database unavailable' }, 503))
    vi.stubGlobal('fetch', fetchMock)
    const user = userEvent.setup()
    render(<App />)

    await user.click(await screen.findByRole('button', { name: /View project details/ }))
    await screen.findByRole('dialog', { name: 'Atlas' })
    await user.click(screen.getByRole('button', { name: /Delete project/ }))
    await user.click(screen.getByRole('button', { name: 'Delete permanently' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Database unavailable')
    expect(screen.getByRole('heading', { name: 'Atlas' })).toBeInTheDocument()
    expect(screen.queryByText('Your next big thing starts here.')).not.toBeInTheDocument()
  })
})
