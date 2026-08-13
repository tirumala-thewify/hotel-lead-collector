function normalized(value) {
  return String(value ?? '').trim().toLowerCase().replace(/\s+/g, ' ')
}

export function businessKey(business) {
  const source = normalized(
    business?.provider || business?.source || business?.sources?.join('+') || 'business',
  )
  const canonicalId = business?.id || business?.place_id
  if (canonicalId) return `${source}:id:${canonicalId}`
  if (business?.osm_type && business?.osm_id != null) {
    return `${source}:osm:${business.osm_type}/${business.osm_id}`
  }
  const mapsUrl = business?.maps_url || business?.google_maps_url
  if (mapsUrl) return `${source}:maps:${mapsUrl}`
  const name = normalized(business?.name)
  if (name && business?.latitude != null && business?.longitude != null) {
    return `${source}:location:${name}:${business.latitude}:${business.longitude}`
  }
  return `${source}:text:${name}:${normalized(business?.address)}`
}

export function displayBusinessValue(value, missing = 'Not Available') {
  return value === null || value === undefined || value === '' ? missing : value
}
