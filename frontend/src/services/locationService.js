const LOCATION_SEARCH_URL = 'http://127.0.0.1:8000/api/locations/search/'

export async function searchLocations(query) {
  const url = new URL(LOCATION_SEARCH_URL)
  url.searchParams.set('q', query)
  let response
  try {
    response = await fetch(url)
  } catch {
    throw new Error('Location search is temporarily unavailable.')
  }
  let data
  try {
    data = JSON.parse(await response.text())
  } catch {
    throw new Error('Location search returned an invalid response.')
  }
  if (!response.ok) {
    throw new Error(response.status === 400
      ? 'Enter at least two characters to search.'
      : 'Location search is temporarily unavailable.')
  }
  return data.results
}
