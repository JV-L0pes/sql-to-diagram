import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { Placeholder } from './Placeholder'

describe('Placeholder', () => {
  it('renders the given label', () => {
    render(<Placeholder label="hello from packages/ui" />)
    expect(screen.getByText('hello from packages/ui')).toBeInTheDocument()
  })
})
