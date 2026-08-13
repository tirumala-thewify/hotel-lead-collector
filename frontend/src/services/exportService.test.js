import assert from 'node:assert/strict'
import test from 'node:test'

import {
  buildHotelsCsv,
  exportHotelsCsv,
  exportHotelsExcel,
} from './exportService.js'

const context = { location: 'Delhi', latitude: 1, longitude: 2, radius: 3, provider: 'Browser Search' }

test('CSV includes structured contacts, social profiles, people, and source URLs', () => {
  const csv = buildHotelsCsv([{
    name: 'Hotel, "One"',
    business_emails: [
      { email: 'sales@hotel.example', type: 'sales', source_url: 'https://hotel.example/contact' },
      { email: 'info@hotel.example', type: 'general', source_url: 'https://hotel.example/' },
    ],
    business_phones: [{ phone: '+1 212 555 0100', type: 'general', source_url: 'https://hotel.example/contact' }],
    social_profiles: { linkedin: 'https://linkedin.com/company/hotel' },
    social_profile_sources: { linkedin: 'https://hotel.example/' },
    decision_makers: [{ name: 'Jane Doe', title: 'IT Director', source_url: 'https://hotel.example/team' }],
  }], context)
  assert.match(csv, /sales@hotel\.example \[sales\]; info@hotel\.example \[general\]/)
  assert.match(csv, /\+1 212 555 0100 \[general\]/)
  assert.match(csv, /linkedin\.com\/company\/hotel/)
  assert.match(csv, /Jane Doe — IT Director/)
  assert.match(csv, /"Hotel, ""One"""/)
})

test('CSV distinguishes confirmed public WhatsApp evidence from unknown phones', () => {
  const csv = buildHotelsCsv([{
    name: 'Confirmed', phone: '+1 111 111 1111',
    whatsapp_contacts: [{
      number: '+1 222 222 2222', normalized: '+12222222222',
      status: 'CONFIRMED_PUBLIC', evidence_type: 'wa.me',
      source_url: 'https://hotel.example/contact',
    }],
  }, { name: 'Phone only', phone: '+1 333 333 3333' }], context)
  assert.match(csv, /"WhatsApp Numbers"/)
  assert.match(csv, /"WhatsApp Status"/)
  assert.match(csv, /"'\+12222222222","CONFIRMED_PUBLIC","https:\/\/hotel\.example\/contact"/)
  assert.match(csv, /"Phone only".*"UNKNOWN"/)
})

test('real CSV and Excel export signatures execute without module-scope arguments', async () => {
  const originalDocument = globalThis.document
  const originalFetch = globalThis.fetch
  const originalCreateObjectURL = globalThis.URL.createObjectURL
  const originalRevokeObjectURL = globalThis.URL.revokeObjectURL
  const clicks = []
  globalThis.document = {
    body: { appendChild() {} },
    createElement: () => ({
      click() { clicks.push(this.download) },
      remove() {},
    }),
  }
  globalThis.URL.createObjectURL = () => 'blob:test'
  globalThis.URL.revokeObjectURL = () => {}
  globalThis.fetch = async (_url, options) => {
    const payload = JSON.parse(options.body)
    assert.equal(payload.hotels[0].name, 'Invocation Hotel')
    assert.equal(payload.context.location, 'Delhi')
    return { ok: true, blob: async () => new Blob(['excel']) }
  }
  try {
    const hotels = [{ name: 'Invocation Hotel', decision_makers: [] }]
    assert.doesNotThrow(() => exportHotelsCsv(hotels, context))
    await assert.doesNotReject(exportHotelsExcel(hotels, context))
    assert.equal(clicks.length, 2)
    assert.match(clicks[0], /\.csv$/)
    assert.match(clicks[1], /\.xlsx$/)
  } finally {
    globalThis.document = originalDocument
    globalThis.fetch = originalFetch
    globalThis.URL.createObjectURL = originalCreateObjectURL
    globalThis.URL.revokeObjectURL = originalRevokeObjectURL
  }
})
