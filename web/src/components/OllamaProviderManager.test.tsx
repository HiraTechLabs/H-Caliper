import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { OllamaProviderManager } from './OllamaProviderManager'

const fetchMock = vi.fn()
const configured = { endpoint_url: 'http://ollama:11434', selected_model_id: null, status: 'configured', checked_at: null, error_code: null, models: [] }
const reachable = { ...configured, status: 'reachable', checked_at: '2026-10-24T10:00:00Z', models: ['qwen:latest', 'llama:8b'] }

beforeEach(() => {
  fetchMock.mockReset()
  vi.stubGlobal('fetch', fetchMock)
  fetchMock.mockResolvedValueOnce({ ok: true, json: async () => configured })
})

describe('OllamaProviderManager', () => {
  it('saves an endpoint, confirms discovery, and persists a selected discovered model', async () => {
    render(<OllamaProviderManager onClose={() => undefined} />)
    const endpoint = await screen.findByLabelText('Ollama endpoint URL')
    await waitFor(() => expect(screen.getByRole('button', { name: 'Save endpoint' })).toBeEnabled())
    fireEvent.change(endpoint, { target: { value: 'http://ollama:11434' } })

    fetchMock.mockResolvedValueOnce({ ok: true, json: async () => configured })
    fireEvent.click(screen.getByRole('button', { name: 'Save endpoint' }))
    expect(await screen.findByRole('status')).toHaveTextContent('Endpoint saved.')

    fetchMock.mockResolvedValueOnce({ ok: true, json: async () => reachable })
    fireEvent.click(screen.getByRole('button', { name: 'Validate and discover' }))
    expect(await screen.findByRole('status')).toHaveTextContent('Found 2 models.')

    fetchMock.mockResolvedValueOnce({ ok: true, json: async () => ({ ...reachable, selected_model_id: 'qwen:latest' }) })
    fireEvent.change(screen.getByLabelText('Available model'), { target: { value: 'qwen:latest' } })
    await waitFor(() => expect(fetchMock).toHaveBeenLastCalledWith('/api/providers/ollama/model', expect.objectContaining({ method: 'PUT' })))
    expect(await screen.findByRole('status')).toHaveTextContent('Selected model saved to Caliper.')
  })
})
