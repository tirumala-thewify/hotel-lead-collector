const NEARBY_HOTELS_URL = 'http://127.0.0.1:8000/api/hotels/nearby/'
const BUSINESS_CATEGORIES_URL = 'http://127.0.0.1:8000/api/hotels/categories/'
const ENRICH_HOTEL_URL = 'http://127.0.0.1:8000/api/hotels/enrich/'
const BULK_ENRICH_HOTELS_URL = 'http://127.0.0.1:8000/api/hotels/enrich/bulk/'
const ENRICH_MANAGERS_URL = 'http://127.0.0.1:8000/api/hotels/enrich-managers/'
const BULK_ENRICH_MANAGERS_URL = 'http://127.0.0.1:8000/api/hotels/enrich-managers/bulk/'

export class HotelServiceError extends Error {
  constructor(message, status = null) {
    super(message)
    this.name = 'HotelServiceError'
    this.status = status
  }
}

export async function fetchNearbyHotels(lat, lng, radius, category = 'hotels_resorts', providers = []) {
  const url = new URL(NEARBY_HOTELS_URL)
  const query = new URLSearchParams({ lat, lng, radius, category })
  providers.forEach((provider) => query.append('providers', provider))
  url.search = query.toString()

  let response
  try {
    response = await fetch(url)
  } catch {
    throw new HotelServiceError(
      'Cannot connect to the hotel API. Make sure the Django server is running.',
    )
  }

  let data
  try {
    data = JSON.parse(await response.text())
  } catch {
    throw new HotelServiceError('The hotel API returned an invalid response.', response.status)
  }

  if (!response.ok) {
    if (response.status === 400) {
      throw new HotelServiceError(
        data?.error || 'Please check the search values and try again.',
        400,
      )
    }
    throw new HotelServiceError(
      data?.error || 'The hotel API could not complete the request.',
      response.status,
    )
  }

  if (!data || !Array.isArray(data.hotels) || typeof data.count !== 'number') {
    throw new HotelServiceError('The hotel API returned an invalid response.', response.status)
  }

  return data
}

export async function fetchBusinessCategories() {
  let response
  try {
    response = await fetch(BUSINESS_CATEGORIES_URL)
  } catch {
    throw new HotelServiceError('Business types could not be loaded.')
  }
  let data
  try {
    data = JSON.parse(await response.text())
  } catch {
    throw new HotelServiceError('The business types API returned an invalid response.', response.status)
  }
  if (!response.ok || !Array.isArray(data?.categories)) {
    throw new HotelServiceError(data?.error || 'Business types could not be loaded.', response.status)
  }
  return data.categories
}

export async function enrichHotel(hotel) {
  let response
  try {
    response = await fetch(ENRICH_HOTEL_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name: hotel.name,
        website: hotel.website,
        address: hotel.address,
        latitude: hotel.latitude,
        longitude: hotel.longitude,
        brand: hotel.brand,
      }),
    })
  } catch {
    throw new HotelServiceError(
      'Cannot connect to the enrichment API. Make sure Django is running.',
    )
  }

  let data
  try {
    data = JSON.parse(await response.text())
  } catch {
    throw new HotelServiceError('The enrichment API returned an invalid response.', response.status)
  }
  if (!response.ok) {
    throw new HotelServiceError(
      data?.message || 'Unable to enrich this hotel at this time.',
      response.status,
    )
  }
  return data
}

export async function freeEnrichHotelsBulk(hotels) {
  let response
  try {
    response = await fetch(BULK_ENRICH_HOTELS_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ hotels }),
    })
  } catch {
    throw new HotelServiceError('Cannot connect to the free enrichment API.')
  }
  let data
  try {
    data = JSON.parse(await response.text())
  } catch {
    throw new HotelServiceError('The free enrichment API returned an invalid response.', response.status)
  }
  if (!response.ok || !Array.isArray(data?.results)) {
    throw new HotelServiceError(data?.message || 'Unable to free enrich these hotels.', response.status)
  }
  return data
}

export async function findDecisionMakers(business) {
  let response
  try {
    response = await fetch(ENRICH_MANAGERS_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name: business.name,
        website: business.website,
        brand: business.brand,
        address: business.address,
        category: business.category || 'hotels_resorts',
      }),
    })
  } catch {
    throw new HotelServiceError('Cannot connect to the decision-maker enrichment API.')
  }

  let data
  try {
    data = JSON.parse(await response.text())
  } catch {
    throw new HotelServiceError('The decision-maker API returned an invalid response.', response.status)
  }
  if (!response.ok) {
    throw new HotelServiceError(
      data?.message || 'Unable to search for decision-makers at this time.',
      response.status,
    )
  }
  return data
}

export async function findDecisionMakersBulk(businesses) {
  let response
  try {
    response = await fetch(BULK_ENRICH_MANAGERS_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        hotels: businesses.map((business) => ({
          name: business.name,
          website: business.website,
          brand: business.brand,
          address: business.address,
          category: business.category || 'hotels_resorts',
        })),
      }),
    })
  } catch {
    throw new HotelServiceError('Cannot connect to the bulk decision-maker API.')
  }

  let data
  try {
    data = JSON.parse(await response.text())
  } catch {
    throw new HotelServiceError('The bulk decision-maker API returned an invalid response.', response.status)
  }
  if (!response.ok || !Array.isArray(data?.results)) {
    throw new HotelServiceError(
      data?.message || 'Unable to search for decision-makers at this time.',
      response.status,
    )
  }
  return data
}

// Backward-compatible aliases for existing imports and integrations.
export const findHotelManagers = findDecisionMakers
export const findManagersBulk = findDecisionMakersBulk
