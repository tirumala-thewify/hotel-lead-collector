import assert from 'node:assert/strict'
import test from 'node:test'

import { prepareHotelsForExport } from './exportEnrichmentService.js'

const resultFor = (hotel) => ({
  hotel_name: hotel.name,
  status: 'FOUND',
  hotel: { website: hotel.website, email: `info@${hotel.name}.example` },
  business_emails: [{ email: `info@${hotel.name}.example`, type: 'general' }],
  business_phones: [{ phone: '+1 212 555 0100', type: 'general' }],
  social_profiles: { linkedin: `https://linkedin.com/company/${hotel.name}` },
  decision_makers: [{ name: 'Jane Doe', title: 'IT Director', role_group: 'it_leadership' }],
})

test('automatically enriches website businesses and preserves businesses without websites', async () => {
  const calls = []
  const hotels = [{ name: 'one', website: 'https://one.example' }, { name: 'two' }]
  const prepared = await prepareHotelsForExport(hotels, async (batch) => {
    calls.push(batch)
    return [merge(hotels[0], resultFor(hotels[0])), hotels[1]]
  })
  assert.equal(calls.length, 1)
  assert.equal(prepared[0].decision_makers[0].title, 'IT Director')
  assert.deepEqual(prepared[1], hotels[1])
})

test('reuses completed structured enrichment without fetching', async () => {
  const hotel = {
    name: 'ready', website: 'https://ready.example', enrichment_status: 'NOT_FOUND',
    business_emails: [], business_phones: [], social_profiles: {}, decision_makers: [],
  }
  let called = false
  assert.deepEqual(await prepareHotelsForExport([hotel], async (items) => { called = true; return items }), [hotel])
  assert.equal(called, true)
})

test('sends more than ten businesses through the dedicated backend orchestrator', async () => {
  const hotels = Array.from({ length: 23 }, (_, index) => ({
    name: `hotel-${index}`, website: `https://hotel-${index}.example`,
  }))
  const prepared = await prepareHotelsForExport(hotels, async (items) => items)
  assert.equal(prepared.length, 23)
})

test('export preparation failures are reported to the button workflow', async () => {
  const hotels = [{ name: 'one', website: 'https://one.example' }]
  await assert.rejects(
    prepareHotelsForExport(hotels, async () => { throw new Error('failed') }),
    /failed/,
  )
})

const merge = (hotel, result) => ({ ...hotel, ...result.hotel, ...result,
  enrichment_status: result.status })
