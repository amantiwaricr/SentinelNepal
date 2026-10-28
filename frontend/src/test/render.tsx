import { render } from '@testing-library/react'
import { MemoryRouter } from 'react-router'

import { App } from '../App'

/** Render the full app at a given URL. */
export function renderAppAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <App />
    </MemoryRouter>,
  )
}
