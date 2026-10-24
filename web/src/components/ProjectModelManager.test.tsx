import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ProjectModelManager } from './ProjectModelManager'

const option = {
  provider_type: 'opencode',
  provider_id: 'openai',
  provider_name: 'OpenAI',
  model_id: 'openai/gpt-test',
  model_name: 'GPT Test',
}

function response(data: unknown, status = 200): Response {
  return { ok: status >= 200 && status < 300, status, json: async () => data } as Response
}

afterEach(() => vi.unstubAllGlobals())

describe('project model assignment', () => {
  it('saves and displays the server-confirmed project model without a reload', async () => {
    const selected = { ...option, updated_at: '2026-10-24T12:00:00Z' }
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(response({ selection: null, options: [option] }))
      .mockResolvedValueOnce(response({ selection: selected, options: [option] }))
    vi.stubGlobal('fetch', fetchMock)
    const user = userEvent.setup()
    render(<ProjectModelManager projectId="project-1" onClose={() => undefined} />)

    await user.selectOptions(await screen.findByLabelText('Available provider model'), JSON.stringify([
      option.provider_type, option.provider_id, option.model_id,
    ]))
    await user.click(screen.getByRole('button', { name: 'Save for this project' }))

    expect(await screen.findByRole('status')).toHaveTextContent('Model selection saved for this project.')
    expect(screen.getByText(/Current: OpenAI · GPT Test/)).toBeInTheDocument()
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2))
    expect(fetchMock).toHaveBeenLastCalledWith('/api/projects/project-1/model', expect.objectContaining({ method: 'PUT' }))
  })
})
