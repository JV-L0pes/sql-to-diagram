import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { HomePage } from './HomePage'

describe('HomePage', () => {
  it('renders the foundation heading', () => {
    render(<HomePage />)
    expect(screen.getByRole('heading', { name: /sql to diagram — foundation/i })).toBeInTheDocument()
  })
})
