import assert from 'node:assert/strict'
import test from 'node:test'

import { businessKey, displayBusinessValue } from './businessIdentity.js'

test('uses canonical provider and place identity when available', () => {
  assert.equal(businessKey({ source: 'Browser Search', place_id: 'ChIJabc' }), 'browser search:id:ChIJabc')
})

test('uses Maps URL before name and coordinates', () => {
  assert.equal(
    businessKey({ source: 'Browser Search', maps_url: 'https://maps.test/place/one' }),
    'browser search:maps:https://maps.test/place/one',
  )
})

test('different businesses without ids do not share undefined keys', () => {
  const first = businessKey({ source: 'Browser Search', name: 'One', latitude: 1, longitude: 2 })
  const second = businessKey({ source: 'Browser Search', name: 'Two', latitude: 1, longitude: 2 })
  assert.notEqual(first, second)
  assert.equal(first.includes('undefined-undefined'), false)
})

test('available detail values are preserved for display', () => {
  assert.equal(displayBusinessValue('0866 664 4444'), '0866 664 4444')
  assert.equal(displayBusinessValue(null), 'Not Available')
})
