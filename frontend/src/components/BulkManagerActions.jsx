import { useState } from 'react'

const MAX_BULK_HOTELS = 10

function BulkManagerActions({ selectedHotels, providerSettings, running, summary, error, onRun }) {
  const [confirming, setConfirming] = useState(false)
  const count = selectedHotels.length
  const tooMany = count > MAX_BULK_HOTELS
  const apolloEnabled = Boolean(providerSettings?.apollo_enabled)
  const apolloConfigured = Boolean(providerSettings?.apollo_configured)
  const canRun = count > 0 && !tooMany && apolloEnabled && apolloConfigured && !running

  return (
    <>
      <div className="toolbar-action">
          <button type="button" className="bulk-manager-button" disabled={!canRun} onClick={() => setConfirming(true)}>
            {running ? 'Finding...' : 'Find Managers'}
          </button>
          <span className="action-note">{tooMany ? 'Maximum 10 hotels' : !apolloEnabled || !apolloConfigured ? 'Apollo not configured' : error}</span>
      </div>
      {summary && (
        <div className="bulk-summary" role="status">
          <strong>{summary.processed} hotels processed</strong>
          <span>{summary.found} had manager contacts</span>
          <span>{summary.not_found} had no matching contacts</span>
          <span>{summary.errors} failed</span>
        </div>
      )}
      {confirming && (
        <div className="confirmation-backdrop" role="presentation">
          <section className="confirmation-dialog" role="dialog" aria-modal="true" aria-labelledby="bulk-confirm-title">
            <h2 id="bulk-confirm-title">Confirm Apollo search</h2>
            <p>You are about to search manager contacts for {count} {count === 1 ? 'hotel' : 'hotels'} using Apollo.</p>
            <p>This may consume Apollo credits.</p>
            <div className="confirmation-actions">
              <button type="button" onClick={() => setConfirming(false)}>Cancel</button>
              <button type="button" className="bulk-manager-button" onClick={() => { setConfirming(false); onRun() }}>
                Continue
              </button>
            </div>
          </section>
        </div>
      )}
    </>
  )
}

export default BulkManagerActions
