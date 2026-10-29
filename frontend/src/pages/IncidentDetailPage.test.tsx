import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { ANALYST, SYNTHETIC_INCIDENT } from '../test/fixtures'
import { mockApi } from '../test/mockApi'
import { renderAppAt } from '../test/render'
import type { AuditLogOut, IncidentDetail, NoteOut } from '../types/api'

function incidentApi() {
  let incident: IncidentDetail = { ...SYNTHETIC_INCIDENT }
  const notes: NoteOut[] = []
  const history: AuditLogOut[] = [
    {
      id: 1,
      occurred_at: '2026-10-28T11:00:00Z',
      actor_type: 'user',
      actor_user_id: 2,
      actor_label: 'analyst1',
      action: 'incident.created',
      target_type: 'incident',
      target_id: '4',
      outcome: 'success',
      ip_address: null,
      request_id: null,
      details: {},
    },
  ]
  const api = mockApi({
    'GET /users/directory': [ANALYST, { ...ANALYST, id: 5, username: 'sita' }],
    'GET /incidents/4': () => incident,
    'PATCH /incidents/4': ({ body }) => {
      const changes = body as Partial<IncidentDetail>
      if (changes.status) {
        history.push({
          ...history[0]!,
          id: history.length + 1,
          action: 'incident.status_changed',
          details: { from: incident.status, to: changes.status },
        })
      }
      incident = {
        ...incident,
        ...changes,
        allowed_transitions:
          changes.status === 'under_investigation'
            ? ['confirmed', 'false_positive', 'resolved']
            : incident.allowed_transitions,
      }
      return incident
    },
    'GET /incidents/4/notes': () => notes,
    'POST /incidents/4/notes': ({ body }) => {
      const note: NoteOut = {
        id: notes.length + 1,
        incident_id: 4,
        author_id: 2,
        author_username: 'analyst1',
        body: (body as { body: string }).body,
        created_at: '2026-10-28T12:00:00Z',
      }
      notes.push(note)
      return note
    },
    'GET /incidents/4/history': () => history,
  })
  return api
}

describe('IncidentDetailPage', () => {
  it('shows linked alerts and history', async () => {
    incidentApi()
    renderAppAt('/incidents/4')
    expect(
      await screen.findByRole('heading', { level: 1, name: /Incident 4: Suspected Exploits/ }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('table', { name: 'Alerts linked to this incident' }),
    ).toBeInTheDocument()
    expect(await screen.findByText('Opened the incident')).toBeInTheDocument()
  })

  it('changes status after confirmation and records it in the history', async () => {
    const user = userEvent.setup()
    const api = incidentApi()
    renderAppAt('/incidents/4')
    await user.click(await screen.findByRole('button', { name: 'Mark under investigation' }))
    const dialog = screen.getByRole('dialog')
    await user.click(within(dialog).getByRole('button', { name: 'Change status' }))

    expect(await screen.findByText('Status New → Under investigation')).toBeInTheDocument()
    expect(api.callsTo('PATCH', '/incidents/4')[0]?.body).toEqual({ status: 'under_investigation' })
    expect(screen.getByRole('button', { name: 'Mark confirmed' })).toBeInTheDocument()
  })

  it('explains what confirming means before doing it', async () => {
    const user = userEvent.setup()
    incidentApi()
    renderAppAt('/incidents/4')
    await user.click(await screen.findByRole('button', { name: 'Mark under investigation' }))
    await user.click(
      within(screen.getByRole('dialog')).getByRole('button', { name: 'Change status' }),
    )
    await user.click(await screen.findByRole('button', { name: 'Mark confirmed' }))
    expect(screen.getByRole('dialog')).toHaveTextContent(/evidence beyond the model output/)
  })

  it('assigns the incident', async () => {
    const user = userEvent.setup()
    const api = incidentApi()
    renderAppAt('/incidents/4')
    await user.selectOptions(await screen.findByLabelText('Assigned to'), 'sita (analyst)')
    await user.click(screen.getByRole('button', { name: 'Save assignment and severity' }))
    await screen.findByText('sita', { selector: 'dd' })
    expect(api.callsTo('PATCH', '/incidents/4')[0]?.body).toEqual({ assigned_to: 5 })
  })

  it('adds a note and renders markup in it as plain text', async () => {
    const user = userEvent.setup()
    const api = incidentApi()
    renderAppAt('/incidents/4')
    const text = 'Checked <b>host</b> logs; nothing found.'
    await user.type(await screen.findByLabelText('Add a note'), text)
    await user.click(screen.getByRole('button', { name: 'Add note' }))
    expect(await screen.findByText(text)).toBeInTheDocument()
    expect(document.querySelector('b')).toBeNull()
    expect(api.callsTo('POST', '/incidents/4/notes')[0]?.body).toEqual({ body: text })
    expect(screen.getByLabelText('Add a note')).toHaveValue('')
  })
})
