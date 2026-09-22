import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { HomePage } from './HomePage'

describe('HomePage', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('renders the foundation heading', () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({ ok: true, json: async () => ({ status: 'ok', db: 'ok' }) }),
    )
    render(<HomePage />)
    expect(screen.getByRole('heading', { name: /schemio — foundation/i })).toBeInTheDocument()
  })

  it('fetches and displays the API health status', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({ ok: true, json: async () => ({ status: 'ok', db: 'ok' }) }),
    )
    render(<HomePage />)
    await waitFor(() => {
      expect(screen.getByText(/api: ok/i)).toBeInTheDocument()
    })
  })

  it('shows the unreachable state and retries on demand', async () => {
    const fetchMock = vi
      .fn()
      .mockRejectedValueOnce(new Error('network down'))
      .mockResolvedValueOnce({ ok: true, json: async () => ({ status: 'ok', db: 'ok' }) })
    vi.stubGlobal('fetch', fetchMock)

    render(<HomePage />)
    const retry = await screen.findByRole('button', { name: /retry/i })
    fireEvent.click(retry)

    await waitFor(() => {
      expect(screen.getByText(/api: ok/i)).toBeInTheDocument()
    })
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })
})
