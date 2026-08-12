import assert from 'node:assert/strict'
import test from 'node:test'

import { buildHotelsCsv } from './exportService.js'

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
