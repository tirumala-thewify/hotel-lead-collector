export function numericCoordinate(value) {
  if (value === null || value === undefined || value === '') return null
  const number = Number(value)
  return Number.isFinite(number) ? number : null
}

export function businessCoordinates(business) {
  if (!business || typeof business !== 'object') return null
  const latitude = numericCoordinate(business.latitude)
  const longitude = numericCoordinate(business.longitude)
  if (
    latitude === null || longitude === null
    || latitude < -90 || latitude > 90
    || longitude < -180 || longitude > 180
  ) return null
  return [latitude, longitude]
}

export function mappableBusinesses(businesses, limit = 100) {
  return businesses.flatMap((business) => {
    const coordinates = businessCoordinates(business)
    return coordinates ? [{ business, coordinates }] : []
  }).slice(0, limit)
}
