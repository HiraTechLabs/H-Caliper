import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { RepositorySyncManager } from './RepositorySyncManager'

function response(data: unknown, status = 200): Response {
  return { ok: status >= 200 && status < 300, status, json: async () => data } as Response
}

afterEach(() => vi.unstubAllGlobals())

describe('RepositorySyncManager', () => {
  it('renders fresh files after a confirmed synchronization', async () => {
    const state = { status: 'configured', source_url: 'https://example.test/repo.git', branch: 'main', revision: null, attempted_at: '2026-10-24T10:00:00Z', last_success_at: null, error_code: null, document_count: 0 }
    const synchronized = { ...state, status: 'synchronized', revision: 'abc123def456', last_success_at: '2026-10-24T10:01:00Z', document_count: 1 }
    const document = { path: 'docs/guide.md', revision: 'abc123def456', sha256: 'hash', content: '<script>not HTML</script>', synced_at: '2026-10-24T10:01:00Z' }
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(response(state)).mockResolvedValueOnce(response([])).mockResolvedValueOnce(response([]))
      .mockResolvedValueOnce(response(synchronized))
      .mockResolvedValueOnce(response(synchronized)).mockResolvedValueOnce(response([document])).mockResolvedValueOnce(response([]))
    vi.stubGlobal('fetch', fetchMock)
    const user = userEvent.setup()
    render(<RepositorySyncManager projectId="project-1" onClose={() => undefined} />)

    await user.click(await screen.findByRole('button', { name: 'Synchronize now' }))

    expect(await screen.findByRole('status')).toHaveTextContent('Synchronized 1 knowledge files from main.')
    expect(await screen.findByText('docs/guide.md')).toBeInTheDocument()
    expect(screen.getByText('<script>not HTML</script>')).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'not HTML' })).not.toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledWith('/api/projects/project-1/sync', expect.objectContaining({ method: 'POST' }))
  })
})
