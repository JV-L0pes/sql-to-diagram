import { render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { HomePage } from './HomePage'

describe('HomePage', () => {
  beforeEach(() => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ status: 'ok', db: 'ok' }),
      }),
    )
  })

  it('renders the foundation heading', () => {
    render(<HomePage />)
    expect(screen.getByRole('heading', { name: /schemio — foundation/i })).toBeInTheDocument()
  })

  it('fetches and displays the API health status', async () => {
    render(<HomePage />)
    await waitFor(() => {
      expect(screen.getByText(/api: ok/i)).toBeInTheDocument()
    })
  })
})
