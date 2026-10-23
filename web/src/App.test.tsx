import { render, screen, waitFor } from '@testing-library/react'
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
  it('renders the server-confirmed create result without reloading the list', async () => {
    const fetchMock = vi.fn()
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
    expect(fetchMock).toHaveBeenCalledTimes(2)
    expect(fetchMock).toHaveBeenLastCalledWith('/api/projects', expect.objectContaining({ method: 'POST' }))
  })

  it('does not claim success or add a project when the server rejects the create', async () => {
    const fetchMock = vi.fn()
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
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2))
  })
})
