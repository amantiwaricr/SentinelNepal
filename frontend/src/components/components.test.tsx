import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { ConfirmDialog } from './ConfirmDialog'
import { CountList } from './CountList'
import { DataTable } from './DataTable'
import { Pagination } from './Pagination'

describe('DataTable', () => {
  const columns = [
    { key: 'name', header: 'Name', render: (r: { id: number; name: string }) => r.name },
    { key: 'id', header: 'ID', render: (r: { id: number; name: string }) => r.id },
  ]

  it('renders a captioned table with one row per item', () => {
    render(
      <DataTable
        caption="Synthetic rows"
        columns={columns}
        rows={[
          { id: 1, name: 'alpha' },
          { id: 2, name: 'beta' },
        ]}
        rowKey={(r) => r.id}
      />,
    )
    const table = screen.getByRole('table', { name: 'Synthetic rows' })
    expect(table).toBeInTheDocument()
    expect(screen.getAllByRole('row')).toHaveLength(3)
    expect(screen.getByRole('columnheader', { name: 'Name' })).toBeInTheDocument()
    expect(screen.getByRole('cell', { name: 'beta' })).toBeInTheDocument()
  })

  it('shows the empty state instead of an empty table', () => {
    render(
      <DataTable
        caption="Nothing"
        columns={columns}
        rows={[]}
        rowKey={(r) => r.id}
        empty={<p>No synthetic rows</p>}
      />,
    )
    expect(screen.queryByRole('table')).not.toBeInTheDocument()
    expect(screen.getByText('No synthetic rows')).toBeInTheDocument()
  })
})

describe('Pagination', () => {
  it('describes the visible range and moves between pages', async () => {
    const user = userEvent.setup()
    const onPageChange = vi.fn()
    render(<Pagination page={2} pageSize={25} total={60} onPageChange={onPageChange} />)
    expect(screen.getByText('Showing 26–50 of 60')).toBeInTheDocument()
    expect(screen.getByText('Page 2 of 3')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Next' }))
    await user.click(screen.getByRole('button', { name: 'Previous' }))
    expect(onPageChange.mock.calls).toEqual([[3], [1]])
  })

  it('disables buttons at the ends', () => {
    render(<Pagination page={1} pageSize={25} total={10} onPageChange={() => {}} />)
    expect(screen.getByRole('button', { name: 'Previous' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Next' })).toBeDisabled()
  })
})

describe('ConfirmDialog', () => {
  it('requires the exact confirmation text before confirming', async () => {
    const user = userEvent.setup()
    const onConfirm = vi.fn()
    render(
      <ConfirmDialog
        title="Approve blocking 192.0.2.10/32?"
        confirmLabel="Approve block"
        requireText="192.0.2.10/32"
        onConfirm={onConfirm}
        onCancel={() => {}}
      />,
    )
    const dialog = screen.getByRole('dialog', { name: 'Approve blocking 192.0.2.10/32?' })
    expect(dialog).toHaveAttribute('aria-modal', 'true')
    const confirm = screen.getByRole('button', { name: 'Approve block' })
    const input = screen.getByLabelText(/Type 192.0.2.10\/32 to confirm/)
    expect(input).toHaveFocus()
    expect(confirm).toBeDisabled()

    await user.type(input, '192.0.2.11/32')
    expect(confirm).toBeDisabled()
    await user.clear(input)
    await user.type(input, '192.0.2.10/32{Enter}')
    expect(onConfirm).toHaveBeenCalledTimes(1)
  })

  it('cancels with Escape and keeps keyboard focus inside the dialog', async () => {
    const user = userEvent.setup()
    const onCancel = vi.fn()
    render(
      <ConfirmDialog title="Sure?" confirmLabel="Yes" onConfirm={() => {}} onCancel={onCancel} />,
    )
    const cancel = screen.getByRole('button', { name: 'Cancel' })
    const yes = screen.getByRole('button', { name: 'Yes' })
    expect(cancel).toHaveFocus()
    await user.tab()
    expect(yes).toHaveFocus()
    await user.tab()
    expect(cancel).toHaveFocus()
    await user.keyboard('{Escape}')
    expect(onCancel).toHaveBeenCalledTimes(1)
  })

  it('shows the API error', () => {
    render(
      <ConfirmDialog
        title="Sure?"
        confirmLabel="Yes"
        error={
          {
            message: 'A different administrator must approve this request',
            requestId: 'r1',
          } as never
        }
        onConfirm={() => {}}
        onCancel={() => {}}
      />,
    )
    expect(screen.getByRole('alert')).toHaveTextContent('A different administrator must approve')
  })
})

describe('CountList', () => {
  it('lists counts largest first, or in a fixed order', () => {
    const { rerender } = render(<CountList counts={{ a: 1, b: 5 }} />)
    expect(screen.getAllByRole('listitem').map((li) => li.textContent)).toEqual(['b5', 'a1'])
    rerender(<CountList counts={{ low: 2, high: 1 }} order={['high', 'medium', 'low']} />)
    expect(screen.getAllByRole('listitem').map((li) => li.textContent)).toEqual(['high1', 'low2'])
  })

  it('says when there is nothing to count', () => {
    render(<CountList counts={{}} empty="No incidents yet" />)
    expect(screen.getByText('No incidents yet')).toBeInTheDocument()
  })
})
