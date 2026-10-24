import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { OpenCodeProviderManager } from './OpenCodeProviderManager'

const initial = {
  status: 'not_configured', error_code: null, checked_at: null, version: '1.19.4',
  providers: [{ id: 'openai', name: 'OpenAI', models: [{ id: 'gpt-test', name: 'Test model' }] }],
  connected_provider_ids: [], auth_methods: { openai: [{ type: 'api', label: 'API key', prompts: [] }] },
  selected_provider_id: null, selected_model_id: null,
}

function response(data: unknown, status = 200) {
  return { ok: status >= 200 && status < 300, status, json: async () => data } as Response
}

afterEach(() => vi.unstubAllGlobals())

describe('OpenCode provider manager', () => {
  it('connects without ever rendering a submitted key and refreshes the provider state', async () => {
    const connected = { ...initial, status: 'connected', connected_provider_ids: ['openai'] }
    const fetchMock = vi.fn().mockResolvedValueOnce(response(initial)).mockResolvedValueOnce(response(connected))
    vi.stubGlobal('fetch', fetchMock)
    render(<OpenCodeProviderManager onClose={() => undefined} />)
    const user = userEvent.setup()
    const key = 'acceptance-secret-value'
    await user.type(await screen.findByLabelText('API key'), key)
    await user.click(screen.getByRole('button', { name: 'Save API key' }))
    await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('Provider credentials saved securely.'))
    expect(screen.queryByDisplayValue(key)).not.toBeInTheDocument()
    expect(fetchMock).toHaveBeenLastCalledWith('/api/providers/opencode/auth/openai/api-key', expect.objectContaining({ method: 'PUT', body: JSON.stringify({ api_key: key, metadata: {} }) }))
  })

  it('selects only a catalogued model from a connected provider', async () => {
    const connected = { ...initial, status: 'connected', connected_provider_ids: ['openai'] }
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(response(connected))
      .mockResolvedValueOnce(response({ status: 'connected', selected_provider_id: 'openai', selected_model_id: 'gpt-test' }))
      .mockResolvedValueOnce(response({ ...connected, selected_provider_id: 'openai', selected_model_id: 'gpt-test' }))
    vi.stubGlobal('fetch', fetchMock)
    render(<OpenCodeProviderManager onClose={() => undefined} />)
    fireEvent.change(await screen.findByRole('combobox', { name: 'Default model' }), { target: { value: 'openai::gpt-test' } })
    await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('Default model saved to Caliper.'))
    expect(fetchMock).toHaveBeenNthCalledWith(2, '/api/providers/opencode/model', expect.objectContaining({ body: JSON.stringify({ provider_id: 'openai', model_id: 'gpt-test' }) }))
  })
})
