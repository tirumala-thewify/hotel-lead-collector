import { useEffect, useState } from 'react'
import SecretInput from './components/SecretInput.jsx'
import {
  fetchProviderSettings,
  updateProviderSettings,
} from './services/providerSettingsService.js'

function SettingsPage() {
  const [settings, setSettings] = useState(null)
  const [googleKey, setGoogleKey] = useState('')
  const [geoapifyKey, setGeoapifyKey] = useState('')
  const [apolloKey, setApolloKey] = useState('')
  const [zoominfoKey, setZoominfoKey] = useState('')
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)

  const toggleProvider = (provider) => {
    const selected = settings.business_providers || [settings.hotel_provider]
    setSettings({ ...settings, business_providers: selected.includes(provider)
      ? selected.filter((item) => item !== provider) : [...selected, provider] })
  }

  const togglePeopleProvider = (provider) => {
    const selected = settings.people_providers || []
    setSettings({ ...settings, people_providers: selected.includes(provider)
      ? selected.filter((item) => item !== provider) : [...selected, provider] })
  }

  useEffect(() => {
    fetchProviderSettings().then(setSettings).catch((requestError) => setError(requestError.message))
  }, [])

  const save = async (values, clearKey) => {
    setSaving(true)
    setError('')
    setMessage('')
    try {
      const updated = await updateProviderSettings(values)
      setSettings(updated)
      clearKey()
      setMessage('Provider settings saved securely.')
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      setSaving(false)
    }
  }

  if (!settings) {
    return (
      <main className="settings-shell">
        <a className="back-link" href="/">← Back to business search</a>
        <div className={`status-card ${error ? 'error-status' : 'loading-status'}`}>
          {error || 'Loading provider settings...'}
        </div>
      </main>
    )
  }

  return (
    <main className="settings-shell">
      <a className="back-link" href="/">← Back to business search</a>
      <header className="settings-header">
        <h1>Settings</h1>
        <p>Configure optional data providers.</p>
      </header>

      {message && <div className="settings-notice success-notice">{message}</div>}
      {error && <div className="settings-notice error-status">{error}</div>}

      <section className="settings-card">
        <div className="settings-card-heading">
          <div><span className="section-kicker">Business data</span><h2>Business data providers</h2><p>Choose the sources available for nearby business searches.</p></div>
          <span className={`configured-badge ${settings.google_configured ? 'is-configured' : ''}`}>
            Google {settings.google_configured ? 'configured' : 'not configured'}
          </span>
        </div>
        <div className="provider-options">
          <label><input type="checkbox" value="openstreetmap"
            checked={settings.business_providers.includes('openstreetmap')}
            onChange={() => toggleProvider('openstreetmap')} />
            <span><strong>OpenStreetMap <em className="inline-status">Default</em></strong><small>Free default business discovery · No API key required</small></span>
          </label>
          <label><input type="checkbox" value="geoapify"
            checked={settings.business_providers.includes('geoapify')}
            disabled={!settings.geoapify_configured}
            onChange={() => toggleProvider('geoapify')} />
            <span><strong>Geoapify <em className="inline-status">{settings.geoapify_configured ? 'Configured' : 'Not configured'}</em></strong><small>Free tier / quota-based · API key required</small></span>
          </label>
          <label><input type="checkbox" value="google"
            checked={settings.business_providers.includes('google')}
            disabled={!settings.google_configured}
            onChange={() => toggleProvider('google')} />
            <span><strong>Google Places <em className="inline-status">Optional</em></strong><small>Currently supports Hotels & Resorts · API key required</small></span>
          </label>
        </div>
        <SecretInput id="geoapify-key" label="Geoapify API Key" value={geoapifyKey}
          onChange={setGeoapifyKey} placeholder={settings.geoapify_configured ? 'Saved key is hidden' : 'Enter API key'} />
        <p className="secret-help">Leave blank to keep the currently saved Geoapify key.</p>
        <SecretInput id="google-key" label="Google Places API Key" value={googleKey}
          onChange={setGoogleKey} placeholder={settings.google_configured ? 'Saved key is hidden' : 'Enter API key'} />
        <p className="secret-help">Leave blank to keep the existing saved key.</p>
        <button className="settings-save" disabled={saving} onClick={() => save({
          business_providers: settings.business_providers,
          ...(geoapifyKey ? { geoapify_api_key: geoapifyKey } : {}),
          ...(googleKey ? { google_api_key: googleKey } : {}),
        }, () => { setGeoapifyKey(''); setGoogleKey('') })}>Save Changes</button>
      </section>

      <section className="settings-card">
        <div className="settings-card-heading">
          <div><span className="section-kicker">People enrichment</span><h2>People enrichment providers</h2><p>Optional decision-maker searches.</p></div>
          <span className={`configured-badge ${settings.people_providers.length ? 'is-configured' : ''}`}>
            {settings.people_providers.length ? 'Enabled' : 'Disabled'}
          </span>
        </div>
        <label className="toggle-row">
          <input type="checkbox" checked={settings.people_providers.includes('apollo')}
            disabled={!settings.apollo_configured} onChange={() => togglePeopleProvider('apollo')} />
          <span><strong>Apollo</strong><small>{settings.apollo_configured ? 'Configured' : 'Not configured'}</small></span>
        </label>
        <label className="toggle-row">
          <input type="checkbox" checked={settings.people_providers.includes('zoominfo')}
            disabled={!settings.zoominfo_configured} onChange={() => togglePeopleProvider('zoominfo')} />
          <span><strong>ZoomInfo</strong><small>{settings.zoominfo_configured ? 'Configured' : 'Not configured'}</small></span>
        </label>
        <SecretInput id="apollo-key" label="Apollo API Key" value={apolloKey}
          onChange={setApolloKey} placeholder={settings.apollo_configured ? 'Saved key is hidden' : 'Enter API key'} />
        <p className="secret-help">Leave blank to keep the existing saved key. Saved keys are never returned.</p>
        <SecretInput id="zoominfo-key" label="ZoomInfo API Key" value={zoominfoKey}
          onChange={setZoominfoKey} placeholder={settings.zoominfo_configured ? 'Saved key is hidden' : 'Enter API key'} />
        <p className="secret-help">Leave blank to keep the existing saved key.</p>
        <button className="settings-save" disabled={saving} onClick={() => save({
          people_providers: settings.people_providers,
          ...(apolloKey ? { apollo_api_key: apolloKey } : {}),
          ...(zoominfoKey ? { zoominfo_api_key: zoominfoKey } : {}),
        }, () => { setApolloKey(''); setZoominfoKey('') })}>Save Changes</button>
      </section>
    </main>
  )
}

export default SettingsPage
