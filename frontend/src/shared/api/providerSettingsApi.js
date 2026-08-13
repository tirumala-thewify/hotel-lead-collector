const PROVIDER_SETTINGS_URL = 'http://127.0.0.1:8000/api/settings/providers/'

async function parseResponse(response) {
  let data
  try {
    data = JSON.parse(await response.text())
  } catch {
    throw new Error('The settings API returned an invalid response.')
  }
  if (!response.ok) {
    const providerError = data?.business_providers
    throw new Error((Array.isArray(providerError) ? providerError[0] : providerError)
      || data?.detail || 'Unable to save provider settings.')
  }
  return data
}

export async function fetchProviderSettings() {
  try {
    return await parseResponse(await fetch(PROVIDER_SETTINGS_URL))
  } catch (error) {
    if (error instanceof TypeError) {
      throw new Error('Cannot connect to the settings API.')
    }
    throw error
  }
}

export async function updateProviderSettings(values) {
  try {
    return await parseResponse(await fetch(PROVIDER_SETTINGS_URL, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(values),
    }))
  } catch (error) {
    if (error instanceof TypeError) {
      throw new Error('Cannot connect to the settings API.')
    }
    throw error
  }
}
