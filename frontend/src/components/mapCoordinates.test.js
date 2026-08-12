import assert from 'node:assert/strict'
import test from 'node:test'

import { businessCoordinates, mappableBusinesses } from './mapCoordinates.js'

test('accepts valid numeric and numeric-string coordinates', () => {
  assert.deepEqual(businessCoordinates({ latitude: 16.5, longitude: 80.6 }), [16.5, 80.6])
  assert.deepEqual(businessCoordinates({ latitude: '16.5', longitude: '80.6' }), [16.5, 80.6])
})

test('rejects a null latitude', () => {
  assert.equal(businessCoordinates({ latitude: null, longitude: 80.6 }), null)
})

test('rejects a null longitude', () => {
  assert.equal(businessCoordinates({ latitude: 16.5, longitude: null }), null)
})

test('rejects two null coordinates', () => {
  assert.equal(businessCoordinates({ latitude: null, longitude: null }), null)
})

test('mixed results retain only valid map entries without changing the source list', () => {
  const businesses = [
    { name: 'Mapped', latitude: 16.5, longitude: 80.6 },
    { name: 'List only', latitude: null, longitude: null },
    { name: 'Also mapped', latitude: 17, longitude: 81 },
  ]
  assert.deepEqual(
    mappableBusinesses(businesses).map(({ business }) => business.name),
    ['Mapped', 'Also mapped'],
  )
  assert.equal(businesses.length, 3)
})

test('rejects empty, non-finite, and out-of-range coordinate pairs', () => {
  assert.equal(businessCoordinates({ latitude: '', longitude: 80.6 }), null)
  assert.equal(businessCoordinates({ latitude: Infinity, longitude: 80.6 }), null)
  assert.equal(businessCoordinates({ latitude: 91, longitude: 80.6 }), null)
  assert.equal(businessCoordinates({ latitude: 16.5, longitude: 181 }), null)
})
