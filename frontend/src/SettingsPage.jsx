import { useEffect, useState } from 'react'
import SecretInput from './components/SecretInput.jsx'
import {
  fetchProviderSettings,
  updateProviderSettings,
} from './services/providerSettingsService.js'

function SettingsPage() {
  const [settings, setSettings] = useState(null)
  const [googleKey, setGoogleKey] = useState('')
  const [apolloKey, setApolloKey] = useState('')
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)

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
        <a className="back-link" href="/">← Back to hotel search</a>
        <div className={`status-card ${error ? 'error-status' : 'loading-status'}`}>
          {error || 'Loading provider settings...'}
        </div>
      </main>
    )
  }

  return (
    <main className="settings-shell">
      <a className="back-link" href="/">← Back to hotel search</a>
      <header className="settings-header">
        <h1>Settings</h1>
        <p>Configure optional data providers.</p>
      </header>

      {message && <div className="settings-notice success-notice">{message}</div>}
      {error && <div className="settings-notice error-status">{error}</div>}

      <section className="settings-card">
        <div className="settings-card-heading">
          <div><span className="section-kicker">Hotel data</span><h2>Hotel provider</h2><p>Choose the source used for nearby hotel searches.</p></div>
          <span className={`configured-badge ${settings.google_configured ? 'is-configured' : ''}`}>
            Google {settings.google_configured ? 'configured' : 'not configured'}
          </span>
        </div>
        <div className="provider-options">
          <label><input type="radio" name="hotel-provider" value="openstreetmap"
            checked={settings.hotel_provider === 'openstreetmap'}
            onChange={() => setSettings({ ...settings, hotel_provider: 'openstreetmap' })} />
            <span><strong>OpenStreetMap <em className="inline-status">Default</em></strong><small>Free · No API key required</small></span>
          </label>
          <label><input type="radio" name="hotel-provider" value="google"
            checked={settings.hotel_provider === 'google'}
            onChange={() => setSettings({ ...settings, hotel_provider: 'google' })} />
            <span><strong>Google Places <em className="inline-status">Optional</em></strong><small>API key required</small></span>
          </label>
        </div>
        <SecretInput id="google-key" label="Google Places API Key" value={googleKey}
          onChange={setGoogleKey} placeholder={settings.google_configured ? 'Saved key is hidden' : 'Enter API key'} />
        <p className="secret-help">Leave blank to keep the existing saved key.</p>
        <button className="settings-save" disabled={saving} onClick={() => save({
          hotel_provider: settings.hotel_provider,
          ...(googleKey ? { google_api_key: googleKey } : {}),
        }, () => setGoogleKey(''))}>Save Changes</button>
      </section>

      <section className="settings-card">
        <div className="settings-card-heading">
          <div><span className="section-kicker">People enrichment</span><h2>Apollo</h2><p>Optional decision-maker searches.</p></div>
          <span className={`configured-badge ${settings.apollo_configured ? 'is-configured' : ''}`}>
            Apollo {settings.apollo_configured ? 'configured' : 'not configured'}
          </span>
        </div>
        <label className="toggle-row">
          <input type="checkbox" checked={settings.apollo_enabled}
            onChange={(event) => setSettings({ ...settings, apollo_enabled: event.target.checked })} />
          <span><strong>Enable Apollo</strong><small>Disabled by default</small></span>
        </label>
        <SecretInput id="apollo-key" label="Apollo API Key" value={apolloKey}
          onChange={setApolloKey} placeholder={settings.apollo_configured ? 'Saved key is hidden' : 'Enter API key'} />
        <p className="secret-help">Leave blank to keep the existing saved key. Saved keys are never returned.</p>
        <button className="settings-save" disabled={saving} onClick={() => save({
          apollo_enabled: settings.apollo_enabled,
          ...(apolloKey ? { apollo_api_key: apolloKey } : {}),
        }, () => setApolloKey(''))}>Save Changes</button>
      </section>
    </main>
  )
}

export default SettingsPage
