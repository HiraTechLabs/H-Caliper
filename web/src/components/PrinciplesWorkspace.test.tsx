import { fireEvent, render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { PrinciplesWorkspace } from './PrinciplesWorkspace'

const fetchMock = vi.fn()

beforeEach(() => {
  fetchMock.mockReset()
  vi.stubGlobal('fetch', fetchMock)
  fetchMock.mockResolvedValue({ ok: true, json: async () => ({
    sync: { status: 'synchronized', source_url: 'https://example.invalid/repo.git', branch: 'main', revision: '0123456789abcdef0123456789abcdef01234567', last_success_at: '2026-10-24T10:00:00Z', error_code: null, task_id: null },
    documents: [
      { path: '.caliper/principles/security.md', revision: '0123456789abcdef0123456789abcdef01234567', sha256: 'a'.repeat(64), content: '# Security\n\n**Keep secrets private.**\n\n<script>alert(1)</script>', synced_at: '2026-10-24T10:00:00Z' },
      { path: '.caliper/manifest.yaml', revision: '0123456789abcdef0123456789abcdef01234567', sha256: 'b'.repeat(64), content: 'project:\n  name: Caliper', synced_at: '2026-10-24T10:00:00Z' },
      { path: '.caliper/DECISIONS.md', revision: '0123456789abcdef0123456789abcdef01234567', sha256: 'c'.repeat(64), content: '## D-001 — PostgreSQL\n\nUse durable storage.', synced_at: '2026-10-24T10:00:00Z' },
    ],
    graph: { nodes: [{ id: 'api', label: 'API', kind: 'service', status: 'implemented' }], edges: [] }, graph_errors: [],
  }) })
})

describe('PrinciplesWorkspace', () => {
  it('renders revisioned principles safely, searches documents, and validates the graph view', async () => {
    render(<PrinciplesWorkspace projectId="project-1" onClose={() => undefined} />)

    expect(await screen.findByRole('heading', { name: 'Security' })).toBeInTheDocument()
    expect(screen.getByText('Keep secrets private.')).toBeInTheDocument()
    expect(document.querySelector('script')).toBeNull()
    expect(screen.getByText('0123456789ab')).toBeInTheDocument()
    fireEvent.change(screen.getByRole('searchbox', { name: 'Search this view' }), { target: { value: 'missing phrase' } })
    expect(screen.getByText('No matching documents in this view for the synchronized revision.')).toBeInTheDocument()
    fireEvent.change(screen.getByRole('searchbox', { name: 'Search this view' }), { target: { value: '' } })

    fireEvent.click(screen.getByRole('button', { name: 'Manifest' }))
    expect(await screen.findByText((_, element) => element?.tagName === 'P' && Boolean(element.textContent?.includes('Caliper')))).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Decisions' }))
    expect(await screen.findByRole('heading', { name: /D-001/ })).toBeInTheDocument()
    expect(screen.getByText('Decision records · 1')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Graph' }))
    expect(await screen.findByRole('img', { name: '1 components and 0 relationships' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /API service · implemented/ })).toBeInTheDocument()
  })
})

